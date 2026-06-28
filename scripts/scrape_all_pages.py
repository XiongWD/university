"""
Scrape ALL pages of plan data by navigating rendered pages.
Uses Playwright to get rendered DOM data + pagination.
"""
import asyncio, json, csv, sys
from pathlib import Path
try:
    from playwright.async_api import async_playwright
except ImportError:
    sys.exit(1)

OUT = Path("data/raw/henan_2026")
COOKIES = [
    {"url": "https://www.gaokao.cn", "name": "_c_WBKFRo", "value": "VSGvAAq0Edw8SS4Wkrp6rGJxQDOejWkZVxArwVm1"},
    {"url": "https://www.gaokao.cn", "name": "_token.common", "value": "64a06244f95046fc9c14df52f06aa9bb"},
    {"url": "https://www.gaokao.cn", "name": "_token.gaokao", "value": "64a06244f95046fc9c14df52f06aa9bb"},
    {"url": "https://www.gaokao.cn", "name": "originLoginKey", "value": "9a10e5875081002ac16346e577fd2e6fe9987c94e0544d33298aafb775f8842ffd554babbfcfe11915670ecf2157467280dc59641a631e3d0b214145f9668dacb9c7403aadad41e54c7ae5216be1852c63641ffc99c43102af230a5fe68f35739b14ba2f4e6b6fb2e43212e7eb444b226ae56b49f4ed613a663d8f113da2f7c7"},
]

async def get_plan_data(page, school_id):
    """Get plan data from DOM for a school, paginating through all pages."""
    all_items = []
    
    # Navigate to the plan page (sturule = 招生计划)
    await page.goto(f"https://www.gaokao.cn/school/{school_id}/sturule",
                    wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)
    
    max_pages = 10  # safety limit
    for page_num in range(1, max_pages + 1):
        # Extract plan data from rendered DOM
        items = await page.evaluate("""
            () => {
                const rows = document.querySelectorAll('table tbody tr, .ant-table-tbody tr');
                const results = [];
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 5) {
                        results.push({
                            sp_name: cells[0]?.textContent?.trim() || '',
                            sg_info: cells[1]?.textContent?.trim() || '',
                            num: cells[2]?.textContent?.trim() || '',
                            tuition: cells[3]?.textContent?.trim() || '',
                            length: cells[4]?.textContent?.trim() || '',
                        });
                    }
                });
                return results;
            }
        """)
        
        if items:
            all_items.extend(items)
        
        # Try to click next page
        try:
            next_btn = page.locator('li.ant-pagination-next:not(.ant-pagination-disabled)')
            if await next_btn.count() > 0:
                await next_btn.click()
                await page.wait_for_timeout(2000)
                try: await page.wait_for_load_state("networkidle", timeout=10000)
                except: pass
            else:
                break
        except:
            break
    
    return all_items

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0', viewport={'width': 1920, 'height': 1080}, locale='zh-CN',
        )
        await ctx.add_cookies(COOKIES)
        page = await ctx.new_page()

        # Test with school 62 first
        print("[1] Testing with school 62 (郑州大学)...")
        items = await get_plan_data(page, "62")
        print(f"  Got {len(items)} items from DOM")
        for item in items[:5]:
            print(f"    {json.dumps(item, ensure_ascii=False)}")
        
        # Save test
        (OUT / "dom_test_62.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')

        await browser.close()

asyncio.run(main())
