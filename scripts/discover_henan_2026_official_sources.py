"""Discover public official 2026 Henan admission catalog sources.

This script only visits public official pages. It does not bypass login,
captcha, rate limits, paywalls, or other access controls.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


DEFAULT_SEEDS = [
    "https://www.haeea.cn/",
    "https://news.haeea.cn/",
    "https://gaokao.chsi.com.cn/",
]

OFFICIAL_DOMAINS = {
    "haeea.cn",
    "www.haeea.cn",
    "news.haeea.cn",
    "gaokao.chsi.com.cn",
}

KEYWORDS = [
    "2026",
    "河南",
    "招生专业目录",
    "招生计划",
    "院校专业组",
    "普通本科批",
    "志愿填报",
    "招生章程",
]

CATALOG_KEYWORDS = ["招生专业目录", "招生计划", "院校专业组", "普通本科批"]
CHARTER_KEYWORDS = ["招生章程"]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = dict(attrs)
        self._current_href = attrs_dict.get("href")
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href:
            text = " ".join(x for x in self._current_text if x)
            self.links.append((self._current_href, text))
            self._current_href = None
            self._current_text = []


@dataclass
class Source:
    url: str
    source_domain: str
    source_type: str
    title: str
    discovered_at: str
    download_status: str = "pending"
    parser_status: str = "pending"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def official_domain(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in OFFICIAL_DOMAINS or any(host.endswith("." + d) for d in OFFICIAL_DOMAINS)


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    path = re.sub(r";jsessionid=[A-Za-z0-9]+", "", parsed.path, flags=re.I)
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", parsed.query, ""))


def fetch_text(url: str, timeout: int) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 HenanZhiyuantuiOfficialSourceDiscovery/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        raw = response.read(2_000_000)
    if "charset=" in content_type:
        encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
    else:
        encoding = "utf-8"
    try:
        return raw.decode(encoding, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def extract_links(base_url: str, html: str) -> Iterable[tuple[str, str]]:
    parser = LinkParser()
    parser.feed(html)
    for href, text in parser.links:
        if not href:
            continue
        url = canonical_url(urljoin(base_url, href))
        if url.startswith(("http://", "https://")) and official_domain(url):
            yield url, text


def classify_source(url: str, title: str) -> str:
    haystack = f"{url} {title}"
    if any(k in haystack for k in CATALOG_KEYWORDS):
        return "exam_authority_catalog"
    if any(k in haystack for k in CHARTER_KEYWORDS):
        return "university_charter"
    if "chsi.com.cn" in urlparse(url).netloc.lower():
        return "chsi_plan"
    if re.search(r"\.(pdf|xls|xlsx|doc|docx)(?:$|\?)", url, flags=re.I):
        return "official_attachment"
    return "official_page"


def is_interesting(url: str, title: str) -> bool:
    haystack = f"{url} {title}"
    if re.search(r"\.(pdf|xls|xlsx|doc|docx)(?:$|\?)", url, flags=re.I):
        return any(k in haystack for k in KEYWORDS) or "2026" in haystack
    return any(k in haystack for k in KEYWORDS)


def discover(seeds: list[str], max_pages: int, depth: int, timeout: int) -> list[Source]:
    queue: deque[tuple[str, int, str]] = deque((seed, 0, "") for seed in seeds)
    visited: set[str] = set()
    found: dict[str, Source] = {}
    stamp = now_iso()

    while queue and len(visited) < max_pages:
        url, level, title_hint = queue.popleft()
        url = canonical_url(url)
        if url in visited or not official_domain(url):
            continue
        visited.add(url)
        try:
            html = fetch_text(url, timeout)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if is_interesting(url, title_hint):
                found[url] = Source(
                    url=url,
                    source_domain=urlparse(url).netloc,
                    source_type=classify_source(url, title_hint),
                    title=title_hint,
                    discovered_at=stamp,
                    download_status=f"discover_error:{type(exc).__name__}",
                )
            continue

        page_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:4000]
        if is_interesting(url, title_hint + " " + page_text):
            found[url] = Source(
                url=url,
                source_domain=urlparse(url).netloc,
                source_type=classify_source(url, title_hint + " " + page_text),
                title=title_hint[:120],
                discovered_at=stamp,
            )

        if level >= depth:
            continue
        for child_url, text in extract_links(url, html):
            if child_url not in visited:
                queue.append((child_url, level + 1, text))
            if is_interesting(child_url, text):
                found.setdefault(
                    child_url,
                    Source(
                        url=child_url,
                        source_domain=urlparse(child_url).netloc,
                        source_type=classify_source(child_url, text),
                        title=text[:120],
                        discovered_at=stamp,
                    ),
                )

    return sorted(found.values(), key=lambda x: (x.source_domain, x.source_type, x.url))


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover official Henan 2026 admission sources")
    parser.add_argument("--out", default="data/raw/henan_2026/official_sources.json")
    parser.add_argument("--seed", action="append", default=[])
    parser.add_argument("--max-pages", type=int, default=80)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args()

    seeds = args.seed or DEFAULT_SEEDS
    sources = discover(seeds, args.max_pages, args.depth, args.timeout)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([asdict(source) for source in sources], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"discovered {len(sources)} official candidate sources -> {out}")
    return 0 if sources else 2


if __name__ == "__main__":
    sys.exit(main())
