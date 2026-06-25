from pydantic import BaseModel, field_validator

from app.models.base import SourcedRecord


class RatePair(BaseModel):
    """单一险种的个人/单位缴纳比例（0–1）。"""

    employee: float
    employer: float

    @field_validator("employee", "employer")
    @classmethod
    def _rate_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("社保比例必须在 [0.0, 1.0]")
        return v


class InsuranceRates(BaseModel):
    pension: RatePair
    medical: RatePair
    unemployment: RatePair
    work_injury: RatePair
    maternity: RatePair
    housing_fund: RatePair


class SocialInsurance(SourcedRecord):
    """城市五险一金配置。城市差异是比例范围，结构统一。"""

    city: str
    rates: InsuranceRates


# 全国基准比例（文档给定）：养老 8%/16%、医疗 2%/9%、失业 0.3%/0.5%、
# 工伤 0%/0.5%、生育 0%/0%、公积金 8%/8%。
NATIONAL_BASELINE_RATES = InsuranceRates(
    pension=RatePair(employee=0.08, employer=0.16),
    medical=RatePair(employee=0.02, employer=0.09),
    unemployment=RatePair(employee=0.003, employer=0.005),
    work_injury=RatePair(employee=0.0, employer=0.005),
    maternity=RatePair(employee=0.0, employer=0.0),
    housing_fund=RatePair(employee=0.08, employer=0.08),
)
