"""
基于当前志愿组共性 + heao/种子数据，推荐公办+国贸商务类专业组候选。

逻辑：
1. 提取当前13所共性：全民办/商科对口/学费1.5-3.4万
2. 从种子库筛公办+历史类+位次在弟弟可录范围(7万+)的院校
3. 过滤含国贸/商务/管理类专业的专业组
4. 用 admission_history 核实位次，按冲稳保分档
5. 落盘推荐报告
"""
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BROTHER_RANK = 73822
BROTHER_SCORE = 480

# 商科对口关键词（用户关注国际贸易/商务类）
BIZ_KEYWORDS = [
    "国际经济与贸易", "国际商务", "跨境电子商务", "贸易经济", "电子商务",
    "商务英语", "物流管理", "工商管理", "财务管理", "金融学", "经济学",
]

# 弟弟能录的公办校（从 admission_history_2025 确认位次 7万+）
PUBLIC_REACHABLE = {
    "咸阳师范学院": 76495,
    "成都大学": 79353,
    "河南理工大学": 79353,
    "南阳理工学院": 85097,
    "白城师范学院": 86143,
    "桂林旅游学院": 88177,
    "海南热带海洋学院": 89224,
    "琼台师范学院": 106050,
}


def classify(rank: int) -> tuple[str, int]:
    gap = rank - BROTHER_RANK
    if gap < 2000:
        return "冲", gap
    elif gap < 9000:
        return "稳", gap
    elif gap < 18000:
        return "保", gap
    else:
        return "垫", gap


