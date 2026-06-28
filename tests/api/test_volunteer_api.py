from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


def _boot_client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("vol_api") / "vol_api.db"
    import app.db as db_module

    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as session:
        if is_db_empty(session):
            load_all_seeds(settings.seed_dir, session)
    return TestClient(app)


def test_recommend_returns_three_buckets(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.post(
            "/api/v1/volunteer/recommend",
            json={
                "province": "河南",
                "total_score": 543,
                "track": "历史类",
                "data_year": 2026,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert "sprint" in body and "stable" in body and "safe" in body
    assert body["track"] == "历史类"
    assert body["data_year"] == 2025
    assert "2025" in body["source_note"]


def test_recommend_contains_real_school(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.post(
            "/api/v1/volunteer/recommend",
            json={
                "province": "河南",
                "total_score": 543,
                "track": "历史类",
                "data_year": 2026,
            },
        )
    body = response.json()
    all_schools = [s["school"] for s in body["sprint"] + body["stable"] + body["safe"]]
    assert "信阳农林学院" in all_schools


def test_recommend_risk_preference_changes_quotas(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        body_safe = client.post(
            "/api/v1/volunteer/recommend",
            json={
                "province": "河南",
                "total_score": 543,
                "track": "历史类",
                "data_year": 2026,
                "risk_preference": "稳",
            },
        ).json()
        body_aggressive = client.post(
            "/api/v1/volunteer/recommend",
            json={
                "province": "河南",
                "total_score": 543,
                "track": "历史类",
                "data_year": 2026,
                "risk_preference": "冲",
            },
        ).json()
    assert len(body_safe["safe"]) >= len(body_aggressive["safe"])


def test_recommend_empty_when_no_data(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.post(
            "/api/v1/volunteer/recommend",
            json={
                "province": "不存在省",
                "total_score": 600,
                "track": "历史类",
                "data_year": 2026,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["sprint"] == [] and body["stable"] == [] and body["safe"] == []


def test_recommend_suggestion_has_probability(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.post(
            "/api/v1/volunteer/recommend",
            json={
                "province": "河南",
                "total_score": 543,
                "track": "历史类",
                "data_year": 2026,
            },
        )
    body = response.json()
    all_suggestions = body["sprint"] + body["stable"] + body["safe"]
    assert len(all_suggestions) > 0
    for suggestion in all_suggestions:
        assert 0 <= suggestion["probability"]["probability"] <= 1
        assert suggestion["last_year_rank"] > 0


def test_admissions_filter_by_track(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.get(
            "/api/v1/volunteer/admissions",
            params={"province": "河南", "track": "历史类"},
        )
    assert response.status_code == 200
    for admission in response.json():
        assert admission["track"] == "历史类"


def test_admissions_filter_by_score_range(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.get(
            "/api/v1/volunteer/admissions",
            params={
                "province": "河南",
                "track": "历史类",
                "year": 2025,
                "min_score": 530,
                "max_score": 600,
            },
        )
    assert response.status_code == 200
    for admission in response.json():
        assert 530 <= admission["min_score"] <= 600


def test_admissions_empty_ok(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.get(
            "/api/v1/volunteer/admissions", params={"school": "不存在的学校"}
        )
    assert response.status_code == 200
    assert response.json() == []


def test_life_trajectory_deprecated_still_runs(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.post(
            "/api/v1/volunteer/life-trajectory",
            json={
                "province": "河南",
                "total_score": 543,
                "track": "历史类",
                "data_year": 2026,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert "sprint" in body and "stable" in body and "safe" in body
    for bucket in ("sprint", "stable", "safe"):
        for item in body[bucket]:
            assert item["payback"] is None
    assert "deprecated" in body["source_note"]


def test_life_paths_deprecated_still_runs(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.post(
            "/api/v1/volunteer/life-paths",
            json={
                "total_score": 543,
                "primary_subject": "历史",
                "math_score": 75,
                "exam_foreign_language": "日语",
                "foreign_language_score": 120,
                "english_actual_level": "basic",
                "elective_subjects": ["政治", "地理"],
                "family_annual_income": 80000,
                "family_savings": 20000,
                "max_annual_education_budget": 25000,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert "paths" in body
    assert "notes" in body
    assert any("deprecated" in note for note in body["notes"])
