from fastapi.testclient import TestClient

from app.api.main import app


def test_henan_options_returns_schools():
    client = TestClient(app)
    response = client.get("/api/v1/henan/options")
    assert response.status_code == 200
    body = response.json()
    assert "schools" in body
    assert any(s["name"] == "郑州大学" for s in body["schools"])
    assert "majors" in body
    assert "groups" in body
    assert "scope" in body
    assert body["scope"]["source_province"] == "河南"
    assert body["scope"]["track"] == "历史类"
    assert "coverage_status" in body
    assert "pilot_ready" in body
    assert "production_ready" in body
    assert "data_evidence" in body
    assert body["data_evidence"]["scope"]["batch"] == "本科批"
    assert body["pilot_ready"] is True
    assert body["production_ready"] is False
    assert body["coverage_status"] == "pilot_ready"
    assert any("官方全量专业目录" in note for note in body["coverage_notes"])
    assert all(g["track"] == "历史类" for g in body["groups"])


def test_target_evaluation_returns_not_recommended_for_unreachable_school():
    """位次差极大的院校：按新原则位次差不导致不可达，判「搏」档（高风险但可评估）。

    480分/位次85000 对郑州大学(位次~3000)：advantage≈-82000，录取希望渺茫，
    但用户有权看到这个信息（搏档+低概率），overall_bucket=可评估。
    资格不符（选科/语种）才判"不推荐"。
    """
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
    # 位次差极大（advantage≈-82000，超-20%R阈值）→ 归需人工复核/不推荐（匹配度过低）
    # 不再因位次差判"不推荐"（资格不符），但差太远也不判"搏"
    assert body["overall_bucket"] in {"不推荐", "需人工复核"}
    assert body["coverage_status"] in {"pilot_ready", "production_ready", "not_ready"}
    assert "pilot_ready" in body
    assert "production_ready" in body
    assert "data_evidence" in body


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
    assert body["pilot_ready"] is False
    assert body["production_ready"] is False
    assert body["data_evidence"]["readiness"]["official_catalog_available"] is False


def test_target_evaluation_rejects_non_history_track():
    client = TestClient(app)
    response = client.post(
        "/api/v1/henan/target-evaluation",
        json={
            "score": 600,
            "rank": 20000,
            "track": "物理类",
            "source_province": "河南",
            "target_school": "郑州大学",
            "target_majors": [],
            "target_group": None,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overall_bucket"] == "不推荐"
    assert any("历史类" in reason for reason in body["reasons"])
    assert body["pilot_ready"] is False
    assert body["production_ready"] is False
    assert body["data_evidence"]["scope"]["year"] == 2026


def test_target_evaluation_uses_candidate_generator(monkeypatch):
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
    response = client.post("/api/v1/henan/target-evaluation", json={
        "score": 600,
        "rank": 12000,
        "track": "历史类",
        "source_province": "河南",
        "target_school": "测试大学",
        "target_majors": [],
        "target_group": None,
    })
    body = response.json()
    assert body["overall_bucket"] == "可评估"
    assert body["items"][0]["bucket"] == "稳"
    assert body["items"][0]["major_group_code"] == "101"
    assert "data_evidence" in body


def test_target_evaluation_derives_rank_from_score_when_rank_missing():
    client = TestClient(app)
    response = client.post(
        "/api/v1/henan/target-evaluation",
        json={
            "score": 600,
            "rank": None,
            "track": "历史类",
            "source_province": "河南",
            "target_school": "福建师范大学",
            "target_majors": [],
            "target_group": None,
            "exam_foreign_language": "英语",
            "primary_subject": "历史",
            "elective_subjects": ["政治", "地理"],
            "subject_scores_detail": {"数学": 90, "外语": 130},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_bucket"] == "可评估"
    assert len(body["items"]) > 0
    assert body["coverage_status"] == "pilot_ready"
    assert "data_evidence" in body["items"][0]
