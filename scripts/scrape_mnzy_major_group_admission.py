"""
采集 mnzy.gaokao.cn 的真实专业组级录取位次数据（基于已验证的 DOM 提取方案）。

数据源：mnzy 是 Nuxt.js SSR，专业组录取数据直接渲染在首屏 DOM。
  每个专业组是一个 [data-row-key="院校代码+组号"] 元素，innerText 含
  「25年录取 N人 最低分 X分 最低位次 Y名 ... 24年 ... 23年 ...」。

采集流程（每校）：
  1. goto mnzy 院校详情页（zsgkId=系统 school_code）
  2. 提取所有 [data-row-key] 元素的 innerText
  3. 正则解析每年的最低分/最低位次/录取人数/26年计划/选科要求

输出：data/raw/henan_2026/mnzy_admission/{school_code}.json
  [{group_code(如108), recruit_code(如6974), years:[{year,min_score,min_rank,plan_count}],
    plan_2026, subject_requirement, major_categories}]

用法：
  python scripts/scrape_mnzy_major_group_admission.py --zsgk-id 1400   # 单校
  python scripts/scrape_mnzy_major_group_admission.py --all            # 全量
  python scripts/scrape_mnzy_major_group_admission.py --all --limit 10
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("pip install playwright", file=sys.stderr); sys.exit(1)

OUT = Path("data/raw/henan_2026/mnzy_admission")
OUT.mkdir(parents=True, exist_ok=True)
COOKIE_FILE = Path(r"C:\Users\Administrator\Downloads\cookies-2026-06-26.json")


def load_cookies():
    raw = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    return [
        {"name": c["name"], "value": c["value"], "domain": c.get("domain", ".gaokao.cn"),
         "path": c.get("path", "/"), "expires": c.get("expirationDate", -1),
         "httpOnly": c.get("httpOnly", False), "secure": c.get("secure", False), "sameSite": "Lax"}
        for c in raw if c.get("value")
    ]


def parse_group_text(text: str, group_code: str, recruit_code: str) -> dict:
    """解析单个专业组 DOM 文本，提取多年录取数据。

    DOM 文本格式（实测）：
      '... 26年计划 4人 院校代码 6974 选科要求 不限
       25年录取 2人 最低分 486分 最低位次 75472名 比我位次 靠后1650名 等效分 475 分 ...
       24年录取 2人 最低分 439分 最低位次 87279名 ...
       23年录取 2人 最低分 470分 最低位次 93542名 ...'
    """
    # 每年块：N年录取 X人 最低分 Y分 最低位次 Z名
    year_pattern = re.compile(
        r"(\d{2})年录取\s*(\d+)人\s*最低分\s*(\d+)分\s*最低位次\s*(\d+)名"
    )
    years = []
    for m in year_pattern.finditer(text):
        yy = int(m.group(1))
        # 25→2025, 24→2024, 23→2023
        year = 2000 + yy if yy < 100 else yy
        years.append({
            "year": year,
            "min_score": int(m.group(3)),
            "min_rank": int(m.group(4)),
            "plan_count": int(m.group(2)),
        })
    years.sort(key=lambda y: y["year"], reverse=True)

    # 26年计划（当年招生计划，非历史录取）
    plan_2026 = None
    m26 = re.search(r"26年计划\s*(\d+)人", text)
    if m26:
        plan_2026 = int(m26.group(1))

    # 选科要求
    subject_req = ""
    msub = re.search(r"选科要求\s*([^2]+?)(?:\d{2}年|$)", text)
    if msub:
        subject_req = msub.group(1).strip()

    return {
        "group_code": group_code,
        "recruit_code": recruit_code,
        "years": years,
        "plan_2026": plan_2026,
        "subject_requirement": subject_req,
        "raw_text": text[:600],  # 保留原始文本便于核对
    }


async def scrape_school(page, zsgk_id: str, school_name: str) -> list[dict]:
    """采集单校所有专业组的录取数据。"""
    from urllib.parse import quote
    url = (f"https://mnzy.gaokao.cn/?universityName={quote(school_name)}"
           "&type=ALL&notRecommendScore=1&for=school_clq&source=school"
           f"&zsgkId={zsgk_id}")
    await page.goto(url, wait_until="networkidle", timeout=45000)
    await page.wait_for_timeout(3500)

    # 提取所有 [data-row-key] 元素
    rows = await page.evaluate("""() => {
        const els = document.querySelectorAll('[data-row-key]');
        return Array.from(els).map(el => ({
            key: el.getAttribute('data-row-key'),
            text: el.innerText.replace(/\\s+/g, ' ').trim(),
        }));
    }""")

    results = []
    for row in rows:
        key = row["key"] or ""
        text = row["text"]
        if not text:
            continue
        # data-row-key 格式：院校代码+组号（如 6974108 = 6974 + 108）
        # 组号是末尾部分；recruit_code 是前缀。但长度不固定，用文本里的「N组」更可靠
        m_group = re.search(r"\[(\d+)组\]", text)
        m_recruit = re.search(r"院校代码\s*(\d+)", text)
        group_code = m_group.group(1) if m_group else key[-3:]
        recruit_code = m_recruit.group(1) if m_recruit else ""
        parsed = parse_group_text(text, group_code, recruit_code)
        if parsed["years"]:  # 只保留有录取数据的
            results.append(parsed)
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zsgk-id", help="单校 zsgkId（=系统 school_code）")
    parser.add_argument("--all", action="store_true", help="全量采集")
    parser.add_argument("--limit", type=int, default=0, help="--all 时限制数量")
    args = parser.parse_args()
    if not args.zsgk_id and not args.all:
        parser.error("需指定 --zsgk-id 或 --all")

    import yaml
    unis = yaml.safe_load(Path("data/seed/henan/universities.yaml").read_text(encoding="utf-8"))
    unis = unis if isinstance(unis, list) else (unis.get("universities") or unis.get("records") or [])

    if args.all:
        targets = [(str(u["school_code"]), u.get("school_name", "")) for u in unis if u.get("school_code")]
        if args.limit:
            targets = targets[:args.limit]
    else:
        name = next((u.get("school_name", "") for u in unis if str(u.get("school_code")) == args.zsgk_id), "")
        targets = [(args.zsgk_id, name)]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}, locale="zh-CN")
        await ctx.add_cookies(load_cookies())
        page = await ctx.new_page()

        total_groups = 0
        ok = 0
        for i, (sid, sname) in enumerate(targets):
            try:
                groups = await scrape_school(page, sid, sname)
                if groups:
                    (OUT / f"{sid}.json").write_text(
                        json.dumps({"school_code": sid, "school_name": sname,
                                    "groups": groups}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
                    total_groups += len(groups)
                    ok += 1
                    print(f"[{i+1}/{len(targets)}] {sid} {sname}: {len(groups)} 组 ✓")
                else:
                    print(f"[{i+1}/{len(targets)}] {sid} {sname}: 无数据")
                await asyncio.sleep(0.8)
            except Exception as e:
                print(f"[{i+1}/{len(targets)}] {sid} {sname}: 失败 {e}")

        await browser.close()

    print(f"\n完成：{ok}/{len(targets)} 校有数据，共 {total_groups} 个专业组")
    print(f"原始数据：{OUT}")


if __name__ == "__main__":
    asyncio.run(main())
