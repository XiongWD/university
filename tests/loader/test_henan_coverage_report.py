import pytest

from app.loader.henan_coverage_report import (
    assert_henan_launch_gate,
    build_henan_coverage_report,
)
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
