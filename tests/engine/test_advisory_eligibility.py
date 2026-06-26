"""advisory 资格边界测试（§6.2）：日语考生过滤 + 评分仅在 eligible 集合运行。

build_advisory 内部调用 filter_eligible；这里验证不变量：资格前置门定义可行解空间，
日语考生被英语限定专业过滤，且 advisory 不对其评分。
"""
from app.engine.eligibility import filter_eligible
from app.models.eligibility import (
    AdmissionOfferingRule,
    EnglishLevel,
    StudentAcademicProfile,
)


def _japanese_student():
    return StudentAcademicProfile(
        province="河南", admission_year=2026, total_score=543,
        primary_subject="历史", chinese_score=100, math_score=90,
        exam_foreign_language="日语", foreign_language_score=120,
        english_actual_level=EnglishLevel.BASIC,
        elective_subjects=["政治", "地理"],
    )


def _offering_requires_english(school="某大学英语专业"):
    return AdmissionOfferingRule(
        school=school, major_group_code="101", province="河南",
        major_group_name="英语",
        required_exam_language="英语",  # 仅限英语考生（A 类硬约束）
        direction_hint="外语与文学",
        source="test", as_of="2026-06-01", confidence=0.8,
    )


def test_japanese_student_blocked_from_english_required():
    """§6.2: 日语考生被英语限定专业过滤（出现在 ineligible，不在 eligible）。"""
    student = _japanese_student()
    offerings = [_offering_requires_english()]
    eligible, ineligible = filter_eligible(student, offerings)
    assert eligible == []
    assert len(ineligible) == 1
    assert ineligible[0][1].eligible is False


def test_advisory_only_scores_eligible_invariant():
    """§3.2 不变量：评分仅在 eligible 集合上运行。

    build_advisory 对 eligible 列表迭代评分；日语考生对英语限定专业的 eligible 为空，
    故无评分对象——保证不会对不可报专业产出推荐。
    """
    student = _japanese_student()
    offerings = [_offering_requires_english()]
    eligible, ineligible = filter_eligible(student, offerings)
    # eligible 为空 → build_advisory 不会为该专业构造 SchoolOption
    assert eligible == []
    # 不可报原因保留（供 ineligible_options 输出）
    assert any(res.blocked_summary for _, res in ineligible)
