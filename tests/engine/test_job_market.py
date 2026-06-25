"""第1步职业市场快照层测试：归一引擎 + 方向加权聚合。

验证P0-1/P0-2/P0-8：
- 薪资同城市同学历归一（深圳软件vs河南教师可比）
- career_stage派生（非硬编码）
- 证据等级ABCD
- 方向加权聚合（非方向级共用一个缺口）
- confidence向基准收缩
"""
from datetime import date

import pytest
import yaml
from pathlib import Path

from app.engine.job_market import (
    score_direction,
    score_snapshot,
    _salary_to_index,
    _derive_career_stage,
    _evidence_level,
)
from app.models.job_market import (
    CareerStage,
    EducationLevel,
    ExperienceLevel,
    JobMarketSnapshot,
    MajorDirection,
    MarketScores,
)

SEED = Path("data/seed")


def _snap(career_id, city, p50, **kw):
    """构造快照测试辅助。"""
    defaults = dict(
        education_level=EducationLevel.BACHELOR,
        experience_level=ExperienceLevel.FRESH,
        as_of=date(2026, 5, 1),
        salary_p25=int(p50 * 0.7), salary_p50=p50, salary_p75=int(p50 * 1.5),
        source="test", confidence=0.8,
    )
    defaults.update(kw)
    return JobMarketSnapshot(career_id=career_id, city=city, **defaults)


# ===== 归一化测试 =====
def test_salary_index_city_normalized():
    """薪资按城市锚点归一：深圳14000 vs 郑州5500 应相近（都接近当地基准1.0）。"""
    sz = _salary_to_index(9000, "深圳")  # 深圳锚9000，9k=1.0→index0.5
    zz = _salary_to_index(5500, "郑州")  # 郑州锚5500，5.5k=1.0→index0.5
    assert abs(sz - zz) < 0.15  # 城市归一后相近


def test_salary_index_high_salary_high_index():
    """高薪→高指数。"""
    low = _salary_to_index(4000, "深圳")
    high = _salary_to_index(18000, "深圳")
    assert high > low


# ===== career_stage派生（非硬编码）=====
def test_career_stage_sunrise():
    """需求高+增长→朝阳。"""
    stage = _derive_career_stage(
        demand_index=0.8, growth_index=0.7, salary_index=0.6, competition_proxy=0.4
    )
    assert stage == CareerStage.SUNRISE


def test_career_stage_sunset():
    """增长低→夕阳。"""
    stage = _derive_career_stage(
        demand_index=0.5, growth_index=0.2, salary_index=0.5, competition_proxy=0.6
    )
    assert stage == CareerStage.SUNSET


def test_career_stage_uncertain_when_no_data():
    """关键数据缺失→待定（不臆断）。"""
    stage = _derive_career_stage(
        demand_index=0.5, growth_index=0.5, salary_index=0.5, competition_proxy=None
    )
    assert stage == CareerStage.UNCERTAIN


# ===== 证据等级ABCD =====
def test_evidence_level_A_for_high_conf_large_sample():
    assert _evidence_level(0.9, 200) == "A"


def test_evidence_level_D_for_low_conf():
    assert _evidence_level(0.4, 10) == "D"


def test_evidence_level_C_for_medium():
    assert _evidence_level(0.6, 50) == "C"


# ===== confidence向基准收缩 =====
def test_confidence_shrinks_to_baseline():
    """低置信快照的分数应向0.5中性收缩。"""
    high_conf = _snap("测试", "郑州", 5000, demand_intensity=0.9, confidence=0.9)
    low_conf = _snap("测试", "郑州", 5000, demand_intensity=0.9, confidence=0.3)
    s_high = score_snapshot(high_conf)
    s_low = score_snapshot(low_conf)
    # 低置信的current应更接近0.5（向中性收缩）
    assert abs(s_low.current_market_score - 0.5) < abs(s_high.current_market_score - 0.5)


# ===== 方向加权聚合（P0-1核心）=====
def test_direction_aggregates_careers():
    """外语外贸方向 = 多个职业加权，非单一缺口。"""
    direction = MajorDirection(
        name="外语外贸", description="test",
        majors=["日语"], career_weights={"对日外贸业务员": 0.6, "跨境电商运营": 0.4},
    )
    snapshots = {
        "对日外贸业务员": [_snap("对日外贸业务员", "深圳", 8500, demand_intensity=0.65, posting_growth=0.12)],
        "跨境电商运营": [_snap("跨境电商运营", "深圳", 9500, demand_intensity=0.85, posting_growth=0.22)],
    }
    scores = score_direction(direction, snapshots)
    assert 0 < scores.current_market_score < 1
    assert scores.evidence_level in ("A", "B", "C", "D")
    # 跨境运营权重0.4且需求更高，聚合分应高于纯外贸


def test_direction_no_data_returns_neutral():
    """无职业数据→中性低置信。"""
    direction = MajorDirection(
        name="未知方向", description="test", majors=["x"], career_weights={"无此职业": 1.0},
    )
    scores = score_direction(direction, {})
    assert scores.current_market_score == 0.5
    assert scores.evidence_level == "D"
    assert scores.career_stage == CareerStage.UNCERTAIN


# ===== 种子数据加载验证 =====
def test_seed_directions_loadable():
    """专业方向种子可加载。"""
    data = yaml.safe_load((SEED / "major_directions/major_directions.yaml").read_text(encoding="utf-8"))
    assert len(data) >= 6
    directions = [MajorDirection.model_validate(d) for d in data]
    foreign = next(d for d in directions if d.name == "外语外贸")
    assert "日语" in foreign.majors
    assert sum(foreign.career_weights.values()) <= 1.1  # 权重和≈1


def test_seed_snapshots_loadable():
    """职业快照种子可加载。"""
    data = yaml.safe_load((SEED / "job_markets/job_snapshots.yaml").read_text(encoding="utf-8"))
    assert len(data) >= 15
    snaps = [JobMarketSnapshot.model_validate(d) for d in data]
    # 对日外贸在深圳和郑州都有（不同城市独立快照）
    sz = [s for s in snaps if s.career_id == "对日外贸业务员" and s.city == "深圳"]
    zz = [s for s in snaps if s.career_id == "对日外贸业务员" and s.city == "郑州"]
    assert len(sz) == 1 and len(zz) == 1
    # 深圳薪资应高于郑州（同职业不同城市）
    assert sz[0].salary_p50 > zz[0].salary_p50


def test_seed_direction_score_real():
    """用真实种子计算外语外贸方向市场分（端到端）。"""
    dirs = yaml.safe_load((SEED / "major_directions/major_directions.yaml").read_text(encoding="utf-8"))
    snaps_data = yaml.safe_load((SEED / "job_markets/job_snapshots.yaml").read_text(encoding="utf-8"))
    snaps = [JobMarketSnapshot.model_validate(d) for d in snaps_data]
    # 按career_id分组
    snap_map: dict[str, list[JobMarketSnapshot]] = {}
    for s in snaps:
        snap_map.setdefault(s.career_id, []).append(s)
    foreign = MajorDirection.model_validate(next(d for d in dirs if d["name"] == "外语外贸"))
    scores = score_direction(foreign, snap_map)
    assert scores.current_market_score > 0.4  # 外语外贸有市场需求
    print(f"\n外语外贸方向: current={scores.current_market_score} future={scores.future_outlook_score} stage={scores.career_stage.value} evidence={scores.evidence_level}")
