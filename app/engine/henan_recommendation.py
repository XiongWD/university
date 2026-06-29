"""河南志愿推推荐引擎（design §3、§8）。

主链路：资格先行 → 位次风险 → 冲稳保分桶 → 48 志愿草案。
分桶分三层状态：
  1. eligibility_status（报考资格）：硬过滤（选科/语种/单科/体检），不通过→不可报
  2. admission_tier（录取档位）：搏/冲/稳/保/垫，纯位次匹配，用 clamp 阈值
  3. recommendation_status（推荐适配）：用户偏好（冷启动暂全设 recommended）
核心规则：位次差只影响 admission_tier，不得改变 eligibility_status。

注意：这是河南志愿推的新主链路，与旧 advisory（冲/中/稳）并行，旧链路保留不删。
"""
from __future__ import annotations

# ── 冷启动五档阈值（advantage = H参考位次 − R考生位次；位次数字越小=分数越高）──
# advantage < 0：目标门槛比考生高（更难录，属于冲/搏）
# advantage > 0：考生位次优于门槛（更易录，属于保/垫）
# 每档用 [比例边界, clamp(min绝对跨度, max绝对跨度)] 双重约束，避免高分段档位太挤、低分段太松
TIER_THRESHOLDS = {
    # 档位: (advantage下界比例, advantage上界比例, min绝对跨度, max绝对跨度)
    # 搏/冲有上限保护：差太远（超过20%R）的院校不判搏，归需人工复核（匹配度过低）
    "搏":  (-0.20,   -0.10, 300,    10000),   # -20%R ≤ advantage < -10%R，差最多20%
    "冲":  (-0.10,   -0.03, 300,    10000),   # -10%R ≤ advantage < -3%R，clamp[300,10000]
    "稳":  (-0.03,    0.05, 300,     6000),   # -3%R ≤ advantage < +5%R，clamp[300,6000]
    "保":  ( 0.05,    0.15, 1500,   20000),   # +5%R ≤ advantage < +15%R，clamp[1500,20000]
    "垫":  ( 0.15,    None, 3000,    None),   # advantage ≥ +15%R，min3000，不截断上界
}
# 档位顺序（用于排序/展示）
TIER_ORDER = ["搏", "冲", "稳", "保", "垫"]


def _clamp(value: float, lo: float | None, hi: float | None) -> float:
    """将 value 限制在 [lo, hi] 区间（None 表示不限）。"""
    if lo is not None and value < lo:
        return lo
    if hi is not None and value > hi:
        return hi
    return value


def classify_admission_tier(student_rank: int, adjusted_rank: int) -> str:
    """根据考生位次与参考录取位次，判定录取档位（搏/冲/稳/保/垫）。

    advantage = adjusted_rank − student_rank（>0 表示考生优于门槛）。
    每档的 advantage 区间由比例边界 ×R 决定，并对区间宽度做 clamp：
      - 高分段(R小)：比例区间过窄 → 扩展到 min_gap（避免档位太挤）
      - 低分段(R大)：比例区间过宽 → 压缩到 max_gap（避免档位太松）
    分界线从稳档两侧向外推导，保证各档连续不重叠。
    """
    advantage = adjusted_rank - student_rank
    R = student_rank
    # 稳档中心 = advantage 0。各档分界线 = 比例×R，clamp 到绝对跨度
    # 冲/搏（advantage<0，门槛更高）：分界线负向
    # 保/垫（advantage>0，考生更优）：分界线正向

    def clamped_boundary(ratio: float, min_gap: float | None, max_gap: float | None, sign: int) -> float:
        """计算分界线 = ratio×R，clamp 使其绝对值在 [min_gap, max_gap]。"""
        raw = ratio * R
        boundary = abs(raw)
        if max_gap is not None:
            boundary = min(boundary, max_gap)
        if min_gap is not None:
            boundary = max(boundary, min_gap)
        return sign * boundary

    # 各档分界线（从稳档向外，保证连续不重叠）
    # 冲稳分界 = -3%R；稳保 = +5%R；保垫 = +15%R；搏冲 = -10%R；搏下界 = -20%R
    sprint_stable = clamped_boundary(0.03, 300, 10000, -1)
    stable_safe = clamped_boundary(0.05, 300, 6000, +1)
    safe_fallback = clamped_boundary(0.15, 1500, 20000, +1)
    reach_sprint = clamped_boundary(0.10, None, None, -1)       # 搏/冲分界
    reach_floor = clamped_boundary(0.20, 300, 10000, -1)        # 搏档下界，差超20%R不再判搏

    # advantage < reach_floor（差太远，匹配度过低）→ 返回特殊标记，调用方归"需人工复核"
    if advantage < reach_floor:
        return "需人工复核"
    if advantage < reach_sprint:
        return "搏"
    if advantage < sprint_stable:
        return "冲"
    if advantage < stable_safe:
        return "稳"
    if advantage < safe_fallback:
        return "保"
    return "垫"


