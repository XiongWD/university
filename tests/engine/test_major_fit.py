"""第2步专业适配引擎测试：market_value × student_fit 乘法门控。

验证核心纠正：数学差的学生即使计算机市场分高，major_value也坍缩，不排前列。
"""
from datetime import date

import pytest

from app.engine.major_fit import (
    compute_major_value,
    compute_student_fit,
    _math_fit,
    _foreign_language_fit,
)
from app.engine.job_market import MarketScores
from app.models.job_market import CareerStage
from app.models.major import (
    Barriers, EmploymentDensity, Major, SalaryQuantile, Upside,
)
from app.models.student import (
    FamilyResources, RiskPreference, StudentProfile,
)


def _major(name="计算机科学与技术", category="工学", math_req=True, eng_req=False, postgrad=False):
    return Major(
        name=name, category=category,
        employment_density=EmploymentDensity(jobs=10000, frequency=0.8, city_coverage=0.7),
        salary=SalaryQuantile(p25=8000, p50=12000, p75=18000),
        barriers=Barriers(english=eng_req, math=math_req, certificate=False, postgrad=postgrad),
        upside=Upside(management=True, freelance=True, cross_industry=True),
        source="test", as_of=date(2026, 1, 1), confidence=0.9,
    )


def _student(math_score=95, foreign_lang="英语", foreign_score=110, risk="稳", interests=None):
    return StudentProfile(
        province="河南", total_score=480,
        subject_scores={"总分": 480},
        family_resources=FamilyResources(), gender="男",
        interests=interests or [], strengths=[],
        risk_preference=RiskPreference(risk),
        foreign_language=foreign_lang,
        elective_subjects=["政治", "地理"],
        subject_scores_detail={"数学": math_score, "外语": foreign_score},
        source="test", as_of=date(2026, 6, 25), confidence=1.0,
    )


def _market(current=0.7, future=0.6, stage=CareerStage.SUNRISE, evidence="A"):
    return MarketScores(
        current_market_score=current, future_outlook_score=future,
        career_stage=stage, salary_index=0.7, demand_index=0.8, growth_index=0.7,
        evidence_level=evidence, breakdown_note="test",
    )


# ===== 乘法门控核心测试（P0关键）=====
def test_multiplicative_gating_weak_math_collapses():
    """数学差的学生+计算机(市场高) → major_value坍缩，不排前列。"""
    strong_math = _student(math_score=130)
    weak_math = _student(math_score=70)  # 数学极弱
    cs_major = _major("计算机科学与技术", math_req=True)
    market = _market(current=0.85)  # 计算机市场分高

    val_strong, _ = compute_major_value(market, strong_math, cs_major)
    val_weak, _ = compute_major_value(market, weak_math, cs_major)
    # 弱数学的major_value应显著低于强数学（乘法门控生效）
    assert val_weak < val_strong * 0.5
    # 弱数学的不应超过0.4（坍缩，不排前列）
    assert val_weak < 0.4


def test_high_market_does_not_rescue_poor_fit():
    """市场分0.9但适配0.2 → major_value≤0.18（乘法，非加法）。"""
    poor_fit_student = _student(math_score=60, foreign_score=60)
    math_heavy_major = _major("人工智能", math_req=True, eng_req=True)
    market = _market(current=0.9, future=0.85)
    val, breakdown = compute_major_value(market, poor_fit_student, math_heavy_major)
    # 乘法：market_value~0.88 × student_fit(低) → 应远低于0.88
    assert val < 0.4
    assert breakdown["major_value"] == val


def test_good_fit_good_market_high_value():
    """适配好+市场好 → 高分。"""
    good_student = _student(math_score=135, foreign_score=125)
    cs = _major("计算机科学与技术", math_req=True)
    market = _market(current=0.85)
    val, _ = compute_major_value(market, good_student, cs)
    assert val > 0.6


# ===== 单维适配测试 =====
def test_math_fit_no_requirement_is_neutral():
    """不要求数学的专业 → 数学适配1.0。"""
    s = _student(math_score=50)
    m = _major("汉语言文学", math_req=False)
    assert _math_fit(s, m) == 1.0


def test_math_fit_grades():
    """数学适配分级。"""
    m = _major(math_req=True)
    assert _math_fit(_student(math_score=130), m) == 1.0
    assert _math_fit(_student(math_score=105), m) == 0.8
    assert _math_fit(_student(math_score=70), m) == 0.15


def test_foreign_language_fit_japanese_vs_english_requirement():
    """日语考生+要求英语专业 → 适配降级(0.4)，但非0（可补救）。"""
    ja_student = _student(foreign_lang="日语")
    en_required_major = _major("英语", eng_req=True)
    assert _foreign_language_fit(ja_student, en_required_major) == 0.4
    # 日语考生+不要求英语 → 1.0
    no_en_major = _major("历史学", eng_req=False)
    assert _foreign_language_fit(ja_student, no_en_major) == 1.0


def test_interest_fit_match():
    """兴趣匹配加分。"""
    s = _student(interests=["计算机", "编程"])
    m = _major("计算机科学与技术")
    assert _interest_fit_check(s, m) == 1.0


def _interest_fit_check(student, major):
    from app.engine.major_fit import _interest_fit
    return _interest_fit(student, major)


# ===== student_fit 整体测试 =====
def test_student_fit_range():
    """适配分在[0,1]。"""
    s = _student()
    m = _major()
    fit = compute_student_fit(s, m)
    assert 0 <= fit <= 1


def test_stable_student_postgrad_penalty():
    """稳健考生+需考研专业 → 适配略降。"""
    stable = _student(risk="稳")
    aggressive = _student(risk="冲")
    postgrad_major = _major("临床医学", postgrad=True)
    fit_stable = compute_student_fit(stable, postgrad_major)
    fit_aggr = compute_student_fit(aggressive, postgrad_major)
    assert fit_stable < fit_aggr  # 稳健对考研专业更保守


# ===== 弟弟场景（480+日语+数学弱）=====
def test_brother_scenario_japanese_weak_math():
    """弟弟480+日语+数学弱：计算机(数学要求)应显著低于历史学(不要求数学)。"""
    brother = _student(math_score=75, foreign_lang="日语", foreign_score=110)
    cs = _major("计算机科学与技术", math_req=True)
    history = _major("历史学", math_req=False, category="历史学")
    market_cs = _market(current=0.85)  # 计算机市场高
    market_history = _market(current=0.45)  # 历史/师范市场一般

    val_cs, _ = compute_major_value(market_cs, brother, cs)
    val_hist, _ = compute_major_value(market_history, brother, history)
    # 关键：弟弟数学弱，即使计算机市场分高，major_value应低于不要求数学的历史学
    # 这是乘法门控的核心价值——不让弱适配的高市场专业误导推荐
    print(f"\n弟弟场景: 计算机(市场高但数学弱)={val_cs} vs 历史学(市场一般但适配好)={val_hist}")
    assert val_cs < val_hist  # 适配差的专业不应因市场高而排前列
