# Henan 2026 Ordinary Undergraduate History-Track Data Backfill Task

## Scope

This task is limited to:

```text
河南 2026 普通本科批 历史类
```

Do not work on:

- 物理类
- 普通专科批
- 提前批
- 艺体类
- 公安 / 军校 / 定向 / 公费师范等独立批次链路

The goal is to backfill the current dataset until it is usable for:

- 首页专业推荐
- target-evaluation 目标评估

within the narrowed scope above.

## Current Baseline

Current coverage state from `python scripts/build_henan_coverage_report.py`:

```text
universities_2026: 1110
program_groups_2026: 2355
enrollment_plans_henan_2026: 8266

verified_program_groups_2026: 200
verified_enrollment_plans_2026: 600
verified_2025_history: 923
verified_2024_history: 1078
nonzero_enrollment_plans_2026: 8266
```

Important caveat:

```text
2025 / 2024 historical records are currently school-level only.
They are not yet major-group-level or major-level baselines.
```

Already present in the seed:

- `data/seed/henan/universities.yaml`
- `data/seed/henan/program_groups_2026.yaml`
- `data/seed/henan/enrollment_plans_2026.yaml`
- `data/seed/henan/admission_history_2025.yaml`
- `data/seed/henan/admission_history_2024.yaml`

Already present in datasets:

- `data/datasets/henan_2025_score_rank.csv`
- `data/datasets/henan_2024_score_rank.csv`

## Main Gaps To Backfill

This single agent should backfill these items in order:

1. Upgrade historical baselines from `school` to `major_group` where possible.
2. Backfill `single_subject_requirements`.
3. Backfill `public_foreign_languages`.
4. Backfill `accommodation`.
5. Expand `verified` coverage for 2026 groups and plans.
6. Write verification results back into the enrichment report.
7. Re-run coverage and tests and leave the seed in a consistent state.

## Required Output Files

The agent must update or create only the files below as needed:

```text
data/seed/henan/admission_history_2025.yaml
data/seed/henan/admission_history_2024.yaml
data/seed/henan/program_groups_2026.yaml
data/seed/henan/enrollment_plans_2026.yaml
data/seed/henan/data_coverage_report.json
data/seed/henan/verified_groups.txt
data/raw/henan_2026/gaokao_cn_enrichment_report.json
```

If script changes are required, limit them to:

```text
scripts/build_henan_admission_history.py
scripts/verify_gaokao_cn_sample.py
scripts/promote_verified_groups.py
scripts/import_henan_2026_catalog.py
app/loader/henan_data_loader.py
app/engine/henan_recommendation.py
app/models/henan_data.py
tests/
```

Do not broaden scope outside the narrowed dataset.

## Sequential Work Plan

### Step 1. Verify Current Inputs

Before modifying data, confirm:

```powershell
python scripts\build_henan_coverage_report.py
python -m pytest -q --disable-warnings --basetemp .pytest-tmp
```

Record:

- current coverage counts;
- current pytest total and runtime;
- whether any tests already fail.

Do not rely on stale numbers in prior notes.

### Step 2. Upgrade Historical Admission Baselines

Target:

```text
2025 / 2024 历史类 普通本科批
school-level -> major_group-level
```

Rules:

- Preserve existing `school` rows as fallback if needed.
- Add `major_group` rows whenever a reliable mapping exists.
- If a source only supports school-level, keep it but do not pretend it is group-level.
- `review_status=verified` only when the row has:
  - valid source trace;
  - valid score;
  - valid rank;
  - clear mapping to the 2026 history-track ordinary undergraduate group.

Required fields for new `major_group` rows:

```text
year
track=历史类
batch=本科批
school_code
school_name
major_group_code
major_group_name
min_score
min_rank
data_granularity=major_group
source_name
source_url
as_of
confidence
review_status
```

Acceptance for this step:

- `admission_history_2025.yaml` contains verified `major_group` rows.
- `admission_history_2024.yaml` contains verified `major_group` rows.
- There is measurable overlap between:
  - `(school_code, major_group_code, track, batch)` in admission history
  - `(school_code, major_group_code, track, batch)` in 2026 program groups

Minimum target:

```text
At least 500 verified 2025 major_group rows
At least 300 verified 2024 major_group rows
```

If full coverage is not achievable, prioritize:

- 河南省内院校
- 用户高频关注院校
- 历史类热门专业组

### Step 3. Backfill Single-Subject Requirements

Target field:

```text
program_groups_2026.yaml -> single_subject_requirements
```

Expected structure:

