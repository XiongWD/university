# 河南志愿推产品重构修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前“河南志愿推”从样例壳子修复为可验收的河南 2026 志愿推荐和目标评估主链路。

**Architecture:** 保留旧 `/volunteer/*` 和旧 target 接口作为兼容层，新建并打通 `/api/v1/henan/*` 主链路。数据先行：真实覆盖报告和上线门禁必须先拦住假推荐；推荐引擎统一生成院校专业组候选，首页推荐和目标评估都只消费同一候选集。

**Tech Stack:** Python/FastAPI/Pydantic/pytest/YAML/CSV，React/TypeScript/Vite/Playwright。

## Global Constraints

- 产品名固定为“河南志愿推”。
- 当前只服务河南考生，`source_province` 固定为 `河南`。
- 普通本科批志愿单位是院校专业组，不是学校或单个专业。
- 真实推荐必须依赖 2026 河南招生计划、2026 院校专业组、2025/2024 历史录取、一分一段、省控线。
- `plan_count=0`、`review_status=needs_review`、缺少专业组限制、缺少河南计划的数据不得进入 `稳` 或 `保`。
- 首页推荐和目标评估必须复用同一个 `build_henan_candidates(...)` 候选生成器。
- 旧 advisory/target 接口保留兼容，不作为河南志愿推新主链路继续扩展。

---

## Current Failure Evidence

- `/api/v1/henan/options` 当前只有 4 所学校、3 个专业、5 个专业组。
- `data/seed/henan/enrollment_plans_2026.yaml` 当前 3 条计划的 `plan_count` 全为 `0`，且均为 `needs_review`。
- `app/engine/henan_recommendation.py::build_henan_candidates()` 当前只校验生源地后返回 `[]`。
- `web-ui/src/pages/HomePage.tsx` 当前仍调用旧 `advisory(req)`，没有接入河南新推荐 API。
- `data/seed/henan/data_coverage_report.example.json` 写的是示例数字，不是实际覆盖报告。
- 全量测试通过只能说明样例链路未崩溃，不能证明河南志愿推验收通过。

---

## File Structure

- Modify: `app/models/henan_data.py`
- Modify: `app/loader/henan_data_loader.py`
- Modify: `app/loader/henan_coverage_report.py`
- Modify: `app/loader/henan_program_group_index.py`
- Modify: `app/engine/henan_recommendation.py`
- Modify: `app/engine/henan_target_evaluation.py`
- Modify: `app/api/routers/henan.py`
- Modify: `app/api/main.py`
- Modify: `web-ui/src/api/types.ts`
- Modify: `web-ui/src/api/client.ts`
- Modify: `web-ui/src/pages/HomePage.tsx`
- Modify: `web-ui/src/pages/TargetEvaluationPage.tsx`
- Modify: `web-ui/src/App.tsx`
- Create: `scripts/build_henan_coverage_report.py`
- Create: `scripts/import_henan_2026_catalog.py`
- Create: `data/seed/henan/data_coverage_report.json`
- Replace or regenerate: `data/seed/henan/program_groups_2026.yaml`
- Replace or regenerate: `data/seed/henan/enrollment_plans_2026.yaml`
- Create or regenerate: `data/seed/henan/admission_history_2025.yaml`
- Create or regenerate: `data/seed/henan/admission_history_2024.yaml`
- Replace or regenerate: `data/seed/henan/universities.yaml`
- Test: `tests/loader/test_henan_real_coverage_gate.py`
- Test: `tests/engine/test_henan_candidate_generation.py`
- Test: `tests/api/test_henan_recommendation_api.py`
- Test: `web-ui/e2e/henan-recommendation.spec.ts`
- Test: `web-ui/e2e/henan-target-evaluation.spec.ts`

---

### Task 1: Replace Fake Coverage With Real Data Gate

