"""导入 2026 河南招生目录 normalized CSV → YAML（design Task 2）。

接受从官方目录人工/OCR 标准化的 CSV，产 universities/program_groups/enrollment_plans。
保留 source_url/as_of/review_status 每行可追溯。供后续全量增量导入用。
当前 seed 用方案 A 已核实的核心校真实数据手工构造。
"""
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

    universities: dict[str, dict] = {}
    groups: dict[tuple, dict] = {}
    plans: list[dict] = []

    for row in rows:
        school_code = row["school_code"]
        universities[school_code] = {
            "school_code": school_code,
            "school_name": row["school_name"],
            "province": row["school_origin_province"],
            "city": row.get("city", ""),
            "ownership": row.get("ownership", ""),
            "school_level": row.get("school_level", ""),
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
        if row.get("major_code") and row["major_code"] not in group["major_codes"]:
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
    (out_dir / "universities.yaml").write_text(
        yaml.safe_dump(list(universities.values()), allow_unicode=True, sort_keys=False), encoding="utf-8")
    (out_dir / "program_groups_2026.yaml").write_text(
        yaml.safe_dump(list(groups.values()), allow_unicode=True, sort_keys=False), encoding="utf-8")
    (out_dir / "enrollment_plans_2026.yaml").write_text(
        yaml.safe_dump(plans, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"imported {len(universities)} universities, {len(groups)} groups, {len(plans)} plans")


if __name__ == "__main__":
    main()
