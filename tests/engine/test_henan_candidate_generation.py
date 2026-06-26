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
