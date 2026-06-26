from app.loader.henan_program_group_index import find_groups_by_major
from app.models.henan_data import HenanProgramGroup


def _group(code, majors, track="历史类", batch="本科批"):
    return HenanProgramGroup(
        year=2026,
        track=track,
        batch=batch,
        school_code="10469",
        school_name="河南牧业经济学院",
        major_group_code=code,
        major_group_name=f"{code}组",
        included_majors=majors,
        primary_subject_requirement="历史",
        elective_subject_requirement={},
        accepted_exam_languages=["英语", "日语"],
        public_foreign_languages=["英语"],
        adjustment_scope="组内专业",
        source_name="河南2026招生专业目录",
        source_url="https://www.haeea.cn/",
        as_of="2026-06-26",
        confidence=0.9,
    )


def test_find_groups_by_major_returns_all_matching_groups():
    groups = [
        _group("101", ["会计学", "财务管理"]),
        _group("105", ["会计学"], batch="本科批"),
        _group("201", ["动物医学"], track="物理类"),
    ]

    result = find_groups_by_major(groups, "10469", "会计学", "历史类", "本科批")

    assert [group.major_group_code for group in result] == ["101", "105"]


def test_find_groups_by_major_does_not_cross_track_or_school():
    groups = [
        _group("101", ["会计学"], track="历史类"),
        _group("201", ["会计学"], track="物理类"),
    ]

    result = find_groups_by_major(groups, "10469", "会计学", "历史类", "本科批")

    assert [group.major_group_code for group in result] == ["101"]
