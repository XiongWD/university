"""河南志愿推目标评估引擎（design §9）。

复用首页专业推荐的同一套冲稳保逻辑，不使用更宽松的规则。
按目标院校/专业/专业组筛选候选，区分「能否投进专业组」与「能否录到目标专业」。
任何专业/专业组都不达冲稳保条件时，输出院校级「不推荐」，不给虚假可尝试结论。

注意：本模块是河南志愿推新链路（/henan/target-evaluation），与旧
app/engine/target_evaluation.py（/target/evaluate）并行，旧链路保留。
"""
from __future__ import annotations

# 可达档位（design §8.3）：只有这三个才算"可评估"
REACHABLE_BUCKETS = {"冲", "稳", "保"}


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

    # 可达：资格通过且档位为冲/稳/保
    reachable = [
        item
        for item in scoped
        if item.get("qualified", True) and item.get("bucket") in REACHABLE_BUCKETS
    ]

    # 无任何可达专业/专业组 → 院校级不推荐（design §9.3）
    if not reachable:
        reasons = ["没有达到冲稳保条件的专业或专业组"]
        blocked = [reason for item in scoped for reason in item.get("blocked_reasons", [])]
        reasons.extend(sorted(set(blocked)))
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
