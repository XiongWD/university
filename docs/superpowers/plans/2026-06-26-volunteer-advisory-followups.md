# Volunteer Advisory Followups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the remaining stale OpenSpec state, make the advisory spec production-readable, move the frontend primary flow onto `/api/v1/volunteer/advisory`, and then evaluate removal of deprecated life-path code.

**Architecture:** Treat the current archived `narrative-policy` and `volunteer-advisory` work as the source of truth. Do not revive the old life-path optimizer. Split follow-up work into independently reviewable changes: OpenSpec hygiene, frontend advisory integration, UI presentation, and deprecated-code removal.

**Tech Stack:** FastAPI/Pydantic backend, React + TypeScript + Vite frontend, pytest, OpenSpec.

## Global Constraints

- Product positioning is `高考志愿专业推荐系统`, not life simulation or economic-return simulation.
- User-visible product copy MUST NOT use fixed-life narrative or transaction narrative: `人生路径`, `人生轨迹`, `赛道`, `回本`, `ROI`, `投资回报`, `15年净收益`, `命运`.
- Cost may show university-period expense and affordability pressure, but MUST NOT compute payback period or return-on-investment framing.
- The main recommendation chain MUST remain: eligibility gate -> score/rank -> `market * fit` major-direction scoring -> admission prediction -> cost pressure -> reach/match/safe -> explainable output.
- `StudentAcademicProfile` remains canonical for advisory inputs; keep `exam_foreign_language` separate from `english_actual_level`.
- Deprecated endpoints may stay temporarily for compatibility, but new primary UI and docs must point to `/api/v1/volunteer/advisory`.
- Do not introduce a new frontend test framework unless a task explicitly requires it; use TypeScript build, pytest, OpenSpec validation, and narrative scan as the baseline verification.

---

### Task 1: Retire Stale `v22-eligibility-core` Change

**Files:**
- Move: `openspec/changes/2026-06-25-v22-eligibility-core/` -> `openspec/changes/archive/2026-06-25-v22-eligibility-core-superseded/`
- Create: `openspec/changes/archive/2026-06-25-v22-eligibility-core-superseded/superseded.md`
- Modify: `openspec/changes/archive/2026-06-25-v22-eligibility-core-superseded/proposal.md`
- Modify: `openspec/changes/archive/2026-06-25-v22-eligibility-core-superseded/tasks.md`

**Interfaces:**
- Consumes: archived changes `2026-06-26-deprecate-life-path-narrative` and `2026-06-26-volunteer-advisory-engine`.
- Produces: no active invalid v22 change; `openspec.cmd validate --all` is no longer blocked by v22.

- [ ] **Step 1: Confirm the current blocker**

Run:

```powershell
openspec.cmd list
openspec.cmd validate 2026-06-25-v22-eligibility-core
```

Expected:

```text
2026-06-25-v22-eligibility-core
Change must have at least one delta
```

- [ ] **Step 2: Move the stale change into archive with a superseded suffix**

Run:

```powershell
git mv openspec\changes\2026-06-25-v22-eligibility-core openspec\changes\archive\2026-06-25-v22-eligibility-core-superseded
```

Expected: the active `openspec/changes/2026-06-25-v22-eligibility-core` directory no longer exists.

- [ ] **Step 3: Add an explicit supersession note**

Create `openspec/changes/archive/2026-06-25-v22-eligibility-core-superseded/superseded.md` with exactly this content:

```markdown
# Superseded Change: 2026-06-25-v22-eligibility-core

This change was intentionally retired after the product refocus on June 26, 2026.

The useful eligibility and admission-prediction concepts were carried forward by:

- `2026-06-26-deprecate-life-path-narrative`
- `2026-06-26-volunteer-advisory-engine`

The original Phase 4 and Phase 5 scope proposed a three-path life optimizer and path-oriented frontend. That scope is incompatible with the current product policy and must not be resumed.

Future work should build on the canonical specs:

- `openspec/specs/narrative-policy/spec.md`
- `openspec/specs/volunteer-advisory/spec.md`
```

- [ ] **Step 4: Replace the archived proposal with readable closure text**

Replace `openspec/changes/archive/2026-06-25-v22-eligibility-core-superseded/proposal.md` with:

```markdown
# Change: v22-eligibility-core (superseded)

## Status

Superseded by the June 26, 2026 volunteer-advisory refocus.

## Retained Concepts

- Eligibility is a hard gate before scoring.
- Admission prediction should distinguish professional-group投档 risk from target-major risk.
- Market, fit, and cost scoring should only run on eligible offerings.

## Rejected Scope

- Three-path life optimizer.
- Path-oriented frontend.
- Payback, ROI, or long-horizon net-income framing.

## Successor Specs

- `narrative-policy`
- `volunteer-advisory`
```

- [ ] **Step 5: Replace the archived task list with closure checklist**

Replace `openspec/changes/archive/2026-06-25-v22-eligibility-core-superseded/tasks.md` with:

```markdown
# Tasks - v22-eligibility-core (superseded)

- [x] Preserve the original execution notes in this archived folder.
- [x] Carry forward eligibility and admission concepts through `volunteer-advisory`.
- [x] Retire the three-path life optimizer scope.
- [x] Retire the path-oriented frontend scope.
- [x] Remove this change from the active OpenSpec change list.
```

- [ ] **Step 6: Verify OpenSpec active list and full validation**

Run:

```powershell
openspec.cmd list
openspec.cmd validate --all
```

Expected:

```text
No changes
All checks passed
```

If `openspec.cmd list` shows other active changes created after this plan, do not hide them. Report them separately and verify they are unrelated.

- [ ] **Step 7: Commit**

Run:

```powershell
git status --short
git add openspec\changes\archive\2026-06-25-v22-eligibility-core-superseded
git commit -m "chore(openspec): retire superseded v22 eligibility change"
```

Expected: commit succeeds and no active v22 path remains.

---

### Task 2: Clean `volunteer-advisory` Spec Purpose

**Files:**
- Modify: `openspec/specs/volunteer-advisory/spec.md`

**Interfaces:**
- Consumes: current `volunteer-advisory` spec.
- Produces: a production-readable Purpose section that states the advisory product scope without placeholder archive text.

- [ ] **Step 1: Write the failing hygiene check**

Run:

```powershell
rg -n "created by archiving|Update Purpose after archive" openspec\specs\volunteer-advisory\spec.md
```

Expected before implementation: at least one match in the Purpose section.

- [ ] **Step 2: Replace only the Purpose paragraph**

Update the Purpose section to this text:

```markdown
## Purpose
Define the main high-school-application advisory capability: given a student's academic profile, province/year context, rank data, eligibility rules, major-direction market signals, admission history, and family budget, the system recommends explainable major directions and reach/match/safe school options. The capability supports students and parents in志愿填报 simulation and planning without fixed-life narrative, path determinism, payback-period framing, ROI framing, or long-horizon net-income framing.
```

- [ ] **Step 3: Verify the placeholder text is gone**

Run:

```powershell
rg -n "created by archiving|Update Purpose after archive" openspec\specs\volunteer-advisory\spec.md
```

Expected: exit code `1` with no matches.

- [ ] **Step 4: Verify the spec and narrative policy**

Run:

```powershell
openspec.cmd validate volunteer-advisory
openspec.cmd validate narrative-policy
```

Expected:

```text
Specification 'volunteer-advisory' is valid
Specification 'narrative-policy' is valid
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add openspec\specs\volunteer-advisory\spec.md
git commit -m "docs(openspec): clarify volunteer advisory purpose"
```

---

### Task 3: Add Frontend Advisory Types and API Client

**Files:**
- Modify: `web-ui/src/api/types.ts`
- Modify: `web-ui/src/api/client.ts`

**Interfaces:**
- Consumes: backend `POST /api/v1/volunteer/advisory`, request shape currently compatible with `LifePathsRequest`.
- Produces:
  - `AdvisoryRequest`
  - `MajorDirectionAdvice`
  - `BudgetSummary`
  - `IneligibleReason`
  - `VolunteerAdvisoryResult`
  - `advisory(req: AdvisoryRequest): Promise<VolunteerAdvisoryResult>`

- [ ] **Step 1: Add frontend response types**

In `web-ui/src/api/types.ts`, add this block near the existing `LifePathsRequest` and `AdmissionBuckets` definitions:

