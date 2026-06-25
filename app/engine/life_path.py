"""人生路径优化器（V2.2 Phase 4——三路径+多样性约束，纯函数）。

三条路径各有独立目标函数（非综合分前三名），加多样性约束（min_path_distance）。
路径差异不足时允许"两条有效+一个不建议"，不强造第三条。

目标函数=风险调整后综合效用（评审：非收入最大化）。
在 Eligibility 输出的合法集合 + 家庭预算约束下优化。
"""
from __future__ import annotations

from app.engine.eligibility import EligibilityResult, filter_eligible
from app.engine.job_market import MarketScores
from app.models.eligibility import AdmissionOfferingRule, StudentAcademicProfile
from app.models.life_path import (
    AdmissionBuckets, FamilyBudget, LifePath, LifePathResult, PathType, RiskLevel,
    SchoolOption,
)

# 三路径独立权重（评审要求，非综合分前三）
PATH_WEIGHTS = {
    PathType.STABLE: {  # 稳健：低成本高确定，公办优先
        "major_value": 0.30, "employment_certainty": 0.20, "admission_match": 0.20,
        "cost_value": 0.15, "school_resource": 0.15,
    },
    PathType.BALANCED: {  # 均衡：综合最优（默认推荐）
        "major_value": 0.40, "city_employment": 0.20, "school_quality": 0.10,
        "school_employment": 0.10, "admission_match": 0.10, "cost_value": 0.10,
    },
    PathType.GROWTH: {  # 进取：长期上限+平台
        "major_long_value": 0.35, "school_platform": 0.20, "city_opportunity": 0.15,
        "transition_potential": 0.15, "school_employment": 0.10, "cost_value": 0.05,
    },
}

MIN_PATH_DISTANCE = 0.25  # 路径最小差异（专业方向/职业/城市/成本/风险）


def _path_distance(p1: LifePath, p2: LifePath) -> float:
    """计算两路径差异（0=完全相同，1=完全不同）。

    差异维度：专业方向/目标职业/费用区间/风险等级。
    """
    diff = 0.0
    # 专业方向不同
    if p1.major_direction != p2.major_direction:
        diff += 0.3
    # 目标职业集合差异
    c1, c2 = set(p1.target_careers), set(p2.target_careers)
    if c1 and c2:
        jaccard = len(c1 & c2) / len(c1 | c2)
        diff += 0.25 * (1 - jaccard)
    elif c1 != c2:
        diff += 0.25
    # 费用区间差异（对数比）
    if p1.family_net_cost_4y > 0 and p2.family_net_cost_4y > 0:
        import math
        ratio = max(p1.family_net_cost_4y, p2.family_net_cost_4y) / min(p1.family_net_cost_4y, p2.family_net_cost_4y)
        diff += 0.2 * min(1.0, math.log(ratio) / 2)
    # 风险等级不同
    if p1.risk_level != p2.risk_level:
        diff += 0.25
    return min(1.0, diff)


def compute_path_score(
    path_type: PathType,
    major_value: float,
    market_scores: MarketScores,
    admission_level: str,
    cost_4y: int,
    budget: FamilyBudget | None,
    school_platform: float = 0.5,
) -> float:
    """计算某路径下某候选的综合效用分（0-1）。

    用路径独立权重，非统一公式。
    """
    w = PATH_WEIGHTS[path_type]
    # 各维度归一到0-1
    employment_certainty = market_scores.current_market_score
    admission_match = {"保": 1.0, "偏保": 0.85, "稳": 0.7, "偏冲": 0.45, "冲": 0.3, "不推荐": 0.1}.get(admission_level, 0.5)
    # 成本性：预算内且低成本→高分
    cost_value = 0.5
    if budget:
        if budget.can_afford(cost_4y):
            cost_value = 1.0 - min(0.5, cost_4y / max(budget.affordable_total, 1) * 0.5)
        else:
            cost_value = 0.1  # 超预算极低分

    if path_type == PathType.STABLE:
        return (
            w["major_value"] * major_value
            + w["employment_certainty"] * employment_certainty
            + w["admission_match"] * admission_match
            + w["cost_value"] * cost_value
            + w["school_resource"] * school_platform * 0.7  # 稳健不追求平台
        )
    if path_type == PathType.BALANCED:
        return (
            w["major_value"] * major_value
            + w["city_employment"] * employment_certainty
            + w["school_quality"] * school_platform
            + w["school_employment"] * market_scores.current_market_score * 0.8
            + w["admission_match"] * admission_match
            + w["cost_value"] * cost_value
        )
    # GROWTH
    long_value = market_scores.future_outlook_score  # 进取看长期
    return (
        w["major_long_value"] * long_value
        + w["school_platform"] * school_platform
        + w["city_opportunity"] * employment_certainty
        + w["transition_potential"] * market_scores.future_outlook_score * 0.7
        + w["school_employment"] * market_scores.current_market_score * 0.6
        + w["cost_value"] * cost_value
    )


