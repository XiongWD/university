# gaokao.cn Henan 2026 Field Completion Plan

## Goal

Use `www.gaokao.cn` plus the provided authenticated cookie to complete missing fields for the imported Henan 2026 history-track plan dataset.

Current imported baseline:

```text
raw file: data/raw/henan_2026/henan_2026_all_plans_merged.csv
normalized file: data/raw/henan_2026/normalized_catalog_from_gaokao_cn_history.csv
universities: 1,110
program groups: 2,355
plans: 8,266
track: 历史类
review_status: needs_review
```

Cookie file provided by user:

```text
C:\Users\Administrator\Downloads\cookies-2026-06-26.json
```

Do not commit the cookie file or cookie values. Scripts must accept a cookie-file path argument or environment variable and load cookies at runtime.

## Current Field Coverage

Available from `henan_2026_all_plans_merged.csv`:

- `school_id`
- `school_name`
- `sp_name`
- `num`
- `tuition`
- `length`
- `sg_info`
- `zslx_name`
- `remark`
- `special_group`
- `school_special_id`

Mapped into normalized catalog:

- `source_province = 河南`
- `year = 2026`
- `track = 历史类`
- `batch = 本科批` as provisional value
- `school_code = school_id`
- `school_name`
- `major_group_code = special_group`
- `major_group_name = school_name-special_group`
- `major_code = school_special_id`
- `major_name = sp_name`
- `plan_count = num`
- `primary_subject_requirement` from `sg_info`
- `elective_subject_requirement` from `sg_info`
- `tuition`
- `remarks = remark`
- `review_status = needs_review`

## Missing Fields To Complete

### Source Traceability

Required:

- exact `source_url` for each school/group/major plan row;
- page number or API request parameters if the source is API-backed;
- scrape timestamp;
- source response checksum;
- evidence that `school_id`, `special_group`, and `school_special_id` are gaokao.cn identifiers and whether they map to official education-exam codes.

Acceptance:

```text
Every row has source_url or source_api_endpoint + source_params.
Every row can be re-fetched from source identifiers.
No row is marked verified without source evidence.
```

### School Attributes

Required per `school_id`:

- official school code if different from gaokao.cn `school_id`;
- school origin province;
- city;
- public/private/Chinese-foreign cooperation ownership;
- undergraduate/vocational level;
- 985/211/双一流/省重点 tags;
- school official admission website;
- school official 2026 admission charter URL.

Acceptance:

```text
universities.yaml has province, city, ownership for all 1,110 schools.
Rows with unresolved official school code remain needs_review.
```

### Program Group Attributes

Required per `special_group`:

- official group code if gaokao.cn uses an internal ID;
- official displayed group name;
- batch confirmation: 本科批 / 专科批 / 提前批 / 专项计划;
- group category: 普通类 / 高校专项 / 地方专项 / 中外合作 / 高收费 / 校区;
- adjustment scope: group-internal adjustment only;
- whether the group is ordinary 48-parallel-volunteer compatible.

Acceptance:

```text
No 高校专项/提前批/特殊资格 row is mixed into ordinary本科批 recommendation buckets.
special_group is either verified as official group code or stored as gaokao.cn_internal_group_id.
```

### Major Attributes

Required per `school_special_id` or major row:

- official major code where available;
- major display name after removing package text only when safe;
- major class/package decomposition from `remark`;
- duration in years;
- tuition numeric value and unit;
- accommodation fee if available;
- campus;
- Chinese-foreign cooperation/high-fee marker.

Acceptance:

```text
Major package rows keep original package name and included majors.
Tuition is numeric or null with needs_review.
Accommodation remains null unless source explicitly provides it.
```

### Eligibility Restrictions

Required from `remark`, gaokao.cn detail pages, and university charters:

- accepted exam language;
- English-only restriction;
- Japanese candidate compatibility;
- public foreign language taught after enrollment;
- single-subject score requirements;
- oral test requirement;
- color blindness/color weakness restrictions;
- height/vision/sex/age/political-review requirements;
- special eligibility: 高校专项、地方专项、公费师范、定向医学生、公安、军校.

Acceptance:

```text
Japanese students are not treated as eligible when row text says 只招英语语种考生.
Rows with ambiguous language text stay needs_review and surface warning.
Physical/special-qualification blockers are visible in recommendation explanations.
```

### Historical Admission Baseline

This dataset does not contain historical admission ranks. Separate data is still needed:

- 2025 major-group minimum rank;
- 2024 major-group minimum rank;
- 2025/2024 major-level minimum rank where available;
- fallback school-batch rank with lower confidence.

Acceptance:

```text
No candidate enters 稳 or 保 without verified historical rank baseline.
```

## Suggested Crawler Architecture

Create a new script rather than modifying the importer directly:

```text
scripts/enrich_gaokao_cn_henan_2026.py
```

Inputs:

```text
--plans data/raw/henan_2026/henan_2026_all_plans_merged.json
--cookies C:\Users\Administrator\Downloads\cookies-2026-06-26.json
--out data/raw/henan_2026/gaokao_cn_enriched_plans.json
--normalized-out data/raw/henan_2026/normalized_catalog_from_gaokao_cn_history_enriched.csv
--cache-dir data/raw/henan_2026/gaokao_cn_cache
```

Runtime rules:

- Read cookies from the provided path at runtime.
- Never print cookie values.
- Never write cookie values into cache, logs, reports, CSV, or YAML.
- Rate-limit requests.
- Cache responses by endpoint + params checksum.
- On HTTP 401/403/captcha/redirect-to-login, stop and report blocked status.
- Do not bypass captcha, paywall, login limits, or anti-abuse protections.

## Discovery Steps For Other Agent

1. Inspect existing scrape scripts:

```text
scripts/scrape_all_pages.py
scripts/scrape_all_plans.py
scripts/scrape_all_plans_v2.py
scripts/scrape_missing_pages.py
scripts/verify_pagination.py
scripts/capture_page2.py
```

2. Identify the actual gaokao.cn API endpoints already used to produce:

```text
data/raw/henan_2026/henan_2026_all_plans_merged.json
```

3. For a small sample of rows, refetch details by:

```text
school_id
special_group
school_special_id
```

4. Record source request metadata:

```json
{
  "endpoint": "...",
  "params": {
    "school_id": "...",
    "special_group": "...",
    "school_special_id": "..."
  },
  "fetched_at": "...",
  "sha256": "..."
}
```

5. Expand to all 8,266 rows only after sample rows confirm field meaning.

## Output Files

Recommended outputs:

```text
data/raw/henan_2026/gaokao_cn_enriched_plans.json
data/raw/henan_2026/gaokao_cn_enrichment_report.json
data/raw/henan_2026/normalized_catalog_from_gaokao_cn_history_enriched.csv
data/raw/henan_2026/gaokao_cn_unresolved_fields.csv
```

Do not directly overwrite seed files during enrichment. First produce normalized CSV and report, then run:

```powershell
python scripts\import_henan_2026_catalog.py data\raw\henan_2026\normalized_catalog_from_gaokao_cn_history_enriched.csv
python scripts\build_henan_coverage_report.py
```

## Review Status Rules

Keep `needs_review` when:

- source URL/API params are missing;
- field exists only in free text and parser confidence is low;
- school/group/major code meaning is not confirmed;
- language/physical restriction is ambiguous;
- row is not ordinary本科批.

Allow `verified` only when:

- the row can be re-fetched from gaokao.cn with stable identifiers;
- plan count, school, group, major, subject requirement, and tuition match source;
- row category/batch is confirmed;
- code mapping is confirmed or explicitly labeled as gaokao.cn internal ID;
- no unresolved critical eligibility field remains.

## Final Acceptance Checklist

- `normalized_catalog_from_gaokao_cn_history_enriched.csv` still has 8,266 rows unless rows are explicitly excluded with reason.
- 1,110 schools have province/city/ownership or documented missing reason.
- 2,355 groups have batch/category/subject requirements.
- All language restriction rows are parsed into structured fields or flagged.
- All special-qualification rows are excluded from ordinary recommendation buckets or flagged.
- `build_henan_coverage_report.py` shows 8,266 nonzero plans.
- `verified_*` counts increase only for rows with source evidence.
