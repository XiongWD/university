from datetime import date

from app.models.city import CityCost, RentTiers
from app.models.base import CostBand
from app.engine.cost import compute_annual_cost


def _city() -> CityCost:
    return CityCost(
        city="深圳",
        rent=RentTiers(
            single=CostBand(low=1200, high=1800),
            one_bed=CostBand(low=1800, high=2600),
            shared=CostBand(low=800, high=1200),
        ),
        food=CostBand(low=1200, high=2000),
        commute=CostBand(low=150, high=300),
        other=CostBand(low=400, high=800),
        monthly_total=CostBand(low=3500, high=6000),
        house_price_avg=55000,
        source="贝壳",
        as_of=date(2024, 6, 1),
        confidence=0.5,
        note="待爬虫校准",
    )


def test_annual_cost_uses_monthly_mid():
    c = _city()
    band = compute_annual_cost(c, tuition=5000, accommodation=1200)
    monthly_mid = (c.monthly_total.low + c.monthly_total.high) / 2
    expected = round(12 * monthly_mid + 5000 + 1200)
    assert band.low == expected
    assert band.high == expected  # 中位法单值，两端相等
