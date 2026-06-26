# Target Admission Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增“目标院校 + 专业（可选）评估”能力，按考生生源地和 3+1+2 条件判断目标院校/专业是否可报及风险档位。

**Architecture:** 新建 target evaluation 模型、引擎、API router 和前端页面。数据层复用 advisory 增强中的专业组规则与招生计划模型，评估链路明确区分资格、专业组投档、目标专业录取和数据缺口。

**Tech Stack:** Python/FastAPI/Pydantic/pytest，React/TypeScript/Vite。

## Global Constraints

- `source_province` 必填，用于筛选分省招生计划。
- 不得把全国计划或外省计划当作河南计划。
- 不输出精确百分比；风险档位固定为 `高 / 中高 / 中 / 低 / 不可报 / 数据不足`。
- 缺 2026 招生计划时必须在 `missing_data` 中标注，并降低置信度。
- 指定专业时必须区分专业组投档风险和目标专业录取风险。
- 所有来源必须进入 `sources` 数组。

---

## File Structure

- Create: `app/models/target_evaluation.py`
- Create: `app/engine/target_evaluation.py`
- Create: `app/api/routers/target.py`
- Modify: `app/api/main.py`
- Create: `tests/engine/test_target_evaluation.py`
- Create: `tests/api/test_target_evaluation_api.py`
- Modify: `web-ui/src/api/types.ts`
- Modify: `web-ui/src/api/client.ts`
- Create: `web-ui/src/pages/TargetEvaluationPage.tsx`
- Modify: `web-ui/src/App.tsx`

---

### Task 1: Target evaluation models

**Files:**
- Create: `app/models/target_evaluation.py`
- Test: `tests/models/test_target_evaluation.py`

**Interfaces:**
- Produces:
  - `TargetEvaluationRequest`
  - `AdmissionSource`
  - `EligibilityAssessment`
  - `RiskAssessment`
  - `MajorAdmissionAssessment`
  - `TargetEvaluationResult`

- [ ] **Step 1: Write failing tests**

Create `tests/models/test_target_evaluation.py`:

```python
from app.models.target_evaluation import TargetEvaluationRequest, TargetEvaluationResult


def test_request_requires_source_province_and_target_school():
    req = TargetEvaluationRequest(
        source_province="河南",
        target_school="郑州大学",
        target_major="计算机科学与技术",
        total_score=620,
        primary_subject="物理",
        elective_subjects=["化学", "生物"],
        exam_foreign_language="英语",
        foreign_language_score=125,
        math_score=130,
    )
    assert req.source_province == "河南"
    assert req.target_school == "郑州大学"


def test_result_can_report_missing_2026_plan():
    result = TargetEvaluationResult(
        target_school="郑州大学",
        target_major="计算机科学与技术",
        source_province="河南",
        eligibility={"eligible": False, "blocked_reasons": [], "review_warnings": ["缺少2026招生计划"]},
        group_admission={"risk_band": "数据不足", "basis": "", "student_rank": None, "baseline_rank": None, "data_year_used": None, "confidence": 0.2},
        major_admission={"risk_band": "数据不足", "target_major_available": False, "plan_count": None, "basis": "", "adjustment_risk": "数据不足"},
        sources=[],
        missing_data=["2026_enrollment_plan"],
        recommendation_summary="缺少目标院校河南 2026 分专业计划，无法给出可靠评估",
    )
    assert "2026_enrollment_plan" in result.missing_data
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/models/test_target_evaluation.py --basetemp .pytest-tmp -q`

Expected: import error.

- [ ] **Step 3: Implement models**

Create `app/models/target_evaluation.py`:

