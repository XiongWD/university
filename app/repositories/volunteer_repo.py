"""我的志愿组 Repo（用户级持久化，design：志愿编排工作台）。

数据一致性核心：
  - sort_order 是全局唯一顺序（编排页分区仅视觉）
  - 跨档拖拽走 apply_layout 单事务原子更新（planned_tier+sort_order+version）
  - 乐观锁 version 防多标签页覆盖（不符抛 VolunteerConflictError）
  - 服务端用 group.profile_snapshot 重新校验资格/档位（不信任前端传的展示字段）
  - 算法档位存审计快照 algorithm_tier_at_add；GET 时重算 latest_algorithm_tier（不覆盖 planned_tier）
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, select

from app.models.tables import UserVolunteerGroupRow, UserVolunteerItemRow
from app.models.volunteer import (
    StructureHint,
    UserVolunteerGroup,
    UserVolunteerItem,
    VolunteerConflictError,
    VolunteerStats,
)

MAX_ITEMS = 48  # 河南本科批 48 个院校专业组
# 规划档位白名单（algorithm 可含 超冲/需复核，但 planned_tier 仅允许五档）
_PLANNABLE_TIERS = ["搏", "冲", "稳", "保", "垫"]
# 档位顺序（用于插入位置计算，从难到易）
_TIER_ORDER = {"超冲": 0, "搏": 1, "冲": 2, "稳": 3, "保": 4, "垫": 5, "需人工复核": 6, "不推荐": 7}


def _now() -> datetime:
    return datetime.now()


def get_or_create_group(session: Session, owner_key: str = "default") -> UserVolunteerGroupRow:
    """获取或创建志愿方案（唯一约束保证单条）。首次创建不绑 profile（首次添加时绑定）。"""
    group = session.exec(
        select(UserVolunteerGroupRow).where(UserVolunteerGroupRow.owner_key == owner_key)
    ).first()
    if group is None:
        now = _now()
        group = UserVolunteerGroupRow(
            owner_key=owner_key, name="我的志愿组", profile_snapshot="{}",
            manually_reordered=False, version=1, created_at=now, updated_at=now,
        )
        session.add(group)
        session.commit()
        session.refresh(group)
    return group


def _recompute_candidates(profile: dict) -> list[dict]:
    """用考生档案跑推荐引擎，返回候选列表（GET/POST 重算依据）。"""
    from app.engine.henan_recommendation import build_henan_candidates
    try:
        return build_henan_candidates(profile)
    except (ValueError, Exception):
        return []  # 档案无效或本科线不达标 → 无法重算，返回空（item 降级显示添加时快照）


def _find_candidate(candidates: list[dict], school_code: str, group_code: str) -> dict | None:
    """从候选列表中找指定院校专业组。"""
    for c in candidates:
        if str(c.get("school_code")) == str(school_code) and str(c.get("major_group_code")) == str(group_code):
            return c
    return None


def _item_to_domain(row: UserVolunteerItemRow, candidate: dict | None) -> UserVolunteerItem:
    """Row → Domain item。candidate 非空时用当前推荐结果重算展示字段，否则用添加时快照。"""
    snap = json.loads(row.source_snapshot) if row.source_snapshot else {}
    if candidate:
        latest_tier = candidate.get("bucket") or snap.get("algorithm_tier", "需复核")
        eligibility = candidate.get("group_eligibility_status") or snap.get("eligibility_status", "uncertain")
        is_local = candidate.get("is_henan_local")
        ownership = candidate.get("school_ownership")
        four_year = candidate.get("four_year_total")
    else:
        latest_tier = snap.get("algorithm_tier", "需复核")
        eligibility = snap.get("eligibility_status", "uncertain")
        is_local = snap.get("is_henan_local")
        ownership = snap.get("school_ownership")
        four_year = snap.get("four_year_total")

    planned = row.planned_tier
    effective = planned if planned in _PLANNABLE_TIERS else latest_tier
    return UserVolunteerItem(
        id=row.id, group_id=row.group_id,
        school_code=row.school_code, school_name=row.school_name,
        major_group_code=row.major_group_code, major_group_name=row.major_group_name,
        algorithm_tier_at_add=row.algorithm_tier_at_add,
        latest_algorithm_tier=latest_tier,
        algorithm_changed=(latest_tier != row.algorithm_tier_at_add),
        planned_tier=planned,
        effective_tier=effective,
        sort_order=row.sort_order,
        eligibility_status=eligibility,
        is_henan_local=is_local,
        school_ownership=ownership,
        four_year_total=four_year,
    )


def _group_to_domain(
    session: Session, group_row: UserVolunteerGroupRow, recompute: bool = True
) -> UserVolunteerGroup:
    """Row → Domain group（含 items + stats）。recompute=True 时用 profile_snapshot 重算展示字段。"""
    profile = json.loads(group_row.profile_snapshot) if group_row.profile_snapshot else {}
    candidates = _recompute_candidates(profile) if (recompute and profile) else []
    cand_by_key = {(str(c.get("school_code")), str(c.get("major_group_code"))): c for c in candidates}

    item_rows = session.exec(
        select(UserVolunteerItemRow)
        .where(UserVolunteerItemRow.group_id == group_row.id)
        .order_by(UserVolunteerItemRow.sort_order)
    ).all()

    items = []
    for r in item_rows:
        cand = cand_by_key.get((r.school_code, r.major_group_code))
        items.append(_item_to_domain(r, cand))

    stats = _compute_stats(items)
    return UserVolunteerGroup(
        id=group_row.id, owner_key=group_row.owner_key, name=group_row.name,
        version=group_row.version, manually_reordered=group_row.manually_reordered,
        profile_snapshot=profile, items=items, stats=stats,
    )


def get_group(session: Session, owner_key: str = "default") -> UserVolunteerGroup:
    """获取志愿方案（GET 重算 latest_algorithm_tier + stats）。"""
    group = get_or_create_group(session, owner_key)
    return _group_to_domain(session, group, recompute=True)


def add_item(
    session: Session, owner_key: str, school_code: str, major_group_code: str, profile: dict
) -> UserVolunteerGroup:
    """添加志愿。服务端用 profile 重新校验（不信任前端传的展示字段）。

    校验：资格（ineligible 拒绝 400）、去重、上限48。
    首次添加时把 profile 绑定为 group.profile_snapshot（后续 GET/POST 重算依据）。
    """
    group = get_or_create_group(session, owner_key)
    # 首次绑定 profile_snapshot（若之前为空）
    if not json.loads(group.profile_snapshot or "{}"):
        group.profile_snapshot = json.dumps(profile, ensure_ascii=False)

    # 重新校验：跑推荐引擎找该专业组
    candidates = _recompute_candidates(profile)
    candidate = _find_candidate(candidates, school_code, major_group_code)
    if not candidate:
        raise ValueError("该院校专业组在当前考生档案下不存在或不可达，无法加入志愿组")

    eligibility = candidate.get("group_eligibility_status") or "uncertain"
    if eligibility == "ineligible":
        raise ValueError(
            f"该院校专业组资格不符（{candidate.get('group_eligibility_status')}），"
            f"不可加入志愿组：{'；'.join(candidate.get('blocked_reasons') or [])}"
        )

    # 去重预检（唯一约束兜底）
    exists = session.exec(
        select(UserVolunteerItemRow).where(
            UserVolunteerItemRow.group_id == group.id,
            UserVolunteerItemRow.school_code == str(school_code),
            UserVolunteerItemRow.major_group_code == str(major_group_code),
        )
    ).first()
    if exists:
        raise ValueError("该院校专业组已在志愿组中，不可重复添加")

    # 上限校验（48，含 uncertain/超冲都占名额）
    count = session.exec(
        select(UserVolunteerItemRow).where(UserVolunteerItemRow.group_id == group.id)
    ).all()
    if len(count) >= MAX_ITEMS:
        raise ValueError(f"志愿组已达上限 {MAX_ITEMS} 个院校专业组")

    algorithm_tier = candidate.get("bucket") or "需复核"
    # 插入位置：按档位策略（不粗暴放末尾）
    sort_order = _compute_insert_position(count, algorithm_tier, group.manually_reordered)

    # 生成添加时快照（审计用）
    snapshot = {
        "algorithm_tier": algorithm_tier,
        "eligibility_status": eligibility,
        "is_henan_local": candidate.get("is_henan_local"),
        "school_ownership": candidate.get("school_ownership"),
        "four_year_total": candidate.get("four_year_total"),
    }
    # 把新项之后的所有项 sort_order +1（保持连续）
    _shift_after(session, group.id, sort_order, delta=1)
    new_item = UserVolunteerItemRow(
        group_id=group.id, school_code=str(school_code),
        school_name=candidate.get("school_name", ""), major_group_code=str(major_group_code),
        major_group_name=candidate.get("major_group_name", ""),
        algorithm_tier_at_add=algorithm_tier, planned_tier=None,
        sort_order=sort_order, source_snapshot=json.dumps(snapshot, ensure_ascii=False),
        added_at=_now(),
    )
    session.add(new_item)
    group.version += 1
    group.updated_at = _now()
    session.add(group)
    session.commit()
    session.refresh(group)
    return _group_to_domain(session, group, recompute=True)


def _compute_insert_position(existing: list, tier: str, manually_reordered: bool) -> int:
    """计算新项插入位置（按档位策略，防破坏梯度）。

    manually_reordered=False：插入到同 algorithm_tier 档末尾
    manually_reordered=True：仍尝试同档末尾，无同档则按档位顺序插入
    """
    if not existing:
        return 0
    same_tier = [e for e in existing if e.algorithm_tier_at_add == tier]
    if same_tier:
        # 同档末尾
        return max(e.sort_order for e in same_tier) + 1
    if manually_reordered:
        # 手动排序过：无同档，按档位顺序找插入点（插入到下一档之前）
        target_rank = _TIER_ORDER.get(tier, 99)
        for e in sorted(existing, key=lambda x: x.sort_order):
            if _TIER_ORDER.get(e.algorithm_tier_at_add, 99) > target_rank:
                return e.sort_order
        return max(e.sort_order for e in existing) + 1
    # 未手动排序：无同档，放末尾
    return max(e.sort_order for e in existing) + 1


def _shift_after(session: Session, group_id: int, from_order: int, delta: int) -> None:
    """把 sort_order >= from_order 的项整体偏移 delta。"""
    session.exec(
        select(UserVolunteerItemRow).where(
            UserVolunteerItemRow.group_id == group_id,
            UserVolunteerItemRow.sort_order >= from_order,
        )
    )  # 触发查询；更新用原生 SQL 更高效
    from sqlmodel import text
    session.exec(text(
        "UPDATE user_volunteer_items SET sort_order = sort_order + :d "
        "WHERE group_id = :gid AND sort_order >= :fo"
    ), params={"d": delta, "gid": group_id, "fo": from_order})


def apply_layout(
    session: Session, group_row: UserVolunteerGroupRow,
    layout_items: list[dict], expected_version: int,
) -> UserVolunteerGroup:
    """原子布局更新（跨档拖拽专用）：单事务同时改 planned_tier+全局sort_order+version。

    layout_items: [{item_id, planned_tier|null, sort_order}]
    """
    if group_row.version != expected_version:
        raise VolunteerConflictError(
            "志愿组已在其他页面更新", _group_to_domain(session, group_row)
        )
    # 校验 planned_tier 取值（仅五档或 null）
    for li in layout_items:
        pt = li.get("planned_tier")
        if pt is not None and pt not in _PLANNABLE_TIERS:
            raise ValueError(f"规划档位仅允许 搏/冲/稳/保/垫/null，得到 {pt}")
    # 校验 sort_order 连续且覆盖全部项
    item_ids = [li["item_id"] for li in layout_items]
    orders = sorted(li["sort_order"] for li in layout_items)
    if orders and (orders[0] != 0 or orders != list(range(len(orders)))):
        raise ValueError("sort_order 必须从0开始连续")
    existing = session.exec(
        select(UserVolunteerItemRow).where(UserVolunteerItemRow.group_id == group_row.id)
    ).all()
    existing_ids = {e.id for e in existing}
    if set(item_ids) != existing_ids:
        raise ValueError("layout 必须覆盖志愿组全部项")

    # 单事务批量更新
    by_id = {e.id: e for e in existing}
    for li in layout_items:
        item = by_id[li["item_id"]]
        item.planned_tier = li.get("planned_tier")
        item.sort_order = li["sort_order"]
        session.add(item)
    group_row.version += 1
    group_row.manually_reordered = True
    group_row.updated_at = _now()
    session.add(group_row)
    session.commit()
    session.refresh(group_row)
    return _group_to_domain(session, group_row, recompute=True)


def update_planned_tier(
    session: Session, group_row: UserVolunteerGroupRow, item_id: int,
    planned_tier: str | None, expected_version: int,
) -> UserVolunteerGroup:
    """菜单内单改规划档位（乐观锁）。planned_tier=null 恢复用算法档位。"""
    if group_row.version != expected_version:
        raise VolunteerConflictError(
            "志愿组已在其他页面更新", _group_to_domain(session, group_row)
        )
    if planned_tier is not None and planned_tier not in _PLANNABLE_TIERS:
        raise ValueError(f"规划档位仅允许 搏/冲/稳/保/垫/null，得到 {planned_tier}")
    item = session.exec(
        select(UserVolunteerItemRow).where(
            UserVolunteerItemRow.id == item_id,
            UserVolunteerItemRow.group_id == group_row.id,
        )
    ).first()
    if not item:
        raise ValueError("志愿项不存在")
    item.planned_tier = planned_tier
    session.add(item)
    group_row.version += 1
    group_row.updated_at = _now()
    session.add(group_row)
    session.commit()
    session.refresh(group_row)
    return _group_to_domain(session, group_row, recompute=True)


def delete_item(
    session: Session, group_row: UserVolunteerGroupRow, item_id: int, expected_version: int,
) -> UserVolunteerGroup:
    """删除单个志愿 + 重排 sort_order 连续 + version+1。"""
    if group_row.version != expected_version:
        raise VolunteerConflictError(
            "志愿组已在其他页面更新", _group_to_domain(session, group_row)
        )
    item = session.exec(
        select(UserVolunteerItemRow).where(
            UserVolunteerItemRow.id == item_id,
            UserVolunteerItemRow.group_id == group_row.id,
        )
    ).first()
    if not item:
        raise ValueError("志愿项不存在")
    deleted_order = item.sort_order
    session.delete(item)
    # 重排：deleted_order 之后的项 -1
    from sqlmodel import text
    session.exec(text(
        "UPDATE user_volunteer_items SET sort_order = sort_order - 1 "
        "WHERE group_id = :gid AND sort_order > :fo"
    ), params={"gid": group_row.id, "fo": deleted_order})
    group_row.version += 1
    group_row.updated_at = _now()
    session.add(group_row)
    session.commit()
    session.refresh(group_row)
    return _group_to_domain(session, group_row, recompute=True)


def clear_group(
    session: Session, group_row: UserVolunteerGroupRow, expected_version: int,
) -> UserVolunteerGroup:
    """清空全部志愿（单条 SQL 删全组 items，事务化）+ version+1。"""
    if group_row.version != expected_version:
        raise VolunteerConflictError(
            "志愿组已在其他页面更新", _group_to_domain(session, group_row)
        )
    from sqlmodel import text
    session.exec(text("DELETE FROM user_volunteer_items WHERE group_id = :gid"),
                 params={"gid": group_row.id})
    group_row.version += 1
    group_row.manually_reordered = False
    group_row.updated_at = _now()
    session.add(group_row)
    session.commit()
    session.refresh(group_row)
    return _group_to_domain(session, group_row, recompute=True)


def _compute_stats(items: list[UserVolunteerItem]) -> VolunteerStats:
    """档位/地域/性质统计 + 温和结构提示（非官方，可配置）。"""
    by_eff: dict[str, int] = {}
    by_algo: dict[str, int] = {}
    local = public = private = 0
    for it in items:
        by_eff[it.effective_tier] = by_eff.get(it.effective_tier, 0) + 1
        by_algo[it.latest_algorithm_tier] = by_algo.get(it.latest_algorithm_tier, 0) + 1
        if it.is_henan_local:
            local += 1
        else:
            pass
        if it.school_ownership == "公办":
            public += 1
        elif it.school_ownership in ("民办", "独立学院"):
            private += 1
    out_of_province = len(items) - local

    hints: list[StructureHint] = []
    # 温和结构提示（标注非官方，阈值可配）
    n = len(items)
    if n > 0:
        chong_like = by_eff.get("冲", 0) + by_eff.get("搏", 0)
        if n >= 5 and chong_like / n > 0.6:
            hints.append(StructureHint(
                code="too_aggressive",
                message=f"冲/搏档占比 {chong_like}/{n}（{(chong_like/n*100):.0f}%）偏高，建议适当增加保/垫档兜底（参考提示，非官方要求）",
                severity="warning",
            ))
        bao_dian = by_eff.get("保", 0) + by_eff.get("垫", 0)
        if n >= 5 and bao_dian < 2:
            hints.append(StructureHint(
                code="insufficient_safety",
                message=f"保/垫档仅 {bao_dian} 个，兜底偏少，建议补充（参考提示，非官方要求）",
                severity="warning",
            ))

    return VolunteerStats(
        total=n, by_effective_tier=by_eff, by_algorithm_tier=by_algo,
        local_count=local, out_of_province_count=out_of_province,
        public_count=public, private_count=private,
        structure_hints=hints,
    )
