"""资格链专业级下沉测试（P0 语种上卷事故修复）。

覆盖：
  - henan_language_rule：normalize_language_rule / aggregate_group_language_rule
  - build_henan_candidates：哈尔滨石油学院回归（部分专业可报，不再整组误杀）
  - 性质测试：顺序无关、混合不上卷、全一致才上卷、空≠不限、无证据不硬阻
"""
from __future__ import annotations

from app.loader.henan_language_rule import (
    aggregate_group_language_rule,
    normalize_language_rule,
)
from app.models.henan_data import (
    HenanAdmissionHistory,
    HenanEnrollmentPlan,
    HenanProgramGroup,
)


# ── normalize_language_rule 单元测试 ──────────────────────────────────────

def test_normalize_language_rule_restricted_english():
    """明确"只招英语语种"→ restricted 英语。"""
    rule = normalize_language_rule("（只招英语语种的考生）")
    assert rule == {"rule_status": "restricted", "accepted": ["英语"], "required": "英语"}


def test_normalize_language_rule_unrestricted():
    """明确"语种不限/零起点"→ unrestricted（仅当无硬限制词）。"""
    for text in ["（零起点，语种不限）", "语种不限", "不限外语语种"]:
        rule = normalize_language_rule(text)
        assert rule == {"rule_status": "unrestricted", "accepted": [], "required": None}, text


def test_unknown_language_rule_is_not_unrestricted():
    """空 remark / 无匹配 → unknown，绝不当 unrestricted（保守降级）。"""
    for text in ["", "   ", "（英才班）", "（经管学院）"]:
        rule = normalize_language_rule(text)
        assert rule["rule_status"] == "unknown", f"空/无匹配应判 unknown，实际 {rule}（text={text!r}）"
        assert rule["accepted"] == []
        assert rule["required"] is None


def test_restricted_beats_unrestricted_when_both_present():
    """同时含"零起点"和"只招英语语种"→ restricted（硬限制优先于不限）。
    如吉林大学日语"零起点培养；只招英语语种的考生"应判 restricted 英语，而非不限。
    """
    rule = normalize_language_rule("（零起点培养；只招英语语种的考生）")
    assert rule["rule_status"] == "restricted"
    assert rule["accepted"] == ["英语"]


# ── aggregate_group_language_rule 单元测试 ─────────────────────────────────

def test_common_rule_promoted_only_when_all_majors_match():
    """组内全专业限制一致（全限英语）→ 上卷为组级。"""
    rules = [
        {"rule_status": "restricted", "accepted": ["英语"], "required": "英语"},
        {"rule_status": "restricted", "accepted": ["英语"], "required": "英语"},
    ]
    agg = aggregate_group_language_rule(rules)
    assert agg["accepted_exam_languages"] == ["英语"]
    assert agg["required_exam_language"] == "英语"
    assert agg["has_mixed_language_rules"] is False


def test_mixed_major_language_rules_not_promoted_to_group():
    """组内混合（一个限英语、一个不限）→ 组级置空 + has_mixed_language_rules=True。"""
    rules = [
        {"rule_status": "restricted", "accepted": ["英语"], "required": "英语"},
        {"rule_status": "unrestricted", "accepted": [], "required": None},
    ]
    agg = aggregate_group_language_rule(rules)
    assert agg["accepted_exam_languages"] == []
    assert agg["required_exam_language"] is None
    assert agg["has_mixed_language_rules"] is True


def test_mixed_restricted_and_unknown_not_promoted():
    """组内限英语 + 未知（空 remark）→ 组级置空（不能假设未知专业也限英语）。"""
    rules = [
        {"rule_status": "restricted", "accepted": ["英语"], "required": "英语"},
        {"rule_status": "unknown", "accepted": [], "required": None},
    ]
    agg = aggregate_group_language_rule(rules)
    assert agg["accepted_exam_languages"] == []
    assert agg["has_mixed_language_rules"] is True


def test_group_language_result_is_order_independent():
    """聚合顺序无关（防 setdefault 首行污染）。
    [英语专业, 财务专业] 与 [财务专业, 英语专业] 应得到相同的混合结果。
    """
    eng = {"rule_status": "restricted", "accepted": ["英语"], "required": "英语"}
    fin = {"rule_status": "unknown", "accepted": [], "required": None}
    a = aggregate_group_language_rule([eng, fin])
    b = aggregate_group_language_rule([fin, eng])
    assert a == b, "混合规则聚合应与顺序无关"
    assert a["has_mixed_language_rules"] is True


def test_all_unknown_not_promoted_to_group_restriction():
    """组内全 unknown（空 remark）→ 组级不生成限制（不能假设全部限制）。"""
    rules = [
        {"rule_status": "unknown", "accepted": [], "required": None},
        {"rule_status": "unknown", "accepted": [], "required": None},
    ]
    agg = aggregate_group_language_rule(rules)
    assert agg["accepted_exam_languages"] == []
    assert agg["has_mixed_language_rules"] is False  # 全一致（都是unknown）→ 不算混合


