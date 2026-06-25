from datetime import date

from app.models.insurance import SocialInsurance, NATIONAL_BASELINE_RATES
from app.engine.insurance import (
    progressive_tax,
    compute_total_labor_cost,
    compute_take_home_pay,
    TAX_BRACKETS_2024,
)

SI = SocialInsurance(
    city="全国基准",
    rates=NATIONAL_BASELINE_RATES,
    source="基准",
    as_of=date(2024, 1, 1),
    confidence=0.9,
)


def _employer_sum() -> float:
    return sum(rp["employer"] for rp in NATIONAL_BASELINE_RATES.model_dump().values())


def _employee_sum() -> float:
    return sum(rp["employee"] for rp in NATIONAL_BASELINE_RATES.model_dump().values())


def test_progressive_tax_low_bracket():
    # 2920 落 3% 档（≤3000），progressive_tax 返回精确 float
    assert progressive_tax(2920) == 2920 * 0.03


def test_progressive_tax_boundary_3000():
    # 边界 3000 归 3% 档
    assert progressive_tax(3000) == 90


def test_progressive_tax_high_bracket():
    # 21400 落 20% 档（速算扣除 1410）
    assert progressive_tax(21400) == round(21400 * 0.20 - 1410)


def test_progressive_tax_zero_or_negative():
    assert progressive_tax(0) == 0
    assert progressive_tax(-100) == 0


def test_total_labor_cost():
    assert compute_total_labor_cost(9000, SI) == round(9000 * (1 + _employer_sum()))


def test_take_home_pay_positive_and_matches_formula():
    th = compute_take_home_pay(9000, SI)
    personal = round(9000 * _employee_sum())
    taxable = 9000 - personal - 5000
    expected = 9000 - personal - progressive_tax(taxable)
    assert th > 0
    assert th == round(expected)


def test_take_home_pay_special_deduction():
    base = compute_take_home_pay(20000, SI)
    with_ded = compute_take_home_pay(20000, SI, special_deduction=2000)
    assert with_ded >= base  # 扣除更多，个税更低，到手更高


def test_seven_brackets_present():
    assert len(TAX_BRACKETS_2024) == 7
