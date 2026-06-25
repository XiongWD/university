"""位次法双向查询纯函数（基于一分一段表）。

- score_to_rank：精确匹配
- rank_to_score：就近匹配（cumulative_rank 与目标绝对差最小的 entry 的 score）
"""

from app.models.provincial import ScoreRankEntry


def score_to_rank(entries: list[ScoreRankEntry], score: int) -> int | None:
    """分数 → 累计位次（精确匹配，不存在返回 None）。"""
    for e in entries:
        if e.score == score:
            return e.cumulative_rank
    return None


def rank_to_score(entries: list[ScoreRankEntry], rank: int) -> int | None:
    """位次 → 分数（就近匹配）。空表返回 None。"""
    if not entries:
        return None
    best = min(entries, key=lambda e: abs(e.cumulative_rank - rank))
    return best.score
