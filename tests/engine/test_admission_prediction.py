"""录取预测引擎测试（V2.2 Phase 2——两阶段录取）。

验证核心：
- 专业组投档(Stage A) vs 组内专业(Stage B)分开，不混为一谈
- 数据优先级：2025同制度primary，2024旧制度trend(降置信)
- 三场景→档位(冲/偏冲/稳/偏保/保)，非精确概率
- 仅有专业组数据→"目标专业数据不足"
"""
import pytest

from app.engine.admission_prediction import (
    predict_admission,
    predict_group_admission,
    predict_major_allocation,
)
from app.models.admission_prediction import (
    AdmissionLevel, DataPriority,
)


# ===== Stage A：专业组投档 =====
def test_safe_when_student_rank_well_within():
    """考生位次远优于专业组线(悲观都能录)→保。"""
    g = predict_group_admission("A校", "101", student_rank=50000, baseline_rank_2025=80000)
    assert g.admission_level == AdmissionLevel.SAFE
    assert g.data_priority == DataPriority.SAME_REGIME_PRIMARY


def test_sprint_when_student_rank_far():
    """考生位次远低于专业组线(仅乐观勉强)→冲。"""
    g = predict_group_admission("A校", "101", student_rank=80000, baseline_rank_2025=50000)
    # 考生位次80000 > 截止，乐观也难→不推荐或偏冲
    assert g.admission_level in (AdmissionLevel.NOT_RECOMMENDED, AdmissionLevel.LEAN_SPRINT)


def test_stable_when_matched():
    """考生位次接近专业组线(基准能录)→稳。"""
    g = predict_group_admission("A校", "101", student_rank=75000, baseline_rank_2025=80000)
    # 基准场景截止约80000，考生75000能录；悲观可能前移
    assert g.admission_level in (AdmissionLevel.STABLE, AdmissionLevel.LEAN_SAFE, AdmissionLevel.SAFE)


def test_three_scenarios_generated():
    """三场景(乐观/基准/悲观)都生成。"""
    g = predict_group_admission("A校", "101", student_rank=50000, baseline_rank_2025=60000)
    assert len(g.scenarios) == 3
    scenarios = [s.scenario for s in g.scenarios]
    assert "optimistic" in scenarios and "baseline" in scenarios and "pessimistic" in scenarios


# ===== 数据优先级 =====
def test_2025_same_regime_is_primary():
    """有2025同制度数据→primary。"""
    g = predict_group_admission("A校", "101", 50000, baseline_rank_2025=60000)
    assert g.data_priority == DataPriority.SAME_REGIME_PRIMARY
    assert g.confidence >= 0.6


def test_2024_old_regime_is_trend_with_lower_confidence():
    """仅2024旧制度→trend，置信降低。"""
    g = predict_group_admission("A校", "101", 50000, baseline_rank_2025=None, old_regime_rank_2024=55000)
    assert g.data_priority == DataPriority.OLD_REGIME_TREND
    assert g.confidence <= 0.5  # 旧制度降置信


def test_no_data_is_fallback():
    """无历史数据→fallback极低置信。"""
    g = predict_group_admission("A校", "101", 50000, baseline_rank_2025=None)
    assert g.data_priority == DataPriority.MANUAL_FALLBACK
    assert g.confidence <= 0.3


# ===== Stage B：组内专业风险 =====
def test_major_data_insufficient_when_only_group_data():
    """仅有专业组数据无组内专业→data_sufficient=False。"""
    m = predict_major_allocation(
        target_major="日语", major_history_rank=None,
        student_rank=50000, group_plan_count=None, major_plan_count=None,
    )
    assert not m.data_sufficient
    assert m.target_major_admittable is None  # 无法判断


def test_major_admittable_when_rank_sufficient():
    """有组内专业数据+考生位次优于专业线→可录。"""
    m = predict_major_allocation(
        target_major="日语", major_history_rank=60000,
        student_rank=50000, group_plan_count=10, major_plan_count=5,
    )
    assert m.data_sufficient
    assert m.target_major_admittable is True


def test_adjustment_risk_high_when_not_accept():
    """不服从调剂→高调剂风险。"""
    m = predict_major_allocation(
        target_major="日语", major_history_rank=60000,
        student_rank=50000, group_plan_count=10, major_plan_count=5,
        accepts_adjustment=False,
    )
    assert m.adjustment_risk == "high"


def test_unwanted_major_risk_when_cannot_admit_target():
    """录不进目标专业但服从调剂→冷门专业风险高。"""
    m = predict_major_allocation(
        target_major="日语", major_history_rank=40000,  # 专业线优于考生
        student_rank=50000, group_plan_count=10, major_plan_count=5,
        accepts_adjustment=True,
    )
    assert m.target_major_admittable is False  # 录不进日语
    assert m.unwanted_major_risk == "high"  # 可能被调剂到冷门


# ===== 两阶段集成（禁止混为一谈）=====
def test_summary_does_not_confuse_group_with_major():
    """summary不得把'专业组录取'写成'专业录取'。"""
    pred = predict_admission(
        school="A校", major_group_code="101", student_rank=50000,
        baseline_rank_2025=60000, target_major="日语",
        major_history_rank=None,  # 无组内专业数据
    )
    summary = pred.summary
    # 专业组可估算，但目标专业数据不足（不混为一谈）
    assert "专业组" in summary
    assert "数据不足" in summary or "目标专业" in summary


def test_summary_shows_both_stages_when_data_sufficient():
    """数据充足时summary同时显示专业组+目标专业。"""
    pred = predict_admission(
        school="A校", major_group_code="101", student_rank=50000,
        baseline_rank_2025=60000, target_major="日语",
        major_history_rank=55000, major_plan_count=5, group_plan_count=10,
    )
    summary = pred.summary
    assert "专业组" in summary
    assert "日语" in summary


# ===== 弟弟场景（480历史类位次73822）=====
def test_brother_scenario_group_prediction():
    """弟弟480位次73822 vs 某校专业组2025线85000→应可录。"""
    g = predict_group_admission(
        school="升达", major_group_code="101",
        student_rank=73822, baseline_rank_2025=85000,
    )
    # 考生73822 < 截止85000 → 应能录
    assert g.admission_level in (AdmissionLevel.STABLE, AdmissionLevel.LEAN_SAFE, AdmissionLevel.SAFE)


def test_data_granularity_carried():
    """data_granularity从输入传递到输出（防伪装）。"""
    g = predict_group_admission("A校", "101", 50000, 60000, data_granularity="school")
    assert g.data_granularity == "school"
