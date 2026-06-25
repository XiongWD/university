from datetime import date

import pytest
from pydantic import ValidationError

from app.models.student import StudentProfile, RiskPreference


def _kw(**over):
    base = dict(
        province="河南",
        total_score=450,
        subject_scores={"数学": 120, "英语": 75, "理综": 200},
        minor_language=None,
        family_resources=dict(
            has_govt_resource=False, has_medical_resource=False,
            has_education_resource=True, has_finance_resource=False,
            has_law_resource=False, has_business_resource=False,
        ),
        gender="男",
        interests=["语言"],
        strengths=["外语"],
        risk_preference=RiskPreference.BALANCED,
        source="手编2024",
        as_of=date(2024, 6, 1),
        confidence=0.4,
        note="待爬虫校准",
    )
    base.update(over)
    return base


def test_student_legal_traditional():
    s = StudentProfile(**_kw())
    assert s.total_score == 450
    assert s.family_resources.has_education_resource is True
    assert s.source == "手编2024"


def test_student_new_gaokao_subjects():
    s = StudentProfile(**_kw(subject_scores={
        "语文": 100, "数学": 110, "英语": 90,
        "物理": 80, "化学": 75, "生物": 70,
    }))
    assert len(s.subject_scores) == 6


def test_missing_required_rejected():
    bad = _kw()
    bad.pop("province")
    with pytest.raises(ValidationError):
        StudentProfile(**bad)


def test_bad_risk_preference_rejected():
    with pytest.raises(ValidationError):
        StudentProfile(**_kw(risk_preference="unknown"))


def test_minor_language_optional():
    s = StudentProfile(**_kw(minor_language={"lang": "日语", "level": "N2"}))
    assert s.minor_language.level == "N2"
