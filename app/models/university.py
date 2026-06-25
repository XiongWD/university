from enum import Enum

from pydantic import BaseModel

from app.models.base import SourcedRecord


class UniversityTier(str, Enum):
    TIER_985 = "985"
    TIER_211 = "211"
    DOUBLE_FIRST_CLASS = "双一流"
    FIRST_BATCH = "一本"
    SECOND_BATCH = "二本"
    JUNIOR_COLLEGE = "专科"


class EmploymentAbility(BaseModel):
    campus_tier: str
    avg_entry_salary: int
    employment_rate: float


class Discipline(BaseModel):
    name: str
    grade: str


class University(SourcedRecord):
    """大学三维实力：层级 + 就业能力 + 学科评估。"""

    name: str
    province: str
    tier: UniversityTier
    employment_ability: EmploymentAbility
    disciplines: list[Discipline]
