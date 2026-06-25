"""职业市场快照层（P0-1/P0-2）。

核心纠正：JobMarket不挂在专业方向上，而是下沉到"职业×城市×学历×经验×时间"快照。
外语外贸方向下的日语翻译/对日外贸/跨境运营各有独立薪资缺口，不能共用一个。

关键设计：
- talent_gap(人才缺口)非人工事实字段，仅在可靠供需证据时填，否则留空
- demand_intensity(招聘需求强度)/posting_growth(招聘量变化)/competition_proxy(竞争代理)是可观测指标
- career_stage(朝阳/稳定/夕阳)是派生结论，由需求趋势+薪资趋势+行业产出+技术替代+供给变化推导
- 薪资按同城市同学历同经验分位归一，避免深圳软件工程vs河南教师直接比
- confidence参与决策（第3步实现向基准收缩）
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class CareerStage(str, Enum):
    """职业生命周期阶段（派生结论，非人工事实）。"""

    SUNRISE = "朝阳"  # 需求增长+薪资增长+行业扩张
    STABLE = "稳定"  # 需求平稳+薪资平稳
    SUNSET = "夕阳"  # 需求收缩或技术替代严重
    UNCERTAIN = "待定"  # 证据不足，不臆断


class EducationLevel(str, Enum):
    JUNIOR_COLLEGE = "专科"
    BACHELOR = "本科"
    MASTER = "硕士"


class ExperienceLevel(str, Enum):
    FRESH = "应届"  # 应届/0经验
    JUNIOR = "1-3年"
    MID = "3-5年"
    SENIOR = "5年以上"


class JobMarketSnapshot(BaseModel):
    """职业市场快照：某职业在某城市某学历某经验层的招聘数据。

    这是JobMarket的最小可观测单元。专业方向的市场分由关联职业加权聚合。
    所有字段带 source/as_of/sample_size/confidence，支持证据等级判定。
    """

    career_id: str  # 职业标识，关联 Career.name
    city: str | None = None  # 城市，None=全国/全省汇总
    education_level: EducationLevel = EducationLevel.BACHELOR
    experience_level: ExperienceLevel = ExperienceLevel.FRESH
    as_of: date

    # 可观测招聘指标（招聘网站可抓）
    posting_count: int | None = None  # 有效招聘岗位数
    salary_p25: int  # 薪资三分位（月，元）
    salary_p50: int
    salary_p75: int
    demand_intensity: float | None = None  # 招聘需求强度(0-1，规模修正后)
    posting_growth: float | None = None  # 招聘量同比变化(负=收缩)
    competition_proxy: float | None = None  # 竞争代理(投递/岗位比，高=竞争激烈)

    # 仅在有可靠供需证据时填写
    saturation_index: float | None = None  # 饱和度(0=紧缺 1=饱和)，无证据留空

    # 派生结论（由需求+薪资+趋势推导，非人工硬编码）
    career_stage: CareerStage = CareerStage.UNCERTAIN

    # 证据与溯源
    source: str
    sample_size: int | None = None
    confidence: float  # 0-1
    note: str | None = None


class MajorDirection(BaseModel):
    """专业方向（Level1）：聚合多个具体专业(Level2)和关联职业。

    市场分由关联职业的JobMarketSnapshot加权聚合，非方向级硬编码。
    """

    name: str  # 方向名，如"外语外贸""计算机""师范"
    description: str
    majors: list[str]  # 关联具体专业(Level2)，如["日语","商务英语","翻译","国际经济与贸易"]
    # 职业→权重映射（该方向下各职业的市场贡献占比，和≈1.0）
    career_weights: dict[str, float]  # {"对日外贸业务员": 0.35, "跨境电商运营": 0.25, ...}


class MarketScores(BaseModel):
    """市场双分（第1步归一输出）：当前就业吸引力 + 长期趋势。

    拆开避免"当前好找工作"和"长期朝阳"混成一个分数。
    """

    current_market_score: float  # 0-1，当前就业吸引力
    future_outlook_score: float  # 0-1，长期趋势
    career_stage: CareerStage
    salary_index: float  # 0-1，薪资分位（同城市同学历同经验归一）
    demand_index: float  # 0-1，需求强度
    growth_index: float  # 0-1，增长趋势
    evidence_level: str  # A/B/C/D 证据等级
    breakdown_note: str  # 各维度来源说明
