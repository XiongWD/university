"""合并 heao 历史录取 CSV：bridge（志愿组号权威）优先 + matched 补缺。

【为什么 bridge 优先】matched 用专业名 Jaccard 匹配 heao 组，存在误配（2025 验证：
13 处冲突全部是 matched 错、bridge 对）。bridge 基于真实志愿组号(zyzh)直接桥接，
同志愿组号=同投档线，是河南新高考专业组模式的权威语义。

【合并规则】按 (major_group_code, year, data_granularity) 去重：
  1. bridge 专业组级行优先（权威位次）
  2. matched 专业组级行补 bridge 未覆盖的组
  3. matched 院校级(school)行全部保留（引擎不用于判档，仅溯源展示，不冲突）
输出最终 CSV，供 import_henan_admission_history.py 导入。
"""
import csv
import sys
from pathlib import Path

D = Path("data/raw/henan_2026/heao_admission")


def load(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def merge_year(year: str) -> int:
    bridge = load(D / f"admission_history_bridge_{year}.csv")
    matched = load(D / f"admission_history_matched_{year}.csv")

    # bridge 专业组级优先，建已覆盖键
    seen: set[tuple] = set()
    out: list[dict] = []
    for r in bridge:
        if r.get("data_granularity") != "major_group":
            continue
        key = (r["major_group_code"], r["year"], r["data_granularity"])
        if r["major_group_code"] and key not in seen:
            seen.add(key)
            out.append(r)
    n_bridge = len(out)

    # matched 补缺：专业组级未覆盖的 + 全部院校级
    n_grp_fill = 0
    n_school = 0
    for r in matched:
        gran = r.get("data_granularity")
        if gran == "major_group":
            key = (r["major_group_code"], r["year"], r["data_granularity"])
            if r["major_group_code"] and key not in seen:
                seen.add(key)
                out.append(r)
                n_grp_fill += 1
        elif gran == "school":
            out.append(r)
            n_school += 1

    cols = ["school_code", "yxdh", "school_name", "zyzh", "major_group_code",
            "major_group_name", "major_name", "year", "track", "batch",
            "min_score", "min_rank", "data_granularity", "source_name",
            "source_url", "confidence", "review_status"]
    out_csv = D / f"admission_history_final_{year}.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({c: r.get(c, "") for c in cols})

    n_grp_total = sum(1 for r in out if r.get("data_granularity") == "major_group")
    print(f"{year}: bridge专业组{n_bridge} + matched专业组补缺{n_grp_fill} + 院校级{n_school}"
          f" = 专业组级{n_grp_total} 行 → {out_csv.name}")
    return n_grp_total


if __name__ == "__main__":
    for yr in ("2024", "2025"):
        merge_year(yr)
