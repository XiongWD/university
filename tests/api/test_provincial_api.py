from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


def _boot_client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("prov_api") / "prov_api.db"
    import app.db as db_module

    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as session:
        if is_db_empty(session):
            load_all_seeds(settings.seed_dir, session)
    return TestClient(app)


def test_control_line_has_source(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.get(
            "/api/v1/provincial/control-line?province=河南&year=2026&track=历史类"
        )
    assert response.status_code == 200
    body = response.json()
    assert body[0]["batches"]["undergrad_batch"] == 459
    assert body[0]["batches"]["junior_college"] == 179
    assert body[0]["source"] == "河南省教育考试院2026(教育在线核实)"
    assert body[0]["confidence"] >= 0.95


def test_control_line_empty_ok(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.get(
            "/api/v1/provincial/control-line?province=不存在&year=1900&track=x"
        )
    assert response.status_code == 200
    assert response.json() == []


def test_score_rank_list(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.get(
            "/api/v1/provincial/score-rank?province=河南&year=2026&track=历史类"
        )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0


def test_score_to_rank_endpoint(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.get(
            "/api/v1/provincial/score-rank/rank"
            "?province=河南&year=2024&track=历史类&score=600"
        )
    assert response.status_code == 200
    body = response.json()
    assert body["rank"] == 9500
    assert body["source"] == "河南省教育考试院2024(OCR自阳光高考图片版,累计单调清洗)"
    assert body["confidence"] == 0.9


def test_rank_to_score_endpoint(tmp_path_factory):
    with _boot_client(tmp_path_factory) as client:
        response = client.get(
            "/api/v1/provincial/score-rank/score"
            "?province=河南&year=2026&track=历史类&rank=9500"
        )
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 583
    assert body["source"] == "河南省教育考试院2026(OCR自官方PDF,5硬锚点校验)"
    assert body["confidence"] == 0.95
