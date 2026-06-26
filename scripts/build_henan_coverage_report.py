"""生成河南志愿推真实覆盖报告（design D1、Task 1）。

读取 data/seed 实际计数，输出 data/seed/henan/data_coverage_report.json。
支持 --fail-on-not-ready：数据未就绪时退出码非 0（用于 CI 门禁）。
"""
import argparse
import json
import sys
from pathlib import Path

from app.loader.henan_coverage_report import (
    assert_henan_recommendation_ready,
    build_actual_henan_coverage,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成河南志愿推真实覆盖报告")
    parser.add_argument("--fail-on-not-ready", action="store_true", help="数据未就绪时退出码 1")
    args = parser.parse_args()

    report = build_actual_henan_coverage(Path("data/seed"))
    out = Path("data/seed/henan/data_coverage_report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.fail_on_not_ready:
        try:
            assert_henan_recommendation_ready(report)
        except ValueError as exc:
            print(f"[门禁] {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
