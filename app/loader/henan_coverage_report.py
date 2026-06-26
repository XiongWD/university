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


def build_actual_henan_coverage(seed_dir) -> dict:
    """基于实际 seed 计数生成真实覆盖报告（design D1）。

    区分 actual（计数）与 quality（质量指标）。推荐就绪门禁用 quality 判定。
    """
    from app.loader.henan_data_loader import (
        load_henan_admission_history,
        load_henan_enrollment_plans,
        load_henan_program_groups,
        load_henan_universities,
    )

    universities = load_henan_universities(seed_dir)
    groups = load_henan_program_groups(seed_dir)
    plans = load_henan_enrollment_plans(seed_dir)
    history = load_henan_admission_history(seed_dir)

    return {
        "actual": {
            "universities_2026": len(universities),
            "program_groups_2026": len(groups),
            "enrollment_plans_henan_2026": len(plans),
        },
        "quality": {
            "verified_program_groups_2026": sum(1 for x in groups if x.review_status == "verified"),
            "verified_enrollment_plans_2026": sum(1 for x in plans if x.review_status == "verified"),
            "nonzero_enrollment_plans_2026": sum(1 for x in plans if x.plan_count > 0),
            "verified_2025_history": sum(
                1 for x in history if x.year == 2025 and x.review_status == "verified" and (x.min_rank or 0) > 0
            ),
            "verified_2024_history": sum(
                1 for x in history if x.year == 2024 and x.review_status == "verified" and (x.min_rank or 0) > 0
            ),
        },
    }


def assert_henan_recommendation_ready(report: dict) -> None:
    """推荐就绪门禁：4 项质量指标任一为 0 抛 ValueError（design D1）。

    verified 专业组 / verified 计划 / 非零计划 / verified 2025 历史位次 缺一即阻断可信推荐。
    """
    quality = report.get("quality", {})
    required = [
        "verified_program_groups_2026",
        "verified_enrollment_plans_2026",
        "nonzero_enrollment_plans_2026",
        "verified_2025_history",
    ]
    missing = [key for key in required if quality.get(key, 0) <= 0]
    if missing:
        raise ValueError(f"河南志愿推推荐数据未就绪: {', '.join(missing)}")
