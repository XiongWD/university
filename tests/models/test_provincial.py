from datetime import date

import pytest
from pydantic import ValidationError

from app.models.provincial import (
    BatchLines, ProvincialControlLine, ScoreRankTable, ScoreRankEntry,
)


def _src(**over):
    base = dict(source="省考试院2024", as_of=date(2024, 7, 1),
                confidence=0.9, note=None)
    base.update(over)
    return base


def test_henan_traditional_track():
    cl = ProvincialControlLine(
        province="河南", year=2024, track="理科",
        batches=BatchLines(first_batch=511, second_batch=396, junior_college=185),
        **_src(),
    )
    assert cl.batches.first_batch == 511
    assert cl.batches.undergrad_batch is None


def test_guangdong_new_gaokao_batches_optional():
    cl = ProvincialControlLine(
        province="广东", year=2024, track="物理类",
        batches=BatchLines(special_line=539, undergrad_batch=442),
        **_src(),
    )
    assert cl.batches.special_line == 539
    assert cl.batches.first_batch is None


def test_control_line_missing_province_rejected():
    with pytest.raises(ValidationError):
        ProvincialControlLine(
            year=2024, track="理科",
            batches=BatchLines(first_batch=511),
            **_src(),
        )


def test_control_line_missing_year_rejected():
    with pytest.raises(ValidationError):
        ProvincialControlLine(
            province="河南", track="理科",
            batches=BatchLines(first_batch=511),
            **_src(),
        )


def test_control_line_negative_score_rejected():
    with pytest.raises(ValidationError):
        BatchLines(first_batch=-1)


def test_score_rank_entry_non_negative():
    with pytest.raises(ValidationError):
        ScoreRankEntry(score=690, count_at=-1, cumulative_rank=215)
    with pytest.raises(ValidationError):
        ScoreRankEntry(score=690, count_at=22, cumulative_rank=-5)


def test_score_rank_entry_missing_field_rejected():
    with pytest.raises(ValidationError):
        ScoreRankEntry(score=690, cumulative_rank=215)


def test_score_rank_table_monotonic_ok():
    t = ScoreRankTable(
        province="河南", year=2024, track="理科",
        entries=[
            ScoreRankEntry(score=691, count_at=19, cumulative_rank=193),
            ScoreRankEntry(score=690, count_at=22, cumulative_rank=215),
            ScoreRankEntry(score=689, count_at=24, cumulative_rank=239),
        ],
        **_src(),
    )
    assert len(t.entries) == 3


def test_score_rank_table_monotonic_violation_rejected():
    with pytest.raises(ValidationError):
        ScoreRankTable(
            province="河南", year=2024, track="理科",
            entries=[
                ScoreRankEntry(score=700, count_at=5, cumulative_rank=500),
                ScoreRankEntry(score=690, count_at=22, cumulative_rank=300),
            ],
            **_src(),
        )
