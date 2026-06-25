from datetime import date

import pytest
from pydantic import ValidationError

from app.models.admission import AdmissionRecord, Batch


def _kw(**over):
    base = dict(
        school="郑州大学",
        major="计算机科学与技术",
        province="河南",
        year=2023,
        track="理科",
        min_score=585,
        min_rank=32000,
        avg_score=600,
        batch=Batch.FIRST,
        source="省考试院2023",
        as_of=date(2023, 7, 1),
        confidence=0.95,
        note=None,
    )
    base.update(over)
    return base


def test_admission_legal():
    a = AdmissionRecord(**_kw())
    assert a.batch == Batch.FIRST
    assert a.track == "理科"


def test_missing_province_rejected():
    bad = _kw()
    bad.pop("province")
    with pytest.raises(ValidationError):
        AdmissionRecord(**bad)


def test_missing_year_rejected():
    bad = _kw()
    bad.pop("year")
    with pytest.raises(ValidationError):
        AdmissionRecord(**bad)


def test_new_gaokao_track_free_string():
    a = AdmissionRecord(**_kw(track="物理+化学+生物"))
    assert "物理" in a.track
