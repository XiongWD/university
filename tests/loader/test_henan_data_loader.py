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
    zzu = next(g for g in groups if g.school_name == "郑州大学" and g.track == "物理类")
    assert zzu.elective_subject_requirement["require"] == ["化学"]


def test_load_enrollment_plans():
    plans = load_henan_enrollment_plans(SEED)
    assert plans[0].source_province == "河南"


def test_load_employment_signals():
    signals = load_henan_employment_signals(SEED)
    assert signals[0].major_name == "计算机科学与技术"
