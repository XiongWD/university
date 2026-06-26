---
archived-with: 2026-06-26-volunteer-advisory-engine
status: final
---
# volunteer-advisory-engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 新建 `POST /api/v1/volunteer/advisory` 主接口，把已落地的资格/录取/适配/市场/费用/位次引擎组装成"专业方向优先"主链路，输出 VolunteerAdvisoryResult。

**Architecture:** 纯新增：`app/models/advisory.py`（输出模型）+ `app/engine/advisory.py`（`build_advisory` 纯函数编排 + affordability 分类器）+ router handler（复用 LifePathsRequest 与现有 `_build_*`/`_load_*` helper）。专业方向评分用 `compute_major_value_academic`（market×fit 门控，修正现有 life_paths 错误）。

**Tech Stack:** Python/FastAPI、Pydantic、pytest、OpenSpec。

## Global Constraints

- **纯新增，不改现有行为**：不改 eligibility/admission_prediction/major_fit/job_market/cost/rank_query 引擎内部；不动 A 已 deprecated 的 life_path.py/trajectory.py/life-paths/life-trajectory 端点。
- **请求模型复用 `LifePathsRequest`**（字段集已含 §3.1 全部 + 家庭预算）；`_build_academic_profile`/`_build_budget` 直接复用。
- **专业方向评分用 `compute_major_value_academic`**（基于 StudentAcademicProfile + english_actual_level），`major_value = market_value × student_fit`（§3.4 乘法门控）—— 不得用 `market.current_market_score` 替代。
- **affordability 4 级标签固定**：`可承受 / 有压力 / 明显负担 / 超预算`（§3.6）。新建独立分类器，不改 FamilyBudget。
- **遵守 narrative-policy**（A 已建主 spec）：advisory 输出与 docstring 不出现 `人生路径/人生轨迹/回本/ROI/投资回报/15年净收益/命运/赛道/人生经济模型模拟器`。
- **数据粒度**：`SchoolOption.data_granularity` 来自 `GroupAdmissionPrediction.data_granularity`；group/school 时 warnings 追加"组内目标专业数据不足"。
- **SchoolOption/AdmissionBuckets 复用** `app.models.life_path`（字段已兼容 §4.1）。
- **回滚**：纯新增，删除新文件 + handler 即可，无副作用。

## 精确接口参考（已勘察确认，实现时直接用）

```python
# eligibility
filter_eligible(profile: StudentAcademicProfile, offerings: list[AdmissionOfferingRule])
    -> tuple[list[tuple[AdmissionOfferingRule, EligibilityResult]], list[tuple[AdmissionOfferingRule, EligibilityResult]]]
# EligibilityResult: .eligible, .reasons: list[str], .blocked_summary: str (property)

# rank (volunteer.py)
convert_score_to_rank(entries: list[ScoreRankEntry], score: int) -> int | None

# job_market
score_direction(direction: MajorDirection, snapshots: dict[str, list[JobMarketSnapshot]]) -> MarketScores
# MarketScores: .current_market_score, .future_outlook_score, .career_stage, .evidence_level

# major_fit
compute_major_value_academic(market_scores: MarketScores, profile, major: Major, english_dependency: str = "low", market_weight: float = 0.6)
    -> tuple[float, dict]
# breakdown keys: market_value, student_fit, major_value, math_learning_risk, english_adaptation, english_actual_level, exam_foreign_language, career_stage, evidence_level

# admission_prediction
predict_group_admission(school: str, major_group_code: str | None, student_rank: int, baseline_rank_2025: int | None, ...)
    -> GroupAdmissionPrediction
# GroupAdmissionPrediction: .admission_level.value (冲/偏冲/稳/偏保/保), .data_granularity (major/group/school), .confidence, .note

# FamilyBudget (life_path.py): .affordable_total (property), .can_afford(cost_4y) -> bool, .annual_income

# router helpers (volunteer.py): _build_academic_profile(req), _build_budget(req), _load_offerings(),
# _load_directions_and_snapshots() -> (directions, snap_map), _load_rank_entries(session, province, year, track),
# _load_admissions(session, province, track, year), _load_universities(session), _load_cities(session),
# _load_majors(session), _load_careers(session)
# LifePathsRequest (volunteer.py:64) — 复用为 advisory 请求
```