def _lookup_subject_score(profile: dict, subject: str) -> int | None:
    scores = profile.get("subject_scores_detail") or {}
    if subject in scores:
        return scores[subject]
    if subject in {"外语", "英语"}:
        return scores.get("外语")
    return None


def _classify_language_restriction(profile: dict, group) -> dict:
    """语种限制结构化分类（日语考生场景）：用于卡片明确标注。

    返回 {level, note}：
    - hard_blocked: 要求英语语种/白名单不含考生语种 → 录取不可报
    - soft_warning: 已明确公共外语不含考生日语 → 可录取但有英语适应风险
    - missing_data: 公共外语语种未提供 → 无法确认入学后语种适配
    - none: 无限制
    """
    lang = profile.get("exam_foreign_language")
    if lang == "英语":
        return {"level": "none", "note": ""}
    # 硬阻：要求英语或白名单不含考生语种
    if group.required_exam_language == "英语":
        return {"level": "hard_blocked", "note": f"要求英语语种，{lang}考生不可录取"}
    accepted = group.accepted_exam_languages or []
    if accepted and lang not in accepted:
        return {"level": "hard_blocked", "note": f"仅接受{'/'.join(accepted)}，{lang}考生不可录取"}
    # 软警告：不限语种但公共外语明确不含考生日语
    pubfl = group.public_foreign_languages or []
    if lang == "日语" and "日语" not in pubfl:
        if pubfl:
            return {"level": "soft_warning", "note": f"公共外语仅开{'/'.join(pubfl)}，可录取但入学后英语课程需适应"}
        return {"level": "missing_data", "note": "未提供公共外语语种数据，暂无法确认日语考生入学后的语种适配"}
    return {"level": "none", "note": ""}


def check_henan_eligibility(profile: dict, group) -> tuple[bool, list[str], list[str]]:
    """资格先行（design §8.1、§8.2）：首选/再选/语种/体检/专项硬过滤 + 日语软风险提示。

    返回 (eligible, blocked_reasons, soft_warnings)。
    blocked 为硬阻断（不可报）；warnings 为软风险（可报但需提示，如日语公共外语适应）。
    """
    blocked: list[str] = []
    warnings: list[str] = []

    # 首选科目（物理/历史）
    if group.primary_subject_requirement and profile.get("primary_subject") != group.primary_subject_requirement:
        blocked.append(f"首选科目要求{group.primary_subject_requirement}")

    # 再选科目（3+1+2 的"2"）
    require = (group.elective_subject_requirement or {}).get("require", [])
    for subject in require:
        if subject not in profile.get("elective_subjects", []):
            blocked.append(f"再选科目要求包含{subject}")

    # 语种硬限制：要求英语语种 → 日语考生不可报（design §3.4、§8.2）
    if group.required_exam_language == "英语" and profile.get("exam_foreign_language") != "英语":
        blocked.append("要求英语语种，日语考生不可报")

    # 接受语种白名单：非空且不含考生语种 → 不可报
    accepted = group.accepted_exam_languages or []
    if accepted and profile.get("exam_foreign_language") not in accepted:
        blocked.append(f"外语语种需为{'/'.join(accepted)}，{profile.get('exam_foreign_language')}考生不可报")

    # 日语提示：已知仅开英语时给适应风险；未知时给数据缺失提示（都不挡资格）
    if profile.get("exam_foreign_language") == "日语":
        pubfl = group.public_foreign_languages or []
        if pubfl and "日语" not in pubfl:
            warnings.append(
                f"英语适应风险：本专业可录取日语考生，但公共外语仅开{'/'.join(pubfl)}。"
                "入学后英语课程、四六级、部分学位/留学要求需自行适应，建议英语基础尚可者填报"
            )
        elif not pubfl:
            warnings.append("语种数据缺失：未提供公共外语语种，暂无法确认日语考生入学后的课程语种适配")

    # 单科要求：缺分数或未达门槛都直接阻断
    for requirement in group.single_subject_requirements or []:
        subject = requirement.get("subject")
        min_score = requirement.get("min_score")
        if not subject or not isinstance(min_score, int):
            continue
        score = _lookup_subject_score(profile, subject)
        if subject == "英语" and profile.get("exam_foreign_language") != "英语":
            blocked.append(f"英语单科要求 {min_score} 分，非英语语种考生不符合")
            continue
        if score is None:
            blocked.append(f"缺少{subject}单科成绩，无法校验最低 {min_score} 分要求")
            continue
        if score < min_score:
            blocked.append(f"{subject}单科 {score} 分，未达到最低 {min_score} 分要求")

    # 体检限制（design §8.2 扩展）：检查组级或计划级体检要求
    for restriction_text in [group.physical_restrictions or ""]:
        if not restriction_text:
            continue
        if "辨色力异常" in restriction_text and profile.get("color_vision") == "异常":
            blocked.append("辨色力异常不符招生要求")
        if "身高要求" in restriction_text:
            required_height = _parse_height_requirement(restriction_text)
            if required_height and profile.get("height", 0) < required_height:
                blocked.append(f"身高须达到{required_height}cm以上")
        if "视力要求" in restriction_text and profile.get("vision_corrected") is False:
            blocked.append("视力不符招生要求")

    # 专项类型限制（design §8.2 扩展）
    spec_type = group.special_qualification_type or ""
    if spec_type:
        student_quals = profile.get("special_qualifications", [])
        if spec_type == "高校专项" and "高校专项" not in student_quals:
            blocked.append("须具备高校专项计划资格")
        elif spec_type == "地方专项" and "地方专项" not in student_quals:
            blocked.append("须具备地方专项计划资格")
        elif spec_type == "国家专项" and "国家专项" not in student_quals:
            blocked.append("须具备国家专项计划资格")
        elif spec_type == "公费师范" and "公费师范" not in student_quals:
            blocked.append("须具备公费师范生资格")
        elif spec_type == "定向医学生" and "定向医学生" not in student_quals:
            blocked.append("须具备定向医学生资格")

    return len(blocked) == 0, blocked, warnings


