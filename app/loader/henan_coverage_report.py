"""河南志愿推数据覆盖报告与上线门禁（design §2.3）。

按数据版本分层汇总各数据集记录数，并校验上线门禁：
阻断性关键数据（2026 专业组/招生计划/历史录取等）缺失时禁止上线推荐。
"""
from __future__ import annotations

from app.models.henan_source_registry import HenanDataSource

# 覆盖报告的分组顺序
_REPORT_GROUPS = ["historical", "latest_2026", "historical_and_latest", "current_signal"]


def build_henan_coverage_report(
    registry: list[HenanDataSource],
    records: dict[str, int],
) -> dict:
    """按 year_type 分组汇总各数据集记录数，并标记阻断性缺失与告警。"""
    report: dict = {group: {} for group in _REPORT_GROUPS}
    report["blocking_missing"] = []
    report["warnings"] = []

    for source in registry:
        count = records.get(source.dataset_key, 0)
        report.setdefault(source.year_type, {})[source.dataset_key] = count
        if count <= 0 and source.blocks_recommendation_when_missing:
            report["blocking_missing"].append(source.dataset_key)
        elif count <= 0:
            report["warnings"].append(source.dataset_key)
    return report


def assert_henan_launch_gate(report: dict) -> None:
    """上线门禁：阻断性关键数据缺失时抛错，禁止展示推荐。"""
    blocking = report.get("blocking_missing", [])
    if blocking:
        raise ValueError(f"河南志愿推关键数据缺失: {', '.join(blocking)}")
