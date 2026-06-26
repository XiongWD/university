"""河南 2026 专业组规则、招生计划与批次线判断模型。

这些模型承载「以河南 2026 为主、可追溯」的志愿辅助能力所需的数据结构。
所有新增数据必须通过 SourceMetadata 携带来源粒度、置信度与复核状态。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SourceMetadata(BaseModel):
    """每条新增数据的来源元数据（design §3 强制字段）。"""

    source_name: str
    source_url: str
    as_of: str
    confidence: float = Field(ge=0, le=1)
    data_granularity: str  # official_plan / official_admission / official_rule / third_party_estimate / manual_review
    review_status: str  # verified / needs_review


class ProgramGroupRule(SourceMetadata):
    """一个院校专业组在河南的可报资格（design §4.1）。"""

    school: str
    province: str
    year: int
    batch: str
    major_group_code: str | None = None
    major_group_name: str
    primary_subject_requirement: str | None = None  # 物理 / 历史 / 空
    elective_subject_rule: dict = {}  # {"require": ["化学"], "any_of": []}
    accepted_exam_languages: list[str] = []
    required_exam_language: str | None = None
    subject_score_rules: list[dict] = []
    included_majors: list[str] = []


class EnrollmentPlan(SourceMetadata):
    """某院校、某省份、某年份的专业计划（design §4.2）。"""

    school: str
    source_province: str
    year: int
    major_group_code: str | None = None
    major_name: str
    plan_count: int = Field(ge=0)
    tuition: int | None = None
    school_system_years: int | None = None
    batch: str
    subject_requirement_text: str = ""


class BatchLineDecision(BaseModel):
    """引擎内部结构，用于本科线/专科线判断（design §4.3）。"""

    score: int
    rank: int
    undergrad_line: int | None = None
    junior_college_line: int | None = None
    distance_to_undergrad_line: int | None = None
    batch_position: str  # above_undergrad / below_undergrad / junior_college_only
    recommendation_policy_note: str
