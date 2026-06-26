from app.models.target_evaluation import TargetEvaluationRequest, TargetEvaluationResult


def test_request_requires_source_province_and_target_school():
    req = TargetEvaluationRequest(
        source_province="河南",
        target_school="郑州大学",
        target_major="计算机科学与技术",
        total_score=620,
        primary_subject="物理",
        elective_subjects=["化学", "生物"],
        exam_foreign_language="英语",
        foreign_language_score=125,
        math_score=130,
    )
    assert req.source_province == "河南"
    assert req.target_school == "郑州大学"


def test_result_can_report_missing_2026_plan():
    result = TargetEvaluationResult(
        target_school="郑州大学",
        target_major="计算机科学与技术",
        source_province="河南",
        eligibility={"eligible": False, "blocked_reasons": [], "review_warnings": ["缺少2026招生计划"]},
        group_admission={"risk_band": "数据不足", "basis": "", "student_rank": None, "baseline_rank": None, "data_year_used": None, "confidence": 0.2},
        major_admission={"risk_band": "数据不足", "target_major_available": False, "plan_count": None, "basis": "", "adjustment_risk": "数据不足"},
        sources=[],
        missing_data=["2026_enrollment_plan"],
        recommendation_summary="缺少目标院校河南 2026 分专业计划，无法给出可靠评估",
    )
    assert "2026_enrollment_plan" in result.missing_data
