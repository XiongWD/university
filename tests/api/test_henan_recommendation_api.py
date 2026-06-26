from fastapi.testclient import TestClient

from app.api.main import app


def test_henan_recommendation_returns_data_readiness_and_buckets():
    client = TestClient(app)
    response = client.post("/api/v1/henan/recommendation", json={
        "score": 540,
        "rank": 45000,
        "track": "历史类",
        "source_province": "河南",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
        "strategy": "自动",
    })
    assert response.status_code == 200
    body = response.json()
    assert "data_ready" in body
    assert "buckets" in body
    assert set(body["buckets"].keys()) == {"冲", "稳", "保", "不推荐", "需人工复核"}
    assert "coverage" in body


def test_henan_recommendation_non_henan_blocked():
    client = TestClient(app)
    response = client.post("/api/v1/henan/recommendation", json={
        "score": 540,
        "rank": 45000,
        "track": "历史类",
        "source_province": "山东",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["data_ready"] is False