```typescript
export type AdvisoryRequest = LifePathsRequest;

export interface MajorDirectionAdvice {
  direction: string;
  recommended_majors: string[];
  market_value: number;
  student_fit: number;
  major_value: number;
  fit_explanation: string[];
  risk_warnings: string[];
}

export interface BudgetSummary {
  tuition_4y: number;
  accommodation_4y: number;
  living_4y: number;
  total_4y: number;
  affordable_total: number | null;
  affordability_status: string;
  data_note: string | null;
}

export interface IneligibleReason {
  school: string;
  major_group_name: string;
  reasons: string[];
  blocked_summary: string;
}

export interface VolunteerAdvisoryResult {
  student_rank: number;
  province: string;
  track: string;
  data_year: number;
  major_directions: MajorDirectionAdvice[];
  school_options: AdmissionBuckets;
  ineligible_options: IneligibleReason[];
  budget_summary: BudgetSummary;
  notes: string[];
}
```

- [ ] **Step 2: Add the API client method**

In `web-ui/src/api/client.ts`, import `AdvisoryRequest` and `VolunteerAdvisoryResult`, then add:

```typescript
// POST /volunteer/advisory
export function advisory(req: AdvisoryRequest): Promise<VolunteerAdvisoryResult> {
  return request<VolunteerAdvisoryResult>("/volunteer/advisory", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
```

- [ ] **Step 3: Verify TypeScript**

Run:

```powershell
cd web-ui
npx.cmd tsc --noEmit
```

Expected: exit code `0`.

- [ ] **Step 4: Verify no new forbidden user-visible copy**

Run from repo root:

```powershell
rg -n "人生路径|人生轨迹|回本|ROI|投资回报|15年净收益|命运|赛道" web-ui\src README.md app\api -S
```

Expected: exit code `1` with no matches.

- [ ] **Step 5: Commit**

Run:

```powershell
git add web-ui\src\api\types.ts web-ui\src\api\client.ts
git commit -m "feat(web): add volunteer advisory client types"
```

---

### Task 4: Switch Home Flow from Deprecated Trajectory to Advisory

**Files:**
- Modify: `web-ui/src/components/ScoreForm.tsx`
- Modify: `web-ui/src/pages/HomePage.tsx`
- Optional create: `web-ui/src/components/AdvisorySchoolCard.tsx`
- Optional create: `web-ui/src/components/MajorDirectionPanel.tsx`

**Interfaces:**
- Consumes: `advisory(req: AdvisoryRequest)` from Task 3.
- Produces: the first-screen submission flow calls `/volunteer/advisory`, not `/volunteer/life-trajectory`.

- [ ] **Step 1: Change `ScoreForm` submit contract**

In `web-ui/src/components/ScoreForm.tsx`, change the prop type from `RecommendRequest` to `AdvisoryRequest`:

```typescript
import type { AdvisoryRequest, RiskPreference } from "../api/types";

interface Props {
  loading: boolean;
  onSubmit: (req: AdvisoryRequest) => void;
}
```

- [ ] **Step 2: Build advisory request from form state**

Replace the current `onSubmit({ ... })` payload with:

```typescript
onSubmit({
  province,
  total_score: totalScore,
  primary_subject: track.includes("历史") ? "历史" : "物理",
  math_score: mathScore,
  exam_foreign_language: foreignLang,
  foreign_language_score: foreignScore,
  english_actual_level: foreignLang === "英语" && foreignScore >= 120 ? "advanced" : "intermediate",
  elective_subjects: electives,
  max_annual_education_budget: undefined,
  accept_private_school: true,
});
```

If the file currently contains mojibake string literals, do not mass-rewrite the whole file in this task. Only change the request type and payload mapping unless the UI text must be corrected for the advisory flow.

- [ ] **Step 3: Change HomePage state and API call**

In `web-ui/src/pages/HomePage.tsx`, replace trajectory imports and state:

```typescript
import { advisory, ApiError } from "../api/client";
import type { AdvisoryRequest, VolunteerAdvisoryResult } from "../api/types";

const [result, setResult] = useState<VolunteerAdvisoryResult | null>(null);
```

Replace the submit handler with:

```typescript
async function handleSubmit(req: AdvisoryRequest) {
  setLoading(true);
  setError(null);
  try {
    const response = await advisory(req);
    setResult(response);
  } catch (e) {
    setError(e instanceof ApiError ? e.message : "请求失败，请确认后端服务已启动");
    setResult(null);
  } finally {
    setLoading(false);
  }
}
```

- [ ] **Step 4: Render advisory buckets**

