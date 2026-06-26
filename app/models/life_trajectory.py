# DEPRECATED: 旧版志愿集成模型，见 volunteer-recommendation-refocus；本模型保留字段以维持 deprecated 端点序列化，主链路不再填充 payback
"""志愿推荐集成模型：志愿 + 费用 + 就业参考（历史名 life_trajectory）。

本模型承载冲稳保志愿的附加信息。历史兼容字段保留为遗留序列化用途，主链路不再生成。
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


# DEPRECATED: 旧版教育收益分析模型，主链路不再生成，仅遗留端点序列化保留
class PaybackAnalysis(BaseModel):
    """旧版教育收益分析（大学投入 vs 毕业收入）。"""

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
    batch: str = "本科批"  # 录取批次：本科批/本科一批/专科等
    degree_level: str = "本科"  # 学历层次：本科/专科
    last_year_rank: int
    last_year_score: int
    student_rank: int
    probability: float  # 录取概率
    cost: CostSummary | None  # 费用（无该校数据则空）
    career: CareerProspect | None  # 就业前景
    payback: PaybackAnalysis | None  # 回本分析


class LifeTrajectory(BaseModel):
    """志愿推荐结果：志愿表 + 每校费用/就业参考。"""

    student_score: int
    student_rank: int
    track: str
    data_year: int
    sprint: list[TrajectoryItem]
    stable: list[TrajectoryItem]
    safe: list[TrajectoryItem]
    source_note: str  # 数据来源与时效
