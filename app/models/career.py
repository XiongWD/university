from enum import Enum

from pydantic import BaseModel, field_validator, model_validator

from app.models.base import SourcedRecord


class SalaryBand(BaseModel):
    """薪资区间（起薪/中位/上限），强制 low ≤ mid ≤ high。"""

    low: int
    mid: int
    high: int

    @model_validator(mode="after")
    def _ordered(self) -> "SalaryBand":
        if not (self.low <= self.mid <= self.high):
            raise ValueError("薪资区间需满足 low ≤ mid ≤ high")
        return self


class PromotionSpeed(str, Enum):
    SLOW = "慢"
    MEDIUM = "中"
    FAST = "快"


class EstablishmentType(str, Enum):
    ADMINISTRATIVE = "行政编"
    PUBLIC_INSTITUTION = "事业编"
    ENTERPRISE = "企业"
    NONE = "无"


class Career(SourcedRecord):
    """职业数据（薪资三档区间 + 稳定性 + 编制）。"""

    name: str
    category: str
    entry_salary: SalaryBand
    mid_salary_5y: SalaryBand
    ceil_salary_15y: SalaryBand
    stability: float
    promotion_speed: PromotionSpeed
    establishment_type: EstablishmentType
    related_majors: list[str]

    @field_validator("stability")
    @classmethod
    def _stability_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("stability 必须在 [0.0, 1.0]")
        return v
