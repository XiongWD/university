"""
Batch extract ALL plan pages for schools with >=10 plans.
Uses Playwright DOM scraping with pagination.
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

async def extract_school(page, school_id):
    """Extract all plan data for a school via DOM pagination."""
    try:
        await page.goto(f"https://www.gaokao.cn/school/{school_id}/sturule",
                        wait_until="domcontentloaded", timeout=20000)
    except:
        return []
    
    await page.wait_for_timeout(3000)
    
    all_items = []
    for pg in range(1, 20):
        items = await page.evaluate("""() => {
            const r = [];
            const rows = document.querySelectorAll('table.tb-normal tbody tr');
            for (const row of rows) {
                const c = row.querySelectorAll('td');
                if (c.length < 3) continue;
                const t = c[0].innerText || '';
                const sp = t.split('\\n')[0] || '';
                const sg = (t.match(/选科要求：(.+)/) || ['',''])[1].trim();
                const rm = (t.match(/（[^）]+）/) || [''])[0];
                const num = (c[1].innerText || '').replace(/[^0-9]/g,'') || '0';
                const tt = (c[2].innerText || '').split('\\n');
                const len = (tt[0]||'').replace(/[^0-9]/g,'') || '4';
                const fee = (tt[1]||'').replace(/[^0-9]/g,'') || '0';
                r.push({sp_name:sp, sg_info:sg, remark:rm, num, tuition:fee, length:len, page:pg});
            }
            return r;
        }""")
        
        if not items or len(items) == 0:
            break
        all_items.extend(items)
        
        # Check if next page available and click it
        has_next = await page.evaluate("""() => {
            const n = document.querySelector('li.ant-pagination-next');
            return n && !n.className.includes('disabled');
        }""")
        if not has_next:
            break
        
        await page.evaluate("""() => {
            const n = document.querySelector('li.ant-pagination-next');
            if (n && !n.className.includes('disabled')) n.click();
        }""")
        await page.wait_for_timeout(1500)
    
    return all_items

async def main():
    # Load existing API data to find schools with >=10 plans
    with open(OUT / "henan_2026_all_plans.json", 'r', encoding='utf-8') as f:
        api_plans = json.load(f)
    
    from collections import Counter
    school_counts = Counter(p.get('school_id', '') for p in api_plans)
    at_limit = [sid for sid, cnt in school_counts.items() if cnt >= 10]
    print(f"Schools with >=10 plans to re-scrape: {len(at_limit)}")
    
    # Also load linkage for school names
    import urllib.request
    try:
        req = urllib.request.Request(
            'https://static-data.gaokao.cn/www/2.0/info/linkage.json?a=www.gaokao.cn',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        linkage = json.loads(resp.read())
        school_names = {s['school_id']: s['name'] for s in linkage.get('data', {}).get('school', [])}
    except:
        school_names = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0', viewport={'width': 1920, 'height': 1080}, locale='zh-CN',
        )
        await ctx.add_cookies(COOKIES)
        page = await ctx.new_page()
        
        all_new_plans = []
        existing_keys = set()
        for p_data in api_plans:
            key = (p_data.get('school_id',''), p_data.get('sp_name',''), p_data.get('sg_info',''))
            existing_keys.add(key)
        
        for idx, sid in enumerate(at_limit[:50]):  # Batch: first 50 schools
            name = school_names.get(sid, sid)
            print(f"[{idx+1}/{len(at_limit)}] Scraping {name} (id={sid})...")
            
            items = await extract_school(page, sid)
            print(f"  Got {len(items)} items")
            
            # Only keep items we don't already have
            for item in items:
                key = (sid, item.get('sp_name',''), item.get('sg_info',''))
                if key not in existing_keys:
                    item['school_id'] = sid
                    item['school_name'] = name
                    all_new_plans.append(item)
                    existing_keys.add(key)
            
            if (idx + 1) % 10 == 0:
                print(f"  Progress: {len(all_new_plans)} new plans found so far")
        
        print(f"\nTotal new plans found: {len(all_new_plans)}")
        
        # Save new plans
        if all_new_plans:
            (OUT / "henan_2026_new_plans.json").write_text(
                json.dumps(all_new_plans, ensure_ascii=False, indent=2), encoding='utf-8')
            
            # Merge with existing
            all_plans_merged = api_plans + all_new_plans
            (OUT / "henan_2026_merged_plans.json").write_text(
                json.dumps(all_plans_merged, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"Merged total: {len(all_plans_merged)} plans")
        
        await browser.close()

asyncio.run(main())
