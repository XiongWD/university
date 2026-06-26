import sys, re, urllib.request, json

def find_urls_in_js(url):
    """Fetch a JS file and find API URLs"""
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        # Try to decode
        for enc in ['utf-8', 'gbk', 'latin-1']:
            try:
                text = raw.decode(enc)
                break
            except:
                continue
        else:
            text = raw.decode('utf-8', errors='replace')
        
        urls = set()
        # Find string patterns that look like API endpoints
        for m in re.finditer(r'["\'](https?://[^"\']+)["\']', text):
            url_str = m.group(1)
            if any(k in url_str for k in ['api', 'plan', 'school', 'gk/', 'data', 'volunteer', 'zsjh', 'zhaosheng']):
                urls.add(url_str)
        
        # Also find URL-like patterns without quotes
        for m in re.finditer(r'["\'](/[a-z]+/[a-z]+/[a-z]+(?:/[a-z]+)*)["\']', text):
            path = m.group(1)
            if any(k in path for k in ['api', 'plan', 'school', 'gk/', 'zsjh']):
                urls.add('https://www.gaokao.cn' + path)
        
        return urls
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return set()

# Try to find the main chunks and analyze them
base_url = "https://www.gaokao.cn/static/js/"
import glob

# Search for API URLs in a few key chunks
chunks_to_check = [
    "2026_06_26_01_07.59e7ed7fc61ad6edf4ab.main~e9c242a2.chunk.js",
    "2026_06_26_01_07.4937d5eeba4388a201c2.main~0520be64.chunk.js",
    "2026_06_26_01_07.7fb14f64a648caf5f33e.main~139f7333.chunk.js",
    "2026_06_26_01_07.2d4b27a157e491e1121a.main~886f0b5c.chunk.js",
    "2026_06_26_01_07.fe7b5d0d731b50cc2b82.main~748942c6.chunk.js",
]

all_urls = set()
for chunk in chunks_to_check:
    url = base_url + chunk
    print(f"Checking {chunk[:40]}...")
    urls = find_urls_in_js(url)
    all_urls.update(urls)

print("\n=== Found API URLs ===")
for u in sorted(all_urls):
    print(u)
