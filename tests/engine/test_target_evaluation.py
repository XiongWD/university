from app.engine.target_evaluation import evaluate_target
from app.models.target_evaluation import TargetEvaluationRequest
from app.models.program_plan import EnrollmentPlan, ProgramGroupRule


def test_no_source_province_plan_is_data_insufficient():
    req = TargetEvaluationRequest(
        source_province="河南",
        target_school="外省大学",
        target_major="计算机科学与技术",
        total_score=620,
        primary_subject="物理",
        elective_subjects=["化学", "生物"],
        math_score=130,
        foreign_language_score=125,
    )
    result = evaluate_target(req=req, plans=[], rules=[], admissions=[], rank_entries=[])
    assert result.group_admission.risk_band == "数据不足"
    assert "2026_enrollment_plan" in result.missing_data


def test_physics_target_without_required_chemistry_is_ineligible():
    req = TargetEvaluationRequest(
        source_province="河南",
        target_school="郑州大学",
        target_major="计算机科学与技术",
        total_score=620,
        primary_subject="物理",
        elective_subjects=["生物", "地理"],
        math_score=130,
        foreign_language_score=125,
    )
    plans = [EnrollmentPlan(
        school="郑州大学", source_province="河南", year=2026,
        major_group_code="501", major_name="计算机科学与技术",
        plan_count=120, batch="本科批",
        source_name="郑州大学本科招生网", source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26", confidence=0.9,
        data_granularity="official_plan", review_status="verified",
    )]
    rules = [ProgramGroupRule(
        school="郑州大学", province="河南", year=2026, batch="本科批",
        major_group_code="501", major_group_name="物理类计算机组",
        primary_subject_requirement="物理",
        elective_subject_rule={"require": ["化学"], "any_of": []},
        included_majors=["计算机科学与技术"],
        source_name="郑州大学本科招生网", source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26", confidence=0.9,
        data_granularity="official_rule", review_status="verified",
    )]
    result = evaluate_target(req=req, plans=plans, rules=rules, admissions=[], rank_entries=[])
    assert result.eligibility.eligible is False
    assert any("化学" in x for x in result.eligibility.blocked_reasons)


def test_eligible_target_reports_major_available_but_data_insufficient_risk():
    """资格满足但有计划：报告专业可报，但缺历史投档位次时风险为数据不足。"""
    req = TargetEvaluationRequest(
        source_province="河南",
        target_school="郑州大学",
        target_major="计算机科学与技术",
        total_score=620,
        primary_subject="物理",
        elective_subjects=["化学", "生物"],
        math_score=130,
        foreign_language_score=125,
    )
    plans = [EnrollmentPlan(
        school="郑州大学", source_province="河南", year=2026,
        major_group_code="501", major_name="计算机科学与技术",
        plan_count=180, batch="本科批",
        source_name="郑州大学本科招生网", source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26", confidence=0.9,
        data_granularity="official_plan", review_status="verified",
    )]
    rules = [ProgramGroupRule(
        school="郑州大学", province="河南", year=2026, batch="本科批",
        major_group_code="501", major_group_name="物理类计算机组",
        primary_subject_requirement="物理",
        elective_subject_rule={"require": ["化学"], "any_of": []},
        included_majors=["计算机科学与技术"],
        source_name="郑州大学本科招生网", source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26", confidence=0.9,
        data_granularity="official_rule", review_status="verified",
    )]
    result = evaluate_target(req=req, plans=plans, rules=rules, admissions=[], rank_entries=[])
    assert result.eligibility.eligible is True
    assert result.major_admission.target_major_available is True
    assert result.major_admission.plan_count == 180
    # 缺历史投档位次 → 风险档位为数据不足
    assert result.group_admission.risk_band == "数据不足"
    assert "historical_group_rank" in result.missing_data


def test_eligible_but_far_below_admission_is_high_risk():
    """资格可报 ≠ 能录得上：低分(位次233796)远弱于投档位次(21686) → 投档高风险，
    且即便服从调剂，调剂风险也不应是"低"（投不进档谈不上调剂）。
    回归修复：之前调剂风险只看是否服从调剂、不看投档风险，会给出误导性"低"。"""
    from datetime import date
    from app.models.admission import AdmissionRecord, Batch, DataGranularity

    req = TargetEvaluationRequest(
        source_province="河南", target_school="郑州大学", target_major="计算机科学与技术",
        total_score=480, primary_subject="物理", elective_subjects=["化学", "生物"],
        math_score=85, foreign_language_score=95, accept_adjustment=True,
    )
    plans = [EnrollmentPlan(
        school="郑州大学", source_province="河南", year=2026,
        major_group_code="501", major_name="计算机科学与技术",
        plan_count=180, batch="本科批",
        source_name="郑州大学本科招生网", source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26", confidence=0.9,
        data_granularity="official_plan", review_status="verified",
    )]
    rules = [ProgramGroupRule(
        school="郑州大学", province="河南", year=2026, batch="本科批",
        major_group_code="501", major_group_name="物理类计算机组",
        primary_subject_requirement="物理",
        elective_subject_rule={"require": ["化学"], "any_of": []},
        included_majors=["计算机科学与技术"],
        source_name="郑州大学本科招生网", source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26", confidence=0.9,
        data_granularity="official_rule", review_status="verified",
    )]
    # 2025 投档位次 21686（真实郑大数据量级）
    admissions = [AdmissionRecord(
        school="郑州大学", major="物理学类", province="河南", year=2025, track="物理类",
        min_score=626, min_rank=21686, avg_score=635, batch=Batch.UNDERGRAD,
        major_group="501", data_granularity=DataGranularity.GROUP,
        source="河南省教育考试院2025", as_of=date(2025, 7, 1), confidence=0.8,
    )]
    # 480 分对应位次约 233796（远弱于 21686）
    from app.models.provincial import ScoreRankEntry
    rank_entries = [ScoreRankEntry(score=480, count_at=300, cumulative_rank=233796)]

    result = evaluate_target(req=req, plans=plans, rules=rules, admissions=admissions, rank_entries=rank_entries)

    # 资格仍可报（选科满足），但投档必须高风险
    assert result.eligibility.eligible is True
    assert result.group_admission.risk_band == "高"
    assert result.major_admission.risk_band == "高"
    # 关键回归：服从调剂也不能是"低"——投档困难时调剂风险至少中高
    assert result.major_admission.adjustment_risk != "低"
    assert result.major_admission.adjustment_risk == "中高"
    # 总结必须点出"资格可报但录取难度大"，不能只说风险高让人误以为不可报
    assert "资格可报" in result.recommendation_summary
    assert "录取难度大" in result.recommendation_summary