```yaml
single_subject_requirements:
  - subject: 英语
    min_score: 110
    hard: true
    source_text: "英语单科成绩不低于110分"
```

Backfill from:

- 招生章程
- 招生目录备注
- gaokao.cn remark text when explicit

Prioritize:

- 英语
- 商务英语
- 翻译
- 小语种
- 国际经济与贸易 / 国际商务 / 中外合作中常见英语要求

Acceptance for this step:

- `single_subject_requirements > 0`
- At least 50 real groups have explicit single-subject requirements where source text supports it.
- Recommendation eligibility blocks candidates correctly when the profile misses the requirement.

### Step 4. Backfill Exam Language and Public Foreign Language

Target fields:

```text
program_groups_2026.yaml -> accepted_exam_languages
program_groups_2026.yaml -> public_foreign_languages
```

Rules:

- Distinguish between:
  - `只招英语语种考生`
  - `不限语种，但入校后公共外语只开英语`
  - `非英语语种慎报`
- Hard restrictions belong in `accepted_exam_languages`.
- Public-teaching language belongs in `public_foreign_languages`.
- Soft wording that is not a hard blocker should still remain traceable in source text or warnings.

Acceptance for this step:

- `public_foreign_languages > 0`
- `accepted_exam_languages` coverage increases from current baseline
- Japanese-candidate scenarios can be separated into:
  - blocked;
  - allowed with warning;
  - fully allowed

### Step 5. Backfill Accommodation

Target field:

```text
enrollment_plans_2026.yaml -> accommodation
```

Rules:

- Standardize as annual accommodation fee when explicit.
- If the source gives a range, store a normalized numeric value only if the rule is consistent.
- If the source is ambiguous, keep null and do not fabricate a number.

Prioritize:

- 河南省内普通本科历史类院校
- 高频目标院校
- 中外合作 / 校区差异明显院校

Acceptance for this step:

- `accommodation > 0`
- The value is traceable to a source
- No fabricated fee rows

### Step 6. Expand Verified Coverage

Use the existing verification flow and extend it.

Scripts:

```text
scripts/verify_gaokao_cn_sample.py
scripts/promote_verified_groups.py
```

Verification strategy:

- Do not do blind random-only sampling.
- Prioritize:
  - 河南省内院校
  - 热门历史类院校
  - 用户高频目标院校
  - 中外合作 / 专项 / 语言限制组

Minimum target after promotion:

```text
verified_program_groups_2026 >= 800
verified_enrollment_plans_2026 >= 2500
```

Keep:

- `review_status=needs_review` for rows not yet verified;
- no fake promotion without source match.

### Step 7. Write Verification Back Into Report

Current problem:

```text
data/raw/henan_2026/gaokao_cn_enrichment_report.json
```

may still show zero verification summary even after seed promotion.

This step must update the report so it contains real values for:

```json
{
  "verification": {
    "matched": "...",
    "mismatched": "...",
    "failed": "...",
    "details": [...]
  }
}
```

At minimum, the top-level counts must reflect the actual latest verification run.

### Step 8. Final Consistency Pass

Re-run:

```powershell
python scripts\build_henan_coverage_report.py
python -m pytest -q --disable-warnings --basetemp .pytest-tmp
```

Also confirm that loader-consumed values are really present:

- `single_subject_requirements`
- `public_foreign_languages`
- `accommodation`
- `major_group` historical baseline rows

Do not leave a state where YAML changed but loader / engine / tests still assume old shapes.

## Final Acceptance Checklist

The task is complete only if all of the following are true:

```text
Scope remains 河南 2026 普通本科批 历史类 only
verified_program_groups_2026 >= 800
verified_enrollment_plans_2026 >= 2500
verified_2025_history contains major_group rows
verified_2024_history contains major_group rows
single_subject_requirements > 0
public_foreign_languages > 0
accommodation > 0
coverage report matches actual seed contents
pytest passes
enrichment report includes real verification counts
```

## Required Completion Note

At the end, the agent must leave a short written summary including:

1. what files were changed;
2. the final coverage numbers;
3. how many verified 2025 / 2024 rows are now `major_group`;
4. how many groups have:
   - `single_subject_requirements`
   - `public_foreign_languages`
5. how many plans now have `accommodation`;
6. final pytest total and runtime;
7. any remaining honest gaps that still require another pass.

## Non-Negotiable Rules

- Do not fabricate scores, ranks, fees, or restrictions.
- Do not mark data `verified` without a reproducible source.
- Do not expand into physics track or non-undergraduate batches.
- Do not weaken recommendation gating just to make more rows appear reachable.
- Keep source traceability intact for any backfilled field.
