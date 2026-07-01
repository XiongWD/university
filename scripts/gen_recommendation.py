"""基于 heao 权威数据生成志愿组调整推荐报告。"""
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = yaml.safe_load(open(ROOT / 'data/seed/henan/heao_assessment_2025.yaml', encoding='utf-8'))
BROTHER_RANK = 73822
PLANNED = {
    "安阳学院": "稳", "商丘学院": "稳", "中原科技学院": "稳", "新乡工程学院": "稳",
    "郑州经贸学院": "保", "长春财经学院": "保", "西安外事学院": "稳", "广东理工学院": "保",
    "陕西服装工程学院": "保", "齐齐哈尔工程学院": "保", "哈尔滨石油学院": "保",
    "信阳学院": "冲", "黑龙江外国语学院": "冲",
}

schools_data = {}
for s in d['schools']:
    name = s['school_name'].split('(')[0]
    schools_data[name] = sorted(s['groups'], key=lambda g: -(g.get('advantage') or -1e9))

RECOMMEND = {}
for name, groups in schools_data.items():
    if not groups:
        continue
    best = groups[0]
    adv = best.get('advantage')
    if adv is None:
        continue
    if adv < -5000:
        RECOMMEND[name] = ("冲", best, "位次差>5000，冲一冲")
    elif adv < 2000:
        RECOMMEND[name] = ("冲", best, "位次接近，有希望")
    elif adv < 9000:
        RECOMMEND[name] = ("稳", best, "位次匹配，录取把握大")
    elif adv < 18000:
        RECOMMEND[name] = ("保", best, "稳录保底")
    else:
        RECOMMEND[name] = ("保", best, "远超录取线，极保底")

L = []
L.append("# 志愿组调整推荐（基于 heao 权威数据）\n")
L.append("**考生**：480分 / 位次 73822 / 历史类 / 2026  ")
L.append("**数据源**：book.heao.com.cn 2025 历年录取\n")
L.append("## 核心问题\n")
L.append("### 🔺 严重：郑州经贸学院设定【保】实际是【超冲】")
L.append("- heao 2025录取：501分 / 位次 61895（101组）")
L.append("- 弟弟位次 73822，**差 11927 位（约14分）**")
L.append("- 占了保底名额却根本录不到，必须降级为冲或替换\n")
L.append("### ⚠️ 结构失衡：保底过多、冲稳不足")
L.append("- 当前设定：冲2 / 稳5 / 保6")
L.append("- 保底6个中4个实际是垫级（位次差3-4万），2-3个足够")
L.append("- 信阳学院101/102组实际超冲，只有501组能稳\n")
L.append("## 推荐调整（按位次73822重新分档）\n")
L.append("| 学校 | 原设定 | 推荐 | 最优组 | 2025录取 | 位次差 | 理由 |")
L.append("|------|--------|------|--------|---------|--------|------|")
for tier_name in ["冲", "稳", "保"]:
    for name in PLANNED:
        if name not in RECOMMEND:
            continue
        rec_tier, best, reason = RECOMMEND[name]
        if rec_tier != tier_name:
            continue
        old = PLANNED[name]
        adv = best.get('advantage', 0)
        change = "→" + rec_tier if old != rec_tier else "=同"
        ss = str(best.get('min_score_2025', '—')) + "分/" + str(best.get('min_rank_2025', '—')) + "位"
        L.append(f"| {name} | {old} | {change} | {best['zyzh']}组 | {ss} | {adv:+d} | {reason} |")

L.append("\n## 具体操作建议\n")
L.append("### 1. 郑州经贸学院：降级为冲或移除")
L.append("- 501分/61895位，差1.2万位，2026大概率录不到")
L.append("- 若保留：改为冲档；若求稳：移除用省外校替代\n")
L.append("### 2. 精简保底：6个→3个")
L.append("- 保留：长春财经(94273位)、齐齐哈尔工程(94273位)")
L.append("- 可移除：广东理工(117012)、陕西服装(110379)、哈尔滨石油(106050)\n")
L.append("### 3. 校正冲稳")
L.append("- 信阳501组(76495位)：冲→稳（唯一能稳录的组）")
L.append("- 西安外事(91159位)：稳→保更准确\n")
L.append("## 调整后理想结构\n")
L.append("| 档位 | 数量 | 学校 |")
L.append("|------|------|------|")
L.append("| 冲 | 3 | 安阳103组、中原科技101组、信阳501组 |")
L.append("| 稳 | 6 | 安阳501/903组、商丘102/103组、中原科技501组、新乡工程101组 |")
L.append("| 保 | 3 | 长春财经103组、齐齐哈尔104组、西安外事101组 |")
L.append("| 移除 | 1 | 郑州经贸（超冲） |")
L.append("| 精简 | 3 | 广东理工、陕西服装、哈尔滨石油（保留1个极保底） |")
L.append("\n> 河南48志愿可填更多，建议冲稳保 8/24/16，当前保底偏多冲稳偏少。")

open(ROOT / 'data/evaluate/recommendation.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print("推荐报告已生成: data/evaluate/recommendation.md")
