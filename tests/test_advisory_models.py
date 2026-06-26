"""advisory 输出模型测试（TDD：模型结构与字段）。"""
from app.models.advisory import (
    BudgetSummary,
    IneligibleReason,
    MajorDirectionAdvice,
    VolunteerAdvisoryResult,
)
from app.models.life_path import AdmissionBuckets


def test_major_direction_advice_fields():
    m = MajorDirectionAdvice(direction="计算机")
    assert m.direction == "计算机"
    assert m.recommended_majors == []
    assert m.market_value == 0.0
    assert m.student_fit == 0.0
    assert m.major_value == 0.0
    assert m.fit_explanation == []
    assert m.risk_warnings == []


def test_budget_summary_fields():
    b = BudgetSummary()
    assert b.affordability_status == ""
    for f in ("tuition_4y", "accommodation_4y", "living_4y", "total_4y", "affordable_total"):
        assert hasattr(b, f)


def test_ineligible_reason_fields():
    r = IneligibleReason(school="某大学", blocked_summary="语种不符")
    assert r.school == "某大学"
    assert r.reasons == []
    assert r.blocked_summary == "语种不符"


def test_volunteer_advisory_result_structure():
    r = VolunteerAdvisoryResult(
        student_rank=1000, province="河南", track="历史类", data_year=2025,
        school_options=AdmissionBuckets(), budget_summary=BudgetSummary(),
    )
    assert r.student_rank == 1000
    assert r.major_directions == []
    assert isinstance(r.school_options, AdmissionBuckets)
    assert r.ineligible_options == []
    assert r.notes == []