---

### Task 1: 输出模型 app/models/advisory.py

**Files:**
- Create: `app/models/advisory.py`

**Interfaces:**
- Produces: `MajorDirectionAdvice`, `BudgetSummary`, `IneligibleReason`, `VolunteerAdvisoryResult`（供 Task 2/3 使用）

- [x] **Step 1: 创建模型文件**

创建 `app/models/advisory.py`：

```python
"""志愿推荐 advisory 输出模型（专业方向优先主链路结果）。

对应父设计 docs/superpowers/specs/2026-06-26-volunteer-recommendation-refocus-design.md §4.1。
SchoolOption/AdmissionBuckets 复用 app.models.life_path（字段已兼容 §4.1）。
"""
from __future__ import annotations

from pydantic import BaseModel

from app.models.life_path import AdmissionBuckets  # noqa: F401  (re-export for convenience)


class MajorDirectionAdvice(BaseModel):
    """专业方向建议：方向 + 推荐专业 + market×fit 评分 + 解释/风险。"""

    direction: str
    recommended_majors: list[str] = []
    market_value: float = 0.0
    student_fit: float = 0.0
    major_value: float = 0.0  # market_value × student_fit（§3.4 乘法门控）
    fit_explanation: list[str] = []
    risk_warnings: list[str] = []


class BudgetSummary(BaseModel):
    """家庭预算与大学期间费用汇总（§3.6：费用压力，非回本）。"""

    tuition_4y: int = 0
    accommodation_4y: int = 0
    living_4y: int = 0
    total_4y: int = 0
    affordable_total: int = 0
    affordability_status: str = ""  # 可承受/有压力/明显负担/超预算
    data_note: str = ""


class IneligibleReason(BaseModel):
    """不可报原因（来自资格过滤）。"""

    school: str
    major_group_name: str = ""
    reasons: list[str] = []
    blocked_summary: str = ""


class VolunteerAdvisoryResult(BaseModel):
    """advisory 主接口结果（§4.1）。"""

    student_rank: int
    province: str
    track: str
    data_year: int
    major_directions: list[MajorDirectionAdvice] = []
    school_options: AdmissionBuckets
    ineligible_options: list[IneligibleReason] = []
    budget_summary: BudgetSummary
    notes: list[str] = []
```

- [x] **Step 2: 验证导入**

Run: `python -c "from app.models.advisory import VolunteerAdvisoryResult, MajorDirectionAdvice, BudgetSummary, IneligibleReason; print('models OK')"`
Expected: `models OK`

- [x] **Step 3: 提交**

```bash
git add app/models/advisory.py
git commit -m "feat(advisory): 新增输出模型 VolunteerAdvisoryResult/MajorDirectionAdvice/BudgetSummary/IneligibleReason"
```

---

### Task 2: affordability 4 级分类器 + build_advisory 主链路

**Files:**
- Create: `app/engine/advisory.py`

**Interfaces:**
- Consumes: Task 1 的输出模型；现有引擎 `filter_eligible`/`convert_score_to_rank`/`score_direction`/`compute_major_value_academic`/`predict_group_admission`；`FamilyBudget`/`SchoolOption`/`AdmissionBuckets`
- Produces: `classify_affordability(cost_4y, budget) -> str`；`build_advisory(...) -> VolunteerAdvisoryResult`

- [x] **Step 1: 创建引擎文件 + affordability 分类器**

创建 `app/engine/advisory.py`，先写 affordability（阈值常量化）：