Render `result.school_options.reach`, `result.school_options.match`, and `result.school_options.safe`. The UI labels must be `冲`, `稳`, `保`; do not mention deprecated trajectory concepts.

Each school option must show:

```text
school
matched_major
admission_level
total_cost_4y
affordability_status
data_granularity
warnings
```

- [ ] **Step 5: Render major-direction advice before school buckets**

Above the school buckets, render `result.major_directions.slice(0, 5)` with:

```text
direction
recommended_majors
major_value
market_value
student_fit
fit_explanation
risk_warnings
```

Use compact panels, not marketing-style hero cards. This is a decision-support tool.

- [ ] **Step 6: Render budget and ineligible explanations**

Render:

```text
result.budget_summary.total_4y
result.budget_summary.affordability_status
result.ineligible_options.slice(0, 8)
result.notes
```

The ineligible section should use the heading `不可报原因` or `资格限制说明`.

- [ ] **Step 7: Verify frontend build and narrative scan**

Run:

```powershell
cd web-ui
npx.cmd tsc --noEmit
cd ..
rg -n "lifeTrajectory\(|/volunteer/life-trajectory" web-ui\src\pages web-ui\src\components web-ui\src\api -S
rg -n "人生路径|人生轨迹|回本|ROI|投资回报|15年净收益|命运|赛道" web-ui\src README.md app\api -S
```

Expected:

```text
npx.cmd tsc --noEmit exits 0
the deprecated endpoint search has no matches in pages/components
the forbidden-copy scan has no matches
```

It is acceptable for `web-ui/src/api/client.ts` to still contain the deprecated `lifeTrajectory` function until Task 6.

- [ ] **Step 8: Run backend regression**

Run from repo root:

```powershell
python -m pytest -q --basetemp .tmp\pytest -p no:cacheprovider
```

Expected:

```text
340 passed
```

If the count changes because tests were added, all tests must still pass.

- [ ] **Step 9: Commit**

Run:

```powershell
git add web-ui\src\components\ScoreForm.tsx web-ui\src\pages\HomePage.tsx web-ui\src\components
git commit -m "feat(web): switch home flow to volunteer advisory"
```

---

### Task 5: Add Advisory-Focused Frontend Presentation Polish

**Files:**
- Modify: `web-ui/src/pages/HomePage.tsx`
- Modify or create: `web-ui/src/components/MajorDirectionPanel.tsx`
- Modify or create: `web-ui/src/components/AdvisorySchoolCard.tsx`
- Modify: `web-ui/src/index.css` only if existing styles cannot support the layout.

**Interfaces:**
- Consumes: `VolunteerAdvisoryResult`.
- Produces: a readable advisory interface centered on professional directions, eligibility explanations, admission buckets, and cost pressure.

- [ ] **Step 1: Make major directions the first result section**

The first result section after the student summary must be `专业方向建议`. It should sort by backend order and show at most five directions.

Each direction panel must include:

```text
专业方向
建议专业
综合匹配
市场参考
学生适配
解释
风险提示
```

- [ ] **Step 2: Keep school options dense and comparable**

School cards must fit a comparison workflow:

```text
学校
专业组或匹配专业
冲稳保等级
四年费用
费用压力
数据粒度
风险提示
```

Avoid oversized decorative cards. Use stable dimensions and avoid text overflow on mobile.

- [ ] **Step 3: Add a compact eligibility-limits section**

Show up to eight ineligible options. Each row must include:

```text
school
major_group_name
blocked_summary
```

If there are more than eight, show `还有 N 条资格限制未展开`.

- [ ] **Step 4: Add a compact data notes section**

Render `result.notes` as short lines under `数据说明`. Notes are advisory evidence, not marketing copy.

- [ ] **Step 5: Verify visual and textual constraints**

Run:

```powershell
cd web-ui
npx.cmd tsc --noEmit
cd ..
rg -n "人生路径|人生轨迹|回本|ROI|投资回报|15年净收益|命运|赛道" web-ui\src README.md app\api -S
```

Expected:

```text
TypeScript passes
forbidden-copy scan has no matches
```

- [ ] **Step 6: Commit**

Run:

```powershell
git add web-ui\src\pages\HomePage.tsx web-ui\src\components web-ui\src\index.css
git commit -m "feat(web): present advisory recommendations"
```

---

