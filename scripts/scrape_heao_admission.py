"""
采集河南省考试院 book.heao.com.cn 的真实专业组级/专业级录取位次数据。

数据源：河南省考试院官方志愿填报系统（权威数据）
  接口：GET /prod-api/choose/volunteer/getSchoolList?pcdm=1&minWc=1&maxWc=300000&pageNum=&pageSize=
  返回：每校一条，含三级数据：
    - schoolRecentYearsAdmission：院校级多年录取（minCj/maxCj/maxWc/lqs）
    - majorList[]：专业组级（zyzh专业组号, kskmyqzw选科要求, minCj最低分, minWc最低位次, year）
    - majorList[].zyzMajorList[]：专业级（majorName, recentYearsAdmission含maxWc位次）

字段对照（参考显示页面 https://book.heao.com.cn/?#/choose）：
  minCj=最低分  maxCj=最高分  minWc/maxWc=位次  lqs=录取数  zyzh=专业组号
  kskmyqzw=选科要求  yxdh=河南院校代码  schoolCode=国标代码

输出：data/raw/henan_2026/heao_admission/
  - raw_page_{n}.json：原始接口响应（溯源）
  - groups.csv：专业组级录取位次（对齐 import CSV 列名）
  - majors.csv：专业级录取位次
"""
import argparse
import csv
import json
import ssl
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path("data/raw/henan_2026/heao_admission")
OUT.mkdir(parents=True, exist_ok=True)

# 从 cookie 文件读取 token（避免硬编码失效 token）
TOKEN_FILE = Path(r"C:\Users\Administrator\Downloads\cookies-2026-06-28 (1).json")
TOKEN = ""
if TOKEN_FILE.exists():
    _c = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    TOKEN = next((x["value"] for x in _c if x.get("name") == "Web-Token"), "")
if not TOKEN:
    TOKEN = ("eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
             "eyJsb2dpblR5cGUiOiJsb2dpbiIsImxvZ2luSWQiOiJzdHVkZW50OjIwNzA0MTIwMDU0NTgxODYyNDIi"
             "LCJyblN0ciI6Ing3dmFDN1BNOGo4eGFtbHQ1b2ZIOWllSlFVSG9xUUVpIiwidXNlcklkIjoyMDcwNDEyMDA1NDU4MTg2MjQyfQ."
             "wqLq4cqq_lJx4tN3PVS-hPIvDf6YCLNZnxqfKMjcJZA")

