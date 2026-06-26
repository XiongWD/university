from pathlib import Path

import pytest

from app.loader.henan_source_registry_loader import load_henan_source_registry


FIXTURE = Path("data/seed/henan/source_registry.yaml")


def test_registry_distinguishes_historical_and_2026_datasets():
    sources = load_henan_source_registry(FIXTURE)
    by_dataset = {source.dataset_key: source for source in sources}

    assert by_dataset["score_segment_2025"].year_type == "historical"
    assert by_dataset["score_segment_2024"].year_type == "historical"
    assert by_dataset["admission_history_2025"].year_type == "historical"
    assert by_dataset["admission_history_2024"].year_type == "historical"
    assert by_dataset["program_groups_2026"].year_type == "latest_2026"
    assert by_dataset["enrollment_plans_henan_2026"].year_type == "latest_2026"
    assert by_dataset["tuition_accommodation_2026"].year_type == "latest_2026"
    assert by_dataset["major_employment_signal_2026"].year_type == "current_signal"


def test_registry_requires_authoritative_primary_source():
    sources = load_henan_source_registry(FIXTURE)
    for source in sources:
        assert source.primary_source_name
        assert source.primary_source_url.startswith("https://") or source.primary_source_url.startswith("http://")
        assert source.required_fields
        assert source.verification_rules


def test_registry_rejects_unclassified_dataset(tmp_path):
    bad = tmp_path / "bad_registry.yaml"
    bad.write_text(
        """
- dataset_key: unclassified
  display_name: 未分类数据
  year_type: unknown
  primary_source_name: 河南省教育考试院
  primary_source_url: https://www.haeea.cn/
  required_fields: [school_code]
  verification_rules: [保留来源]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="year_type"):
        load_henan_source_registry(bad)
