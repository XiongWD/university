from pathlib import Path

from app.loader.henan_data_loader import (
    load_henan_policy,
    load_henan_universities,
    load_henan_program_groups,
    load_henan_enrollment_plans,
    load_henan_employment_signals,
)


SEED = Path("data/seed")


def test_load_policy():
    policies = load_henan_policy(SEED)
    assert policies[0].province == "河南"
    assert policies[0].parallel_volunteer_count == 48


def test_load_universities():
    universities = load_henan_universities(SEED)
    assert any(u.school_name == "郑州大学" for u in universities)


def test_load_program_groups():
    groups = load_henan_program_groups(SEED)
    zzu = next(g for g in groups if g.school_name == "郑州大学" and g.track == "历史类")
    # 历史类某些组有再选科目要求（思想政治）
    if zzu.elective_subject_requirement.get("require"):
        assert "思想政治" in zzu.elective_subject_requirement["require"]
    assert zzu.primary_subject_requirement == "历史"


def test_load_enrollment_plans():
    plans = load_henan_enrollment_plans(SEED)
    assert plans[0].source_province == "河南"


def test_load_traceability_fields_from_enrollment_plans_and_groups():
    plans = load_henan_enrollment_plans(SEED)
    groups = load_henan_program_groups(SEED)

    traced_plan = next(p for p in plans if p.source_api_endpoint)
    traced_group = next(g for g in groups if g.source_api_endpoint)

    assert "api-gaokao.zjzw.cn" in traced_plan.source_api_endpoint
    assert '"school_id"' in traced_plan.source_params
    assert traced_plan.source_response_checksum
    assert "api-gaokao.zjzw.cn" in traced_group.source_api_endpoint
    assert "v1/school/special_plan" in traced_group.source_params
    assert traced_group.source_params


def test_load_employment_signals():
    signals = load_henan_employment_signals(SEED)
    assert signals[0].major_name == "计算机科学与技术"
