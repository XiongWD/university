from datetime import date

import pytest
from pydantic import ValidationError

from app.models.city import CityCost, RentTiers
from app.models.base import CostBand


def _kw(**over):
    base = dict(
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
        source="贝壳租房2024",
        as_of=date(2024, 6, 1),
        confidence=0.5,
        note="待爬虫校准",
    )
    base.update(over)
    return base


def test_city_legal():
    c = CityCost(**_kw())
    assert c.rent.one_bed.high == 2600
    assert c.monthly_total.low == 3500


def test_rent_band_inverted_rejected():
    with pytest.raises(ValidationError):
        CityCost(**_kw(rent=RentTiers(
            single=CostBand(low=3000, high=1000),
            one_bed=CostBand(low=1800, high=2600),
            shared=CostBand(low=800, high=1200),
        )))
