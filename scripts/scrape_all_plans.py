"""
Mass scraper for Henan 2026 enrollment plans using Playwright.
Uses browser automation to generate valid signsafe tokens.
"""
import asyncio, json, csv, os, sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("pip install playwright")
    sys.exit(1)

OUT = Path("data/raw/henan_2026")
OUT.mkdir(parents=True, exist_ok=True)

cookies_data = [
    {"url": "https://www.gaokao.cn", "name": "_c_WBKFRo", "value": "VSGvAAq0Edw8SS4Wkrp6rGJxQDOejWkZVxArwVm1"},
    {"url": "https://www.gaokao.cn", "name": "_token.common", "value": "64a06244f95046fc9c14df52f06aa9bb"},
    {"url": "https://www.gaokao.cn", "name": "_token.gaokao", "value": "64a06244f95046fc9c14df52f06aa9bb"},
    {"url": "https://www.gaokao.cn", "name": "fillVolunteerData", "value": "%7B%22year%22%3A2026%2C%22province%22%3A%22%E6%B2%B3%E5%8D%97%22%2C%22score%22%3A480%2C%22optional%22%3A%22%E5%8E%86%E5%8F%B2%2C%E6%94%BF%E6%B2%BB%2C%E5%9C%B0%E7%90%86%22%2C%22classify%22%3A%22%E5%8E%86%E5%8F%B2%22%2C%22ranks%22%3A73822%2C%22gradeType%22%3Anull%2C%22subjects%22%3A%22%E5%8E%86%E5%8F%B2%2C%E6%94%BF%E6%B2%BB%2C%E5%9C%B0%E7%90%86%22%2C%22batch%22%3A%22%E6%9C%AC%E7%A7%91%E6%89%B9%22%2C%22artCategory%22%3Anull%2C%22entrantType%22%3A1%2C%22artRank%22%3Anull%2C%22artScore%22%3Anull%2C%22spring%22%3A%7B%22score%22%3Anull%2C%22subjects%22%3Anull%2C%22category%22%3Anull%2C%22classify%22%3Anull%2C%22ranks%22%3Anull%2C%22province%22%3Anull%2C%22gradeType%22%3Anull%7D%7D"},
    {"url": "https://www.gaokao.cn", "name": "originLoginKey", "value": "9a10e5875081002ac16346e577fd2e6fe9987c94e0544d33298aafb775f8842ffd554babbfcfe11915670ecf2157467280dc59641a631e3d0b214145f9668dacb9c7403aadad41e54c7ae5216be1852c63641ffc99c43102af230a5fe68f35739b14ba2f4e6b6fb2e43212e7eb444b226ae56b49f4ed613a663d8f113da2f7c7"},
    {"url": "https://www.gaokao.cn", "name": "parseLoginKey", "value": "%7B%22phone%22%3A%2213418660438%22%2C%22mac%22%3A%22841b079c84178f7e152e2934dbae99d4%22%2C%22agent%22%3A%226%22%2C%22time%22%3A%221782482448%22%2C%22is_perfect%22%3A%221%22%2C%22wx_uin%22%3A%22%22%2C%22openid%22%3A%22%22%2C%22random%22%3A%22d7RZ4omG%22%7D"},
]

ALL_PLANS_CSV = OUT / "henan_2026_all_plans.csv"
ALL_SCHOOLS_JSON = OUT / "henan_schools.json"
PROGRESS_JSON = OUT / "scrape_progress.json"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}, locale='zh-CN',
        )
        await ctx.add_cookies(cookies_data)
        page = await ctx.new_page()

        captured = []
        async def on_response(response):
            url = response.url
            if 'api-gaokao.zjzw.cn' in url:
                try:
                    body = await response.body()
                    captured.append({
                        'url': url,
                        'status': response.status,
                        'body': body.decode('utf-8', errors='replace')[:5000],
                    })
                except: pass
        
        page.on('response', on_response)

        # Step 1: Load gaokao.cn school page to generate valid session
        print("[1] Loading gaokao.cn school page...")
        await page.goto("https://www.gaokao.cn/school/62/introduce",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Step 2: Try to get the plan data by intercepting API calls
        # The plan data API is called when "招生计划" tab is clicked
        # Use page.evaluate to make a direct API call with Playwright's auth context
        print("[2] Trying direct API call via fetch...")
        
        plan_data = await page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('https://api-gaokao.zjzw.cn/apidata/web', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Origin': 'https://www.gaokao.cn',
                            'Referer': 'https://www.gaokao.cn/',
                        },
                        body: JSON.stringify({
                            'autosign': '',
                            'like_spname': '',
                            'local_batch_id': '14',
                            'local_province_id': '41',
                            'local_type_id': '2074',
                            'page': 1,
                            'platform': '2',
                            'school_id': '62',
                            'sg_xuanke': '',
                            'size': 50,
                            'special_group': '',
                            'uri': 'v1/school/special_plan',
                            'year': '2026',
                            'signsafe': '751346eb97a6672dc1771bd63f83dfca'
                        })
                    });
                    const data = await resp.json();
                    return JSON.stringify(data);
                } catch(e) {
                    return 'Error: ' + e.message;
                }
            }
        """)
        
        print(f"  Plan API response: {plan_data[:500]}")

        # Step 3: Save all captured responses    
        api_file = OUT / "playwright_api_captures.json"
        api_file.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\n[3] Saved {len(captured)} API responses to {api_file}")

        await browser.close()

asyncio.run(main())
