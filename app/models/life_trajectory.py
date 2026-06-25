"""人生轨迹模拟：把志愿推荐与大学费用、就业收入、回本周期串联。

核心问题：读这所大学（某专业）4年要花多少？毕业后能赚多少？多久回本？
家长和孩子在筛选志愿的那一刻，就能看到「投入产出」全貌。
"""
from pydantic import BaseModel


class CostSummary(BaseModel):
    """大学期间费用汇总。"""

    tuition_total: int  # N年学费合计
    accommodation_total: int  # N年住宿费合计
    living_total: int  # N年生活费合计
    grand_total: int  # N年总开销
    annual_total: int  # 年均
    years: int
    nature: str  # 公立/民办/中外合作
    city: str | None
    city_cost_source: str | None


class CareerProspect(BaseModel):
    """就业前景（基于专业/职业数据）。"""

    major_name: str | None
    entry_salary_low: int  # 起薪下限
    entry_salary_mid: int  # 起薪中位
    entry_salary_high: int  # 起薪上限
    mid_salary_5y: int | None  # 5年中位（若有职业匹配）
    ceil_salary_15y: int | None  # 15年上限
    stability: float | None  # 稳定性 0-1
    establishment_type: str | None  # 编制类型
    source: str  # 数据来源说明


class PaybackAnalysis(BaseModel):
    """回本分析：大学投入 vs 毕业收入。"""

    total_investment: int  # 大学总投入(费用)
    annual_income_after_grad: int  # 毕业后预期年收入(起薪中位×12)
    years_to_break_even: float | None  # 回本所需年数(投入/年收入)
    lifetime_15y_net: int  # 15年净收益(15年收入 - 大学投入)
    note: str  # 说明，如"回本快/慢"判断


class TrajectoryItem(BaseModel):
    """单条人生轨迹：一所学校 + 费用 + 就业 + 回本。"""

    strategy: str  # 冲/稳/保
    school: str
    major: str | None
    major_group: str | None
    subject_requirement: str | None
    last_year_rank: int
    last_year_score: int
    student_rank: int
    probability: float  # 录取概率
    cost: CostSummary | None  # 费用（无该校数据则空）
    career: CareerProspect | None  # 就业前景
    payback: PaybackAnalysis | None  # 回本分析


class LifeTrajectory(BaseModel):
    """完整人生轨迹：志愿表 + 每校费用/就业/回本。"""

    student_score: int
    student_rank: int
    track: str
    data_year: int
    sprint: list[TrajectoryItem]
    stable: list[TrajectoryItem]
    safe: list[TrajectoryItem]
    source_note: str  # 数据来源与时效
