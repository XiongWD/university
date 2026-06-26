"""河南志愿推 seed 加载器（design §4、File Structure Task 2）。

从 data/seed/henan/ 加载政策、院校、专业组、招生计划、就业信号。
缺文件降级返回空列表，不阻断调用方。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from app.models.henan_data import (
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
