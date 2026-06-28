from __future__ import annotations


UNKNOWN_TUITION_VALUES = {"", "-", "待定", "待定。", "待定；", "待定元", "null", "none", "None"}


def _normalize_text(value) -> str:
    return str(value or "").strip()


def _normalize_tuition(value) -> str | None:
    text = _normalize_text(value)
    if text in UNKNOWN_TUITION_VALUES:
        return None
    return text


def reconcile_group_from_api_items(local_rows: list[dict], api_items: list[dict]) -> dict | None:
    if not local_rows or not api_items:
        return None

    api_by_special_id: dict[str, list[dict]] = {}
    for item in api_items:
        special_id = _normalize_text(item.get("school_special_id"))
        if not special_id:
            continue
        api_by_special_id.setdefault(special_id, []).append(item)

    destination_groups: set[str] = set()
    matched_count = 0

    for row in local_rows:
        special_id = _normalize_text(row.get("school_special_id"))
        candidates = api_by_special_id.get(special_id, [])
        if not candidates:
            return None

        local_name = _normalize_text(row.get("sp_name"))
        local_num = _normalize_text(row.get("num"))
        local_tuition = _normalize_tuition(row.get("tuition"))
        api_item = None
        for candidate in candidates:
            if _normalize_text(candidate.get("sp_name")) != local_name:
                continue
            if _normalize_text(candidate.get("num")) != local_num:
                continue
            api_tuition = _normalize_tuition(candidate.get("tuition"))
            if local_tuition is not None and api_tuition is not None and local_tuition != api_tuition:
                continue
            api_item = candidate
            break
        if api_item is None:
            return None

        destination_group = _normalize_text(api_item.get("special_group"))
        if not destination_group:
            return None
        destination_groups.add(destination_group)
        matched_count += 1

    if len(destination_groups) != 1:
        return None

    old_group = _normalize_text(local_rows[0].get("special_group"))
    new_group = next(iter(destination_groups))
    return {
        "old_group": old_group,
        "new_group": new_group,
        "matched_count": matched_count,
    }
