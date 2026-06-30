"""
将 heao 采集的真实专业组级录取位次，按专业名匹配到系统的 major_group_code，
生成与 import_henan_admission_history.py 兼容的 admission_history CSV。

匹配策略：heao 专业组（含多个专业）↔ 系统 program_group（含 included_majors），
按"专业名重合度"最佳匹配。一个系统组可能匹配到 heao 的一个组（专业集合最接近的）。

院校匹配（关键：campus-aware 校名归一化，避免校园/校区误并）：
  heao 和系统用的是**不同的院校代码体系**——heao 用 yxdh(河南院校代码) + 国标码，
  系统用 gaokao.cn school_id，三者互不相等，无法用码做主键。因此只能用校名桥接，
  但必须**保留校园/校区括号**（北京/武汉/深圳/威海/苏州校区/宣城校区 等），否则会把
  不同学校错误合并（如 中国地质大学(北京)≠(武汉)；中国石油大学(北京)≠(华东)；
  哈工大≠(深圳)≠(威海)；人大≠(苏州校区)；山大≠(威海)）。
  归一化规则（norm_school）：
    1) 统一全/半角括号；
    2) 仅剥 (原XXX) 这类**更名后缀**，保留 (地点) 校区括号；
    3) 查更名白名单 SCHOOL_RENAME_MAP（仅确无歧义的真更名 + 个别措辞差异）。

输出 CSV 含 yxdh（河南院校代码）+ zyzh（专业组真实填报号）两列，供真实志愿填报用。
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


# campus-aware 校名归一化：统一括号 + 只剥 (原XXX) 更名后缀（保留地点校区括号）。
# 例：'信阳师范大学(原信阳师范学院)' → '信阳师范大学'；'中国地质大学（北京）' → '中国地质大学(北京)'。
def norm_school(name: str) -> str:
    if not name:
        return ""
    n = name.strip().replace("（", "(").replace("）", ")")
    n = re.sub(r"\(原[^)]*\)", "", n).strip()
    return n


# 校名更名/措辞差异白名单（heao 原名 → 系统名归一化后）。
# 仅放确无歧义的真更名，或个别校区措辞差异。**禁止**放入同名异校/校区歧义项。
# 维护说明：dry-run 会打印未匹配的 heao 校名，逐条核对后补到这里。
SCHOOL_RENAME_MAP = {
    # 真更名（2025/2026）
    "淮阴工学院": "淮安大学",
    "绍兴文理学院": "绍兴大学",
    "闽江学院": "闽江大学",
    "新乡医学院": "河南医药大学",
    "新疆理工学院": "新疆理工职业大学",
    # 2026 由"学院"升"大学"（heao 仍用旧名）
    "吉林化工学院": "吉林化工大学",
    "天水师范学院": "天水师范大学",
    "榆林学院": "榆林大学",
    "湖南理工学院": "湖南理工大学",
    "湖州师范学院": "湖州师范大学",
    "西藏农牧学院": "西藏农牧大学",
    "赤峰学院": "赤峰大学",
    # 校区措辞差异（heao 旧称 → 系统括号形式）
    "山东大学威海分校": "山东大学(威海)",
}


def school_key(name: str) -> str:
    """heao / 系统 校名归一到统一 key（campus-aware + 更名白名单）。"""
    base = norm_school(name)
    return SCHOOL_RENAME_MAP.get(base, base)


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

    # 加载系统的 program_groups（历史类本科批），按 campus-aware 归一化校名索引。
    # 系统 school_code 是 gaokao.cn school_id（≠heao yxdh/国标），无法用码桥接，
    # 只能靠校名（school_key：统一括号+剥更名后缀+保留校区括号+更名白名单）。
    import yaml
    pg = yaml.safe_load(PROGRAM_GROUPS.read_text(encoding="utf-8"))
    pg = pg if isinstance(pg, list) else (pg.get("program_groups") or pg.get("records") or [])
    sys_by_school: dict[str, list[dict]] = {}   # school_key -> groups
    for g in pg:
        if g.get("track") == "历史类" and g.get("batch") == "本科批":
            sys_by_school.setdefault(school_key(g.get("school_name", "")), []).append(g)

    # 匹配 + 统计
    matched_rows = []   # 专业组级真实位次
    school_rows = []    # 院校级真实位次（保留）
    n_heao_groups = 0
    n_matched = 0
    n_unmatched = 0
    unmatched_samples = []
    matched_schools = set()      # 命中的 heao 校（归一化 key），统计救回数
    unmatched_school_names = []  # heao 原始校名（未匹配到任何系统组），辅助补更名白名单

    SRC_NAME = "河南省考试院 book.heao.com.cn"
    SRC_URL = "https://book.heao.com.cn/?#/choose"

    def resolve_sys_groups(s: dict) -> list[dict]:
        """按 campus-aware 归一化校名命中系统组。"""
        return sys_by_school.get(school_key(s.get("school_name", "")), [])

    def base_cols(sys_groups0: list[dict], sname_heao: str, yxdh: str) -> dict:
        sc = str(sys_groups0[0].get("school_code") or "") if sys_groups0 else ""
        # school_name 用系统侧名（保证与 program_groups 一致，便于引擎 by_school 查找）
        sn = sys_groups0[0].get("school_name", sname_heao) if sys_groups0 else sname_heao
        return {
            "school_code": sc,
            "yxdh": yxdh,   # 河南院校代码（真实填报用）
            "school_name": sn,
            "track": "历史类", "batch": "本科批",
            "source_name": SRC_NAME, "source_url": SRC_URL,
            "review_status": "verified",
        }

    for s in heao_data:
        sname = s["school_name"]
        yxdh = str(s.get("yxdh") or "")
        sys_groups = resolve_sys_groups(s)
        if sys_groups:
            matched_schools.add(sname)
        else:
            unmatched_school_names.append(sname)

        # 院校级（保留，作为兜底）—— 仅保留有有效位次的
        for h in s["school_history"]:
            if not h.get("min_rank") or h["min_rank"] <= 0:
                continue
            school_rows.append({
                **base_cols(sys_groups, sname, yxdh),
                "zyzh": "",   # 院校级无专业组号
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
                    **base_cols(sys_groups, sname, yxdh),
                    "zyzh": g["zyzh"],   # 专业组真实填报号
                    "major_group_code": code, "major_group_name": "", "major_name": "",
                    "year": yr,
                    "min_score": best.get("min_score"), "min_rank": best.get("min_rank"),
                    "data_granularity": "major_group", "confidence": 0.95,
                })

    print(f"=== heao 专业组匹配结果 ===")
    print(f"  heao 专业组总数: {n_heao_groups}")
    print(f"  成功匹配到系统 code: {n_matched} ({n_matched/max(n_heao_groups,1)*100:.1f}%)")
    print(f"  未匹配: {n_unmatched} ({n_unmatched/max(n_heao_groups,1)*100:.1f}%)")
    print(f"  救回院校数: {len(matched_schools)}（campus-aware 校名归一化命中）")
    print(f"  院校级（保留兜底）: {len(school_rows)} 条")
    # 年份覆盖统计
    from collections import Counter
    yr_dist = Counter(str(r["year"]) for r in matched_rows)
    print(f"  专业组级年份分布: {dict(yr_dist)}")
    print(f"\n未匹配样本（heao 有专业组但系统无对应 program_group）:")
    for u in unmatched_samples:
        print(f"  - {u}")
    # heao 整校在系统里找不到对应（可能需要补更名白名单）
    uniq_unmatched = sorted(set(unmatched_school_names))
    if uniq_unmatched:
        print(f"\nheao 校在系统无对应 program_group（{len(uniq_unmatched)} 校，前 40）—"
              f"若是确无歧义的真更名可补 SCHOOL_RENAME_MAP（切勿放入同名异校/校区）：")
        for u in uniq_unmatched[:40]:
            print(f"  - {u}")

    if args.apply:
        cols = ["school_code", "yxdh", "school_name", "zyzh", "major_group_code",
                "major_group_name", "major_name", "year", "track", "batch",
                "min_score", "min_rank", "data_granularity", "source_name",
                "source_url", "confidence", "review_status"]
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
            n_yxdh = sum(1 for r in yr_rows if r.get("yxdh"))
            n_zyzh = sum(1 for r in yr_rows if r.get("zyzh"))
            print(f"  {out.name}: {len(yr_rows)} 行（专业组级 {n_grp} + 院校级 {n_sch}）"
                  f"｜含 yxdh {n_yxdh} / zyzh {n_zyzh}")
    else:
        print(f"\n（--dry-run，未写文件。加 --apply 实际生成）")


if __name__ == "__main__":
    main()
