"""冲稳保口径统一 + 需复核原因细分测试（问题1/问题2 修复）。

问题2：判档用 advantage=参考−考生（负=更难），但旧展示口径 rank_gap_ratio=考生−参考（正=更难），
       方向相反、分母不同。修复后统一为 advantage_ratio=advantage/考生位次。
问题1：需人工复核≠不符合，应告知用户具体缺什么数据（缺2025位次/2024旧口径/计划未核验等）。
"""
from __future__ import annotations

from app.models.henan_data import (
    HenanAdmissionHistory,
    HenanEnrollmentPlan,
    HenanProgramGroup,
)


def _profile(score=480, rank=73822, lang="英语"):
    return {
        "source_province": "河南", "score": score, "rank": rank,
        "track": "历史类", "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"], "exam_foreign_language": lang,
    }


def _make_group(code, major="测试专业", accepted=None, school_code="999"):
    return HenanProgramGroup.model_validate({
        "year": 2026, "track": "历史类", "batch": "本科批",
        "school_code": school_code, "school_name": f"测试大学{code}",
        "major_group_code": code, "major_group_name": f"测试大学{code}-{code}",
        "included_majors": [major], "major_codes": [f"m-{code}"],
        "primary_subject_requirement": "历史", "elective_subject_requirement": {},
        "accepted_exam_languages": accepted or [],
        "public_foreign_languages": [],
        "single_subject_requirements": [], "adjustment_scope": "组内专业",
        "physical_restrictions": "", "special_qualification_type": "",
        "source_name": "test", "source_url": "https://example.com",
        "as_of": "2026-06-27T00:00:00+00:00", "confidence": 0.9, "review_status": "verified",
    })


def _make_plan(code, major="测试专业", remarks="", school_code="999"):
    return HenanEnrollmentPlan.model_validate({
        "year": 2026, "source_province": "河南", "school_origin_province": "河南",
        "is_henan_local_school": True, "school_code": school_code,
        "school_name": f"测试大学{code}", "major_group_code": code, "major_name": major,
        "plan_count": 2, "tuition": 5000, "accommodation": 1000,
        "batch": "本科批", "track": "历史类", "campus": "",
        "physical_restrictions": "", "special_qualification_type": "",
        "accepted_exam_languages": "", "remarks": remarks,
        "source_name": "test", "source_url": "https://example.com",
        "as_of": "2026-06-27T00:00:00+00:00", "confidence": 0.9, "review_status": "verified",
    })


def _make_history(code, year=2025, min_rank=60415, granularity="major_group", school_code="999"):
    return HenanAdmissionHistory.model_validate({
        "year": year, "track": "历史类", "school_code": school_code,
        "school_name": f"测试大学{code}", "major_group_code": code,
        "major_group_name": f"测试大学{code}-{code}", "major_name": None,
        "min_score": 490, "min_rank": min_rank, "avg_score": None, "avg_rank": None,
        "plan_count": 2, "batch": "本科批", "data_granularity": granularity,
        "source_name": "heao", "source_url": "https://example.com",
        "as_of": "2026-06-27T00:00:00+00:00", "confidence": 0.9, "review_status": "verified",
    })


def _setup(monkeypatch, groups, plans, history):
    from app.loader import henan_data_loader as loader
    monkeypatch.setattr(loader, "load_henan_program_groups", lambda seed_dir: groups)
    monkeypatch.setattr(loader, "load_henan_enrollment_plans", lambda seed_dir: plans)
    monkeypatch.setattr(loader, "load_henan_admission_history", lambda seed_dir: history)


# ── 问题2：advantage 口径统一 ──────────────────────────────────────────────

def test_advantage_caliber_reference_minus_student(monkeypatch):
    """advantage = 参考位次 − 考生位次（负=目标更难），与判档口径一致。"""
    from app.engine.henan_recommendation import build_henan_candidates
    # 考生位次 73822，2025原始位次68000 → 经百分位归一化到2026等效约60977
    # advantage = 60977 - 73822 = -12845（落入搏档[-14764,-7382)）
    groups = [_make_group("G1")]
    plans = [_make_plan("G1")]
    history = [_make_history("G1", 2025, 68000)]
    _setup(monkeypatch, groups, plans, history)

    c = build_henan_candidates(_profile(rank=73822))[0]
    d = c["bucket_detail"]
    assert d["advantage"] == 60977 - 73822  # = -12845（参考归一化后−考生）
    assert d["reference_rank"] == 60977  # 归一化后参考位次
    assert d["student_rank"] == 73822
    assert c["bucket"] == "搏"  # advantage=-12845 落入搏档


def test_advantage_ratio_uses_student_rank_denominator(monkeypatch):
    """advantage_ratio = advantage / 考生位次（分母是考生位次，非参考位次）。"""
    from app.engine.henan_recommendation import build_henan_candidates
    groups = [_make_group("G1")]
    plans = [_make_plan("G1")]
    history = [_make_history("G1", 2025, 68000)]
    _setup(monkeypatch, groups, plans, history)

    c = build_henan_candidates(_profile(rank=73822))[0]
    d = c["bucket_detail"]
    # advantage_ratio = -12845 / 73822 ≈ -0.174（分母是考生位次，非参考位次60977）
    expected = round((60977 - 73822) / 73822, 4)
    assert d["advantage_ratio"] == expected
    # 验证分母不是参考位次：若是 /60977 会得到 -0.2108，明显不同
    assert abs(d["advantage_ratio"] - (-0.174)) < 0.005


