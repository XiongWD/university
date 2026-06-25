"""志愿填报引擎 API 端到端测试。"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("vol_api") / "vol_api.db"
    import app.db as db_module
    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
    with TestClient(app) as c:
        yield c


# ===== POST /volunteer/recommend =====
def test_recommend_returns_three_buckets(client):
    """推荐端点返回冲稳保三档结构。"""
    r = client.post("/api/v1/volunteer/recommend", json={
        "province": "河南", "total_score": 543, "track": "理科", "data_year": 2024,
    })
    assert r.status_code == 200
    body = r.json()
    assert "sprint" in body and "stable" in body and "safe" in body
    assert body["track"] == "理科"
    assert body["data_year"] == 2024
    assert "2024" in body["source_note"]


def test_recommend_contains_real_school(client):
    """543分(河师大附近)考生，应能匹配到河南农业大学(保)。"""
    r = client.post("/api/v1/volunteer/recommend", json={
        "province": "河南", "total_score": 543, "track": "理科", "data_year": 2024,
    })
    body = r.json()
    all_schools = [s["school"] for s in body["sprint"] + body["stable"] + body["safe"]]
    assert "河南农业大学" in all_schools


def test_recommend_risk_preference_changes_quotas(client):
    """不同风险偏好返回的各档数量不同。"""
    body_safe = client.post("/api/v1/volunteer/recommend", json={
        "province": "河南", "total_score": 543, "track": "理科",
        "data_year": 2024, "risk_preference": "稳",
    }).json()
    body_aggr = client.post("/api/v1/volunteer/recommend", json={
        "province": "河南", "total_score": 543, "track": "理科",
        "data_year": 2024, "risk_preference": "冲",
    }).json()
    # 稳型考生保档配额(5) >= 冲型考生保档配额(2)
    assert len(body_safe["safe"]) >= len(body_aggr["safe"])


def test_recommend_empty_when_no_data(client):
    """无录取数据的省份/年份 → 返回空三档（不报错）。"""
    r = client.post("/api/v1/volunteer/recommend", json={
        "province": "不存在省", "total_score": 600, "track": "理科", "data_year": 2024,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["sprint"] == [] and body["stable"] == [] and body["safe"] == []


def test_recommend_suggestion_has_probability(client):
    """每条建议应含录取概率估算。"""
    r = client.post("/api/v1/volunteer/recommend", json={
        "province": "河南", "total_score": 543, "track": "理科", "data_year": 2024,
    })
    body = r.json()
    all_sug = body["sprint"] + body["stable"] + body["safe"]
    assert len(all_sug) > 0
    for s in all_sug:
        assert 0 <= s["probability"]["probability"] <= 1
        assert s["last_year_rank"] > 0


# ===== GET /volunteer/admissions =====
def test_admissions_filter_by_track(client):
    """按 track 过滤录取数据。"""
    r = client.get("/api/v1/volunteer/admissions", params={"province": "河南", "track": "理科"})
    assert r.status_code == 200
    for a in r.json():
        assert a["track"] == "理科"


def test_admissions_filter_by_score_range(client):
    """按分数范围筛选（如 530-600 分可报学校）。"""
    r = client.get("/api/v1/volunteer/admissions", params={
        "province": "河南", "track": "理科", "year": 2024,
        "min_score": 530, "max_score": 600,
    })
    assert r.status_code == 200
    for a in r.json():
        assert 530 <= a["min_score"] <= 600


def test_admissions_empty_ok(client):
    r = client.get("/api/v1/volunteer/admissions", params={"school": "不存在的学校"})
    assert r.status_code == 200
    assert r.json() == []