```python
from pydantic import BaseModel


class TargetEvaluationRequest(BaseModel):
    source_province: str
    target_school: str
    target_major: str | None = None
    data_year: int = 2026
    total_score: int
    primary_subject: str
    elective_subjects: list[str] = []
    exam_foreign_language: str = "英语"
    foreign_language_score: int = 0
    math_score: int = 0
    english_actual_level: str = "intermediate"
    accept_adjustment: bool = True


class AdmissionSource(BaseModel):
    source_name: str
    source_url: str
    source_type: str
    as_of: str
    confidence: float


class EligibilityAssessment(BaseModel):
    eligible: bool
    blocked_reasons: list[str] = []
    review_warnings: list[str] = []


class RiskAssessment(BaseModel):
    risk_band: str
    basis: str = ""
    student_rank: int | None = None
    baseline_rank: int | None = None
    data_year_used: int | None = None
    confidence: float = 0.0


class MajorAdmissionAssessment(BaseModel):
    risk_band: str
    target_major_available: bool = False
    plan_count: int | None = None
    basis: str = ""
    adjustment_risk: str = "数据不足"


class TargetEvaluationResult(BaseModel):
    target_school: str
    target_major: str | None = None
    source_province: str
    eligibility: EligibilityAssessment | dict
    group_admission: RiskAssessment | dict
    major_admission: MajorAdmissionAssessment | dict
    sources: list[AdmissionSource] = []
    missing_data: list[str] = []
    recommendation_summary: str
```

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/models/test_target_evaluation.py --basetemp .pytest-tmp -q`

Expected: 2 passed.

---

### Task 2: Target evaluation engine

**Files:**
- Create: `app/engine/target_evaluation.py`
- Test: `tests/engine/test_target_evaluation.py`

**Interfaces:**
- Produces:
  - `evaluate_target(req, plans, rules, admissions, rank_entries) -> TargetEvaluationResult`

- [ ] **Step 1: Write failing engine tests**

Create `tests/engine/test_target_evaluation.py`:

```python
from app.engine.target_evaluation import evaluate_target
from app.models.target_evaluation import TargetEvaluationRequest
from app.models.program_plan import EnrollmentPlan, ProgramGroupRule


def test_no_source_province_plan_is_data_insufficient():
    req = TargetEvaluationRequest(
        source_province="河南",
        target_school="外省大学",
        target_major="计算机科学与技术",
        total_score=620,
        primary_subject="物理",
        elective_subjects=["化学", "生物"],
        math_score=130,
        foreign_language_score=125,
    )
    result = evaluate_target(req=req, plans=[], rules=[], admissions=[], rank_entries=[])
    assert result.group_admission.risk_band == "数据不足"
    assert "2026_enrollment_plan" in result.missing_data


def test_physics_target_without_required_chemistry_is_ineligible():
    req = TargetEvaluationRequest(
        source_province="河南",
        target_school="郑州大学",
        target_major="计算机科学与技术",
        total_score=620,
        primary_subject="物理",
        elective_subjects=["生物", "地理"],
        math_score=130,
        foreign_language_score=125,
    )
    plans = [EnrollmentPlan(
        school="郑州大学", source_province="河南", year=2026,
        major_group_code="501", major_name="计算机科学与技术",
        plan_count=120, batch="本科批",
        source_name="郑州大学本科招生网", source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26", confidence=0.9,
        data_granularity="official_plan", review_status="verified",
    )]
    rules = [ProgramGroupRule(
        school="郑州大学", province="河南", year=2026, batch="本科批",
        major_group_code="501", major_group_name="物理类计算机组",
        primary_subject_requirement="物理",
        elective_subject_rule={"require": ["化学"], "any_of": []},
        included_majors=["计算机科学与技术"],
        source_name="郑州大学本科招生网", source_url="https://ao.zzu.edu.cn/",
        as_of="2026-06-26", confidence=0.9,
        data_granularity="official_rule", review_status="verified",
    )]
    result = evaluate_target(req=req, plans=plans, rules=rules, admissions=[], rank_entries=[])
    assert result.eligibility.eligible is False
    assert any("化学" in x for x in result.eligibility.blocked_reasons)
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/engine/test_target_evaluation.py --basetemp .pytest-tmp -q`

Expected: import error.

- [ ] **Step 3: Implement minimal engine**

Create `app/engine/target_evaluation.py`:

```python
from app.engine.volunteer import convert_score_to_rank
from app.models.target_evaluation import (
    EligibilityAssessment,
    MajorAdmissionAssessment,
    RiskAssessment,
    TargetEvaluationRequest,
    TargetEvaluationResult,
)


def _filter_plans(req: TargetEvaluationRequest, plans: list):
    return [
        p for p in plans
        if p.school == req.target_school
        and p.source_province == req.source_province
        and p.year == req.data_year
        and (req.target_major is None or p.major_name == req.target_major)
    ]


def _find_rule(plan, rules: list):
    return next(
        (
            r for r in rules
            if r.school == plan.school
            and r.province == plan.source_province
            and r.year == plan.year
            and r.major_group_code == plan.major_group_code
        ),
        None,
    )


