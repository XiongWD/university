from datetime import date

import pytest
from pydantic import ValidationError

from app.models.career import (
    Career, SalaryBand, PromotionSpeed, EstablishmentType,
)


def _band(low, mid, high):
    return {"low": low, "mid": mid, "high": high}


def _kw(**over):
    base = dict(
        name="公务员-科员",
        category="公务员",
        entry_salary=_band(4000, 5000, 6000),
        mid_salary_5y=_band(7000, 8000, 9000),
        ceil_salary_15y=_band(10000, 12000, 15000),
        stability=0.9,
        promotion_speed=PromotionSpeed.SLOW,
        establishment_type=EstablishmentType.ADMINISTRATIVE,
        related_majors=["法学", "公共管理"],
        source="公务员公开报告2024",
        as_of=date(2024, 5, 1),
        confidence=0.5,
        note="待爬虫校准",
    )
    base.update(over)
    return base


def test_career_legal():
    c = Career(**_kw())
    assert c.entry_salary.mid == 5000
    assert c.establishment_type == EstablishmentType.ADMINISTRATIVE


def test_salary_band_inverted_rejected():
    with pytest.raises(ValidationError):
        SalaryBand(low=6000, mid=5000, high=4000)


def test_stability_out_of_range_rejected():
    with pytest.raises(ValidationError):
        Career(**_kw(stability=1.5))


def test_bad_establishment_rejected():
    with pytest.raises(ValidationError):
        Career(**_kw(establishment_type="虚构编"))