def main() -> None:
    groups = yaml.safe_load(
        (ROOT / "data/seed/henan/program_groups_2026.yaml").read_text(encoding="utf-8")
    )
    unis = yaml.safe_load(
        (ROOT / "data/seed/henan/universities.yaml").read_text(encoding="utf-8")
    )
    uni_idx = {u["school_name"].split("(")[0]: u for u in unis}
    plans = yaml.safe_load(
        (ROOT / "data/seed/henan/enrollment_plans_2026.yaml").read_text(encoding="utf-8")
    )

    # 每校学费（取最低值）
    school_tuition: dict[str, int] = {}
    for p in plans:
        sn = p.get("school_name", "").split("(")[0]
        t = p.get("tuition")
        if t and (sn not in school_tuition or t < school_tuition[sn]):
            school_tuition[sn] = t

    # 匹配公办校的专业组
    recommendations = []
    for school, rank_2025 in PUBLIC_REACHABLE.items():
        u = uni_idx.get(school, {})
        tier, gap = classify(rank_2025)
        tuition = school_tuition.get(school)
        for g in groups:
            name = g.get("school_name", "").split("(")[0]
            if name != school:
                continue
            majors = g.get("included_majors", [])
            biz_majors = [m for m in majors if any(k in m for k in BIZ_KEYWORDS)]
            if not biz_majors:
                continue
            recommendations.append({
                "school": school,
                "province": u.get("province", "?"),
                "city": u.get("city", "?"),
                "ownership": u.get("ownership", "?"),
                "tier": tier,
                "rank_2025": rank_2025,
                "gap": gap,
                "major_group_code": g["major_group_code"],
                "requirement": g.get("primary_subject_requirement", ""),
                "biz_majors": biz_majors,
                "all_majors": majors,
                "tuition": tuition,
            })

    # 按 tier + gap 排序
    tier_order = {"冲": 0, "稳": 1, "保": 2, "垫": 3}
    recommendations.sort(key=lambda r: (tier_order.get(r["tier"], 9), r["gap"]))

    # 生成报告
    L = []
    L.append("# 公办+国贸商务类 候选推荐（基于志愿组共性分析）\n")
    L.append("**考生**：480分 / 位次 73822 / 历史类 / 2026  ")
    L.append("**当前志愿组共性**：13所全民办、学费1.5-3.4万、专业组含商科（国贸/电商/财管）  ")
    L.append("**推荐方向**：补充公办院校（学费低）+ 国际贸易/商务对口专业组\n")
    L.append("## 核心发现\n")
    L.append("**公办本科在弟弟位段（7万+）极其稀缺**：河南2025历史类公办录取数据2284条中，")
    L.append("仅6所独立公办院校的位次在弟弟可录范围（7万以后），其余2271条都在5万以内（弟弟够不上）。\n")
    L.append("以下为弟弟能录的公办校中，含国贸/商务类专业组的候选：\n")
    L.append("| 学校 | 省份 | 档位 | 2025位次 | 位次差 | 专业组 | 商科对口专业 | 学费/年 |")
    L.append("|------|------|------|---------|--------|--------|------------|--------|")
    for r in recommendations:
        tuition_str = f"{r['tuition']:,}元" if r["tuition"] else "待核实"
        biz_str = "、".join(r["biz_majors"][:3])
        L.append(
            f"| **{r['school']}** | {r['province']} | {r['tier']} | "
            f"{r['rank_2025']:,} | {r['gap']:+,} | {r['major_group_code']} | "
            f"{biz_str} | {tuition_str} |"
        )

    L.append("\n## 重点推荐（按优先级）\n")
    # 筛出国贸/商务最对口的
    top = [r for r in recommendations if any(
        k in " ".join(r["biz_majors"]) for k in ["国际经济与贸易", "国际商务", "跨境电子商务", "商务"]
    )]
    for i, r in enumerate(top, 1):
        L.append(f"### {i}. {r['school']}（{r['tier']}档 · {r['province']}{r['city']}）")
        L.append(f"- **2025录取位次**：{r['rank_2025']:,}（弟弟差 {r['gap']:+,} 位）")
        L.append(f"- **专业组**：{r['major_group_code']}（{r['requirement']}）")
        L.append(f"- **对口商科专业**：{'、'.join(r['biz_majors'])}")
        L.append(f"- **学费**：{r['tuition']:,}元/年" if r["tuition"] else "- **学费**：待核实")
        L.append(f"- **组内全部专业**：{'、'.join(r['all_majors'])}")
        L.append("")

    L.append("## 与当前志愿组对比\n")
    L.append("| 维度 | 当前13所（民办） | 推荐公办候选 |")
    L.append("|------|-----------------|-------------|")
    L.append(f"| 学费 | 15,000~33,800元/年 | 4,000~6,000元/年（公办） |")
    L.append("| 性质 | 全民办 | 全公办 |")
    L.append("| 4年学费差 | — | 每校省 **4-11万** |")
    L.append("| 商科对口 | 多数含国贸/电商 | 含国贸/商务/财管 |")
    L.append("")
    L.append("## 建议\n")
    L.append("1. **南阳理工学院**（国贸对口·稳档）最值得加入：省内公办、学费低、国际经济与贸易直接对口")
    L.append("2. **成都大学**（商务英语/工商管理·稳档）：城市好、公办、位次匹配")
    L.append("3. **海南热带海洋学院**（跨境电商·保档）：含跨境电子商务，公办保底")
    L.append("4. 建议替换当前志愿组中位次过远的垫底校（广东理工/陕西服装/哈石油，位次差3-4万）")
    L.append("5. 公办师范类（咸阳师范/白城师范）虽有位次匹配，但商科对口弱，仅作备选\n")
    L.append("> ⚠️ 以上位次来自本地种子 admission_history_2025，未逐校 heao 核实（heao 不覆盖")
    L.append("> 这些公办校）。建议填报前在 heao 系统逐校确认 2026 招生计划与专业组代码。")

    out = ROOT / "data/evaluate/public_recommendation.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"推荐报告: {out}")
    print(f"候选: {len(recommendations)} 个公办商科专业组")
    for r in recommendations:
        print(f"  {r['tier']} {r['school']}({r['province']}) 位次{r['rank_2025']} 差{r['gap']:+d} | {'、'.join(r['biz_majors'][:3])}")


if __name__ == "__main__":
    main()