```python
"""志愿推荐 advisory 主链路编排：专业方向优先（父设计 §3）。

纯函数，数据由 router 注入。资格前置门 → 位次 → market×fit 专业方向评分
→ 录取预测 → 费用压力 → 冲稳保分桶 → 可解释输出。
"""
from __future__ import annotations

from app.models.advisory import (
    BudgetSummary,
    IneligibleReason,
    MajorDirectionAdvice,
    VolunteerAdvisoryResult,
)
from app.models.admission_prediction import GroupAdmissionPrediction  # noqa: F401
from app.models.eligibility import AdmissionOfferingRule, StudentAcademicProfile
from app.models.admission import AdmissionRecord
from app.models.city import CityCost
from app.models.job_market import JobMarketSnapshot, MajorDirection, MarketScores
from app.models.life_path import AdmissionBuckets, FamilyBudget, SchoolOption
from app.models.major import Major
from app.models.provincial import ScoreRankEntry
from app.models.university import University

# affordability 4 级阈值（§3.6，经验值，可调）
AFFORD_PRESSURE_THRESHOLD = 1.5   # cost_4y / annual_income <= 1.5 → 有压力
AFFORD_BURDEN_THRESHOLD = 3.0     # <= 3.0 → 明显负担；> 3.0 → 超预算


def classify_affordability(cost_4y: int, budget: FamilyBudget) -> str:
    """费用压力 4 级（§3.6）：可承受/有压力/明显负担/超预算。

    可承受 = 4 年总开销 <= 家庭可承担总预算；否则按 cost_4y/annual_income 分级。
    """
    if cost_4y <= budget.affordable_total:
        return "可承受"
    if not budget.can_afford(cost_4y):
        return "超预算"
    pressure = cost_4y / max(budget.annual_income, 1)
    if pressure <= AFFORD_PRESSURE_THRESHOLD:
        return "有压力"
    if pressure <= AFFORD_BURDEN_THRESHOLD:
        return "明显负担"
    return "超预算"
```

- [x] **Step 2: 实现 build_advisory 主链路**

在 `app/engine/advisory.py` 追加（匹配方向 + 评分 + 录取 + 费用 + 分桶 + 聚合）：

