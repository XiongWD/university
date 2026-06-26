from app.engine.batch_line import decide_batch_position


def test_above_undergrad_line():
    d = decide_batch_position(score=480, rank=73822, undergrad_line=471, junior_college_line=180)
    assert d.batch_position == "above_undergrad"
    assert d.distance_to_undergrad_line == 9


def test_below_undergrad_line_requires_risk_note():
    d = decide_batch_position(score=460, rank=91753, undergrad_line=471, junior_college_line=180)
    assert d.batch_position == "below_undergrad"
    assert "本科仅可作为冲刺" in d.recommendation_policy_note


def test_junior_college_only_when_far_below_undergrad():
    d = decide_batch_position(score=350, rank=180000, undergrad_line=471, junior_college_line=180)
    assert d.batch_position == "junior_college_only"