def _parse_height_requirement(text: str) -> int | None:
    """从体检限制文本解析身高要求（cm）。
    示例：'身高要求(160-)' → 160, '身高要求(170-185)' → 170
    """
    import re
    m = re.search(r"身高要求[（(](\d+)", text)
    if m:
        return int(m.group(1))
    return None


def classify_henan_bucket(student_rank: int, historical_rank: int | None, policy_mode: str) -> str:
    """按绝对位次差分桶（design §8.3 基础口径，与 classify_group_bucket 统一判档口径）。

    复用 classify_admission_tier 的五档 clamp 阈值，policy_mode 仅作语义占位。
    遗留函数：仅单测引用，生产主链路用 classify_group_bucket。
    """
    if historical_rank is None or historical_rank <= 0 or student_rank <= 0:
        return "不推荐"
    return classify_admission_tier(student_rank, historical_rank)


def estimate_admission_probability(bucket: str, rank_gap_ratio: float | None, confidence: float) -> float:
    """估算投档成功率（0-1，problem1：成功率可见）。

    基于 rank_gap_ratio（考生位次相对参考位次偏离）分段校准，覆盖冲稳保三档：
    - 保（ratio < -0.10）：位次明显优于参考，成功率 92-99%
    - 稳（-0.10 ≤ ratio ≤ 0.03）：位次接近，成功率 60-92%
    - 冲（0.03 < ratio ≤ 0.15）：位次略靠后，成功率 25-60%
    ratio 越优概率越高，并按置信度衰减（confidence<0.7 打 0.85 折）。
    无 ratio（资格层/历史缺失）时返回 0。
    """
    if rank_gap_ratio is None:
        return 0.0
    r = rank_gap_ratio
    if bucket == "垫":
        # 兜底：考生位次远优于门槛，录取近乎必然
        return round(min(0.999, 0.99 + confidence * 0.005), 3) if confidence < 0.7 else 0.999
    if bucket == "保":
        # ratio 越负越稳：-0.10→92%，-0.30→99%
        prob = min(0.99, 0.92 + min(0.07, max(0.0, (-r - 0.10)) * 0.35))
    elif bucket == "稳":
        # -0.10→92%，0.03→60%（区间内线性）
        prob = 0.92 - (r - (-0.10)) / (0.03 - (-0.10)) * (0.92 - 0.60)
        prob = max(0.60, min(0.92, prob))
    elif bucket == "冲":
        # 0.03→60%，0.15→25%（区间内线性）
        prob = 0.60 - (r - 0.03) / (0.15 - 0.03) * (0.60 - 0.25)
        prob = max(0.25, min(0.60, prob))
    elif bucket == "搏":
        # 门槛比考生高 10% 以上：录取概率较低 5-15%
        prob = max(0.05, min(0.15, 0.15 - max(0.0, -r - 0.10) * 0.5))
    else:
        # 不推荐 / 需人工复核：资格未通过或数据不足
        return 0.0
    if confidence < 0.7:
        prob *= 0.85
    return round(prob, 3)


