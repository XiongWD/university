"""导入 2025/2024 河南历史录取 normalized CSV → YAML（design Task 2B）。

接受官方/人工标准化历史 CSV，按年份写入 admission_history_{year}.yaml。
校验：verified 行必须有 min_rank>0；保留 source_url/source_published_at 可追溯。
"""
import argparse
import csv
import sys
from pathlib import Path

import yaml

ALLOWED_GRANULARITY = {"major", "major_group", "school_batch", "school"}


def main() -> int:
    parser = argparse.ArgumentParser(description="导入河南历史录取")
    parser.add_argument("csv_path", help="normalized CSV 路径")
    parser.add_argument("--year", type=int, required=True, choices=(2024, 2025))
    args = parser.parse_args()

    source = Path(args.csv_path)
    rows = list(csv.DictReader(source.read_text(encoding="utf-8-sig").splitlines()))

    records: list[dict] = []
    for row in rows:
        review_status = row.get("review_status", "verified")
        min_rank = int(row.get("min_rank") or 0)
        # verified 行必须有正 min_rank（design Task 2B 强制）
        if review_status == "verified" and min_rank <= 0:
            raise ValueError(
                f"verified 历史行缺 min_rank: {row.get('school_name')} {row.get('major_name')}"
            )
        granularity = row.get("data_granularity", "major")
        if granularity not in ALLOWED_GRANULARITY:
            raise ValueError(f"data_granularity 非法: {granularity}")

        records.append({
            "year": int(row["year"]),
            "track": row["track"],
            "school_code": row["school_code"],
            "school_name": row["school_name"],
            "major_group_code": row.get("major_group_code") or None,
            "major_group_name": row.get("major_group_name", ""),
            "major_name": row.get("major_name") or None,
            "min_score": int(row["min_score"]) if row.get("min_score") else None,
            "min_rank": min_rank or None,
            "avg_score": int(row["avg_score"]) if row.get("avg_score") else None,
            "plan_count": int(row["plan_count"]) if row.get("plan_count") else None,
            "batch": row["batch"],
            "data_granularity": granularity,
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "as_of": row.get("source_published_at") or row.get("as_of", ""),
            "confidence": float(row.get("confidence", 0.8)),
            "review_status": review_status,
        })

    out = Path(f"data/seed/henan/admission_history_{args.year}.yaml")
    out.write_text(yaml.safe_dump(records, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"imported {len(records)} {args.year} history records -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