# ── build_henan_candidates 哈尔滨石油学院回归（monkeypatch 端到端）──────────

def _make_group(code, majors, accepted=None):
    return HenanProgramGroup.model_validate({
        "year": 2026, "track": "历史类", "batch": "本科批",
        "school_code": "2535", "school_name": "哈尔滨石油学院",
        "major_group_code": code, "major_group_name": f"哈尔滨石油学院-{code}",
        "included_majors": majors, "major_codes": [f"m-{i}" for i in range(len(majors))],
        "primary_subject_requirement": "历史", "elective_subject_requirement": {},
        "accepted_exam_languages": accepted or [],
        "public_foreign_languages": [],
        "single_subject_requirements": [], "adjustment_scope": "组内专业",
        "physical_restrictions": "", "special_qualification_type": "",
        "source_name": "gaokao.cn", "source_url": "https://www.gaokao.cn/school/2535/sturule",
        "as_of": "2026-06-27T00:00:00+00:00", "confidence": 0.9, "review_status": "verified",
    })


def _make_plan(code, major_name, accepted="", remarks=""):
    return HenanEnrollmentPlan.model_validate({
        "year": 2026, "source_province": "河南", "school_origin_province": "黑龙江",
        "is_henan_local_school": False, "school_code": "2535",
        "school_name": "哈尔滨石油学院", "major_group_code": code, "major_name": major_name,
        "plan_count": 5, "tuition": 25000, "accommodation": None,
        "batch": "本科批", "track": "历史类", "campus": "",
        "physical_restrictions": "", "special_qualification_type": "",
        "accepted_exam_languages": accepted, "remarks": remarks,
        "source_name": "gaokao.cn", "source_url": "https://www.gaokao.cn/school/2535/sturule",
        "as_of": "2026-06-27T00:00:00+00:00", "confidence": 0.9, "review_status": "verified",
    })


def _japanese_profile(rank=12000):
    return {
        "source_province": "河南", "score": 480, "rank": rank,
        "track": "历史类", "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"], "exam_foreign_language": "日语",
    }


def test_harbin_petroleum_partial_eligible_not_blocked(monkeypatch):
    """哈尔滨石油学院：日语考生应 partially_eligible（俄语可报、英语不可报），不再整组误杀。"""
    from app.engine.henan_recommendation import build_henan_candidates
    from app.loader import henan_data_loader as loader

    majors = ["财务管理", "英语", "俄语", "供应链管理", "跨境电子商务"]
    # 组级语种置空（has_mixed_language_rules=True），专业级各自带语种
    group = _make_group("759266", majors, accepted=[])
    plans = [
        _make_plan("759266", "财务管理", "", "（英才班）"),
        _make_plan("759266", "英语", "英语", "（只招英语语种的考生）"),
        _make_plan("759266", "俄语", "", "（英才班）（零起点，语种不限）"),
        _make_plan("759266", "供应链管理", "", ""),
        _make_plan("759266", "跨境电子商务", "", ""),
    ]
    history = [
        HenanAdmissionHistory.model_validate({
            "year": 2025, "track": "历史类", "school_code": "2535",
            "school_name": "哈尔滨石油学院", "major_group_code": "759266",
            "major_group_name": "哈尔滨石油学院-759266", "major_name": None,
            "min_score": 470, "min_rank": 55000, "avg_score": None, "avg_rank": None,
            "plan_count": 60, "batch": "本科批", "data_granularity": "major_group",
            "source_name": "heao", "source_url": "https://www.gaokao.cn/school/2535/sturule",
            "as_of": "2026-06-27T00:00:00+00:00", "confidence": 0.9, "review_status": "verified",
        }),
    ]

    monkeypatch.setattr(loader, "load_henan_program_groups", lambda seed_dir: [group])
    monkeypatch.setattr(loader, "load_henan_enrollment_plans", lambda seed_dir: plans)
    monkeypatch.setattr(loader, "load_henan_admission_history", lambda seed_dir: history)

    candidates = build_henan_candidates(_japanese_profile())
    assert len(candidates) == 1
    c = candidates[0]
    # 不再被误杀为"不推荐"
    assert c["group_eligibility_status"] == "partially_eligible"
    assert c["bucket"] in {"搏", "冲", "稳", "保", "垫"}, f"应进入冲稳保，实际 {c['bucket']}"
    # 俄语明确可报（零起点不限），英语明确不可报
    assert "俄语" in c["eligible_majors"]
    assert any(m["major"] == "英语" for m in c["ineligible_majors"])
    assert any("英语" in r for m in c["ineligible_majors"] for r in m["reasons"])


