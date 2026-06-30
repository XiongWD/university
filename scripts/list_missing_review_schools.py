"""
生成「需人工复核（主因 missing_verified_2025_rank）」的院校清单，作为增量补抓的输入。

复用引擎的数据加载 + scope 过滤 + 历史基线查找，遍历所有 2026 历史类普通本科批专业组，
挑出：资格通过、2026 计划已核验、专业组已核验，但 find_best_historical_baseline 返回 None
（即缺 2025/2024 同口径录取位次）的校。

输出 data/raw/henan_2026/heao_admission/missing_review_schools.txt（每行一校名），
以及同名 .json（含每校的 school_code / group_code / included_majors，便于核对）。
"""
import json
from pathlib import Path

from app.loader.henan_data_loader import (
    find_best_historical_baseline,
    load_henan_admission_history,
    load_henan_enrollment_plans,
    load_henan_program_groups,
)
from app.loader.henan_scope import filter_henan_history_regular_scope, filter_henan_history_regular_history

OUT_DIR = Path("data/raw/henan_2026/heao_admission")
OUT_TXT = OUT_DIR / "missing_review_schools.txt"
OUT_JSON = OUT_DIR / "missing_review_schools.json"


def main() -> int:
    seed_dir = Path("data/seed")
    groups = load_henan_program_groups(seed_dir)
    plans = load_henan_enrollment_plans(seed_dir)
    history = load_henan_admission_history(seed_dir)

    groups, plans = filter_henan_history_regular_scope(groups, plans)
    history = filter_henan_history_regular_history(history, groups)

    # 计划按 (school_code, group_code, track, batch) 聚合
    plans_by_key: dict[tuple, list] = {}
    for p in plans:
        plans_by_key.setdefault(
            (p.school_code, p.major_group_code, p.track, p.batch), []
        ).append(p)

    missing: dict[str, dict] = {}   # school_name -> {school_code, groups: [...]}
    n_total = 0
    n_missing = 0
    for g in groups:
        if g.track != "历史类":
            continue
        n_total += 1
        gp = plans_by_key.get((g.school_code, g.major_group_code, g.track, g.batch), [])
        has_2026_plan = any(p.plan_count > 0 and p.review_status == "verified" for p in gp)
        has_verified_group = g.review_status == "verified"
        if not (has_2026_plan and has_verified_group):
            continue  # 不是「资格暂无问题，仅缺位次」的类型，跳过
        baseline = find_best_historical_baseline(
            history,
            school_code=g.school_code,
            group_code=g.major_group_code,
            major_names=g.included_majors,
            track=g.track,
            batch=g.batch,
        )
        if baseline is None:
            n_missing += 1
            entry = missing.setdefault(g.school_name, {
                "school_name": g.school_name,
                "school_code": g.school_code,
                "groups": [],
            })
            entry["groups"].append({
                "major_group_code": g.major_group_code,
                "included_majors": g.included_majors,
            })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    names = sorted(missing.keys())
    OUT_TXT.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {"total_groups_evaluated": n_total, "missing_groups": n_missing,
             "missing_schools": list(missing.values())},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    print(f"评估专业组: {n_total}")
    print(f"缺 2025 同口径位次的专业组: {n_missing}")
    print(f"涉及院校: {len(names)} 校")
    print(f"  清单 -> {OUT_TXT}")
    print(f"  明细 -> {OUT_JSON}")
    print("\n清单（前 60）：")
    for n in names[:60]:
        print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