def _check_rule(req: TargetEvaluationRequest, rule) -> list[str]:
    reasons: list[str] = []
    if rule.primary_subject_requirement and req.primary_subject != rule.primary_subject_requirement:
        reasons.append(f"首选科目要求{rule.primary_subject_requirement}，考生为{req.primary_subject}")
    require = (rule.elective_subject_rule or {}).get("require", [])
    for subject in require:
        if subject not in req.elective_subjects:
            reasons.append(f"再选科目要求包含{subject}")
    return reasons


def evaluate_target(req: TargetEvaluationRequest, plans: list, rules: list, admissions: list, rank_entries: list) -> TargetEvaluationResult:
    matched_plans = _filter_plans(req, plans)
    if not matched_plans:
        return TargetEvaluationResult(
            target_school=req.target_school,
            target_major=req.target_major,
            source_province=req.source_province,
            eligibility=EligibilityAssessment(
                eligible=False,
                review_warnings=[f"缺少{req.target_school}在{req.source_province}的{req.data_year}分专业计划"],
            ),
            group_admission=RiskAssessment(risk_band="数据不足", confidence=0.2),
            major_admission=MajorAdmissionAssessment(risk_band="数据不足"),
            missing_data=["2026_enrollment_plan"],
            recommendation_summary="缺少目标院校分省分专业计划，无法给出可靠评估",
        )

    plan = matched_plans[0]
    rule = _find_rule(plan, rules)
    blocked = _check_rule(req, rule) if rule else []
    student_rank = convert_score_to_rank(rank_entries, req.total_score) if rank_entries else None

    if blocked:
        return TargetEvaluationResult(
            target_school=req.target_school,
            target_major=req.target_major,
            source_province=req.source_province,
            eligibility=EligibilityAssessment(eligible=False, blocked_reasons=blocked),
            group_admission=RiskAssessment(risk_band="不可报", student_rank=student_rank, confidence=0.9),
            major_admission=MajorAdmissionAssessment(
                risk_band="不可报",
                target_major_available=True,
                plan_count=plan.plan_count,
                adjustment_risk="不可报",
            ),
            missing_data=[],
            recommendation_summary="当前选科或资格条件不满足目标专业组要求",
        )

    return TargetEvaluationResult(
        target_school=req.target_school,
        target_major=req.target_major,
        source_province=req.source_province,
        eligibility=EligibilityAssessment(eligible=True),
        group_admission=RiskAssessment(
            risk_band="数据不足",
            basis="缺少同专业组历史投档位次，暂不输出风险档位",
            student_rank=student_rank,
            confidence=0.4,
        ),
        major_admission=MajorAdmissionAssessment(
            risk_band="数据不足",
            target_major_available=True,
            plan_count=plan.plan_count,
            adjustment_risk="数据不足",
        ),
        missing_data=["historical_group_rank"],
        recommendation_summary="资格满足，但缺少历史投档位次，需补齐数据后评估风险",
    )
```

- [ ] **Step 4: Verify tests pass**

Run: `python -m pytest tests/engine/test_target_evaluation.py --basetemp .pytest-tmp -q`

Expected: 2 passed.

---

### Task 3: API router

**Files:**
- Create: `app/api/routers/target.py`
- Modify: `app/api/main.py`
- Test: `tests/api/test_target_evaluation_api.py`

**Interfaces:**
- Produces: `POST /api/v1/target/evaluate`

- [ ] **Step 1: Write failing API tests**

Create `tests/api/test_target_evaluation_api.py`:

```python
from fastapi.testclient import TestClient

from app.api.main import app


def test_target_evaluate_requires_source_province():
    client = TestClient(app)
    r = client.post("/api/v1/target/evaluate", json={
        "target_school": "郑州大学",
        "total_score": 620,
        "primary_subject": "物理",
    })
    assert r.status_code == 422


def test_target_evaluate_returns_structure():
    client = TestClient(app)
    r = client.post("/api/v1/target/evaluate", json={
        "source_province": "河南",
        "target_school": "郑州大学",
        "target_major": "计算机科学与技术",
        "total_score": 620,
        "primary_subject": "物理",
        "elective_subjects": ["化学", "生物"],
        "exam_foreign_language": "英语",
        "foreign_language_score": 125,
        "math_score": 130,
    })
    assert r.status_code == 200
    body = r.json()
    assert "eligibility" in body
    assert "group_admission" in body
    assert "major_admission" in body
    assert "missing_data" in body
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/api/test_target_evaluation_api.py --basetemp .pytest-tmp -q`

Expected: route not found.

- [ ] **Step 3: Implement router**

Create `app/api/routers/target.py`:

```python
from fastapi import APIRouter

