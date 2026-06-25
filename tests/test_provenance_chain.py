"""来源追溯全链路集成测试。

验证 YAML 种子 → Domain → DB → API 响应来源字段不丢失。
"""

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("prov") / "prov_test.db"
    import app.db as db_module
    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
    with TestClient(app) as c:
        yield c


def test_provenance_survives_full_chain(client):
    seed = yaml.safe_load(
        (settings.seed_dir / "careers" / "careers.yaml").read_text(encoding="utf-8")
    )[0]
    body = client.get("/api/v1/careers").json()
    match = next(c for c in body if c["name"] == seed["name"])
    assert match["source"] == seed["source"]
    assert match["confidence"] == seed["confidence"]
    assert match["as_of"]

    # cities 端点必须带来源
    c2 = client.get("/api/v1/cities").json()[0]
    assert c2["source"]
    assert c2["confidence"] is not None

    # universities
    u = client.get("/api/v1/universities").json()[0]
    assert u["source"]


def test_low_confidence_hand_edited_seeds_flagged(client):
    for c in client.get("/api/v1/careers").json():
        assert c["confidence"] <= 0.6
        assert c.get("note") and "待爬虫校准" in c["note"]