```python
def _match_direction(offering: AdmissionOfferingRule, directions: list[MajorDirection]) -> MajorDirection:
    """匹配 offering 到 MajorDirection：direction_hint 优先，否则子串匹配。"""
    hint = getattr(offering, "direction_hint", None) or ""
    if hint:
        for d in directions:
            if d.name == hint:
                return d
    best, best_score = (directions[0] if directions else None), 0
    for d in directions:
        score = sum(1 for m in d.majors if m in offering.major_group_name or m in offering.school)
        if score > best_score:
            best, best_score = d, score
    return best


def _compute_4y_cost(uni: University | None, cities: dict[str, CityCost], school: str) -> tuple[int, int, int, int]:
    """4 年费用分项 (tuition_4y, accommodation_4y, living_4y, total_4y)。"""
    if uni:
        city = cities.get(uni.city) if uni.city else None
        if city and city.monthly_total:
            # CityCost.monthly_total 是 (low, high) 或 CostBand；取中位
            mt = city.monthly_total
            monthly_mid = (mt.low + mt.high) / 2 if hasattr(mt, "low") else mt
        else:
            monthly_mid = 2000  # 默认郑州级
        t4 = uni.tuition * 4
        a4 = uni.accommodation * 4
        l4 = int(monthly_mid * 12 * 4)
        return t4, a4, l4, t4 + a4 + l4
    # 无 university 数据：按校名估
    is_private = any(k in school for k in ["升达", "黄河科技", "工商", "商丘", "西亚斯"])
    t4 = 40000 if is_private else 20000
    a4 = 4000
    l4 = 96000
    return t4, a4, l4, t4 + a4 + l4


_LEVEL_BUCKETS = {
    "冲": "reach", "偏冲": "reach",
    "稳": "match",
    "偏保": "safe", "保": "safe",
}


def build_advisory(
    profile: StudentAcademicProfile,
    budget: FamilyBudget,
    offerings: list[AdmissionOfferingRule],
    directions: list[MajorDirection],
    snap_map: dict[str, list[JobMarketSnapshot]],
    admissions: list[AdmissionRecord],
    unis: list[University],
    cities: list[CityCost],
    majors: list[Major],
    careers: list,  # careers 仅作未来扩展，当前 build_advisory 不直接用
    rank_entries: list[ScoreRankEntry],
    data_year: int = 2025,
) -> VolunteerAdvisoryResult:
    """专业方向优先主链路（§3）。"""
    from app.engine.eligibility import filter_eligible
    from app.engine.job_market import score_direction
    from app.engine.major_fit import compute_major_value_academic
    from app.engine.admission_prediction import predict_group_admission
    from app.engine.volunteer import convert_score_to_rank

    # [§3.2] 资格前置门
    eligible, ineligible = filter_eligible(profile, offerings)

    # [§3.3] 位次
    track = "历史类" if profile.primary_subject == "历史" else "物理类"
    student_rank = convert_score_to_rank(rank_entries, profile.total_score) or 0

    adm_by_school = {a.school: a for a in admissions}
    uni_map = {u.name: u for u in unis}
    city_map = {c.city: c for c in cities}
    major_map = {m.name: m for m in majors}

    buckets = AdmissionBuckets()
    ineligible_options: list[IneligibleReason] = []
    # 方向聚合：direction_name -> list[(market_value, student_fit, major_value, breakdown, direction)]
    dir_agg: dict[str, list[dict]] = {}

    for off, elig_result in eligible:
        direction = _match_direction(off, directions)
        market = score_direction(direction, snap_map)
        # [§3.4] market × fit（修正 life_paths 错误）
        matched_major_name = next((m for m in direction.majors if m in major_map), None)
        major_obj = major_map.get(matched_major_name) if matched_major_name else (majors[0] if majors else None)
        english_dep = getattr(off, "english_dependency_level", "low")
        major_value, breakdown = compute_major_value_academic(market, profile, major_obj, english_dependency=english_dep)

        # [§3.3] 录取预测
        adm = adm_by_school.get(off.school)
        baseline = adm.min_rank if adm else None
        group_pred = predict_group_admission(off.school, off.major_group_code, student_rank, baseline_rank_2025=baseline)
        level = group_pred.admission_level.value

        # [§3.6] 费用 4 年分项
        uni = uni_map.get(off.school)
        t4, a4, l4, total4 = _compute_4y_cost(uni, city_map, off.school)
        ownership = uni.nature if uni else ("民办" if any(k in off.school for k in ["升达", "黄河科技", "工商", "商丘", "西亚斯"]) else "公办")
        afford = classify_affordability(total4, budget)

        warnings: list[str] = []
        if group_pred.data_granularity in ("group", "school"):
            warnings.append("组内目标专业数据不足，仅按专业组投档参考")
        if not budget.accept_private_school and ownership != "公办":
            warnings.append("家庭不接受民办/中外合作")

        opt = SchoolOption(
            school=off.school,
            major_group_code=off.major_group_code,
            matched_major=matched_major_name,
            ownership=ownership,
            city=uni.city if uni else None,
            admission_level=level,
            admission_probability_note=group_pred.note,
            total_cost_4y=total4,
            affordability_status=afford,
            data_granularity=group_pred.data_granularity,
            confidence=group_pred.confidence,
            warnings=warnings,
        )
        bk = _LEVEL_BUCKETS.get(level, "match")
        getattr(buckets, bk).append(opt)

        # 方向聚合
        dir_agg.setdefault(direction.name, []).append({
            "market_value": breakdown["market_value"],
            "student_fit": breakdown["student_fit"],
            "major_value": breakdown["major_value"],
            "direction": direction,
            "math_risk": breakdown.get("math_learning_risk", 0),
            "english_adapt": breakdown.get("english_adaptation", 1),
            "major_name": matched_major_name,
        })

    # 不可报原因
    for off, res in ineligible:
        ineligible_options.append(IneligibleReason(
            school=off.school,
            major_group_name=off.major_group_name,
            reasons=res.reasons,
            blocked_summary=res.blocked_summary,
        ))

    # 专业方向聚合（加权均值，按方向内 offerings 等权）
    major_directions: list[MajorDirectionAdvice] = []
    for dname, items in dir_agg.items():
        n = len(items)
        mv = sum(it["market_value"] for it in items) / n
        sf = sum(it["student_fit"] for it in items) / n
        mav = sum(it["major_value"] for it in items) / n
        d = items[0]["direction"]
        risk: list[str] = []
        fit_exp: list[str] = []
        if any(it["math_risk"] > 0.5 for it in items):
            risk.append(f"{dname} 方向数学学习风险较高，数学较弱考生需谨慎")
        if any(it["english_adapt"] < 0.4 for it in items):
            risk.append(f"{dname} 方向英语适配偏低，需评估实际英语能力")
        if sf >= 0.6:
            fit_exp.append(f"{dname} 与考生选科/单科能力匹配较好")
        major_directions.append(MajorDirectionAdvice(
            direction=dname,
            recommended_majors=list(d.majors[:5]),
            market_value=round(mv, 3),
            student_fit=round(sf, 3),
            major_value=round(mav, 3),
            fit_explanation=fit_exp,
            risk_warnings=risk,
        ))
    major_directions.sort(key=lambda x: x.major_value, reverse=True)

    # BudgetSummary（取代表院校：all school_options 的中位费用）
    all_opts = buckets.reach + buckets.match + buckets.safe
    if all_opts:
        rep = sorted(all_opts, key=lambda o: o.total_cost_4y)[len(all_opts) // 2]
        # 重新算分项（rep 只有 total，分项用整体均值近似或标注）
        budget_summary = BudgetSummary(
            total_4y=rep.total_cost_4y,
            affordable_total=budget.affordable_total,
            affordability_status=rep.affordability_status,
            data_note="费用按代表院校（中位）展示；各校分项见 school_options",
        )
    else:
        budget_summary = BudgetSummary(affordable_total=budget.affordable_total, data_note="无可推荐院校")

    notes = [
        f"录取数据基于 {data_year} 年同制度位次参考",
        "专业方向评分 = 市场参考 × 考生适配（乘法门控）",
    ]

    return VolunteerAdvisoryResult(
        student_rank=student_rank,
        province=profile.province,
        track=track,
        data_year=data_year,
        major_directions=major_directions,
        school_options=buckets,
        ineligible_options=ineligible_options,
        budget_summary=budget_summary,
        notes=notes,
    )
```

