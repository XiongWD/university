"""Phase 3 适配测试：基于 StudentAcademicProfile（拆分字段）。

验证评审核心纠正：
- 英语适配用 english_actual_level（实际英语能力），非高考应试语种
- 数学适配区分：章程门槛(硬,Phase1已过滤) vs 学习风险(软,此处标风险不挡资格)
"""
from datetime import date

import pytest

from app.engine.major_fit import (
    _math_learning_risk,
    _english_adaptation,
    compute_student_fit_academic,
    compute_major_value_academic,
)
from app.engine.job_market import MarketScores
from app.models.eligibility import EnglishLevel, StudentAcademicProfile
from app.models.job_market import CareerStage
from app.models.major import Barriers, EmploymentDensity, Major, SalaryQuantile, Upside


def _major(name="计算机科学与技术", math_req=True, eng_req=False):
    return Major(
        name=name, category="工学",
        employment_density=EmploymentDensity(jobs=10000, frequency=0.8, city_coverage=0.7),
        salary=SalaryQuantile(p25=8000, p50=12000, p75=18000),
        barriers=Barriers(english=eng_req, math=math_req, certificate=False, postgrad=False),
        upside=Upside(management=True, freelance=True, cross_industry=True),
        source="test", as_of=date(2026, 1, 1), confidence=0.9,
    )


def _profile(math=75, lang="日语", eng_level=EnglishLevel.BASIC):
    return StudentAcademicProfile(
        province="河南", admission_year=2026, total_score=480,
        primary_subject="历史", chinese_score=100, math_score=math,
        exam_foreign_language=lang, foreign_language_score=120,
        english_actual_level=eng_level, elective_subjects=["政治", "地理"],
    )


def _market(current=0.7, future=0.6):
    return MarketScores(
        current_market_score=current, future_outlook_score=future,
        career_stage=CareerStage.SUNRISE, salary_index=0.7, demand_index=0.8,
        growth_index=0.7, evidence_level="A", breakdown_note="test",
    )


# ===== 英语适配用 english_actual_level（核心纠正）=====
def test_english_adaptation_uses_actual_level_not_exam_language():
    """日语考生+英语能力advanced → 适配高（用实际英语能力，非高考语种）。"""
    profile = _profile(lang="日语", eng_level=EnglishLevel.ADVANCED)
    m = _major("跨境电商", eng_req=True)
    fit = _english_adaptation(profile, m, english_dependency="medium")
    assert fit > 0.6  # advanced实际英语能力→适配不低，尽管高考语种是日语


def test_english_adaptation_low_for_basic_japanese_student():
    """日语考生+英语能力basic → 适配低（真实反映英语薄弱）。"""
    profile = _profile(lang="日语", eng_level=EnglishLevel.BASIC)
    m = _major("跨境电商", eng_req=True)
    fit = _english_adaptation(profile, m, english_dependency="high")
    assert fit < 0.4  # basic+高英语依赖→低适配


def test_english_adaptation_none_level_very_low():
    """英语能力none → 极低适配。"""
    profile = _profile(eng_level=EnglishLevel.NONE)
    m = _major(eng_req=True)
    assert _english_adaptation(profile, m, "high") < 0.2


def test_no_english_dependency_means_no_penalty():
    """专业不依赖英语→适配1.0（不构成障碍）。"""
    profile = _profile(eng_level=EnglishLevel.NONE)
    m = _major("历史学", eng_req=False)
    assert _english_adaptation(profile, m, "low") == 1.0


# ===== 数学学习风险（软，非资格门槛）=====
def test_math_is_learning_risk_not_hard_block():
    """数学弱(75)+计算机 → 学习风险标记，但不挡资格（Phase1管资格）。"""
    profile = _profile(math=75)
    m = _major("计算机", math_req=True)
    risk = _math_learning_risk(profile, m)
    assert risk < 0.5  # 学习风险高
    # 但这返回的是风险分(软)，不是True/False资格判定


def test_math_risk_grades():
    m = _major(math_req=True)
    assert _math_learning_risk(_profile(math=130), m) == 1.0
    assert _math_learning_risk(_profile(math=75), m) == 0.4
    assert _math_learning_risk(_profile(math=60), m) == 0.2


def test_no_math_requirement_no_risk():
    """不要求数学的专业→无风险(1.0)。"""
    profile = _profile(math=50)
    m = _major("汉语言文学", math_req=False)
    assert _math_learning_risk(profile, m) == 1.0


# ===== Phase 3 整体适配 =====
def test_brother_japanese_basic_english_drops_english_heavy_major():
    """弟弟(日语+basic英语)+英语高依赖专业(跨境电商)→适配显著降。"""
    brother = _profile(lang="日语", eng_level=EnglishLevel.BASIC, math=75)
    cs = _major("跨境电商", math_req=True, eng_req=True)
    fit_heavy = compute_student_fit_academic(brother, cs, english_dependency="high")
    # 数学弱(0.4) × 英语弱(basic高依赖) → 应该很低
    assert fit_heavy < 0.25


def test_major_value_multiplicative_gating_academic():
    """乘法门控在academic版本同样生效。"""
    brother = _profile(lang="日语", eng_level=EnglishLevel.BASIC, math=70)
    cs = _major("计算机", math_req=True, eng_req=True)
    market = _market(current=0.9)  # 计算机市场高
    val, breakdown = compute_major_value_academic(market, brother, cs, english_dependency="high")
    # 弱适配×高市场→坍缩
    assert val < 0.3
    assert breakdown["english_actual_level"] == "basic"


def test_breakdown_shows_split_fields():
    """breakdown显示拆分字段（英语实际能力+高考语种分开）。"""
    profile = _profile(lang="日语", eng_level=EnglishLevel.INTERMEDIATE)
    m = _major(eng_req=True)
    _, breakdown = compute_major_value_academic(_market(), profile, m, "medium")
    assert breakdown["english_actual_level"] == "intermediate"
    assert breakdown["exam_foreign_language"] == "日语"
    assert "math_learning_risk" in breakdown
    assert "english_adaptation" in breakdown
