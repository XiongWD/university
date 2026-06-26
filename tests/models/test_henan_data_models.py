from app.models.henan_data import (
    HenanAdmissionPolicy,
    HenanUniversity,
    HenanProgramGroup,
    HenanEnrollmentPlan,
    MajorEmploymentSignal,
)


def test_policy_has_parallel_volunteer_count_and_adjustment_rule():
    policy = HenanAdmissionPolicy(
        year=2026,
        province="河南",
        batch="本科批",
        track="历史类",
        parallel_volunteer_count=48,
        volunteer_unit="院校专业组",
        major_count_per_group=6,
        has_major_adjustment=True,
        filing_rule_summary="平行志愿，按位次投档",
        source_name="河南省教育考试院",
        source_url="https://www.haeea.cn/",
        as_of="2026-06-26",
        confidence=0.9,
    )
    assert policy.parallel_volunteer_count == 48
    assert policy.volunteer_unit == "院校专业组"


def test_program_group_supports_japanese_language_risk_fields():
    group = HenanProgramGroup(
        year=2026,
        track="历史类",
        school_code="10475",
        school_name="河南大学",
        major_group_code="101",
        major_group_name="历史类不限组",
        included_majors=["汉语言文学"],
        primary_subject_requirement="历史",
        elective_subject_requirement={},
        accepted_exam_languages=["英语", "日语"],
        public_foreign_languages=["英语"],
        single_subject_requirements=[],
        adjustment_scope="组内专业",
        source_name="河南大学本科招生网",
        source_url="https://zs.henu.edu.cn/",
        as_of="2026-06-26",
        confidence=0.8,
        review_status="verified",
    )
    assert group.public_foreign_languages == ["英语"]


def test_enrollment_plan_is_henan_specific():
    plan = HenanEnrollmentPlan(
        year=2026,
        source_province="河南",
        school_code="10459",
        school_name="郑州大学",
        major_group_code="501",
        major_name="计算机科学与技术",
        plan_count=120,
        school_system_years=4,
        tuition=5700,
        accommodation=1100,
        batch="本科批",
        track="物理类",
        source_name="郑州大学本科招生网",
        source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26",
        confidence=0.9,
    )
    assert plan.source_province == "河南"


def test_employment_signal_can_mark_insufficient_data():
    signal = MajorEmploymentSignal(
        major_name="历史学",
        direction="师范教育",
        policy_signal="稳定",
        domestic_demand_summary="以教师编制、教培、文博方向为主",
        job_market_city_scope="河南",
        evidence_level="C",
        source_name="阳光高考专业库",
        source_url="https://gaokao.chsi.com.cn/",
        as_of="2026-06-26",
        confidence=0.6,
    )
    assert signal.boss_job_count is None
