from datetime import date

from pydantic import BaseModel, field_validator, model_validator


class SourcedRecord(BaseModel):
    """带来源追溯的记录基类。

    所有实体数据继承本类，强制每个数字可追溯到来源。
    """

    source: str
    as_of: date
    confidence: float
    note: str | None = None

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence 必须在 [0.0, 1.0] 之间")
        return v


class CostBand(BaseModel):
    """成本区间（low ≤ high），如租金、生活成本。"""

    low: int
    high: int

    @model_validator(mode="after")
    def _ordered(self) -> "CostBand":
        if self.low > self.high:
            raise ValueError("区间 low 不能大于 high")
        return self
