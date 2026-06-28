"""
Mass scraper - verify signsafe works for different schools, then batch scrape all.
"""
import asyncio, json, csv, sys
from pathlib import Path
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("pip install playwright"); sys.exit(1)

OUT = Path("data/raw/henan_2026")
OUT.mkdir(parents=True, exist_ok=True)

cookies_data = [
    {"url": "https://www.gaokao.cn", "name": "_c_WBKFRo", "value": "VSGvAAq0Edw8SS4Wkrp6rGJxQDOejWkZVxArwVm1"},
    {"url": "https://www.gaokao.cn", "name": "_token.common", "value": "64a06244f95046fc9c14df52f06aa9bb"},
    {"url": "https://www.gaokao.cn", "name": "_token.gaokao", "value": "64a06244f95046fc9c14df52f06aa9bb"},
    {"url": "https://www.gaokao.cn", "name": "fillVolunteerData", "value": "%7B%22year%22%3A2026%2C%22province%22%3A%22%E6%B2%B3%E5%8D%97%22%2C%22score%22%3A480%2C%22optional%22%3A%22%E5%8E%86%E5%8F%B2%2C%E6%94%BF%E6%B2%BB%2C%E5%9C%B0%E7%90%86%22%2C%22classify%22%3A%22%E5%8E%86%E5%8F%B2%22%2C%22ranks%22%3A73822%2C%22gradeType%22%3Anull%2C%22subjects%22%3A%22%E5%8E%86%E5%8F%B2%2C%E6%94%BF%E6%B2%BB%2C%E5%9C%B0%E7%90%86%22%2C%22batch%22%3A%22%E6%9C%AC%E7%A7%91%E6%89%B9%22%2C%22artCategory%22%3Anull%2C%22entrantType%22%3A1%2C%22artRank%22%3Anull%2C%22artScore%22%3Anull%2C%22spring%22%3A%7B%22score%22%3Anull%2C%22subjects%22%3Anull%2C%22category%22%3Anull%2C%22classify%22%3Anull%2C%22ranks%22%3Anull%2C%22province%22%3Anull%2C%22gradeType%22%3Anull%7D%7D"},
    {"url": "https://www.gaokao.cn", "name": "originLoginKey", "value": "9a10e5875081002ac16346e577fd2e6fe9987c94e0544d33298aafb775f8842ffd554babbfcfe11915670ecf2157467280dc59641a631e3d0b214145f9668dacb9c7403aadad41e54c7ae5216be1852c63641ffc99c43102af230a5fe68f35739b14ba2f4e6b6fb2e43212e7eb444b226ae56b49f4ed613a663d8f113da2f7c7"},
]

async def call_plan_api(page, school_id, batch_id="14", page_num=1):
    """Call the special_plan API from within browser context."""
    result = await page.evaluate("""
        async (params) => {
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
                        'local_batch_id': params.batch_id,
                        'local_province_id': '41',
                        'local_type_id': '2074',
                        'page': params.page,
                        'platform': '2',
                        'school_id': params.school_id,
                        'sg_xuanke': '',
                        'size': 100,
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
    """, {"school_id": str(school_id), "batch_id": str(batch_id), "page": page_num})
    return json.loads(result)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}, locale='zh-CN',
        )
        await ctx.add_cookies(cookies_data)
        page = await ctx.new_page()

        # Load gaokao.cn to establish session
        print("[1] Loading gaokao.cn to establish session...")
        await page.goto("https://www.gaokao.cn/school/62/introduce",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Test with different school IDs using the same signsafe
        print("[2] Testing signsafe with different school IDs...")
        test_ids = ["62", "1920", "880", "1324", "1502"]
        for sid in test_ids:
            data = await call_plan_api(page, sid)
            items = data.get("data", {}).get("item", [])
            num_found = data.get("data", {}).get("numFound", 0)
            print(f"  school_id={sid}: {num_found} plans, returned {len(items)} items")
            if items:
                print(f"    First: {items[0].get('sp_name','?')} - num={items[0].get('num','?')} - tuition={items[0].get('tuition','?')}")

        # If signsafe works, batch scrape all schools
        print("\n[3] Fetching all school IDs for Henan...")
        # Get total count first with the exact working request
        school_list_raw = await page.evaluate("""
            async () => {
                const resp = await fetch('https://api-gaokao.zjzw.cn/apidata/web', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'Origin': 'https://www.gaokao.cn'},
                    body: JSON.stringify({
                        'autosign': '', 'keyword': '', 'local_type_id': '2074',
                        'page': 1, 'platform': '2', 'province_id': '41', 'ranktype': '',
                        'request_type': 1, 'size': 200, 'spe_ids': '',
                        'top_school_id': '1920,880,2451,1324,1502,2671,2638',
                        'uri': 'v1/school/lists',
                        'signsafe': '7485c1698dfce2981951d257bd4b5b50'
                    })
                });
                const data = await resp.json();
                return JSON.stringify(data);
            }
        """)
        school_data = json.loads(school_list_raw) if isinstance(school_list_raw, str) else school_list_raw
        if isinstance(school_data, str):
            school_data = json.loads(school_data)
        schools = school_data.get("data", {}).get("item", [])
        total = school_data.get("data", {}).get("numFound", 0)
        print(f"  Found {len(schools)} schools (total: {total})")
        
        # Save school list
        school_ids = [s["school_id"] for s in schools if "school_id" in s]
        all_schools_file = OUT / "henan_school_ids.json"
        all_schools_file.write_text(json.dumps(school_ids, indent=2), encoding='utf-8')
        print(f"  Saved {len(school_ids)} school IDs to {all_schools_file}")
        
        # Batch scrape all plans
        print(f"\n[4] Batch scraping plans for all schools...")
        all_plans = []
        for i, sid in enumerate(school_ids):
            data = await call_plan_api(page, sid)
            items = data.get("data", {}).get("item", [])
            num_found = data.get("data", {}).get("numFound", 0)
            
            if items:
                for item in items:
                    item["school_id"] = sid
                all_plans.extend(items)
            
            if (i+1) % 10 == 0:
                print(f"  Progress: {i+1}/{len(school_ids)} schools, {len(all_plans)} plans collected")
        
        print(f"\n  Total: {len(all_plans)} plans from {len(school_ids)} schools")
        
        # Save to CSV
        if all_plans:
            fieldnames = ["school_id", "sp_name", "num", "tuition", "length", "sg_info", "zslx_name", "remark", "special_group"]
            with open(ALL_PLANS_CSV, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                w.writeheader()
                w.writerows(all_plans)
            print(f"  Saved to {ALL_PLANS_CSV}")
        
        # Also save raw JSON
        plans_file = OUT / "henan_2026_all_plans.json"
        plans_file.write_text(json.dumps(all_plans, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  Saved to {plans_file}")

        await browser.close()

ALL_PLANS_CSV = OUT / "henan_2026_all_plans.csv"
asyncio.run(main())
