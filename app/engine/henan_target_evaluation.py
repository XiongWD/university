"""河南志愿推目标评估引擎（design §9）。

复用首页专业推荐的同一套冲稳保逻辑，不使用更宽松的规则。
按目标院校/专业/专业组筛选候选，区分「能否投进专业组」与「能否录到目标专业」。
任何专业/专业组都不达冲稳保条件时，输出院校级「不推荐」，不给虚假可尝试结论。

注意：本模块是河南志愿推新链路（/henan/target-evaluation），与旧
app/engine/target_evaluation.py（/target/evaluate）并行，旧链路保留。
"""
from __future__ import annotations

# 可达档位（design §8.3）：只有这三个才算"可评估"
REACHABLE_BUCKETS = {"搏", "冲", "稳", "保", "垫"}


def _classify_unreachable(item: dict) -> str:
    """把单个不推荐候选归因到一类：hard_block（资格阻断）/ rank_gap（位次不达标）/ data_missing（数据不足）。

    依据 build_henan_candidates 的输出：qualified=False 即资格层阻断；qualified=True 但
    bucket=不推荐 是位次差比超阈值；bucket=需人工复核 是缺 verified 历史/计划基线。
    """
    if not item.get("qualified", True):
        return "hard_block"
    bucket = item.get("bucket")
    if bucket == "需人工复核":
        return "data_missing"
    return "rank_gap"


def _summarize_unreachable_reasons(profile: dict, scoped: list[dict]) -> list[str]:
    """汇总院校级不推荐的原因（design §9.3），区分资格阻断与位次/数据不达标。

    与旧逻辑的区别：旧版只聚合 blocked_reasons，会丢失「位次不够」这个最常见主因，
    导致用户误以为只是语种/选科问题。新版按分类汇总，并把位次差比主因前置。
    """
    reasons: list[str] = ["没有达到冲稳保条件的专业或专业组"]

    # 按原因分类统计专业组数
    by_kind: dict[str, list[dict]] = {"hard_block": [], "rank_gap": [], "data_missing": []}
    for item in scoped:
        by_kind[_classify_unreachable(item)].append(item)

    # 主因优先：位次不达标（最常见，且多数专业组会落在这里）
    student_rank = profile.get("rank")
    rank_gap_items = by_kind["rank_gap"]
    if rank_gap_items:
        # 取该校参考位次最低（最好进）的那个组作为"最接近"参照
        best = min(
            rank_gap_items,
            key=lambda it: (it.get("bucket_detail") or {}).get("adjusted_min_rank") or float("inf"),
        )
        detail = best.get("bucket_detail") or {}
        adj = detail.get("adjusted_min_rank")
        ratio = detail.get("rank_gap_ratio")
        group_desc = f"{best.get('major_group_code', '?')}/{best.get('major_name', '?')}"
        if adj and student_rank:
            base = f"位次差距过大：考生位次 {student_rank}，而 {group_desc} 参考录取位次约 {int(adj)}"
            if ratio is not None:
                base += f"（位次差比 {ratio * 100:+.1f}%，超过 15% 不推荐阈值）"
            base += f"；该校共有 {len(rank_gap_items)} 个专业组因分数暂不够"
            reasons.append(base)
        else:
            reasons.append(f"位次差距过大：{group_desc} 当前分数暂达不到参考录取位次（共 {len(rank_gap_items)} 个专业组）")

    # 资格硬阻断：去重列出具体原因（语种/选科/单科/体检/专项）
    hard_items = by_kind["hard_block"]
    if hard_items:
        seen: set[str] = set()
        ordered: list[str] = []
        for reason in (r for it in hard_items for r in (it.get("blocked_reasons") or [])):
            if reason not in seen:
                seen.add(reason)
                ordered.append(reason)
        prefix = f"资格不符（{len(hard_items)} 个专业组）：" if len(hard_items) > 1 else "资格不符："
        reasons.append(prefix + "；".join(ordered))

    # 数据不足：缺 verified 历史/计划，无法判定冲稳保
    missing_items = by_kind["data_missing"]
    if missing_items:
        sample_missing = (missing_items[0].get("missing_data_items") or ["未提供"])
        reasons.append(
            f"数据待核验（{len(missing_items)} 个专业组）：{sample_missing[0]}，暂无法判定冲稳保"
        )

    return reasons


def evaluate_target_school(
    profile: dict,
    target_school: str,
    target_majors: list[str],
    target_group: str | None,
    candidates: list[dict],
) -> dict:
    """评估目标院校的可报性与冲稳保档位。

    candidates 必须是首页推荐（build_henan_candidates）已应用资格过滤与分桶的结果，
    本函数只做按校/专业/专业组的筛选与可达性判定，不重新放宽规则。
    """
    # 仅支持河南（design §1 范围）
    if profile.get("source_province") not in (None, "河南"):
        return {
            "school_name": target_school,
            "overall_bucket": "不推荐",
            "items": [],
            "reasons": ["河南志愿推仅支持河南考生"],
        }

    # 按目标院校筛选
    scoped = [item for item in candidates if item.get("school_name") == target_school]
    # 指定专业时只评估这些专业及其所属专业组
    if target_majors:
        scoped = [item for item in scoped if item.get("major_name") in target_majors]
    # 指定专业组时优先按该组评估
    if target_group:
        scoped = [item for item in scoped if item.get("major_group_code") == target_group]

    # 可达：资格通过且档位为搏/冲/稳/保/垫（位次差不导致不可达，仅影响档位）
    reachable = [
        item
        for item in scoped
        if item.get("qualified", True) and item.get("bucket") in REACHABLE_BUCKETS
    ]

    # 无任何可达专业/专业组 → 院校级不推荐（design §9.3）
    if not reachable:
        reasons = _summarize_unreachable_reasons(profile, scoped)
        return {
            "school_name": target_school,
            "overall_bucket": "不推荐",
            "items": [],
            "reasons": reasons,
        }

    return {
        "school_name": target_school,
        "overall_bucket": "可评估",
        "items": reachable,
        "reasons": [],
    }
