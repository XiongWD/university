"""Backfill gaokao.cn fetch traceability into current Henan 2026 seed YAML.

Reads the enriched normalized CSV and copies:

- source_api_endpoint
- source_params
- source_page
- source_response_checksum

into the current seed files without changing recommendation-facing business data.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import yaml


CSV_PATH = Path("data/raw/henan_2026/normalized_catalog_from_gaokao_cn_history_enriched.csv")
SEED_DIR = Path("data/seed/henan")


def _read_csv_rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))


def _dump_yaml(path: Path, rows: list[dict]) -> None:
    path.write_text(yaml.safe_dump(rows, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main() -> None:
    csv_rows = _read_csv_rows(CSV_PATH)

    plan_trace = {}
    group_trace: dict[tuple[str, str, str, str], dict] = {}
    university_trace: dict[str, dict] = {}
    group_checksums: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    university_checksums: dict[str, set[str]] = defaultdict(set)

    for row in csv_rows:
        trace = {
            "source_api_endpoint": row.get("source_api_endpoint", "") or "",
            "source_params": row.get("source_params", "") or "",
            "source_page": row.get("source_page", "") or "",
            "source_response_checksum": row.get("source_response_checksum", "") or "",
        }
        plan_key = (
            row.get("year", ""),
            row.get("track", ""),
            row.get("school_code", ""),
            row.get("major_group_code", ""),
            row.get("major_name", ""),
        )
        group_key = (
            row.get("year", ""),
            row.get("track", ""),
            row.get("school_code", ""),
            row.get("major_group_code", ""),
        )
        school_key = row.get("school_code", "")

        plan_trace[plan_key] = trace
        group_trace.setdefault(group_key, trace.copy())
        university_trace.setdefault(school_key, trace.copy())
        if trace["source_response_checksum"]:
            group_checksums[group_key].add(trace["source_response_checksum"])
            university_checksums[school_key].add(trace["source_response_checksum"])

    universities = yaml.load((SEED_DIR / "universities.yaml").read_text(encoding="utf-8"), Loader=yaml.CSafeLoader) or []
    groups = yaml.load((SEED_DIR / "program_groups_2026.yaml").read_text(encoding="utf-8"), Loader=yaml.CSafeLoader) or []
    plans = yaml.load((SEED_DIR / "enrollment_plans_2026.yaml").read_text(encoding="utf-8"), Loader=yaml.CSafeLoader) or []

    university_updates = 0
    for row in universities:
        trace = university_trace.get(str(row.get("school_code", "")))
        if not trace:
            continue
        for key, value in trace.items():
            if value:
                row[key] = value
        checksums = sorted(university_checksums.get(str(row.get("school_code", "")), set()))
        if checksums:
            row["source_response_checksum"] = "|".join(checksums[:20])
        university_updates += 1

    group_updates = 0
    for row in groups:
        key = (
            str(row.get("year", "")),
            str(row.get("track", "")),
            str(row.get("school_code", "")),
            str(row.get("major_group_code", "")),
        )
        trace = group_trace.get(key)
        if not trace:
            continue
        row["source_api_endpoint"] = trace.get("source_api_endpoint", "")
        row["source_params"] = trace.get("source_params", "")
        row["source_page"] = trace.get("source_page", "")
        checksums = sorted(group_checksums.get(key, set()))
        if checksums:
            row["source_response_checksum"] = "|".join(checksums[:20])
        group_updates += 1

    plan_updates = 0
    for row in plans:
        key = (
            str(row.get("year", "")),
            str(row.get("track", "")),
            str(row.get("school_code", "")),
            str(row.get("major_group_code", "")),
            str(row.get("major_name", "")),
        )
        trace = plan_trace.get(key)
        if not trace:
            continue
        for field in ("source_api_endpoint", "source_params", "source_page", "source_response_checksum"):
            row[field] = trace.get(field, "")
        plan_updates += 1

    _dump_yaml(SEED_DIR / "universities.yaml", universities)
    _dump_yaml(SEED_DIR / "program_groups_2026.yaml", groups)
    _dump_yaml(SEED_DIR / "enrollment_plans_2026.yaml", plans)

    print(
        f"backfilled traceability: universities={university_updates}, "
        f"groups={group_updates}, plans={plan_updates}"
    )


if __name__ == "__main__":
    main()
