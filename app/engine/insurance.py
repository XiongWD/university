"""五险一金 + 个税计算引擎（纯函数，无 DB 依赖）。

文档给定公式：
    企业成本 = 工资 × (1 + 五险一金单位部分比例合计)
    到手工资 = 工资 - 个人五险一金 - 个税

个税使用 2024 年月度累进税率表，起征点 5000，7 档。
"""

from app.models.insurance import InsuranceRates, SocialInsurance

# 2024 个人所得税月度累进税率表：(应纳税所得额上限, 税率, 速算扣除数)
TAX_BRACKETS_2024 = [
    (3000, 0.03, 0),
    (12000, 0.10, 210),
    (25000, 0.20, 1410),
    (35000, 0.25, 2660),
    (55000, 0.30, 4410),
    (80000, 0.35, 7160),
    (float("inf"), 0.45, 15160),
]

TAX_THRESHOLD = 5000  # 月度起征点


def progressive_tax(taxable: float) -> float:
    """按 2024 累进表计算个税。应纳税所得额 ≤ 0 时返回 0。"""
    if taxable <= 0:
        return 0.0
    for upper, rate, quick_deduction in TAX_BRACKETS_2024:
        if taxable <= upper:
            return taxable * rate - quick_deduction
    raise RuntimeError("unreachable")  # 最后一档上限为 inf


def _employer_total(insurance: SocialInsurance) -> float:
    """单位缴纳比例合计（遍历六险种，避免硬编码字段名）。"""
    return sum(
        getattr(getattr(insurance.rates, k), "employer")
        for k in InsuranceRates.model_fields
    )


def _employee_total(insurance: SocialInsurance) -> float:
    """个人缴纳比例合计。"""
    return sum(
        getattr(getattr(insurance.rates, k), "employee")
        for k in InsuranceRates.model_fields
    )


def compute_total_labor_cost(salary: int, insurance: SocialInsurance) -> int:
    """企业总用工成本 = 工资 × (1 + 单位缴纳比例合计)。"""
    return round(salary * (1 + _employer_total(insurance)))


def compute_take_home_pay(
    salary: int,
    insurance: SocialInsurance,
    special_deduction: int = 0,
) -> int:
    """到手工资 = 工资 - 个人五险一金 - 个税。

    应纳税所得额 = 工资 - 个人五险一金 - 起征点 5000 - 专项附加扣除。
    """
    personal = salary * _employee_total(insurance)
    taxable = salary - personal - TAX_THRESHOLD - special_deduction
    tax = progressive_tax(taxable)
    return round(salary - personal - tax)
