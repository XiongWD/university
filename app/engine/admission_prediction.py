"""录取预测引擎（V2.2 Phase 2——两阶段录取，纯函数）。

Stage A：专业组投档预测
- 用2025同制度位次为primary基准，2024旧制度仅trend辅助（不直接平均）
- 三场景：乐观/基准/悲观（替代"比去年高10分=稳"）
- 2026新高考第二年，输出档位(冲/偏冲/稳/偏保/保)+置信度，非精确概率

Stage B：组内专业录取风险
- 仅当有组内专业数据时判断 target_major_admittable
- 仅有专业组数据→data_sufficient=False，明确"目标专业数据不足"
- adjustment_risk/unwanted_major_risk 基于招生计划+调剂规则

关键禁止（Execution Spec）：不允许把"投进专业组"写成"录取目标专业"。
"""
from __future__ import annotations

from app.models.admission_prediction import (
    AdmissionLevel,
    AdmissionPrediction,
    DataPriority,
    GroupAdmissionPrediction,
    MajorAllocationPrediction,
    ScenarioPrediction,
)


def _scenario_cutoff(
    baseline_rank: int,
    plan_change_ratio: float,
    heat_shift: int,
    scenario: str,
) -> int:
    """计算某场景的预期截止位次。

    baseline_rank: 2025同制度该专业组最低投档位次
    plan_change_ratio: 2026计划数/2025计划数 - 1（扩招位次后移）
    heat_shift: 热度变化导致的位次偏移（正=更热位次前移）
    """
    plan_adj = baseline_rank * plan_change_ratio
    if scenario == "optimistic":
        return int(baseline_rank + plan_adj + heat_shift * -1.5)
    if scenario == "pessimistic":
        return int(baseline_rank - plan_adj * 0.5 + heat_shift * 1.5)
    return int(baseline_rank + plan_adj + heat_shift * -0.5)


def predict_group_admission(
    school: str,
    major_group_code: str | None,
    student_rank: int,
    baseline_rank_2025: int | None,
    old_regime_rank_2024: int | None = None,
    plan_change_ratio: float = 0.0,
    heat_shift: int = 0,
    data_granularity: str = "group",
    confidence: float = 0.7,
) -> GroupAdmissionPrediction:
    """Stage A：专业组投档预测（三场景到档位）。

    数据优先级：2025同制度primary，2024旧制度trend only(降置信)，都无则fallback。
    """
    if baseline_rank_2025 is not None:
        baseline = baseline_rank_2025
        priority = DataPriority.SAME_REGIME_PRIMARY
    elif old_regime_rank_2024 is not None:
        baseline = old_regime_rank_2024
        priority = DataPriority.OLD_REGIME_TREND
        confidence = min(confidence, 0.5)
    else:
        baseline = 0
        priority = DataPriority.MANUAL_FALLBACK
        confidence = 0.3

    scenarios = []
    for scen, label in [("optimistic", "乐观"), ("baseline", "基准"), ("pessimistic", "悲观")]:
        cutoff = max(1, _scenario_cutoff(baseline, plan_change_ratio, heat_shift, scen))
        can_admit = student_rank <= cutoff
        scenarios.append(ScenarioPrediction(
            scenario=scen, can_admit=can_admit,
            expected_cutoff_rank=cutoff, note=f"{label}场景截止{cutoff}",
        ))

    opt = scenarios[0].can_admit
    base_ok = scenarios[1].can_admit
    pess = scenarios[2].can_admit

    if pess:
        level = AdmissionLevel.SAFE
    elif base_ok and not pess:
        level = AdmissionLevel.LEAN_SAFE
    elif base_ok:
        level = AdmissionLevel.STABLE
    elif opt:
        level = AdmissionLevel.SPRINT
    else:
        opt_cutoff = scenarios[0].expected_cutoff_rank
        level = AdmissionLevel.LEAN_SPRINT if student_rank <= opt_cutoff * 1.1 else AdmissionLevel.NOT_RECOMMENDED

    if priority == DataPriority.SAME_REGIME_PRIMARY:
        note = f"2025同制度位次{baseline_rank_2025}为主据"
    elif priority == DataPriority.OLD_REGIME_TREND:
        note = f"仅2024旧制度({old_regime_rank_2024})趋势参考，置信降低"
    else:
        note = "无同制度历史数据，人工估算，置信极低"

    return GroupAdmissionPrediction(
        school=school, major_group_code=major_group_code,
        student_rank=student_rank, scenarios=scenarios,
        admission_level=level, data_priority=priority,
        data_granularity=data_granularity, confidence=confidence, note=note,
    )


def predict_major_allocation(
    target_major: str | None,
    major_history_rank: int | None,
    student_rank: int,
    group_plan_count: int | None,
    major_plan_count: int | None,
    accepts_adjustment: bool = True,
    data_sufficient: bool | None = None,
) -> MajorAllocationPrediction:
    """Stage B：组内专业录取风险。"""
    if data_sufficient is None:
        data_sufficient = major_history_rank is not None and major_plan_count is not None

    if not data_sufficient:
        return MajorAllocationPrediction(
            target_major=target_major, target_major_admittable=None,
            adjustment_risk="medium" if not accepts_adjustment else "low",
            unwanted_major_risk="medium", data_sufficient=False,
            note="仅有专业组数据，组内目标专业录取数据不足",
        )

    admittable = student_rank <= major_history_rank if major_history_rank else None

    if not accepts_adjustment:
        adj_risk = "high"
    elif major_plan_count is not None and major_plan_count <= 2:
        adj_risk = "medium"
    else:
        adj_risk = "low"

    unwanted = "low"
    if admittable is False and accepts_adjustment:
        unwanted = "high"
    elif admittable is None:
        unwanted = "medium"

    return MajorAllocationPrediction(
        target_major=target_major, target_major_admittable=admittable,
        adjustment_risk=adj_risk, unwanted_major_risk=unwanted,
        data_sufficient=True,
        note=f"目标专业历史位次{major_history_rank}，考生{student_rank}",
    )


def predict_admission(
    school: str,
    major_group_code: str | None,
    student_rank: int,
    baseline_rank_2025: int | None,
    target_major: str | None = None,
    major_history_rank: int | None = None,
    old_regime_rank_2024: int | None = None,
    plan_change_ratio: float = 0.0,
    heat_shift: int = 0,
    major_plan_count: int | None = None,
    group_plan_count: int | None = None,
    accepts_adjustment: bool = True,
    data_granularity: str = "group",
    confidence: float = 0.7,
) -> AdmissionPrediction:
    """完整两阶段录取预测（Stage A + Stage B）。"""
    group = predict_group_admission(
        school=school, major_group_code=major_group_code,
        student_rank=student_rank, baseline_rank_2025=baseline_rank_2025,
        old_regime_rank_2024=old_regime_rank_2024,
        plan_change_ratio=plan_change_ratio, heat_shift=heat_shift,
        data_granularity=data_granularity, confidence=confidence,
    )
    major = predict_major_allocation(
        target_major=target_major, major_history_rank=major_history_rank,
        student_rank=student_rank, group_plan_count=group_plan_count,
        major_plan_count=major_plan_count, accepts_adjustment=accepts_adjustment,
    )
    return AdmissionPrediction(group=group, major=major)
