from datetime import date

import pytest
from pydantic import ValidationError

from app.models.university import University, UniversityTier


def _kw(**over):
    base = dict(
        name="郑州大学",
        province="河南",
        tier=UniversityTier.TIER_211,
        employment_ability=dict(
            campus_tier="省属重点+央企校招",
            avg_entry_salary=6500,
            employment_rate=0.92,
        ),
        disciplines=[{"name": "化学", "grade": "A"}, {"name": "材料", "grade": "B+"}],
        source="教育部第四轮学科评估",
        as_of=date(2017, 12, 28),
        confidence=0.9,
        note="第四轮评估数据",
    )
    base.update(over)
    return base


def test_university_legal():
    u = University(**_kw())
    assert u.tier == UniversityTier.TIER_211
    assert u.disciplines[0].grade == "A"


def test_bad_tier_rejected():
    with pytest.raises(ValidationError):
        University(**_kw(tier="C9"))


def test_low_confidence_doubtful_employment():
    u = University(**_kw(confidence=0.4, note="官方数据可能有水分"))
    assert u.confidence < 0.5
