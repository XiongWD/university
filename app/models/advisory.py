"""志愿推荐 advisory 输出模型（专业方向优先主链路结果）。

对应父设计 docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md §4.1。
SchoolOption/AdmissionBuckets 复用 app.models.life_path（字段已兼容 §4.1）。
"""
from __future__ import annotations

from pydantic import BaseModel

from app.models.life_path import AdmissionBuckets  # noqa: F401  (re-export for convenience)


class MajorDirectionAdvice(BaseModel):
    """专业方向建议：方向 + 推荐专业 + market×fit 评分 + 解释/风险。"""

    direction: str
    recommended_majors: list[str] = []
    market_value: float = 0.0
    student_fit: float = 0.0
    major_value: float = 0.0  # market_value × student_fit（§3.4 乘法门控）
    fit_explanation: list[str] = []
    risk_warnings: list[str] = []


class BudgetSummary(BaseModel):
    """家庭预算与大学期间费用汇总（§3.6：费用压力，非回本）。"""

    tuition_4y: int = 0
    accommodation_4y: int = 0
    living_4y: int = 0
    total_4y: int = 0
    affordable_total: int = 0
    affordability_status: str = ""  # 可承受/有压力/明显负担/超预算
    data_note: str = ""


class IneligibleReason(BaseModel):
    """不可报原因（来自资格过滤）。"""

    school: str
    major_group_name: str = ""
    reasons: list[str] = []
    blocked_summary: str = ""


class VolunteerAdvisoryResult(BaseModel):
    """advisory 主接口结果（§4.1）。"""

    student_rank: int
    province: str
    track: str
    data_year: int
    major_directions: list[MajorDirectionAdvice] = []
    school_options: AdmissionBuckets
    ineligible_options: list[IneligibleReason] = []
    budget_summary: BudgetSummary
    notes: list[str] = []
