"""学校专业供给数据桥梁层（P0-3）。

解决"学校属于财经类≠当年在豫招该专业"的事实风险。
两层关系：
1. SchoolMajorOffering: 学校长期开设哪些专业（学位层面）
2. AdmissionOffering: 某省某年某校某专业的实际招生计划（年度层面，含粒度标记）

数据粒度（data_granularity）是核心防伪装字段：
- major: 精确到专业录取线（最准）
- group: 精确到院校专业组（新高考）
- school: 仅学校级最低投档（专业未验证，只能"方向适合候选"）
避免把学校级数据伪装成专业级录取概率。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel

from app.models.base import SourcedRecord


class DataGranularity(str, Enum):
    """录取数据粒度，决定推荐可信度。"""

    MAJOR = "major"  # 精确到专业（老高考专业线，最准）
    GROUP = "group"  # 精确到院校专业组（新高考，含专业组内多个专业）
    SCHOOL = "school"  # 仅学校级最低投档（专业未确认，标注"方向适合候选"）


class SchoolMajorOffering(BaseModel):
    """学校长期开设的专业（学位层面，非年度招生）。

    用于判断"这所学校有没有这个专业"，而非"今年招不招"。
    is_active=False 表示已停招（如某专业近年撤销）。
    """

    school: str
    major: str
    degree_level: str = "本科"  # 本科/专科/硕士
    is_active: bool = True
    source: str
    as_of: str  # ISO date
    confidence: float
    note: str | None = None


class AdmissionOffering(SourcedRecord):
    """某省某年某校的招生计划/录取数据（年度层面）。

    在 AdmissionRecord 基础上增加 data_granularity，明确数据精确度。
    planned_enrollment 为招生计划数（名额少=波动大）。
    """

    school: str
    major: str | None  # None=学校级（未到专业）
    province: str
    admission_year: int
    track: str
    major_group_code: str | None = None
    subject_requirements: list[str] = []  # 选科要求，如["物理","化学"]
    foreign_language_restriction: str | None = None  # None=不限
    planned_enrollment: int | None = None  # 招生计划数
    tuition_year: int | None = None
    min_score: int | None = None
    min_rank: int | None = None
    data_granularity: DataGranularity = DataGranularity.SCHOOL
