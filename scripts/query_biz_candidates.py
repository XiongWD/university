"""
吸取教训后重新推荐：只用 heao 专业组级数据（已验证可靠），不碰本地学校级最低位次。

逻辑：
1. 从种子库筛含国贸/商务核心专业的公办院校
2. 用 heao getSchoolList 逐校查询，带位次窗口过滤（只返回位次匹配的）
3. 只保留 heao 返回了专业组、且组内有国贸/商务专业的
4. 输出真实可录的候选（专业组级，带最低分/位次/科目要求）
"""
import json
import sys
import time
import urllib.parse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from heao_client import get_json, load_token  # noqa: E402

API = "https://book.heao.com.cn/prod-api/choose/volunteer/getSchoolList"
BROTHER_RANK = 73822  # 注：若弟弟实际是480分，位次约81000，这里用宽窗覆盖两种可能

# 国贸/商务核心专业关键词
CORE_BIZ = ["国际经济与贸易", "国际商务", "跨境电子商务", "贸易"]

EXISTING = {
    "安阳学院", "商丘学院", "中原科技学院", "新乡工程学院", "郑州经贸学院",
    "长春财经学院", "西安外事学院", "广东理工学院", "陕西服装工程学院",
    "齐齐哈尔工程学院", "哈尔滨石油学院", "信阳学院", "黑龙江外国语学院",
}


def main() -> None:
    groups = yaml.safe_load(
        (ROOT / "data/seed/henan/program_groups_2026.yaml").read_text(encoding="utf-8")
    )
    unis_data = yaml.safe_load(
        (ROOT / "data/seed/henan/universities.yaml").read_text(encoding="utf-8")
    )
    uni_idx = {u["school_name"].split("(")[0]: u for u in unis_data}

    # 候选：公办 + 含国贸/商务核心专业 + 非志愿组已有
    candidates = []
    seen = set()
    for g in groups:
        name = g.get("school_name", "").split("(")[0]
        if name in EXISTING or name in seen:
            continue
        u = uni_idx.get(name, {})
        if u.get("ownership") != "公办":
            continue
        majors = g.get("included_majors", [])
        if not any(any(k in m for k in CORE_BIZ) for m in majors):
            continue
        seen.add(name)
        candidates.append((name, u.get("province", "?"), u.get("city", "?")))

    # 优先省内、邻省（学费低、区位近），其他省份靠后
    NEAR = ["河南", "山东", "河北", "安徽", "湖北", "山西", "陕西", "江西", "湖南"]
    candidates.sort(key=lambda x: (0 if x[1] == "河南" else (1 if x[1] in NEAR else 2), x[0]))

    print(f"公办+国贸商务核心 候选 {len(candidates)} 所，用 heao 逐校查专业组级数据...")
    token = load_token()

    matched = []
    raw_dir = ROOT / "data/evaluate/raw_candidates"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for i, (name, prov, city) in enumerate(candidates, 1):
        # heao 位次窗口：宽窗 5万-13万覆盖弟弟冲到保
        for lo, hi in [(50000, 130000), (30000, 50000)]:
            params = {
                "pageNum": "1", "pageSize": "10",
                "schoolName": name, "pcdm": "1",
                "minWc": str(lo), "maxWc": str(hi),
            }
            url = f"{API}?{urllib.parse.urlencode(params)}"
            try:
                data = get_json(url, token)
                rows = data.get("rows") or []
            except Exception:
                rows = []
            if rows:
                s = rows[0]
                # 保存原始响应
                safe_name = name.replace("/", "_")
                (raw_dir / f"{safe_name}.json").write_text(
                    json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                # 筛专业组：zyzh是组号 + 组内含国贸/商务专业
                for g in s.get("majorList", []):
                    if not str(g.get("zyzh", "")).strip().isdigit():
                        continue
                    wc = g.get("minWc")
                    if not wc:
                        continue
                    wc = int(wc)
                    majors = [
                        m.get("majorName", "")
                        for m in g.get("zyzMajorList", [])
                    ]
                    biz_in_group = [
                        m for m in majors if any(k in m for k in CORE_BIZ)
                    ]
                    if not biz_in_group:
                        continue
                    gap = wc - BROTHER_RANK
                    matched.append({
                        "school": name,
                        "province": prov,
                        "city": city,
                        "zyzh": g["zyzh"],
                        "requirement": g.get("kskmyqzw", ""),
                        "min_score": g.get("minCj"),
                        "rank": wc,
                        "gap": gap,
                        "biz_majors": biz_in_group,
                        "all_majors": majors,
                    })
                break  # 命中一个窗口就够了
        if i % 20 == 0:
            print(f"  已查 {i}/{len(candidates)}...", flush=True)
        time.sleep(0.2)

    # 按位次差排序
    matched.sort(key=lambda x: abs(x["gap"]))

    # 输出
    print(f"\nheao 验证通过（有专业组级真实位次 + 含国贸/商务专业）: {len(matched)} 个专业组")
    out = ROOT / "data/evaluate/biz_candidates_heao.json"
    out.write_text(json.dumps(matched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"原始数据: {out}")

    # 控制台预览
    for m in matched[:25]:
        tier = "冲" if m["gap"] < 2000 else ("稳" if m["gap"] < 9000 else ("保" if m["gap"] < 18000 else "垫"))
        print(f"  {tier} {m['school']:<18} {m['province']:<4} 组{m['zyzh']} {m['min_score']}分/{m['rank']}位 差{m['gap']:+d} | {','.join(m['biz_majors'][:2])}")


if __name__ == "__main__":
    main()
