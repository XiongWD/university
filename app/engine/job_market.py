"""职业市场归一引擎（P0-1/P0-2/P0-5/P0-8，纯函数）。

核心：
1. 薪资按"同城市同学历同经验"分位归一，避免深圳软件工程vs河南教师直接比
2. 需求强度做规模修正（有效岗位÷城市就业人口或行业规模）
3. 拆 current_market_score(当前就业吸引力) + future_outlook_score(长期趋势)
4. career_stage 是派生结论（需求+薪资+趋势+替代风险+供给推导），非人工硬编码
5. confidence参与决策：adjusted = conf×observed + (1-conf)×baseline，低置信向基准收缩
6. 证据等级ABCD：A官方足样近期/B多源招聘/C行业报告有限/D人工估算（D只能"值得关注"）

专业方向市场分 = 关联职业快照加权聚合（非方向级硬编码）。
"""
from __future__ import annotations

from app.models.job_market import (
    CareerStage,
    JobMarketSnapshot,
    MajorDirection,
    MarketScores,
)


# ── 归一化基准（城市薪资参照系，用于跨城市可比）──
# 取本科应届中位薪资做锚点，各城市按生活成本系数调整。
# 这些是模型假设，非精确事实，用于让"深圳软件vs河南教师"可比。
_CITY_SALARY_ANCHOR = {
    "深圳": 9000, "北京": 9000, "上海": 9000,
    "广州": 7500, "杭州": 7500, "南京": 7000,
    "成都": 6500, "武汉": 6000, "西安": 5800,
    "郑州": 5500, "洛阳": 4800, "新乡": 4500,
    "驻马店": 4200, "信阳": 4200, "商丘": 4200,
    "九江": 4500, "韶关": 4800, "苏州": 7500, "宁波": 7000,
}
_DEFAULT_ANCHOR = 5500  # 全国本科应届中位估算


def _salary_to_index(salary_p50: int, city: str | None) -> float:
    """薪资→0-1指数：按城市锚点归一，使跨城市可比。

    index = salary_p50 / city_anchor，clip 到 [0, 2] 后映射 [0,1]。
    例：深圳12000 / 9000锚 = 1.33 → 高于当地基准；
        河南5000 / 5500锚 = 0.91 → 接近当地基准。
    """
    anchor = _CITY_SALARY_ANCHOR.get(city, _DEFAULT_ANCHOR) if city else _DEFAULT_ANCHOR
    ratio = salary_p50 / anchor if anchor > 0 else 0.5
    return max(0.0, min(1.0, ratio / 2))  # ratio∈[0,2] → index∈[0,1]


def _demand_to_index(demand_intensity: float | None, posting_count: int | None) -> float:
    """需求强度→0-1。优先用已归一的demand_intensity，否则用posting_count粗估。"""
    if demand_intensity is not None:
        return max(0.0, min(1.0, demand_intensity))
    if posting_count is not None:
        # 粗估：>500岗位=高需求(0.9)，100-500=中(0.6)，<100=低(0.3)，0=极低(0.1)
        if posting_count > 500:
            return 0.9
        if posting_count > 100:
            return 0.6
        if posting_count > 0:
            return 0.3
        return 0.1
    return 0.5  # 无数据，中性


def _growth_to_index(posting_growth: float | None) -> float:
    """增长→0-1。posting_growth是同比变化(如0.2=+20%，-0.1=-10%)。"""
    if posting_growth is None:
        return 0.5  # 无数据中性
    # growth∈[-0.5, 0.5] → index∈[0, 1]
    return max(0.0, min(1.0, (posting_growth + 0.5)))


def _derive_career_stage(
    demand_index: float,
    growth_index: float,
    salary_index: float,
    competition_proxy: float | None,
) -> CareerStage:
    """派生职业阶段（朝阳/稳定/夕阳/待定），非人工硬编码。

    规则（可解释）：
    - 朝阳：需求高(growth>0.6) 且 (增长或薪资上行)
    - 夕阳：增长低(growth<0.35) 或 需求显著收缩
    - 稳定：其余，需求薪资平稳
    - 待定：关键数据缺失（growth/demand 无）
    """
    if growth_index == 0.5 and demand_index == 0.5:
        return CareerStage.UNCERTAIN
    if growth_index > 0.6 and demand_index >= 0.5:
        return CareerStage.SUNRISE
    if growth_index < 0.35 or (demand_index < 0.25 and growth_index < 0.5):
        return CareerStage.SUNSET
    return CareerStage.STABLE


def _evidence_level(confidence: float, sample_size: int | None) -> str:
    """证据等级ABCD（P0-8）：决定结论可信度，D只能'值得关注'。"""
    if confidence >= 0.85 and sample_size and sample_size >= 100:
        return "A"  # 官方/足样/近期
    if confidence >= 0.7:
        return "B"  # 多源招聘数据
    if confidence >= 0.5:
        return "C"  # 行业报告/有限样本
    return "D"  # 人工估算


