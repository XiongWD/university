from app.engine.rank_query import score_to_rank, rank_to_score
from app.models.provincial import ScoreRankEntry


def _entries():
    return [
        ScoreRankEntry(score=691, count_at=19, cumulative_rank=193),
        ScoreRankEntry(score=690, count_at=22, cumulative_rank=215),
        ScoreRankEntry(score=689, count_at=24, cumulative_rank=239),
        ScoreRankEntry(score=688, count_at=35, cumulative_rank=274),
        ScoreRankEntry(score=687, count_at=30, cumulative_rank=304),
    ]


def test_score_to_rank_exact():
    assert score_to_rank(_entries(), 690) == 215


def test_score_to_rank_missing_returns_none():
    assert score_to_rank(_entries(), 700) is None


def test_score_to_rank_empty():
    assert score_to_rank([], 690) is None


def test_rank_to_score_exact():
    assert rank_to_score(_entries(), 215) == 690


def test_rank_to_score_nearest_match():
    assert rank_to_score(_entries(), 220) == 690


def test_rank_to_score_nearest_other_side():
    assert rank_to_score(_entries(), 230) == 689


def test_rank_to_score_empty():
    assert rank_to_score([], 100) is None