**Files:**
- Modify: `app/loader/henan_coverage_report.py`
- Create: `scripts/build_henan_coverage_report.py`
- Create: `tests/loader/test_henan_real_coverage_gate.py`
- Create: `data/seed/henan/data_coverage_report.json`
- Stop relying on: `data/seed/henan/data_coverage_report.example.json`

**Interfaces:**
- Produces:
  - `build_actual_henan_coverage(seed_dir: Path) -> dict`
  - `assert_henan_recommendation_ready(report: dict) -> None`

- [ ] **Step 1: Write failing coverage tests**

Create `tests/loader/test_henan_real_coverage_gate.py`:

```python
from pathlib import Path

import pytest

from app.loader.henan_coverage_report import (
    assert_henan_recommendation_ready,
    build_actual_henan_coverage,
)


def test_actual_coverage_counts_seed_records():
    report = build_actual_henan_coverage(Path("data/seed"))
    assert report["actual"]["universities_2026"] >= 1
    assert report["actual"]["program_groups_2026"] >= 1
    assert report["actual"]["enrollment_plans_henan_2026"] >= 1
    assert "verified_program_groups_2026" in report["quality"]
    assert "nonzero_enrollment_plans_2026" in report["quality"]


def test_launch_gate_blocks_zero_plan_and_unverified_groups(tmp_path):
    report = {
        "actual": {
            "universities_2026": 4,
            "program_groups_2026": 5,
            "enrollment_plans_henan_2026": 3,
        },
        "quality": {
            "verified_program_groups_2026": 0,
            "verified_enrollment_plans_2026": 0,
            "nonzero_enrollment_plans_2026": 0,
            "verified_2025_history": 0,
        },
    }
    with pytest.raises(ValueError, match="verified_program_groups_2026"):
        assert_henan_recommendation_ready(report)
```

- [ ] **Step 2: Implement real coverage report**

In `app/loader/henan_coverage_report.py`, add:

```python
from pathlib import Path

from app.loader.henan_data_loader import (
    load_henan_enrollment_plans,
    load_henan_program_groups,
    load_henan_universities,
)


def build_actual_henan_coverage(seed_dir: Path) -> dict:
    universities = load_henan_universities(seed_dir)
    groups = load_henan_program_groups(seed_dir)
    plans = load_henan_enrollment_plans(seed_dir)
    return {
        "actual": {
            "universities_2026": len(universities),
            "program_groups_2026": len(groups),
            "enrollment_plans_henan_2026": len(plans),
        },
        "quality": {
            "verified_program_groups_2026": sum(1 for x in groups if x.review_status == "verified"),
            "verified_enrollment_plans_2026": sum(1 for x in plans if x.review_status == "verified"),
            "nonzero_enrollment_plans_2026": sum(1 for x in plans if x.plan_count > 0),
            "verified_2025_history": 0,
        },
    }


def assert_henan_recommendation_ready(report: dict) -> None:
    quality = report.get("quality", {})
    missing = [
        key for key in [
            "verified_program_groups_2026",
            "verified_enrollment_plans_2026",
            "nonzero_enrollment_plans_2026",
            "verified_2025_history",
        ]
        if quality.get(key, 0) <= 0
    ]
    if missing:
        raise ValueError(f"河南志愿推推荐数据未就绪: {', '.join(missing)}")
```

- [ ] **Step 3: Add coverage CLI**

Create `scripts/build_henan_coverage_report.py`:

```python
import json
from pathlib import Path

from app.loader.henan_coverage_report import build_actual_henan_coverage


def main() -> None:
    report = build_actual_henan_coverage(Path("data/seed"))
    out = Path("data/seed/henan/data_coverage_report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/loader/test_henan_real_coverage_gate.py --basetemp .pytest-tmp
python scripts/build_henan_coverage_report.py
```

Expected:
- Tests pass.
- Current report shows low actual coverage and blocks recommendation readiness until real data is imported.

---

### Task 2: Import Real 2026 Henan Catalog Data

