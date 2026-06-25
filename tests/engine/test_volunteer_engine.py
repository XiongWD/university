"""志愿填报引擎纯函数测试。

覆盖4个核心能力：位次换算 / 等效位次 / 冲稳保分档 / 志愿表生成。
所有测试用真实河南2024数据锚点（郑大22963 / 河大37744 / 河南农大114271 等）。
"""
import pytest

from app.engine.rank_query import score_to_rank
from app.engine.volunteer import (
    classify_strategy,
    convert_score_to_rank,
    equivalent_rank,
    estimate_probability,
    generate_volunteer_table,
)
from app.models.admission import AdmissionRecord, Batch
from app.models.student import FamilyResources, RiskPreference, StudentProfile
from app.models.volunteer import Strategy
from app.models.provincial import ScoreRankEntry


# ===== 测试数据（真实锚点）=====
# 河南2024理科一本院校录取位次（从冲到保）
ADMISSIONS_2024 = [
    AdmissionRecord(school="郑州大学", major="普通类", province="河南", year=2024,
                    track="理科", min_score=601, min_rank=22963, avg_score=615,
                    batch=Batch.FIRST, source="考试院2024", as_of=__import__("datetime").date(2024, 7, 1),
                    confidence=0.95),
    AdmissionRecord(school="河南大学", major="普通类", province="河南", year=2024,
                    track="理科", min_score=582, min_rank=37744, avg_score=595,
                    batch=Batch.FIRST, source="考试院2024", as_of=__import__("datetime").date(2024, 7, 1),
                    confidence=0.95),
    AdmissionRecord(school="河南师范大学", major="普通类", province="河南", year=2024,
                    track="理科", min_score=543, min_rank=78624, avg_score=555,
                    batch=Batch.FIRST, source="考试院2024", as_of=__import__("datetime").date(2024, 7, 1),
                    confidence=0.9),
    AdmissionRecord(school="河南财经政法大学", major="普通类", province="河南", year=2024,
                    track="理科", min_score=536, min_rank=92030, avg_score=548,
                    batch=Batch.FIRST, source="考试院2024", as_of=__import__("datetime").date(2024, 7, 1),
                    confidence=0.9),
    AdmissionRecord(school="中原工学院", major="普通类", province="河南", year=2024,
                    track="理科", min_score=530, min_rank=100737, avg_score=542,
                    batch=Batch.FIRST, source="考试院2024", as_of=__import__("datetime").date(2024, 7, 1),
                    confidence=0.9),
    AdmissionRecord(school="河南农业大学", major="普通类", province="河南", year=2024,
                    track="理科", min_score=521, min_rank=114271, avg_score=533,
                    batch=Batch.FIRST, source="考试院2024", as_of=__import__("datetime").date(2024, 7, 1),
                    confidence=0.9),
]

# 河南2024一分一段表片段（关键锚点：本科线465→位次约20万；物理类600→32622是2026，
# 2024理科600分位次约2万出头，这里构造测试用片段）
RANK_ENTRIES_2024 = [
    ScoreRankEntry(score=605, count_at=80, cumulative_rank=19000),
    ScoreRankEntry(score=601, count_at=120, cumulative_rank=22963),  # 郑大锚点
    ScoreRankEntry(score=582, count_at=150, cumulative_rank=37744),  # 河大锚点
    ScoreRankEntry(score=543, count_at=200, cumulative_rank=78624),  # 河师大锚点
    ScoreRankEntry(score=521, count_at=180, cumulative_rank=114271),  # 农大锚点
    ScoreRankEntry(score=465, count_at=500, cumulative_rank=200000),  # 本科线
]


def _student(score: int, pref: RiskPreference = RiskPreference.BALANCED) -> StudentProfile:
    return StudentProfile(
        province="河南", total_score=score,
        subject_scores={"语文": 110, "数学": 120, "英语": 120, "理综": score - 350},
        family_resources=FamilyResources(), gender="男",
        interests=["计算机"], strengths=["数学"],
        risk_preference=pref,
        source="test", as_of=__import__("datetime").date(2026, 6, 25), confidence=1.0,
    )


