# Henan 2026 Advisory Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将专业推荐升级为以河南 2026 为主、可解释、可回归测试的真实志愿辅助能力。

**Architecture:** 在现有 advisory 主链路上增加河南数据模型、批次线判断、严格选科资格、风险偏好分桶和数据证据链。保持 `/api/v1/volunteer/advisory` 兼容现有字段，同时扩展响应解释字段。

**Tech Stack:** Python/FastAPI/Pydantic/SQLModel/pytest，React/TypeScript/Vite，YAML/CSV seed data。

## Global Constraints

- 以河南为主，不承诺全国覆盖。
- 2026 无最终录取结果时必须使用 2025 同制度数据并明确标注。
- 理工农医强相关专业组缺少物理+化学来源时不得作为安全推荐。
- 不输出伪精确概率；使用冲/稳/保和置信度说明。
- 不出现 narrative-policy 禁止词：`人生路径`、`人生轨迹`、`回本`、`ROI`、`投资回报`、`15年净收益`、`命运`、`赛道`。
- 每条新增数据必须有 `source_name/source_url/as_of/confidence/review_status/data_granularity`。

---

## File Structure

- Create: `app/models/program_plan.py`
  - 负责 `ProgramGroupRule`、`EnrollmentPlan`、`BatchLineDecision`。
- Create: `app/engine/batch_line.py`
  - 负责本科线/专科线判断。
- Create: `app/engine/risk_buckets.py`
  - 负责按 `risk_preference` 和位次差生成冲稳保分桶。
- Modify: `app/engine/eligibility.py`
  - 复用现有资格链，增加物化缺来源时的 `needs_review` 处理入口。
- Modify: `app/engine/advisory.py`
  - 编排批次线、资格、分桶、证据链。
- Modify: `app/api/routers/volunteer.py`
  - advisory 请求/响应扩展。
- Create: `data/seed/program_groups/henan_2026.yaml`
  - 河南 2026 专业组规则。
- Create: `data/seed/enrollment_plans/henan_2026.yaml`
  - 河南 2026 分省分专业计划。
- Create: `tests/engine/test_batch_line.py`
- Create: `tests/engine/test_risk_buckets.py`
- Create: `tests/api/test_advisory_henan_2026_cases.py`
- Modify: `web-ui/src/api/types.ts`
- Modify: `web-ui/src/pages/HomePage.tsx`

---

### Task 1: 数据模型

**Files:**
- Create: `app/models/program_plan.py`
- Test: `tests/models/test_program_plan.py`

**Interfaces:**
- Produces:
  - `ProgramGroupRule`
  - `EnrollmentPlan`
  - `BatchLineDecision`

- [ ] **Step 1: Write failing tests**

Create `tests/models/test_program_plan.py`:

```python
from app.models.program_plan import ProgramGroupRule, EnrollmentPlan, BatchLineDecision


def test_program_group_rule_requires_source_metadata():
    rule = ProgramGroupRule(
        school="郑州大学",
        province="河南",
        year=2026,
        batch="本科批",
        major_group_code="501",
        major_group_name="物理类计算机组",
        primary_subject_requirement="物理",
        elective_subject_rule={"require": ["化学"], "any_of": []},
        included_majors=["计算机科学与技术"],
        source_name="郑州大学本科招生网",
        source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26",
        confidence=0.9,
        data_granularity="official_rule",
        review_status="verified",
    )
    assert rule.elective_subject_rule["require"] == ["化学"]


def test_enrollment_plan_tracks_source_province():
    plan = EnrollmentPlan(
        school="郑州大学",
        source_province="河南",
        year=2026,
        major_group_code="501",
        major_name="计算机科学与技术",
        plan_count=120,
        batch="本科批",
        source_name="郑州大学本科招生网",
        source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26",
        confidence=0.9,
        data_granularity="official_plan",
        review_status="verified",
    )
    assert plan.source_province == "河南"


def test_batch_line_decision_values():
    decision = BatchLineDecision(
        score=460,
        rank=91753,
        undergrad_line=471,
        junior_college_line=180,
        distance_to_undergrad_line=-11,
        batch_position="below_undergrad",
        recommendation_policy_note="低于本科线，普通本科仅可作为冲刺",
    )
    assert decision.batch_position == "below_undergrad"
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/models/test_program_plan.py --basetemp .pytest-tmp -q`

Expected: import error for `app.models.program_plan`.

- [ ] **Step 3: Implement models**

Create `app/models/program_plan.py`:

```python
from pydantic import BaseModel, Field


class SourceMetadata(BaseModel):
    source_name: str
    source_url: str
    as_of: str
    confidence: float = Field(ge=0, le=1)
    data_granularity: str
    review_status: str


class ProgramGroupRule(SourceMetadata):
    school: str
    province: str
    year: int
    batch: str
    major_group_code: str | None = None
    major_group_name: str
    primary_subject_requirement: str | None = None
    elective_subject_rule: dict = {}
    accepted_exam_languages: list[str] = []
    required_exam_language: str | None = None
    subject_score_rules: list[dict] = []
    included_majors: list[str] = []


class EnrollmentPlan(SourceMetadata):
    school: str
    source_province: str
    year: int
    major_group_code: str | None = None
    major_name: str
    plan_count: int = Field(ge=0)
    tuition: int | None = None
    school_system_years: int | None = None
    batch: str
    subject_requirement_text: str = ""


class BatchLineDecision(BaseModel):
    score: int
    rank: int
    undergrad_line: int | None = None
    junior_college_line: int | None = None
    distance_to_undergrad_line: int | None = None
    batch_position: str
    recommendation_policy_note: str
```

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/models/test_program_plan.py --basetemp .pytest-tmp -q`

Expected: 3 passed.

---

### Task 2: 批次线判断

**Files:**
- Create: `app/engine/batch_line.py`
- Test: `tests/engine/test_batch_line.py`

**Interfaces:**
- Consumes: `ProvincialControlLine`
- Produces: `decide_batch_position(score: int, rank: int, undergrad_line: int | None, junior_college_line: int | None) -> BatchLineDecision`

- [ ] **Step 1: Write failing tests**

Create `tests/engine/test_batch_line.py`:

```python
from app.engine.batch_line import decide_batch_position


def test_above_undergrad_line():
    d = decide_batch_position(score=480, rank=73822, undergrad_line=471, junior_college_line=180)
    assert d.batch_position == "above_undergrad"
    assert d.distance_to_undergrad_line == 9


def test_below_undergrad_line_requires_risk_note():
    d = decide_batch_position(score=460, rank=91753, undergrad_line=471, junior_college_line=180)
    assert d.batch_position == "below_undergrad"
    assert "本科仅可作为冲刺" in d.recommendation_policy_note


def test_junior_college_only_when_far_below_undergrad():
    d = decide_batch_position(score=350, rank=180000, undergrad_line=471, junior_college_line=180)
    assert d.batch_position == "junior_college_only"
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/engine/test_batch_line.py --basetemp .pytest-tmp -q`

Expected: import error.

- [ ] **Step 3: Implement engine**

Create `app/engine/batch_line.py`:

```python
from app.models.program_plan import BatchLineDecision


def decide_batch_position(
    score: int,
    rank: int,
    undergrad_line: int | None,
    junior_college_line: int | None,
) -> BatchLineDecision:
    if undergrad_line is None:
        return BatchLineDecision(
            score=score,
            rank=rank,
            undergrad_line=undergrad_line,
            junior_college_line=junior_college_line,
            distance_to_undergrad_line=None,
            batch_position="above_undergrad",
            recommendation_policy_note="缺少本科线数据，仅按位次推荐并降低置信度",
        )

    distance = score - undergrad_line
    if distance >= 0:
        position = "above_undergrad"
        note = "达到本科线，可进行本科冲稳保推荐"
    elif distance >= -15:
        position = "below_undergrad"
        note = "低于本科线，普通本科仅可作为冲刺，同时需要专科稳妥方案"
    else:
        position = "junior_college_only"
        note = "明显低于本科线，默认以专科稳妥方案为主"

    return BatchLineDecision(
        score=score,
        rank=rank,
        undergrad_line=undergrad_line,
        junior_college_line=junior_college_line,
        distance_to_undergrad_line=distance,
        batch_position=position,
        recommendation_policy_note=note,
    )
```

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/engine/test_batch_line.py --basetemp .pytest-tmp -q`

Expected: 3 passed.

---

### Task 3: 风险偏好分桶

**Files:**
- Create: `app/engine/risk_buckets.py`
- Test: `tests/engine/test_risk_buckets.py`

**Interfaces:**
- Produces:
  - `classify_rank_gap(student_rank: int, baseline_rank: int, risk_preference: str) -> str`

- [ ] **Step 1: Write failing tests**

Create `tests/engine/test_risk_buckets.py`:

```python
from app.engine.risk_buckets import classify_rank_gap


def test_balanced_bucket_near_baseline_is_match():
    assert classify_rank_gap(student_rank=50000, baseline_rank=51000, risk_preference="中") == "稳"


def test_aggressive_allows_wider_reach():
    assert classify_rank_gap(student_rank=56000, baseline_rank=50000, risk_preference="冲") == "偏冲"


def test_safe_preference_demotes_weak_reach():
    assert classify_rank_gap(student_rank=56000, baseline_rank=50000, risk_preference="稳") == "不推荐"


def test_strong_rank_is_safe():
    assert classify_rank_gap(student_rank=40000, baseline_rank=50000, risk_preference="中") == "保"
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/engine/test_risk_buckets.py --basetemp .pytest-tmp -q`

Expected: import error.

- [ ] **Step 3: Implement risk buckets**

Create `app/engine/risk_buckets.py`:

```python
def classify_rank_gap(student_rank: int, baseline_rank: int, risk_preference: str) -> str:
    if student_rank <= 0 or baseline_rank <= 0:
        return "不推荐"

    gap_ratio = (student_rank - baseline_rank) / baseline_rank

    if risk_preference == "冲":
        if gap_ratio <= -0.12:
            return "保"
        if gap_ratio <= 0.06:
            return "稳"
        if gap_ratio <= 0.18:
            return "偏冲"
        return "不推荐"

    if risk_preference == "稳":
        if gap_ratio <= -0.18:
            return "保"
        if gap_ratio <= -0.03:
            return "稳"
        if gap_ratio <= 0.04:
            return "偏冲"
        return "不推荐"

    if gap_ratio <= -0.15:
        return "保"
    if gap_ratio <= 0.06:
        return "稳"
    if gap_ratio <= 0.12:
        return "偏冲"
    return "不推荐"
```

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/engine/test_risk_buckets.py --basetemp .pytest-tmp -q`

Expected: 4 passed.

---

### Task 4: advisory 主链路集成

**Files:**
- Modify: `app/engine/advisory.py`
- Modify: `app/api/routers/volunteer.py`
- Test: `tests/api/test_advisory_henan_2026_cases.py`

**Interfaces:**
- Consumes:
  - `decide_batch_position`
  - `classify_rank_gap`
- Produces response fields:
  - `batch_line_decision`
  - `review_warnings`
  - `recommendation_policy`

- [ ] **Step 1: Write failing API tests**

Create `tests/api/test_advisory_henan_2026_cases.py`:

```python
from tests.api.test_advisory_api import client


def _post(client, payload):
    r = client.post("/api/v1/volunteer/advisory", json=payload)
    assert r.status_code == 200
    return r.json()


def test_history_460_reports_undergrad_risk(client):
    body = _post(client, {
        "province": "河南",
        "data_year": 2026,
        "risk_preference": "中",
        "total_score": 460,
        "primary_subject": "历史",
        "math_score": 95,
        "exam_foreign_language": "英语",
        "foreign_language_score": 120,
        "english_actual_level": "advanced",
        "elective_subjects": ["政治", "地理"],
    })
    assert body["batch_line_decision"]["batch_position"] in {"below_undergrad", "junior_college_only"}
    assert "本科" in body["batch_line_decision"]["recommendation_policy_note"]


def test_physics_without_chemistry_does_not_safe_recommend_computer(client):
    body = _post(client, {
        "province": "河南",
        "data_year": 2026,
        "risk_preference": "中",
        "total_score": 540,
        "primary_subject": "物理",
        "math_score": 110,
        "exam_foreign_language": "日语",
        "foreign_language_score": 115,
        "english_actual_level": "basic",
        "elective_subjects": ["生物", "地理"],
    })
    safe_text = str(body["school_options"]["safe"])
    assert "计算机" not in safe_text


def test_history_520_not_all_safe_when_data_exists(client):
    body = _post(client, {
        "province": "河南",
        "data_year": 2026,
        "risk_preference": "中",
        "total_score": 520,
        "primary_subject": "历史",
        "math_score": 105,
        "exam_foreign_language": "英语",
        "foreign_language_score": 125,
        "english_actual_level": "advanced",
        "elective_subjects": ["政治", "地理"],
    })
    total = sum(len(body["school_options"][k]) for k in ("reach", "match", "safe"))
    assert total > 0
    assert len(body["school_options"]["reach"]) + len(body["school_options"]["match"]) > 0 or body["review_warnings"]
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/api/test_advisory_henan_2026_cases.py --basetemp .pytest-tmp -q`

Expected: missing response fields or assertion failures.

- [ ] **Step 3: Extend response model**

Modify `app/models/advisory.py`:

```python
from app.models.program_plan import BatchLineDecision