**Files:**
- Create: `scripts/import_henan_2026_catalog.py`
- Replace or regenerate: `data/seed/henan/program_groups_2026.yaml`
- Replace or regenerate: `data/seed/henan/enrollment_plans_2026.yaml`
- Replace or regenerate: `data/seed/henan/universities.yaml`
- Modify: `data/seed/henan/source_registry.yaml`

**Interfaces:**
- Produces:
  - `program_groups_2026.yaml` with verified or needs_review records.
  - `enrollment_plans_2026.yaml` with real nonzero `plan_count`.
  - `universities.yaml` with all schools that have 2026 Henan plans.

- [ ] **Step 1: Define import input format**

Create importer that accepts a normalized CSV exported from official source parsing:

```csv
source_province,school_origin_province,school_code,school_name,year,batch,track,major_group_code,major_group_name,major_code,major_name,plan_count,primary_subject_requirement,elective_subject_requirement,accepted_exam_languages,public_foreign_languages,tuition,accommodation,source_name,source_url,as_of,review_status
河南,河南,10459,郑州大学,2026,本科批,历史类,101,历史类人文组,030101K,法学,12,历史,{},英语|日语,英语,4400,1100,河南2026招生专业目录,https://www.haeea.cn/,2026-06-26,verified
```

- [ ] **Step 2: Implement importer**

Create `scripts/import_henan_2026_catalog.py`:

