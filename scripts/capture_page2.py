"""
Use Playwright to find which gaokao.cn page loads plan data,
click pagination, and capture the signsafe for page 2.
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

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0', viewport={'width': 1920, 'height': 1080}, locale='zh-CN',
        )
        await ctx.add_cookies(COOKIES)
        page = await ctx.new_page()

        api_calls = []
        async def on_request(request):
            url = request.url
            if 'api-gaokao.zjzw.cn' in url:
                api_calls.append({
                    'url': url,
                    'method': request.method,
                    'post_data': request.post_data[:3000] if request.post_data else None,
                    'timestamp': asyncio.get_event_loop().time(),
                })
        
        page.on('request', on_request)

        # Try various URL patterns that might show the plan data
        urls_to_try = [
            "https://www.gaokao.cn/choose/school/rank?provinceId=41",
            "https://www.gaokao.cn/school/62/specialplan",
            "https://www.gaokao.cn/school/62/plan",
            "https://www.gaokao.cn/school/62/zsjh",
            "https://www.gaokao.cn/school/62/recruit",
            "https://www.gaokao.cn/school/62/province/41",
            "https://www.gaokao.cn/plan/search?schoolId=62&provinceId=41",
        ]
        
        print("[1] Trying various URLs to find plan data page...")
        for url in urls_to_try:
            print(f"  Trying: {url}")
            before = len(api_calls)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                new_calls = len(api_calls) - before
                print(f"    New API calls: {new_calls}")
                if new_calls > 0:
                    for c in api_calls[-new_calls:]:
                        print(f"    > {c['url'][:150]}")
            except Exception as e:
                print(f"    Error: {str(e)[:50]}")
            
            if len(api_calls) > before:
                # Found API calls! Save and break
                break
        
        # If we found zjzw API calls, try to extract the signsafe
        print(f"\n[2] Total zjzw API calls captured: {len(api_calls)}")
        for i, c in enumerate(api_calls):
            pd = c.get('post_data', '') or ''
            print(f"\n  Call {i+1}: {c['url'][:150]}")
            # Extract signsafe from URL
            if 'signsafe=' in c['url']:
                idx = c['url'].index('signsafe=')
                ss = c['url'][idx:idx+50]
                print(f"  signsafe in URL: {ss}")
            # Extract signsafe from POST data
            if 'signsafe' in pd:
                # Find the value
                import re
                m = re.search(r'"signsafe"\s*:\s*"([^"]+)"', pd)
                if m:
                    print(f"  signsafe in body: {m.group(1)}")
                # Find page
                m2 = re.search(r'"page"\s*:\s*(\d+)', pd)
                if m2:
                    print(f"  page: {m2.group(1)}")

        # Save captured calls
        out_file = OUT / "page2_api_capture.json"
        out_file.write_text(json.dumps(api_calls, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\nSaved to {out_file}")

        await browser.close()

asyncio.run(main())