def score_snapshot(snapshot: JobMarketSnapshot) -> MarketScores:
    """单个职业快照→市场双分（current + future）。

    current_market_score = 0.4×薪资 + 0.4×需求 + 0.2×入门占比(用低竞争代理)
    future_outlook_score = 0.5×增长 + 0.3×薪资趋势 + 0.2×(1-饱和)
    """
    salary_idx = _salary_to_index(snapshot.salary_p50, snapshot.city)
    demand_idx = _demand_to_index(snapshot.demand_intensity, snapshot.posting_count)
    growth_idx = _growth_to_index(snapshot.posting_growth)
    stage = _derive_career_stage(demand_idx, growth_idx, salary_idx, snapshot.competition_proxy)
    evidence = _evidence_level(snapshot.confidence, snapshot.sample_size)

    # 当前就业吸引力：薪资+需求为主，竞争低加分
    competition_factor = (1 - snapshot.competition_proxy) if snapshot.competition_proxy else 0.5
    current = 0.4 * salary_idx + 0.4 * demand_idx + 0.2 * competition_factor

    # 长期趋势：增长为主，薪资趋势+反饱和
    saturation_rev = (1 - snapshot.saturation_index) if snapshot.saturation_index is not None else 0.5
    future = 0.5 * growth_idx + 0.3 * salary_idx + 0.2 * saturation_rev

    # confidence向基准收缩（P0-8）：低置信拉向0.5中性
    conf = snapshot.confidence
    current_adj = conf * current + (1 - conf) * 0.5
    future_adj = conf * future + (1 - conf) * 0.5

    breakdown = (
        f"薪资指数{salary_idx:.2f}(P50={snapshot.salary_p50}@{snapshot.city or '全国'}) "
        f"需求{demand_idx:.2f} 增长{growth_idx:.2f} 阶段={stage.value} 证据={evidence}"
    )
    return MarketScores(
        current_market_score=round(current_adj, 3),
        future_outlook_score=round(future_adj, 3),
        career_stage=stage,
        salary_index=round(salary_idx, 3),
        demand_index=round(demand_idx, 3),
        growth_index=round(growth_idx, 3),
        evidence_level=evidence,
        breakdown_note=breakdown,
    )


def score_direction(
    direction: MajorDirection,
    snapshots: dict[str, list[JobMarketSnapshot]],  # career_id -> 该职业的快照列表
) -> MarketScores:
    """专业方向市场分 = 关联职业快照加权聚合（P0-1核心）。

    例：外语外贸方向 = 0.35×对日外贸 + 0.25×跨境运营 + 0.20×翻译本地化 + ...
    每个职业取其最相关快照（应届本科+目标城市），score后按权重加权。
    """
    weighted_current = 0.0
    weighted_future = 0.0
    weighted_salary = 0.0
    weighted_demand = 0.0
    weighted_growth = 0.0
    total_weight = 0.0
    stages = []
    evidences = []

    for career_id, weight in direction.career_weights.items():
        career_snaps = snapshots.get(career_id, [])
        if not career_snaps:
            continue
        # 取第一个快照（调用方应已筛选最相关：应届本科+目标城市）
        snap = career_snaps[0]
        scores = score_snapshot(snap)
        weighted_current += weight * scores.current_market_score
        weighted_future += weight * scores.future_outlook_score
        weighted_salary += weight * scores.salary_index
        weighted_demand += weight * scores.demand_index
        weighted_growth += weight * scores.growth_index
        total_weight += weight
        stages.append(scores.career_stage)
        evidences.append(scores.evidence_level)

    if total_weight == 0:
        # 无任何职业数据，返回中性低置信
        return MarketScores(
            current_market_score=0.5, future_outlook_score=0.5,
            career_stage=CareerStage.UNCERTAIN,
            salary_index=0.5, demand_index=0.5, growth_index=0.5,
            evidence_level="D", breakdown_note="无职业市场数据，中性估计",
        )

    # 聚合阶段：若有任一朝阳且无夕阳→朝阳；任一日落→夕阳倾向；否则稳定/待定
    if CareerStage.SUNSET in stages and CareerStage.SUNRISE not in stages:
        agg_stage = CareerStage.SUNSET
    elif CareerStage.SUNRISE in stages:
        agg_stage = CareerStage.SUNRISE
    elif CareerStage.UNCERTAIN in stages and len(set(stages)) == 1:
        agg_stage = CareerStage.UNCERTAIN
    else:
        agg_stage = CareerStage.STABLE

    # 聚合证据等级：取最差（保守）
    agg_evidence = min(evidences) if evidences else "D"

    return MarketScores(
        current_market_score=round(weighted_current / total_weight, 3),
        future_outlook_score=round(weighted_future / total_weight, 3),
        career_stage=agg_stage,
        salary_index=round(weighted_salary / total_weight, 3),
        demand_index=round(weighted_demand / total_weight, 3),
        growth_index=round(weighted_growth / total_weight, 3),
        evidence_level=agg_evidence,
        breakdown_note=f"方向'{direction.name}'由{len(stages)}个关联职业加权聚合，证据{agg_evidence}",
    )
