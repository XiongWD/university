import yaml
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


def _boot_client(tmp_path_factory, name: str) -> TestClient:
    tmp_db = tmp_path_factory.mktemp(name) / f"{name}.db"
    import app.db as db_module

    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as session:
        if is_db_empty(session):
            load_all_seeds(settings.seed_dir, session)
    return TestClient(app)


def test_provenance_survives_full_chain(tmp_path_factory):
    with _boot_client(tmp_path_factory, "prov_base") as client:
        seed = yaml.safe_load(
            (settings.seed_dir / "careers" / "careers.yaml").read_text(encoding="utf-8")
        )[0]
        body = client.get("/api/v1/careers").json()
        match = next(career for career in body if career["name"] == seed["name"])
        assert match["source"] == seed["source"]
        assert match["confidence"] == seed["confidence"]
        assert match["as_of"]

        city = client.get("/api/v1/cities").json()[0]
        assert city["source"]
        assert city["confidence"] is not None

        university = client.get("/api/v1/universities").json()[0]
        assert university["source"]


def test_low_confidence_hand_edited_seeds_flagged(tmp_path_factory):
    with _boot_client(tmp_path_factory, "prov_low_conf") as client:
        for career in client.get("/api/v1/careers").json():
            assert career["confidence"] <= 0.6
            assert career.get("note")


def test_provincial_control_line_provenance(tmp_path_factory):
    with _boot_client(tmp_path_factory, "prov_control") as client:
        body = client.get(
            "/api/v1/provincial/control-line?province=河南&year=2026&track=历史类"
        ).json()
    assert body, "河南 2026 历史类省控线应存在"
    control_line = body[0]
    assert control_line["batches"]["undergrad_batch"] == 459
    assert control_line["source"] == "河南省教育考试院2026(教育在线核实)"
    assert control_line["confidence"] >= 0.95


def test_score_rank_provenance_full_chain(tmp_path_factory):
    with _boot_client(tmp_path_factory, "prov_chain") as client:
        body = client.get(
            "/api/v1/provincial/score-rank/rank"
            "?province=河南&year=2024&track=历史类&score=600"
        ).json()
    assert body["rank"] == 9500
    assert body["source"] == "河南省教育考试院2024(OCR自阳光高考图片版,累计单调清洗)"
    assert body["confidence"] == 0.9
