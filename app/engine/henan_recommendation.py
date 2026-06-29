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

import csv
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=6)
def _load_score_rank_entries(year: int, track: str = "历史类") -> tuple[tuple[int, int], ...]:
    """从一分一段表 CSV 加载指定年份/科类的 (score, cumulative_rank) 列表（按分数降序）。

    用于年度归一化的等位分换算。返回 tuple 便于 lru_cache + 排序后二分查找。
    文件：data/datasets/henan_{year}_score_rank.csv（河南历史类）。
    """
    path = Path("data/datasets") / f"henan_{year}_score_rank.csv"
    if not path.exists():
        return ()
    rows: list[tuple[int, int]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("综合") != track or r.get("省级行政区") != "河南":
                continue
            try:
                score = int(r["最高分"])
                cumu = int(r["累计"])
                rows.append((score, cumu))
            except (ValueError, KeyError):
                continue
    rows.sort(key=lambda x: x[0], reverse=True)  # 分数降序（位次升序）
    return tuple(rows)


def _rank_to_score(entries: tuple[tuple[int, int], ...], rank: int) -> int | None:
    """位次 → 分数（就近匹配，无插值，精度±0.5分）。仅作诊断/展示用。"""
    if not entries or rank <= 0:
        return None
    best_score, best_diff = None, None
    for score, cumu in entries:
        diff = abs(cumu - rank)
        if best_diff is None or diff < best_diff:
            best_score, best_diff = score, diff
    return best_score


def _score_to_rank(entries: tuple[tuple[int, int], ...], score: int) -> int | None:
    """分数 → 位次（就近匹配）。仅作诊断/展示用。"""
    if not entries or score <= 0:
        return None
    best_rank, best_diff = None, None
    for s, cumu in entries:
        diff = abs(s - score)
        if best_diff is None or diff < best_diff:
            best_rank, best_diff = cumu, diff
    return best_rank


# 同口径年份（3+1+2 历史类、合并本科批）：仅这些年份之间可做百分位归一化
# 2024 是传统文理科口径（文科≠历史类、一本/二本≠合并本科批），口径断裂，不参与
_SAME_CALIBER_YEARS = {2025, 2026}


def normalize_rank_to_target_year(
    history_rank: int, history_year: int, target_year: int = 2026
) -> dict:
    """把历史年份的录取位次，归一化到目标年份(2026)的等效口径。

    核心方法：**累计百分位映射**（保持考生在群体中的相对竞争位置），而非同分跨年映射。
      历史位次 R_hist → 历史百分位 P = R_hist / N_hist → 目标年等效位次 R_target = P × N_target

    为什么用百分位而非"同分映射"：
      同分映射（历史位次→历史分数→目标年同分位次）保留了裸分，会被试卷难度污染——
      2025年500分与2026年500分不代表相同竞争水平。百分位才保持相对位置。

    返回 dict（保留原始值+归一化方法+置信度，不静默回退）：
      normalized_rank: 用于判档的归一化后位次
      raw_rank: 历史原始位次（不被覆盖）
      same_score_reference_rank: 同分跨年映射位次（仅诊断，不进判档）
      method: "percentile" | "raw" （百分位映射 | 口径不一致降级用原始）
      confidence: "high" | "medium" | "low"
      fallback_reason: 降级原因（仅 method="raw" 时有值）
    """
    result = {
        "normalized_rank": history_rank, "raw_rank": history_rank,
        "same_score_reference_rank": None, "method": "raw",
        "confidence": "low", "fallback_reason": None,
    }

    if history_rank <= 0 or history_year == target_year:
        result["method"] = "raw"
        result["confidence"] = "high"  # 同年无需归一化
        result["fallback_reason"] = "同年位次无需归一化"
        return result

    n_hist = _total_candidates(history_year)
    n_target = _total_candidates(target_year)

    # 口径校验：仅同口径年份（3+1+2历史类）做百分位归一化
    if history_year not in _SAME_CALIBER_YEARS or target_year not in _SAME_CALIBER_YEARS:
        result["method"] = "raw"
        result["confidence"] = "low"
        result["fallback_reason"] = f"{history_year}与{target_year}年口径不一致（如旧高考文科vs新高考历史类），使用原始位次"
        # 仍计算同分映射作诊断参考
        result["same_score_reference_rank"] = _same_score_map(history_rank, history_year, target_year)
        return result

    if not n_hist or not n_target:
        result["method"] = "raw"
        result["confidence"] = "low"
        result["fallback_reason"] = f"缺{history_year}或{target_year}年考生规模数据"
        return result

    # 主路径：累计百分位映射 R_target = R_hist / N_hist × N_target
    percentile = history_rank / n_hist
    normalized = round(percentile * n_target)
    # 边界约束：1 ≤ normalized ≤ N_target
    normalized = max(1, min(normalized, n_target))

    result["normalized_rank"] = normalized
    result["method"] = "percentile"
    result["confidence"] = "high"
    # 同分映射作诊断（对比两种口径差异，差越大置信越低）
    result["same_score_reference_rank"] = _same_score_map(history_rank, history_year, target_year)
    return result


def _same_score_map(history_rank: int, history_year: int, target_year: int) -> int | None:
    """同分跨年映射（诊断用）：历史位次→历史分数→目标年同分位次。不进判档。"""
    hist_entries = _load_score_rank_entries(history_year)
    target_entries = _load_score_rank_entries(target_year)
    if not hist_entries or not target_entries:
        return None
    hist_score = _rank_to_score(hist_entries, history_rank)
    if hist_score is None:
        return None
    return _score_to_rank(target_entries, hist_score)


def _fallback_scale_rank(rank: int, from_year: int, to_year: int) -> int:
    """[已弃用主路径] 按考生规模比例折算位次。保留供诊断/兼容。"""
    from_total = _total_candidates(from_year)
    to_total = _total_candidates(to_year)
    if from_total and to_total:
        return round(rank * to_total / from_total)
    return rank


@lru_cache(maxsize=6)
def _total_candidates(year: int, track: str = "历史类") -> int:
    """历史类考生总数（近似=一分一段表最大累计位次）。

    口径说明：2025/2026 是 3+1+2 历史类一分一段表（统计到104分），口径一致；
    2024 是传统文理科（统计到200分），口径与2025/2026断裂，不混用。
    """
    entries = _load_score_rank_entries(year, track)
    return entries[-1][1] if entries else 0  # 最低分档的累计位次


@lru_cache(maxsize=8)
def _load_undergrad_batch_line(year: int, track: str) -> int | None:
    """读取河南某年某科类普通本科批控制线（control_line/henan.yaml）。"""
    import yaml
    path = Path("data/seed/provincial/control_line/henan.yaml")
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # data 是 list[dict]，每项含 province/year/track/batches
    for item in data if isinstance(data, list) else [data]:
        if (item.get("province") == "河南" and item.get("year") == year
                and item.get("track") == track):
            batches = item.get("batches") or {}
            return batches.get("undergrad_batch")
    return None


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


def _round_half_up(x: float) -> int:
    """ROUND_HALF_UP 四舍五入为整数（银行家 round 会偶数向下，这里统一向上半进）。"""
    import math
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def compute_tier_boundaries(student_rank: int) -> dict:
    """计算五档整数边界（ROUND_HALF_UP，clamp 约束档位宽度，从稳档中心向两侧累加）。

    返回 dict（统一边界对象，判档/API/前端/测试共用，禁止重新计算）：
      reach_floor:  超冲/搏分界（A）= -20%R，ROUND_HALF_UP
      reach_sprint: 搏/冲分界（B）
      sprint_stable:冲/稳分界（C）= -3%R
      stable_safe:  稳/保分界（D）= +5%R
      safe_fallback:保/垫分界（E）
    半开区间：超冲<A, 搏[A,B), 冲[B,C), 稳[C,D), 保[D,E), 垫[E,+∞)
    """
    R = student_rank
    # 原始比例边界 → ROUND_HALF_UP 整数
    c = _round_half_up(-0.03 * R)   # 冲稳分界 C
    d = _round_half_up(0.05 * R)    # 稳保分界 D
    # 各档宽度 clamp（min,max）：先算比例宽度，再 clamp
    # 冲档宽度 = |C - (-10%R)|，clamp[300,10000]
    reach_sprint_raw = _round_half_up(-0.10 * R)
    sprint_w = min(10000, max(300, abs(c - reach_sprint_raw)))
    b = c - sprint_w                 # 搏冲分界 B = C - 冲档宽度
    # 搏档宽度 = |-20%R - (-10%R)| = 10%R，clamp[300,10000]
    reach_floor_raw = _round_half_up(-0.20 * R)
    gamble_w = min(10000, max(300, abs(reach_floor_raw - reach_sprint_raw)))
    a = b - gamble_w                 # 超冲搏分界 A = B - 搏档宽度
    # 保档宽度 = |15%R - 5%R| = 10%R，clamp[1500,20000]
    safe_fallback_raw = _round_half_up(0.15 * R)
    safe_w = min(20000, max(1500, abs(safe_fallback_raw - d)))
    e = d + safe_w                   # 保垫分界 E = D + 保档宽度
    return {"reach_floor": a, "reach_sprint": b, "sprint_stable": c,
            "stable_safe": d, "safe_fallback": e, "R": R}


def classify_admission_tier(student_rank: int, adjusted_rank: int) -> tuple[str, dict]:
    """根据考生位次与参考录取位次，判定录取档位（超冲/搏/冲/稳/保/垫）。

    边界用 ROUND_HALF_UP 整数，互斥半开区间，判档与展示共用同一边界对象。
    返回 (档位, {advantage, bounds, R})。
    """
    advantage = adjusted_rank - student_rank  # 整数（位次均为整数）
    bounds = compute_tier_boundaries(student_rank)
    a, b, c, d, e = (bounds["reach_floor"], bounds["reach_sprint"],
                     bounds["sprint_stable"], bounds["stable_safe"], bounds["safe_fallback"])
    if advantage < a:
        tier = "超冲"   # (-∞, A)
    elif advantage < b:
        tier = "搏"     # [A, B)
    elif advantage < c:
        tier = "冲"     # [B, C)
    elif advantage < d:
        tier = "稳"     # [C, D)
    elif advantage < e:
        tier = "保"     # [D, E)
    else:
        tier = "垫"     # [E, +∞)
    return tier, {"advantage": advantage, "bounds": bounds, "R": student_rank}


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


def _classify_language_restriction_from_aggregation(
    profile: dict, group_elig_status: str,
    eligible_majors: list[str], ineligible_majors: list[dict],
) -> dict:
    """基于专业级资格聚合结果的语种标注（资格链下沉后，比旧 group 级判断更精确）。

    返回 {level, note}：
    - partial: 组内部分专业可报、部分不可报（如英语专业限英语，俄语不限）→ 列出可报/不可报
    - hard_blocked: 整组所有专业都不可报（含考生语种之外的硬限制）
    - soft_warning: 全组可报但公共外语有适应风险
    - missing_data: 全组可报但公共外语语种未知
    - none: 英语考生或无限制
    """
    lang = profile.get("exam_foreign_language")
    if lang == "英语":
        return {"level": "none", "note": ""}

    if group_elig_status == "partially_eligible":
        reportable = "、".join(eligible_majors) if eligible_majors else "无"
        blocked_names = "、".join(m["major"] for m in ineligible_majors) if ineligible_majors else "无"
        return {
            "level": "partial",
            "note": f"部分专业可报：{lang}考生可报{reportable}；不可报{blocked_names}"
                    f"（限英语语种）。建议仅选可报专业，并核对调剂规则",
        }
    if group_elig_status == "ineligible":
        blocked_names = "、".join(m["major"] for m in ineligible_majors) if ineligible_majors else ""
        return {"level": "hard_blocked",
                "note": f"整组专业均不招收{lang}考生" + (f"（{blocked_names}）" if blocked_names else "")}
    if group_elig_status == "uncertain":
        return {"level": "missing_data", "note": "该组语种要求未采集，无法确认是否符合，建议核实招生章程"}
    # eligible：全组可报，但仍可能需提示公共外语适应
    return {"level": "none", "note": ""}


def _resolve_major_language_rule(group, major_plan) -> dict:
    """解析单个专业的生效语种规则（专业级覆盖语义）。

    优先级（design：专业规则 > 组规则，但保守覆盖）：
      1. major_plan.accepted_exam_languages 非空（已核验硬限制）→ restricted
      2. major_plan.remarks 解析（normalize_language_rule）：restricted / unrestricted / unknown
      3. group.accepted_exam_languages 非空（仅全专业一致组有值）→ restricted
      4. 否则 unknown

    覆盖语义：major 的明确规则（restricted/unrestricted）覆盖 group；
              major 为 unknown（未采集）时不覆盖 group 的明确限制（保守）。

    返回 normalize_language_rule 兼容结构 {rule_status, accepted, required}。
    """
    from app.loader.henan_language_rule import normalize_language_rule

    # 1. 专业级已核验硬限制语种
    if major_plan is not None:
        acc = (getattr(major_plan, "accepted_exam_languages", "") or "").strip()
        if acc:
            langs = [a.strip() for a in acc.split("|") if a.strip()]
            return {"rule_status": "restricted", "accepted": langs,
                    "required": langs[0] if len(langs) == 1 else None}
        # 2. remark 解析
        remark = getattr(major_plan, "remarks", "") or ""
        rule = normalize_language_rule(remark)
        if rule["rule_status"] != "unknown":
            return rule  # 专业级明确规则（restricted/unrestricted）覆盖 group

    # 3. 组级（仅全专业一致组有值）
    group_accepted = getattr(group, "accepted_exam_languages", None) or []
    if group_accepted:
        return {"rule_status": "restricted", "accepted": list(group_accepted),
                "required": getattr(group, "required_exam_language", None)}
    # 4. 未知
    return {"rule_status": "unknown", "accepted": [], "required": None}


def check_major_language_eligibility(profile: dict, group, major_plan) -> tuple[str, list[str], list[str]]:
    """单个专业的语种资格判断（资格链专业级下沉）。

    返回 (status, hard_failures, warnings)：
      status: "eligible" | "ineligible" | "uncertain"
        - eligible: 考生语种被接受 / 专业明确不限 / 无限制
        - ineligible: 专业/组明确限制某语种且不含考生语种（有证据的硬阻断）
        - uncertain: 语种规则未知（未采集），不能自动杀
    """
    lang = profile.get("exam_foreign_language")
    # 英语考生不受语种限制影响
    if lang == "英语":
        return ("eligible", [], [])

    rule = _resolve_major_language_rule(group, major_plan)
    failures: list[str] = []
    warnings: list[str] = []

    if rule["rule_status"] == "restricted":
        accepted = rule["accepted"]
        required = rule["required"]
        if required == "英语" and lang != "英语":
            major_name = getattr(major_plan, "major_name", "") if major_plan else ""
            failures.append(f"{major_name}专业要求英语语种，{lang}考生不可报"
                            if major_name else f"要求英语语种，{lang}考生不可报")
        elif accepted and lang not in accepted:
            major_name = getattr(major_plan, "major_name", "") if major_plan else ""
            failures.append(f"{major_name}专业仅接受{'/'.join(accepted)}语种，{lang}考生不可报"
                            if major_name else f"仅接受{'/'.join(accepted)}语种，{lang}考生不可报")
        else:
            return ("eligible", [], [])
        return ("ineligible", failures, warnings)

    if rule["rule_status"] == "unrestricted":
        return ("eligible", [], [])

    # unknown：语种规则未采集，保守降级 uncertain（不硬阻，但提示复核）
    return ("uncertain", [],
            ["该专业语种要求未采集，无法确认是否符合，建议核实招生章程"])


def aggregate_group_eligibility(profile: dict, group, group_plans: list) -> dict:
    """专业组级资格聚合（资格链专业级下沉，design §8.1/§8.2）。

    先做组级硬过滤（首选/再选科目、体检、专项、单科），通过后逐专业判断语种，
    最后按"组内是否至少存在一个可报专业"聚合为组级状态。

    返回:
        {
            "status": "eligible" | "partially_eligible" | "ineligible" | "uncertain",
            "blocked_reasons": list[str],      # 组级硬阻断原因（首选/再选/体检/专项）
            "warnings": list[str],             # 软提示
            "eligible_majors": list[str],      # 可报专业名
            "ineligible_majors": list[dict],   # [{major, reasons}] 不可报专业及原因
            "uncertain_majors": list[str],     # 语种未知专业名
        }
    """
    # ── 第1步：组级硬过滤（非语种，作用于整组）──
    group_blocked: list[str] = []
    group_warnings: list[str] = []

    if group.primary_subject_requirement and profile.get("primary_subject") != group.primary_subject_requirement:
        group_blocked.append(f"首选科目要求{group.primary_subject_requirement}")

    require = (group.elective_subject_requirement or {}).get("require", [])
    for subject in require:
        if subject not in profile.get("elective_subjects", []):
            group_blocked.append(f"再选科目要求包含{subject}")

    # 单科要求（组级）
    for requirement in group.single_subject_requirements or []:
        subject = requirement.get("subject")
        min_score = requirement.get("min_score")
        if not subject or not isinstance(min_score, int):
            continue
        score = _lookup_subject_score(profile, subject)
        if subject == "英语" and profile.get("exam_foreign_language") != "英语":
            group_blocked.append(f"英语单科要求 {min_score} 分，非英语语种考生不符合")
            continue
        if score is None:
            group_blocked.append(f"缺少{subject}单科成绩，无法校验最低 {min_score} 分要求")
            continue
        if score < min_score:
            group_blocked.append(f"{subject}单科 {score} 分，未达到最低 {min_score} 分要求")

    # 体检限制（组级）
    for restriction_text in [group.physical_restrictions or ""]:
        if not restriction_text:
            continue
        if "辨色力异常" in restriction_text and profile.get("color_vision") == "异常":
            group_blocked.append("辨色力异常不符招生要求")
        if "身高要求" in restriction_text:
            required_height = _parse_height_requirement(restriction_text)
            if required_height and profile.get("height", 0) < required_height:
                group_blocked.append(f"身高须达到{required_height}cm以上")
        if "视力要求" in restriction_text and profile.get("vision_corrected") is False:
            group_blocked.append("视力不符招生要求")

    # 专项类型限制（组级）
    spec_type = group.special_qualification_type or ""
    if spec_type:
        student_quals = profile.get("special_qualifications", [])
        spec_map = {"高校专项": "高校专项", "地方专项": "地方专项",
                    "国家专项": "国家专项", "公费师范": "公费师范",
                    "定向医学生": "定向医学生"}
        need = spec_map.get(spec_type)
        if need and need not in student_quals:
            group_blocked.append(f"须具备{need}资格")

    # 组级硬阻断 → 整组不可报，无需逐专业判断语种
    if group_blocked:
        return {"status": "ineligible", "blocked_reasons": group_blocked,
                "warnings": group_warnings,
                "eligible_majors": [], "ineligible_majors": [], "uncertain_majors": []}

    # ── 第2步：逐专业语种判断（专业级下沉）──
    # 建立 major_name → plan 索引
    plans_by_name = {p.major_name: p for p in group_plans} if group_plans else {}
    included = group.included_majors or []
    # 若 included_majors 为空但有 plans，用 plans 的专业名兜底
    if not included and group_plans:
        included = list(plans_by_name.keys())

    eligible_majors: list[str] = []
    ineligible_majors: list[dict] = []
    uncertain_majors: list[str] = []
    all_warnings: list[str] = []

    for major_name in included:
        major_plan = plans_by_name.get(major_name)
        status, failures, warnings = check_major_language_eligibility(profile, group, major_plan)
        if status == "eligible":
            eligible_majors.append(major_name)
        elif status == "ineligible":
            ineligible_majors.append({"major": major_name, "reasons": failures})
        else:  # uncertain
            uncertain_majors.append(major_name)
            all_warnings.extend(warnings)

    # 日语公共外语软提示（仅英语考生不受影响，已在上层返回）
    if profile.get("exam_foreign_language") == "日语":
        pubfl = group.public_foreign_languages or []
        if pubfl and "日语" not in pubfl:
            all_warnings.append(
                f"英语适应风险：本专业组可录取日语考生，但公共外语仅开{'/'.join(pubfl)}。"
                "入学后英语课程、四六级、部分学位/留学要求需自行适应，建议英语基础尚可者填报"
            )
        elif not pubfl and (eligible_majors or uncertain_majors):
            # 公共外语语种未提供：只要该组有可报或语种待核的专业（非整组硬阻），就提示数据缺失
            all_warnings.append("语种数据缺失：未提供公共外语语种，暂无法确认日语考生入学后的课程语种适配")

    # ── 第3步：组级状态聚合（情况A-D）──
    has_eligible = len(eligible_majors) > 0
    has_ineligible = len(ineligible_majors) > 0
    has_uncertain = len(uncertain_majors) > 0

    if has_eligible and has_ineligible:
        status = "partially_eligible"
    elif has_eligible and not has_ineligible:
        status = "eligible"
    elif not has_eligible and has_ineligible and not has_uncertain:
        status = "ineligible"
    elif not has_eligible and has_uncertain:
        status = "uncertain"
    else:
        # 兜底：无 included_majors 且无 plans，无法判断专业级 → 用旧 check_henan_eligibility 兜底
        ok, blocked, warns = check_henan_eligibility(profile, group)
        status = "eligible" if ok else "ineligible"
        group_blocked = blocked
        all_warnings = warns

    return {"status": status, "blocked_reasons": group_blocked,
            "warnings": all_warnings,
            "eligible_majors": eligible_majors, "ineligible_majors": ineligible_majors,
            "uncertain_majors": uncertain_majors}


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
    tier, _ = classify_admission_tier(student_rank, historical_rank)
    return tier


def _risk_level(bucket: str) -> str:
    """档位→风险等级文字（未经回测校准，不展示精确概率）。"""
    return {
        "超冲": "录取希望极低",
        "搏": "机会较低",
        "冲": "有一定机会",
        "稳": "匹配度较高",
        "保": "录取优势较明显",
        "垫": "录取优势很明显",
    }.get(bucket, "—")


def estimate_admission_probability(bucket: str, rank_gap_ratio: float | None, confidence: float) -> float:
    """[已废弃] 估算投档成功率。

    废弃原因：
      1. 基于旧 rank_gap_ratio（考生−参考/参考位次），方向与判档 advantage 相反；
      2. 精确概率未经历史回测校准，易误导；
      3. 现已改用 risk_level（定性区间）展示。

    保留函数体仅为兼容旧测试/调用方，生产链路不再调用（admission_probability 恒为 null）。
    新代码请用 _risk_level(bucket) 或 advantage_ratio。
    """
    return 0.0


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

    # ── 第2层：录取档位（位次匹配，五档+超冲，严格半开区间）──
    tier, tier_detail = classify_admission_tier(student_rank, adjusted_rank)
    # 超冲（advantage < 搏档下界A）：资格可报，但目标门槛明显高于当前位次
    # 推荐状态由适配因素决定（冷启动无适配问题设 conditional），不因超冲设 not_recommended
    if tier == "超冲":
        return {"eligibility_status": "eligible", "admission_tier": "超冲",
                "recommendation_status": "conditional", "bucket": "超冲",
                "tier_detail": tier_detail,
                "visibility_status": "hidden_by_default",
                "hide_reason_code": "extreme_reach",
                "can_manually_include": True}

    # ── 第3层：推荐适配（冷启动：资格通过即 recommended）──
    return {"eligibility_status": "eligible", "admission_tier": tier,
            "recommendation_status": "recommended", "bucket": tier,
            "tier_detail": tier_detail}


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

    # ── 本科线资格门：低于本科控制线不生成常规本科五档 ──
    # 2026历史类本科线459（control_line/henan.yaml）。线下考生不具备常规本科填报资格，
    # 应引导至专科批 + 关注本科征集志愿，而非给出虚假的本科搏/冲/稳/保/垫。
    student_score = profile.get("score") or 0
    undergrad_line = _load_undergrad_batch_line(2026, "历史类")
    if undergrad_line and student_score < undergrad_line:
        profile["_batch_ineligible"] = True
        profile["_batch_gap"] = undergrad_line - student_score
        return []  # 不生成常规本科候选（API 层据此输出线下提示）

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

        # 2026 计划校验（提前到资格判断之前，供专业级语种聚合用）
        group_plans = plans_by_key.get(
            (group.school_code, group.major_group_code, group.track, group.batch), []
        )
        has_2026_plan = any(p.plan_count > 0 and p.review_status == "verified" for p in group_plans)
        has_verified_group = group.review_status == "verified"
        plan_count = sum(p.plan_count for p in group_plans)

        # 资格层（专业级下沉：语种按专业判断，组级聚合 partially_eligible）
        agg = aggregate_group_eligibility(profile, group, group_plans)
        group_elig_status = agg["status"]
        blocked = agg["blocked_reasons"]
        warnings = agg["warnings"]
        eligible_majors = agg["eligible_majors"]
        ineligible_majors = agg["ineligible_majors"]
        uncertain_majors = agg["uncertain_majors"]
        # 兼容旧 ok 语义：ineligible → 不通过；其余（eligible/partially_eligible/uncertain）→ 通过资格门
        ok = group_elig_status != "ineligible"

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
            norm = {"method": "raw", "confidence": "high", "raw_rank": None,
                    "same_score_reference_rank": None, "fallback_reason": None}
            tier_detail = None
            visibility_status, hide_reason_code, can_manually_include = "visible", None, False
        elif baseline is None or not has_verified_history:
            # design D2/I1：资格通过但缺 verified 历史基线 → 需人工复核（不得稳/保，也不混为不推荐）
            bucket = "需人工复核"
            eligibility_status = "uncertain"
            admission_tier = None
            recommendation_status = "conditional"
            data_confidence = "low"
            norm = {"method": "raw", "confidence": "high", "raw_rank": None,
                    "same_score_reference_rank": None, "fallback_reason": None}
            tier_detail = None
            visibility_status, hide_reason_code, can_manually_include = "visible", None, False
        else:
            # —— 年度归一化（百分位映射）必须在判档之前 ——
            # 解决跨年位次不可比：用归一化后的2026等效位次判档，非原始历史位次
            raw_min_rank = baseline.get("adjusted_min_rank")
            baseline_year = baseline.get("year")
            if raw_min_rank and raw_min_rank > 0 and baseline_year and baseline_year != 2026:
                norm = normalize_rank_to_target_year(raw_min_rank, baseline_year, 2026)
                normalized_rank = norm["normalized_rank"]
            else:
                normalized_rank = raw_min_rank
                norm = {"method": "raw", "confidence": "high", "raw_rank": raw_min_rank,
                        "same_score_reference_rank": None, "fallback_reason": None}

            # 2024旧口径数据（method=raw 因口径断裂）：不参与确定性五档，标需人工复核
            if norm.get("method") == "raw" and baseline_year == 2024:
                bucket = "需人工复核"
                eligibility_status = "uncertain"
                admission_tier = None
                recommendation_status = "conditional"
                data_confidence = "low"
                tier_detail = None
                visibility_status, hide_reason_code, can_manually_include = "visible", None, False
            else:
                # 三层状态判定（用归一化后的2026等效位次）
                verdict = classify_group_bucket(
                    student_rank=student_rank,
                    adjusted_rank=normalized_rank,
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
                tier_detail = verdict.get("tier_detail")  # 五档边界详情（供核对/前端展示）
                # 超冲可见性控制（其他档位默认可见）
                visibility_status = verdict.get("visibility_status", "visible")
                hide_reason_code = verdict.get("hide_reason_code")
                can_manually_include = verdict.get("can_manually_include", False)
                # 数据置信度：有专业组级 verified 历史为 high，校级/单年为 medium
                data_confidence = "high" if baseline.get("data_granularity") in ("major", "major_group", "major_group_trend") else ("medium" if baseline else "low")
                # 缺计划或未核验组的可达档位降级为需人工复核
                if bucket in {"搏", "冲", "稳", "保", "垫"} and (not has_2026_plan or not has_verified_group):
                    bucket = "需人工复核"
                    eligibility_status = "uncertain"
                admission_tier = None
                # 资格链专业级下沉：partially_eligible 组进五档参与排序，
                # 但 eligibility_status 标记为 partially_eligible（卡片据此展示可报/不可报专业分区）
                if group_elig_status == "partially_eligible":
                    eligibility_status = "partially_eligible"

        # —— 需复核原因细分（design：需人工复核≠不符合，需告知用户具体缺什么数据）——
        # 区分"不能报"（ineligible）与"暂时算不出"（uncertain/需人工复核），
        # 让用户明白是资格硬阻还是数据证据不足。
        review_reason_codes: list[str] = []
        review_reason: str | None = None
        eligibility_known = group_elig_status != "uncertain"  # 资格是否已明确（eligible/partially_eligible/ineligible=已知）
        admission_predictable = bucket in {"超冲", "搏", "冲", "稳", "保", "垫"}
        if bucket == "需人工复核":
            # 收集全部数据缺口（多原因，非只取首个）——便于数据治理看到完整缺口清单
            if baseline is None or not has_verified_history:
                review_reason_codes.append("missing_verified_2025_rank")
            if baseline is not None and baseline.get("year") == 2024:
                review_reason_codes.append("only_2024_old_regime")
            if not has_2026_plan:
                review_reason_codes.append("missing_verified_2026_plan")
            if not has_verified_group:
                review_reason_codes.append("unverified_2026_group")
            if not review_reason_codes:
                review_reason_codes.append("other_review_needed")
            # 主因（最高优先级），用于卡片主展示 + 向后兼容 review_reason_code 单值字段
            primary_code = review_reason_codes[0]
            review_reason = {
                "missing_verified_2025_rank": "资格暂无问题，但缺少2025同口径院校专业组最低录取位次，无法严谨判定搏/冲/稳/保/垫，需补充数据后复核",
                "only_2024_old_regime": "仅有2024旧文科口径数据（≠新高考历史类），口径断裂不可直接判档，待2025同口径数据补齐后复核",
                "missing_verified_2026_plan": "2026河南招生计划未核验，无法确认本组2026是否招生",
                "unverified_2026_group": "2026专业组结构未核验，无法确认选科/语种等限制是否最新",
                "other_review_needed": "数据证据不足，需人工复核",
            }[primary_code]

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

        # —— 冲稳保计算明细：统一口径（advantage = 参考位次 − 考生位次，负值=更难）——
        # 判档用 classify_admission_tier 的 advantage（参考−考生），展示口径必须与之一致。
        # advantage_ratio = advantage / 考生位次R（分母用考生位次，与判档边界口径一致）。
        # 旧 rank_gap_ratio=(考生−参考)/参考 已废弃：方向相反、分母不同，与判档逻辑矛盾。
        adjusted_min_rank = norm.get("normalized_rank") or norm.get("raw_rank")
        tier_advantage = (tier_detail or {}).get("advantage")
        advantage_ratio = (
            round(tier_advantage / student_rank, 4)
            if (tier_advantage is not None and student_rank > 0)
            else None
        )
        # admission_probability 停用：未经回测校准且方向曾与新判档相反，仅保留 risk_level。
        # 字段保留为 null（兼容旧 API 消费方），内部排序已不依赖它（用 bucket/risk_level）。
        admission_probability = None
        bucket_detail = {
            "student_rank": student_rank if student_rank > 0 else None,
            "reference_rank": adjusted_min_rank,  # 归一化后参考录取位次（语义更清晰，替代旧 adjusted_min_rank）
            "adjusted_min_rank": adjusted_min_rank,  # 保留旧字段名兼容
            "advantage": tier_advantage,  # 参考位次 − 考生位次（负=目标更难，正=考生更优）
            "advantage_ratio": advantage_ratio,  # advantage / 考生位次R（判档同口径比例）
            "rank_gap_ratio": None,  # 已废弃（旧口径），置 null 防误用
            "admission_probability": admission_probability,  # 已停用，保留 null 兼容
            # 风险等级（未经回测校准，不展示精确概率，用定性区间）
            "risk_level": _risk_level(bucket),
            "baseline_year": baseline.get("year") if baseline else None,
            "baseline_granularity": baseline.get("data_granularity") if baseline else None,
            # 年度归一化元信息（不静默回退，前端可见计算口径）
            "raw_historical_rank": norm.get("raw_rank"),
            "normalization_method": norm.get("method"),
            "normalization_confidence": norm.get("confidence"),
            "same_score_reference_rank": norm.get("same_score_reference_rank"),
            "fallback_reason": norm.get("fallback_reason"),
            # 五档边界详情（advantage + 各分界线，供核对/前端展示计算过程）
            "tier_detail": tier_detail,
            "confidence": group.confidence,
            "calculation_version": "henan_tier_v1",  # 口径版本标记，便于前端/测试识别
            "thresholds": {
                "超冲": "位次优势 < 搏档下界 A（目标门槛远高于考生，录取希望极低）",
                "搏": "A ≤ 位次优势 < B（参考位次比考生高 10%~20%R）",
                "冲": "B ≤ 位次优势 < C（参考位次比考生高 3%~10%R）",
                "稳": "C ≤ 位次优势 < D（考生与参考位次基本匹配，-3%~+5%R）",
                "保": "D ≤ 位次优势 < E（考生位次优于参考 5%~15%R）",
                "垫": "位次优势 ≥ E（考生位次远优于参考，兜底）",
                "不推荐": "资格层未通过（选科/语种/单科/体检不符）",
            },
            "formula": "位次优势 = 参考位次 − 考生位次；优势>0 表示考生更易录取，<0 表示目标更难",
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
            # 可见性控制（超冲默认隐藏但可手动加入）
            "visibility_status": visibility_status,
            "hide_reason_code": hide_reason_code,
            "can_manually_include": can_manually_include,
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
            "language_restriction": _classify_language_restriction_from_aggregation(
                profile, group_elig_status, eligible_majors, ineligible_majors),
            # 资格链专业级下沉（design §8.1/§8.2）：组级资格状态 + 可报/不可报专业明细
            "group_eligibility_status": group_elig_status,
            "eligible_majors": eligible_majors,
            "ineligible_majors": ineligible_majors,
            "uncertain_majors": uncertain_majors,
            "single_subject_requirements": group.single_subject_requirements,
            "physical_restrictions": group.physical_restrictions or (group_plans[0].physical_restrictions if group_plans else ""),
            "special_qualification_type": group.special_qualification_type or (group_plans[0].special_qualification_type if group_plans else ""),
            "missing_data_items": missing_data_items,
            # 需复核原因细分（design：需人工复核≠不符合，让用户明白缺什么数据）
            "review_reason_codes": review_reason_codes,           # 全部数据缺口列表（数据治理用）
            "primary_review_reason_code": review_reason_codes[0] if review_reason_codes else None,
            "review_reason_code": review_reason_codes[0] if review_reason_codes else None,  # 兼容旧字段=主因
            "review_reason": review_reason,
            "eligibility_known": eligibility_known,
            "admission_predictable": admission_predictable,
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
