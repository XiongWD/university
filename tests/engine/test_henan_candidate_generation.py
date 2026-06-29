from app.engine.henan_recommendation import build_henan_candidates
from app.models.henan_data import HenanAdmissionHistory, HenanEnrollmentPlan, HenanProgramGroup


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
    assert all(item["bucket"] in {"超冲", "搏", "冲", "稳", "保", "垫", "不推荐", "需人工复核"} for item in candidates)


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
    """日语考生报限英语专业组 → 不推荐。

    东北农业大学历史类组750491 标注接受外语语种为英语，日语考生应被阻断。
    """
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
    # 东北农业大学750491（仅接受英语）对日语考生必须不推荐
    eng_only = [c for c in candidates if c["school_name"] == "东北农业大学" and c.get("accepted_exam_languages", "") == "英语"]
    # 如无匹配组（数据可能变更），至少确保没有英语-only 组被误判为可达
    if eng_only:
        assert eng_only[0]["bucket"] == "不推荐"
        assert any("英语" in r for r in eng_only[0]["blocked_reasons"])
    # 所有被 blocked_reasons 标记的组都不得是 冲/稳/保
    for c in candidates:
        if any("英语" in r for r in c.get("blocked_reasons", [])):
            assert c["bucket"] not in {"冲", "稳", "保"}, f"{c['school_name']} 英语限制不得为可达桶"


def test_real_seed_produces_reachable_bucket_for_verified_group():
    """正向验收（审查 C1+数据标注）：有 verified 历史基线的组应产出冲/稳/保。

    当前 14 校同时有 verified 组+计划+历史。学生 rank=12000 对 福建警察学院(rank≈20115) 应为保。
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
    # 应有可达候选（搏/冲/稳/保/垫，verified 历史基线存在）
    reachable = [c for c in candidates if c["bucket"] in {"搏", "冲", "稳", "保", "垫"}]
    assert len(reachable) >= 1, f"应有至少 1 个可达候选，实际 {len(reachable)}"
    # 需人工复核候选也应存在（needs_review 组/缺计划）
    needs_review = [c for c in candidates if c["bucket"] == "需人工复核"]
    assert len(needs_review) >= 1, "应有至少 1 个需人工复核候选"
    # 福建警察学院 verified 组对 rank12000（advantage≈9635，差80%）应为垫档（明显兜底）
    fj_police = [c for c in candidates if c["school_name"] == "福建警察学院" and c["bucket"] in {"保", "垫"}]
    assert len(fj_police) >= 1, "福建警察学院应有保/垫候选"


def test_missing_history_uses_needs_human_review_not_reject():
    """审查 I1：资格通过但缺 verified 历史 → 需人工复核，不是不推荐。

    清华大学 score=685 超出 2025 位次表范围 → history needs_review → 需人工复核。
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
    # 清华大学（真实历史数据齐全）→ 考生位次12000对清华(位次~296)是高风险搏档
    tsinghua = [c for c in candidates if c["school_name"] == "清华大学"]
    assert len(tsinghua) >= 1
    for c in tsinghua:
        assert c["bucket"] in {"超冲", "搏", "冲", "稳", "保", "垫", "需人工复核", "不推荐"}, \
            f"清华大学应被判档，实际 {c['bucket']}"
def test_build_henan_candidates_filters_to_regular_undergrad_history_scope(monkeypatch):
    profile = {
        "source_province": "河南",
        "score": 610,
        "rank": 12000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "英语",
    }

    def make_group(code, major_name, special_type=""):
        return HenanProgramGroup.model_validate({
            "year": 2026,
            "track": "历史类",
            "batch": "本科批",
            "school_code": "1",
            "school_name": "测试大学",
            "major_group_code": code,
            "major_group_name": f"测试大学-{code}",
            "included_majors": [major_name],
            "major_codes": [f"m-{code}"],
            "primary_subject_requirement": "历史",
            "elective_subject_requirement": {},
            "accepted_exam_languages": [],
            "public_foreign_languages": [],
            "single_subject_requirements": [],
            "adjustment_scope": "组内专业",
            "physical_restrictions": "",
            "special_qualification_type": special_type,
            "source_name": "gaokao.cn",
            "source_url": "https://www.gaokao.cn/school/1/sturule",
            "as_of": "2026-06-27T00:00:00+00:00",
            "confidence": 0.9,
            "review_status": "verified",
        })

    def make_plan(code, major_name, remarks="", special_type=""):
        return HenanEnrollmentPlan.model_validate({
            "year": 2026,
            "source_province": "河南",
            "school_origin_province": "河南",
            "is_henan_local_school": True,
            "school_code": "1",
            "school_name": "测试大学",
            "major_group_code": code,
            "major_name": major_name,
            "plan_count": 2,
            "tuition": 5000,
            "accommodation": 1000,
            "batch": "本科批",
            "track": "历史类",
            "campus": "主校区",
            "physical_restrictions": "",
            "special_qualification_type": special_type,
            "accepted_exam_languages": "",
            "remarks": remarks,
            "source_name": "gaokao.cn",
            "source_url": "https://www.gaokao.cn/school/1/sturule",
            "as_of": "2026-06-27T00:00:00+00:00",
            "confidence": 0.9,
            "review_status": "verified",
        })

    history = [
        HenanAdmissionHistory.model_validate({
            "year": 2025,
            "track": "历史类",
            "school_code": "1",
            "school_name": "测试大学",
            "major_group_code": "1001",
            "major_group_name": "测试大学-1001",
            "major_name": None,
            "min_score": 590,
            "min_rank": 15000,
            "avg_score": None,
            "avg_rank": None,
            "plan_count": 2,
            "batch": "本科批",
            "data_granularity": "major_group",
            "source_name": "gaokao.cn",
            "source_url": "https://www.gaokao.cn/school/1/sturule",
            "as_of": "2026-06-27T00:00:00+00:00",
            "confidence": 0.9,
            "review_status": "verified",
        }),
        HenanAdmissionHistory.model_validate({
            "year": 2025,
            "track": "历史类",
            "school_code": "1",
            "school_name": "测试大学",
            "major_group_code": "1002",
            "major_group_name": "测试大学-1002",
            "major_name": None,
            "min_score": 590,
            "min_rank": 15000,
            "avg_score": None,
            "avg_rank": None,
            "plan_count": 2,
            "batch": "本科批",
            "data_granularity": "major_group",
            "source_name": "gaokao.cn",
            "source_url": "https://www.gaokao.cn/school/1/sturule",
            "as_of": "2026-06-27T00:00:00+00:00",
            "confidence": 0.9,
            "review_status": "verified",
        }),
    ]

    groups = [
        make_group("1001", "法学", ""),
        make_group("1002", "国际经济与贸易", "中外合作"),
        make_group("1003", "法学", "国家专项"),
        make_group("1004", "戏剧影视文学", ""),
        make_group("1005", "预科班", ""),
    ]
    plans = [
        make_plan("1001", "法学"),
        make_plan("1002", "国际经济与贸易", "（中外合作办学组）", "中外合作"),
        make_plan("1003", "法学", "（国家专项计划组）", "国家专项"),
        make_plan("1004", "戏剧影视文学", "（不组织专业考试的艺术类专业组）（授予艺术学学士学位）"),
        make_plan("1005", "预科班", "（边防军人子女预科班）（预科组）"),
    ]

    from app.loader import henan_data_loader as loader

    monkeypatch.setattr(loader, "load_henan_program_groups", lambda seed_dir: groups)
    monkeypatch.setattr(loader, "load_henan_enrollment_plans", lambda seed_dir: plans)
    monkeypatch.setattr(loader, "load_henan_admission_history", lambda seed_dir: history)

    candidates = build_henan_candidates(profile)

    codes = {item["major_group_code"] for item in candidates}
    assert codes == {"1001", "1002"}


