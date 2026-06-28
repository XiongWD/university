"""
Verify if schools are missing data and try to get more pages.
"""
import asyncio, json, sys
from pathlib import Path
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("pip install playwright"); sys.exit(1)

OUT = Path("data/raw/henan_2026")

COOKIES = [
    {"url": "https://www.gaokao.cn", "name": "_c_WBKFRo", "value": "VSGvAAq0Edw8SS4Wkrp6rGJxQDOejWkZVxArwVm1"},
    {"url": "https://www.gaokao.cn", "name": "_token.common", "value": "64a06244f95046fc9c14df52f06aa9bb"},
    {"url": "https://www.gaokao.cn", "name": "_token.gaokao", "value": "64a06244f95046fc9c14df52f06aa9bb"},
    {"url": "https://www.gaokao.cn", "name": "originLoginKey", "value": "9a10e5875081002ac16346e577fd2e6fe9987c94e0544d33298aafb775f8842ffd554babbfcfe11915670ecf2157467280dc59641a631e3d0b214145f9668dacb9c7403aadad41e54c7ae5216be1852c63641ffc99c43102af230a5fe68f35739b14ba2f4e6b6fb2e43212e7eb444b226ae56b49f4ed613a663d8f113da2f7c7"},
]

async def call_api(page, params):
    result = await page.evaluate("""
        async (params) => {
            try {
                const resp = await fetch('https://api-gaokao.zjzw.cn/apidata/web', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'Origin': 'https://www.gaokao.cn', 'Referer': 'https://www.gaokao.cn/'},
                    body: JSON.stringify(params)
                });
                const data = await resp.json();
                return JSON.stringify(data);
            } catch(e) {
                return JSON.stringify({error: e.message});
            }
        }
    """, params)
    if isinstance(result, str):
        try: return json.loads(result)
        except: return None
    return result

async def try_different_params(page, base_params):
    """Try different parameter combinations to get more results per page."""
    results = {}
    
    # Try different page size parameter names
    size_params = [
        {'size': 100},
        {'size': 200},
        {'size': 50},
        {'limit': 100},
        {'pageSize': 100},
        {'page_size': 100},
        {'rows': 100},
        {'max': 100},
        {'count': 100},
    ]
    
    for extra in size_params:
        params = {**base_params, **extra}
        data = await call_api(page, params)
        if data:
            inner = data.get('data', {})
            if isinstance(inner, str):
                try: inner = json.loads(inner)
                except: pass
            if isinstance(inner, dict):
                items = inner.get('item', [])
                num_found = inner.get('numFound', 0)
                key = list(extra.keys())[0]
                results[key + '=' + str(list(extra.values())[0])] = {
                    'returned': len(items),
                    'total': num_found
                }
    
    return results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0', viewport={'width': 1920, 'height': 1080}, locale='zh-CN',
        )
        await ctx.add_cookies(COOKIES)
        page = await ctx.new_page()

        print("[1] Establishing session...")
        await page.goto("https://www.gaokao.cn/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        # Load existing data and find schools with exactly 10 plans
        with open(OUT / "henan_2026_all_plans.json", 'r', encoding='utf-8') as f:
            existing = json.load(f)
        
        from collections import Counter
        school_counts = Counter(p.get('school_name', str(p.get('school_id', ''))) for p in existing)
        at_limit = [(name, sid, count) for name, sid, count in 
                    sorted(((name, next((p['school_id'] for p in existing if p.get('school_name')==name), ''), count) 
                           for name, count in school_counts.items() if count >= 10),
                          key=lambda x: -x[2])]
        
        print(f"[2] Schools with >=10 plans: {len(at_limit)}")
        
        # Test 1: Try different size params on school 62 (郑州大学, 35 total)
        print("\n[3] Testing different page size params on school_id=62...")
        base_params = {
            'autosign': '', 'like_spname': '', 'local_batch_id': '14',
            'local_province_id': '41', 'local_type_id': '2074',
            'page': 1, 'platform': '2', 'school_id': '62',
            'sg_xuanke': '', 'size': 10, 'special_group': '',
            'uri': 'v1/school/special_plan', 'year': '2026',
            'signsafe': '751346eb97a6672dc1771bd63f83dfca'
        }
        
        results = await try_different_params(page, base_params)
        for param, r in results.items():
            print(f"  {param}: returned={r['returned']}, total={r['total']}")
        
        # Test 2: Try pages 2-4 for school 62 with the CORRECT signsafe
        # To get the correct signsafe, we need the frontend to generate it
        # So let's navigate to the school page and intercept the API call
        print("\n[4] Attempting to get page 2 via browser navigation...")
        
        # Navigate to gaokao.cn school page with special plan visible
        await page.goto("https://www.gaokao.cn/school/62/introduce",
                        wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # Set up request interception
        api_calls = []
        async def on_request(request):
            if 'api-gaokao.zjzw.cn' in request.url:
                api_calls.append({
                    'url': request.url,
                    'method': request.method,
                    'post_data': request.post_data[:2000] if request.post_data else None,
                })
        
        page.on('request', on_request)
        
        # Scroll to find/click pagination
        # First get the current page content
        body_text = await page.inner_text('body')
        print(f"  Page content preview: {body_text[:200]}...")
        
        # Try to find and click "下一页" or load more
        for selector in ['text=下一页', 'text=2', 'text=›', 'text=»', '[class*="next"]', '[class*="page-item"]', '[class*="pagination"]']:
            try:
                el = await page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    print(f"  Found: '{text.strip()}' at selector '{selector}'")
                    await el.click()
                    await page.wait_for_timeout(3000)
                    print(f"  Clicked! API calls now: {len(api_calls)}")
                    break
            except:
                pass
        
        # Check if any new API calls were made
        print(f"\n[5] New API calls captured: {len(api_calls)}")
        for c in api_calls:
            print(f"\n  URL: {c['url'][:200]}")
            if c.get('post_data'):
                # Truncate to show signsafe
                pd = c['post_data']
                if 'signsafe' in pd:
                    idx = pd.index('signsafe')
                    print(f"  Body (around signsafe): ...{pd[max(0,idx-50):idx+80]}...")
        
        # Try the mnzy.gaokao.cn page which has the volunteer system
        print("\n[6] Trying mnzy.gaokao.cn for pagination...")
        await page.goto("https://mnzy.gaokao.cn/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # Look for plan search
        search_input = await page.query_selector('input[placeholder*="搜索"], input[type="text"]')
        if search_input:
            print("  Found search input")
        
        await browser.close()

asyncio.run(main())
