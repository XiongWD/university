"""用河南省考试院真实志愿组号(zyzh)做权威桥接，补齐被 gaokao.cn 拆碎的系统组位次。

【背景】系统 program_groups 用 gaokao.cn 的 major_group_code（如 '754911'）做精确键，
引擎 find_best_historical_baseline 按 group_code == h.major_group_code 查 history。
但 gaokao.cn 常把 heao 的【一个真实志愿组】拆成多个系统组（如南阳理工 heao 组102
{汉语言/网络新媒体/小学教育/英语/日语} 被拆成 754907 + 754911 + 754906）。拆出来的子组
专业集合太小，与 heao 组的 Jaccard < 0.3 → import_heao_admission_to_history.py 匹配失败
→ history 不写入 → 引擎查空 → 显示"需复核"。

【权威语义】河南新高考专业组模式下，一个志愿组号(zyzh)对应一个投档线/门槛位次。
填报时同志愿组号就是同组。故系统凡有相同 volunteer_group_code(=zyzh) 的组，都应共享
该真实志愿组位次，不受 gaokao.cn 拆分影响。

【本脚本做反向桥接】对每个历史类本科批系统组：
  - B 类（已有 volunteer_group_code）：直接用该志愿组号的 heao 真实位次。
  - D 类（无 volunteer_group_code）：先用专业子集包含 / 最大重合回填一个 zyzh，再用其位次。
  - A 类（heao 无此校）：跳过（数据源真实缺口，不虚构）。
输出 admission_history_bridge_{year}.csv，列结构与 matched CSV 完全一致，可被
import_henan_admission_history.py 直接导入（major_group_code 精确填系统组码）。
"""
import csv
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 复用 matcher 的 campus-aware 校名归一化（单一来源，含更名白名单）
from import_heao_admission_to_history import school_key  # noqa: E402

HEAO = Path("data/raw/henan_2026/heao_admission/all_schools.json")
PROGRAM_GROUPS = Path("data/seed/henan/program_groups_2026.yaml")
OUT_DIR = Path("data/raw/henan_2026/heao_admission")

SRC_NAME = "河南省考试院 book.heao.com.cn"
SRC_URL = "https://book.heao.com.cn/?#/choose"


def norm_major(name: str) -> str:
    if not name:
        return ""
    return re.sub(r"[（(].*?[)）]", "", name).strip()


def build_heao_index(heao: list[dict]) -> dict:
    """建 {(school_key, zyzh): {majors:set, '2025':{rank,score}, '2024':{rank,score}}}。

    仅取纯数字 zyzh（真实志愿组号），排除 '2024年招生专业' 等合成占位组。
    每组门槛位次 = 组内最低分对应的最大位次（与 scrape 脚本 max(min_rank) 一致）。
    """
    idx: dict[tuple[str, str], dict] = {}
    for s in heao:
        k = school_key(s["school_name"])
        for g in s.get("groups", []):
            zyzh = str(g.get("zyzh") or "")
            if not zyzh.isdigit():  # 仅真实志愿组号
                continue
            key = (k, zyzh)
            rec = idx.setdefault(key, {"majors": set()})
            rec["majors"].update(
                norm_major(m["major_name"]) for m in g.get("majors", []) if m.get("major_name")
            )
            # 按年聚合组内专业：门槛 = max(min_rank)（最低分对应位次）
            by_year: dict[str, list[dict]] = {}
            for m in g.get("majors", []):
                for h in m.get("history", []):
                    yr = str(h.get("year"))
                    if h.get("min_rank") and h["min_rank"] > 0:
                        by_year.setdefault(yr, []).append(h)
            for yr, items in by_year.items():
                best = max(items, key=lambda x: x.get("min_rank") or 0)
                rec[yr] = {"rank": best.get("min_rank"), "score": best.get("min_score")}
    return idx


def resolve_zyzh(
    vgc: str, sys_majors: list[str], school_k: str, heao_idx: dict
) -> tuple[str, str]:
    """解析系统组对应的 heao 志愿组号。

    返回 (zyzh, method)。method ∈ {'direct','subset','overlap','none'}：
      - vgc 非空且 heao 有该组 → 'direct'
      - vgc 空，系统专业是 heao 某组子集 → 'subset'（最可靠）
      - vgc 空，无子集但有最大重合（交集≥2 或 Jaccard≥0.2）→ 'overlap'
      - 否则 'none'
    """
    if vgc:
        if (school_k, vgc) in heao_idx:
            return vgc, "direct"
        # vgc 在 heao 此校不存在（罕见），回退到专业匹配
    # 专业子集包含（精确，优先）
    sys_set = {norm_major(m) for m in (sys_majors or []) if m}
    if school_k and sys_set:
        candidates = [
            (zyzh, info) for (sk, zyzh), info in heao_idx.items() if sk == school_k
        ]
        # 1) 子集包含：系统专业 ⊆ heao 组
        for zyzh, info in candidates:
            if sys_set <= info["majors"]:
                return zyzh, "subset"
        # 2) 最大重合：交集≥2 专业 或 Jaccard≥0.2
        best_zyzh, best_score = "", 0.0
        best_inter = 0
        for zyzh, info in candidates:
            inter = len(sys_set & info["majors"])
            if inter == 0:
                continue
            jacc = inter / len(sys_set | info["majors"])
            if inter >= 2 or jacc >= 0.2:
                if jacc > best_score:
                    best_score, best_zyzh, best_inter = jacc, zyzh, inter
        if best_zyzh:
            return best_zyzh, "overlap"
    return "", "none"


