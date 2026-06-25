from pydantic import BaseModel, ConfigDict

from app.models.base import SourcedRecord


class EmploymentDensity(BaseModel):
    jobs: int
    frequency: float
    city_coverage: float


class SalaryQuantile(BaseModel):
    """薪资三分位（强制 P25/P50/P75，禁用平均值）。"""

    p25: int
    p50: int
    p75: int


class Barriers(BaseModel):
    english: bool
    math: bool
    certificate: bool
    postgrad: bool


class Upside(BaseModel):
    management: bool
    freelance: bool
    cross_industry: bool


class Major(SourcedRecord):
    """专业实力：就业密度 + 薪资三分位 + 门槛 + 上升空间。

    extra=forbid 拒绝 avg 等平均值字段，强制三分位。
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
    employment_density: EmploymentDensity
    salary: SalaryQuantile
    barriers: Barriers
    upside: Upside
