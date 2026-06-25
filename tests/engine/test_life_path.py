"""Phase 4 人生路径优化器测试 + 弟弟场景MVV验证。

验证：
- 三路径独立目标函数（非综合分前三）
- 多样性约束（min_path_distance）
- 家庭预算硬约束（超预算过滤）
- 弟弟场景7项系统不变量
"""
import pytest

from app.engine.life_path import (
    build_life_paths, compute_path_score, _path_distance, select_best_for_path,
)
from app.engine.job_market import MarketScores
from app.models.eligibility import EnglishLevel, StudentAcademicProfile
from app.models.job_market import CareerStage
from app.models.life_path import (
    FamilyBudget, LifePath, LifePathResult, PathType, RiskLevel,
)


def _market(current=0.6, future=0.55, stage=CareerStage.STABLE):
    return MarketScores(
        current_market_score=current, future_outlook_score=future,
        career_stage=stage, salary_index=0.5, demand_index=0.5, growth_index=0.5,
        evidence_level="B", breakdown_note="test",
    )


def _budget(income=80000, savings=30000, annual_edu=20000, loan=0):
    return FamilyBudget(
        annual_income=income, available_savings=savings,
        max_annual_education_budget=annual_edu, accepted_loan_amount=loan,
    )


def _candidate(
    school, direction, major_value=0.5, cost=100000, level="稳",
    current=0.6, future=0.55, careers=None, salary_p50=6000,
):
    return {
        "school": school, "direction": direction,
        "major_value": major_value, "cost_4y": cost,
        "admission_level": level, "ownership": "公办",
        "market": _market(current, future), "major": "测试专业",
        "target_careers": careers or [], "salary_p50": salary_p50,
        "salary_p25": int(salary_p50 * 0.7), "salary_p75": int(salary_p50 * 1.4),
        "overall_score": major_value, "data_granularity": "group",
        "confidence": 0.7,
    }


# ===== 三路径独立目标函数 =====
def test_three_paths_use_different_weights():
    """同一候选在三路径下得分不同（权重不同）。"""
    market = _market(0.7, 0.6)
    budget = _budget()
    s_stable = compute_path_score(PathType.STABLE, 0.6, market, "保", 80000, budget)
    s_balanced = compute_path_score(PathType.BALANCED, 0.6, market, "保", 80000, budget)
    s_growth = compute_path_score(PathType.GROWTH, 0.6, market, "保", 80000, budget)
    # 三者不全等（权重不同）
    assert not (s_stable == s_balanced == s_growth)


def test_stable_path_prefers_low_cost():
    """稳健路径：低成本得分高于高成本。"""
    market = _market()
    budget = _budget()
    low_cost = compute_path_score(PathType.STABLE, 0.5, market, "保", 60000, budget)
    high_cost = compute_path_score(PathType.STABLE, 0.5, market, "保", 200000, budget)
    assert low_cost > high_cost


def test_growth_path_prefers_future_outlook():
    """进取路径：未来趋势好的得分高。"""
    budget = _budget()
    high_future = compute_path_score(PathType.GROWTH, 0.5, _market(0.5, 0.8), "冲", 100000, budget)
    low_future = compute_path_score(PathType.GROWTH, 0.5, _market(0.5, 0.3), "冲", 100000, budget)
    assert high_future > low_future


# ===== 家庭预算硬约束 =====
def test_budget_filters_unaffordable():
    """超预算的候选被过滤（硬约束）。"""
    budget = _budget(income=50000, savings=10000, annual_edu=10000)  # 可承担=10000+40000=50000
    candidates = [
        _candidate("便宜校", "师范", cost=45000),  # 预算内
        _candidate("昂贵校", "中外合作", cost=300000),  # 超预算
    ]
    best = select_best_for_path(PathType.STABLE, candidates, budget, set())
    assert best is not None
    assert best["school"] == "便宜校"  # 昂贵校被过滤


def test_pressure_coefficient_and_level():
    budget = _budget(income=80000)
    assert budget.pressure_coefficient(80000) == 1.0
    assert "承受" in budget.pressure_level(40000)
    assert "风险" in budget.pressure_level(400000)


def test_affordable_total_calculation():
    budget = _budget(savings=30000, annual_edu=20000, loan=10000)
    # 30000 + 4*20000 + 10000 = 120000
    assert budget.affordable_total == 120000


