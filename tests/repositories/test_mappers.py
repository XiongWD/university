import json
from datetime import date

from app.models.career import (
    Career, SalaryBand, PromotionSpeed, EstablishmentType,
)
from app.repositories.mappers import career_to_row, career_to_domain


def _career() -> Career:
    return Career(
        name="公务员-科员", category="公务员",
        entry_salary=SalaryBand(low=4000, mid=5000, high=6000),
        mid_salary_5y=SalaryBand(low=7000, mid=8000, high=9000),
        ceil_salary_15y=SalaryBand(low=10000, mid=12000, high=15000),
        stability=0.9, promotion_speed=PromotionSpeed.SLOW,
        establishment_type=EstablishmentType.ADMINISTRATIVE,
        related_majors=["法学", "公共管理"],
        source="公开报告", as_of=date(2024, 5, 1), confidence=0.5, note="待爬虫校准",
    )


def test_career_roundtrip():
    row = career_to_row(_career())
    assert row.entry_salary_mid == 5000
    assert json.loads(row.related_majors) == ["法学", "公共管理"]
    dom = career_to_domain(row)
    assert dom.entry_salary.high == 6000
    assert dom.related_majors == ["法学", "公共管理"]
    assert dom.source == "公开报告"
