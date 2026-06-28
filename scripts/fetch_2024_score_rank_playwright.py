"""
使用 Playwright 访问 haeea.cn 查找 2024 河南文科一分一段表。

尝试两种方式：
1. 直接导航到省考试院成绩分数段页面
2. 通过 gaokao.cn API 获取
"""
import asyncio, json, re
from pathlib import Path
try:
    from playwright.async_api import async_playwright
except ImportError:
    raise SystemExit("pip install playwright")

COOKIE_FILE = Path("C:/Users/Administrator/Downloads/cookies-2026-06-26.json")

def convert_cookies(raw_cookies):
    result = []
    for c in raw_cookies:
        domain = c["domain"].lstrip(".")
        if not domain or not c.get("name"):
            continue
        entry = {"name": c["name"], "value": c.get("value", ""), "domain": domain,
                 "path": c.get("path", "/"), "secure": c.get("secure", False), "httpOnly": c.get("httpOnly", False)}
        if c.get("sameSite") in ("Lax", "Strict", "None"):
            entry["sameSite"] = c["sameSite"]
        if c.get("expirationDate"):
            entry["expires"] = int(c["expirationDate"])
        result.append(entry)
    return result

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
        except: return {"error": "parse_failed"}
    return result

async def main():
    raw_cookies = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    cookies = convert_cookies(raw_cookies)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}, locale='zh-CN',
        )
        for c in cookies:
            try: await ctx.add_cookies([c])
            except: pass

        page = await ctx.new_page()

        # 方法1: 通过 gaokao.cn API 获取 2024 一分一段表
        print("=== 方法1: gaokao.cn API ===")
        await page.goto("https://www.gaokao.cn/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # 尝试不同的 API URI 来获取一分一段表
        api_patterns = [
            # 分数段统计
            ("v1/score/segment", {"province_id": "41", "year": "2024", "local_type_id": "2074"}),
            ("v1/score/segment", {"province_id": "41", "year": "2024", "local_type_id": "2073"}),
            ("v1/score/segment", {"province_id": "41", "year": "2024"}),
            ("v1/province/segment", {"province_id": "41", "year": "2024", "local_type_id": "2074"}),
            # 分数排名
            ("v1/score/rank", {"province_id": "41", "year": "2024"}),
            ("v1/province/score/rank", {"province_id": "41", "year": "2024"}),
            # 一分一段
            ("v1/province/yiyiduan", {"province_id": "41", "year": "2024"}),
            ("v1/score/yiyiduan", {"province_id": "41", "year": "2024"}),
            # 老高考文科 - 尝试文科 type
            ("v1/score/segment", {"province_id": "41", "year": "2024", "local_type_id": "1"}),
            ("v1/score/segment", {"province_id": "41", "year": "2024", "local_type_id": "2"}),
        ]

        for uri, extra in api_patterns:
            params = {"autosign": "", "platform": "2", "page": 1, "size": 200, "uri": uri, **extra}
            data = await call_api(page, params)
            if data and str(data.get("code")) == "0":
                d = data.get("data")
                if isinstance(d, str):
                    try: d = json.loads(d)
                    except: d = {}
                if isinstance(d, dict):
                    items = d.get("item", [])
                    num = d.get("numFound", 0)
                    if items or num:
                        print(f"  ✅ {uri}: items={len(items) if isinstance(items, list) else '?'}, total={num}")
                        if isinstance(items, list) and items:
                            print(f"     Sample: {json.dumps(items[0], ensure_ascii=False)[:200]}")
                            # If this looks like score-rank data, save it!
                            if isinstance(items[0], dict) and ("score" in items[0] or "分数" in str(items[0])):
                                print(f"     *** POTENTIAL SCORE-RANK DATA FOUND ***")
                    else:
                        print(f"  ⚠️  {uri}: code=0 but no items")
                elif isinstance(d, list) and d:
                    print(f"  ✅ {uri}: list[{len(d)}]")
                    if isinstance(d[0], dict):
                        print(f"     Keys: {list(d[0].keys())[:15]}")
                        print(f"     Sample: {json.dumps(d[0], ensure_ascii=False)[:200]}")
            elif data and str(data.get("code")) != "0" and "未上线" not in str(data.get("message", "")):
                print(f"  ❌ {uri}: code={data.get('code')}, msg={str(data.get('message',''))[:80]}")
            await asyncio.sleep(0.3)

        # 方法2: 尝试 gaokao.cn static-data 寻找 2024 score-rank
        print("\n=== 方法2: 静态数据接口 ===")
        static_urls = [
            "https://static-data.gaokao.cn/www/2.0/province/41/segment/2024.json",
            "https://static-data.gaokao.cn/www/2.0/province/41/score/2024.json",
            "https://static-data.gaokao.cn/www/2.0/province/41/rank/2024.json",
        ]
        for url in static_urls:
            result = await page.evaluate(f"""
                async () => {{
                    try {{
                        const resp = await fetch('{url}?a=www.gaokao.cn');
                        const data = await resp.json();
                        return JSON.stringify(data).substring(0, 1000);
                    }} catch(e) {{
                        return JSON.stringify({{error: e.message}});
                    }}
                }}
            """)
            print(f"  {url.split('/')[-1]}: {result[:200]}")

        # 方法3: 尝试访问 haeea.cn 页面（可能被反爬）
        print("\n=== 方法3: haeea.cn 直连 ===")
        try:
            await page.goto("https://www.haeea.cn/henan/2024/putonggaokao/zhongzhaotougdangxian/", 
                          wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(5000)
            content = await page.content()
            # 查找所有链接
            links = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a').forEach(a => {
                        const href = a.href;
                        const text = a.innerText.trim();
                        if (href && !href.startsWith('javascript')) {
                            links.push({href: href.substring(0, 200), text: text.substring(0, 100)});
                        }
                    });
                    return links;
                }
            """)
            print(f"  Found {len(links)} links")
            for link in links:
                if any(k in link['text'] + link['href'] for k in ['一分一段', '分数段', '累计', '位次', '统考成绩']):
                    print(f"  >>> {link['text']}: {link['href']}")
        except Exception as e:
            print(f"  haeea.cn error: {e}")

        await browser.close()

asyncio.run(main())