def main() -> int:
    heao = json.loads(HEAO.read_text(encoding="utf-8"))
    heao_idx = build_heao_index(heao)
    heao_school_keys = {sk for (sk, _zyzh) in heao_idx}

    pg = yaml.safe_load(PROGRAM_GROUPS.read_text(encoding="utf-8"))
    pg = pg if isinstance(pg, list) else (pg.get("program_groups") or pg.get("records") or [])
    sys_groups = [
        g for g in pg if g.get("track") == "历史类" and g.get("batch") == "本科批"
    ]

    # 统计 + 输出行
    rows_by_year: dict[str, list[dict]] = {"2024": [], "2025": []}
    method_stat = {"direct": 0, "subset": 0, "overlap": 0, "no_school": 0, "no_match": 0}
    sample = {"subset": [], "overlap": []}
    vgc_backfilled = 0  # 回写 program_groups 的 vgc 计数

    for g in sys_groups:
        sn = g.get("school_name", "")
        k = school_key(sn)
        vgc = str(g.get("volunteer_group_code") or "")
        zyzh, method = resolve_zyzh(vgc, g.get("included_majors") or [], k, heao_idx)
        if method == "none":
            if k not in heao_school_keys:
                method_stat["no_school"] += 1
            else:
                method_stat["no_match"] += 1
            continue
        method_stat[method] += 1
        # 回写真实志愿组号：仅当系统组原 vgc 为空/非数字时（subset/overlap 回填场景），
        # direct 命中说明 vgc 本就正确，不覆盖。让前端能显示真实填报组号。
        if method in ("subset", "overlap") and not vgc.isdigit():
            g["volunteer_group_code"] = zyzh
            vgc_backfilled += 1
        info = heao_idx[(k, zyzh)]
        base = {
            "school_code": g.get("school_code", ""),
            "yxdh": "",
            "school_name": sn,
            "zyzh": zyzh,
            "major_group_code": g["major_group_code"],  # 精确填系统组码（引擎匹配键）
            "major_group_name": g.get("major_group_name", ""),
            "major_name": "",
            "track": "历史类",
            "batch": "本科批",
            "data_granularity": "major_group",
            "source_name": SRC_NAME,
            "source_url": SRC_URL,
            "confidence": 0.9,
            "review_status": "verified",
        }
        for yr in ("2024", "2025"):
            if yr in info:
                rows_by_year[yr].append({
                    **base,
                    "year": yr,
                    "min_score": info[yr]["score"],
                    "min_rank": info[yr]["rank"],
                })
        # 回填样本（抽查误配用）
        if method in ("subset", "overlap") and len(sample[method]) < 6:
            sample[method].append(
                f"{sn} 组{g['major_group_code']}(原vgc={vgc or '空'}) "
                f"系统{sorted({norm_major(m) for m in (g.get('included_majors') or [])})} "
                f"→ heao组{zyzh}"
            )

    # 写 CSV（列序与 import_henan_admission_history.py 兼容）
    cols = ["school_code", "yxdh", "school_name", "zyzh", "major_group_code",
            "major_group_name", "major_name", "year", "track", "batch",
            "min_score", "min_rank", "data_granularity", "source_name",
            "source_url", "confidence", "review_status"]
    for yr in ("2024", "2025"):
        out = OUT_DIR / f"admission_history_bridge_{yr}.csv"
        with out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows_by_year[yr]:
                w.writerow({c: r.get(c, "") for c in cols})
        print(f"  {out.name}: {len(rows_by_year[yr])} 行")

    # 回写真实志愿组号到 program_groups（让前端显示真实填报组号，不再出现"无专业组"裸志愿）
    if vgc_backfilled:
        PROGRAM_GROUPS.write_text(
            yaml.safe_dump(pg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"  回写 volunteer_group_code: {vgc_backfilled} 组 → {PROGRAM_GROUPS.name}")

    print(f"\n=== 志愿组号桥接统计（历史类本科批 {len(sys_groups)} 系统组）===")
    print(f"  direct (有vgc直接命中):    {method_stat['direct']}")
    print(f"  subset (专业子集回填):     {method_stat['subset']}")
    print(f"  overlap (最大重合回填):    {method_stat['overlap']}")
    print(f"  no_school (heao无此校-A类): {method_stat['no_school']}")
    print(f"  no_match (专业对不上):      {method_stat['no_match']}")
    print(f"  可救回合计(direct+subset+overlap): "
          f"{method_stat['direct'] + method_stat['subset'] + method_stat['overlap']}")
    for m in ("subset", "overlap"):
        if sample[m]:
            print(f"\n--- {m} 回填样本（抽查）---")
            for s in sample[m]:
                print(f"  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
