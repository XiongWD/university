from fastapi.testclient import TestClient

from app.api.main import app


def test_henan_recommendation_returns_data_readiness_and_buckets():
    client = TestClient(app)
    response = client.post("/api/v1/henan/recommendation", json={
        "score": 600,
        "rank": None,
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
    assert "pilot_ready" in body
    assert "production_ready" in body
    assert "coverage_status" in body
    assert body["coverage_status"] in {"not_ready", "pilot_ready", "production_ready"}
    assert "buckets" in body
    assert set(body["buckets"].keys()) == {"搏", "冲", "稳", "保", "垫", "不推荐", "需人工复核"}
    assert "coverage" in body
    assert "data_evidence" in body
    assert "coverage_notes" in body
    assert isinstance(body["coverage_notes"], list)
    assert body["data_evidence"]["scope"]["province"] == "河南"
    assert body["data_evidence"]["readiness"]["official_catalog_available"] is False
    assert body["pilot_ready"] is True
    assert body["production_ready"] is False
    assert body["data_ready"] is True
    assert body["coverage_status"] == "pilot_ready"
    assert any("官方全量专业目录" in note for note in body["coverage_notes"])


def test_henan_recommendation_non_henan_blocked():
    client = TestClient(app)
    response = client.post("/api/v1/henan/recommendation", json={
        "score": 600,
        "rank": None,
        "track": "历史类",
        "source_province": "山东",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["data_ready"] is False
    assert body["pilot_ready"] is False
    assert body["production_ready"] is False
    assert body["data_evidence"]["scope"]["track"] == "历史类"


def test_henan_recommendation_non_history_track_blocked():
    client = TestClient(app)
    response = client.post("/api/v1/henan/recommendation", json={
        "score": 600,
        "rank": None,
        "track": "物理类",
        "source_province": "河南",
        "primary_subject": "物理",
        "elective_subjects": ["化学", "生物"],
        "exam_foreign_language": "英语",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["data_ready"] is False
    assert body["pilot_ready"] is False
    assert body["production_ready"] is False
    assert any("历史类" in err for err in body["readiness_errors"])
    assert "missing_official_catalog_reason" in body["data_evidence"]["source_gaps"]


def test_henan_recommendation_derives_rank_from_score_when_rank_missing():
    client = TestClient(app)
    response = client.post("/api/v1/henan/recommendation", json={
        "score": 540,
        "rank": None,
        "track": "历史类",
        "source_province": "河南",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
        "subject_scores_detail": {"数学": 80, "外语": 110},
        "strategy": "自动",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["data_ready"] is True
    assert sum(len(v) for v in body["buckets"].values()) > 0
    assert sum(len(body["buckets"][k]) for k in ("冲", "稳", "保")) > 0
    reachable = next(item for bucket in ("冲", "稳", "保") for item in body["buckets"][bucket] if body["buckets"][bucket])
    assert "data_evidence" in reachable
    assert "source_trace" in reachable["data_evidence"]
    assert reachable["data_evidence"]["official_gap"]["official_catalog_available"] is False


def test_henan_recommendation_separates_missing_language_data_and_same_language_gap():
    client = TestClient(app)
    response = client.post("/api/v1/henan/recommendation", json={
        "score": 600,
        "rank": None,
        "track": "历史类",
        "source_province": "河南",
        "primary_subject": "历史",
        "elective_subjects": ["政治", "地理"],
        "exam_foreign_language": "日语",
        "strategy": "自动",
        "prefer_same_language_major": True,
    })
    assert response.status_code == 200
    body = response.json()
    summary = body["language_restriction_summary"]
    assert summary is not None
    assert "missing_data_count" in summary
    assert "same_language_major_group_count" in summary
    assert "reachable_same_language_major_group_count" in summary
    assert summary["same_language_major_group_count"] >= summary["reachable_same_language_major_group_count"]
    if summary["reachable_same_language_major_group_count"] == 0:
        assert "当前分数条件下未检出可达的日语专业组" in summary["note"]