```python
import csv
import sys
from pathlib import Path

import yaml


def split_pipe(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split("|") if x.strip()]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_henan_2026_catalog.py <normalized_catalog.csv>")
    source = Path(sys.argv[1])
    rows = list(csv.DictReader(source.read_text(encoding="utf-8-sig").splitlines()))

    universities = {}
    groups = {}
    plans = []

    for row in rows:
        school_code = row["school_code"]
        universities[school_code] = {
            "school_code": school_code,
            "school_name": row["school_name"],
            "province": row["school_origin_province"],
            "city": "",
            "ownership": "",
            "school_level": "",
            "strong_majors": [],
            "tags": [],
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "as_of": row["as_of"],
            "confidence": 0.9 if row["review_status"] == "verified" else 0.5,
            "review_status": row["review_status"],
        }
        key = (row["year"], row["track"], school_code, row["major_group_code"])
        group = groups.setdefault(key, {
            "year": int(row["year"]),
            "track": row["track"],
            "batch": row["batch"],
            "school_code": school_code,
            "school_name": row["school_name"],
            "major_group_code": row["major_group_code"],
            "major_group_name": row["major_group_name"],
            "included_majors": [],
            "major_codes": [],
            "primary_subject_requirement": row["primary_subject_requirement"],
            "elective_subject_requirement": yaml.safe_load(row["elective_subject_requirement"] or "{}") or {},
            "accepted_exam_languages": split_pipe(row["accepted_exam_languages"]),
            "public_foreign_languages": split_pipe(row["public_foreign_languages"]),
            "single_subject_requirements": [],
            "adjustment_scope": "组内专业",
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "as_of": row["as_of"],
            "confidence": 0.9 if row["review_status"] == "verified" else 0.5,
            "review_status": row["review_status"],
        })
        if row["major_name"] not in group["included_majors"]:
            group["included_majors"].append(row["major_name"])
        if row["major_code"] and row["major_code"] not in group["major_codes"]:
            group["major_codes"].append(row["major_code"])

        plans.append({
            "year": int(row["year"]),
            "source_province": row["source_province"],
            "school_origin_province": row["school_origin_province"],
            "is_henan_local_school": row["school_origin_province"] == "河南",
            "school_code": school_code,
            "school_name": row["school_name"],
            "major_group_code": row["major_group_code"],
            "major_name": row["major_name"],
            "plan_count": int(row["plan_count"]),
            "school_system_years": 4,
            "tuition": int(row["tuition"] or 0) or None,
            "accommodation": int(row["accommodation"] or 0) or None,
            "batch": row["batch"],
            "track": row["track"],
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "as_of": row["as_of"],
            "confidence": 0.9 if row["review_status"] == "verified" else 0.5,
            "review_status": row["review_status"],
        })

    out_dir = Path("data/seed/henan")
    (out_dir / "universities.yaml").write_text(yaml.safe_dump(list(universities.values()), allow_unicode=True, sort_keys=False), encoding="utf-8")
    (out_dir / "program_groups_2026.yaml").write_text(yaml.safe_dump(list(groups.values()), allow_unicode=True, sort_keys=False), encoding="utf-8")
    (out_dir / "enrollment_plans_2026.yaml").write_text(yaml.safe_dump(plans, allow_unicode=True, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Import real source**

Run with normalized official catalog:

```powershell
python scripts/import_henan_2026_catalog.py data/raw/henan_2026/normalized_catalog.csv
python scripts/build_henan_coverage_report.py
```

Expected:
- `program_groups_2026.yaml` contains all parsed 2026 Henan groups.
- `enrollment_plans_2026.yaml` contains nonzero plan counts.
- Coverage report records actual counts and quality.

- [ ] **Step 4: Minimum data acceptance gate**

Before recommendation UI is considered usable:

```text
verified_program_groups_2026 > 0
verified_enrollment_plans_2026 > 0
nonzero_enrollment_plans_2026 > 0
verified_2025_history > 0
```

Before product release:

```text
All 2026 Henan ordinary undergraduate schools in official catalog imported.
All ordinary undergraduate program groups imported.
All ordinary undergraduate Henan plan counts imported.
All records retain source_url and review_status.
```

---

### Task 2B: Import 2025/2024 Historical Admission Baselines

**Files:**
- Create: `scripts/import_henan_admission_history.py`
- Create or regenerate: `data/seed/henan/admission_history_2025.yaml`
- Create or regenerate: `data/seed/henan/admission_history_2024.yaml`
- Modify: `app/loader/henan_data_loader.py`
- Test: `tests/loader/test_henan_admission_history_import.py`

**Why this is mandatory:**
2026 专业组和招生计划只能回答“能不能报”和“招多少”。冲稳保必须依赖 2025/2024 历史录取位次、专业组或专业录取位次、一分一段换算和招生计划变化。没有历史基线时，系统不得把任何院校专业组标成 `稳` 或 `保`。

- [ ] **Step 1: Define historical import format**

Importer accepts normalized CSV:

```csv
year,source_province,track,batch,school_code,school_name,major_group_code,major_group_name,major_code,major_name,min_score,min_rank,avg_score,plan_count,admitted_count,data_granularity,source_name,source_url,source_published_at,review_status
2025,河南,历史类,本科批,10459,郑州大学,101,历史类人文组,030101K,法学,612,11020,618,12,12,major,河南2025普通高校招生录取统计,https://www.haeea.cn/,2025-07-30,verified
```

Required fields:
- `year`: only `2025` or `2024` for this task.
- `data_granularity`: `major`, `major_group`, or `school_batch`.
- `min_rank`: must be positive for verified rows.
- `review_status`: `verified` required for production scoring.
- `source_url` and `source_published_at`: required for traceability.

- [ ] **Step 2: Implement importer and loader**

`scripts/import_henan_admission_history.py` must:
- read official or manually normalized historical CSV;
- validate required columns;
- reject verified rows with missing `min_rank`;
- write year-specific YAML under `data/seed/henan/`;
- preserve source metadata per row.

`app/loader/henan_data_loader.py` must expose:

```python
def load_henan_admission_history(seed_dir: Path, years: tuple[int, ...] = (2025, 2024)) -> list[HenanAdmissionHistory]:
    ...
```

and lookup helpers:

```python
def find_best_historical_baseline(history, *, school_code, group_code, major_names, track, batch):
    ...
