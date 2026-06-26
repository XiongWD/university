"""目标院校 + 专业评估模型（design target-admission-evaluation §4）。

区分「能投进专业组」与「能录取目标专业」，输出资格、投档风险、专业风险、
调剂风险、数据缺口与来源。不输出精确百分比，风险档位固定为
`高 / 中高 / 中 / 低 / 不可报 / 数据不足`。
"""
from __future__ import annotations

from pydantic import BaseModel


class TargetEvaluationRequest(BaseModel):
    """目标评估请求（design §4.1）。"""

    source_province: str  # 考生生源地，如河南
    target_school: str
    target_major: str | None = None  # 可选；为空时只评估专业组/学校投档风险
    data_year: int = 2026
    total_score: int
    primary_subject: str  # 物理 / 历史
    elective_subjects: list[str] = []
    exam_foreign_language: str = "英语"
    foreign_language_score: int = 0
    math_score: int = 0
    english_actual_level: str = "intermediate"
    accept_adjustment: bool = True


class AdmissionSource(BaseModel):
    """结构化来源（design §4.3）。"""

    source_name: str
    source_url: str
    source_type: str  # admission_brochure / enrollment_plan / score_rank / control_line / historical_admission
    as_of: str
    confidence: float


class EligibilityAssessment(BaseModel):
    """资格判断结果（design §5.3）。"""

    eligible: bool
    blocked_reasons: list[str] = []
    review_warnings: list[str] = []


class RiskAssessment(BaseModel):
    """投档/录取风险评估（design §5.4）。"""

    risk_band: str  # 高 / 中高 / 中 / 低 / 不可报 / 数据不足
    basis: str = ""
    student_rank: int | None = None
    baseline_rank: int | None = None
    data_year_used: int | None = None
    confidence: float = 0.0


class MajorAdmissionAssessment(BaseModel):
    """目标专业录取风险评估（design §5.5）。"""

    risk_band: str  # 高 / 中高 / 中 / 低 / 不可报 / 数据不足
    target_major_available: bool = False
    plan_count: int | None = None
    basis: str = ""
    adjustment_risk: str = "数据不足"  # 服从调剂时的退档/滑档风险


class TargetEvaluationResult(BaseModel):
    """目标评估结果（design §4.2）。

    eligibility/group_admission/major_admission 接受模型或 dict，
    便于不同数据完整度下灵活构造（缺数据时常用 dict 简化）。
    """

    target_school: str
    target_major: str | None = None
    source_province: str
    eligibility: EligibilityAssessment | dict
    group_admission: RiskAssessment | dict
    major_admission: MajorAdmissionAssessment | dict
    sources: list[AdmissionSource] = []
    missing_data: list[str] = []
    recommendation_summary: str
