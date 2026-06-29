from app.engine.henan_recommendation import (
    build_48_volunteer_draft,
    build_henan_volunteer_table,
    check_henan_eligibility,
    classify_henan_bucket,
    classify_group_bucket,
    get_bucket_quota,
    sort_henan_bucket_candidates,
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


def test_single_subject_requirement_blocks_low_score():
    group = HenanProgramGroup(
        year=2026,
        track="历史类",
        school_code="x",
        school_name="测试大学",
        major_group_code="102",
        major_group_name="外语要求组",
        included_majors=["商务英语"],
        primary_subject_requirement="历史",
        elective_subject_requirement={},
        required_exam_language=None,
        accepted_exam_languages=["英语"],
        public_foreign_languages=["英语"],
        single_subject_requirements=[
            {"subject": "英语", "min_score": 120, "hard": True, "source_text": "英语不低于120分"}
        ],
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
            "exam_foreign_language": "英语",
            "subject_scores_detail": {"外语": 110, "数学": 90},
        },
        group=group,
    )
    assert ok is False
    assert warnings == []
    assert any("未达到最低 120 分要求" in x for x in blocked)


def test_bucket_classification():
    # 五档绝对位次差（与 classify_admission_tier 一致）
    assert classify_henan_bucket(student_rank=73822, historical_rank=70000, policy_mode="冲") == "冲"
    assert classify_henan_bucket(student_rank=73822, historical_rank=73822, policy_mode="稳") == "稳"
    assert classify_henan_bucket(student_rank=73822, historical_rank=80000, policy_mode="保") == "保"
    assert classify_henan_bucket(student_rank=73822, historical_rank=100000, policy_mode="垫") == "垫"


def test_group_bucket_requires_2026_plan_and_verified_group():
    # 资格层不通过 → ineligible → "不推荐"（位次差不改变资格）
    r1 = classify_group_bucket(
        student_rank=40000, adjusted_rank=50000, has_2025_history=True,
        has_2026_plan=False, has_verified_group=True, confidence=0.9)
    assert r1["bucket"] == "不推荐" and r1["eligibility_status"] == "ineligible"
    r2 = classify_group_bucket(
        student_rank=40000, adjusted_rank=50000, has_2025_history=True,
        has_2026_plan=True, has_verified_group=False, confidence=0.9)
    assert r2["bucket"] == "不推荐" and r2["eligibility_status"] == "ineligible"


def test_group_bucket_eligible_uses_admission_tier():
    # 资格通过后，纯按位次匹配判 admission_tier（五档 clamp）
    R = 50000
    # 冲：门槛比考生高（advantage<0），-10%R=-5000 ≤ advantage < -3%R=-1500
    assert classify_group_bucket(R, 46000, True, True, True, 0.9)["bucket"] == "冲"
    # 稳：基本匹配 -3%R ≤ advantage < +5%R
    assert classify_group_bucket(R, 50000, True, True, True, 0.9)["bucket"] == "稳"
    # 保：考生优于门槛 +5%R ≤ advantage < +15%R
    assert classify_group_bucket(R, 56000, True, True, True, 0.9)["bucket"] == "保"
    # 垫：考生远优于门槛 advantage ≥ +15%R
    assert classify_group_bucket(R, 70000, True, True, True, 0.9)["bucket"] == "垫"
    # 搏：门槛远高于考生 advantage < -10%R
    assert classify_group_bucket(R, 40000, True, True, True, 0.9)["bucket"] == "搏"


def test_group_bucket_returns_three_layer_status():
    # 三层状态完整性：eligible + admission_tier + recommended
    r = classify_group_bucket(50000, 50000, True, True, True, 0.9)
    assert r["eligibility_status"] == "eligible"
    assert r["admission_tier"] == "稳"
    assert r["recommendation_status"] == "recommended"


def test_bucket_quota_for_balanced_48_volunteers():
    # 均衡档贴合官方黄金比 3:4:3（冲10-15/稳~20/保13-18）
    quota = get_bucket_quota(48, "均衡", {"track": "物理类", "exam_foreign_language": "英语"})
    assert quota == {"冲": (12, 15), "稳": (18, 20), "保": (13, 15)}


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


def test_volunteer_table_prioritizes_enabled_local_and_public_preferences():
    candidates = [
        {
            "bucket": "稳",
            "school_name": "省外民办位次更近",
            "major_group_code": "101",
            "selected_majors": ["会计学"],
            "bucket_detail": {"rank_gap_ratio": -0.01},
            "is_henan_local": False,
            "school_ownership": "民办",
        },
        {
            "bucket": "稳",
            "school_name": "河南公办位次略远",
            "major_group_code": "102",
            "selected_majors": ["法学"],
            "bucket_detail": {"rank_gap_ratio": 0.02},
            "is_henan_local": True,
            "school_ownership": "公办",
        },
    ]

    table = build_henan_volunteer_table(
        {
            "track": "历史类",
            "exam_foreign_language": "英语",
            "strategy": "均衡",
            "sort_mode": "rank",
            "prefer_local": True,
            "prefer_public": True,
        },
        candidates,
        _policy(),
    )

    assert table["prefer_local"] is True
    assert table["prefer_public"] is True
    assert table["items"][0]["school_name"] == "河南公办位次略远"