def classify_group_bucket(
    student_rank: int,
    adjusted_rank: int | None,
    has_2025_history: bool,
    has_2026_plan: bool,
    has_verified_group: bool,
    confidence: float,
) -> dict:
    """专业组级三层状态判定（design §8.3 重构）。

    返回 dict：
      eligibility_status: eligible | ineligible | uncertain  （报考资格，硬过滤）
      admission_tier:     搏 | 冲 | 稳 | 保 | 垫 | null        （录取档位，位次匹配）
      recommendation_status: recommended | conditional | not_recommended
      bucket: 中文档位（eligible→admission_tier，ineligible→"不推荐"，uncertain→"需人工复核"）

    核心规则：位次差只影响 admission_tier，不得改变 eligibility_status。
    """
    # ── 第1层：报考资格（硬过滤）──
    if not has_2026_plan or not has_verified_group:
        return {"eligibility_status": "ineligible", "admission_tier": None,
                "recommendation_status": "not_recommended", "bucket": "不推荐"}
    if adjusted_rank is None or adjusted_rank <= 0 or student_rank <= 0:
        return {"eligibility_status": "uncertain", "admission_tier": None,
                "recommendation_status": "conditional", "bucket": "需人工复核"}

    # ── 第2层：录取档位（位次匹配，五档 clamp 阈值）──
    tier = classify_admission_tier(student_rank, adjusted_rank)
    # 差太远（advantage < -20%R）→ 匹配度过低，归需人工复核而非搏档（避免搏档泛滥）
    if tier == "需人工复核":
        return {"eligibility_status": "uncertain", "admission_tier": None,
                "recommendation_status": "conditional", "bucket": "需人工复核"}

    # ── 第3层：推荐适配（冷启动：资格通过即 recommended）──
    return {"eligibility_status": "eligible", "admission_tier": tier,
            "recommendation_status": "recommended", "bucket": tier}


def get_bucket_quota(policy_count: int, strategy: str, profile: dict) -> dict[str, tuple[int, int]]:
    """48 志愿草案的冲稳保数量配额（design §8.4）。

    均衡档贴合河南省教育考试院官方「黄金比 3:4:3」建议（冲10-15/稳~20/保13-18）。
    比例是产品默认策略，非官方强制。历史类+日语默认保守；自动策略按科类/语种选择。
    返回各档 (下限, 上限)。
    """
    # 非 48 志愿政策时按比例缩放
    if policy_count != 48:
        ratio = policy_count / 48

        def scaled(low: int, high: int) -> tuple[int, int]:
            return (max(0, round(low * ratio)), max(0, round(high * ratio)))
    else:
        def scaled(low: int, high: int) -> tuple[int, int]:
            return (low, high)

    # 自动策略：历史类+日语 → 保守；否则均衡（design §8.4）
    if strategy == "自动" and profile.get("track") == "历史类" and profile.get("exam_foreign_language") == "日语":
        strategy = "保守"
    elif strategy == "自动":
        strategy = "均衡"

    if strategy == "保守":
        return {"冲": scaled(6, 8), "稳": scaled(22, 26), "保": scaled(14, 18)}
    if strategy == "积极":
        return {"冲": scaled(12, 16), "稳": scaled(18, 22), "保": scaled(8, 12)}
    # 均衡：贴合河南省教育考试院官方"黄金比 3:4:3"建议（冲10-15/稳~20/保13-18）
    return {"冲": scaled(12, 15), "稳": scaled(18, 20), "保": scaled(13, 15)}


# 冲稳保排序权重（冲在前，保次之，不推荐最后，需人工复核在末尾）
_BUCKET_ORDER = {"冲": 0, "稳": 1, "保": 2, "不推荐": 3, "需人工复核": 4}


def build_48_volunteer_draft(candidates: list[dict], policy) -> dict:
    """生成 48 志愿草案（design §3.3、§8.4）。

    每个志愿单位是「院校专业组」，不是学校或单个专业。按冲→稳→保排序后裁剪到
    政策规定的平行志愿数量。组内专业不超过 major_count_per_group。
    """
    ordered = sorted(
        candidates,
        key=lambda x: _BUCKET_ORDER.get(x.get("bucket"), 9),
    )
    items = []
    for item in ordered[: policy.parallel_volunteer_count]:
        majors = item.get("selected_majors", [])
        if len(majors) > policy.major_count_per_group:
            majors = majors[: policy.major_count_per_group]
        items.append({**item, "volunteer_unit": "院校专业组", "selected_majors": majors})
    return {"policy_count": policy.parallel_volunteer_count, "items": items}


