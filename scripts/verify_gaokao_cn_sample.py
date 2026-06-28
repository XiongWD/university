"""
抽样核验（design §2.2：源追溯 → verified）。

对 gaokao.cn 历史类数据集做 Playwright + cookie 重取 API 复核。
匹配通过后将对应 school_id + special_group（专业组）标记为 verified。

用法：
    python scripts/verify_gaokao_cn_sample.py
        --cookies C:/Users/Administrator/Downloads/cookies-2026-06-26.json
        [--sample-size 50]
        [--verified-out data/seed/henan/verified_groups.txt]

输出：
    - 控制台：每匹配行 + summary
    - verified_groups.txt：通过核验的 (school_id, special_group) 列表
    - 可选：将 verified 写入 YAML 标注
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    raise SystemExit("pip install playwright")


COOKIE_FILE = "C:/Users/Administrator/Downloads/cookies-2026-06-26.json"
ENRICHED_PLANS = "data/raw/henan_2026/gaokao_cn_enriched_plans.json"

_CHROME_CANDIDATES = [
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
]


def convert_cookies(raw_cookies):
    result = []
    for c in raw_cookies:
        domain = c["domain"].lstrip(".")
        if not domain or not c.get("name"):
            continue
        entry = {
            "name": c["name"], "value": c.get("value", ""),
            "domain": domain, "path": c.get("path", "/"),
            "secure": c.get("secure", False), "httpOnly": c.get("httpOnly", False),
        }
        if c.get("sameSite") in ("Lax", "Strict", "None"):
            entry["sameSite"] = c["sameSite"]
        if c.get("expirationDate"):
            entry["expires"] = int(c["expirationDate"])
        result.append(entry)
    return result


def resolve_browser_executable(explicit_path: str | None = None) -> str | None:
    if explicit_path:
        return explicit_path if Path(explicit_path).exists() else None
    for candidate in _CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    env_candidate = os.environ.get("PLAYWRIGHT_CHROME_EXECUTABLE")
    if env_candidate and Path(env_candidate).exists():
        return env_candidate
    return None


async def verify_sample(cookie_path: str, sample: list[dict], executable_path: str | None = None) -> dict:
    """
    对 sample（每项含 school_id, special_group）做 API 重取核验。
    
    返回 { school_group_key: { "matched": bool, "api_data": dict, "fields_checked": [...] } }
    """
    raw_cookies = json.loads(Path(cookie_path).read_text(encoding="utf-8"))
    cookies = convert_cookies(raw_cookies)

    results = {}

    async with async_playwright() as pw:
        launch_kwargs = {"headless": True}
        browser_executable = resolve_browser_executable(executable_path)
        if browser_executable:
            launch_kwargs["executable_path"] = browser_executable
            print(f"  [browser] Using system browser: {browser_executable}")
        browser = await pw.chromium.launch(**launch_kwargs)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}, locale="zh-CN",
        )
        for c in cookies:
            try:
                await ctx.add_cookies([c])
            except Exception:
                pass

        page = await ctx.new_page()
        print("  [auth] Loading gaokao.cn home page...")
        await page.goto("https://www.gaokao.cn/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Group sample by school_id for batch per-school verification
        by_school = defaultdict(set)
        for item in sample:
            by_school[item["school_id"]].add(item["special_group"])

        total = len(sample)
        done = 0

        for school_id, special_groups in by_school.items():
            print(f"  [fetch] school_id={school_id}, groups={len(special_groups)}...")
            
            params = {
                "autosign": "", "like_spname": "", "local_batch_id": "14",
                "local_province_id": "41", "local_type_id": "2074",
                "page": 1, "platform": "2", "school_id": school_id,
                "sg_xuanke": "", "size": 100, "special_group": "",
                "uri": "v1/school/special_plan", "year": "2026",
            }

            api_result = await page.evaluate("""
                async (params) => {
                    try {
                        const resp = await fetch('https://api-gaokao.zjzw.cn/apidata/web', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Origin': 'https://www.gaokao.cn',
                                'Referer': 'https://www.gaokao.cn/',
                            },
                            body: JSON.stringify(params)
                        });
                        const data = await resp.json();
                        return JSON.stringify(data);
                    } catch(e) {
                        return JSON.stringify({error: e.message});
                    }
                }
            """, params)

            try:
                data = json.loads(api_result) if isinstance(api_result, str) else api_result
            except json.JSONDecodeError:
                print(f"    [FAIL] JSON parse error")
                for sg in special_groups:
                    key = f"{school_id}:{sg}"
                    results[key] = {"matched": False, "api_data": None, "fields_checked": []}
                continue

            if not data or str(data.get("code")) != "0":
                print(f"    [FAIL] API error: {data.get('message', 'unknown')}")
                for sg in special_groups:
                    key = f"{school_id}:{sg}"
                    results[key] = {"matched": False, "api_data": None, "fields_checked": []}
                continue

            items = data.get("data", {}).get("item", [])

            # Index API items by special_group
            api_by_group = defaultdict(list)
            for item in items:
                sg = str(item.get("special_group", ""))
                api_by_group[sg].append(item)

            for sg in special_groups:
                key = f"{school_id}:{sg}"
                api_items = api_by_group.get(sg, [])

                # Find matching sample row
                sample_rows = [s for s in sample if str(s["school_id"]) == school_id and str(s["special_group"]) == sg]
                
                if not api_items:
                    results[key] = {"matched": False, "api_data": None, "fields_checked": [], "reason": "API returned no items for this group"}
                    print(f"    {key}: FAIL API returned 0 items")
                    done += 1
                    continue

                # Verify each plan in the sample matches API
                all_ok = True
                checked = []
                for sr in sample_rows:
                    api_match = None
                    for ai in api_items:
                        if str(ai.get("school_special_id", "")) == str(sr.get("school_special_id", "")):
                            api_match = ai
                            break
                    
                    if api_match:
                        # Check key fields
                        fields_ok = True
                        field_checks = {}
                        
                        # Compare num (plan count)
                        num_match = str(api_match.get("num", "")).strip() == str(sr.get("num", "")).strip()
                        field_checks["num"] = num_match
                        
                        # Compare tuition
                        t_match = str(api_match.get("tuition", "")).strip() == str(sr.get("tuition", "")).strip()
                        field_checks["tuition"] = t_match
                        
                        # Compare sp_name (major name)
                        name_match = api_match.get("sp_name", "").strip() == sr.get("sp_name", "").strip()
                        field_checks["sp_name"] = name_match
                        
                        if not all(field_checks.values()):
                            all_ok = False
                        
                        checked.append({
                            "school_special_id": str(api_match.get("school_special_id", "")),
                            "sp_name_match": name_match,
                            "num_match": num_match,
                            "tuition_match": t_match,
                        })
                    else:
                        all_ok = False
                        checked.append({
                            "school_special_id": str(sr.get("school_special_id", "")),
                            "sp_name_match": False,
                            "num_match": False,
                            "tuition_match": False,
                        })

                results[key] = {
                    "matched": all_ok and len(checked) > 0,
                    "api_items_count": len(api_items),
                    "sample_items_count": len(sample_rows),
                    "fields_checked": checked,
                }
                
                if all_ok:
                    print(f"    {key}: OK {len(checked)}/{len(sample_rows)} plans matched")
                else:
                    print(
                        f"    {key}: MISMATCH "
                        f"{len([c for c in checked if not (c.get('sp_name_match') and c.get('num_match') and c.get('tuition_match'))])}"
                    )
                
                done += 1

            await asyncio.sleep(0.3)  # rate limit

        await browser.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="Verify gaokao.cn Henan 2026 plans via API")
    parser.add_argument("--cookies", default=COOKIE_FILE)
    parser.add_argument("--sample-size", type=int, default=30, help="Number of groups to verify")
    parser.add_argument("--verified-out", default="data/seed/henan/verified_groups.txt")
    parser.add_argument("--plans", default=ENRICHED_PLANS)
    parser.add_argument("--executable-path", default=None, help="Optional system Chrome/Edge executable path")
    args = parser.parse_args()

    # Load enriched plans
    plans = json.loads(Path(args.plans).read_text(encoding="utf-8"))
    print(f"Loaded {len(plans)} enriched plans")

    # Build unique (school_id, special_group) pairs, sample from them
    group_keys = {}
    for p in plans:
        key = (str(p.get("school_code", "")), str(p.get("major_group_code", "")))
        if key not in group_keys:
            group_keys[key] = []
        group_keys[key].append({
            "school_id": key[0],
            "special_group": key[1],
            "school_special_id": str(p.get("major_code", "")),
            "num": str(p.get("plan_count", "")),
            "tuition": str(p.get("tuition", "")),
            "sp_name": str(p.get("major_name", "")),
        })

    all_groups = list(group_keys.keys())
    print(f"Unique groups: {len(all_groups)}")

    # Sample: first N groups + some from middle
    sample_size = min(args.sample_size, len(all_groups))
    # Sample: offset to maximize unverified group coverage
    offset = 800  # skip past most verified groups
    sample_indices = list(range(offset, min(offset + 10, len(all_groups))))
    if sample_size > 10:
        mid1 = len(all_groups) // 4
        mid2 = len(all_groups) // 2
        mid3 = len(all_groups) * 3 // 4
        chunk = (sample_size - 10) // 3
        sample_indices += list(range(mid1, min(mid1 + chunk, len(all_groups))))
        sample_indices += list(range(mid2, min(mid2 + chunk, len(all_groups))))
        sample_indices += list(range(mid3, min(mid3 + sample_size - 10 - chunk, len(all_groups))))
    sample_indices = sample_indices[:sample_size]
    if sample_size > 10:
        mid = len(all_groups) // 2
        sample_indices += list(range(mid, min(mid + sample_size - 10, len(all_groups))))
    sample_indices = sample_indices[:sample_size]

    sample_items = []
    for idx in sample_indices:
        key = all_groups[idx]
        sample_items.append({
            "school_id": key[0],
            "special_group": key[1],
            "school_special_id": group_keys[key][0]["school_special_id"],
            "num": group_keys[key][0]["num"],
            "tuition": group_keys[key][0]["tuition"],
            "sp_name": group_keys[key][0]["sp_name"],
        })

    print(f"\nSample: {len(sample_items)} groups from {len(set(i['school_id'] for i in sample_items))} schools")

    # Run verification
    print("\nVerifying via Playwright + API...")
    results = asyncio.run(verify_sample(args.cookies, sample_items, args.executable_path))

    # Summary
    matched = sum(1 for r in results.values() if r.get("matched"))
    failed = sum(1 for r in results.values() if not r.get("matched"))
    print(f"\n=== Verification Summary ===")
    print(f"  Total groups checked: {len(results)}")
    print(f"  Matched: {matched}")
    print(f"  Failed/Mismatched: {failed}")
    print(f"  Match rate: {matched/len(results)*100:.1f}%" if results else "  N/A")

    # Save verified groups
    verified_groups = {k for k, v in results.items() if v.get("matched")}
    if verified_groups:
        out_path = Path(args.verified_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(sorted(verified_groups)), encoding="utf-8")
        print(f"\n  Verified groups saved -> {out_path}")

    # Detailed results
    print("\n=== Detailed Results ===")
    for key, result in sorted(results.items()):
        status = "OK" if result.get("matched") else "FAIL"
        api_count = result.get("api_items_count", 0)
        sample_count = result.get("sample_items_count", 0)
        reason = result.get("reason", "")
        print(f"  {status} {key}: api={api_count} items, sample={sample_count} items" + (f" ({reason})" if reason else ""))


if __name__ == "__main__":
    main()