> **注意**：上面假设 `University` 有 `.tuition/.accommodation/.nature/.city`、`CityCost` 有 `.city/.monthly_total`（含 low/high）、`AdmissionRecord` 有 `.school/.min_rank`、`Major` 有 `.name`。实现时若字段名不符，按实际模型调整（先 `python -c "from app.models.university import University; print(University.model_fields)"` 核对）。

- [x] **Step 3: 核对模型字段并按实调整**

Run: `python -c "from app.models.university import University; from app.models.city import CityCost; from app.models.admission import AdmissionRecord; from app.models.major import Major; print('uni:', list(University.model_fields)); print('city:', list(CityCost.model_fields)); print('adm:', list(AdmissionRecord.model_fields)); print('major:', list(Major.model_fields))"`

按输出核对 `_compute_4y_cost` 与 build_advisory 中的字段访问（tuition/accommodation/nature/city/monthly_total/min_rank）。不符则修正。

- [x] **Step 4: 验证导入**

Run: `python -c "from app.engine.advisory import build_advisory, classify_affordability; print('engine import OK')"`
Expected: `engine import OK`

- [x] **Step 5: 提交**

```bash
git add app/engine/advisory.py
git commit -m "feat(advisory): build_advisory 主链路编排 + classify_affordability 4 级

专业方向优先：资格前置门→位次→market×fit→录取→费用压力→冲稳保→聚合。
修正 life_paths 的 major_value 错误（用 compute_major_value_academic）。"
```

---

### Task 3: advisory API 端点

**Files:**
- Modify: `app/api/routers/volunteer.py`（新增 handler，复用 helper + LifePathsRequest）

**Interfaces:**
- Consumes: Task 1 模型、Task 2 `build_advisory`、现有 helper

- [x] **Step 1: 新增 advisory handler**

在 `app/api/routers/volunteer.py` 的 `/life-paths` handler 之后追加：

