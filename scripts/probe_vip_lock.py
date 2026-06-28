"""验证未付费 cookie 能否拿到完整专业组数据（是否有付费墙截断）。
对比：DOM 中渲染的组数 vs 页面声称的总组数；检查是否有锁定/VIP 提示。"""
import asyncio, json, re
from urllib.parse import quote
from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_FILE = Path(r"C:\Users\Administrator\Downloads\cookies-2026-06-26.json")
raw = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
cookies = [{"name": c["name"], "value": c["value"], "domain": c.get("domain", ".gaokao.cn"),
            "path": c.get("path", "/"), "expires": c.get("expirationDate", -1),
            "httpOnly": c.get("httpOnly", False), "secure": c.get("secure", False), "sameSite": "Lax"}
           for c in raw if c.get("value")]


async def check_school(page, sid, name):
    url = (f"https://mnzy.gaokao.cn/?universityName={quote(name)}"
           "&type=ALL&notRecommendScore=1&for=school_clq&source=school&zsgkId=" + sid)
    await page.goto(url, wait_until="networkidle", timeout=45000)
    await page.wait_for_timeout(3500)
    body_text = await page.inner_text("body")
    # DOM 渲染的组数
    dom_groups = await page.evaluate("""() => document.querySelectorAll('[data-row-key]').length""")
    # 页面声称的总组数（常见表述："共X个专业组" 或 tab 上的数字）
    m_total = re.search(r"共\s*(\d+)\s*个?[专业组院校]", body_text)
    claimed = m_total.group(1) if m_total else "?"
    # 付费墙信号
    lock_signals = []
    for kw in ["VIP", "vip", "会员", "付费", "解锁", "升级", "查看更多", "登录查看", "仅限", "特权", "购买", "至尊卡", "志愿卡"]:
        if kw in body_text:
            # 取上下文
            idx = body_text.find(kw)
            lock_signals.append(body_text[max(0, idx-15):idx+25].replace("\n", " ").strip())
    # 提取所有组号
    group_nums = re.findall(r"\[(\d+)组\]", body_text)
    return {
        "school": name, "dom_groups": dom_groups,
        "group_nums": group_nums,
        "claimed_total": claimed,
        "lock_signals": list(set(lock_signals))[:8],
    }


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080}, locale="zh-CN")
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()

        # 选专业组较多的学校测试
        for sid, name in [("62", "郑州大学"), ("1400", "青岛城市学院"), ("114", "浙江大学")]:
            r = await check_school(page, sid, name)
            print(f"\n=== {r['school']} (zsgkId={sid}) ===")
            print(f"  DOM 渲染组数: {r['dom_groups']}")
            print(f"  页面声称总数: {r['claimed_total']}")
            print(f"  组号: {r['group_nums']}")
            print(f"  付费/锁定信号: {r['lock_signals'] if r['lock_signals'] else '无'}")

        await browser.close()

asyncio.run(main())