def build_henan_candidates(profile: dict) -> list[dict]:
    """真实候选生成器（design §8、D2、D4）。

    加载 2026 专业组+计划+历史，逐组做资格过滤、计划校验、历史位次、冲稳保分桶。
    不再返回空占位。首页推荐与目标评估共同消费此候选集。

    分桶规则：
    - 资格层不通过 → 不推荐
    - 缺 2026 计划(plan_count=0 或非 verified) → 需人工复核/不推荐
    - 缺 verified 历史位次 → 即使位次优也 需人工复核（不得稳/保）
    - classify_group_bucket 按位次差比分桶
    """
    from pathlib import Path

    from app.loader.henan_data_loader import (
        find_best_historical_baseline,
        load_city_living_cost,
        load_henan_admission_history,
        load_henan_enrollment_plans,
        load_henan_program_groups,
        load_henan_universities,
    )
    from app.loader.henan_scope import (
        filter_henan_history_regular_history,
        filter_henan_history_regular_scope,
    )

    if profile.get("source_province") not in (None, "河南"):
        raise ValueError("河南志愿推仅支持河南考生")
    if profile.get("track") not in (None, "历史类"):
        raise ValueError("河南志愿推当前仅支持2026历史类普通本科批")

    seed_dir = Path("data/seed")
    groups = load_henan_program_groups(seed_dir)
    plans = load_henan_enrollment_plans(seed_dir)
    history = load_henan_admission_history(seed_dir)
    universities = load_henan_universities(seed_dir)
    city_monthly_mid = load_city_living_cost(seed_dir)
    groups, plans = filter_henan_history_regular_scope(groups, plans)
    history = filter_henan_history_regular_history(history, groups)

    # 院校属性索引（design §4.1）：ownership / province / city / tags → 区分公办民办、省内省外
    unis_by_code: dict[str, object] = {u.school_code: u for u in universities}

    # 按 (school_code, group_code, track, batch) 聚合计划
    plans_by_key: dict[tuple, list] = {}
    for plan in plans:
        plans_by_key.setdefault(
            (plan.school_code, plan.major_group_code, plan.track, plan.batch), []
        ).append(plan)
    history_rows_by_key: dict[tuple, list] = {}
    for row in history:
        history_rows_by_key.setdefault(
            (row.school_code, row.track, getattr(row, "batch", "本科批")), []
        ).append(row)

    candidates: list[dict] = []
    student_rank = profile.get("rank") or 0

    for group in groups:
        if group.track != profile.get("track"):
            continue

        # 资格层
        ok, blocked, warnings = check_henan_eligibility(profile, group)

        # 2026 计划校验
        group_plans = plans_by_key.get(
            (group.school_code, group.major_group_code, group.track, group.batch), []
        )
        has_2026_plan = any(p.plan_count > 0 and p.review_status == "verified" for p in group_plans)
        has_verified_group = group.review_status == "verified"
        plan_count = sum(p.plan_count for p in group_plans)

        # 历史位次基线
        baseline = find_best_historical_baseline(
            history,
            school_code=group.school_code,
            group_code=group.major_group_code,
            major_names=group.included_majors,
            track=group.track,
            batch=group.batch,
        )
        has_verified_history = baseline is not None and baseline.get("review_status") == "verified"
        missing_data_items: list[str] = []
        if not has_verified_group:
            missing_data_items.append("2026专业组数据未核验")
        if not has_2026_plan:
            missing_data_items.append("2026河南招生计划缺失或未核验")
        if baseline is None:
            same_school_history_rows = history_rows_by_key.get(
                (group.school_code, group.track, group.batch),
                [],
            )
            if same_school_history_rows:
                missing_data_items.append("同校历史存在，但缺少已核验录取位次")
            else:
                missing_data_items.append("缺少同校同科类同批次历史录取位次")

        if not ok:
            bucket = "不推荐"
            eligibility_status = "ineligible"
            admission_tier = None
            recommendation_status = "not_recommended"
            data_confidence = "low"
        elif baseline is None or not has_verified_history:
            # design D2/I1：资格通过但缺 verified 历史基线 → 需人工复核（不得稳/保，也不混为不推荐）
            bucket = "需人工复核"
            eligibility_status = "uncertain"
            admission_tier = None
            recommendation_status = "conditional"
            data_confidence = "low"
        else:
            # 三层状态判定（有 verified 历史基线才进入风险层）
            verdict = classify_group_bucket(
                student_rank=student_rank,
                adjusted_rank=baseline["adjusted_min_rank"],
                has_2025_history=has_verified_history
                    and baseline.get("data_granularity") in ("major", "major_group", "major_group_trend"),
                has_2026_plan=has_2026_plan,
                has_verified_group=has_verified_group,
                confidence=group.confidence,
            )
            bucket = verdict["bucket"]
            eligibility_status = verdict["eligibility_status"]
            admission_tier = verdict["admission_tier"]
            recommendation_status = verdict["recommendation_status"]
            # 数据置信度：有专业组级 verified 历史为 high，校级/单年为 medium，无历史为 low
            data_confidence = "high" if baseline.get("data_granularity") in ("major", "major_group", "major_group_trend") else ("medium" if baseline else "low")
            # 缺计划或未核验组的可达档位降级为需人工复核
            if bucket in {"搏", "冲", "稳", "保", "垫"} and (not has_2026_plan or not has_verified_group):
                bucket = "需人工复核"
                eligibility_status = "uncertain"
                admission_tier = None

        # —— 费用与学校性质（design §4.4/§4.5，问题3/问题4）——
        lead_plan = group_plans[0] if group_plans else None
        tuition = getattr(lead_plan, "tuition", None) if lead_plan else None
        accommodation = getattr(lead_plan, "accommodation", None) if lead_plan else None
        uni = unis_by_code.get(group.school_code)
        school_ownership = getattr(uni, "ownership", "") if uni else ""
        school_province = getattr(uni, "province", "") or (getattr(lead_plan, "school_origin_province", "") if lead_plan else "")
        school_city = getattr(uni, "city", "") if uni else ""
        school_tags = getattr(uni, "tags", []) if uni else []
        school_level = getattr(uni, "school_level", "") if uni else ""
        is_henan_local = bool(getattr(lead_plan, "is_henan_local_school", False)) or (school_province == "河南")
        # 生活费：按学校城市匹配月综合成本中位×12，缺失回退全国基准(月2000)
        monthly_mid = city_monthly_mid.get(school_city)
        if monthly_mid is None:
            # 城市名未直接命中时尝试按省名兜底（取该省任一已知城市），再不行用全国基准
            monthly_mid = 2000
        living_cost_per_year = monthly_mid * 12
        years = getattr(lead_plan, "school_system_years", None) or 4
        tuition_annual = tuition or 0
        # 住宿费：官方数据缺失时用全国中位估算(~1200)并标注 estimated，避免合计为空
        ACCOMMODATION_ESTIMATE = 1200
        accommodation_is_estimate = accommodation is None
        accommodation_annual = accommodation if accommodation else ACCOMMODATION_ESTIMATE
        four_year_total = (tuition_annual + accommodation_annual + living_cost_per_year) * years

        # —— 冲稳保计算明细（问题2）：位次差比 + 阈值 + 成功率 + 本组计算链 ——
        adjusted_min_rank = baseline.get("adjusted_min_rank") if baseline else None
        rank_gap_ratio = (
            round((student_rank - adjusted_min_rank) / adjusted_min_rank, 4)
            if (adjusted_min_rank and adjusted_min_rank > 0 and student_rank > 0)
            else None
        )
        # 投档成功率（problem1）：基于位次差比与档位分段校准
        admission_probability = estimate_admission_probability(bucket, rank_gap_ratio, group.confidence)
        bucket_detail = {
            "student_rank": student_rank if student_rank > 0 else None,
            "adjusted_min_rank": adjusted_min_rank,
            "rank_gap_ratio": rank_gap_ratio,
            "admission_probability": admission_probability,
            "baseline_year": baseline.get("year") if baseline else None,
            "baseline_granularity": baseline.get("data_granularity") if baseline else None,
            "confidence": group.confidence,
            "thresholds": {
                "搏": "参考位次比考生高 10%R 以上（门槛更高，搏一搏）",
                "冲": "参考位次比考生高 3%~10%R（clamp 300~10000名）",
                "稳": "考生与参考位次基本匹配，-3%~+5%R（clamp 300~6000名）",
                "保": "考生位次优于参考 5%~15%R（clamp 1500~20000名）",
                "垫": "考生位次优于参考 15%R 以上（兜底，min 3000名）",
                "不推荐": "资格层未通过（选科/语种/单科/体检不符）",
            },
            "formula": "advantage = 参考位次 − 考生位次；advantage>0 表示考生更易录取",
        }

        candidates.append({
            "volunteer_unit": "院校专业组",
            "school_name": group.school_name,
            "school_code": group.school_code,
            "major_group_code": group.major_group_code,
            "major_group_name": group.major_group_name,
            "major_name": group.included_majors[0] if group.included_majors else "",
            "selected_majors": group.included_majors[:6],
            "track": group.track,
            "batch": group.batch,
            "bucket": bucket,
            # 三层状态（design §8.3 重构）
            "eligibility_status": eligibility_status,
            "admission_tier": admission_tier,
            "recommendation_status": recommendation_status,
            "data_confidence": data_confidence,
            "group_bucket": bucket,
            "major_bucket": bucket,
            "qualified": ok,
            "blocked_reasons": blocked,
            "warnings": warnings,
            "plan_count": plan_count,
            "campus": group_plans[0].campus if group_plans else "",
            # 费用（问题3）：真实学费/住宿费 + 城市生活费 + 4年合计
            "tuition": tuition_annual if tuition else None,
            "accommodation": accommodation_annual,
            "accommodation_is_estimate": accommodation_is_estimate,
            "living_cost_per_year": living_cost_per_year,
            "school_system_years": years,
            "four_year_total": four_year_total,
            # 学校性质（问题4）：公办/民办/中外 + 省内/省外 + 985/211
            "school_ownership": school_ownership,
            "school_province": school_province,
            "school_city": school_city,
            "school_level": school_level,
            "school_tags": school_tags,
            "is_henan_local": is_henan_local,
            # 冲稳保计算明细（问题2）+ 投档成功率（problem1）
            "admission_probability": admission_probability,
            "bucket_detail": bucket_detail,
            "accepted_exam_languages": group.accepted_exam_languages,
            "public_foreign_languages": group.public_foreign_languages,
            # 语种限制结构化标注（日语考生场景）：hard_blocked=不可报 / soft_warning=可报但英语适应风险 / none
            "language_restriction": _classify_language_restriction(profile, group),
            "single_subject_requirements": group.single_subject_requirements,
            "physical_restrictions": group.physical_restrictions or (group_plans[0].physical_restrictions if group_plans else ""),
            "special_qualification_type": group.special_qualification_type or (group_plans[0].special_qualification_type if group_plans else ""),
            "missing_data_items": missing_data_items,
            "review_status": "verified" if (has_verified_group and has_2026_plan) else "needs_review",
            "bucket_reason": "按2026河南专业组、招生计划、选科语种和历史位次综合判断",
            "data_evidence": {
                "scope": {
                    "province": "河南",
                    "year": 2026,
                    "track": group.track,
                    "batch": group.batch,
                },
                "verification": {
                    "group_review_status": group.review_status,
                    "group_confidence": group.confidence,
                    "has_verified_group": has_verified_group,
                    "has_verified_plan": has_2026_plan,
                    "has_verified_history": has_verified_history,
                    "baseline_year": baseline.get("year") if baseline else None,
                    "baseline_granularity": baseline.get("data_granularity") if baseline else None,
                    "adjusted_min_rank": baseline.get("adjusted_min_rank") if baseline else None,
                    "missing_data_items": missing_data_items,
                },
                "source_trace": {
                    "source_name": group.source_name,
                    "source_url": group.source_url,
                    "source_api_endpoint": group.source_api_endpoint,
                    "source_params": group.source_params,
                    "source_response_checksum": group.source_response_checksum,
                },
                "official_gap": {
                    "official_catalog_available": False,
                    "reason": "当前仍缺河南 2026 官方全量专业目录结构化源",
                },
            },
        })
    return candidates


