from app.models.program_plan import ProgramGroupRule, EnrollmentPlan, BatchLineDecision


def test_program_group_rule_requires_source_metadata():
    rule = ProgramGroupRule(
        school="郑州大学",
        province="河南",
        year=2026,
        batch="本科批",
        major_group_code="501",
        major_group_name="物理类计算机组",
        primary_subject_requirement="物理",
        elective_subject_rule={"require": ["化学"], "any_of": []},
        included_majors=["计算机科学与技术"],
        source_name="郑州大学本科招生网",
        source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26",
        confidence=0.9,
        data_granularity="official_rule",
        review_status="verified",
    )
    assert rule.elective_subject_rule["require"] == ["化学"]


def test_enrollment_plan_tracks_source_province():
    plan = EnrollmentPlan(
        school="郑州大学",
        source_province="河南",
        year=2026,
        major_group_code="501",
        major_name="计算机科学与技术",
        plan_count=120,
        batch="本科批",
        source_name="郑州大学本科招生网",
        source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26",
        confidence=0.9,
        data_granularity="official_plan",
        review_status="verified",
    )
    assert plan.source_province == "河南"


def test_batch_line_decision_values():
    decision = BatchLineDecision(
        score=460,
        rank=91753,
        undergrad_line=471,
        junior_college_line=180,
        distance_to_undergrad_line=-11,
        batch_position="below_undergrad",
        recommendation_policy_note="低于本科线，普通本科仅可作为冲刺",
    )
    assert decision.batch_position == "below_undergrad"
