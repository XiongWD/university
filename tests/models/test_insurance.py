from datetime import date

import pytest
from pydantic import ValidationError

from app.models.insurance import (
    SocialInsurance, InsuranceRates, RatePair, NATIONAL_BASELINE_RATES,
)


def test_rate_pair_legal():
    rp = RatePair(employee=0.08, employer=0.16)
    assert rp.employer == 0.16


def test_rate_out_of_range_rejected():
    with pytest.raises(ValidationError):
        RatePair(employee=1.5, employer=0.1)


def test_social_insurance_legal():
    si = SocialInsurance(
        city="深圳", rates=NATIONAL_BASELINE_RATES,
        source="人社局2024", as_of=date(2024, 1, 1),
        confidence=0.85, note=None,
    )
    assert si.rates.pension.employer == 0.16


def test_national_baseline_employer_sum_reasonable():
    rates = NATIONAL_BASELINE_RATES.model_dump().values()
    s = sum(rp["employer"] for rp in rates)
    assert 0.2 < s < 0.6
