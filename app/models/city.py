from pydantic import BaseModel

from app.models.base import SourcedRecord, CostBand


class RentTiers(BaseModel):
    """租房三档区间：单间/一房一厅/合租。"""

    single: CostBand
    one_bed: CostBand
    shared: CostBand


class CityCost(SourcedRecord):
    """城市生活成本（租房三档 + 吃饭/通勤/其他 + 综合月成本 + 房价）。"""

    city: str
    rent: RentTiers
    food: CostBand
    commute: CostBand
    other: CostBand
    monthly_total: CostBand
    house_price_avg: int