def test_old_rank_gap_ratio_is_null(monkeypatch):
    """旧 rank_gap_ratio 已废弃，恒为 null（方向相反，防误用）。"""
    from app.engine.henan_recommendation import build_henan_candidates
    groups = [_make_group("G1")]
    plans = [_make_plan("G1")]
    history = [_make_history("G1", 2025, 68000)]
    _setup(monkeypatch, groups, plans, history)

    c = build_henan_candidates(_profile(rank=73822))[0]
    d = c["bucket_detail"]
    assert d["rank_gap_ratio"] is None  # 旧口径废弃
    assert d["admission_probability"] is None  # 未校准概率停用
    assert d["calculation_version"] == "henan_tier_v1"


def test_advantage_positive_means_easier(monkeypatch):
    """advantage 正值 = 考生位次优于参考（更易录，应判保/垫）。"""
    from app.engine.henan_recommendation import build_henan_candidates, normalize_rank_to_target_year
    # 考生位次 30000，2025参考60000 → 归一化2026等效约53803，advantage=+23803（考生远优于参考）
    groups = [_make_group("G1")]
    plans = [_make_plan("G1")]
    history = [_make_history("G1", 2025, 60000)]
    _setup(monkeypatch, groups, plans, history)

    expected_ref = normalize_rank_to_target_year(60000, 2025, 2026)["normalized_rank"]
    c = build_henan_candidates(_profile(rank=30000))[0]
    d = c["bucket_detail"]
    assert d["advantage"] == expected_ref - 30000  # 正值：考生优于参考
    assert d["advantage"] > 0
    assert c["bucket"] in {"保", "垫"}  # 考生明显优于参考 → 保/垫


def test_tier_detail_bounds_present(monkeypatch):
    """bucket_detail.tier_detail 含判档真实边界（前端应直接读，不重算）。"""
    from app.engine.henan_recommendation import build_henan_candidates
    groups = [_make_group("G1")]
    plans = [_make_plan("G1")]
    history = [_make_history("G1", 2025, 68000)]
    _setup(monkeypatch, groups, plans, history)

    c = build_henan_candidates(_profile(rank=73822))[0]
    td = c["bucket_detail"]["tier_detail"]
    assert "advantage" in td
    assert "bounds" in td
    bounds = td["bounds"]
    # 五档分界线齐全
    for k in ("reach_floor", "reach_sprint", "sprint_stable", "stable_safe", "safe_fallback", "R"):
        assert k in bounds
    assert bounds["R"] == 73822  # 边界基于考生位次 R


# ── 问题1：需复核原因细分 ──────────────────────────────────────────────────

def test_review_reason_missing_2025_rank(monkeypatch):
    """缺2025同口径录取位次 → review_reason_code=missing_verified_2025_rank。"""
    from app.engine.henan_recommendation import build_henan_candidates
    groups = [_make_group("G1")]
    plans = [_make_plan("G1")]
    history = []  # 完全缺历史
    _setup(monkeypatch, groups, plans, history)

    c = build_henan_candidates(_profile(rank=73822))[0]
    assert c["bucket"] == "需人工复核"
    assert c["review_reason_code"] == "missing_verified_2025_rank"
    assert "2025" in c["review_reason"]
    # 资格已知（无硬阻），但录取不可预测
    assert c["admission_predictable"] is False


def test_review_reason_only_2024_old_regime(monkeypatch):
    """仅有2024旧文科数据 → review_reason_code=only_2024_old_regime。"""
    from app.engine.henan_recommendation import build_henan_candidates
    groups = [_make_group("G1")]
    plans = [_make_plan("G1")]
    history = [_make_history("G1", 2024, 60415)]  # 2024旧口径
    _setup(monkeypatch, groups, plans, history)

    c = build_henan_candidates(_profile(rank=73822))[0]
    assert c["bucket"] == "需人工复核"
    assert c["review_reason_code"] == "only_2024_old_regime"
    assert "2024" in c["review_reason"]


def test_review_summary_in_api(monkeypatch):
    """API review_summary 统计各需复核原因数量。"""
    from app.api.routers.henan import _summarize_language_restriction  # 仅确认 import 链路
    # 这里直接验证 build_henan_candidates 输出的 review_reason_code 分布
    from app.engine.henan_recommendation import build_henan_candidates
    from collections import Counter
    # 构造：一个缺2025、一个2024旧口径（不同 school_code 避免同校推断互相干扰）
    groups = [_make_group("G1", school_code="991"), _make_group("G2", school_code="992")]
    plans = [_make_plan("G1", school_code="991"), _make_plan("G2", school_code="992")]
    history = [_make_history("G2", 2024, 60415, school_code="992")]  # G2 有2024，G1 完全缺
    _setup(monkeypatch, groups, plans, history)

    candidates = build_henan_candidates(_profile(rank=73822))
    codes = Counter(c.get("review_reason_code") for c in candidates if c["bucket"] == "需人工复核")
    assert codes["missing_verified_2025_rank"] == 1  # G1
    assert codes["only_2024_old_regime"] == 1  # G2


def test_eligible_tiered_no_review_reason(monkeypatch):
    """进入五档（搏冲稳保垫）的候选不应有 review_reason（数据完整）。"""
    from app.engine.henan_recommendation import build_henan_candidates
    groups = [_make_group("G1")]
    plans = [_make_plan("G1")]
    history = [_make_history("G1", 2025, 68000)]  # 2025 verified
    _setup(monkeypatch, groups, plans, history)

    c = build_henan_candidates(_profile(rank=73822))[0]
    assert c["bucket"] in {"搏", "冲", "稳", "保", "垫"}
    assert c["review_reason_code"] is None
    assert c["admission_predictable"] is True
