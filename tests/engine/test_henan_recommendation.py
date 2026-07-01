from app.engine.henan_recommendation import (
    build_48_volunteer_draft,
    build_henan_volunteer_table,
    check_henan_eligibility,
    classify_admission_tier,
    classify_henan_bucket,
    classify_group_bucket,
    compute_tier_boundaries,
    get_bucket_quota,
    normalize_rank_to_target_year,
    sort_henan_bucket_candidates,
    _total_candidates,
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
    # 默认(稳保为主)：模拟人类"稳保为主、少量冲刺"——稳+保占主体，搏3-5/冲6-8
    quota = get_bucket_quota(48, "均衡", {"track": "物理类", "exam_foreign_language": "英语"})
    assert quota == {"搏": (3, 5), "冲": (6, 8), "稳": (20, 24), "保": (14, 18)}


def test_bucket_quota_auto_not_forced_conservative_for_history_japanese():
    # 自动策略=稳保为主：人类求稳选法，稳保占主体
    quota = get_bucket_quota(48, "自动", {"track": "历史类", "exam_foreign_language": "日语"})
    assert quota == {"搏": (3, 5), "冲": (6, 8), "稳": (20, 24), "保": (14, 18)}


def test_bucket_quota_for_aggressive_48_volunteers():
    # 积极：偏冲，加大冲刺缩减保底
    quota = get_bucket_quota(48, "积极", {"track": "物理类", "exam_foreign_language": "英语"})
    assert quota == {"搏": (8, 10), "冲": (12, 14), "稳": (14, 16), "保": (6, 8)}


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
            "bucket_detail": {"reference_rank": 73000},
            "is_henan_local": False,
            "school_ownership": "民办",
        },
        {
            "school_name": "河南公办位次略远",
            "bucket_detail": {"reference_rank": 75000},
            "is_henan_local": True,
            "school_ownership": "公办",
        },
    ]

    ordered = sort_henan_bucket_candidates(
        candidates,
        {"sort_mode": "rank", "prefer_local": True, "prefer_public": True},
    )

    # 同位次段（73000/75000 同在 36000-38000 段附近）内，省内公办偏好加分更高
    assert ordered[0]["school_name"] == "河南公办位次略远"


