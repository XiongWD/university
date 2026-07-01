"""
评估弟弟 13 所志愿院校的 heao 权威数据。

用最新 cookie 调 book.heao.com.cn getSchoolList 接口，按校名查询每所院校的
历年专业组录取数据（2025/2024），再用本地一分一段表换算位次，评估对弟弟
（480分/位次73822/历史类/2026）的录取档次。

数据源：河南志愿填报系统 book.heao.com.cn（权威，非各校官网）。
用法：python scripts/evaluate_brother_volunteers.py
"""
import csv
import json
import sys
import time
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from heao_client import get_json, load_token  # noqa: E402
from app.engine.henan_recommendation import (  # noqa: E402
    _load_score_rank_entries,
    _score_to_rank,
)

API = "https://book.heao.com.cn/prod-api/choose/volunteer/getSchoolList"

# 弟弟信息：480分/位次73822/历史类/2026
BROTHER_SCORE = 480
BROTHER_RANK = 73822
BROTHER_YEAR = 2026

# 13 所志愿院校（与 db default 组一致）
BROTHER_SCHOOLS = [
    "安阳学院", "商丘学院", "中原科技学院", "新乡工程学院",
    "郑州经贸学院", "长春财经学院", "西安外事学院", "广东理工学院",
    "陕西服装工程学院", "齐齐哈尔工程学院", "哈尔滨石油学院",
    "信阳学院", "黑龙江外国语学院",
]

# 弟弟设定的 tier（与 db planned_tier 一致，用于对比 heao 实际判档）
BROTHER_PLANNED_TIER = {
    "安阳学院": "稳", "商丘学院": "稳", "中原科技学院": "稳",
    "新乡工程学院": "稳", "郑州经贸学院": "保", "长春财经学院": "保",
    "西安外事学院": "稳", "广东理工学院": "保", "陕西服装工程学院": "保",
    "齐齐哈尔工程学院": "保", "哈尔滨石油学院": "保",
    "信阳学院": "冲", "黑龙江外国语学院": "冲",
}

OUT_DIR = PROJECT_ROOT / "data" / "evaluate"
RAW_DIR = OUT_DIR / "raw"


