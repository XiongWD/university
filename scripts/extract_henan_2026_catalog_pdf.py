"""Extract official Henan 2026 catalog sources into normalized_catalog.csv.

The extractor is conservative: rows are emitted only when the source text has
enough fields to support traceability. Unparsed sources are reported instead of
being turned into guessed data.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


FIELDS = [
    "source_province",
    "school_origin_province",
    "school_code",
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
    "tuition",
    "accommodation",
    "remarks",
    "source_name",
    "source_url",
    "source_page",
    "as_of",
    "review_status",
]


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_cell = False
        self.in_row = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self.in_row = True
            self.current_row = []
        elif tag in {"td", "th"} and self.in_row:
            self.in_cell = True
            self.current_cell = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self.in_cell:
            text = " ".join(x for x in self.current_cell if x)
            self.current_row.append(re.sub(r"\s+", " ", text).strip())
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if any(self.current_row):
                self.rows.append(self.current_row)
            self.in_row = False


@dataclass
class ExtractIssue:
    source_url: str
    local_path: str
    reason: str


def read_pdf_text(path: Path) -> tuple[str, str | None]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return "", "missing_pdf_library"

    try:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages), None
    except Exception as exc:  # pragma: no cover - depends on external PDFs
        return "", f"pdf_extract_error:{type(exc).__name__}"


def normalize_track(text: str) -> str:
    if "历史" in text:
        return "历史类"
    if "物理" in text:
        return "物理类"
    return ""


def normalize_subject(text: str, track: str) -> str:
    if "物理" in text:
        return "物理"
    if "历史" in text:
        return "历史"
    if track == "历史类":
        return "历史"
    if track == "物理类":
        return "物理"
    return ""


def row_from_cells(cells: list[str], *, source: dict[str, Any], page: str = "") -> dict[str, str] | None:
    joined = " ".join(cells)
    if not any(key in joined for key in ["本科", "历史", "物理", "专业组", "计划"]):
        return None

    school_code = next((c for c in cells if re.fullmatch(r"\d{4,6}", c)), "")
    plan_count = next((c for c in reversed(cells) if re.fullmatch(r"\d{1,4}", c)), "")
    if not school_code or not plan_count:
        return None

    track = normalize_track(joined)
    school_name = ""
    major_name = ""
    for cell in cells:
        if school_code and cell != school_code and 2 <= len(cell) <= 40 and not re.fullmatch(r"\d+", cell):
            if not school_name and ("大学" in cell or "学院" in cell or "学校" in cell):
                school_name = cell
            elif not major_name and cell != school_name:
                major_name = cell

    if not school_name or not major_name:
        return None

    group_code = next((c for c in cells if re.fullmatch(r"[A-Za-z0-9]{2,6}", c) and c != school_code), "")
    batch = "本科批" if "本科" in joined else ""

    return {
        "source_province": "河南",
        "school_origin_province": "",
        "school_code": school_code,
        "school_name": school_name,
        "year": "2026",
        "batch": batch,
        "track": track,
        "major_group_code": group_code,
        "major_group_name": f"{school_name}{group_code}" if group_code else "",
        "major_code": "",
        "major_name": major_name,
        "plan_count": plan_count,
        "primary_subject_requirement": normalize_subject(joined, track),
        "elective_subject_requirement": "{}",
        "accepted_exam_languages": "",
        "public_foreign_languages": "",
        "tuition": "",
        "accommodation": "",
        "remarks": joined[:300],
        "source_name": source.get("title") or source.get("source_type") or "official_source",
        "source_url": source["url"],
        "source_page": page,
        "as_of": source.get("downloaded_at") or source.get("discovered_at") or "",
        "review_status": "needs_review",
    }


def extract_html(path: Path, source: dict[str, Any]) -> tuple[list[dict[str, str]], list[ExtractIssue]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parser = TableParser()
    parser.feed(text)
    rows = []
    for cells in parser.rows:
        row = row_from_cells(cells, source=source)
        if row:
            rows.append(row)
    issues = [] if rows else [ExtractIssue(source["url"], str(path), "no_parseable_catalog_table")]
    return rows, issues


def extract_pdf(path: Path, source: dict[str, Any]) -> tuple[list[dict[str, str]], list[ExtractIssue]]:
    text, error = read_pdf_text(path)
    if error:
        return [], [ExtractIssue(source["url"], str(path), error)]
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        parts = [x for x in re.split(r"\s{2,}|\t", line.strip()) if x]
        row = row_from_cells(parts, source=source)
        if row:
            rows.append(row)
    issues = [] if rows else [ExtractIssue(source["url"], str(path), "no_parseable_catalog_rows")]
    return rows, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract official Henan 2026 catalog sources")
    parser.add_argument("--sources", default="data/raw/henan_2026/official_sources.json")
    parser.add_argument("--out", default="data/raw/henan_2026/normalized_catalog.csv")
    parser.add_argument("--report", default="data/raw/henan_2026/extraction_report.json")
    args = parser.parse_args()

    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    issues: list[ExtractIssue] = []

    for source in sources:
        local_path = source.get("local_path")
        if not local_path:
            continue
        path = Path(local_path)
        if not path.exists():
            issues.append(ExtractIssue(source["url"], local_path, "missing_local_file"))
            continue
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            found, found_issues = extract_pdf(path, source)
        elif suffix in {".html", ".htm", ".dhtml", ".jsp"}:
            found, found_issues = extract_html(path, source)
        else:
            found, found_issues = [], [ExtractIssue(source["url"], str(path), f"unsupported_file_type:{suffix}")]
        rows.extend(found)
        issues.extend(found_issues)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "row_count": len(rows),
        "issue_count": len(issues),
        "issues": [asdict(issue) for issue in issues],
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if rows else 2


if __name__ == "__main__":
    sys.exit(main())
