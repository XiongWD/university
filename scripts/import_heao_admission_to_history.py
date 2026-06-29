"""
将 heao 采集的真实专业组级录取位次，按专业名匹配到系统的 major_group_code，
生成与 import_henan_admission_history.py 兼容的 admission_history CSV。

匹配策略：heao 专业组（含多个专业）↔ 系统 program_group（含 included_majors），
按"专业名重合度"最佳匹配。一个系统组可能匹配到 heao 的一个组（专业集合最接近的）。

本脚本先做匹配分析（--dry-run），确认匹配率后再实际生成 CSV（默认 dry-run）。
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HEAO = Path("data/raw/henan_2026/heao_admission/all_schools.json")
PROGRAM_GROUPS = Path("data/seed/henan/program_groups_2026.yaml")
OUT = Path("data/raw/henan_2026/heao_admission/admission_history_matched.csv")

# 专业名归一化：去除括号说明、统一全角
import re
def norm_major(name: str) -> str:
    if not name:
        return ""
    n = re.sub(r"[（(].*?[)）]", "", name).strip()
    return n


def best_match_group(heao_group_majors: list[str], sys_groups: list[dict]) -> str | None:
    """从系统的多个专业组中，找与 heao 组专业集合重合度最高的那个 major_group_code。"""
    heao_set = {norm_major(m) for m in heao_group_majors if m}
    if not heao_set:
        return None
    best_code, best_score = None, 0
    for sg in sys_groups:
        sys_set = {norm_major(m) for m in (sg.get("included_majors") or []) if m}
        if not sys_set:
            continue
        # Jaccard 重合度
        inter = len(heao_set & sys_set)
        if inter == 0:
            continue
        score = inter / len(heao_set | sys_set)
        if score > best_score:
            best_score, best_code = score, sg.get("major_group_code")
    return best_code if best_score >= 0.3 else None  # 低于 0.3 视为不可靠


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="实际生成 CSV（默认只分析）")
    args = parser.parse_args()

    heao_data = json.loads(HEAO.read_text(encoding="utf-8"))

    # 加载系统的 program_groups（历史类本科批），按学校分组
    import yaml
    pg = yaml.safe_load(PROGRAM_GROUPS.read_text(encoding="utf-8"))
    pg = pg if isinstance(pg, list) else (pg.get("program_groups") or pg.get("records") or [])
    sys_by_school: dict[str, list[dict]] = {}
    for g in pg:
        if g.get("track") == "历史类" and g.get("batch") == "本科批":
            sys_by_school.setdefault(g.get("school_name", ""), []).append(g)

    # 匹配 + 统计
    matched_rows = []   # 专业组级真实位次
    school_rows = []    # 院校级真实位次（保留）
    n_heao_groups = 0
    n_matched = 0
    n_unmatched = 0
    unmatched_samples = []

    # 建立 (school_name -> school_code) 映射，从 program_groups 取（国标代码）
    school_code_map = {}
    for sname, gs in sys_by_school.items():
        if gs and gs[0].get("school_code"):
            school_code_map[sname] = str(gs[0]["school_code"])

    SRC_NAME = "河南省考试院 book.heao.com.cn"
    SRC_URL = "https://book.heao.com.cn/?#/choose"

    def base_cols(sname: str) -> dict:
        return {
            "school_code": school_code_map.get(sname, ""),
            "school_name": sname,
            "track": "历史类", "batch": "本科批",
            "source_name": SRC_NAME, "source_url": SRC_URL,
            "review_status": "verified",
        }

    for s in heao_data:
        sname = s["school_name"]
        sys_groups = sys_by_school.get(sname, [])
        # 院校级（保留，作为兜底）—— 仅保留有有效位次的
        for h in s["school_history"]:
            if not h.get("min_rank") or h["min_rank"] <= 0:
                continue
            school_rows.append({
                **base_cols(sname),
                "major_group_code": "", "major_group_name": "", "major_name": "",
                "year": h["year"], "min_score": h["min_score"], "min_rank": h["min_rank"],
                "data_granularity": "school", "confidence": 0.9,
            })
        # 专业组级 —— 从组内专业的 recentYearsAdmission 按年聚合（每年取位次最小=最易录取的专业）
        for g in s["groups"]:
            n_heao_groups += 1
            heao_majors = [m["major_name"] for m in g["majors"]]
            code = best_match_group(heao_majors, sys_groups)
            if not code:
                n_unmatched += 1
                if len(unmatched_samples) < 8:
                    unmatched_samples.append(f"{sname} zyzh={g['zyzh']} 专业={heao_majors[:3]}")
                continue

            # 按年聚合：该组内所有专业的 recentYearsAdmission
            # 专业组门槛 = 该组最低录取分对应的位次 = 组内各专业 min_rank 的最大值
            # （位次越大→分数越低→越容易录取，专业组门槛取最容易进的）
            by_year: dict[str, list[dict]] = {}
            for m in g["majors"]:
                for h in m.get("history", []):
                    if not h.get("min_rank") or h["min_rank"] <= 0:
                        continue
                    by_year.setdefault(str(h.get("year")), []).append(h)

            if not by_year:
                n_unmatched += 1
                continue
            n_matched += 1
            for yr, items in by_year.items():
                # 专业组门槛：取位次最大（最易录取）的，即该组最低录取分对应的位次
                best = max(items, key=lambda x: x.get("min_rank") or 0)
                matched_rows.append({
                    **base_cols(sname),
                    "major_group_code": code, "major_group_name": "", "major_name": "",
                    "year": yr,
                    "min_score": best.get("min_score"), "min_rank": best.get("min_rank"),
                    "data_granularity": "major_group", "confidence": 0.95,
                })

    print(f"=== heao 专业组匹配结果 ===")
    print(f"  heao 专业组总数: {n_heao_groups}")
    print(f"  成功匹配到系统 code: {n_matched} ({n_matched/max(n_heao_groups,1)*100:.1f}%)")
    print(f"  未匹配: {n_unmatched} ({n_unmatched/max(n_heao_groups,1)*100:.1f}%)")
    print(f"  院校级（保留兜底）: {len(school_rows)} 条")
    # 年份覆盖统计
    from collections import Counter
    yr_dist = Counter(str(r["year"]) for r in matched_rows)
    print(f"  专业组级年份分布: {dict(yr_dist)}")
    print(f"\n未匹配样本（heao 有专业组但系统无对应 program_group）:")
    for u in unmatched_samples:
        print(f"  - {u}")

    if args.apply:
        cols = ["school_code", "school_name", "major_group_code", "major_group_name",
                "major_name", "year", "track", "batch", "min_score", "min_rank",
                "data_granularity", "source_name", "source_url", "confidence", "review_status"]
        all_rows = matched_rows + school_rows
        # 按年份拆分输出（import_henan_admission_history.py 按 --year 写对应 yaml，CSV 需单年份）
        for yr in (2024, 2025):
            yr_rows = [r for r in all_rows if str(r.get("year")) == str(yr)]
            out = OUT.parent / f"admission_history_matched_{yr}.csv"
            with out.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for r in yr_rows:
                    w.writerow({k: r.get(k, "") for k in cols})
            n_grp = sum(1 for r in yr_rows if r["data_granularity"] == "major_group")
            n_sch = sum(1 for r in yr_rows if r["data_granularity"] == "school")
            print(f"  {out.name}: {len(yr_rows)} 行（专业组级 {n_grp} + 院校级 {n_sch}）")
    else:
        print(f"\n（--dry-run，未写文件。加 --apply 实际生成）")


if __name__ == "__main__":
    main()