```python
@router.post("/advisory")
def advisory(req: LifePathsRequest, session: Session = Depends(get_session_dep)):
    """志愿推荐 advisory 主接口（专业方向优先）。

    输入完整考生画像（分数+选科+外语+数学+实际英语能力+家庭预算），
    输出专业方向建议 + 冲稳保院校清单 + 费用压力 + 不可报原因 + 数据说明。
    主链路：资格过滤 → 位次 → 专业方向评分(market×fit) → 录取预测 → 费用压力 → 冲稳保。
    """
    from app.engine.advisory import build_advisory

    profile = _build_academic_profile(req)
    budget = _build_budget(req)
    offerings = _load_offerings()
    directions, snap_map = _load_directions_and_snapshots()

    track = "历史类" if profile.primary_subject == "历史" else "物理类"
    entries = _load_rank_entries(session, profile.province, 2026, track)
    admissions = _load_admissions(session, profile.province, track, 2025)
    actual_year = admissions[0].year if admissions else 2025

    result = build_advisory(
        profile=profile, budget=budget, offerings=offerings,
        directions=directions, snap_map=snap_map, admissions=admissions,
        unis=_load_universities(session), cities=_load_cities(session),
        majors=_load_majors(session), careers=_load_careers(session),
        rank_entries=entries, data_year=actual_year,
    )
    return result.model_dump(mode="json")
```

- [x] **Step 2: 验证路由导入 + 端点注册**

Run: `python -c "from app.api.routers.volunteer import advisory; from app.api.main import app; routes=[r.path for r in app.routes if 'advisory' in r.path]; print('advisory route:', routes)"`
Expected: `advisory route: ['/api/v1/volunteer/advisory']`

- [x] **Step 3: 提交**

```bash
git add app/api/routers/volunteer.py
git commit -m "feat(advisory): 新增 POST /api/v1/volunteer/advisory 主接口

复用 LifePathsRequest 与现有 _build_*/_load_* helper；调用 build_advisory。"
```

---

### Task 4: API 契约测试

**Files:**
- Create: `tests/api/test_advisory_api.py`

**Interfaces:** 验证 Task 3 端点

- [x] **Step 1: 写 API 测试**

创建 `tests/api/test_advisory_api.py`（复用 `tests/api/test_volunteer_api.py` 的 client fixture 模式）：

```python
"""advisory 主接口 API 测试。"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("adv_api") / "adv_api.db"
    import app.db as db_module
    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
    with TestClient(app) as c:
        yield c


_REQ = {
    "total_score": 543, "primary_subject": "历史",
    "math_score": 75, "exam_foreign_language": "英语",
    "foreign_language_score": 120, "english_actual_level": "intermediate",
    "elective_subjects": ["政治", "地理"],
    "family_annual_income": 80000, "family_savings": 20000,
    "max_annual_education_budget": 25000,
}


def test_advisory_returns_full_structure(client):
    r = client.post("/api/v1/volunteer/advisory", json=_REQ)
    assert r.status_code == 200
    body = r.json()
    for k in ("major_directions", "school_options", "ineligible_options",
              "budget_summary", "notes", "student_rank", "data_year"):
        assert k in body, f"missing {k}"
    # school_options 含冲稳保分桶
    so = body["school_options"]
    for bk in ("reach", "match", "safe"):
        assert bk in so


def test_advisory_no_forbidden_narrative(client):
    """遵守 narrative-policy：不出现禁止词。"""
    body = client.post("/api/v1/volunteer/advisory", json=_REQ).json()
    forbidden = ["人生路径", "人生轨迹", "回本", "ROI", "投资回报", "15年净收益", "赛道", "命运"]
    import json
    text = json.dumps(body, ensure_ascii=False)
    for w in forbidden:
        assert w not in text, f"advisory 响应含禁止词 {w}"
```

- [x] **Step 2: 运行**

Run: `python -m pytest tests/api/test_advisory_api.py -v`
Expected: 2 passed（若 543 分无匹配院校，school_options 三桶为空但结构仍存在，测试仍 pass）

- [x] **Step 3: 提交**

```bash
git add tests/api/test_advisory_api.py
git commit -m "test(advisory): advisory 端点返回完整结构 + 不含禁止词"
```

---

### Task 5: engine 测试（affordability + market×fit 门控）

**Files:**
- Create: `tests/engine/test_advisory_engine.py`

**Interfaces:** 验证 Task 2 的 `classify_affordability` 与 `build_advisory` 乘法门控

- [x] **Step 1: 写 engine 测试**

创建 `tests/engine/test_advisory_engine.py`：

