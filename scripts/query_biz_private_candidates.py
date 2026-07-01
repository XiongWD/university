"""
重新推荐：公办够不上，改在民办/独立学院里找比当前13所更优的国贸商务候选。

已验证：弟弟位次73822够不上任何含国贸/商务的公办本科（212所全部heao查不到）。
本次：在民办/独立学院里，用heao查含国贸/商务核心专业 + 位次匹配的候选，
对比当前13所，找学费更低/区位更好/对口更强的替代或补充。
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
BROTHER_RANK = 73822
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

    # 候选：民办/独立学院 + 含国贸/商务核心专业 + 非已有
    candidates = []
    seen = set()
    for g in groups:
        name = g.get("school_name", "").split("(")[0]
        if name in EXISTING or name in seen:
            continue
        u = uni_idx.get(name, {})
        own = u.get("ownership", "")
        if own not in ("民办", "独立学院"):
            continue
        majors = g.get("included_majors", [])
        if not any(any(k in m for k in CORE_BIZ) for m in majors):
            continue
        seen.add(name)
        candidates.append((name, own, u.get("province", "?"), u.get("city", "?")))

    # 优先省内（学费低）、邻省
    NEAR = ["河南", "山东", "河北", "安徽", "湖北", "山西", "陕西", "江西", "湖南"]
    candidates.sort(key=lambda x: (0 if x[2] == "河南" else (1 if x[2] in NEAR else 2), x[0]))

    print(f"民办/独立学院+国贸商务核心 候选 {len(candidates)} 所，heao 逐校查...")
    token = load_token()
    matched = []

    for i, (name, own, prov, city) in enumerate(candidates, 1):
        for lo, hi in [(50000, 130000)]:
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
                for g in s.get("majorList", []):
                    if not str(g.get("zyzh", "")).strip().isdigit():
                        continue
                    wc = g.get("minWc")
                    if not wc:
                        continue
                    wc = int(wc)
                    majors = [m.get("majorName", "") for m in g.get("zyzMajorList", [])]
                    biz_in = [m for m in majors if any(k in m for k in CORE_BIZ)]
                    if not biz_in:
                        continue
                    gap = wc - BROTHER_RANK
                    matched.append({
                        "school": name, "ownership": own, "province": prov, "city": city,
                        "zyzh": g["zyzh"], "requirement": g.get("kskmyqzw", ""),
                        "min_score": g.get("minCj"), "rank": wc, "gap": gap,
                        "biz_majors": biz_in, "all_majors": majors,
                    })
                break
        time.sleep(0.2)

    matched.sort(key=lambda x: abs(x["gap"]))
    print(f"\nheao 验证通过: {len(matched)} 个民办/独立学院国贸商务专业组")

    out = ROOT / "data/evaluate/biz_private_candidates_heao.json"
    out.write_text(json.dumps(matched, ensure_ascii=False, indent=2), encoding="utf-8")

    for m in matched:
        tier = "冲" if m["gap"] < 2000 else ("稳" if m["gap"] < 9000 else ("保" if m["gap"] < 18000 else "垫"))
        print(f"  {tier} {m['school']:<20} {m['province']:<4} {m['ownership']:<5} 组{m['zyzh']} {m['min_score']}分/{m['rank']}位 差{m['gap']:+d} | {','.join(m['biz_majors'][:2])}")


if __name__ == "__main__":
    main()
