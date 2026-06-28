import pytest

from app.loader.henan_coverage_report import (
    assert_henan_launch_gate,
    build_henan_readiness_status,
    build_henan_coverage_report,
)
from app.loader.henan_scope import is_henan_history_regular_group
from app.models.henan_data import HenanEnrollmentPlan, HenanProgramGroup
from app.loader.henan_source_registry_loader import load_henan_source_registry


def test_coverage_report_keeps_historical_and_2026_counts_separate():
    registry = load_henan_source_registry("data/seed/henan/source_registry.yaml")
    report = build_henan_coverage_report(
        registry,
        records={
            "score_segment_2025": 500,
            "score_segment_2024": 500,
            "admission_history_2025": 3000,
            "admission_history_2024": 2800,
            "universities_2026": 1500,
            "program_groups_2026": 3200,
            "enrollment_plans_henan_2026": 12000,
            "tuition_accommodation_2026": 9000,
            "major_employment_signal_2026": 180,
        },
    )

    assert report["historical"]["score_segment_2025"] == 500
    assert report["historical"]["admission_history_2024"] == 2800
    assert report["latest_2026"]["program_groups_2026"] == 3200
    assert report["latest_2026"]["enrollment_plans_henan_2026"] == 12000
    assert report["current_signal"]["major_employment_signal_2026"] == 180


def test_launch_gate_blocks_when_2026_plan_or_group_missing():
    registry = load_henan_source_registry("data/seed/henan/source_registry.yaml")
    report = build_henan_coverage_report(
        registry,
        records={
            "score_segment_2025": 500,
            "score_segment_2024": 500,
            "admission_history_2025": 3000,
            "admission_history_2024": 2800,
            "universities_2026": 1500,
            "program_groups_2026": 0,
            "enrollment_plans_henan_2026": 0,
            "tuition_accommodation_2026": 9000,
            "major_employment_signal_2026": 180,
        },
    )

    with pytest.raises(ValueError, match="program_groups_2026"):
        assert_henan_launch_gate(report)


def test_launch_gate_allows_missing_employment_salary_data():
    registry = load_henan_source_registry("data/seed/henan/source_registry.yaml")
    report = build_henan_coverage_report(
        registry,
        records={
            "score_segment_2025": 500,
            "score_segment_2024": 500,
            "admission_history_2025": 3000,
            "admission_history_2024": 2800,
            "universities_2026": 1500,
            "program_groups_2026": 3200,
            "enrollment_plans_henan_2026": 12000,
            "tuition_accommodation_2026": 0,
            "major_employment_signal_2026": 0,
        },
    )

    assert_henan_launch_gate(report)


def test_readiness_status_distinguishes_pilot_and_production():
    report = {
        "actual": {
            "universities_2026": 1110,
            "program_groups_2026": 2355,
            "enrollment_plans_henan_2026": 8266,
        },
        "quality": {
            "verified_program_groups_2026": 2183,
            "verified_enrollment_plans_2026": 7935,
            "nonzero_enrollment_plans_2026": 8266,
            "verified_2025_history": 2919,
            "verified_2024_history": 3393,
            "verified_2025_major_group_history": 1996,
            "verified_2024_major_group_history": 2315,
            "single_subject_requirement_groups_2026": 83,
            "public_foreign_language_groups_2026": 31,
            "accommodation_plans_2026": 1090,
            "official_catalog_source_ready": 0,
        },
    }

    status = build_henan_readiness_status(report)

    assert status["pilot_ready"] is True
    assert status["production_ready"] is False
    assert status["coverage_status"] == "pilot_ready"


def test_readiness_status_allows_gaokao_cn_only_when_scope_coverage_is_high():
    report = {
        "actual": {
            "universities_2026": 1110,
            "program_groups_2026": 1000,
            "enrollment_plans_henan_2026": 4000,
        },
        "quality": {
            "verified_program_groups_2026": 990,
            "verified_enrollment_plans_2026": 3950,
            "nonzero_enrollment_plans_2026": 4000,
            "verified_2025_history": 2919,
            "verified_2024_history": 3393,
            "verified_2025_major_group_history": 1996,
            "verified_2024_major_group_history": 2315,
            "single_subject_requirement_groups_2026": 83,
            "public_foreign_language_groups_2026": 31,
            "accommodation_plans_2026": 1090,
            "official_catalog_source_ready": 0,
        },
    }

    status = build_henan_readiness_status(report)

    assert status["pilot_ready"] is True
    assert status["production_ready"] is False
    assert status["data_ready"] is True
    assert status["coverage_status"] == "pilot_ready"
    assert any("官方全量专业目录" in note for note in status["coverage_notes"])


