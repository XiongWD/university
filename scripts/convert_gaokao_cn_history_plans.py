"""Convert gaokao.cn Henan 2026 history-track plans to normalized catalog CSV.

Input is the merged scrape file:
data/raw/henan_2026/henan_2026_all_plans_merged.csv

Output is compatible with scripts/import_henan_2026_catalog.py. All rows are
marked needs_review because school codes, source pages, language restrictions,
and school attributes still need field-level verification.
"""
from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path


OUTPUT_FIELDS = [
    "source_province",
    "school_origin_province",
    "school_code",
    "school_name",
    "year",
    "batch",
    "track",
    "major_group_code",
    "major_group_name",
    "major_code",
    "major_name",
    "plan_count",
    "primary_subject_requirement",
    "elective_subject_requirement",
    "accepted_exam_languages",
    "public_foreign_languages",
    "tuition",
    "accommodation",
    "remarks",
    "source_name",
    "source_url",
    "source_page",
    "as_of",
    "review_status",
]


def parse_elective_requirement(value: str) -> str:
    """Return a YAML/JSON-compatible dict literal consumed by the existing importer."""
    if "再选不限" in value:
        return "{}"
    require: list[str] = []
    for subject in ("思想政治", "地理", "生物", "化学"):
        if subject in value:
            require.append(subject)
    if not require:
        return "{}"
    quoted = ", ".join(f'"{subject}"' for subject in require)
    return f'{{"require": [{quoted}], "any_of": []}}'


def primary_subject(value: str) -> str:
    if "首选历史" in value:
        return "历史"
    if "首选物理" in value:
        return "物理"
    return ""


def track(value: str) -> str:
    if "首选历史" in value:
        return "历史类"
    if "首选物理" in value:
        return "物理类"
    return ""


def clean_int(value: str) -> str:
    value = (value or "").strip()
    return value if re.fullmatch(r"\d+", value) else ""


def convert(input_csv: Path, output_csv: Path, *, source_url: str, as_of: str) -> int:
    rows = list(csv.DictReader(input_csv.open(encoding="utf-8-sig", newline="")))
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in rows:
            sg_info = row.get("sg_info", "")
            school_id = row.get("school_id", "").strip()
            group_code = row.get("special_group", "").strip()
            major_code = row.get("school_special_id", "").strip()
            plan_count = clean_int(row.get("num", ""))
            if not school_id or not group_code or not major_code or not plan_count:
                continue

            writer.writerow({
                "source_province": "河南",
                "school_origin_province": "",
                "school_code": school_id,
                "school_name": row.get("school_name", "").strip(),
                "year": "2026",
                "batch": "本科批",
                "track": track(sg_info),
                "major_group_code": group_code,
                "major_group_name": f'{row.get("school_name", "").strip()}-{group_code}',
                "major_code": major_code,
                "major_name": row.get("sp_name", "").strip(),
                "plan_count": plan_count,
                "primary_subject_requirement": primary_subject(sg_info),
                "elective_subject_requirement": parse_elective_requirement(sg_info),
                "accepted_exam_languages": "",
                "public_foreign_languages": "",
                "tuition": clean_int(row.get("tuition", "")),
                "accommodation": "",
                "remarks": row.get("remark", "").strip(),
                "source_name": "gaokao.cn 2026 河南历史类招生计划",
                "source_url": source_url,
                "source_page": "",
                "as_of": as_of,
                "review_status": "needs_review",
            })
    return sum(1 for _ in csv.DictReader(output_csv.open(encoding="utf-8-sig", newline="")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert gaokao.cn Henan 2026 history-track plans")
    parser.add_argument(
        "--input",
        default="data/raw/henan_2026/henan_2026_all_plans_merged.csv",
        help="Merged gaokao.cn scrape CSV",
    )
    parser.add_argument(
        "--output",
        default="data/raw/henan_2026/normalized_catalog_from_gaokao_cn_history.csv",
        help="Output normalized catalog CSV",
    )
    parser.add_argument("--source-url", default="https://www.gaokao.cn/")
    parser.add_argument("--as-of", default=datetime.now().date().isoformat())
    args = parser.parse_args()

    count = convert(Path(args.input), Path(args.output), source_url=args.source_url, as_of=args.as_of)
    print(f"converted {count} rows -> {args.output}")


if __name__ == "__main__":
    main()
