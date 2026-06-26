import pytest

from app.engine.admission_data_provider import HenanAdmissionDataProvider


def test_henan_provider_only_serves_henan_candidates():
    provider = HenanAdmissionDataProvider()
    assert provider.source_province == "河南"

    with pytest.raises(ValueError, match="仅支持河南"):
        provider.ensure_supported("山东")


def test_provider_keeps_henan_plans_for_in_and_out_of_province_schools():
    provider = HenanAdmissionDataProvider()
    plans = [
        {"source_province": "河南", "school_origin_province": "河南", "school_name": "郑州大学"},
        {"source_province": "河南", "school_origin_province": "湖北", "school_name": "武汉大学"},
        {"source_province": "山东", "school_origin_province": "河南", "school_name": "郑州大学"},
    ]

    result = provider.filter_plans_for_source_province(plans, "河南")

    assert [item["school_name"] for item in result] == ["郑州大学", "武汉大学"]
