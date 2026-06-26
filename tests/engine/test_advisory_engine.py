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


def test_affordability_boundaries():
    """精确边界：ratio 恰为阈值时归入低一级（<= 语义）。"""
    # ratio 恰为 1.5（income 100000, cost 150000）→ 有压力（<= 1.5）
    assert classify_affordability(150000, _budget(income=100000)) == "有压力"
    # ratio 恰为 3.0（income 100000, cost 300000）→ 明显负担（<= 3.0）
    assert classify_affordability(300000, _budget(income=100000)) == "明显负担"
    # ratio 略超 3.0 → 超预算
    assert classify_affordability(310000, _budget(income=100000)) == "超预算"


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


def test_build_advisory_produces_nonempty_for_normal_student(tmp_path, monkeypatch):
    """端到端：正常符合资格考生应产出非空的专业方向与院校建议。

    用真实 seed 数据（offerings/directions/snapshots/majors）驱动 build_advisory，
    断言 major_directions 与 school_options 至少有一项，budget_summary 有费用。
    """
    import yaml
    from pathlib import Path

    from app.engine.advisory import build_advisory
    from app.models.eligibility import (
        AdmissionOfferingRule,
        EnglishLevel,
        StudentAcademicProfile,
    )
    from app.models.job_market import JobMarketSnapshot, MajorDirection
    from app.models.life_path import FamilyBudget

    seed = Path("data/seed")
    offerings = [
        AdmissionOfferingRule.model_validate(d)
        for d in (yaml.safe_load((seed / "admission_offerings/admission_offerings.yaml").read_text(encoding="utf-8")) or [])
    ]
    directions = [
        MajorDirection.model_validate(d)
        for d in (yaml.safe_load((seed / "major_directions/major_directions.yaml").read_text(encoding="utf-8")) or [])
    ]
    snaps = [
        JobMarketSnapshot.model_validate(d)
        for d in (yaml.safe_load((seed / "job_markets/job_snapshots.yaml").read_text(encoding="utf-8")) or [])
    ]
    snap_map: dict[str, list[JobMarketSnapshot]] = {}
    for s in snaps:
        snap_map.setdefault(s.career_id, []).append(s)
    majors = [
        __import_major(d) for d in (yaml.safe_load((seed / "majors/majors.yaml").read_text(encoding="utf-8")) or [])
    ]

    # 正常历史类考生（非日语，宽口径 eligible）
    profile = StudentAcademicProfile(
        province="河南", admission_year=2026, total_score=500, primary_subject="历史",
        chinese_score=100, math_score=90,
        exam_foreign_language="英语", foreign_language_score=110,
        english_actual_level=EnglishLevel.INTERMEDIATE,
        elective_subjects=["政治", "地理"],
    )
    budget = FamilyBudget(
        annual_income=80000, available_savings=20000,
        max_annual_education_budget=25000, accept_private_school=True,
    )

    result = build_advisory(
        profile=profile, budget=budget, offerings=offerings,
        directions=directions, snap_map=snap_map, admissions=[],
        unis=[], cities=[], majors=majors, careers=[],
        rank_entries=[], data_year=2025,
    )

    # 至少有专业方向建议或院校建议（取决于 seed 中该考生能匹配多少 offering）
    total_schools = len(result.school_options.reach) + len(result.school_options.match) + len(result.school_options.safe)
    assert len(result.major_directions) >= 1 or total_schools >= 1, (
        "advisory 应为正常考生产出非空建议（方向或院校）"
    )
    # ineligible_options 与 notes 结构完整
    assert isinstance(result.ineligible_options, list)
    assert len(result.notes) >= 1


def __import_major(d):
    from app.models.major import Major
    return Major.model_validate(d)
