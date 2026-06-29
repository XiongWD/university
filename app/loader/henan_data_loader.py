"""河南志愿推 seed 加载器（design §4、File Structure Task 2）。

从 data/seed/henan/ 加载政策、院校、专业组、招生计划、就业信号。
缺文件降级返回空列表，不阻断调用方。
使用 lru_cache 避免重复解析 YAML（性能优化）。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from collections import defaultdict

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
    # 使用 C 加速解析器（性能提升约 6x）
    content = path.read_text(encoding="utf-8")
    return yaml.load(content, Loader=yaml.CSafeLoader) or []


@lru_cache(maxsize=1)
def load_city_living_cost_cached(seed_dir_str: str) -> dict[str, int]:
    """加载城市生活成本库（data/seed/cities/cities.yaml），返回 {城市名: 月综合成本中位}。

    月综合成本中位 = (monthly_total.low + monthly_total.high) / 2。
    供推荐候选按学校城市估算生活费；缺失文件返回空 dict，调用方回退全国基准。
    """
    rows = _read_yaml(Path(seed_dir_str) / "cities" / "cities.yaml")
    monthly_mid: dict[str, int] = {}
    for row in rows:
        city = row.get("city")
        mt = row.get("monthly_total") or {}
        low = mt.get("low")
        high = mt.get("high")
        if city and isinstance(low, (int, float)) and isinstance(high, (int, float)):
            monthly_mid[city] = round((low + high) / 2)
    return monthly_mid


def load_city_living_cost(seed_dir: Path) -> dict[str, int]:
    """加载城市月综合成本中位（非 lru_cache 入口，便于传 Path）。"""
    return load_city_living_cost_cached(str(seed_dir))


def load_henan_policy(seed_dir: Path) -> list[HenanAdmissionPolicy]:
    rows: list[dict] = []
    for path in (seed_dir / "henan/policy").glob("*.yaml"):
        rows.extend(_read_yaml(path))
    return [HenanAdmissionPolicy.model_validate(x) for x in rows]


@lru_cache(maxsize=1)
def load_henan_universities_cached(seed_dir_str: str) -> list[HenanUniversity]:
    return [HenanUniversity.model_validate(x) for x in _read_yaml(Path(seed_dir_str) / "henan/universities.yaml")]


def load_henan_universities(seed_dir: Path) -> list[HenanUniversity]:
    return load_henan_universities_cached(str(seed_dir))


@lru_cache(maxsize=1)
def load_henan_program_groups_cached(seed_dir_str: str) -> list[HenanProgramGroup]:
    return [HenanProgramGroup.model_validate(x) for x in _read_yaml(Path(seed_dir_str) / "henan/program_groups_2026.yaml")]


def load_henan_program_groups(seed_dir: Path) -> list[HenanProgramGroup]:
    return load_henan_program_groups_cached(str(seed_dir))


@lru_cache(maxsize=1)
def load_henan_enrollment_plans_cached(seed_dir_str: str) -> list[HenanEnrollmentPlan]:
    return [HenanEnrollmentPlan.model_validate(x) for x in _read_yaml(Path(seed_dir_str) / "henan/enrollment_plans_2026.yaml")]


def load_henan_enrollment_plans(seed_dir: Path) -> list[HenanEnrollmentPlan]:
    return load_henan_enrollment_plans_cached(str(seed_dir))


def load_henan_employment_signals(seed_dir: Path) -> list[MajorEmploymentSignal]:
    return [MajorEmploymentSignal.model_validate(x) for x in _read_yaml(seed_dir / "henan/employment_signals.yaml")]


def load_henan_admission_history(
    seed_dir: Path, years: tuple[int, ...] = (2025, 2024)
) -> list[HenanAdmissionHistory]:
    """加载 2025/2024 历史录取分数和位次（design §4.2、Task 2B）。

    每年一个 YAML 文件 admission_history_{year}.yaml，缺文件降级返回空。
    使用 lru_cache 缓存。
    """
    return _load_henan_admission_history_cached(str(seed_dir), years)


@lru_cache(maxsize=2)
def _load_henan_admission_history_cached(
    seed_dir_str: str, years: tuple[int, ...]
) -> list[HenanAdmissionHistory]:
    rows: list[HenanAdmissionHistory] = []
    seed_dir = Path(seed_dir_str)
    for year in years:
        rows.extend(
            HenanAdmissionHistory.model_validate(x)
            for x in _read_yaml(seed_dir / f"henan/admission_history_{year}.yaml")
        )
    return rows


# ── 历史基线预索引 ────────────────────────────────────────────────────

_HISTORY_INDEX: dict | None = None
_HISTORY_INDEX_KEY: tuple[int, int] | None = None


def _build_history_index(history: list[HenanAdmissionHistory]) -> dict:
    """建立历史录取的预索引，加速 find_best_historical_baseline。"""
    global _HISTORY_INDEX, _HISTORY_INDEX_KEY
    # 缓存键用首个元素的 id + 长度，避免测试间不同 history 对象因 id 复用而命中错误缓存
    cache_key = (id(history[0]) if history else 0, len(history))
    if _HISTORY_INDEX is not None and _HISTORY_INDEX_KEY == cache_key:
        return _HISTORY_INDEX

    idx: dict = {
        "by_school_track_batch": defaultdict(list),
        "by_school_group": defaultdict(list),
        "by_year_granularity": defaultdict(list),
    }
    for h in history:
        key = (h.school_code, h.track, getattr(h, "batch", "本科批"))
        idx["by_school_track_batch"][key].append(h)
        if h.major_group_code:
            idx["by_school_group"][(h.school_code, h.major_group_code)].append(h)
        idx["by_year_granularity"][(h.school_code, h.year, h.data_granularity)].append(h)
    _HISTORY_INDEX = idx
    _HISTORY_INDEX_KEY = cache_key
    return idx


def clear_history_cache() -> None:
    """清除历史数据缓存（用于测试热加载）。"""
    global _HISTORY_INDEX, _HISTORY_INDEX_KEY
    _HISTORY_INDEX = None
    _HISTORY_INDEX_KEY = None
    _load_henan_admission_history_cached.cache_clear()
    load_henan_program_groups_cached.cache_clear()
    load_henan_enrollment_plans_cached.cache_clear()
    load_henan_universities_cached.cache_clear()


def find_best_historical_baseline(
    history: list[HenanAdmissionHistory],
    *,
    school_code: str,
    group_code: str | None,
    major_names: list[str],
    track: str,
    batch: str,
) -> dict | None:
    """多层级历史基线查找（design D3）。使用预索引加速。"""
    idx = _build_history_index(history)
    same_school_track = idx["by_school_track_batch"].get((school_code, track, batch), [])

    def _verified_rank(h: HenanAdmissionHistory) -> int | None:
        if h.review_status != "verified":
            return None
        if not h.min_rank or h.min_rank <= 0:
            return None
        return h.min_rank

    def _inferred_school_baseline(year: int) -> dict | None:
        ranks = [
            rank
            for h in same_school_track
            if h.year == year
            for rank in [_verified_rank(h)]
            if rank
        ]
        if not ranks:
            return None
        # Use the toughest same-school cutoff as a conservative fallback.
        return {
            "adjusted_min_rank": min(ranks),
            "year": year,
            "review_status": "verified",
            "data_granularity": "school_inferred",
        }

    # 1. 2025 专业级（最精确，单年即可定）
    for h in same_school_track:
        if h.year == 2025 and h.data_granularity == "major" and h.major_name in major_names:
            rank = _verified_rank(h)
            if rank:
                return {"adjusted_min_rank": rank, "year": 2025,
                        "review_status": h.review_status, "data_granularity": "major"}

    # 2. 2025+2024 专业组级加权趋势（两年都有时优先用，比单年更稳定）
    r2025 = next((_verified_rank(h) for h in same_school_track
                  if h.year == 2025 and h.data_granularity == "major_group"
                  and h.major_group_code == group_code), None)
    r2024 = next((_verified_rank(h) for h in same_school_track
                  if h.year == 2024 and h.data_granularity == "major_group"
                  and h.major_group_code == group_code), None)
    if r2025 and r2024:
        # 2025 权重 0.7，2024 权重 0.3（近年权重更高，但纳入历史趋势降噪）
        weighted = round(r2025 * 0.7 + r2024 * 0.3)
        return {"adjusted_min_rank": weighted, "year": 2025,
                "review_status": "verified", "data_granularity": "major_group_trend"}

    # 3. 仅 2025 专业组级（2024 缺失时的单年兜底）
    if r2025:
        return {"adjusted_min_rank": r2025, "year": 2025,
                "review_status": "verified", "data_granularity": "major_group"}

    # 4. 仅 2024 专业组级（2025 缺失时用上一年，比校级精确）
    if r2024:
        return {"adjusted_min_rank": r2024, "year": 2024,
                "review_status": "verified", "data_granularity": "major_group"}

    # 5. 2025 校级兜底（低置信）
    for h in same_school_track:
        if h.year == 2025 and h.data_granularity in ("school", "school_batch") and not h.major_group_code:
            rank = _verified_rank(h)
            if rank:
                return {"adjusted_min_rank": rank, "year": 2025,
                        "review_status": h.review_status, "data_granularity": "school"}

    inferred_2025 = _inferred_school_baseline(2025)
    if inferred_2025:
        return inferred_2025

    inferred_2024 = _inferred_school_baseline(2024)
    if inferred_2024:
        return inferred_2024

    return None
