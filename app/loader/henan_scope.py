from __future__ import annotations

from collections import defaultdict


EXCLUDED_SPECIAL_TYPES = {"国家专项", "高校专项", "地方专项"}
ART_REMARK_KEYWORDS = (
    "艺术类专业组",
    "授予艺术学学士学位",
    "艺术类专业",
    "不得转入非艺术类专业",
)
PREPARATORY_KEYWORDS = ("预科班", "预科组", "边防军人子女预科班")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def is_henan_history_regular_group(group, group_plans: list | None = None) -> bool:
    if group.track != "历史类" or group.batch != "本科批":
        return False

    if (group.special_qualification_type or "").strip() in EXCLUDED_SPECIAL_TYPES:
        return False

    group_major_text = " ".join(group.included_majors or [])
    group_remark_text = f"{group.major_group_name or ''} {getattr(group, 'remarks', '') or ''}"
    if _contains_any(group_major_text, PREPARATORY_KEYWORDS):
        return False
    if _contains_any(group_remark_text, ART_REMARK_KEYWORDS + PREPARATORY_KEYWORDS):
        return False

    for plan in group_plans or []:
        if plan.track != "历史类" or plan.batch != "本科批":
            return False
        if (plan.special_qualification_type or "").strip() in EXCLUDED_SPECIAL_TYPES:
            return False
        text = f"{plan.major_name or ''} {getattr(plan, 'remarks', '') or ''}"
        if _contains_any(text, ART_REMARK_KEYWORDS + PREPARATORY_KEYWORDS):
            return False

    return True


def filter_henan_history_regular_scope(groups: list, plans: list) -> tuple[list, list]:
    plans_by_key: dict[tuple[str, str, str, str], list] = defaultdict(list)
    for plan in plans:
        plans_by_key[(plan.school_code, plan.major_group_code, plan.track, plan.batch)].append(plan)

    scoped_groups = []
    scoped_keys = set()
    for group in groups:
        key = (group.school_code, group.major_group_code, group.track, group.batch)
        if is_henan_history_regular_group(group, plans_by_key.get(key, [])):
            scoped_groups.append(group)
            scoped_keys.add(key)

    scoped_plans = [plan for plan in plans if (plan.school_code, plan.major_group_code, plan.track, plan.batch) in scoped_keys]
    return scoped_groups, scoped_plans


def filter_henan_history_regular_universities(universities: list, scoped_groups: list) -> list:
    school_codes = {group.school_code for group in scoped_groups}
    return [university for university in universities if university.school_code in school_codes]


def filter_henan_history_regular_history(history: list, scoped_groups: list) -> list:
    group_keys = {(group.school_code, group.major_group_code) for group in scoped_groups}
    school_codes = {group.school_code for group in scoped_groups}
    filtered = []
    for item in history:
        if item.track != "历史类" or item.batch != "本科批":
            continue
        if item.data_granularity == "major_group":
            if (item.school_code, item.major_group_code) in group_keys:
                filtered.append(item)
            continue
        if item.school_code in school_codes:
            filtered.append(item)
    return filtered