def test_one_restricted_major_does_not_block_whole_group(monkeypatch):
    """组内存在一个限英语专业，不应阻断整组（其他专业仍可报）。"""
    from app.engine.henan_recommendation import build_henan_candidates
    from app.loader import henan_data_loader as loader

    majors = ["英语", "财务管理", "国际经济与贸易"]
    group = _make_group("G1", majors, accepted=[])
    plans = [
        _make_plan("G1", "英语", "英语", "（只招英语语种的考生）"),
        _make_plan("G1", "财务管理", "", ""),
        _make_plan("G1", "国际经济与贸易", "", ""),
    ]
    history = [
        HenanAdmissionHistory.model_validate({
            "year": 2025, "track": "历史类", "school_code": "2535",
            "school_name": "哈尔滨石油学院", "major_group_code": "G1",
            "major_group_name": "哈尔滨石油学院-G1", "major_name": None,
            "min_score": 470, "min_rank": 55000, "avg_score": None, "avg_rank": None,
            "plan_count": 30, "batch": "本科批", "data_granularity": "major_group",
            "source_name": "heao", "source_url": "https://www.gaokao.cn/school/2535/sturule",
            "as_of": "2026-06-27T00:00:00+00:00", "confidence": 0.9, "review_status": "verified",
        }),
    ]
    monkeypatch.setattr(loader, "load_henan_program_groups", lambda seed_dir: [group])
    monkeypatch.setattr(loader, "load_henan_enrollment_plans", lambda seed_dir: plans)
    monkeypatch.setattr(loader, "load_henan_admission_history", lambda seed_dir: history)

    candidates = build_henan_candidates(_japanese_profile())
    c = candidates[0]
    assert c["group_eligibility_status"] in {"partially_eligible", "uncertain"}
    # 财务管理、国贸不限语种，应可报（remark 空判 uncertain，但有英语不可报）
    assert any(m["major"] == "英语" for m in c["ineligible_majors"])


def test_english_candidate_unaffected_by_language_restriction(monkeypatch):
    """英语考生不受语种限制影响（含限英语专业也可报）。"""
    from app.engine.henan_recommendation import build_henan_candidates
    from app.loader import henan_data_loader as loader

    majors = ["英语", "俄语"]
    group = _make_group("G2", majors, accepted=[])
    plans = [
        _make_plan("G2", "英语", "英语", "（只招英语语种的考生）"),
        _make_plan("G2", "俄语", "", "（零起点，语种不限）"),
    ]
    history = [
        HenanAdmissionHistory.model_validate({
            "year": 2025, "track": "历史类", "school_code": "2535",
            "school_name": "哈尔滨石油学院", "major_group_code": "G2",
            "major_group_name": "哈尔滨石油学院-G2", "major_name": None,
            "min_score": 470, "min_rank": 55000, "avg_score": None, "avg_rank": None,
            "plan_count": 20, "batch": "本科批", "data_granularity": "major_group",
            "source_name": "heao", "source_url": "https://www.gaokao.cn/school/2535/sturule",
            "as_of": "2026-06-27T00:00:00+00:00", "confidence": 0.9, "review_status": "verified",
        }),
    ]
    monkeypatch.setattr(loader, "load_henan_program_groups", lambda seed_dir: [group])
    monkeypatch.setattr(loader, "load_henan_enrollment_plans", lambda seed_dir: plans)
    monkeypatch.setattr(loader, "load_henan_admission_history", lambda seed_dir: history)

    profile = _japanese_profile()
    profile["exam_foreign_language"] = "英语"
    candidates = build_henan_candidates(profile)
    c = candidates[0]
    # 英语考生：全部可报，无 ineligible_majors
    assert c["group_eligibility_status"] == "eligible"
    assert len(c["ineligible_majors"]) == 0


def test_group_unverified_language_rule_cannot_hard_block(monkeypatch):
    """无证据（全 unknown）的语种规则不能硬阻，应降级 uncertain/eligible 而非 ineligible。"""
    from app.engine.henan_recommendation import build_henan_candidates
    from app.loader import henan_data_loader as loader

    majors = ["财务管理", "供应链管理"]
    group = _make_group("G3", majors, accepted=[])
    plans = [
        _make_plan("G3", "财务管理", "", ""),  # 全空 remark = unknown
        _make_plan("G3", "供应链管理", "", ""),
    ]
    history = [
        HenanAdmissionHistory.model_validate({
            "year": 2025, "track": "历史类", "school_code": "2535",
            "school_name": "哈尔滨石油学院", "major_group_code": "G3",
            "major_group_name": "哈尔滨石油学院-G3", "major_name": None,
            "min_score": 470, "min_rank": 55000, "avg_score": None, "avg_rank": None,
            "plan_count": 20, "batch": "本科批", "data_granularity": "major_group",
            "source_name": "heao", "source_url": "https://www.gaokao.cn/school/2535/sturule",
            "as_of": "2026-06-27T00:00:00+00:00", "confidence": 0.9, "review_status": "verified",
        }),
    ]
    monkeypatch.setattr(loader, "load_henan_program_groups", lambda seed_dir: [group])
    monkeypatch.setattr(loader, "load_henan_enrollment_plans", lambda seed_dir: plans)
    monkeypatch.setattr(loader, "load_henan_admission_history", lambda seed_dir: history)

    candidates = build_henan_candidates(_japanese_profile())
    c = candidates[0]
    # 全 unknown：不能硬阻为 ineligible
    assert c["group_eligibility_status"] != "ineligible"