```

Lookup order:
1. 2025 exact major-level rank.
2. 2025 major-group rank.
3. Weighted 2025 + 2024 major/group trend when both exist.
4. 2025 school-batch fallback only as low-confidence reference.
5. No verified history: return `None`.

- [ ] **Step 3: Add history tests**

`tests/loader/test_henan_admission_history_import.py` must cover:
- verified row with `min_rank <= 0` is rejected;
- 2025 exact major rank wins over group fallback;
- 2024 data is used only as trend correction, not as the sole `保` basis;
- missing verified history returns `None`.

- [ ] **Step 4: Verify**

```powershell
python scripts/import_henan_admission_history.py data/raw/henan_2025/normalized_admission_history.csv --year 2025
python scripts/import_henan_admission_history.py data/raw/henan_2024/normalized_admission_history.csv --year 2024
python -m pytest tests/loader/test_henan_admission_history_import.py --basetemp .pytest-tmp
python scripts/build_henan_coverage_report.py --fail-on-not-ready
```

Expected:
- Coverage report separates `verified_2025_history` and `verified_2024_history`.
- Recommendation readiness fails if 2026 catalog exists but historical rank baseline is missing.
- No candidate can enter `稳` or `保` without verified 2025/2024 historical support.

---

### Task 3: Implement Real Henan Candidate Generation

**Files:**
- Modify: `app/engine/henan_recommendation.py`
- Modify: `app/loader/henan_data_loader.py`
- Test: `tests/engine/test_henan_candidate_generation.py`

**Interfaces:**
- Produces:
  - `build_henan_candidates(profile: dict) -> list[dict]`
  - Candidate fields consumed by homepage and target evaluation.

- [ ] **Step 1: Write failing candidate tests**

Create `tests/engine/test_henan_candidate_generation.py`:

```python
from app.engine.henan_recommendation import build_henan_candidates


def test_build_henan_candidates_returns_groups_when_verified_data_exists():
    profile = {
        "source_province": "河南",
        "score": 610,
        "rank": 12000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
        "strategy": "自动",
    }

    candidates = build_henan_candidates(profile)

    assert isinstance(candidates, list)
    assert all(item["volunteer_unit"] == "院校专业组" for item in candidates)
    assert all("major_group_code" in item for item in candidates)
    assert all(item["bucket"] in {"冲", "稳", "保", "不推荐", "需人工复核"} for item in candidates)


def test_build_henan_candidates_excludes_zero_plan_from_reachable_buckets():
    profile = {
        "source_province": "河南",
        "score": 610,
        "rank": 12000,
        "track": "历史类",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
    }
    candidates = build_henan_candidates(profile)
    assert all(not (item.get("plan_count", 1) == 0 and item["bucket"] in {"冲", "稳", "保"}) for item in candidates)
```

- [ ] **Step 2: Implement candidate loading**

In `app/engine/henan_recommendation.py`, replace the placeholder `return []` implementation with:

```python
from pathlib import Path

from app.loader.henan_data_loader import (
    find_best_historical_baseline,
    load_henan_admission_history,
    load_henan_enrollment_plans,
    load_henan_program_groups,
)


SEED_DIR = Path("data/seed")


