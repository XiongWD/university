from app.engine.risk_buckets import classify_rank_gap


def test_balanced_bucket_near_baseline_is_match():
    assert classify_rank_gap(student_rank=50000, baseline_rank=51000, risk_preference="中") == "稳"


def test_aggressive_allows_wider_reach():
    assert classify_rank_gap(student_rank=56000, baseline_rank=50000, risk_preference="冲") == "偏冲"


def test_safe_preference_demotes_weak_reach():
    assert classify_rank_gap(student_rank=56000, baseline_rank=50000, risk_preference="稳") == "不推荐"


def test_strong_rank_is_safe():
    assert classify_rank_gap(student_rank=40000, baseline_rank=50000, risk_preference="中") == "保"