def test_bucket_candidate_sort_uses_same_local_and_public_preferences():
    candidates = [
        {
            "school_name": "省外民办位次更近",
            "bucket_detail": {"rank_gap_ratio": -0.01},
            "is_henan_local": False,
            "school_ownership": "民办",
        },
        {
            "school_name": "河南公办位次略远",
            "bucket_detail": {"rank_gap_ratio": 0.02},
            "is_henan_local": True,
            "school_ownership": "公办",
        },
    ]

    ordered = sort_henan_bucket_candidates(
        candidates,
        {"sort_mode": "rank", "prefer_local": True, "prefer_public": True},
    )

    assert ordered[0]["school_name"] == "河南公办位次略远"


def test_bucket_candidate_sort_prioritizes_major_match_with_japanese_fit_before_probability_and_cost():
    candidates = [
        {
            "school_name": "高概率低费用但专业不匹配",
            "selected_majors": ["会计学", "财务管理"],
            "bucket_detail": {"rank_gap_ratio": -0.02},
            "admission_probability": 0.95,
            "four_year_total": 80000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "soft_warning", "note": "公共外语仅开英语"},
        },
        {
            "school_name": "日语专业匹配但概率较低",
            "selected_majors": ["日语", "翻译"],
            "bucket_detail": {"rank_gap_ratio": 0.02},
            "admission_probability": 0.70,
            "four_year_total": 120000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "none", "note": ""},
        },
    ]

    ordered = sort_henan_bucket_candidates(
        candidates,
        {
            "sort_mode": "rank",
            "prefer_local": True,
            "prefer_public": True,
            "exam_foreign_language": "日语",
            "interest_majors": ["日语"],
        },
    )

    assert ordered[0]["school_name"] == "日语专业匹配但概率较低"


def test_bucket_candidate_sort_local_priority_dominates_later_factors():
    candidates = [
        {
            "school_name": "省内公办但专业不匹配",
            "selected_majors": ["会计学"],
            "admission_probability": 0.80,
            "four_year_total": 80000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "none", "note": ""},
        },
        {
            "school_name": "省外民办但专业更匹配",
            "selected_majors": ["日语"],
            "admission_probability": 0.80,
            "four_year_total": 120000,
            "is_henan_local": False,
            "school_ownership": "民办",
            "language_restriction": {"level": "none", "note": ""},
        },
    ]

    ordered = sort_henan_bucket_candidates(
        candidates,
        {
            "prefer_local": True,
            "prefer_public": True,
            "exam_foreign_language": "日语",
            "interest_majors": ["日语"],
        },
    )

    assert ordered[0]["school_name"] == "省内公办但专业不匹配"


def test_bucket_candidate_sort_uses_lower_cost_as_final_tiebreaker():
    candidates = [
        {
            "school_name": "A高费用同质候选",
            "selected_majors": ["法学"],
            "admission_probability": 0.80,
            "four_year_total": 160000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "none", "note": ""},
        },
        {
            "school_name": "B低费用同质候选",
            "selected_majors": ["法学"],
            "admission_probability": 0.80,
            "four_year_total": 90000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "none", "note": ""},
        },
    ]

    ordered = sort_henan_bucket_candidates(
        candidates,
        {
            "prefer_local": True,
            "prefer_public": True,
            "exam_foreign_language": "英语",
            "interest_majors": ["法学"],
        },
    )

    assert ordered[0]["school_name"] == "B低费用同质候选"


def test_bucket_candidate_sort_can_prefer_same_language_major_when_enabled():
    candidates = [
        {
            "school_name": "日语专业候选",
            "selected_majors": ["日语", "翻译"],
            "admission_probability": 0.75,
            "four_year_total": 120000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "none", "note": ""},
        },
        {
            "school_name": "高概率非日语专业",
            "selected_majors": ["会计学"],
            "admission_probability": 0.92,
            "four_year_total": 80000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "none", "note": ""},
        },
    ]

    ordered = sort_henan_bucket_candidates(
        candidates,
        {
            "prefer_local": True,
            "prefer_public": True,
            "exam_foreign_language": "日语",
            "interest_majors": [],
            "prefer_same_language_major": True,
        },
    )

    assert ordered[0]["school_name"] == "日语专业候选"


def test_bucket_candidate_sort_keeps_explicit_interest_over_same_language_inference():
    candidates = [
        {
            "school_name": "法学候选",
            "selected_majors": ["法学"],
            "admission_probability": 0.80,
            "four_year_total": 100000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "none", "note": ""},
        },
        {
            "school_name": "日语专业候选",
            "selected_majors": ["日语"],
            "admission_probability": 0.85,
            "four_year_total": 90000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "none", "note": ""},
        },
    ]

    ordered = sort_henan_bucket_candidates(
        candidates,
        {
            "prefer_local": True,
            "prefer_public": True,
            "exam_foreign_language": "日语",
            "interest_majors": ["法学"],
            "prefer_same_language_major": True,
        },
    )

    assert ordered[0]["school_name"] == "法学候选"
