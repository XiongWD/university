from pathlib import Path

import pytest

from app.loader.henan_coverage_report import (
    assert_henan_recommendation_ready,
    build_actual_henan_coverage,
)


def test_actual_coverage_counts_seed_records():
    report = build_actual_henan_coverage(Path("data/seed"))
    assert report["actual"]["universities_2026"] >= 1
    assert report["actual"]["program_groups_2026"] >= 1
    assert report["actual"]["enrollment_plans_henan_2026"] >= 1
    assert "verified_program_groups_2026" in report["quality"]
    assert "nonzero_enrollment_plans_2026" in report["quality"]


def test_launch_gate_blocks_zero_plan_and_unverified_groups(tmp_path):
    report = {
        "actual": {
            "universities_2026": 4,
            "program_groups_2026": 5,
            "enrollment_plans_henan_2026": 3,
        },
        "quality": {
            "verified_program_groups_2026": 0,
            "verified_enrollment_plans_2026": 0,
            "nonzero_enrollment_plans_2026": 0,
            "verified_2025_history": 0,
        },
    }
    with pytest.raises(ValueError, match="verified_program_groups_2026"):
        assert_henan_recommendation_ready(report)