# ===== 1. 位次换算 =====
def test_convert_score_to_rank_exact():
    """分数在一分一段表中有精确位次。"""
    rank = convert_score_to_rank(RANK_ENTRIES_2024, 582)
    assert rank == 37744


def test_convert_score_to_rank_interpolate_when_missing():
    """分数在表中无精确值时，应就近插值返回近似位次（不返回None）。"""
    # 583分不在表中(582和605之间)，应返回插值位次，约在22963~37744之间
    rank = convert_score_to_rank(RANK_ENTRIES_2024, 583)
    assert rank is not None
    assert 22963 <= rank <= 37744


def test_convert_score_to_rank_empty_returns_none():
    assert convert_score_to_rank([], 600) is None


# ===== 2. 等效位次 =====
def test_equivalent_rank_scales_by_total_candidates():
    """等效位次 = 今年位次 × (历史考生/今年考生)。"""
    # 今年40万考生，去年50万考生，位次30000
    eq = equivalent_rank(rank_this_year=30000, total_this_year=400000, total_history=500000)
    assert eq == 37500  # 30000 * 500000/400000


def test_equivalent_rank_no_data_returns_original():
    """无历史考生数时返回原位次（降级，不阻断）。"""
    eq = equivalent_rank(rank_this_year=30000, total_this_year=400000, total_history=None)
    assert eq == 30000


def test_equivalent_rank_same_scale_unchanged():
    """考生总量相近时等效位次≈原位次。"""
    eq = equivalent_rank(rank_this_year=30000, total_this_year=400000, total_history=400000)
    assert eq == 30000


# ===== 3. 冲稳保分档 =====
def test_classify_strategy_sprint_when_school_rank_better():
    """学校录取位次显著优于考生(数字更小) → 冲。"""
    # 考生位次30000，学校录取位次25000(更难) → 冲
    s = classify_strategy(student_rank=30000, school_rank=25000)
    assert s == Strategy.SPRINT


def test_classify_strategy_stable_when_close():
    """学校录取位次与考生接近(±5%) → 稳。"""
    # 考生位次30000，学校录取位次29500(差1.7%) → 稳
    s = classify_strategy(student_rank=30000, school_rank=29500)
    assert s == Strategy.STABLE


def test_classify_strategy_safe_when_school_lower():
    """学校录取位次显著低于考生(数字更大) → 保。"""
    # 考生位次30000，学校录取位次40000(更容易) → 保
    s = classify_strategy(student_rank=30000, school_rank=40000)
    assert s == Strategy.SAFE


def test_classify_strategy_boundary():
    """边界：恰好5%以内算稳。"""
    # 30000 * 0.95 = 28500，28500-31500区间算稳
    assert classify_strategy(student_rank=30000, school_rank=28500) == Strategy.STABLE
    assert classify_strategy(student_rank=30000, school_rank=28400) == Strategy.SPRINT
    assert classify_strategy(student_rank=30000, school_rank=31500) == Strategy.STABLE
    assert classify_strategy(student_rank=30000, school_rank=31600) == Strategy.SAFE


# ===== 4. 录取概率估算 =====
def test_estimate_probability_high_when_match():
    """位次完全匹配 → 高概率。"""
    p = estimate_probability(student_rank=30000, school_rank=30000)
    assert p.probability >= 0.85


def test_estimate_probability_low_when_sprint():
    """冲的志愿(学校位次远优于考生) → 低概率。"""
    p = estimate_probability(student_rank=30000, school_rank=20000)
    assert p.probability < 0.5


def test_estimate_probability_high_when_safe():
    """保的志愿(学校位次远低于考生) → 高概率。"""
    p = estimate_probability(student_rank=30000, school_rank=50000)
    assert p.probability >= 0.95