from app.engine.target_evaluation import evaluate_target
from app.models.target_evaluation import TargetEvaluationRequest

router = APIRouter(prefix="/target", tags=["target"])


@router.post("/evaluate")
def evaluate(req: TargetEvaluationRequest):
    result = evaluate_target(
        req=req,
        plans=[],
        rules=[],
        admissions=[],
        rank_entries=[],
    )
    return result.model_dump(mode="json")
```

Modify `app/api/main.py`:

```python
from app.api.routers import target

app.include_router(target.router, prefix="/api/v1")
```

- [ ] **Step 4: Verify API tests pass**

Run: `python -m pytest tests/api/test_target_evaluation_api.py --basetemp .pytest-tmp -q`

Expected: 2 passed.

---

### Task 4: Frontend API client and page

**Files:**
- Modify: `web-ui/src/api/types.ts`
- Modify: `web-ui/src/api/client.ts`
- Create: `web-ui/src/pages/TargetEvaluationPage.tsx`
- Modify: `web-ui/src/App.tsx`

**Interfaces:**
- Consumes: `POST /api/v1/target/evaluate`

- [ ] **Step 1: Add TypeScript types**

Modify `web-ui/src/api/types.ts`:

```ts
export interface TargetEvaluationRequest {
  source_province: string;
  target_school: string;
  target_major?: string | null;
  data_year?: number;
  total_score: number;
  primary_subject: string;
  elective_subjects: string[];
  exam_foreign_language: string;
  foreign_language_score: number;
  math_score: number;
  english_actual_level?: string;
  accept_adjustment?: boolean;
}

export interface TargetEvaluationResult {
  target_school: string;
  target_major: string | null;
  source_province: string;
  eligibility: {
    eligible: boolean;
    blocked_reasons: string[];
    review_warnings: string[];
  };
  group_admission: {
    risk_band: string;
    basis: string;
    student_rank: number | null;
    baseline_rank: number | null;
    data_year_used: number | null;
    confidence: number;
  };
  major_admission: {
    risk_band: string;
    target_major_available: boolean;
    plan_count: number | null;
    basis: string;
    adjustment_risk: string;
  };
  sources: Array<Record<string, unknown>>;
  missing_data: string[];
  recommendation_summary: string;
}
```

- [ ] **Step 2: Add client function**

Modify `web-ui/src/api/client.ts`:

```ts
import type { TargetEvaluationRequest, TargetEvaluationResult } from "./types";

