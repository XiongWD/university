"""专业反推 2026 院校专业组（design §4.3）。

从「学校 + 专业 + 科类 + 批次」反查专业组。同一专业可能落在多个组（普通/中外合作/
不同选科组），返回全部候选，不跨校跨科类混查。专业名做全角/半角归一化匹配。
"""
from __future__ import annotations


def _normalize_major(name: str) -> str:
    return name.replace("（", "(").replace("）", ")").strip()


def find_groups_by_major(
    groups: list,
    school_code: str,
    major_name: str,
    track: str,
    batch: str,
) -> list:
    """按 学校代码 + 专业 + 科类 + 批次 反查专业组，返回所有匹配的候选组。"""
    normalized = _normalize_major(major_name)
    matches = []
    for group in groups:
        if group.school_code != school_code:
            continue
        if group.track != track:
            continue
        if getattr(group, "batch", batch) != batch:
            continue
        majors = [_normalize_major(item) for item in group.included_majors]
        if normalized in majors:
            matches.append(group)
    return matches
