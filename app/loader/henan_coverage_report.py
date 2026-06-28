"""河南志愿推数据覆盖报告与上线门禁（design §2.3）。

按数据版本分层汇总各数据集记录数，并校验上线门禁：
阻断性关键数据（2026 专业组/招生计划/历史录取等）缺失时禁止上线推荐。
"""
from __future__ import annotations

from app.loader.henan_scope import (
    filter_henan_history_regular_history,
    filter_henan_history_regular_scope,
)
from app.models.henan_source_registry import HenanDataSource

# 覆盖报告的分组顺序
_REPORT_GROUPS = ["historical", "latest_2026", "historical_and_latest", "current_signal"]
_PILOT_GROUP_RATIO = 0.8
_PILOT_PLAN_RATIO = 0.8
_PRODUCTION_GROUP_RATIO = 0.98
_PRODUCTION_PLAN_RATIO = 0.98
_PILOT_MAJOR_GROUP_HISTORY_2025 = 1000
_PILOT_MAJOR_GROUP_HISTORY_2024 = 1000


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
    all_groups = load_henan_program_groups(seed_dir)
    all_plans = load_henan_enrollment_plans(seed_dir)
    history = load_henan_admission_history(seed_dir)
    groups, plans = filter_henan_history_regular_scope(all_groups, all_plans)
    history = filter_henan_history_regular_history(history, groups)
    scoped_school_codes = {group.school_code for group in groups}
    official_catalog = seed_dir.parent / "raw" / "henan_2026" / "normalized_catalog.csv"
    official_catalog_source_ready = int(
        official_catalog.exists() and sum(1 for _ in official_catalog.open(encoding="utf-8-sig")) > 1
    )

    return {
        "actual": {
            "universities_2026": len({u.school_code for u in universities if u.school_code in scoped_school_codes}),
            "program_groups_2026": len(groups),
            "enrollment_plans_henan_2026": len(plans),
        },
        "quality": {
            "verified_program_groups_2026": sum(1 for x in groups if x.review_status == "verified"),
            "verified_enrollment_plans_2026": sum(1 for x in plans if x.review_status == "verified"),
            "nonzero_enrollment_plans_2026": sum(1 for x in plans if x.plan_count > 0),
            "scoped_unverified_groups_2026": sum(1 for x in groups if x.review_status != "verified"),
            "scoped_unverified_plans_2026": sum(1 for x in plans if x.review_status != "verified"),
            "excluded_special_groups_2026": len(all_groups) - len(groups),
            "excluded_special_plans_2026": len(all_plans) - len(plans),
            "verified_2025_history": sum(
                1 for x in history if x.year == 2025 and x.review_status == "verified" and (x.min_rank or 0) > 0
            ),
            "verified_2024_history": sum(
                1 for x in history if x.year == 2024 and x.review_status == "verified" and (x.min_rank or 0) > 0
            ),
            "verified_2025_major_group_history": sum(
                1
                for x in history
                if x.year == 2025
                and x.data_granularity == "major_group"
                and x.review_status == "verified"
                and (x.min_rank or 0) > 0
            ),
            "verified_2024_major_group_history": sum(
                1
                for x in history
                if x.year == 2024
                and x.data_granularity == "major_group"
                and x.review_status == "verified"
                and (x.min_rank or 0) > 0
            ),
            "single_subject_requirement_groups_2026": sum(1 for x in groups if x.single_subject_requirements),
            "public_foreign_language_groups_2026": sum(1 for x in groups if x.public_foreign_languages),
            "accommodation_plans_2026": sum(1 for x in plans if x.accommodation not in (None, "")),
            "official_catalog_source_ready": official_catalog_source_ready,
        },
    }


