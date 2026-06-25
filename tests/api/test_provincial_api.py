import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("prov_api") / "prov_api.db"
    import app.db as db_module
    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
    with TestClient(app) as c:
        yield c


def test_control_line_has_source(client):
    r = client.get("/api/v1/provincial/control-line?province=河南&year=2024&track=理科")
    assert r.status_code == 200
    body = r.json()
    assert body[0]["batches"]["first_batch"] == 511
    assert body[0]["source"] and body[0]["confidence"] >= 0.8


def test_control_line_empty_ok(client):
    r = client.get("/api/v1/provincial/control-line?province=不存在&year=1900&track=x")
    assert r.status_code == 200
    assert r.json() == []


def test_score_rank_list(client):
    r = client.get("/api/v1/provincial/score-rank?province=河南&year=2024&track=理科")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


def test_score_to_rank_endpoint(client):
    r = client.get(
        "/api/v1/provincial/score-rank/rank"
        "?province=河南&year=2024&track=理科&score=690"
    )
    assert r.status_code == 200
    body = r.json()
    if body.get("rank") is not None:
        assert body["rank"] == 215
    assert body.get("source") == "Gaokao-score-distribution数据集"


def test_rank_to_score_endpoint(client):
    r = client.get(
        "/api/v1/provincial/score-rank/score"
        "?province=河南&year=2024&track=理科&rank=215"
    )
    assert r.status_code == 200
    body = r.json()
    if body.get("score") is not None:
        assert body["score"] == 690
