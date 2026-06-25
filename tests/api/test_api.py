"""API 端点测试。

用真实种子数据加载到临时 DB，override get_session_dep 指向临时 DB。
不依赖全局 data/llm_sim.db，避免污染。
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.db import init_db, get_engine
from app.loader.seed_loader import load_all_seeds, is_db_empty
from app.config import settings


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """加载真实种子到临时 DB，返回 TestClient。"""
    tmp_db = tmp_path_factory.mktemp("api") / "api_test.db"
    import app.db as db_module
    db_module._engine = None  # reset
    settings.db_path = tmp_db

    init_db()
    with Session(get_engine()) as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)

    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert "seed_loaded" in r.json()


def test_careers_list_has_source(client):
    r = client.get("/api/v1/careers")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 15
    assert items[0]["source"]
    assert "confidence" in items[0]


def test_career_detail(client):
    r = client.get("/api/v1/careers")
    cid = r.json()[0]["id"]
    r2 = client.get(f"/api/v1/careers/{cid}")
    assert r2.status_code == 200
    assert r2.json()["entry_salary"]["mid"]


def test_universities_tier_filter(client):
    r = client.get('/api/v1/universities?tier="985"')
    assert r.status_code == 200
    assert all(u["tier"] == "985" for u in r.json())


def test_insurance_compute(client):
    r = client.post("/api/v1/insurance/compute",
                    json={"salary": 9000, "city": "全国基准"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_labor_cost"] > 9000
    assert body["take_home_pay"] > 0


def test_admissions_empty_ok(client):
    r = client.get("/api/v1/admissions?province=不存在省&track=理科")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_city_cost(client):
    r = client.get("/api/v1/cities")
    assert r.status_code == 200
    city = r.json()[0]["city"]
    r2 = client.get(f"/api/v1/cities/{city}/cost")
    assert r2.status_code == 200
    assert r2.json()["rent"]["one_bed"]["high"]


def test_majors_list(client):
    r = client.get("/api/v1/majors")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 15
    assert "p25" in items[0]["salary"]
