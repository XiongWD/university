"""
回填 admission_history_2025.yaml 中缺失的位次（min_rank）。
在不重新抓取 gaokao.cn API 的前提下，利用 score-rank CSV 补齐位次。

用法：python scripts/backfill_henan_history_rank.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

# 复用 build 脚本中的工具函数
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.build_henan_admission_history import load_score_rank_csv, score_to_rank

SCORE_RANK_2025 = Path("data/datasets/henan_2025_score_rank.csv")
HISTORY_2025_PATH = Path("data/seed/henan/admission_history_2025.yaml")


def main():
    rank_entries = load_score_rank_csv(SCORE_RANK_2025)
    print(f"Score-rank entries loaded: {len(rank_entries)}")

    records = yaml.safe_load(HISTORY_2025_PATH.read_text(encoding="utf-8"))
    if not records:
        print("No records found.")
        return

    stats = {"total": len(records), "already_has_rank": 0, "filled": 0, "still_missing": 0}
    still_missing: list[dict] = []

    for r in records:
        if r.get("min_rank") and r["min_rank"] > 0:
            stats["already_has_rank"] += 1
            continue

        if not r.get("min_score") or r["min_score"] <= 0:
            continue  # no score either — can't help

        new_rank = score_to_rank(rank_entries, r["min_score"])
        if new_rank and new_rank > 0:
            r["min_rank"] = new_rank
            r["review_status"] = "verified"
            stats["filled"] += 1
        else:
            stats["still_missing"] += 1
            still_missing.append(r)

    # 写回 YAML
    HISTORY_2025_PATH.write_text(
        yaml.safe_dump(records, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print(f"\n=== 回填统计 ===")
    print(f"  总记录: {stats['total']}")
    print(f"  已有位次: {stats['already_has_rank']}")
    print(f"  本次回填: {stats['filled']}")
    print(f"  仍缺失: {stats['still_missing']}")

    if still_missing:
        print(f"\n仍缺失的条目（{len(still_missing)} 条）:")
        for r in still_missing[:20]:
            print(f"  {r['school_code']:>6} {r['school_name']:20s} score={r.get('min_score')}")


if __name__ == "__main__":
    main()