class VolunteerAdvisoryResult(BaseModel):
    student_rank: int
    province: str
    track: str
    data_year: int
    major_directions: list[MajorDirectionAdvice] = []
    school_options: AdmissionBuckets
    ineligible_options: list[IneligibleReason] = []
    budget_summary: BudgetSummary
    notes: list[str] = []
    batch_line_decision: BatchLineDecision | None = None
    data_sources: list[dict] = []
    review_warnings: list[str] = []
    recommendation_policy: str = ""
```

- [ ] **Step 4: Integrate engines**

Modify `app/engine/advisory.py`:

```python
from app.engine.batch_line import decide_batch_position
from app.engine.risk_buckets import classify_rank_gap


def _apply_level_from_rank(student_rank: int, baseline_rank: int | None, risk_preference: str) -> str:
    if baseline_rank is None:
        return "不推荐"
    return classify_rank_gap(student_rank, baseline_rank, risk_preference)
```

Inside `build_advisory`, before iterating candidates:

```python
batch_line_decision = decide_batch_position(
    score=profile.total_score,
    rank=student_rank,
    undergrad_line=None,
    junior_college_line=None,
)
review_warnings: list[str] = []
```

When classifying each offering, replace `level = group_pred.admission_level.value` with:

```python
level = _apply_level_from_rank(student_rank, baseline, risk_preference)
if level == "不推荐":
    continue
```

When returning result:

```python
batch_line_decision=batch_line_decision,
review_warnings=review_warnings,
recommendation_policy=f"按{risk_preference}策略使用位次差分桶",
```

- [ ] **Step 5: Verify API tests pass**

Run: `python -m pytest tests/api/test_advisory_henan_2026_cases.py --basetemp .pytest-tmp -q`

Expected: 3 passed.

---

### Task 5: 前端展示新增解释字段

**Files:**
- Modify: `web-ui/src/api/types.ts`
- Modify: `web-ui/src/pages/HomePage.tsx`
- Test: `web-ui/e2e/advisory.spec.ts`

**Interfaces:**
- Consumes API fields:
  - `batch_line_decision`
  - `review_warnings`
  - `recommendation_policy`

- [ ] **Step 1: Update TypeScript types**

Add to `web-ui/src/api/types.ts`:

```ts
export interface BatchLineDecision {
  score: number;
  rank: number;
  undergrad_line: number | null;
  junior_college_line: number | null;
  distance_to_undergrad_line: number | null;
  batch_position: string;
  recommendation_policy_note: string;
}
```

Extend `VolunteerAdvisoryResult`:

```ts
batch_line_decision?: BatchLineDecision | null;
data_sources?: Record<string, unknown>[];
review_warnings?: string[];
recommendation_policy?: string;
```

- [ ] **Step 2: Render batch warning**

In `web-ui/src/pages/HomePage.tsx`, below 考生摘要:

```tsx
{result.batch_line_decision && (
  <div className="glass rounded-2xl p-4 mb-6 text-sm text-white/70">
    <div className="font-bold text-white mb-1">批次线判断</div>
    <div>{result.batch_line_decision.recommendation_policy_note}</div>
    {result.batch_line_decision.distance_to_undergrad_line !== null && (
      <div className="text-xs text-white/45 mt-1">
        距本科线 {result.batch_line_decision.distance_to_undergrad_line} 分
      </div>
    )}
  </div>
)}
```

- [ ] **Step 3: Build**

Run: `npm.cmd run build`

Expected: TypeScript and Vite build pass.

---

### Task 6: Final verification

**Files:**
- Verify all touched tests.

- [ ] **Step 1: Run Python tests**

Run:

```powershell
python -m pytest tests/models/test_program_plan.py tests/engine/test_batch_line.py tests/engine/test_risk_buckets.py tests/api/test_advisory_api.py tests/api/test_advisory_henan_2026_cases.py --basetemp .pytest-tmp
```

Expected: all selected tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
npm.cmd run build
```

Working directory: `web-ui`

Expected: build succeeds.

- [ ] **Step 3: Manual browser smoke**

Use `http://localhost:5173/`:

- 河南历史 460：结果显示批次线风险。
- 河南物理 540，不选化学：安全推荐里没有计算机。
- 河南历史 520：不应只出现“保”，除非有 `review_warnings` 说明数据不足。

