"""SQLite 表模型（SQLModel table=True，字段拍平）。

嵌套对象（薪资三档、租房三档、学科评估列表）拍平为多个列，
或存为 JSON 字符串列（list/复合结构）。
"""

from datetime import date
from typing import Optional

from sqlmodel import SQLModel, Field


def _confidence_check(v: float) -> float:
    """Table 层 confidence 不变量校验：与 Domain 层 SourcedRecord 保持一致 [0,1]。

    供 mappers 写回 Row 前调用（SQLModel table 类的 field_validator 不可靠）。
    """
    if v is not None and not 0.0 <= v <= 1.0:
        raise ValueError(f"confidence 必须在 [0.0, 1.0] 之间，得到 {v}")
    return v


class CareerRow(SQLModel, table=True):
    __tablename__ = "careers"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category: str
    entry_salary_low: int
    entry_salary_mid: int
    entry_salary_high: int
    mid5_low: int
    mid5_mid: int
    mid5_high: int
    ceil15_low: int
    ceil15_mid: int
    ceil15_high: int
    stability: float
    promotion_speed: str
    establishment_type: str
    related_majors: str  # JSON
    source: str
    as_of: date
    confidence: float
    note: Optional[str] = None


class SocialInsuranceRow(SQLModel, table=True):
    __tablename__ = "social_insurance"
    id: Optional[int] = Field(default=None, primary_key=True)
    city: str
    pension_employee: float
    pension_employer: float
    medical_employee: float
    medical_employer: float
    unemployment_employee: float
    unemployment_employer: float
    workinjury_employee: float
    workinjury_employer: float
    maternity_employee: float
    maternity_employer: float
    housing_employee: float
    housing_employer: float
    source: str
    as_of: date
    confidence: float
    note: Optional[str] = None


class CityCostRow(SQLModel, table=True):
    __tablename__ = "city_costs"
    id: Optional[int] = Field(default=None, primary_key=True)
    city: str
    rent_single_low: int
    rent_single_high: int
    rent_onebed_low: int
    rent_onebed_high: int
    rent_shared_low: int
    rent_shared_high: int
    food_low: int
    food_high: int
    commute_low: int
    commute_high: int
    other_low: int
    other_high: int
    monthly_total_low: int
    monthly_total_high: int
    house_price_avg: int
    source: str
    as_of: date
    confidence: float
    note: Optional[str] = None


class UniversityRow(SQLModel, table=True):
    __tablename__ = "universities"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    province: str
    tier: str
    campus_tier: str
    avg_entry_salary: int
    employment_rate: float
    disciplines: str  # JSON
    source: str
    as_of: date
    confidence: float
    note: Optional[str] = None
    nature: str = "公立"  # 办学性质(公立/民办/中外合作)
    tuition: int = 5000  # 年学费(元)
    accommodation: int = 1200  # 年住宿费(元)
    city: Optional[str] = None  # 所在城市


class MajorRow(SQLModel, table=True):
    __tablename__ = "majors"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category: str
    jobs: int
    frequency: float
    city_coverage: float
    p25: int
    p50: int
    p75: int
    barrier_english: bool
    barrier_math: bool
    barrier_certificate: bool
    barrier_postgrad: bool
    upside_management: bool
    upside_freelance: bool
    upside_cross_industry: bool
    source: str
    as_of: date
    confidence: float
    note: Optional[str] = None


class AdmissionRow(SQLModel, table=True):
    __tablename__ = "admissions"
    id: Optional[int] = Field(default=None, primary_key=True)
    school: str
    major: str
    province: str
    year: int
    track: str
    min_score: int
    min_rank: int
    avg_score: int
    batch: str
    source: str
    as_of: date
    confidence: float
    note: Optional[str] = None
    major_group: Optional[str] = None
    subject_requirement: Optional[str] = None
    foreign_language_required: str = "不限"
    single_subject_requirements: Optional[str] = None  # JSON


class StudentRow(SQLModel, table=True):
    __tablename__ = "students"
    id: Optional[int] = Field(default=None, primary_key=True)
    province: str
    total_score: int
    subject_scores: str  # JSON
    minor_language: Optional[str]  # JSON or null
    family_resources: str  # JSON of 6 bools
    gender: str
    interests: str  # JSON
    strengths: str  # JSON
    risk_preference: str
    source: str
    as_of: date
    confidence: float
    note: Optional[str] = None


class ProvincialControlLineRow(SQLModel, table=True):
    __tablename__ = "provincial_control_lines"
    id: Optional[int] = Field(default=None, primary_key=True)
    province: str
    year: int
    track: str
    special_line: Optional[int] = None
    first_batch: Optional[int] = None
    second_batch: Optional[int] = None
    undergrad_batch: Optional[int] = None
    junior_college: Optional[int] = None
    source: str
    as_of: date
    confidence: float
    note: Optional[str] = None


class ScoreRankTableRow(SQLModel, table=True):
    __tablename__ = "score_rank_tables"
    id: Optional[int] = Field(default=None, primary_key=True)
    province: str
    year: int
    track: str
    source: str
    as_of: date
    confidence: float
    note: Optional[str] = None


class ScoreRankEntryRow(SQLModel, table=True):
    __tablename__ = "score_rank_entries"
    id: Optional[int] = Field(default=None, primary_key=True)
    table_id: int = Field(foreign_key="score_rank_tables.id")
    score: int
    count_at: int
    cumulative_rank: int
