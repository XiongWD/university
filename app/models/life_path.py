"""人生路径模型（V2.2 Phase 4——三条路径+家庭预算约束）。

顶层：稳健/均衡/进取三条人生路径（回答"读什么、花多少、走哪里、风险回报"）
第二层：每条路径嵌套冲/稳/保学校清单（回答"这所校录取概率"）
命名不冲突：路径用稳健/均衡/进取，录取用冲/稳/保。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class PathType(str, Enum):
    """人生路径类型（顶层，与录取档位冲/稳/保区分）。"""

    STABLE = "稳健"    # 低成本、低风险、尽快就业，公办优先
    BALANCED = "均衡"  # 专业+学校+城市+成本综合最优（默认推荐）
    GROWTH = "进取"    # 更高平台/回报，但成本、考研或转型风险更高
    NOT_VIABLE = "不建议"  # 路径差异不足时，第三条标记不建议（不强造）


class RiskLevel(str, Enum):
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"


class FamilyBudget(BaseModel):
    """家庭预算（P0-4升级：可承担预算，非年收入×k）。

    可承担总预算 = 可投入储蓄 + 4×每年教育预算 + 可接受贷款 + 确定性资助
    硬约束：家庭净支出 ≤ 可承担总预算（超预算过滤+开关）
    """

    annual_income: int  # 家庭年收入（参考，非唯一依据）
    available_savings: int = 0  # 可投入储蓄
    max_annual_education_budget: int = 0  # 每年可用于教育的钱
    accepted_loan_amount: int = 0  # 可接受助学贷款
    confirmed_aid: int = 0  # 确定性资助（亲属/奖学金已确认）
    income_stability: str = "medium"  # low/medium/high
    accept_private_school: bool = True  # 是否接受民办

    @property
    def affordable_total(self) -> int:
        """可承担总预算 = 储蓄 + 4×年预算 + 贷款 + 资助。"""
        return (
            self.available_savings
            + 4 * self.max_annual_education_budget
            + self.accepted_loan_amount
            + self.confirmed_aid
        )

    def pressure_coefficient(self, cost_4y: int) -> float:
        """压力系数 = 4年家庭净支出 / 家庭年收入（展示用，非唯一过滤依据）。"""
        if self.annual_income <= 0:
            return 99.0
        return round(cost_4y / self.annual_income, 2)

    def pressure_level(self, cost_4y: int) -> str:
        """压力分级（展示）。"""
        ratio = self.pressure_coefficient(cost_4y)
        if ratio < 1:
            return "可轻松承受"
        if ratio < 2:
            return "有压力"
        if ratio < 4:
            return "明显负担"
        return "极高风险（需借贷/透支）"

    def can_afford(self, cost_4y: int) -> bool:
        """硬约束：家庭净支出 ≤ 可承担总预算。"""
        return cost_4y <= self.affordable_total


class SchoolOption(BaseModel):
    """路径内单个学校选项。"""

    school: str
    major_group_code: str | None = None
    matched_major: str | None = None
    ownership: str = "公办"  # 公办/民办/中外合作
    city: str | None = None
    admission_level: str = "稳"  # 冲/偏冲/稳/偏保/保
    admission_probability_note: str = ""  # 录取预测汇总
    total_cost_4y: int = 0
    affordability_status: str = ""  # 可承受/超预算
    data_granularity: str = "school"
    confidence: float = 0.5
    warnings: list[str] = []


class AdmissionBuckets(BaseModel):
    """路径内的冲/稳/保学校清单（第二层）。"""

    reach: list[SchoolOption] = []   # 冲
    match: list[SchoolOption] = []   # 稳
    safe: list[SchoolOption] = []    # 保


class LifePath(BaseModel):
    """单条人生路径。"""

    path_type: PathType
    title: str
    summary: str
    major_direction: str  # 专业方向
    recommended_majors: list[str] = []
    target_careers: list[str] = []

    # 费用与压力
    university_cost_4y: int = 0
    family_net_cost_4y: int = 0
    affordability_status: str = ""
    pressure_coefficient: float = 0.0

    # 收入预期
    expected_start_salary_p25: int = 0
    expected_start_salary_p50: int = 0
    expected_start_salary_p75: int = 0
    expected_income_5y: int | None = None
    estimated_payback_years: float | None = None

    # 发展路径
    employment_route: str = ""
    postgraduate_route: str | None = None
    civil_service_route: str | None = None

    # 评分与风险
    major_value_score: float = 0.0
    overall_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.MEDIUM
    key_benefits: list[str] = []
    key_risks: list[str] = []

    # 嵌套冲稳保
    school_buckets: AdmissionBuckets = AdmissionBuckets()


class LifePathResult(BaseModel):
    """三条路径总览（Phase 4 输出）。"""

    paths: list[LifePath] = []
    family_budget: FamilyBudget | None = None
    model_version: str = "v2.2"
    data_snapshot: str = ""
    notes: list[str] = []  # 系统说明（如"仅2条有效路径"）