def test_readiness_status_calls_out_full_verified_scope_when_only_official_source_missing():
    report = {
        "actual": {
            "universities_2026": 1096,
            "program_groups_2026": 2100,
            "enrollment_plans_henan_2026": 7863,
        },
        "quality": {
            "verified_program_groups_2026": 2100,
            "verified_enrollment_plans_2026": 7863,
            "nonzero_enrollment_plans_2026": 7863,
            "scoped_unverified_groups_2026": 0,
            "scoped_unverified_plans_2026": 0,
            "excluded_special_groups_2026": 255,
            "excluded_special_plans_2026": 403,
            "verified_2025_history": 2690,
            "verified_2024_history": 3139,
            "verified_2025_major_group_history": 1778,
            "verified_2024_major_group_history": 2071,
            "single_subject_requirement_groups_2026": 83,
            "public_foreign_language_groups_2026": 31,
            "accommodation_plans_2026": 1023,
            "official_catalog_source_ready": 0,
        },
    }

    status = build_henan_readiness_status(report)

    assert status["pilot_ready"] is True
    assert status["production_ready"] is False
    assert any("全部达到 verified" in note for note in status["coverage_notes"])


def test_regular_scope_excludes_special_art_and_preparatory_groups_but_keeps_sino_foreign():
    base_group = dict(
        year=2026,
        track="历史类",
        batch="本科批",
        school_code="1",
        school_name="测试大学",
        major_group_name="测试大学-1001",
        included_majors=["法学"],
        major_codes=["2001"],
        primary_subject_requirement="历史",
        elective_subject_requirement={},
        accepted_exam_languages=[],
        public_foreign_languages=[],
        single_subject_requirements=[],
        adjustment_scope="组内专业",
        physical_restrictions="",
        source_name="gaokao.cn",
        source_url="https://www.gaokao.cn/school/1/sturule",
        as_of="2026-06-27T00:00:00+00:00",
        confidence=0.9,
        review_status="verified",
    )
    base_plan = dict(
        year=2026,
        source_province="河南",
        school_origin_province="河南",
        is_henan_local_school=True,
        school_code="1",
        school_name="测试大学",
        major_name="法学",
        plan_count=2,
        tuition=5000,
        accommodation=1000,
        batch="本科批",
        track="历史类",
        campus="主校区",
        physical_restrictions="",
        accepted_exam_languages="",
        source_name="gaokao.cn",
        source_url="https://www.gaokao.cn/school/1/sturule",
        as_of="2026-06-27T00:00:00+00:00",
        confidence=0.9,
        review_status="verified",
        remarks="",
    )

    regular_group = HenanProgramGroup.model_validate(
        {**base_group, "major_group_code": "1001", "special_qualification_type": ""}
    )
    regular_plan = HenanEnrollmentPlan.model_validate(
        {**base_plan, "major_group_code": "1001", "special_qualification_type": ""}
    )
    sino_group = HenanProgramGroup.model_validate(
        {**base_group, "major_group_code": "1002", "special_qualification_type": "中外合作"}
    )
    sino_plan = HenanEnrollmentPlan.model_validate(
        {
            **base_plan,
            "major_group_code": "1002",
            "special_qualification_type": "中外合作",
            "remarks": "（中外合作办学组）",
        }
    )
    national_group = HenanProgramGroup.model_validate(
        {**base_group, "major_group_code": "1003", "special_qualification_type": "国家专项"}
    )
    national_plan = HenanEnrollmentPlan.model_validate(
        {
            **base_plan,
            "major_group_code": "1003",
            "special_qualification_type": "国家专项",
            "remarks": "（国家专项计划组）",
        }
    )
    art_group = HenanProgramGroup.model_validate(
        {
            **base_group,
            "major_group_code": "1004",
            "included_majors": ["戏剧影视文学"],
            "major_codes": ["2004"],
            "special_qualification_type": "",
        }
    )
    art_plan = HenanEnrollmentPlan.model_validate(
        {
            **base_plan,
            "major_group_code": "1004",
            "major_name": "戏剧影视文学",
            "remarks": "（不组织专业考试的艺术类专业组）（授予艺术学学士学位）",
        }
    )
    prep_group = HenanProgramGroup.model_validate(
        {
            **base_group,
            "major_group_code": "1005",
            "included_majors": ["预科班"],
            "major_codes": ["2005"],
            "special_qualification_type": "",
        }
    )
    prep_plan = HenanEnrollmentPlan.model_validate(
        {
            **base_plan,
            "major_group_code": "1005",
            "major_name": "预科班",
            "remarks": "（边防军人子女预科班）（预科组）",
        }
    )

    assert is_henan_history_regular_group(regular_group, [regular_plan]) is True
    assert is_henan_history_regular_group(sino_group, [sino_plan]) is True
    assert is_henan_history_regular_group(national_group, [national_plan]) is False
    assert is_henan_history_regular_group(art_group, [art_plan]) is False
    assert is_henan_history_regular_group(prep_group, [prep_plan]) is False
