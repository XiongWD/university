"""城市成本年化计算（纯函数）。

文档公式：年成本 = 12 × 月综合成本中位 + 学费 + 住宿费
月综合成本中位 = (monthly_total.low + monthly_total.high) / 2
"""

from app.models.city import CityCost
from app.models.base import CostBand


def compute_annual_cost(
    city_cost: CityCost,
    tuition: int,
    accommodation: int,
) -> CostBand:
    """计算大学生年成本区间。

    采用文档中位法：月综合成本中位（单点）×12 + 学费 + 住宿费。
    返回区间两端相等（中位法单值）。
    """
    mt = city_cost.monthly_total
    monthly_mid = (mt.low + mt.high) / 2
    value = round(12 * monthly_mid + tuition + accommodation)
    return CostBand(low=value, high=value)
