"""Download discovered public official Henan 2026 admission sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_filename(url: str, index: int, content_type: str = "") -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or f"source_{index:04d}.html"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    if "." not in name:
        if "pdf" in content_type:
            name += ".pdf"
        elif "excel" in content_type or "spreadsheet" in content_type:
            name += ".xlsx"
        else:
            name += ".html"
    return f"{index:04d}_{name}"


def download(url: str, timeout: int) -> tuple[bytes, str]:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 HenanZhiyuantuiOfficialDownloader/1.0",
            "Accept": "text/html,application/pdf,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return response.read(), response.headers.get("content-type", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download official Henan 2026 source files")
    parser.add_argument("--sources", default="data/raw/henan_2026/official_sources.json")
    parser.add_argument("--out-dir", default="data/raw/henan_2026/sources")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    args = parser.parse_args()

    sources_path = Path(args.sources)
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    for index, item in enumerate(sources, start=1):
        if args.limit and downloaded >= args.limit:
            break
        url = item["url"]
        try:
            body, content_type = download(url, args.timeout)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            item["download_status"] = f"error:{type(exc).__name__}"
            item["download_error"] = str(exc)[:300]
            continue

        digest = hashlib.sha256(body).hexdigest()
        filename = safe_filename(url, index, content_type)
        target = out_dir / filename
        target.write_bytes(body)

        item["download_status"] = "downloaded"
        item["downloaded_at"] = now_iso()
        item["content_type"] = content_type
        item["sha256"] = digest
        item["local_path"] = target.as_posix()
        item["size_bytes"] = len(body)
        downloaded += 1

    sources_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"downloaded {downloaded} files -> {out_dir}")
    return 0 if downloaded else 2


if __name__ == "__main__":
    sys.exit(main())
