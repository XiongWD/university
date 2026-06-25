"""录取预测模型（V2.2 Phase 2——两阶段录取结构）。

核心纠正（评审）：
- 专业组投档概率(Stage A) ≠ 组内专业录取风险(Stage B)，不可混为一谈
- "大概率投进专业组"不能写成"大概率录取目标专业"
- 仅有专业组数据无组内专业数据时，必须明确"目标专业数据不足"
- 2026是新高考第二年，不输出精确到个位数概率，用档位(冲/偏冲/稳/偏保/保)+置信度
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class AdmissionMode(str, Enum):
    """批次录取模式（不同批次算法不同）。"""

    MAJOR_SCHOOL = "major_school"       # 提前批：专业+院校
    SCHOOL_MAJOR_GROUP = "major_group"  # 普通本科批：院校专业组（组内填专业+调剂）


class AdmissionLevel(str, Enum):
    """录取档位（替代精确概率，2026新高考第二年数据有限）。"""

    SPRINT = "冲"        # 仅乐观场景可录
    LEAN_SPRINT = "偏冲"  # 基准边缘偏冲
    STABLE = "稳"        # 基准场景可录
    LEAN_SAFE = "偏保"   # 基准+悲观均可录
    SAFE = "保"          # 悲观场景仍可录
    NOT_RECOMMENDED = "不推荐"  # 三场景都难


class DataPriority(str, Enum):
    """历史数据优先级（2026预测关键）。"""

    SAME_REGIME_PRIMARY = "same_regime_primary"  # 2025同制度(历史类/物理类)主依据
    OLD_REGIME_TREND = "old_regime_trend"        # 2024旧制度(文理科)仅趋势辅助
    LONG_TERM_REFERENCE = "long_term_reference"  # 2023及以前长期热度
    MANUAL_FALLBACK = "manual_fallback"          # 手编种子fallback


class ScenarioPrediction(BaseModel):
    """单场景预测（乐观/基准/悲观）。"""

    scenario: str  # optimistic / baseline / pessimistic
    can_admit: bool  # 该场景下能否录取
    expected_cutoff_rank: int  # 预期截止位次
    note: str = ""


class GroupAdmissionPrediction(BaseModel):
    """Stage A：专业组投档预测。"""

    school: str
    major_group_code: str | None
    student_rank: int
    scenarios: list[ScenarioPrediction]  # 三场景
    admission_level: AdmissionLevel  # 综合档位
    data_priority: DataPriority  # 数据依据优先级
    data_granularity: str  # major/group/school（防伪装）
    confidence: float  # 0-1
    note: str = ""


class MajorAllocationPrediction(BaseModel):
    """Stage B：组内专业录取风险（进入专业组后）。"""

    target_major: str | None
    target_major_admittable: bool | None  # None=数据不足无法判断
    adjustment_risk: str  # low/medium/high（服从调剂风险）
    unwanted_major_risk: str  # low/medium/high（被调剂到冷门专业风险）
    data_sufficient: bool  # False=仅有专业组数据，组内专业数据不足
    note: str = ""


class AdmissionPrediction(BaseModel):
    """完整两阶段录取预测。"""

    group: GroupAdmissionPrediction
    major: MajorAllocationPrediction | None = None  # None=未做Stage B

    @property
    def summary(self) -> str:
        """人类可读汇总（禁止把组投档写成专业录取）。"""
        g = self.group
        parts = [f"{g.school} 专业组录取：{g.admission_level.value}（{g.data_priority.value}）"]
        if self.major:
            m = self.major
            if m.data_sufficient:
                if m.target_major:
                    parts.append(f"目标专业({m.target_major})录取：{'可' if m.target_major_admittable else '风险'}")
                parts.append(f"调剂风险：{m.adjustment_risk}")
            else:
                parts.append("目标专业录取：数据不足，仅专业组可估算")
        return "；".join(parts)