### Task 6: Evaluate and Remove Deprecated Life-Path Surface

**Files:**
- Inspect: `app/api/routers/volunteer.py`
- Inspect: `app/engine/life_path.py`
- Inspect: `app/engine/trajectory.py`
- Inspect: `app/models/life_path.py`
- Inspect: `app/models/life_trajectory.py`
- Inspect: `web-ui/src/api/client.ts`
- Inspect: `web-ui/src/api/types.ts`
- Inspect: `tests/engine/test_life_path.py`
- Inspect: `tests/api/test_volunteer_api.py`

**Interfaces:**
- Consumes: completed frontend advisory integration from Tasks 3-5.
- Produces: either a small removal change or a written decision to keep deprecated backend compatibility for one release.

- [ ] **Step 1: Inventory remaining references**

Run:

```powershell
rg -n "life_path|life_paths|lifeTrajectory|LifePath|LifeTrajectory|TrajectoryItem|PaybackAnalysis|/life-paths|/life-trajectory" app tests web-ui\src -S
```

Expected: references are limited to deprecated backend compatibility, deprecated types/client helpers, and legacy tests.

- [ ] **Step 2: Decide removal depth**

Use this decision table:

```text
If HomePage or primary navigation still calls deprecated endpoints: stop and return to Task 4.
If tests require deprecated endpoints as compatibility checks: keep endpoints, remove only frontend imports/usages.
If no tests or frontend code require deprecated endpoints: remove deprecated endpoints and their dedicated engines/models in one change.
If SchoolOption or AdmissionBuckets are still imported from life_path models by advisory: migrate those shared models into app/models/advisory.py before deleting life_path models.
```

- [ ] **Step 3: Minimal safe removal path**

If removal is safe, perform it in this order:

```text
1. Move shared SchoolOption and AdmissionBuckets definitions into app/models/advisory.py.
2. Update imports in app/engine/advisory.py and app/api/routers/volunteer.py.
3. Remove frontend deprecated client helpers and deprecated TypeScript types.
4. Remove deprecated routes only if compatibility tests are intentionally deleted or replaced.
5. Delete unused engine/model files only after rg shows no imports.
```

- [ ] **Step 4: Compatibility-retention path**

If removal is not safe for this release, keep backend deprecated endpoints and only remove frontend exposure:

```text
1. Keep app/api/routers/volunteer.py deprecated route decorators.
2. Keep backend legacy tests.
3. Remove unused frontend calls and hide deprecated frontend pages.
4. Add a short docs note that deprecated endpoints are backend compatibility only.
```

- [ ] **Step 5: Verify after either path**

Run:

```powershell
python -m pytest -q --basetemp .tmp\pytest -p no:cacheprovider
cd web-ui
npx.cmd tsc --noEmit
cd ..
openspec.cmd validate --all
rg -n "人生路径|人生轨迹|回本|ROI|投资回报|15年净收益|命运|赛道" web-ui\src README.md app\api -S
```

Expected:

```text
pytest passes
TypeScript passes
OpenSpec full validation passes
forbidden-copy scan has no matches
```

- [ ] **Step 6: Commit**

For safe removal:

```powershell
git add app tests web-ui\src README.md openspec
git commit -m "refactor: remove deprecated life path surface"
```

For compatibility retention:

```powershell
git add app tests web-ui\src README.md openspec
git commit -m "chore: keep deprecated endpoints as backend compatibility"
```

---

## Acceptance Checklist For Reviewer

- [ ] `openspec.cmd list` has no stale `2026-06-25-v22-eligibility-core` active change.
- [ ] `openspec.cmd validate --all` passes, unless a new unrelated active change is intentionally open and valid.
- [ ] `openspec/specs/volunteer-advisory/spec.md` Purpose is readable and does not contain archive-generated placeholder text.
- [ ] HomePage calls `advisory(...)`, not `lifeTrajectory(...)`.
- [ ] Primary UI renders major directions, school buckets, cost pressure, ineligible explanations, and data notes.
- [ ] `python -m pytest -q --basetemp .tmp\pytest -p no:cacheprovider` passes.
- [ ] `cd web-ui; npx.cmd tsc --noEmit` passes.
- [ ] Forbidden narrative scan has no matches in `web-ui/src`, `README.md`, and `app/api`.
- [ ] Deprecated backend removal decision is explicit: either removed safely or retained only as compatibility.