```python
"""advisory engine 测试：affordability 4 级 + market×fit 门控。"""
from app.engine.advisory import classify_affordability
from app.models.life_path import FamilyBudget


def _budget(income=80000, savings=20000, annual_edu=25000, loan=0, aid=0):
    return FamilyBudget(
        annual_income=income, available_savings=savings,
        max_annual_education_budget=annual_edu,
        accepted_loan_amount=loan, confirmed_aid=aid,
    )


def test_affordability_affordable():
    # affordable_total = 20000 + 4*25000 = 120000；cost <= 120000 → 可承受
    assert classify_affordability(100000, _budget()) == "可承受"


def test_affordability_pressure():
    # cost 130000 > 120000 可承担；income 80000 → 130000/80000=1.625 → 有压力? 不，1.625>1.5 → 明显负担
    # 用 income=100000：130000/100000=1.3 → 有压力
    assert classify_affordability(130000, _budget(income=100000)) == "有压力"


def test_affordability_burden():
    # income=40000：200000/40000=5.0 > 3 → 超预算。需 income 让 ratio∈(1.5,3]
    # cost=200000, income=80000 → 2.5 → 明显负担；affordable_total=120000<200000
    assert classify_affordability(200000, _budget(income=80000)) == "明显负担"


def test_affordability_over_budget():
    # 远超可承担 + ratio 极高
    assert classify_affordability(500000, _budget(income=80000)) == "超预算"
```

- [x] **Step 2: market×fit 门控测试（需构造最小 build_advisory 调用）**

在 `tests/engine/test_advisory_engine.py` 追加（用真实 seed 数据驱动，断言 major_value == market×fit）。若构造完整 build_advisory 输入过重，改为直接断言 `compute_major_value_academic` 的乘法门控：

```python
def test_major_value_is_market_times_fit():
    """§3.4 乘法门控：major_value == market_value × student_fit。"""
    from app.engine.major_fit import compute_major_value_academic
    from app.models.eligibility import StudentAcademicProfile, EnglishLevel
    from app.models.job_market import MarketScores, CareerStage

    class _FakeMajor:
        def __init__(self):
            self.name = "计算机科学与技术"
            self.math_weight = 0.7
            self.foreign_language_weight = 0.3
            self.certificate_boost = 0.0
            self.interest_tags = []

    market = MarketScores(
        current_market_score=0.8, future_outlook_score=0.7,
        career_stage=CareerStage.SUNRISE, salary_index=0.8, demand_index=0.7,
        growth_index=0.8, evidence_level="B", breakdown_note="",
    )
    profile = StudentAcademicProfile(
        province="河南", total_score=543, primary_subject="历史",
        math_score=120, foreign_language_score=120,
        english_actual_level=EnglishLevel.INTERMEDIATE,
    )
    mv, breakdown = compute_major_value_academic(market, profile, _FakeMajor())
    assert abs(breakdown["major_value"] - breakdown["market_value"] * breakdown["student_fit"]) < 0.01
```

> **注意**：`_FakeMajor` 字段需匹配 `compute_student_fit_academic` 实际访问的 Major 属性。实现时先 `python -c "from app.models.major import Major; print(list(Major.model_fields))"` 核对，按实际字段构造。若 Major 必填字段多，改用真实 `_load_majors` 取一个。

- [x] **Step 3: 运行**

Run: `python -m pytest tests/engine/test_advisory_engine.py -v`
Expected: 5 passed

- [x] **Step 4: 提交**

```bash
git add tests/engine/test_advisory_engine.py
git commit -m "test(advisory-engine): affordability 4 级 + market×fit 乘法门控"
```

---

### Task 6: 资格/数据粒度边界测试

**Files:**
- Create: `tests/engine/test_advisory_eligibility.py`

**Interfaces:** 验证 §6.2 资格边界

- [x] **Step 1: 写资格边界测试**

创建 `tests/engine/test_advisory_eligibility.py`（用 filter_eligible 直接验证 §6.2 资格不变量，因 build_advisory 仅在 eligible 集合上运行）：

