from datetime import date

import pytest
from pydantic import ValidationError

from app.models.base import SourcedRecord, CostBand


def _valid_kwargs(**over):
    base = dict(
        source="贝壳租房2024",
        as_of=date(2024, 6, 1),
        confidence=0.5,
        note="待爬虫校准",
    )
    base.update(over)
    return base


def test_sourced_record_legal():
    rec = SourcedRecord(**_valid_kwargs())
    assert rec.source == "贝壳租房2024"
    assert rec.confidence == 0.5


def test_confidence_out_of_range_rejected():
    for bad in (-0.1, 1.1, 2.0):
        with pytest.raises(ValidationError):
            SourcedRecord(**_valid_kwargs(confidence=bad))


def test_confidence_boundary_accepted():
    assert SourcedRecord(**_valid_kwargs(confidence=0.0)).confidence == 0.0
    assert SourcedRecord(**_valid_kwargs(confidence=1.0)).confidence == 1.0


def test_cost_band_legal():
    b = CostBand(low=1800, high=2600)
    assert b.low <= b.high


def test_cost_band_inverted_rejected():
    with pytest.raises(ValidationError):
        CostBand(low=3000, high=2000)


def test_cost_band_equal_allowed():
    b = CostBand(low=2000, high=2000)
    assert b.low == b.high