export function evaluateTarget(req: TargetEvaluationRequest): Promise<TargetEvaluationResult> {
  return request<TargetEvaluationResult>("/target/evaluate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
```

- [ ] **Step 3: Create page**

Create `web-ui/src/pages/TargetEvaluationPage.tsx`:

```tsx
import { useState } from "react";
import { evaluateTarget } from "../api/client";
import type { TargetEvaluationResult } from "../api/types";

export default function TargetEvaluationPage() {
  const [result, setResult] = useState<TargetEvaluationResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setLoading(true);
    try {
      const data = await evaluateTarget({
        source_province: String(form.get("source_province") || "河南"),
        target_school: String(form.get("target_school") || ""),
        target_major: String(form.get("target_major") || "") || null,
        total_score: Number(form.get("total_score") || 0),
        primary_subject: String(form.get("primary_subject") || "物理"),
        elective_subjects: String(form.get("elective_subjects") || "")
          .split(/[、,，\\s]+/)
          .filter(Boolean),
        exam_foreign_language: String(form.get("exam_foreign_language") || "英语"),
        foreign_language_score: Number(form.get("foreign_language_score") || 0),
        math_score: Number(form.get("math_score") || 0),
        english_actual_level: "intermediate",
        accept_adjustment: form.get("accept_adjustment") === "on",
      });
      setResult(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-extrabold">目标评估</h1>
      <form onSubmit={submit} className="glass rounded-3xl p-6 grid grid-cols-2 gap-4">
        <input name="source_province" defaultValue="河南" className="bg-white/10 rounded-xl px-3 py-2" />
        <input name="target_school" placeholder="目标院校" className="bg-white/10 rounded-xl px-3 py-2" />
        <input name="target_major" placeholder="目标专业（可选）" className="bg-white/10 rounded-xl px-3 py-2" />
        <input name="total_score" type="number" defaultValue={620} className="bg-white/10 rounded-xl px-3 py-2" />
        <select name="primary_subject" className="bg-white/10 rounded-xl px-3 py-2">
          <option value="物理">物理</option>
          <option value="历史">历史</option>
        </select>
        <input name="elective_subjects" defaultValue="化学 生物" className="bg-white/10 rounded-xl px-3 py-2" />
        <input name="exam_foreign_language" defaultValue="英语" className="bg-white/10 rounded-xl px-3 py-2" />
        <input name="foreign_language_score" type="number" defaultValue={125} className="bg-white/10 rounded-xl px-3 py-2" />
        <input name="math_score" type="number" defaultValue={130} className="bg-white/10 rounded-xl px-3 py-2" />
        <label className="flex items-center gap-2 text-sm">
          <input name="accept_adjustment" type="checkbox" defaultChecked />
          服从专业调剂
        </label>
        <button type="submit" disabled={loading} className="col-span-2 bg-pink-500 rounded-xl py-3 font-bold">
          {loading ? "评估中..." : "开始评估"}
        </button>
      </form>

      {result && (
        <div className="glass rounded-3xl p-6 space-y-3">
          <div className="font-bold text-xl">{result.recommendation_summary}</div>
          <div>资格：{result.eligibility.eligible ? "可报" : "不可报"}</div>
          <div>投档风险：{result.group_admission.risk_band}</div>
          <div>目标专业风险：{result.major_admission.risk_band}</div>
          {result.missing_data.length > 0 && (
            <div className="text-amber-300 text-sm">缺失数据：{result.missing_data.join("、")}</div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Register route**

Modify `web-ui/src/App.tsx` to add nav link and route:

```tsx
import TargetEvaluationPage from "./pages/TargetEvaluationPage";

<NavLink to="/target-evaluation">目标评估</NavLink>
<Route path="/target-evaluation" element={<TargetEvaluationPage />} />
```

- [ ] **Step 5: Build**

Run: `npm.cmd run build`

Expected: build succeeds.

---

### Task 5: API data integration

**Files:**
- Modify: `app/api/routers/target.py`
- Reuse: `data/seed/program_groups/henan_2026.yaml`
- Reuse: `data/seed/enrollment_plans/henan_2026.yaml`

**Interfaces:**
- Consumes real seed data from Henan advisory upgrade.

- [ ] **Step 1: Load YAML data**

In `app/api/routers/target.py`, add:

```python
from pathlib import Path
import yaml
from app.models.program_plan import EnrollmentPlan, ProgramGroupRule

SEED_DIR = Path("data/seed")


def _load_target_plans():
    path = SEED_DIR / "enrollment_plans/henan_2026.yaml"
    if not path.exists():
        return []
    return [EnrollmentPlan.model_validate(x) for x in (yaml.safe_load(path.read_text(encoding="utf-8")) or [])]


def _load_target_rules():
    path = SEED_DIR / "program_groups/henan_2026.yaml"
    if not path.exists():
        return []
    return [ProgramGroupRule.model_validate(x) for x in (yaml.safe_load(path.read_text(encoding="utf-8")) or [])]
```

Update handler:

```python
result = evaluate_target(
    req=req,
    plans=_load_target_plans(),
    rules=_load_target_rules(),
    admissions=[],
    rank_entries=[],
)
```

- [ ] **Step 2: Verify target API**

Run: `python -m pytest tests/api/test_target_evaluation_api.py --basetemp .pytest-tmp -q`

Expected: 2 passed.

---

### Task 6: Final verification

- [ ] **Step 1: Run Python target tests**

Run:

```powershell
python -m pytest tests/models/test_target_evaluation.py tests/engine/test_target_evaluation.py tests/api/test_target_evaluation_api.py --basetemp .pytest-tmp
```

Expected: all pass.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
npm.cmd run build
```

Working directory: `web-ui`

Expected: build succeeds.

- [ ] **Step 3: Manual browser smoke**

Open `http://localhost:5173/target-evaluation`:

- 郑州大学 + 计算机 + 物理化学：显示评估结果。
- 郑州大学 + 计算机 + 不选化学：显示不可报原因。
- 外省院校且无河南计划：显示数据不足，不使用全国计划。