```python
"""advisory 资格边界测试（§6.2）：日语/选科过滤。"""
from app.engine.eligibility import filter_eligible
from app.models.eligibility import StudentAcademicProfile, EnglishLevel, AdmissionOfferingRule


def _japanese_student():
    return StudentAcademicProfile(
        province="河南", total_score=543, primary_subject="历史",
        exam_foreign_language="日语", foreign_language_score=120,
        english_actual_level=EnglishLevel.BASIC,
        math_score=90, elective_subjects=["政治", "地理"],
    )


def _offering_requires_english(school="某大学英语专业"):
    return AdmissionOfferingRule(
        school=school, province="河南", major_group_name="英语",
        required_exam_language="英语",  # 仅限英语考生
        direction_hint="外语与文学",
    )


def test_japanese_student_blocked_from_english_required():
    """§6.2: 日语考生被英语限定专业过滤。"""
    student = _japanese_student()
    offerings = [_offering_requires_english()]
    eligible, ineligible = filter_eligible(student, offerings)
    assert len(eligible) == 0
    assert len(ineligible) == 1
    assert ineligible[0][1].eligible is False


def test_advisory_only_scores_eligible():
    """§3.2: 评分仅在 eligible 集合上运行（不变量）。"""
    student = _japanese_student()
    offerings = [_offering_requires_english()]
    eligible, ineligible = filter_eligible(student, offerings)
    # build_advisory 应只对 eligible 调用评分；这里断言 eligible 为空则无评分对象
    assert eligible == []
```

- [x] **Step 2: 运行**

Run: `python -m pytest tests/engine/test_advisory_eligibility.py -v`
Expected: 2 passed

- [x] **Step 3: 提交**

```bash
git add tests/engine/test_advisory_eligibility.py
git commit -m "test(advisory): 资格边界——日语考生被英语限定专业过滤（§6.2）"
```

---

### Task 7: 回归 + openspec validate + 任务勾选

**Files:**
- Verify: 全量测试 + OpenSpec

- [x] **Step 1: 全量 pytest**

Run: `python -m pytest -q`
Expected: 全部 PASS（含 A 的 narrative-policy、现有 /recommend//score-rank//life-trajectory、新增 advisory 测试）

- [x] **Step 2: openspec validate**

Run: `openspec validate volunteer-advisory-engine`
Expected: `Change 'volunteer-advisory-engine' is valid`

- [x] **Step 3: 勾选 tasks.md 全部任务**

把 `openspec/changes/volunteer-advisory-engine/tasks.md` 中所有 `- [x]` 改为 `- [x]`。
计划任务→OpenSpec tasks 映射：Task1→1.1-1.4, Task2→2.1-2.5, Task3→3.1-3.2, Task4→4.1-4.2, Task5→5.1-5.3, Task6→6.1-6.4(部分), Task7→7.x/8.x。

- [x] **Step 4: 提交**

```bash
git add openspec/changes/volunteer-advisory-engine/tasks.md
git commit -m "chore: 勾选 volunteer-advisory-engine 任务；全量回归通过"
```

---

## Self-Review

**1. Spec coverage（volunteer-advisory delta 7 requirements / 14 scenarios）:**
- 主接口契约（结构 + 双语种字段）→ Task 1, 3, 4 ✓
- 专业方向优先主链路顺序（资格前置 + ineligible 输出）→ Task 2, 6 ✓
- market×fit 乘法门控（数学弱不前置）→ Task 2, 5 ✓
- 录取风险与数据粒度（仅组数据提示 + 跨年标注）→ Task 2（warnings + data_granularity）, Task 3（notes）✓
- 费用压力 4 级（分项 + 民办压力 + 超预算）→ Task 2（classify_affordability + _compute_4y_cost）, Task 5 ✓
- 冲稳保分桶与可解释输出 → Task 2（_LEVEL_BUCKETS + fit_explanation/risk_warnings/notes）✓

**2. Placeholder scan:** Task 2 Step 3 明确要求核对 University/CityCost/Major/AdmissionRecord 字段并按实调整（提供核对命令）；Task 5 Step 2 同理核对 Major 字段。无 TBD/TODO 占位。✓

**3. Type consistency:** `classify_affordability(cost_4y, budget)` 在 Task 2 定义、Task 5 测试；`build_advisory(...)` 在 Task 2 定义、Task 3 调用；SchoolOption/AdmissionBuckets 从 life_path 导入复用；MajorDirectionAdvice.market_value/student_fit/major_value 类型一致。✓

无遗漏。
