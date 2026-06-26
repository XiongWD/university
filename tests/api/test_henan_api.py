from fastapi.testclient import TestClient

from app.api.main import app


def test_henan_options_returns_schools():
    client = TestClient(app)
    r = client.get("/api/v1/henan/options")
    assert r.status_code == 200
    body = r.json()
    assert "schools" in body
    assert any(s["name"] == "郑州大学" for s in body["schools"])
    assert "majors" in body
    assert "groups" in body


def test_target_evaluation_returns_not_recommended_for_unreachable_school():
    client = TestClient(app)
    response = client.post(
        "/api/v1/henan/target-evaluation",
        json={
            "score": 480,
            "rank": 85000,
            "track": "历史类",
            "source_province": "河南",
            "target_school": "郑州大学",
            "target_majors": [],
            "target_group": None,
        },
    )

    assert response.status_code == 200
    body = response.json()
    # 当前 seed 计划数待核验/无历史位次 → 无可达冲稳保 → 院校级不推荐
    assert body["overall_bucket"] == "不推荐"
    assert body["items"] == []


def test_target_evaluation_rejects_non_henan_source_province():
    client = TestClient(app)
    response = client.post(
        "/api/v1/henan/target-evaluation",
        json={
            "score": 600,
            "rank": 20000,
            "track": "历史类",
            "source_province": "山东",
            "target_school": "郑州大学",
            "target_majors": [],
            "target_group": None,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overall_bucket"] == "不推荐"
    assert "河南" in body["reasons"][0]


def test_target_evaluation_uses_candidate_generator(monkeypatch):
    """目标评估复用 build_henan_candidates：mock 候选返回稳时按专业组显示稳。"""
    from app.api.routers import henan

    def fake_candidates(profile):
        return [{
            "school_name": "测试大学",
            "major_name": "法学",
            "major_group_code": "101",
            "major_group_name": "历史组",
            "bucket": "稳",
            "qualified": True,
            "blocked_reasons": [],
        }]

    monkeypatch.setattr(henan, "build_henan_candidates", fake_candidates)
    client = TestClient(app)
    r = client.post("/api/v1/henan/target-evaluation", json={
        "score": 600,
        "rank": 12000,
        "track": "历史类",
        "source_province": "河南",
        "target_school": "测试大学",
        "target_majors": [],
        "target_group": None,
    })
    body = r.json()
    assert body["overall_bucket"] == "可评估"
    assert body["items"][0]["bucket"] == "稳"
