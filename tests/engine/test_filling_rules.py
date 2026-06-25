"""填报规则引擎测试（8大专家规则）。"""
import pytest
from datetime import date

from app.engine.filling_rules import (
    assess_quota_risk, QuotaRisk,
    convert_same_rank_score,
    assess_region_heat, RegionHeat,
    assess_employment_barrier,
    generate_filling_advice,
    check_same_rank_warning,
)
from app.models.provincial import ScoreRankEntry


# ===== 规则1：招生计划数→波动风险 =====
def test_quota_stable_large_plan():
    risk, _ = assess_quota_risk(15)
    assert risk == QuotaRisk.STABLE


def test_quota_high_risk_tiny_plan():
    risk, note = assess_quota_risk(1)
    assert risk == QuotaRisk.HIGH
    assert "大小年" in note


def test_quota_moderate_small_plan():
    risk, _ = assess_quota_risk(5)
    assert risk == QuotaRisk.MODERATE


def test_quota_unknown_defaults_moderate():
    risk, _ = assess_quota_risk(None)
    assert risk == QuotaRisk.MODERATE


# ===== 规则2：同位分换算 =====
def test_same_rank_conversion():
    """今年位次→目标年等效分数。"""
    target_entries = [
        ScoreRankEntry(score=500, count_at=100, cumulative_rank=70000),
        ScoreRankEntry(score=490, count_at=120, cumulative_rank=80000),
        ScoreRankEntry(score=480, count_at=150, cumulative_rank=90000),
    ]
    # 位次80000→目标年490分
    score = convert_same_rank_score(80000, target_entries, [])
    assert score == 490


def test_same_rank_empty_returns_none():
    assert convert_same_rank_score(80000, [], []) is None


def test_same_rank_warning_when_raw_passes_but_same_rank_fails():
    """裸分>校线但同位分<校线→警告（试卷难度差异）。"""
    warn = check_same_rank_warning(
        student_score=480, same_rank_score_2024=465,
        school_min_score_2024=470,
    )
    assert warn is not None
    assert "同位分" in warn


def test_no_warning_when_both_pass():
    assert check_same_rank_warning(490, 485, 470) is None


# ===== 规则4：地域热度 =====
def test_in_province_heat():
    heat, _ = assess_region_heat("河南", "河南")
    assert heat == RegionHeat.IN_PROVINCE


def test_coastal_high_heat():
    heat, note = assess_region_heat("江苏", "河南")
    assert heat == RegionHeat.COASTAL_HIGH
    assert "高15-40分" in note


def test_inland_low_heat():
    heat, _ = assess_region_heat("江西", "河南")
    assert heat == RegionHeat.INLAND_LOW


# ===== 规则7：就业地域壁垒 =====
def test_in_province_high_recognition():
    barrier = assess_employment_barrier("河南", "河南")
    assert barrier.province_recognition == "high"
    assert barrier.civil_service_advantage == "high"


def test_out_province_lower_recognition():
    barrier = assess_employment_barrier("广东", "河南")
    assert barrier.province_recognition == "low"
    assert "回河南就业认可度低于省内" in barrier.note


# ===== 综合建议生成 =====
def test_advice_for_coastal_tiny_plan_reach():
    """沿海+计划1人+冲→多条警告。"""
    advice = generate_filling_advice(
        school="某沿海校", school_province="广东",
        planned_enrollment=1, admission_level="冲",
    )
    # 应有大小年警告 + 沿海热度警告 + 调剂提醒 + 就业壁垒
    assert len(advice) >= 3
    assert any("大小年" in a for a in advice)
    assert any("调剂" in a for a in advice)


def test_advice_for_in_province_stable():
    """省内+计划多+稳→正面建议。"""
    advice = generate_filling_advice(
        school="河南某校", school_province="河南",
        planned_enrollment=20, admission_level="稳",
    )
    # 省内认可度高应该是正面（含校招/认可/本地等正面词）
    assert any(("省内" in a or "本地" in a) and ("校招" in a or "认可" in a or "优先" in a) for a in advice)


def test_advice_includes_region_info():
    """建议含地域信息。"""
    advice = generate_filling_advice("九江学院", "江西", 5, "稳")
    assert any("中西部" in a or "友好" in a for a in advice)