API = "https://book.heao.com.cn/prod-api/choose/volunteer/getSchoolList"
_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Cookie": f"Web-Token={TOKEN}",
    "Content-Language": "zh_CN",
    "Referer": "https://book.heao.com.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def fetch_page(page: int, size: int = 100) -> dict:
    """拉取一页院校数据。"""
    url = f"{API}?pageNum={page}&pageSize={size}&pcdm=1&minWc=1&maxWc=300000"
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=40, context=_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_school(school: dict) -> dict:
    """解析单校数据，提取院校级/专业组级/专业级录取位次。

    heao 的 majorList 是数组：2025 和 2024 是独立元素（各带 year 字段）。
    专业组级位次不在 majorList[] 顶层（minWc 多为空），而在组内专业的
    recentYearsAdmission[].maxWc 里。因此解析以专业级 recentYearsAdmission 为准。
    """
    name = school.get("schoolName", "")
    yxdh = str(school.get("yxdh") or "")      # 河南院校代码
    code = str(school.get("schoolCode") or "")  # 国标代码

    # 院校级
    school_history = []
    for h in school.get("schoolRecentYearsAdmission") or []:
        if h.get("maxWc"):
            school_history.append({
                "year": h.get("year"),
                "min_score": h.get("minCj"),
                "min_rank": h.get("maxWc"),
                "plan_count": h.get("lqs"),
            })

    # 专业组级：majorList 每个元素是一个 (zyzh, year) 组合。
    # 用 (zyzh) 做主键聚合所有年份的专业级数据（同一专业组在 2025/2024 是不同 majorList 元素）。
    groups_by_key: dict[str, dict] = {}  # zyzh -> {majors: [], elective_requirement}
    for m in school.get("majorList") or []:
        zyzh = str(m.get("zyzh") or "")
        if not zyzh:
            continue
        grp = groups_by_key.setdefault(zyzh, {
            "zyzh": zyzh,
            "elective_requirement": m.get("kskmyqzw", ""),
            "majors_by_code": {},  # major_code -> {major_name, history}
        })
        # 该组（某个年份的元素）下的专业
        for zm in m.get("zyzMajorList") or []:
            mcode = str(zm.get("majorCode") or zm.get("zydh") or "")
            mname = zm.get("majorName", "")
            maj = grp["majors_by_code"].setdefault(mcode, {
                "major_name": mname, "major_code": mcode,
                "zydh": str(zm.get("zydh") or ""), "history": [],
            })
            for rh in zm.get("recentYearsAdmission") or []:
                if not rh.get("maxWc"):
                    continue
                maj["history"].append({
                    "year": rh.get("year"),
                    "min_score": rh.get("minCj"),
                    "min_rank": rh.get("maxWc"),
                    "plan_count": rh.get("lqs"),
                    "avg_score": rh.get("lqpjf"),
                })

    # 展平为 groups 列表（专业级 history 去重同年份）
    groups = []
    for zyzh, grp in groups_by_key.items():
        majors = []
        for mcode, maj in grp["majors_by_code"].items():
            # 同年份去重（2025/2024 元素可能含同一专业的重复记录）
            seen_years = set()
            deduped = []
            for h in maj["history"]:
                y = str(h.get("year"))
                if y in seen_years:
                    continue
                seen_years.add(y)
                deduped.append(h)
            if deduped:
                majors.append({
                    "major_name": maj["major_name"], "major_code": maj["major_code"],
                    "zydh": maj["zydh"], "history": deduped,
                })
        if majors:
            groups.append({
                "zyzh": zyzh,
                "elective_requirement": grp["elective_requirement"],
                "majors": majors,
            })

    return {
        "school_name": name, "yxdh": yxdh, "school_code_guobiao": code,
        "school_history": school_history, "groups": groups,
    }

    return {
        "school_name": name, "yxdh": yxdh, "school_code_guobiao": code,
        "school_history": school_history, "groups": groups,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=0, help="限制页数（调试）")
    parser.add_argument("--reparse", action="store_true",
                        help="不重新抓接口，从已有 raw_page_*.json 重新解析")
    args = parser.parse_args()

    import glob
    all_schools = []

    if args.reparse:
        # 从已缓存的原始响应重新解析（解析逻辑修正后用，无需重新抓接口）
        files = sorted(glob.glob(str(OUT / "raw_page_*.json")))
        print(f"--reparse：从 {len(files)} 个 raw_page 重新解析")
        total = 0
        for f in files:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
            rows = data.get("rows") or data.get("data") or []
            total += len(rows)
            for s in rows:
                all_schools.append(parse_school(s))
        print(f"  重新解析 {total} 校")
    else:
        page = 1
        total = 0
        while True:
            data = fetch_page(page, args.page_size)
            rows = data.get("rows") or data.get("data") or []
            if page == 1:
                total = data.get("total", 0)
                print(f"接口返回 total={total}，开始分页采集（pageSize={args.page_size}）")
            if not rows:
                break
            # 保存原始页（溯源）
            (OUT / f"raw_page_{page:02d}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            for s in rows:
                all_schools.append(parse_school(s))
            print(f"  第 {page} 页: {len(rows)} 校，累计 {len(all_schools)}/{total}")
            if args.max_pages and page >= args.max_pages:
                print(f"  达到 --max-pages {args.max_pages}，停止（调试）")
                break
            if len(rows) < args.page_size:
                break
            page += 1
            time.sleep(0.5)  # 礼貌限速

    # 保存解析后的全量 JSON
    (OUT / "all_schools.json").write_text(
        json.dumps(all_schools, ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出专业组级 CSV（从组内专业 history 按年聚合，门槛=max(min_rank)）
    import_csv = OUT / "groups.csv"
    with import_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["school_name", "yxdh", "zyzh", "elective_requirement",
                    "year", "min_score", "min_rank"])
        n_groups = 0
        for s in all_schools:
            for g in s["groups"]:
                # 按年聚合组内专业
                by_year: dict[str, list[dict]] = {}
                for m in g["majors"]:
                    for h in m["history"]:
                        if h.get("min_rank") and h["min_rank"] > 0:
                            by_year.setdefault(str(h["year"]), []).append(h)
                for yr, items in by_year.items():
                    best = max(items, key=lambda x: x.get("min_rank") or 0)
                    w.writerow([s["school_name"], s["yxdh"], g["zyzh"],
                                g["elective_requirement"], yr,
                                best.get("min_score"), best.get("min_rank")])
                    n_groups += 1

    # 输出专业级 CSV
    majors_csv = OUT / "majors.csv"
    with majors_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["school_name", "yxdh", "zyzh", "major_name", "major_code",
                    "year", "min_score", "min_rank", "avg_score"])
        n_majors = 0
        for s in all_schools:
            for g in s["groups"]:
                for m in g["majors"]:
                    for h in m["history"]:
                        w.writerow([s["school_name"], s["yxdh"], g["zyzh"],
                                    m["major_name"], m["major_code"], h["year"],
                                    h["min_score"], h["min_rank"], h.get("avg_score")])
                        n_majors += 1

    print(f"\n完成：{len(all_schools)}/{total} 校")
    print(f"  专业组级记录: {n_groups} 行 → {import_csv}")
    print(f"  专业级记录:   {n_majors} 行 → {majors_csv}")
    print(f"  全量 JSON:    {OUT / 'all_schools.json'}")


if __name__ == "__main__":
    main()