# 策略中文名映射（前端档位选择 → 48 志愿草案配额策略）
_STRATEGY_LABEL = {"自动": "自动", "积极": "积极", "保守": "保守", "均衡": "均衡"}


def sort_henan_bucket_candidates(candidates: list[dict], profile: dict) -> list[dict]:
    """按固定优先级对同一档位候选排序。

    优先级是字典序：省内 → 公办 → 专业匹配 → 日语适配 → 成功率 → 费用。
    后一层只在前一层相同的候选之间比较。
    """
    prefer_local = bool(profile.get("prefer_local"))
    prefer_public = bool(profile.get("prefer_public"))
    exam_language = profile.get("exam_foreign_language") or "英语"
    interest_majors = profile.get("interest_majors") or []
    prefer_same_language_major = bool(profile.get("prefer_same_language_major"))
    implicit_language_interest = (
        [exam_language]
        if prefer_same_language_major and exam_language != "英语" and not interest_majors
        else []
    )

    def _text_values(c: dict) -> list[str]:
        values: list[str] = []
        for key in ("major_name", "major_group_name"):
            value = c.get(key)
            if value:
                values.append(str(value))
        values.extend(str(x) for x in (c.get("selected_majors") or []) if x)
        return values

    def _major_match_score(c: dict) -> float:
        interests = [str(x).strip() for x in [*interest_majors, *implicit_language_interest] if str(x).strip()]
        if not interests:
            return 0.0
        texts = _text_values(c)
        score = 0.0
        for interest in interests:
            for text in texts:
                if interest == text:
                    score = max(score, 1.0)
                elif interest in text or text in interest:
                    score = max(score, 0.75)
        return score

    def _language_fit_score(c: dict) -> float:
        restriction = c.get("language_restriction") or {}
        level = restriction.get("level")
        if level == "hard_blocked":
            return -1.0
        if exam_language != "英语" and level == "soft_warning":
            return -0.35
        if exam_language != "英语" and level == "missing_data":
            return 0.0
        if exam_language != "英语" and level == "none":
            return 0.25
        return 0.0

    def _probability(c: dict) -> float:
        detail = c.get("bucket_detail") or {}
        value = c.get("admission_probability")
        if value is None:
            value = detail.get("admission_probability")
        return float(value or 0.0)

    def _cost(c: dict) -> float:
        value = c.get("four_year_total")
        return float(value) if isinstance(value, (int, float)) and value > 0 else 999999999.0

    def _sort_key(c: dict):
        local_rank = 0 if (prefer_local and c.get("is_henan_local")) else 1
        public_rank = 0 if (prefer_public and c.get("school_ownership") == "公办") else 1
        return (
            local_rank,
            public_rank,
            -_major_match_score(c),
            -_language_fit_score(c),
            -_probability(c),
            _cost(c),
            c.get("school_name", ""),
        )

    return sorted(candidates, key=_sort_key)