def build_henan_candidates(profile: dict) -> list[dict]:
    if profile.get("source_province") not in (None, "河南"):
        raise ValueError("河南志愿推仅支持河南考生")

    groups = load_henan_program_groups(SEED_DIR)
    plans = load_henan_enrollment_plans(SEED_DIR)
    history = load_henan_admission_history(SEED_DIR)
    plans_by_key = {}
    for plan in plans:
        plans_by_key.setdefault(
            (plan.school_code, plan.major_group_code, plan.track, plan.batch),
            [],
        ).append(plan)

    candidates: list[dict] = []
    for group in groups:
        if group.track != profile.get("track"):
            continue
        ok, blocked, warnings = check_henan_eligibility(profile, group)
        group_plans = plans_by_key.get((group.school_code, group.major_group_code, group.track, group.batch), [])
        has_2026_plan = any(p.plan_count > 0 and p.review_status == "verified" for p in group_plans)
        has_verified_group = group.review_status == "verified"
        baseline = find_best_historical_baseline(
            history,
            school_code=group.school_code,
            group_code=group.major_group_code,
            major_names=group.included_majors,
            track=group.track,
            batch=group.batch,
        )
        has_verified_history = baseline is not None and baseline.review_status == "verified"
        bucket = classify_group_bucket(
            student_rank=profile.get("rank") or 0,
            adjusted_rank=baseline.adjusted_min_rank if baseline else None,
            has_2025_history=has_verified_history and baseline.year == 2025,
            has_2026_plan=has_2026_plan,
            has_verified_group=has_verified_group,
            confidence=group.confidence,
        )
        if bucket in {"稳", "保"} and not has_verified_history:
            bucket = "需人工复核"
        if not ok:
            bucket = "不推荐"
        candidates.append({
            "volunteer_unit": "院校专业组",
            "school_name": group.school_name,
            "school_code": group.school_code,
            "major_group_code": group.major_group_code,
            "major_group_name": group.major_group_name,
            "major_name": group.included_majors[0] if group.included_majors else "",
            "selected_majors": group.included_majors[:6],
            "track": group.track,
            "batch": group.batch,
            "bucket": bucket,
            "group_bucket": bucket,
            "major_bucket": bucket,
            "qualified": ok,
            "blocked_reasons": blocked,
            "warnings": warnings,
            "plan_count": sum(p.plan_count for p in group_plans),
            "review_status": "verified" if has_verified_group and has_2026_plan else "needs_review",
            "bucket_reason": "按2026河南专业组、招生计划、选科语种和历史位次综合判断",
        })
    return candidates
```

This implementation is not acceptable with `adjusted_rank=None` for normal candidates. Verified 2025/2024 history from Task 2B is part of this task, not a later release item.

- [ ] **Step 3: Verify**

Run:

```powershell
python -m pytest tests/engine/test_henan_candidate_generation.py tests/engine/test_henan_recommendation.py --basetemp .pytest-tmp
```

Expected: pass, and `build_henan_candidates()` no longer returns an unconditional empty list.

---

### Task 4: Add Henan Recommendation API

**Files:**
- Modify: `app/api/routers/henan.py`
- Test: `tests/api/test_henan_recommendation_api.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/henan/recommendation`

- [ ] **Step 1: Write failing API tests**

Create `tests/api/test_henan_recommendation_api.py`:

```python
from fastapi.testclient import TestClient

from app.api.main import app


def test_henan_recommendation_returns_data_readiness_and_buckets():
    client = TestClient(app)
    response = client.post("/api/v1/henan/recommendation", json={
        "score": 540,
        "rank": 45000,
        "track": "历史类",
        "source_province": "河南",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
        "strategy": "自动",
    })
    assert response.status_code == 200
    body = response.json()
    assert "data_ready" in body
    assert "buckets" in body
    assert set(body["buckets"].keys()) == {"冲", "稳", "保", "不推荐", "需人工复核"}
    assert "coverage" in body
```

- [ ] **Step 2: Implement endpoint**

Add to `app/api/routers/henan.py`:

```python
class HenanRecommendationRequest(BaseModel):
    score: int
    rank: int | None = None
    track: str
    source_province: str = "河南"
    primary_subject: str
    elective_subjects: list[str] = []
    exam_foreign_language: str = "英语"
    strategy: str = "自动"