# ===== 5. 志愿表生成（端到端）=====
def test_generate_table_classifies_all_three_buckets():
    """考生543分(位次78624，河师大附近)，各校分到冲稳保。

    郑州22963(ratio0.29)过远→过滤；河南大学37744(ratio0.48)→冲；
    河师大78624→稳；财经/中原工/农大→保。
    """
    table = generate_volunteer_table(
        student=_student(543),
        admissions=ADMISSIONS_2024,
        rank_entries=RANK_ENTRIES_2024,
        track="理科",
        data_year=2024,
    )
    # 河大(0.48)在冲，郑州大学(0.29)过远被过滤
    assert any(s.school == "河南大学" for s in table.sprint)
    assert all(s.school != "郑州大学" for s in table.sprint + table.stable + table.safe)
    assert any(s.school == "河南师范大学" for s in table.stable)
    assert any(s.school == "河南农业大学" for s in table.safe)


def test_generate_table_sprint_heavy_when_aggressive():
    """冲型考生 → 冲档配额更大（即使可冲的校少，配额上限更高）。"""
    table_balanced = generate_volunteer_table(
        student=_student(543, RiskPreference.BALANCED),
        admissions=ADMISSIONS_2024, rank_entries=RANK_ENTRIES_2024,
        track="理科", data_year=2024,
    )
    table_aggr = generate_volunteer_table(
        student=_student(543, RiskPreference.AGGRESSIVE),
        admissions=ADMISSIONS_2024, rank_entries=RANK_ENTRIES_2024,
        track="理科", data_year=2024,
    )
    # 冲型考生冲档配额(6) > 稳型考生冲档配额(3)，且保档配额更少
    # 实际冲的校数受数据限制，但稳型考生保档应>=冲型考生保档
    assert len(table_balanced.safe) >= len(table_aggr.safe)


def test_generate_table_safe_heavy_when_safe_pref():
    """稳型考生 → 保档更多（求稳）。"""
    table = generate_volunteer_table(
        student=_student(543, RiskPreference.SAFE),
        admissions=ADMISSIONS_2024,
        rank_entries=RANK_ENTRIES_2024,
        track="理科",
        data_year=2024,
    )
    assert len(table.safe) >= len(table.sprint)


def test_generate_table_filters_wrong_track():
    """track不匹配的录取数据应被剔除。"""
    # 混入一条文科数据
    wrong = ADMISSIONS_2024 + [
        AdmissionRecord(school="文科校", major="普通类", province="河南", year=2024,
                        track="文科", min_score=550, min_rank=10000, avg_score=560,
                        batch=Batch.FIRST, source="test", as_of=__import__("datetime").date(2024, 7, 1),
                        confidence=0.9),
    ]
    table = generate_volunteer_table(
        student=_student(543), admissions=wrong,
        rank_entries=RANK_ENTRIES_2024, track="理科", data_year=2024,
    )
    all_schools = [s.school for s in table.sprint + table.stable + table.safe]
    assert "文科校" not in all_schools


def test_generate_table_filters_wrong_year():
    """年份不匹配的数据应被剔除。"""
    wrong = ADMISSIONS_2024 + [
        AdmissionRecord(school="旧年校", major="普通类", province="河南", year=2023,
                        track="理科", min_score=550, min_rank=10000, avg_score=560,
                        batch=Batch.FIRST, source="test", as_of=__import__("datetime").date(2023, 7, 1),
                        confidence=0.9),
    ]
    table = generate_volunteer_table(
        student=_student(543), admissions=wrong,
        rank_entries=RANK_ENTRIES_2024, track="理科", data_year=2024,
    )
    all_schools = [s.school for s in table.sprint + table.stable + table.safe]
    assert "旧年校" not in all_schools


def test_generate_table_source_note():
    """志愿表应含数据来源与时效说明。"""
    table = generate_volunteer_table(
        student=_student(543), admissions=ADMISSIONS_2024,
        rank_entries=RANK_ENTRIES_2024, track="理科", data_year=2024,
    )
    assert "2024" in table.source_note
    assert "历史" in table.source_note or "预测" in table.source_note


def test_generate_table_empty_admissions():
    """无录取数据时返回空表（不报错）。"""
    table = generate_volunteer_table(
        student=_student(543), admissions=[],
        rank_entries=RANK_ENTRIES_2024, track="理科", data_year=2024,
    )
    assert table.sprint == []
    assert table.stable == []
    assert table.safe == []