def build_henan_volunteer_table(
    profile: dict,
    candidates: list[dict],
    policy,
) -> dict:
    """生成策略感知的 48 志愿草案（design §8.4，问题1：让 strategy 真正生效）。

    candidates 是 build_henan_candidates 的全量候选（含资格层判定与分桶）。
    policy 是 HenanAdmissionPolicy（parallel_volunteer_count / major_count_per_group）。
    按策略取配额 → 仅保留 冲/稳/保 可达候选 → 每档排序(位次/成功率)+偏好(省内/公办)
    → 冲→稳→保 拼接 → 每档裁剪到配额上限 → 组内专业≤major_count_per_group。

    profile 排序/偏好参数：
      sort_mode: "rank"(默认，位次差比升序) | "probability"(成功率降序)
      prefer_local: True 时省内院校同分优先
      prefer_public: True 时公办院校同分优先
    """
    strategy = _STRATEGY_LABEL.get(profile.get("strategy") or "自动", "自动")
    policy_count = getattr(policy, "parallel_volunteer_count", 48) or 48
    major_cap = getattr(policy, "major_count_per_group", 6) or 6
    quota = get_bucket_quota(policy_count, strategy, profile)
    prefer_local = bool(profile.get("prefer_local"))
    prefer_public = bool(profile.get("prefer_public"))
    sort_mode = profile.get("sort_mode") or "rank"

    # 仅可达候选进入志愿表（冲/稳/保）；不推荐/需人工复核不进表
    reachable = [c for c in candidates if c.get("bucket") in {"冲", "稳", "保"}]
    by_bucket: dict[str, list[dict]] = {"冲": [], "稳": [], "保": []}
    for c in reachable:
        by_bucket.setdefault(c["bucket"], []).append(c)

    ordered: list[dict] = []
    used: dict[str, int] = {}
    for bucket in ("冲", "稳", "保"):
        low, high = quota.get(bucket, (0, 0))
        picked = sort_henan_bucket_candidates(by_bucket.get(bucket, []), profile)[:high]
        used[bucket] = len(picked)
        ordered.extend(picked)

    items = []
    for c in ordered:
        majors = c.get("selected_majors", []) or []
        if len(majors) > major_cap:
            majors = majors[:major_cap]
        items.append({**c, "volunteer_unit": "院校专业组", "selected_majors": majors})

    return {
        "policy_count": policy_count,
        "strategy_used": strategy,
        "sort_mode": sort_mode,
        "prefer_local": prefer_local,
        "prefer_public": prefer_public,
        "quota": {b: list(quota.get(b, (0, 0))) for b in ("冲", "稳", "保")},
        "used": used,
        "total": len(items),
        "items": items,
    }
