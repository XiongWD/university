"""
Enrich Henan 2026 gaokao.cn history-track plans with source traceability,
school attributes, and eligibility parsing.

Usage:
    python scripts/enrich_gaokao_cn_henan_2026.py
        [--plans data/raw/henan_2026/henan_2026_all_plans_merged.json]
        [--out data/raw/henan_2026/gaokao_cn_enriched_plans.json]
        [--normalized-out data/raw/henan_2026/normalized_catalog_from_gaokao_cn_history_enriched.csv]
        [--cookies ...]   # optional, for sample verification only

Pipeline:
    1. Load merged plans JSON
    2. Fetch school attributes from static-data.gaokao.cn (no auth needed)
    3. Fetch detailed school info for tags/official-codes (batch)
    4. Parse remarks for eligibility restrictions
    5. Construct source traceability fields
    6. Output enriched JSON and normalized CSV

Notes:
    The gaokao.cn static-data API is publicly accessible (no cookie needed).
    Only the sample verification step requires an authenticated Playwright session.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Fields ────────────────────────────────────────────────────────────────

OUTPUT_FIELDS = [
    "source_province",
    "school_origin_province",
    "school_code",
    "official_school_code",
    "school_name",
    "year",
    "batch",
    "track",
    "major_group_code",
    "major_group_name",
    "major_code",
    "major_name",
    "plan_count",
    "primary_subject_requirement",
    "elective_subject_requirement",
    "accepted_exam_languages",
    "public_foreign_languages",
    "single_subject_score_requirements",
    "physical_restrictions",
    "special_qualification_type",
    "tuition",
    "accommodation",
    "campus",
    "remarks",
    "source_name",
    "source_url",
    "source_api_endpoint",
    "source_params",
    "source_page",
    "source_response_checksum",
    "as_of",
    "city",
    "ownership",
    "school_level",
    "school_category",
    "school_tags",
    "review_status",
]

# ── Helpers ───────────────────────────────────────────────────────────────

GAOKAO_STATIC = "https://static-data.gaokao.cn/www/2.0"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EnrichHenan2026/1.0"


def fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_elective_requirement(value: str) -> str:
    if "再选不限" in value:
        return "{}"
    require: list[str] = []
    for subject in ("思想政治", "地理", "生物", "化学"):
        if subject in value:
            require.append(subject)
    if not require:
        return "{}"
    quoted = ", ".join(f'"{subject}"' for subject in require)
    return f'{{"require": [{quoted}], "any_of": []}}'


def primary_subject(value: str) -> str:
    if "首选历史" in value:
        return "历史"
    if "首选物理" in value:
        return "物理"
    return ""


def track(value: str) -> str:
    if "首选历史" in value:
        return "历史类"
    if "首选物理" in value:
        return "物理类"
    return ""


def clean_int(value: str) -> str:
    value = (value or "").strip()
    return value if re.fullmatch(r"\d+", value) else ""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def checksum(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


# ── Eligibility Parsing ──────────────────────────────────────────────────


def parse_remarks(remark: str) -> dict:
    """Parse remark text for eligibility restriction hints."""
    result = {
        "accepted_exam_languages": "",
        "public_foreign_languages": "",
        "single_subject_score_requirements": "",
        "physical_restrictions": "",
        "special_qualification_type": "",
        "campus": "",
    }
    if not remark:
        return result

    # Language
    if re.search(r"只招英语语种考生|只招英语|限英语|英语语种", remark):
        result["accepted_exam_languages"] = "英语"
    elif re.search(r"招日语考生|可招日语|日语考生", remark):
        result["accepted_exam_languages"] = "日语"

    # Physical restrictions
    phys = []
    if re.search(r"不招收单色识别不全|色盲|色弱|不能识别颜色", remark):
        phys.append("辨色力异常")
    if re.search(r"身高", remark):
        m = re.search(r"身高[^\d]*(\d+[\.\d]*)[^\d]*(\d*[\.\d]*)", remark)
        phys.append(f"身高要求" + (f"({m.group(1)}-{m.group(2)})" if m and m.group(2) else ""))
    if re.search(r"视力[^\d]*(\d+\.?\d*)", remark):
        phys.append("视力要求")
    if re.search(r"口吃|听力", remark):
        phys.append("听说要求")
    if phys:
        result["physical_restrictions"] = "；".join(phys)

    # Special qualification
    for pat, qtype in [
        (r"高校专项|高校专项计划", "高校专项"),
        (r"地方专项|地方专项计划", "地方专项"),
        (r"国家专项|国家专项计划", "国家专项"),
        (r"公费师范", "公费师范"),
        (r"定向医学生|免费医学", "定向医学生"),
        (r"中外合作|中外合作办学", "中外合作"),
        (r"较高收费|高收费", "高收费"),
    ]:
        if re.search(pat, remark):
            result["special_qualification_type"] = qtype
            break

    # Campus
    m = re.search(r"办学地点[：:]([^；。，]+)", remark)
    if m:
        result["campus"] = m.group(1).strip()

    return result


# ── School Attributes ────────────────────────────────────────────────────


def fetch_school_attributes() -> dict[str, dict]:
    """Fetch school attributes from public gaokao.cn static-data API."""
    print("  Fetching school list_v2 (all schools)...")
    data = fetch_json(f"{GAOKAO_STATIC}/school/list_v2.json?a=www.gaokao.cn")
    school_dict = data.get("data", {})
    print(f"  Loaded {len(school_dict)} schools from list_v2")

    # Normalize attributes
    result: dict[str, dict] = {}
    for sid, info in school_dict.items():
        result[str(sid)] = {
            "school_name": info.get("name", ""),
            "province": info.get("p", ""),
            "city": info.get("c", ""),
            "nature": info.get("nature", ""),
            "level": info.get("level", ""),
        "is_985": info.get("f985") == "1",
        "is_211": info.get("f211") == "1",
        "is_dual_class": info.get("dual_class") == "1",
        }
    return result


def fetch_school_detail(school_id: str) -> dict | None:
    """Fetch detailed info for a single school from public API."""
    try:
        data = fetch_json(f"{GAOKAO_STATIC}/school/{school_id}/info.json?a=www.gaokao.cn")
        d = data.get("data")
        if isinstance(d, dict):
            return {
                "official_code": d.get("zs_code", ""),
                "province_name": d.get("province_name", ""),
                "city_name": d.get("city_name", ""),
                "town_name": d.get("town_name", ""),
                "level_name": d.get("level_name", ""),
                "school_nature_name": d.get("school_nature_name", ""),
                "type_name": d.get("type_name", ""),
                "dual_class_name": d.get("dual_class_name", ""),
                "f985": d.get("f985"),
                "f211": d.get("f211"),
                "school_site": d.get("school_site", ""),
                "admission_site": d.get("site", ""),
                "phone": d.get("phone", ""),
                "email": d.get("email", ""),
            }
    except Exception:
        pass
    return None


def build_school_attrs_map(
    school_ids: set[str],
    list_v2_attrs: dict[str, dict],
) -> dict[str, dict]:
    """Build a complete school attributes map from list_v2."""
    result: dict[str, dict] = {}
    for sid in school_ids:
        info = list_v2_attrs.get(sid, {})
        result[sid] = {
            "province": info.get("province", ""),
            "city": info.get("city", ""),
            "ownership": info.get("nature", ""),
            "school_level": info.get("level", ""),
            "tags": [],
        }
        # Build tags
        tags = []
        if info.get("is_985"):
            tags.append("985")
        if info.get("is_211"):
            tags.append("211")
        if info.get("is_dual_class"):
            tags.append("双一流")
        result[sid]["tags"] = tags
    return result


# ── Verification (optional, needs Playwright) ────────────────────────────


def convert_cookies(raw_cookies: list[dict]) -> list[dict]:
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


async def verify_sample_async(
    cookie_path: str, sample_rows: list[dict], cache_dir: str
) -> dict:
    """Re-fetch plan data for a sample via Playwright."""
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    raw_cookies = json.loads(Path(cookie_path).read_text(encoding="utf-8"))
    cookies = convert_cookies(raw_cookies)

    from playwright.async_api import async_playwright

    result = {"matched": 0, "mismatched": 0, "failed": 0, "details": []}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
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
        await page.goto("https://www.gaokao.cn/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        for row in sample_rows:
            school_id = row.get("school_code", "")
            if not school_id:
                result["failed"] += 1
                continue

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

            try:
                data = json.loads(api_result) if isinstance(api_result, str) else api_result
            except json.JSONDecodeError:
                result["failed"] += 1
                continue

            if not data or str(data.get("code")) != "0":
                result["failed"] += 1
                continue

            items = data.get("data", {}).get("item", [])
            found = False
            for item in items:
                if (str(item.get("school_special_id", "")) == row.get("major_code", "") and
                    str(item.get("special_group", "")) == row.get("major_group_code", "")):
                    found = True
                    break

            if found:
                result["matched"] += 1
            else:
                result["mismatched"] += 1

            result["details"].append({
                "school_id": school_id,
                "major_code": row.get("major_code"),
                "group_code": row.get("major_group_code"),
                "matched": found,
            })

        await browser.close()

    return result


def verify_sample(cookie_path: str, sample_rows: list[dict], cache_dir: str) -> dict:
    """Wrapper to run async verification."""
    return asyncio.run(verify_sample_async(cookie_path, sample_rows, cache_dir))


# ── Main Pipeline ────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich Henan 2026 gaokao.cn history-track plans"
    )
    parser.add_argument(
        "--plans",
        default="data/raw/henan_2026/henan_2026_all_plans_merged.json",
    )
    parser.add_argument(
        "--out",
        default="data/raw/henan_2026/gaokao_cn_enriched_plans.json",
    )
    parser.add_argument(
        "--normalized-out",
        default="data/raw/henan_2026/normalized_catalog_from_gaokao_cn_history_enriched.csv",
    )
    parser.add_argument(
        "--unresolved-out",
        default="data/raw/henan_2026/gaokao_cn_unresolved_fields.csv",
    )
    parser.add_argument(
        "--report-out",
        default="data/raw/henan_2026/gaokao_cn_enrichment_report.json",
    )
    parser.add_argument(
        "--school-attrs-out",
        default="data/raw/henan_2026/school_attributes_from_api.json",
    )
    parser.add_argument(
        "--cookies",
        default="",
        help="Path to cookie JSON for sample verification (optional)",
    )
    parser.add_argument(
        "--verify-sample",
        type=int,
        default=0,
        help="Number of sample rows to verify via Playwright (0 = skip)",
    )
    parser.add_argument(
        "--cache-dir",
        default="data/raw/henan_2026/gaokao_cn_cache",
    )
    args = parser.parse_args()

    as_of = now_iso()
    api_endpoint = "https://api-gaokao.zjzw.cn/apidata/web"
    verify_result = {"matched": 0, "mismatched": 0, "failed": 0, "details": []}

    # ── Step 1: Load merged plans ──
    print("=" * 60)
    print("Step 1: Loading merged plans")
    print("=" * 60)
    plans = json.loads(Path(args.plans).read_text(encoding="utf-8"))
    print(f"  Loaded {len(plans)} plans")

    unique_schools = {}
    for p in plans:
        sid = str(p.get("school_id", ""))
        if sid and sid not in unique_schools:
            unique_schools[sid] = p.get("school_name", "")
    print(f"  Unique schools: {len(unique_schools)}")

    # ── Step 2: Fetch school attributes ──
    print("\n" + "=" * 60)
    print("Step 2: Fetching school attributes (public API)")
    print("=" * 60)
    list_v2_attrs = fetch_school_attributes()
    school_attrs = build_school_attrs_map(
        set(unique_schools.keys()), list_v2_attrs
    )

    # Save school attributes
    attrs_path = Path(args.school_attrs_out)
    attrs_path.parent.mkdir(parents=True, exist_ok=True)
    attrs_path.write_text(
        json.dumps(school_attrs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Saved school attributes -> {attrs_path}")

    # Coverage
    covered = sum(1 for sid in unique_schools if sid in school_attrs and school_attrs[sid].get("province"))
    print(f"  Province coverage: {covered}/{len(unique_schools)}")

    # ── Step 3: Sample verification (optional) ──
    if args.verify_sample > 0 and args.cookies:
        print("\n" + "=" * 60)
        print("Step 3: Sample verification via Playwright")
        print("=" * 60)

        school_ids = list(unique_schools.keys())
        sample_ids = school_ids[:5] + school_ids[len(school_ids)//2:len(school_ids)//2+5]

        sample_rows = []
        for p in plans:
            if str(p.get("school_id", "")) in sample_ids and len(sample_rows) < args.verify_sample:
                sample_rows.append({
                    "school_code": str(p.get("school_id", "")),
                    "major_code": str(p.get("school_special_id", "")),
                    "major_group_code": str(p.get("special_group", "")),
                })

        verify_result = verify_sample(args.cookies, sample_rows, args.cache_dir)
        print(f"  Matched: {verify_result['matched']}, Mismatched: {verify_result['mismatched']}, Failed: {verify_result['failed']}")
    else:
        print("\n  [SKIP] Sample verification (no cookie or verify_sample=0)")

    # ── Step 4: Parse remarks and build enriched records ──
    print("\n" + "=" * 60)
    print("Step 4: Parsing remarks and building enriched records")
    print("=" * 60)

    enriched = []
    stats = Counter()

    for p in plans:
        school_id = str(p.get("school_id", "")).strip()
        group_code = str(p.get("special_group", ""))
        major_code = str(p.get("school_special_id", ""))
        plan_count = clean_int(p.get("num", ""))

        if not school_id or not group_code or not major_code or not plan_count:
            continue

        sg_info = p.get("sg_info", "")
        remark = p.get("remark", "")

        # Parse remark
        parsed = parse_remarks(remark)
        if remark:
            stats["with_remarks"] += 1
        if parsed["accepted_exam_languages"]:
            stats["lang_restrictions"] += 1
        if parsed["physical_restrictions"]:
            stats["phys_restrictions"] += 1
        if parsed["special_qualification_type"]:
            stats["special_quals"] += 1
        if parsed["campus"]:
            stats["with_campus"] += 1

        # School attributes
        attrs = school_attrs.get(school_id, {})

        # Source params
        source_params = {
            "uri": "v1/school/special_plan",
            "school_id": school_id,
            "local_batch_id": "14",
            "local_province_id": "41",
            "local_type_id": "2074",
            "year": "2026",
        }

        tuition = clean_int(p.get("tuition", ""))
        if not tuition:
            stats["missing_tuition"] += 1

        school_page_url = f"https://www.gaokao.cn/school/{school_id}/sturule"

        enriched.append({
            "source_province": "河南",
            "school_origin_province": attrs.get("province", ""),
            "school_code": school_id,
            "official_school_code": "",  # Would need individual school detail
            "school_name": p.get("school_name", "").strip(),
            "year": "2026",
            "batch": "本科批",
            "track": track(sg_info),
            "major_group_code": group_code,
            "major_group_name": f'{p.get("school_name", "").strip()}-{group_code}',
            "major_code": major_code,
            "major_name": p.get("sp_name", "").strip(),
            "plan_count": plan_count,
            "primary_subject_requirement": primary_subject(sg_info),
            "elective_subject_requirement": parse_elective_requirement(sg_info),
            "accepted_exam_languages": parsed["accepted_exam_languages"],
            "public_foreign_languages": parsed["public_foreign_languages"],
            "single_subject_score_requirements": parsed["single_subject_score_requirements"],
            "physical_restrictions": parsed["physical_restrictions"],
            "special_qualification_type": parsed["special_qualification_type"],
            "tuition": tuition,
            "accommodation": "",
            "campus": parsed["campus"],
            "remarks": remark,
            "source_name": "gaokao.cn 2026 河南历史类招生计划",
            "source_url": school_page_url,
            "source_api_endpoint": api_endpoint,
            "source_params": json.dumps(source_params, ensure_ascii=False),
            "source_page": "",
            "source_response_checksum": checksum(p),
            "as_of": as_of,
            "city": attrs.get("city", ""),
            "ownership": attrs.get("ownership", ""),
            "school_level": attrs.get("school_level", ""),
            "school_category": "",
            "school_tags": "、".join(attrs.get("tags", [])),
            "review_status": "needs_review",
        })

    stats["total"] = len(enriched)

    # ── Step 5: Write outputs ──
    print("\n" + "=" * 60)
    print("Step 5: Writing output files")
    print("=" * 60)

    # Enriched JSON
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Enriched plans JSON -> {out_path}")

    # Normalized CSV
    csv_path = Path(args.normalized_out)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(enriched)
    print(f"  Normalized CSV -> {csv_path}")

    # Unresolved report
    unresolved = [r for r in enriched if not r.get("school_origin_province")]
    unresolved_path = Path(args.unresolved_out)
    with unresolved_path.open("w", encoding="utf-8-sig", newline="") as f:
        if unresolved:
            w = csv.DictWriter(f, fieldnames=list(unresolved[0].keys()))
            w.writeheader()
            w.writerows(unresolved)
    print(f"  Unresolved (no province): {len(unresolved)} -> {unresolved_path}")

    # Report
    report = {
        "pipeline": "enrich_gaokao_cn_henan_2026",
        "as_of": as_of,
        "input_plans": len(plans),
        "enriched_plans": len(enriched),
        "unique_schools": len(unique_schools),
        "province_coverage": f"{covered}/{len(unique_schools)}",
        "stats": dict(stats),
        "verification": verify_result,
    }
    report_path = Path(args.report_out)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Report -> {report_path}")

    # Summary
    print("\n" + "=" * 60)
    print("Enrichment Summary")
    print("=" * 60)
    print(f"  Total enriched plans: {stats['total']}")
    print(f"  With remarks parsed: {stats.get('with_remarks', 0)}")
    print(f"  Language restrictions: {stats.get('lang_restrictions', 0)}")
    print(f"  Physical restrictions: {stats.get('phys_restrictions', 0)}")
    print(f"  Special qualifications: {stats.get('special_quals', 0)}")
    print(f"  Campus info: {stats.get('with_campus', 0)}")
    print(f"  Missing tuition: {stats.get('missing_tuition', 0)}")
    print(f"  Province coverage: {covered}/{len(unique_schools)}")


if __name__ == "__main__":
    main()