@router.post("/recommendation")
def recommendation(req: HenanRecommendationRequest):
    profile = req.model_dump()
    coverage = build_actual_henan_coverage(_SEED_DIR)
    data_ready = True
    readiness_errors: list[str] = []
    try:
        assert_henan_recommendation_ready(coverage)
    except ValueError as exc:
        data_ready = False
        readiness_errors.append(str(exc))

    candidates = build_henan_candidates(profile)
    buckets = {"冲": [], "稳": [], "保": [], "不推荐": [], "需人工复核": []}
    for item in candidates:
        buckets.setdefault(item["bucket"], []).append(item)
    return {
        "data_ready": data_ready,
        "readiness_errors": readiness_errors,
        "coverage": coverage,
        "buckets": buckets,
    }
```

- [ ] **Step 3: Verify**

Run:

```powershell
python -m pytest tests/api/test_henan_recommendation_api.py tests/api/test_henan_api.py --basetemp .pytest-tmp
```

Expected: pass.

---

### Task 5: Wire Homepage To Henan Recommendation API

**Files:**
- Modify: `web-ui/src/api/types.ts`
- Modify: `web-ui/src/api/client.ts`
- Modify: `web-ui/src/pages/HomePage.tsx`
- Modify: `web-ui/src/components/ScoreForm.tsx`
- Test: `web-ui/e2e/henan-recommendation.spec.ts`

**Interfaces:**
- Consumes: `POST /api/v1/henan/recommendation`.

- [ ] **Step 1: Add frontend types and client**

In `web-ui/src/api/types.ts`, add:

```ts
export interface HenanRecommendationRequest {
  score: number;
  rank?: number | null;
  track: string;
  source_province?: string;
  primary_subject: string;
  elective_subjects?: string[];
  exam_foreign_language?: string;
  strategy?: "自动" | "保守" | "均衡" | "积极";
}