def build_henan_readiness_status(report: dict) -> dict:
    """Build conservative readiness flags for the narrowed Henan history-track scope."""
    actual = report.get("actual", {})
    quality = report.get("quality", {})

    groups_total = actual.get("program_groups_2026", 0) or 0
    plans_total = actual.get("enrollment_plans_henan_2026", 0) or 0
    groups_verified = quality.get("verified_program_groups_2026", 0) or 0
    plans_verified = quality.get("verified_enrollment_plans_2026", 0) or 0
    group_ratio = (groups_verified / groups_total) if groups_total else 0.0
    plan_ratio = (plans_verified / plans_total) if plans_total else 0.0

    notes: list[str] = []

    pilot_ready = (
        group_ratio >= _PILOT_GROUP_RATIO
        and plan_ratio >= _PILOT_PLAN_RATIO
        and quality.get("verified_2025_major_group_history", 0) >= _PILOT_MAJOR_GROUP_HISTORY_2025
        and quality.get("verified_2024_major_group_history", 0) >= _PILOT_MAJOR_GROUP_HISTORY_2024
        and quality.get("single_subject_requirement_groups_2026", 0) > 0
        and quality.get("public_foreign_language_groups_2026", 0) > 0
        and quality.get("accommodation_plans_2026", 0) > 0
    )

    has_official_catalog = quality.get("official_catalog_source_ready", 0) > 0
    production_ready = (
        pilot_ready
        and group_ratio >= _PRODUCTION_GROUP_RATIO
        and plan_ratio >= _PRODUCTION_PLAN_RATIO
        and has_official_catalog
    )

    if not pilot_ready:
        if group_ratio < _PILOT_GROUP_RATIO:
            notes.append("非全量覆盖：已核验专业组覆盖率不足，当前仅适合试运行。")
        if plan_ratio < _PILOT_PLAN_RATIO:
            notes.append("非全量覆盖：已核验招生计划覆盖率不足，当前仅适合试运行。")
        if quality.get("verified_2025_major_group_history", 0) < _PILOT_MAJOR_GROUP_HISTORY_2025:
            notes.append("数据不足：2025 历史类专业组位次基线覆盖不足。")
        if quality.get("verified_2024_major_group_history", 0) < _PILOT_MAJOR_GROUP_HISTORY_2024:
            notes.append("数据不足：2024 历史类专业组位次基线覆盖不足。")
        if quality.get("single_subject_requirement_groups_2026", 0) <= 0:
            notes.append("数据不足：单科要求尚未形成结构化覆盖。")
        if quality.get("public_foreign_language_groups_2026", 0) <= 0:
            notes.append("数据不足：公共外语教学限制尚未形成结构化覆盖。")
        if quality.get("accommodation_plans_2026", 0) <= 0:
            notes.append("数据不足：住宿费尚未形成结构化覆盖。")
    elif not production_ready:
        notes.append("非全量覆盖：当前为 pilot_ready，仍未达到 production_ready。")
        if group_ratio >= 1.0 and plan_ratio >= 1.0:
            notes.append("当前河南 2026 历史类普通本科批范围内专业组与招生计划已全部达到 verified。")
        if group_ratio < _PRODUCTION_GROUP_RATIO:
            notes.append("非全量覆盖：专业组核验覆盖仍未达到生产阈值。")
        if plan_ratio < _PRODUCTION_PLAN_RATIO:
            notes.append("非全量覆盖：招生计划核验覆盖仍未达到生产阈值。")
        if not has_official_catalog:
            notes.append("非全量覆盖：尚缺河南 2026 官方全量专业目录结构化源，当前为 gaokao.cn 核验主链路。")

    coverage_status = "production_ready" if production_ready else "pilot_ready" if pilot_ready else "not_ready"
    return {
        "data_ready": pilot_ready,
        "pilot_ready": pilot_ready,
        "production_ready": production_ready,
        "coverage_status": coverage_status,
        "coverage_notes": notes,
    }


def build_henan_data_evidence(report: dict) -> dict:
    """Return a structured evidence summary for API consumers."""
    quality = report.get("quality", {})
    return {
        "scope": {
            "province": "河南",
            "year": 2026,
            "track": "历史类",
            "batch": "本科批",
        },
        "readiness": {
            "official_catalog_available": quality.get("official_catalog_source_ready", 0) > 0,
            "scoped_groups_fully_verified": quality.get("scoped_unverified_groups_2026", 0) == 0,
            "scoped_plans_fully_verified": quality.get("scoped_unverified_plans_2026", 0) == 0,
        },
        "verification": {
            "verified_program_groups_2026": quality.get("verified_program_groups_2026", 0),
            "verified_enrollment_plans_2026": quality.get("verified_enrollment_plans_2026", 0),
            "verified_2025_major_group_history": quality.get("verified_2025_major_group_history", 0),
            "verified_2024_major_group_history": quality.get("verified_2024_major_group_history", 0),
        },
        "exclusions": {
            "excluded_special_groups_2026": quality.get("excluded_special_groups_2026", 0),
            "excluded_special_plans_2026": quality.get("excluded_special_plans_2026", 0),
        },
        "source_gaps": {
            "official_catalog_source_ready": quality.get("official_catalog_source_ready", 0),
            "missing_official_catalog_reason": (
                "缺少河南 2026 官方全量专业目录结构化源"
                if quality.get("official_catalog_source_ready", 0) <= 0
                else ""
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
