from app.engine.henan_recommendation import (
    build_48_volunteer_draft,
    check_henan_eligibility,
    classify_henan_bucket,
    classify_group_bucket,
    get_bucket_quota,
)
from app.models.henan_data import HenanAdmissionPolicy, HenanProgramGroup


def _policy():
    return HenanAdmissionPolicy(
        year=2026,
        province="河南",
        batch="本科批",
        track="历史类",
        parallel_volunteer_count=48,
        volunteer_unit="院校专业组",
        major_count_per_group=6,
        has_major_adjustment=True,
        filing_rule_summary="平行志愿",
        source_name="河南省教育考试院",
        source_url="https://www.haeea.cn/",
        as_of="2026-06-26",
        confidence=0.7,
    )


def test_japanese_student_blocked_by_english_required_group():
    group = HenanProgramGroup(
        year=2026,
        track="历史类",
        school_code="x",
        school_name="测试大学",
        major_group_code="101",
        major_group_name="英语专业组",
        included_majors=["英语"],
        primary_subject_requirement="历史",
        elective_subject_requirement={},
        required_exam_language="英语",
        accepted_exam_languages=["英语"],
        public_foreign_languages=["英语"],
        single_subject_requirements=[],
        adjustment_scope="组内专业",
        source_name="招生章程",
        source_url="https://example.com",
        as_of="2026-06-26",
        confidence=0.9,
    )
    ok, blocked, warnings = check_henan_eligibility(
        profile={
            "primary_subject": "历史",
            "elective_subjects": ["政治", "地理"],
            "exam_foreign_language": "日语",
            "foreign_language_score": 120,
            "math_score": 90,
        },
        group=group,
    )
    assert ok is False
    assert any("英语语种" in x for x in blocked)


def test_bucket_classification():
    assert classify_henan_bucket(student_rank=52000, historical_rank=50000, policy_mode="冲") == "冲"
    assert classify_henan_bucket(student_rank=49000, historical_rank=50000, policy_mode="稳") == "稳"
    assert classify_henan_bucket(student_rank=40000, historical_rank=50000, policy_mode="保") == "保"


def test_group_bucket_requires_2026_plan_and_verified_group():
    assert classify_group_bucket(
        student_rank=40000,
        adjusted_rank=50000,
        has_2025_history=True,
        has_2026_plan=False,
        has_verified_group=True,
        confidence=0.9,
    ) == "不推荐"
    assert classify_group_bucket(
        student_rank=40000,
        adjusted_rank=50000,
        has_2025_history=True,
        has_2026_plan=True,
        has_verified_group=False,
        confidence=0.9,
    ) == "不推荐"


def test_group_bucket_does_not_mark_safe_without_2025_history_or_confidence():
    assert classify_group_bucket(
        student_rank=40000,
        adjusted_rank=50000,
        has_2025_history=False,
        has_2026_plan=True,
        has_verified_group=True,
        confidence=0.9,
    ) == "稳"
    assert classify_group_bucket(
        student_rank=40000,
        adjusted_rank=50000,
        has_2025_history=True,
        has_2026_plan=True,
        has_verified_group=True,
        confidence=0.5,
    ) == "稳"


def test_group_bucket_uses_rank_gap_thresholds():
    assert classify_group_bucket(58000, 50000, True, True, True, 0.9) == "不推荐"
    assert classify_group_bucket(54000, 50000, True, True, True, 0.9) == "冲"
    assert classify_group_bucket(49500, 50000, True, True, True, 0.9) == "稳"
    assert classify_group_bucket(43000, 50000, True, True, True, 0.9) == "保"


def test_bucket_quota_for_balanced_48_volunteers():
    quota = get_bucket_quota(48, "均衡", {"track": "物理类", "exam_foreign_language": "英语"})
    assert quota == {"冲": (8, 12), "稳": (20, 24), "保": (12, 16)}


def test_bucket_quota_defaults_to_conservative_for_history_japanese():
    quota = get_bucket_quota(48, "自动", {"track": "历史类", "exam_foreign_language": "日语"})
    assert quota == {"冲": (6, 8), "稳": (22, 26), "保": (14, 18)}


def test_bucket_quota_for_aggressive_48_volunteers():
    quota = get_bucket_quota(48, "积极", {"track": "物理类", "exam_foreign_language": "英语"})
    assert quota == {"冲": (12, 16), "稳": (18, 22), "保": (8, 12)}


def test_48_draft_respects_policy_count():
    candidates = [{"bucket": "保", "school_name": f"学校{i}", "major_group_code": str(i)} for i in range(60)]
    draft = build_48_volunteer_draft(candidates, _policy())
    assert len(draft["items"]) == 48


def test_48_draft_uses_major_group_as_volunteer_unit():
    candidates = [
        {
            "bucket": "稳",
            "school_name": "河南牧业经济学院",
            "major_group_code": "101",
            "major_group_name": "历史不限组",
            "selected_majors": ["会计学", "财务管理", "物流管理"],
        },
        {
            "bucket": "稳",
            "school_name": "河南牧业经济学院",
            "major_group_code": "102",
            "major_group_name": "历史政治组",
            "selected_majors": ["思想政治教育"],
        },
    ]
    draft = build_48_volunteer_draft(candidates, _policy())
    assert draft["items"][0]["volunteer_unit"] == "院校专业组"
    assert draft["items"][0]["major_group_code"] == "101"
    assert draft["items"][1]["major_group_code"] == "102"
    assert len(draft["items"]) == 2
