"""
从 gaokao.cn 公开 API 提取 2025/2024 历史录取最低分，转换为位次，
生成 admission_history YAML 文件。使用校内兜底（school-batch 级别）。

无需 Cookie / Playwright，仅调用 static-data.gaokao.cn 公开 JSON。
2025 位次映射使用 data/datasets/henan_2025_score_rank.csv。
2024 尚无 score-rank CSV，仅输出分数（位次留空）。
"""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HenanHistoryBuilder/1.0"
GAOKAO_STATIC = "https://static-data.gaokao.cn/www/2.0"
HISTORY_TRACK_TYPE = "2074"  # gaokao.cn type code for 历史类
# 2024 used different type codes (1=本科一批, 2=本科二批 pre-merger)

# 2025 score-rank CSV path
SCORE_RANK_2025 = Path("data/datasets/henan_2025_score_rank.csv")
SCORE_RANK_2024 = Path("data/datasets/henan_2024_score_rank.csv")

OUT_2025 = Path("data/seed/henan/admission_history_2025.yaml")
OUT_2024 = Path("data/seed/henan/admission_history_2024.yaml")


def load_score_rank_csv(path: Path) -> list[dict]:
    """Load score-rank CSV and return rows matching 历史类."""
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("综合", "").strip() == "历史类":
                rows.append({
                    "score": int(row["最低分"]),
                    "cumulative": int(row["累计"]),
                })
    return sorted(rows, key=lambda x: x["score"], reverse=True)


def score_to_rank(entries: list[dict], score: int) -> int | None:
    """Exact match score→rank, or fallback to nearest higher score's rank.

    当分数在CSV中无精确匹配时，返回最近较高分数的累计位次。
    因为分数断层处表示无人考取该分数，累计位次不变。
    entries 已按分数降序排列。
    """
    if not entries:
        return None
    for i, e in enumerate(entries):
        if e["score"] == score:
            return e["cumulative"]
        if e["score"] < score:
            # 未找到精确匹配：当前是首个低于目标分数的条目
            # 返回上一条（更高分数）的累计位次
            if i > 0:
                return entries[i - 1]["cumulative"]
            return None  # 目标分数超过CSV最高分
    # 目标分数低于CSV最低分：返回最低分对应的位次
    return entries[-1]["cumulative"]


def fetch_school_info(school_id: str) -> dict | None:
    """Fetch /school/{id}/info.json for a single school."""
    url = f"{GAOKAO_STATIC}/school/{school_id}/info.json?a=www.gaokao.cn"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("data")
    except Exception:
        return None


def extract_history_scores(info: dict) -> dict:
    """从 school info 提取河南历史类2025/2024最低分。

    返回:
        {"2025_score": int|None, "2024_score": int|None}
    """
    pro_min = info.get("pro_type_min", {})
    henan = pro_min.get("41", []) if isinstance(pro_min.get("41"), list) else []

    result = {"2025_score": None, "2024_score": None}

    for entry in henan:
        year = entry.get("year")
        types = entry.get("type", {})

        if year == 2025:
            # type 2074 = 历史类
            if HISTORY_TRACK_TYPE in types:
                result["2025_score"] = int(types[HISTORY_TRACK_TYPE])

        elif year == 2024:
            # 2024 used type 1 (本科一批) ≈ history track equivalent
            for t in ("1", "2"):
                if t in types:
                    val = int(types[t])
                    if result["2024_score"] is None or val > result["2024_score"]:
                        result["2024_score"] = val

    return result


def build_history_entry(
    school_id: str,
    school_name: str,
    year: int,
    score: int | None,
    rank: int | None,
    data_granularity: str = "school",
) -> dict:
    return {
        "year": year,
        "track": "历史类",
        "school_code": school_id,
        "school_name": school_name,
        "major_group_code": None,
        "major_group_name": "",
        "major_name": None,
        "min_score": score,
        "min_rank": rank,
        "avg_score": None,
        "avg_rank": None,
        "plan_count": None,
        "batch": "本科批",
        "data_granularity": data_granularity,
        "source_name": "gaokao.cn 院校信息 API",
        "source_url": f"{GAOKAO_STATIC}/school/{school_id}/info.json",
        "as_of": "2026-06-27",
        "confidence": 0.6,
        "review_status": "verified" if (score and rank) else "needs_review",
    }


def main():
    # Load score-rank data for 2025
    rank_2025 = load_score_rank_csv(SCORE_RANK_2025)
    rank_2024 = load_score_rank_csv(SCORE_RANK_2024)
    print(f"Score-rank entries: 2025={len(rank_2025)}, 2024={len(rank_2024)}")

    # Load school IDs from our enriched plans
    plans = json.loads(Path("data/raw/henan_2026/gaokao_cn_enriched_plans.json").read_text(encoding="utf-8"))
    school_ids = sorted(set(str(p.get("school_code", "")) for p in plans))
    print(f"Unique schools: {len(school_ids)}")

    # Fetch historical scores for all schools
    history_2025: list[dict] = []
    history_2024: list[dict] = []
    stats = {"fetched": 0, "with_2025": 0, "with_2024": 0, "failed": 0}

    for i, sid in enumerate(school_ids):
        info = fetch_school_info(sid)
        if not info:
            stats["failed"] += 1
            continue

        stats["fetched"] += 1
        name = info.get("name", "")

        scores = extract_history_scores(info)

        # 2025
        if scores["2025_score"]:
            rank = score_to_rank(rank_2025, scores["2025_score"])
            history_2025.append(build_history_entry(
                sid, name, 2025, scores["2025_score"], rank
            ))
            stats["with_2025"] += 1

        # 2024
        if scores["2024_score"]:
            rank = score_to_rank(rank_2024, scores["2024_score"]) if rank_2024 else None
            history_2024.append(build_history_entry(
                sid, name, 2024, scores["2024_score"], rank
            ))
            stats["with_2024"] += 1

        if (i + 1) % 200 == 0:
            print(f"  Progress: {i+1}/{len(school_ids)} ({stats['fetched']} ok, {stats['with_2025']} with 2025)")

        time.sleep(0.15)  # rate limit

    print(f"\n=== Summary ===")
    print(f"  Schools: {stats['fetched']}/{len(school_ids)} fetched")
    print(f"  With 2025 score: {stats['with_2025']}")
    print(f"  With 2024 score: {stats['with_2024']}")
    print(f"  Failed: {stats['failed']}")

    # Write YAML files
    OUT_2025.parent.mkdir(parents=True, exist_ok=True)

    OUT_2025.write_text(
        yaml.safe_dump(history_2025, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\n  Written: {OUT_2025} ({len(history_2025)} records)")

    OUT_2024.write_text(
        yaml.safe_dump(history_2024, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"  Written: {OUT_2024} ({len(history_2024)} records)")

    # Also output a quick stats report
    report = {
        "total_schools": len(school_ids),
        "fetched": stats["fetched"],
        "with_2025_score_and_rank": stats["with_2025"],
        "with_2024_score_and_rank": stats["with_2024"],
        "failed": stats["failed"],
    }
    print(f"\n  Report: {json.dumps(report, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
