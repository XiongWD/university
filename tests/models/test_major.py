from datetime import date

import pytest
from pydantic import ValidationError

from app.models.major import Major, SalaryQuantile


def _kw(**over):
    base = dict(
        name="日语",
        category="文学",
        employment_density=dict(jobs=8000, frequency=0.6, city_coverage=0.4),
        salary=dict(p25=5500, p50=7500, p75=10000),
        barriers=dict(english=False, math=False, certificate=False, postgrad=False),
        upside=dict(management=True, freelance=True, cross_industry=True),
        source="BOSS直聘2024",
        as_of=date(2024, 4, 1),
        confidence=0.5,
        note="待爬虫校准",
    )
    base.update(over)
    return base


def test_major_legal():
    m = Major(**_kw())
    assert m.salary.p50 == 7500
    assert m.barriers.english is False


def test_missing_quantile_rejected():
    with pytest.raises(ValidationError):
        SalaryQuantile(p25=5500, p50=7500)  # 缺 p75


def test_no_average_field():
    with pytest.raises(ValidationError):
        Major(**_kw(salary={"avg": 7000}))  # 平均值字段，模型不接受
