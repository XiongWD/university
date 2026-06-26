"""advisory engine 测试：affordability 4 级 + market×fit 门控。"""
from app.engine.advisory import classify_affordability
from app.models.life_path import FamilyBudget


def _budget(income=80000, savings=20000, annual_edu=25000, loan=0, aid=0):
    return FamilyBudget(
        annual_income=income, available_savings=savings,
        max_annual_education_budget=annual_edu,
        accepted_loan_amount=loan, confirmed_aid=aid,
    )


def test_affordability_affordable():
    # affordable_total = 20000 + 4*25000 = 120000；cost <= 120000 → 可承受
    assert classify_affordability(100000, _budget()) == "可承受"


def test_affordability_pressure():
    # cost 130000 > affordable_total 120000；income 100000 → 130000/100000=1.3 → 有压力
    assert classify_affordability(130000, _budget(income=100000)) == "有压力"


def test_affordability_burden():
    # cost 200000 > affordable 120000；income 80000 → 200000/80000=2.5 ∈(1.5,3] → 明显负担
    assert classify_affordability(200000, _budget(income=80000)) == "明显负担"


def test_affordability_over_budget():
    # ratio 500000/80000=6.25 > 3 → 超预算
    assert classify_affordability(500000, _budget(income=80000)) == "超预算"


def test_major_value_is_market_times_fit():
    """§3.4 乘法门控：major_value == market_value × student_fit。"""
    import yaml
    from pathlib import Path
    from app.engine.major_fit import compute_major_value_academic
    from app.models.eligibility import StudentAcademicProfile, EnglishLevel
    from app.models.job_market import MarketScores, CareerStage
    from app.models.major import Major

    # 用真实 major（避免手工构造嵌套必填字段）
    majors_data = yaml.safe_load(
        Path("data/seed/majors/majors.yaml").read_text(encoding="utf-8")
    ) or []
    major = Major.model_validate(majors_data[0])

    market = MarketScores(
        current_market_score=0.8, future_outlook_score=0.7,
        career_stage=CareerStage.SUNRISE, salary_index=0.8, demand_index=0.7,
        growth_index=0.8, evidence_level="B", breakdown_note="",
    )
    profile = StudentAcademicProfile(
        province="河南", total_score=543, primary_subject="历史",
        math_score=120, foreign_language_score=120,
        english_actual_level=EnglishLevel.INTERMEDIATE,
    )
    mv, breakdown = compute_major_value_academic(market, profile, major)
    assert abs(breakdown["major_value"] - breakdown["market_value"] * breakdown["student_fit"]) < 0.01