def select_best_for_path(
    path_type: PathType,
    candidates: list[dict],  # [{offering, eligibility, major_value, market, admission_level, cost_4y, school, ...}]
    budget: FamilyBudget | None,
    already_selected_directions: set[str],
) -> dict | None:
    """为某路径选最优候选（考虑多样性：已选方向降权）。"""
    if not candidates:
        return None
    scored = []
    for c in candidates:
        # 预算硬约束：超预算的默认不选（除非进取路径且用户接受）
        if budget and not budget.can_afford(c.get("cost_4y", 0)):
            if not (path_type == PathType.GROWTH and budget.accept_private_school):
                continue  # 超预算跳过
        base_score = compute_path_score(
            path_type, c["major_value"], c["market"], c["admission_level"],
            c.get("cost_4y", 0), budget, c.get("school_platform", 0.5),
        )
        # 多样性：已选方向降权
        direction = c.get("direction", "")
        if direction in already_selected_directions:
            base_score *= 0.6  # 同方向降权，鼓励差异化
        scored.append((base_score, c))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def build_life_paths(
    student: StudentAcademicProfile,
    candidates: list[dict],  # 已过Eligibility+有市场分+有录取预测+有费用的候选
    budget: FamilyBudget | None,
) -> LifePathResult:
    """构建三条人生路径（Phase 4 主入口）。

    candidates 每项含：offering, eligibility, major_value, market, admission_level,
    cost_4y, school, direction, target_careers, salary_p25/p50/p75 等。
    """
    paths: list[LifePath] = []
    selected_directions: set[str] = set()
    notes: list[str] = []

    for path_type in [PathType.STABLE, PathType.BALANCED, PathType.GROWTH]:
        best = select_best_for_path(path_type, candidates, budget, selected_directions)
        if best is None:
            notes.append(f"{path_type.value}路径无合格候选（可能因预算约束或数据不足）")
            continue
        selected_directions.add(best.get("direction", ""))

        cost_4y = best.get("cost_4y", 0)
        affordability = ""
        pressure = 0.0
        if budget:
            affordability = "可承受" if budget.can_afford(cost_4y) else "超预算"
            pressure = budget.pressure_coefficient(cost_4y)

        risk = RiskLevel.LOW
        if path_type == PathType.GROWTH:
            risk = RiskLevel.HIGH
        elif path_type == PathType.BALANCED:
            risk = RiskLevel.MEDIUM
        if pressure > 2:
            risk = RiskLevel.HIGH

        # 构建冲稳保（简化：用候选列表按admission_level分桶）
        buckets = _build_buckets(candidates, budget, best.get("direction", ""))

        path = LifePath(
            path_type=path_type,
            title=f"{path_type.value}路径·{best.get('direction', '')}",
            summary=best.get("summary", ""),
            major_direction=best.get("direction", ""),
            recommended_majors=best.get("majors", []),
            target_careers=best.get("target_careers", []),
            university_cost_4y=cost_4y,
            family_net_cost_4y=cost_4y,
            affordability_status=affordability,
            pressure_coefficient=pressure,
            expected_start_salary_p25=best.get("salary_p25", 0),
            expected_start_salary_p50=best.get("salary_p50", 0),
            expected_start_salary_p75=best.get("salary_p75", 0),
            major_value_score=round(best.get("major_value", 0), 3),
            overall_score=round(best.get("overall_score", best.get("major_value", 0)), 3),
            risk_level=risk,
            key_benefits=best.get("benefits", []),
            key_risks=best.get("risks", []),
            school_buckets=buckets,
        )
        paths.append(path)

    # 多样性约束检查
    if len(paths) >= 2:
        d01 = _path_distance(paths[0], paths[1])
        if d01 < MIN_PATH_DISTANCE:
            notes.append(f"前两条路径差异不足({d01:.2f}<{MIN_PATH_DISTANCE})，建议仅参考差异较大的路径")

    # 所有路径同方向→说明缺乏多样性
    if paths and len(set(p.major_direction for p in paths)) == 1:
        notes.append(f"全部{len(paths)}条路径集中于'{paths[0].major_direction}'方向，缺乏专业方向多样性")

    if len(paths) < 3:
        notes.append(f"仅生成{len(paths)}条有效路径（路径差异/数据/预算约束导致）")

    return LifePathResult(paths=paths, family_budget=budget, notes=notes)


def _build_buckets(
    candidates: list[dict], budget: FamilyBudget | None, direction: str
) -> AdmissionBuckets:
    """为某路径构建冲/稳/保学校清单，每个学校带填报专家建议。"""
    from app.engine.filling_rules import generate_filling_advice
    reach, match, safe = [], [], []
    for c in candidates:
        if c.get("direction", "") != direction:
            continue
        cost = c.get("cost_4y", 0)
        afford = "可承受" if (not budget or budget.can_afford(cost)) else "超预算"
        school_province = c.get("school_province", "河南")
        level = c.get("admission_level", "稳")
        # 生成填报专家建议（8大规则）
        advice = generate_filling_advice(
            school=c.get("school", ""),
            school_province=school_province,
            planned_enrollment=c.get("planned_enrollment"),
            admission_level=level,
        )
        opt = SchoolOption(
            school=c.get("school", ""),
            matched_major=c.get("major", ""),
            ownership=c.get("ownership", "公办"),
            city=c.get("city"),
            admission_level=level,
            total_cost_4y=cost,
            affordability_status=afford,
            data_granularity=c.get("data_granularity", "school"),
            confidence=c.get("confidence", 0.5),
            warnings=advice,
        )
        if level in ("冲", "偏冲"):
            reach.append(opt)
        elif level in ("偏保", "保"):
            safe.append(opt)
        else:
            match.append(opt)
    return AdmissionBuckets(reach=reach[:5], match=match[:8], safe=safe[:5])