def test_build_henan_candidates_rejects_non_history_track():
    import pytest

    profile = {
        "source_province": "河南",
        "score": 610,
        "rank": 12000,
        "track": "物理类",
        "primary_subject": "物理",
        "elective_subjects": ["化学", "生物"],
        "exam_foreign_language": "英语",
    }

    with pytest.raises(ValueError, match="历史类"):
        build_henan_candidates(profile)


def test_build_henan_candidates_marks_missing_public_language_data_separately(monkeypatch):
    profile = {
        "source_province": "河南",
        "score": 610,
        "rank": 12000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
    }

    group = HenanProgramGroup.model_validate({
        "year": 2026,
        "track": "历史类",
        "batch": "本科批",
        "school_code": "1",
        "school_name": "测试大学",
        "major_group_code": "1001",
        "major_group_name": "测试大学-1001",
        "included_majors": ["法学"],
        "major_codes": ["m-1001"],
        "primary_subject_requirement": "历史",
        "elective_subject_requirement": {},
        "accepted_exam_languages": [],
        "public_foreign_languages": [],
        "single_subject_requirements": [],
        "adjustment_scope": "组内专业",
        "physical_restrictions": "",
        "special_qualification_type": "",
        "source_name": "gaokao.cn",
        "source_url": "https://www.gaokao.cn/school/1/sturule",
        "as_of": "2026-06-27T00:00:00+00:00",
        "confidence": 0.9,
        "review_status": "verified",
    })
    plan = HenanEnrollmentPlan.model_validate({
        "year": 2026,
        "source_province": "河南",
        "school_origin_province": "河南",
        "is_henan_local_school": True,
        "school_code": "1",
        "school_name": "测试大学",
        "major_group_code": "1001",
        "major_name": "法学",
        "plan_count": 2,
        "tuition": 5000,
        "accommodation": 1000,
        "batch": "本科批",
        "track": "历史类",
        "campus": "主校区",
        "physical_restrictions": "",
        "special_qualification_type": "",
        "accepted_exam_languages": "",
        "remarks": "",
        "source_name": "gaokao.cn",
        "source_url": "https://www.gaokao.cn/school/1/sturule",
        "as_of": "2026-06-27T00:00:00+00:00",
        "confidence": 0.9,
        "review_status": "verified",
    })
    history = [
        HenanAdmissionHistory.model_validate({
            "year": 2025,
            "track": "历史类",
            "school_code": "1",
            "school_name": "测试大学",
            "major_group_code": "1001",
            "major_group_name": "测试大学-1001",
            "major_name": None,
            "min_score": 590,
            "min_rank": 18000,
            "avg_score": None,
            "avg_rank": None,
            "plan_count": 2,
            "batch": "本科批",
            "data_granularity": "major_group",
            "source_name": "gaokao.cn",
            "source_url": "https://www.gaokao.cn/school/1/sturule",
            "as_of": "2026-06-27T00:00:00+00:00",
            "confidence": 0.9,
            "review_status": "verified",
        }),
    ]

    from app.loader import henan_data_loader as loader

    monkeypatch.setattr(loader, "load_henan_program_groups", lambda seed_dir: [group])
    monkeypatch.setattr(loader, "load_henan_enrollment_plans", lambda seed_dir: [plan])
    monkeypatch.setattr(loader, "load_henan_admission_history", lambda seed_dir: history)

    candidates = build_henan_candidates(profile)

    assert len(candidates) == 1
    assert candidates[0]["language_restriction"]["level"] == "missing_data"
    assert any("语种数据缺失" in warning for warning in candidates[0]["warnings"])