def test_bucket_candidate_sort_prioritizes_major_match_with_japanese_fit_before_probability_and_cost():
    candidates = [
        {
            "school_name": "高概率低费用但专业不匹配",
            "selected_majors": ["会计学", "财务管理"],
            "bucket_detail": {"reference_rank": 74000},
            "admission_probability": 0.95,
            "four_year_total": 80000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "soft_warning", "note": "公共外语仅开英语"},
        },
        {
            "school_name": "日语专业匹配但概率较低",
            "selected_majors": ["日语", "翻译"],
            "bucket_detail": {"reference_rank": 74000},
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
            "bucket_detail": {"reference_rank": 74000},
            "admission_probability": 0.80,
            "four_year_total": 80000,
            "is_henan_local": True,
            "school_ownership": "公办",
            "language_restriction": {"level": "none", "note": ""},
        },
        {
            "school_name": "省外民办但专业更匹配",
            "selected_majors": ["日语"],
            "bucket_detail": {"reference_rank": 74000},
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


# ── 年度归一化性质测试（验证算法正确性，非接口）──
# 这些测试验证百分位映射的数学性质，确保跨年归一化语义正确


def test_normalization_preserves_percentile():
    """性质1：归一化前后累计百分位应基本一致（核心定义）。"""
    n25, n26 = _total_candidates(2025), _total_candidates(2026)
    for r in [296, 5000, 23493, 73822]:
        norm = normalize_rank_to_target_year(r, 2025, 2026)
        p_hist = r / n25
        p_target = norm["normalized_rank"] / n26
        assert abs(p_hist - p_target) < 0.005, f"百分位漂移: {r}名 历史{p_hist:.3f}→目标{p_target:.3f}"


def test_normalization_known_value():
    """性质2：已知值验证——2025第5000名（前1.42%）应映射到约4484（前1.42%），不是3831。"""
    norm = normalize_rank_to_target_year(5000, 2025, 2026)
    assert norm["method"] == "percentile"
    n26 = _total_candidates(2026)
    expected = round(5000 / _total_candidates(2025) * n26)
    assert norm["normalized_rank"] == expected
    # 关键：不应是同分映射的3831（那会无依据提升排名到前1.21%）
    assert norm["normalized_rank"] != norm.get("same_score_reference_rank")


def test_normalization_same_population_identity():
    """性质3：同规模恒等——若两年考生规模相同，等效位次==历史位次。"""
    # 构造同规模场景：用 2025→2025（同年）验证恒等
    norm = normalize_rank_to_target_year(5000, 2025, 2025)
    assert norm["normalized_rank"] == 5000


def test_normalization_monotonic():
    """性质4：单调性——历史位次A<B，则等效位次A≤B。"""
    a = normalize_rank_to_target_year(10000, 2025, 2026)["normalized_rank"]
    b = normalize_rank_to_target_year(50000, 2025, 2026)["normalized_rank"]
    assert a <= b, f"单调性违反: {a} 应 ≤ {b}"


def test_normalization_boundary():
    """性质5：边界约束——1 ≤ 等效位次 ≤ 目标年考生规模。"""
    n26 = _total_candidates(2026)
    for r in [1, 100, n26, n26 + 1000]:
        norm = normalize_rank_to_target_year(r, 2025, 2026)
        assert 1 <= norm["normalized_rank"] <= n26, f"越界: {r}→{norm['normalized_rank']}"


def test_normalization_independent_of_raw_score():
    """性质6：不依赖同分裸分——百分位映射结果不应等于同分跨年映射。"""
    # 5000名：百分位映射≈4484，同分映射=3831，两者不同证明方法独立
    norm = normalize_rank_to_target_year(5000, 2025, 2026)
    assert norm["method"] == "percentile"
    assert norm["normalized_rank"] != norm["same_score_reference_rank"]


def test_normalization_2024_caliber_break_degrades_to_raw():
    """性质7：2024口径断裂（文科vs历史类）应降级为raw，不强行百分位。"""
    norm = normalize_rank_to_target_year(5000, 2024, 2026)
    assert norm["method"] == "raw"
    assert norm["normalized_rank"] == 5000  # 原始位次不被篡改
    assert norm["fallback_reason"] is not None  # 有降级原因，不静默


def test_normalization_outputs_metadata():
    """性质8：输出归一化元信息（method/confidence/raw/reference），不静默。"""
    norm = normalize_rank_to_target_year(73822, 2025, 2026)
    assert "method" in norm and "confidence" in norm
    assert "raw_rank" in norm and norm["raw_rank"] == 73822  # 原始值保留不被覆盖
    assert "same_score_reference_rank" in norm  # 同分映射作诊断保留


# ── 五档精确边界测试（半开区间，边界点唯一归属）──


def test_tier_boundaries_are_half_open_and_disjoint():
    """性质9：每个边界点只落入一个档位（半开区间 [lo, hi)，无重叠）。

    用 R=10000，动态获取实际边界（含 min_gap/max_gap clamp），在每个边界点±1验证唯一归属。
    """
    R = 10000
    # 动态获取实际边界（clamp 后的真实值）
    _, d = classify_admission_tier(R, R)
    bounds = d["bounds"]
    for name in ["reach_floor", "reach_sprint", "sprint_stable", "stable_safe", "safe_fallback"]:
        b = bounds[name]
        # 边界点 b：归入右档（[b, next)）
        tier_at_b, _ = classify_admission_tier(R, R + b)
        # b-1（略小）：归入左档
        tier_below, _ = classify_admission_tier(R, R + b - 1)
        assert tier_at_b != tier_below, f"边界{name}={b}归属重叠: b→{tier_at_b}, b-1→{tier_below}"


def test_tier_extreme_reach_below_gamble_floor():
    """性质10：advantage < 搏档下界(-20%R) → 超冲（资格可报，不归不推荐/需人工复核）。"""
    R = 10000
    # advantage = -2500 < -2000(搏下界) → 超冲
    tier, _ = classify_admission_tier(R, R - 2500)
    assert tier == "超冲", f"超20%R应判超冲，实际{tier}"


def test_tier_extreme_reach_keeps_eligible():
    """性质11：超冲候选资格仍为 eligible（可报）；推荐状态 conditional（不因超冲设not_recommended）。"""
    from app.engine.henan_recommendation import classify_group_bucket
    # advantage=-2500 < 搏下界 → 超冲，资格全通过
    verdict = classify_group_bucket(
        student_rank=10000, adjusted_rank=7500, has_2025_history=True,
        has_2026_plan=True, has_verified_group=True, confidence=0.9)
    assert verdict["bucket"] == "超冲"
    assert verdict["eligibility_status"] == "eligible"  # 资格可报
    # 推荐状态由适配因素决定，冷启动无适配问题设 conditional（不因超冲设 not_recommended）
    assert verdict["recommendation_status"] == "conditional"
    # 可见性控制：默认隐藏但可手动加入
    assert verdict["visibility_status"] == "hidden_by_default"
    assert verdict["hide_reason_code"] == "extreme_reach"
    assert verdict["can_manually_include"] is True


def test_tier_known_boundaries_600_score():
    """性质12：600分(R=4922)边界精确验证——你审查的关键案例。"""
    R = 4922
    # advantage=-849 → 搏（∈[-984,-492)）
    assert classify_admission_tier(R, R - 849)[0] == "搏"
    # advantage=-159 → 冲（∈[-492,-148)）
    assert classify_admission_tier(R, R - 159)[0] == "冲"
    # advantage=+223 → 稳（∈[-148,+246)）
    assert classify_admission_tier(R, R + 223)[0] == "稳"


def test_tier_normalization_used_for_classification():
    """性质13：判档用的位次 == bucket_detail里的归一化位次（解释链=决策链）。"""
    # 验证 classify_group_bucket 返回的 tier 是基于归一化位次判定的
    # build_henan_candidates 在归一化后才调 classify，两者一致
    from app.engine.henan_recommendation import build_henan_candidates
    profile = {"score": 480, "rank": 73822, "track": "历史类",
               "source_province": "河南", "primary_subject": "历史",
               "elective_subjects": ["政治", "地理"], "exam_foreign_language": "英语"}
    cands = build_henan_candidates(profile)
    for c in cands[:20]:
        bd = c.get("bucket_detail") or {}
        adj = bd.get("adjusted_min_rank")
        td = bd.get("tier_detail") or {}
        adv = td.get("advantage")
        if adj and adv is not None:
            # advantage 应 = adjusted_min_rank - student_rank（归一化位次参与判档）
            assert adv == adj - 73822, f"{c['school_name']}: advantage={adv} != {adj}-73822"


# ── 整数边界测试（ROUND_HALF_UP + 边界点±1 + 统一边界对象）──


def test_boundary_round_half_up():
    """性质14：边界用 ROUND_HALF_UP（0.5→1，2.5→3），非银行家 round。"""
    from app.engine.henan_recommendation import _round_half_up
    assert _round_half_up(0.5) == 1
    assert _round_half_up(1.5) == 2
    assert _round_half_up(2.5) == 3   # 银行家 round 会得 2，ROUND_HALF_UP 得 3
    assert _round_half_up(-0.5) == -1
    assert _round_half_up(147.66) == 148


def test_boundaries_are_integers():
    """性质15：compute_tier_boundaries 返回的边界全是整数（无浮点残留）。"""
    from app.engine.henan_recommendation import compute_tier_boundaries
    for R in [296, 4922, 23493, 57184, 73822, 95565]:
        b = compute_tier_boundaries(R)
        for k, v in b.items():
            if k != "R":
                assert isinstance(v, int), f"R={R} 边界{k}={v} 不是整数"


def test_boundary_points_unique_attribution():
    """性质16：边界点±1唯一归属（半开区间，整数边界无浮点歧义）。

    在每个边界点 b：b 归右档，b-1 归左档，两者不同。
    """
    from app.engine.henan_recommendation import compute_tier_boundaries, classify_admission_tier
    R = 4922
    bounds = compute_tier_boundaries(R)
    for name in ["reach_floor", "reach_sprint", "sprint_stable", "stable_safe", "safe_fallback"]:
        b = bounds[name]
        tier_at_b, _ = classify_admission_tier(R, R + b)
        tier_below, _ = classify_admission_tier(R, R + b - 1)
        assert tier_at_b != tier_below, f"边界{name}={b}归属重叠: b→{tier_at_b}, b-1→{tier_below}"


def test_boundary_shared_object_no_recompute():
    """性质17：判档/API/测试复用同一个整数边界对象（compute_tier_boundaries）。

    classify_admission_tier 内部调 compute_tier_boundaries，返回的 tier_detail.bounds
    与直接调 compute_tier_boundaries 结果一致（同一对象，不重新计算）。
    """
    from app.engine.henan_recommendation import compute_tier_boundaries, classify_admission_tier
    R = 73822
    direct = compute_tier_boundaries(R)
    _, detail = classify_admission_tier(R, R + 5000)
    assert detail["bounds"] == direct, "判档用的边界与 compute_tier_boundaries 不一致"


def test_no_float_boundary_ambiguity():
    """性质18：整数边界消除浮点歧义（之前东北师大1746 vs 1746.1的问题）。

    advantage 恰好等于整数边界时，判定确定（无浮点比较歧义）。
    """
    from app.engine.henan_recommendation import classify_admission_tier
    R = 4922
    b = compute_tier_boundaries(R)
    # advantage 恰好 = safe_fallback（保垫边界），应确定判垫（< False）
    tier, _ = classify_admission_tier(R, R + b["safe_fallback"])
    assert tier == "垫", f"advantage=保垫边界应判垫（整数<不成立），实际{tier}"
    # advantage = safe_fallback - 1 应判保
    tier2, _ = classify_admission_tier(R, R + b["safe_fallback"] - 1)
    assert tier2 == "保", f"advantage=保垫边界-1应判保，实际{tier2}"
