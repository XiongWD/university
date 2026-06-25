"""志愿填报引擎（纯函数，无 DB 依赖）。

核心逻辑链：
  考生分数 → [位次换算] 今年位次 → [等效位次] 历年等效位次
           → [冲稳保分档] 各校分类 → [志愿表生成] 完整志愿表

复用 rank_query.score_to_rank 做精确位次换算；分数不在表中时线性插值。
冲稳保阈值：考生位次 ±5% 内为稳，更优为冲，更差为保。
"""
from __future__ import annotations

from app.engine.rank_query import score_to_rank
from app.models.admission import AdmissionRecord
from app.models.provincial import ScoreRankEntry
from app.models.student import RiskPreference, StudentProfile
from app.models.volunteer import (
    AdmissionProbability,
    Strategy,
    VolunteerSuggestion,
    VolunteerTable,
)

# 冲稳保阈值（相对考生位次的偏离比例）
STABLE_BAND = 0.05  # ±5% 内为稳
SPRINT_FLOOR = 0.40  # 冲的志愿最多冲到考生位次的40%(再低=几乎录不了，不列入)


def convert_score_to_rank(entries: list[ScoreRankEntry], score: int) -> int | None:
    """分数 → 今年累计位次。表中无精确值时按相邻位次线性插值。

    复用 rank_query.score_to_rank 做精确匹配；缺失则取夹住该分数的
    两个相邻分数做线性插值（位次随分数单调）。
    """
    exact = score_to_rank(entries, score)
    if exact is not None:
        return exact
    if not entries:
        return None
    # 按 score 降序找夹住 score 的两个相邻分数
    sorted_e = sorted(entries, key=lambda e: -e.score)
    higher = lower = None  # higher = 分数更高(位次更小), lower = 分数更低(位次更大)
    for e in sorted_e:
        if e.score > score:
            higher = e
        elif e.score < score and lower is None:
            lower = e
    if higher and lower:
        # 线性插值：位次在 higher.cumulative_rank 和 lower.cumulative_rank 之间
        span = higher.score - lower.score
        if span <= 0:
            return higher.cumulative_rank
        frac = (higher.score - score) / span
        return round(higher.cumulative_rank + frac * (lower.cumulative_rank - higher.cumulative_rank))
    # score 超出表范围：用最近的端点
    if higher:
        return higher.cumulative_rank
    return lower.cumulative_rank if lower else None


def equivalent_rank(rank_this_year: int, total_this_year: int,
                    total_history: int | None) -> int:
    """今年位次 → 历年等效位次（按考生总量比例折算）。

    解决"今年35万 vs 去年40万考生"的位次不可直接比。
    公式：历史等效位次 = 今年位次 × (历史考生总量 / 今年考生总量)。
    无历史考生数时返回原位次（降级，不阻断）。
    """
    if not total_history or total_this_year <= 0:
        return rank_this_year
    return round(rank_this_year * total_history / total_this_year)


def classify_strategy(student_rank: int, school_rank: int) -> Strategy:
    """根据考生位次与学校录取位次的偏离分冲稳保。

    - 学校录取位次 ≤ 考生位次的 95%（更难录）→ 冲
    - 在考生位次的 95%~105% 之间 → 稳
    - ≥ 考生位次的 105%（更容易录）→ 保
    """
    ratio = school_rank / student_rank if student_rank > 0 else 1.0
    if ratio < 1 - STABLE_BAND:
        return Strategy.SPRINT
    if ratio > 1 + STABLE_BAND:
        return Strategy.SAFE
    return Strategy.STABLE


def estimate_probability(student_rank: int, school_rank: int) -> AdmissionProbability:
    """估算录取概率（0-1）。位次越优于考生，概率越低。

    粗略模型：以 ratio = school_rank/student_rank 为基础，
    ratio=1（完全匹配）→ 0.9；ratio越小（越难）概率越低；ratio越大（越容易）趋近1。
    """
    ratio = school_rank / student_rank if student_rank > 0 else 1.0
    if ratio >= 1:
        # 保：学校更容易录，概率高
        prob = min(0.99, 0.90 + min(0.09, (ratio - 1) * 0.3))
    else:
        # 冲：学校更难录，概率随 ratio 下降
        prob = max(0.05, 0.90 - (1 - ratio) * 2.5)
    basis = f"位次比 {ratio:.2f}（考生{student_rank}/校录{school_rank}）"
    return AdmissionProbability(probability=round(prob, 3), basis=basis)


# 风险偏好 → 各档配额（生成志愿表时每档最多保留多少条）
_QUOTAS = {
    RiskPreference.AGGRESSIVE: {Strategy.SPRINT: 6, Strategy.STABLE: 3, Strategy.SAFE: 2},
    RiskPreference.BALANCED: {Strategy.SPRINT: 3, Strategy.STABLE: 4, Strategy.SAFE: 3},
    RiskPreference.SAFE: {Strategy.SPRINT: 2, Strategy.STABLE: 3, Strategy.SAFE: 5},
}


def generate_volunteer_table(
    student: StudentProfile,
    admissions: list[AdmissionRecord],
    rank_entries: list[ScoreRankEntry],
    track: str,
    data_year: int,
    total_this_year: int | None = None,
    total_history: int | None = None,
) -> VolunteerTable:
    """生成完整冲稳保志愿表。

    1. 考生分数 → 今年位次（convert_score_to_rank）
    2. （可选）等效位次折算（等效位次用于跨年比较，但分档仍用今年位次 vs 校录位次）
    3. 过滤 track/年份匹配的录取数据
    4. 逐校分档（classify_strategy）+ 概率估算
    5. 按风险偏好配额裁剪各档
    """
    student_rank = convert_score_to_rank(rank_entries, student.total_score)
    eq_rank = equivalent_rank(student_rank, total_this_year, total_history) if student_rank else None

    buckets: dict[Strategy, list[VolunteerSuggestion]] = {
        Strategy.SPRINT: [], Strategy.STABLE: [], Strategy.SAFE: [],
    }
    # 分档用等效位次（若有折算）否则用今年位次
    ref_rank = eq_rank if eq_rank else (student_rank or 0)
    for a in admissions:
        if a.track != track or a.year != data_year:
            continue
        if a.province != student.province:
            continue
        strat = classify_strategy(ref_rank, a.min_rank)
        # 过冲：学校位次远优于考生(低于考生位次的SPRINT_FLOOR)则不列入(几乎录不了)
        if strat == Strategy.SPRINT and ref_rank > 0:
            if a.min_rank / ref_rank < SPRINT_FLOOR:
                continue
        prob = estimate_probability(ref_rank, a.min_rank)
        buckets[strat].append(VolunteerSuggestion(
            strategy=strat, school=a.school, major=a.major,
            major_group=a.major_group, subject_requirement=a.subject_requirement,
            last_year_rank=a.min_rank, last_year_score=a.min_score,
            student_rank=ref_rank, probability=prob,
        ))

    quotas = _QUOTAS[student.risk_preference]
    # 各档内按录取概率从高到低排序后裁剪
    for strat in buckets:
        buckets[strat].sort(key=lambda s: -s.probability.probability)
        buckets[strat] = buckets[strat][:quotas[strat]]

    return VolunteerTable(
        student_score=student.total_score,
        student_rank=student_rank or 0,
        equivalent_rank=eq_rank,
        track=track, data_year=data_year,
        sprint=buckets[Strategy.SPRINT],
        stable=buckets[Strategy.STABLE],
        safe=buckets[Strategy.SAFE],
        source_note=f"基于{data_year}年历史录取数据预测（实际录取以当年投档为准）",
    )