export interface HenanRecommendationResult {
  data_ready: boolean;
  readiness_errors: string[];
  coverage: Record<string, unknown>;
  buckets: Record<"冲" | "稳" | "保" | "不推荐" | "需人工复核", HenanTargetItem[]>;
}
```

In `web-ui/src/api/client.ts`, add:

```ts
export function henanRecommendation(req: HenanRecommendationRequest): Promise<HenanRecommendationResult> {
  return request<HenanRecommendationResult>("/henan/recommendation", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
```

- [ ] **Step 2: Replace homepage API call**

In `web-ui/src/pages/HomePage.tsx`, stop calling `advisory(req)` for the河南主页面. Call `henanRecommendation(...)` and render:

```text
数据未就绪 banner
冲 / 稳 / 保 / 不推荐 / 需人工复核 buckets
院校专业组 code/name
组内专业 1-6 个
plan_count
blocked reasons
warnings
```

- [ ] **Step 3: Keep old advisory compatibility out of homepage**

Do not delete `advisory()` from `client.ts`. Only stop using it on the河南志愿推 homepage.

- [ ] **Step 4: Verify**

Run:

```powershell
npm.cmd run build
```

Expected: TypeScript build passes.

---

### Task 6: Fix Target Evaluation To Use Real Candidates

**Files:**
- Modify: `app/api/routers/henan.py`
- Modify: `app/engine/henan_target_evaluation.py`
- Modify: `web-ui/src/pages/TargetEvaluationPage.tsx`
- Test: `tests/api/test_henan_api.py`
- Test: `web-ui/e2e/henan-target-evaluation.spec.ts`

**Interfaces:**
- Consumes: `build_henan_candidates(profile)`.

- [ ] **Step 1: Add API regression test for non-empty reachable data**

Add to `tests/api/test_henan_api.py`:

```python
def test_target_evaluation_uses_candidate_generator(monkeypatch):
    from app.api.routers import henan

    def fake_candidates(profile):
        return [{
            "school_name": "测试大学",
            "major_name": "法学",
            "major_group_code": "101",
            "major_group_name": "历史组",
            "bucket": "稳",
            "qualified": True,
            "blocked_reasons": [],
        }]

    monkeypatch.setattr(henan, "build_henan_candidates", fake_candidates)
    client = TestClient(app)
    r = client.post("/api/v1/henan/target-evaluation", json={
        "score": 600,
        "rank": 12000,
        "track": "历史类",
        "source_province": "河南",
        "target_school": "测试大学",
        "target_majors": [],
        "target_group": None,
    })
    body = r.json()
    assert body["overall_bucket"] == "可评估"
    assert body["items"][0]["bucket"] == "稳"
```

- [ ] **Step 2: Render data readiness**

Target page must show:

```text
专业组数据未就绪
招生计划待核验
没有达到冲稳保条件的专业或专业组
```

Use `readiness_errors` from recommendation endpoint or add readiness output to target endpoint.

- [ ] **Step 3: Verify**

Run:

```powershell
python -m pytest tests/api/test_henan_api.py tests/engine/test_henan_target_evaluation.py --basetemp .pytest-tmp
npm.cmd run build
```

Expected: pass.

---

### Task 7: Remove Or Hide Standalone Cost Page

**Files:**
- Modify: `web-ui/src/App.tsx`
- Modify: `web-ui/src/pages/HomePage.tsx`
- Modify: `web-ui/src/pages/TargetEvaluationPage.tsx`
- Test: `web-ui/e2e/navigation.spec.ts`

**Steps:**

- [ ] Remove the `/cost` route from `App.tsx`.
- [ ] Remove `UniversityCostPage` import from `App.tsx`.
- [ ] Ensure homepage recommendation cards show tuition/accommodation/four-year estimate when data is verified.
- [ ] Ensure target evaluation cards show cost or “费用待核验”.
- [ ] Run `npm.cmd run build`.

Expected: no standalone cost page in navigation or route table.

---

### Task 8: Add Browser Acceptance Tests

**Files:**
- Create: `web-ui/e2e/henan-recommendation.spec.ts`
- Create: `web-ui/e2e/henan-target-evaluation.spec.ts`

**Scenarios:**

- [ ] 首页默认标题为“河南志愿推”。
- [ ] 首页提交历史类 + 日语 + 分数/位次后，显示数据就绪或未就绪状态。
- [ ] 若数据未就绪，不显示假“稳/保”。
- [ ] 档位筛选点击“冲”只显示冲。
- [ ] 目标评估选择学校后，专业和专业组联动。
- [ ] 480 分历史类评估郑州大学，若无可达专业组，显示“不推荐”。
- [ ] 若 mock API 返回稳专业组，页面按专业组显示“稳”。

Run:

```powershell
npx.cmd playwright test web-ui/e2e/henan-recommendation.spec.ts web-ui/e2e/henan-target-evaluation.spec.ts
```

Expected: all pass after Playwright browser is installed.

---

### Task 9: Final Verification

Run:

```powershell
python -m pytest --basetemp .pytest-tmp
npm.cmd run build
python scripts/build_henan_coverage_report.py
```

Manual API checks:

```powershell
@'
from fastapi.testclient import TestClient
from app.api.main import app
c = TestClient(app)
print(c.get("/api/v1/henan/options").json())
print(c.post("/api/v1/henan/recommendation", json={
  "score": 540,
  "rank": 45000,
  "track": "历史类",
  "source_province": "河南",
  "primary_subject": "历史",
  "elective_subjects": ["政治", "地理"],
  "exam_foreign_language": "日语",
  "strategy": "自动"
}).json())
'@ | python -
```

Release acceptance:

- `build_henan_candidates()` is not an empty placeholder.
- Homepage no longer uses `/volunteer/advisory`.
- Target evaluation can return reachable `冲/稳/保` when candidate data exists.
- Real coverage report reflects actual seed/DB counts.
- Records with `plan_count=0` or `needs_review` cannot enter `稳/保`.
- UI clearly shows data-not-ready instead of fake recommendation.
- Standalone cost page removed or hidden.
