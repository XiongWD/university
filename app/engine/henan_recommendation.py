"""河南志愿推推荐引擎（design §3、§8）。

主链路：资格先行 → 位次风险 → 冲稳保分桶 → 48 志愿草案。
分桶分两层：资格层（省控线/计划/选科/语种/单科）不通过直接「不推荐」；
风险层用位次差比（不用裸分）。不输出伪精确概率，只用 冲/稳/保/不推荐 档位。

注意：这是河南志愿推的新主链路，与旧 advisory（冲/中/稳）并行，旧链路保留不删。
"""
from __future__ import annotations

# design §8.3：风险层默认分桶阈值（rank_gap_ratio = 考生位次相对参考位次的偏离）
REACH_RATIO = 0.03       # > 3% 偏后 → 冲
SAFE_DROP_RATIO = -0.10  # 优于参考 10% 以上 → 保
HARD_NOT_RECOMMEND = 0.15  # 偏后超 15% → 不推荐


def check_henan_eligibility(profile: dict, group) -> tuple[bool, list[str], list[str]]:
    """资格先行（design §8.1、§8.2）：首选/再选/语种/单科硬过滤 + 日语软风险提示。

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
        blocked.append(f"外语语种需为{'/'.join(accepted)}")

    # 日语软风险：不限语种但公共外语仅开英语 → 入学后适应风险（不挡资格）
    if profile.get("exam_foreign_language") == "日语" and "日语" not in (group.public_foreign_languages or []):
        warnings.append("入学后公共外语可能仅开英语，日语考生有适应风险")

    return len(blocked) == 0, blocked, warnings


def classify_henan_bucket(student_rank: int, historical_rank: int | None, policy_mode: str) -> str:
    """按位次差比分桶（design §8.3 基础口径）。

    ratio = (student_rank - historical_rank) / historical_rank
    正数表示考生位次更靠后、风险更高。policy_mode 当前仅作语义占位，阈值统一。
    """
    if historical_rank is None or historical_rank <= 0 or student_rank <= 0:
        return "不推荐"
    ratio = (student_rank - historical_rank) / historical_rank
    if ratio > 0.12:
        return "不推荐"
    if ratio > REACH_RATIO:
        return "冲"
    if ratio >= SAFE_DROP_RATIO:
        return "稳"
    return "保"


def classify_group_bucket(
    student_rank: int,
    adjusted_rank: int | None,
    has_2025_history: bool,
    has_2026_plan: bool,
    has_verified_group: bool,
    confidence: float,
) -> str:
    """专业组级分桶（design §8.3 修正规则）。

    比 classify_henan_bucket 更严格：必须有 2026 河南计划、专业组已核验；
    缺 2025 历史或置信度不足时不得判「保」。
    """
    # 资格层：缺计划或缺专业组核验 → 不推荐（design §2.3 上线门禁）
    if not has_2026_plan or not has_verified_group:
        return "不推荐"
    if adjusted_rank is None or adjusted_rank <= 0 or student_rank <= 0:
        return "不推荐"

    rank_gap_ratio = (student_rank - adjusted_rank) / adjusted_rank
    if rank_gap_ratio > HARD_NOT_RECOMMEND:
        return "不推荐"
    if rank_gap_ratio > REACH_RATIO:
        return "冲"
    if rank_gap_ratio >= SAFE_DROP_RATIO:
        return "稳"
    # 保：需 2025 历史可用 + 置信度达标，否则降为稳（design §8.3 修正规则）
    if not has_2025_history or confidence < 0.7:
        return "稳"
    return "保"


def get_bucket_quota(policy_count: int, strategy: str, profile: dict) -> dict[str, tuple[int, int]]:
    """48 志愿草案的冲稳保数量配额（design §8.4）。

    比例是产品默认策略，非官方比例。历史类+日语默认保守；自动策略按科类/语种选择。
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
    return {"冲": scaled(8, 12), "稳": scaled(20, 24), "保": scaled(12, 16)}  # 均衡


# 冲稳保排序权重（冲在前，保次之，不推荐最后）
_BUCKET_ORDER = {"冲": 0, "稳": 1, "保": 2, "不推荐": 3}


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
    """首页推荐候选生成入口（design §8）。

    生产实现需加载 2026 河南专业组、2026 招生计划、2025/2024 历史录取、费用、
    就业信号，再依次调用 check_henan_eligibility() 与 classify_group_bucket()。
    当前返回占位：仅校验生源地。
    """
    if profile.get("source_province") not in (None, "河南"):
        raise ValueError("河南志愿推仅支持河南考生")
    return []