def query_school(school_name: str, token: str) -> list[dict]:
    """查询单个院校的 heao 数据。pcdm=1=历史类。

    minWc/maxWc 是 heao 对院校录取位次的过滤窗口——该校录取位次必须落在窗口内
    才返回。弟弟位次 73822，志愿覆盖冲（5万）到垫（15万+），用宽窗口 [40000, 250000]
    确保所有档次的学校都能查到。
    """
    params = {
        "pageNum": "1",
        "pageSize": "50",
        "schoolName": school_name,
        "pcdm": "1",  # 1=历史类
        "minWc": "40000",
        "maxWc": "250000",
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    data = get_json(url, token)
    # 返回结构：{total, rows, code, msg}（数据在 rows 字段）
    rows = data.get("rows") or data.get("data") or []
    if isinstance(rows, dict):  # 某些接口包一层
        rows = rows.get("list") or rows.get("records") or []
    return rows


def score_to_rank_2026(score: int) -> int | None:
    """2026 历史类分数→位次。"""
    entries = _load_score_rank_entries(2026, "历史类")
    return _score_to_rank(entries, score)


def score_to_rank_2025(score: int) -> int | None:
    """2025 历史类分数→位次。"""
    entries = _load_score_rank_entries(2025, "历史类")
    return _score_to_rank(entries, score)


def assess_group(group: dict, school_name: str) -> dict:
    """评估单个专业组对弟弟的录取可能性。

    双口径判档：
    - 口径A（位次直比）：2025 录取位次 vs 弟弟 2026 位次（同口径 3+1+2，直接对比）
    - 口径B（等位分）：2025 录取分 → 一分一段换算成 2026 等位分 → 对比弟弟 480 分
    两个口径都算，以位次直比为主（更稳定），等位分作交叉验证。
    """
    zyzh = group.get("zyzh", "?")
    req = group.get("kskmyqzw", "")
    min_cj_2025 = group.get("minCj")  # 2025 该组最低分
    min_wc_2025 = group.get("minWc")  # 2025 该组最低位次

    # 专业组历年录取（含 2024）
    years_data = group.get("zyzMajorList", [])
    history = []
    if years_data:
        for y in years_data[0].get("recentYearsAdmission", []):
            history.append({
                "year": y.get("year"),
                "min_score": y.get("minCj"),
                "max_score": y.get("maxCj"),
                "min_rank": y.get("maxWc"),
                "avg_score": y.get("lqpjf"),
                "admit_count": y.get("lqs"),
            })

    # 口径A：位次直比（2025 位次 vs 弟弟 2026 位次 73822）
    group_rank_2025 = min_wc_2025
    if group_rank_2025:
        try:
            group_rank_2025 = int(group_rank_2025)
        except (ValueError, TypeError):
            group_rank_2025 = None

    # 口径B：等位分换算。2025录取分→2026等位分（用一分一段表跨年映射）
    equiv_score_2026 = None
    if min_cj_2025:
        try:
            score_2025 = int(min_cj_2025)
            # 2025 分数 → 2025 位次 → 2026 等位分（反过来查 2026 表）
            from app.engine.henan_recommendation import _rank_to_score
            rank_2025 = score_to_rank_2025(score_2025)
            if rank_2025:
                entries_2026 = _load_score_rank_entries(2026, "历史类")
                equiv_score_2026 = _rank_to_score(entries_2026, rank_2025)
        except (ValueError, TypeError):
            pass

    # 判档（口径A 位次直比为主）
    tier = "未知"
    advantage = None
    if group_rank_2025 and BROTHER_RANK:
        advantage = group_rank_2025 - BROTHER_RANK
        ratio = advantage / group_rank_2025
        if ratio < -0.15:
            tier = "超冲"
        elif ratio < -0.03:
            tier = "搏"
        elif ratio < 0.03:
            tier = "冲"
        elif ratio < 0.12:
            tier = "稳"
        elif ratio < 0.25:
            tier = "保"
        else:
            tier = "垫"

    # 等位分差（口径B）：弟弟480 vs 该组2026等位分
    equiv_score_gap = None
    if equiv_score_2026:
        equiv_score_gap = BROTHER_SCORE - equiv_score_2026  # 正=弟弟分更高=能录

    return {
        "school_name": school_name,
        "zyzh": zyzh,
        "requirement": req,
        "min_cj_2025": min_cj_2025,
        "group_rank_2025": group_rank_2025,
        "equiv_score_2026": equiv_score_2026,  # 2025录取分换算到2026的等位分
        "equiv_score_gap": equiv_score_gap,  # 弟弟480 - 等位分（正=能录）
        "brother_rank": BROTHER_RANK,
        "advantage": advantage,
        "tier": tier,
        "history": history,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    token = load_token()
    print(f"token OK, 弟弟: {BROTHER_SCORE}分/位次{BROTHER_RANK}/历史类/2026")
    print(f"评估 {len(BROTHER_SCHOOLS)} 所院校\n")

    all_results: list[dict] = []
    not_found: list[str] = []

    for i, name in enumerate(BROTHER_SCHOOLS, 1):
        print(f"[{i}/{len(BROTHER_SCHOOLS)}] {name}", end=" ... ", flush=True)
        try:
            rows = query_school(name, token)
        except Exception as e:
            print(f"❌ 查询失败: {e}")
            not_found.append(f"{name}\t查询异常: {e}")
            continue

        if not rows:
            print("❌ 未找到（可能校名不匹配或位次窗口外）")
            not_found.append(f"{name}\tAPI无返回")
            continue

        # 保存原始响应
        raw_path = RAW_DIR / f"{i:02d}_{name}.json"
        raw_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 通常返回 1 条（精确校名匹配），取第一条
        school = rows[0]
        all_groups = school.get("majorList", [])
        # 过滤掉脏数据：heao 会把"2024年招生专业组"（zyzh 是年份而非组号）混入，
        # 只保留 zyzh 是真实组号（纯数字 2-4 位）的组
        groups = [
            g for g in all_groups
            if str(g.get("zyzh", "")).strip().isdigit()
        ]
        dropped = len(all_groups) - len(groups)
        print(f"✅ {len(groups)} 个专业组" + (f"（过滤 {dropped} 个历史脏数据）" if dropped else ""))

        for g in groups:
            result = assess_group(g, name)
            all_results.append(result)
        time.sleep(0.3)  # 礼貌延迟

    # 生成评估报告
    _render_report(all_results, not_found)
    print(f"\n报告: {OUT_DIR / 'assessment.md'}")
    if not_found:
        print(f"未找到 {len(not_found)} 所: {[n.split(chr(9))[0] for n in not_found]}")
    return 0


def _render_report(results: list[dict], not_found: list[str]) -> None:
    today = "2026-07-01"
    # 按学校分组
    by_school: dict[str, list[dict]] = {}
    for r in results:
        by_school.setdefault(r["school_name"], []).append(r)

    lines = [
        "# 弟弟 13 所志愿院校评估报告（heao 权威数据）",
        "",
        f"**评估日期**：{today}",
        f"**考生**：{BROTHER_SCORE}分 / 位次 {BROTHER_RANK} / 历史类 / 2026",
        f"**数据源**：河南志愿填报系统 book.heao.com.cn（getSchoolList 接口，2025/2024 历年）",
        f"**判档口径**：口径A=2025录取位次 vs 弟弟2026位次（主）；口径B=等位分（2025分→一分一段→2026等位分）",
        "",
        "## 汇总（按判档排序）",
        "",
        "| 学校 | 组 | 科目要求 | 弟弟设定 | 2025最低分 | 2025位次 | 2026等位分 | 位次差 | 分差 | 实际判档 | 设定vs实际 |",
        "|------|----|---------|---------|-----------|---------|-----------|--------|------|---------|-----------|",
    ]
    # 按判档严重程度排序
    tier_order = {"超冲": 0, "搏": 1, "冲": 2, "稳": 3, "保": 4, "垫": 5, "未知": 6}
    flat = sorted(results, key=lambda r: (tier_order.get(r["tier"], 9), r["school_name"]))
    for r in flat:
        delta = f"{r['advantage']:+d}" if r["advantage"] is not None else "—"
        equiv = r.get("equiv_score_2026") or "—"
        gap = f"{r['equiv_score_gap']:+d}" if r.get("equiv_score_gap") is not None else "—"
        planned = BROTHER_PLANNED_TIER.get(r["school_name"], "?")
        # 设定 vs 实际对比
        match_icon = "✅" if planned == r["tier"] else ("⚠️" if tier_order.get(r["tier"], 9) > tier_order.get(planned, 9) else "🔺")
        # ⚠️=实际比设定更稳（设定偏保守）；🔺=实际比设定更冲（设定偏激进）
        lines.append(
            f"| {r['school_name']} | {r['zyzh']}组 | {r['requirement']} | "
            f"{planned} | {r['min_cj_2025'] or '—'} | {r['group_rank_2025'] or '—'} | "
            f"{equiv} | {delta} | {gap} | {r['tier']} | {match_icon} |"
        )

    # 逐校明细
    lines += ["", "## 逐校明细", ""]
    for name in BROTHER_SCHOOLS:
        groups = by_school.get(name, [])
        if not groups:
            lines += [f"### {name}", "", "⚠️ heao 未返回数据", ""]
            continue
        lines += [f"### {name}", ""]
        lines += ["| 专业组 | 科目要求 | 2025最低分 | 2025位次 | 位次差 | 判档 | 历年 |"]
        lines += ["|--------|---------|-----------|---------|--------|------|------|"]
        for g in groups:
            delta = f"{g['advantage']:+d}" if g["advantage"] is not None else "—"
            hist = " / ".join(
                f"{h['year']}:{h['min_score']}分({h['min_rank']}位,录{h['admit_count']})"
                for h in g["history"]
            )
            lines.append(
                f"| {g['zyzh']}组 | {g['requirement']} | {g['min_cj_2025'] or '—'} | "
                f"{g['group_rank_2025'] or '—'} | {delta} | **{g['tier']}** | {hist} |"
            )
        lines.append("")

    if not_found:
        lines += ["## 未找到", ""]
        for n in not_found:
            lines.append(f"- {n}")

    (OUT_DIR / "assessment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
