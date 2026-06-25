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


class SchoolNature(str, Enum):
    """办学性质：公立 / 民办 / 中外合作。学费差异巨大，是费用估算关键。"""

    PUBLIC = "公立"
    PRIVATE = "民办"
    SINO_FOREIGN = "中外合作"


class EmploymentAbility(BaseModel):
    campus_tier: str
    avg_entry_salary: int
    employment_rate: float


class Discipline(BaseModel):
    name: str
    grade: str


class University(SourcedRecord):
    """大学：层级 + 就业能力 + 学科评估 + 费用(学费/住宿/办学性质/城市)。"""

    name: str
    province: str
    tier: UniversityTier
    employment_ability: EmploymentAbility
    disciplines: list[Discipline]
    # 费用相关（用于大学期间总开销估算，公立/民办差异大）
    nature: SchoolNature = SchoolNature.PUBLIC
    tuition: int = 5000  # 年学费(元)，公立普通类约5000，民办1.5-3万，中外合作更高
    accommodation: int = 1200  # 年住宿费(元)，普遍800-1500
    city: str | None = None  # 所在城市(关联 CityCost 算生活费)，无则用省级估算
