"""河南志愿推 seed 加载器（design §4、File Structure Task 2）。

从 data/seed/henan/ 加载政策、院校、专业组、招生计划、就业信号。
缺文件降级返回空列表，不阻断调用方。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from app.models.henan_data import (
    HenanAdmissionHistory,
    HenanAdmissionPolicy,
    HenanEnrollmentPlan,
    HenanProgramGroup,
    HenanUniversity,
    MajorEmploymentSignal,
)


def _read_yaml(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def load_henan_policy(seed_dir: Path) -> list[HenanAdmissionPolicy]:
    rows: list[dict] = []
    for path in (seed_dir / "henan/policy").glob("*.yaml"):
        rows.extend(_read_yaml(path))
    return [HenanAdmissionPolicy.model_validate(x) for x in rows]


def load_henan_universities(seed_dir: Path) -> list[HenanUniversity]:
    return [HenanUniversity.model_validate(x) for x in _read_yaml(seed_dir / "henan/universities.yaml")]


def load_henan_program_groups(seed_dir: Path) -> list[HenanProgramGroup]:
    return [HenanProgramGroup.model_validate(x) for x in _read_yaml(seed_dir / "henan/program_groups_2026.yaml")]


def load_henan_enrollment_plans(seed_dir: Path) -> list[HenanEnrollmentPlan]:
    return [HenanEnrollmentPlan.model_validate(x) for x in _read_yaml(seed_dir / "henan/enrollment_plans_2026.yaml")]


def load_henan_employment_signals(seed_dir: Path) -> list[MajorEmploymentSignal]:
    return [MajorEmploymentSignal.model_validate(x) for x in _read_yaml(seed_dir / "henan/employment_signals.yaml")]


def load_henan_admission_history(
    seed_dir: Path, years: tuple[int, ...] = (2025, 2024)
) -> list[HenanAdmissionHistory]:
    """加载 2025/2024 历史录取分数和位次（design §4.2、Task 2B）。

    每年一个 YAML 文件 admission_history_{year}.yaml，缺文件降级返回空。
    """
    rows: list[HenanAdmissionHistory] = []
    for year in years:
        rows.extend(
            HenanAdmissionHistory.model_validate(x)
            for x in _read_yaml(seed_dir / f"henan/admission_history_{year}.yaml")
        )
    return rows


def find_best_historical_baseline(
    history: list[HenanAdmissionHistory],
    *,
    school_code: str,
    group_code: str | None,
    major_names: list[str],
    track: str,
    batch: str,
) -> dict | None:
    """多层级历史基线查找（design D3）。

    查找顺序：
    1. 2025 专业级 min_rank（最准）
    2. 2025 专业组级 min_rank
    3. 2025+2024 加权趋势（两组都有时）
    4. 2025 校级兜底（低置信）
    5. 无则 None

    返回 {adjusted_min_rank, year, review_status, data_granularity} 或 None。
    verified 行的 min_rank 必须 > 0（导入器已拒绝 verified+缺位次）。
    """
    same_school_track = [
        h for h in history
        if h.school_code == school_code and h.track == track
        and getattr(h, "batch", batch) == batch
    ]

    def _verified_rank(h: HenanAdmissionHistory) -> int | None:
        if h.review_status != "verified":
            return None
        if not h.min_rank or h.min_rank <= 0:
            return None
        return h.min_rank

    # 1. 2025 专业级
    for h in same_school_track:
        if h.year == 2025 and h.data_granularity == "major" and h.major_name in major_names:
            rank = _verified_rank(h)
            if rank:
                return {"adjusted_min_rank": rank, "year": 2025,
                        "review_status": h.review_status, "data_granularity": "major"}

    # 2. 2025 专业组级
    for h in same_school_track:
        if h.year == 2025 and h.data_granularity == "major_group" and h.major_group_code == group_code:
            rank = _verified_rank(h)
            if rank:
                return {"adjusted_min_rank": rank, "year": 2025,
                        "review_status": h.review_status, "data_granularity": "major_group"}

    # 3. 2025+2024 加权趋势（专业组级两组都有）
    r2025 = next((_verified_rank(h) for h in same_school_track
                  if h.year == 2025 and h.data_granularity == "major_group"
                  and h.major_group_code == group_code), None)
    r2024 = next((_verified_rank(h) for h in same_school_track
                  if h.year == 2024 and h.data_granularity == "major_group"
                  and h.major_group_code == group_code), None)
    if r2025 and r2024:
        # 2025 权重 0.7，2024 权重 0.3
        weighted = round(r2025 * 0.7 + r2024 * 0.3)
        return {"adjusted_min_rank": weighted, "year": 2025,
                "review_status": "verified", "data_granularity": "major_group_trend"}

    # 4. 2025 校级兜底（低置信）
    for h in same_school_track:
        if h.year == 2025 and h.data_granularity in ("school", "school_batch") and not h.major_group_code:
            rank = _verified_rank(h)
            if rank:
                return {"adjusted_min_rank": rank, "year": 2025,
                        "review_status": h.review_status, "data_granularity": "school"}

    return None
