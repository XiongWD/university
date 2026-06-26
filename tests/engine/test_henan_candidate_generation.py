from app.engine.henan_recommendation import build_henan_candidates


def test_build_henan_candidates_returns_groups_when_verified_data_exists():
    profile = {
        "source_province": "河南",
        "score": 610,
        "rank": 12000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
        "strategy": "自动",
    }

    candidates = build_henan_candidates(profile)

    assert isinstance(candidates, list)
    # 不再是无条件空列表
    assert len(candidates) > 0
    assert all(item["volunteer_unit"] == "院校专业组" for item in candidates)
    assert all("major_group_code" in item for item in candidates)
    assert all(item["bucket"] in {"冲", "稳", "保", "不推荐", "需人工复核"} for item in candidates)


def test_build_henan_candidates_excludes_zero_plan_from_reachable_buckets():
    profile = {
        "source_province": "河南",
        "score": 610,
        "rank": 12000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
    }
    candidates = build_henan_candidates(profile)
    # plan_count=0 的候选不得进入冲/稳/保
    assert all(
        not (item.get("plan_count", 1) == 0 and item["bucket"] in {"冲", "稳", "保"})
        for item in candidates
    )


def test_build_henan_candidates_marks_review_groups_as_needs_human_review():
    """needs_review 专业组即使位次优也只能是 需人工复核/不推荐，不得稳/保。"""
    profile = {
        "source_province": "河南",
        "score": 700,
        "rank": 1000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
    }
    candidates = build_henan_candidates(profile)
    for item in candidates:
        if item.get("review_status") == "needs_review":
            assert item["bucket"] not in {"稳", "保"}, (
                f"{item['school_name']} needs_review 不得稳/保: {item['bucket']}"
            )


def test_build_henan_candidates_japanese_blocked_by_english_only_group():
    """日语考生报限英语专业组 → 不推荐。"""
    profile = {
        "source_province": "河南",
        "score": 610,
        "rank": 12000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
    }
    candidates = build_henan_candidates(profile)
    # 限英语的"综合大学示范 英语专业组"对日语考生必须不推荐
    english_only = [c for c in candidates if c["school_name"] == "综合大学示范"]
    assert len(english_only) == 1
    assert english_only[0]["bucket"] == "不推荐"
    assert any("英语" in r for r in english_only[0]["blocked_reasons"])


def test_real_seed_produces_reachable_bucket_for_verified_group():
    """正向验收（审查 C1）：真实 seed 下，verified 2026 组对合理位次考生须产出稳/保/冲。

    郑大历史类人文组101 有 verified 2025 历史基线(rank13000)，考生 rank=12000(优于)→稳。
    """
    profile = {
        "source_province": "河南",
        "score": 600,
        "rank": 12000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "英语",
    }
    candidates = build_henan_candidates(profile)
    reachable = [c for c in candidates if c["bucket"] in {"冲", "稳", "保"}]
    assert len(reachable) >= 1, "真实 seed 应至少为合理位次考生产出 1 个冲/稳/保候选"
    zzu = next(c for c in candidates if c["school_name"] == "郑州大学" and c["major_group_code"] == "101")
    assert zzu["bucket"] in {"冲", "稳", "保"}, f"郑大历史组对 rank12000 应可达，实际 {zzu['bucket']}"


def test_missing_history_uses_needs_human_review_not_reject():
    """审查 I1：资格通过但缺 verified 历史 → 需人工复核，不是不推荐。"""
    profile = {
        "source_province": "河南",
        "score": 600,
        "rank": 12000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "英语",
    }
    candidates = build_henan_candidates(profile)
    # 河南牧业经济学院组101 needs_review（无 verified 历史基线匹配）→ 需人工复核
    myxy = next(c for c in candidates if c["school_name"] == "河南牧业经济学院")
    assert myxy["bucket"] == "需人工复核", f"缺历史的组应是需人工复核，实际 {myxy['bucket']}"
