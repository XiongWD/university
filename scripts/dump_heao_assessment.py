"""
把 heao getSchoolList 的 raw JSON 格式化为结构化 YAML，便于人工审核与前端读取。

输入：data/evaluate/raw/01_*.json ... 13_*.json（API 原始响应）
输出：data/seed/henan/heao_assessment_2025.yaml（结构化权威数据）

结构：每个学校含 yxdh(院校代码)、各专业组(zyzh)、科目要求、2025/2024 历年录取
（最低分/最高分/最低位次/平均分/录取数），以及用一分一段表换算的 2026 等位分。
"""
import json
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.engine.henan_recommendation import (  # noqa: E402
    _load_score_rank_entries,
    _score_to_rank,
    _rank_to_score,
)

RAW_DIR = PROJECT_ROOT / "data" / "evaluate" / "raw"
OUT_FILE = PROJECT_ROOT / "data" / "seed" / "henan" / "heao_assessment_2025.yaml"

BROTHER_SCORE = 480
BROTHER_RANK = 73822


def score_to_rank(year: int, score: int) -> int | None:
    entries = _load_score_rank_entries(year, "历史类")
    return _score_to_rank(entries, score)


def rank_to_score(year: int, rank: int) -> int | None:
    entries = _load_score_rank_entries(year, "历史类")
    return _rank_to_score(entries, rank)


def classify_tier(group_rank: int | None, brother_rank: int) -> tuple[str, float | None]:
    """位次直比判档。返回 (tier, advantage_ratio)。"""
    if not group_rank:
        return "未知", None
    advantage = group_rank - brother_rank
    ratio = advantage / group_rank
    if ratio < -0.15:
        return "超冲", ratio
    elif ratio < -0.03:
        return "搏", ratio
    elif ratio < 0.03:
        return "冲", ratio
    elif ratio < 0.12:
        return "稳", ratio
    elif ratio < 0.25:
        return "保", ratio
    else:
        return "垫", ratio


def parse_school(raw_path: Path) -> dict | None:
    """解析单个 raw JSON 为结构化记录。"""
    rows = json.loads(raw_path.read_text(encoding="utf-8"))
    if not rows:
        return None
    s = rows[0]
    school_name = s.get("schoolName", raw_path.stem.split("_", 1)[-1])

    # 学校级历年录取
    school_admission = []
    for y in s.get("schoolRecentYearsAdmission", []):
        school_admission.append({
            "year": y.get("year"),
            "min_score": y.get("minCj"),
            "max_score": y.get("maxCj"),
            "min_rank": y.get("maxWc"),
            "admit_count": y.get("lqs"),
        })

    # 专业组（过滤"2024年招生专业组"脏数据）
    groups = []
    for g in s.get("majorList", []):
        zyzh = str(g.get("zyzh", "")).strip()
        if not zyzh.isdigit():
            continue  # 跳过非真实组号

        group_rank_2025 = g.get("minWc")
        try:
            group_rank_2025 = int(group_rank_2025) if group_rank_2025 else None
        except (ValueError, TypeError):
            group_rank_2025 = None

        min_cj_2025 = g.get("minCj")
        try:
            min_cj_2025 = int(min_cj_2025) if min_cj_2025 else None
        except (ValueError, TypeError):
            min_cj_2025 = None

        # 等位分换算：2025分 → 2025位次 → 2026等位分
        equiv_2026 = None
        if min_cj_2025:
            r25 = score_to_rank(2025, min_cj_2025)
            if r25:
                equiv_2026 = rank_to_score(2026, r25)

        tier, ratio = classify_tier(group_rank_2025, BROTHER_RANK)

        # 组内专业历年录取
        majors = []
        for m in g.get("zyzMajorList", []):
            major_history = []
            for y in m.get("recentYearsAdmission", []):
                major_history.append({
                    "year": y.get("year"),
                    "min_score": y.get("minCj"),
                    "max_score": y.get("maxCj"),
                    "min_rank": y.get("maxWc"),
                    "avg_score": y.get("lqpjf"),
                    "admit_count": y.get("lqs"),
                })
            majors.append({
                "major_name": m.get("majorName"),
                "major_code": m.get("zydh"),
                "history": major_history,
            })

        groups.append({
            "zyzh": zyzh,
            "requirement": g.get("kskmyqzw", ""),
            "min_score_2025": min_cj_2025,
            "min_rank_2025": group_rank_2025,
            "equiv_score_2026": equiv_2026,
            "advantage": (group_rank_2025 - BROTHER_RANK) if group_rank_2025 else None,
            "advantage_ratio": round(ratio, 3) if ratio is not None else None,
            "tier": tier,
            "majors": majors,
        })

    return {
        "school_name": school_name,
        "yxdh": str(s.get("yxdh", "")),
        "school_code": str(s.get("schoolCode", "")),
        "school_admission": school_admission,
        "groups": groups,
    }


def main() -> int:
    raw_files = sorted(RAW_DIR.glob("*.json"))
    print(f"解析 {len(raw_files)} 个 raw JSON")

    schools = []
    for f in raw_files:
        rec = parse_school(f)
        if rec:
            n_groups = len(rec["groups"])
            n_majors = sum(len(g["majors"]) for g in rec["groups"])
            print(f"  {rec['school_name']}: {n_groups} 组 / {n_majors} 专业")
            schools.append(rec)

    output = {
        "meta": {
            "source": "河南志愿填报系统 book.heao.com.cn getSchoolList 接口",
            "query_date": "2026-07-01",
            "track": "历史类",
            "years": [2025, 2024],
            "brother": {
                "score": BROTHER_SCORE,
                "rank": BROTHER_RANK,
                "year": 2026,
            },
            "tier_criteria": {
                "口径": "2025专业组最低位次 vs 弟弟2026位次73822",
                "超冲": "ratio < -0.15",
                "搏": "-0.15 <= ratio < -0.03",
                "冲": "-0.03 <= ratio < 0.03",
                "稳": "0.03 <= ratio < 0.12",
                "保": "0.12 <= ratio < 0.25",
                "垫": "ratio >= 0.25",
            },
        },
        "schools": schools,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        yaml.dump(output, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\n输出: {OUT_FILE} ({OUT_FILE.stat().st_size // 1024} KB)")
    print(f"  {len(schools)} 所院校, {sum(len(s['groups']) for s in schools)} 个专业组")
    return 0


if __name__ == "__main__":
    sys.exit(main())
