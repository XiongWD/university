"""大学费用估算 API 测试。"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("uni_cost") / "uni_cost.db"
    import app.db as db_module
    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
    with TestClient(app) as c:
        yield c


def test_public_school_cost(client):
    """公立校费用：学费低 + 城市生活费。"""
    d = client.get("/api/v1/universities/清华大学/cost").json()
    assert d["nature"] == "公立"
    assert d["tuition_per_year"] == 5000
    assert d["years"] == 4
    assert d["grand_total"] == d["annual_total"] * 4
    assert d["grand_total"] > 0
    assert "北京" in d["city_cost_source"]


def test_private_school_higher_tuition(client):
    """民办校学费显著高于公立。"""
    public = client.get("/api/v1/universities/清华大学/cost").json()
    private = client.get("/api/v1/universities/郑州升达经贸管理学院/cost").json()
    assert private["nature"] == "民办"
    assert private["tuition_per_year"] > public["tuition_per_year"] * 2


def test_sino_foreign_highest_tuition(client):
    """中外合作学费最高。"""
    d = client.get("/api/v1/universities/西交利物浦大学/cost").json()
    assert d["nature"] == "中外合作"
    assert d["tuition_per_year"] >= 80000


def test_cost_breakdown_sums_correctly(client):
    """年总开销 = 学费 + 住宿 + 生活费。"""
    d = client.get("/api/v1/universities/郑州大学/cost").json()
    expected = d["tuition_per_year"] + d["accommodation_per_year"] + d["living_cost_per_year"]
    assert d["annual_total"] == expected


def test_custom_years(client):
    """支持自定义年数（如专科3年）。"""
    d = client.get("/api/v1/universities/清华大学/cost", params={"years": 3}).json()
    assert d["years"] == 3
    assert d["grand_total"] == d["annual_total"] * 3


def test_filter_by_nature(client):
    """按办学性质筛选。"""
    public = client.get("/api/v1/universities", params={"nature": "公立"}).json()
    private = client.get("/api/v1/universities", params={"nature": "民办"}).json()
    assert all(u["nature"] == "公立" for u in public)
    assert all(u["nature"] == "民办" for u in private)
    assert len(private) >= 2


def test_unknown_school_returns_none(client):
    """未知学校返回 null（不报错）。"""
    r = client.get("/api/v1/universities/不存在的学校/cost")
    assert r.status_code == 200
    assert r.json() is None