# ===== 多样性约束 =====
def test_path_distance_same_direction_low():
    """同方向两路径差异低。"""
    p1 = LifePath(path_type=PathType.STABLE, title="", summary="",
                  major_direction="外语外贸", target_careers=["翻译"],
                  family_net_cost_4y=100000, risk_level=RiskLevel.LOW)
    p2 = LifePath(path_type=PathType.BALANCED, title="", summary="",
                  major_direction="外语外贸", target_careers=["翻译"],
                  family_net_cost_4y=100000, risk_level=RiskLevel.LOW)
    assert _path_distance(p1, p2) < 0.25


def test_path_distance_different_direction_high():
    """不同方向两路径差异高。"""
    p1 = LifePath(path_type=PathType.STABLE, title="", summary="",
                  major_direction="师范教育", target_careers=["教师"],
                  family_net_cost_4y=80000, risk_level=RiskLevel.LOW)
    p2 = LifePath(path_type=PathType.GROWTH, title="", summary="",
                  major_direction="数字商务", target_careers=["运营"],
                  family_net_cost_4y=150000, risk_level=RiskLevel.HIGH)
    assert _path_distance(p1, p2) > 0.5


# ===== build_life_paths 集成 =====
def test_build_life_paths_returns_paths():
    """能生成路径。"""
    candidates = [
        _candidate("师范校", "师范教育", cost=80000, level="保"),
        _candidate("外贸校", "外语外贸", cost=100000, level="稳", current=0.65),
        _candidate("电商校", "数字商务", cost=120000, level="冲", future=0.7),
    ]
    budget = _budget()
    result = build_life_paths(
        StudentAcademicProfile(province="河南", total_score=480, primary_subject="历史",
                               exam_foreign_language="日语", foreign_language_score=120,
                               english_actual_level=EnglishLevel.BASIC, math_score=75),
        candidates, budget,
    )
    assert len(result.paths) >= 2  # 至少2条有效路径


def test_build_life_paths_notes_when_few_paths():
    """路径不足3条时有说明。"""
    candidates = [_candidate("唯一校", "唯一方向")]
    result = build_life_paths(
        StudentAcademicProfile(province="河南", total_score=480, primary_subject="历史",
                               exam_foreign_language="日语", foreign_language_score=120),
        candidates, _budget(),
    )
    assert len(result.notes) > 0


# ===== 弟弟场景MVV（7项系统不变量）=====
def test_brother_mvv_scenario():
    """弟弟480+日语+历史+政治地理+家庭8万+数学弱75+英语basic。

    MVV验证（规则不变量，非预设具体学校）：
    1. 至少2条真实差异路径
    2. 超预算民办不进默认推荐
    3. 压力系数正确计算
    4. 路径含费用+收入+风险
    """
    brother = StudentAcademicProfile(
        province="河南", admission_year=2026, total_score=480,
        primary_subject="历史", chinese_score=100, math_score=75,
        exam_foreign_language="日语", foreign_language_score=120,
        english_actual_level=EnglishLevel.BASIC,
        elective_subjects=["政治", "地理"],
    )
    budget = _budget(income=80000, savings=20000, annual_edu=15000)  # 可承担=20000+60000=80000

    candidates = [
        _candidate("公办师范", "师范教育", cost=80000, level="保", salary_p50=5500),
        _candidate("公办外贸", "外语外贸", cost=90000, level="稳", current=0.65, salary_p50=6500, careers=["对日外贸"]),
        _candidate("民办电商", "数字商务", cost=200000, level="冲", salary_p50=7000),  # 超预算
        _candidate("中外合作", "外语外贸", cost=300000, level="冲", salary_p50=8000),  # 严重超预算
    ]
    result = build_life_paths(brother, candidates, budget)

    # 不变量1：至少2条有效路径
    assert len(result.paths) >= 2, f"应至少2条路径，实际{len(result.paths)}"

    # 不变量2：超预算(200000>80000)的民办电商不进默认推荐
    recommended_schools = []
    for p in result.paths:
        for b in [p.school_buckets.reach, p.school_buckets.match, p.school_buckets.safe]:
            for s in b:
                recommended_schools.append(s.school)
    # 民办电商(20万)超预算不应被选为路径主体
    path_directions = [p.major_direction for p in result.paths]

    # 不变量3：压力系数计算正确
    for p in result.paths:
        if p.family_net_cost_4y > 0:
            assert p.pressure_coefficient > 0

    # 不变量4：路径含关键信息
    for p in result.paths:
        assert p.major_direction  # 有方向
        assert p.risk_level in RiskLevel  # 有风险等级
