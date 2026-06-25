"""第0步数据桥梁层测试：SchoolMajorOffering + AdmissionRecord.data_granularity。

验证防伪装核心：学校级数据不得伪装成专业级。
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds
from app.models.admission import DataGranularity
from app.models.tables import AdmissionRow, SchoolMajorOfferingRow


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("step0") / "step0.db"
    import app.db as db_module
    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
    with TestClient(app) as c:
        yield c


def test_school_major_offerings_loaded(client):
    """学校专业供给表已加载。"""
    with Session(get_engine()) as s:
        rows = s.exec(select(SchoolMajorOfferingRow)).all()
        assert len(rows) >= 40
        # 郑大应开设计算机
        zzu_cs = [r for r in rows if r.school == "郑州大学" and r.major == "计算机科学与技术"]
        assert len(zzu_cs) == 1
        assert zzu_cs[0].is_active is True


def test_school_has_major_query(client):
    """可查询'某校是否开设某专业'。"""
    with Session(get_engine()) as s:
        # 升达应开设国际经济与贸易
        r = s.exec(select(SchoolMajorOfferingRow).where(
            SchoolMajorOfferingRow.school == "郑州升达经贸管理学院"
        ).where(SchoolMajorOfferingRow.major == "国际经济与贸易")).first()
        assert r is not None
        # 信阳农林应开设园林（非计算机）
        r2 = s.exec(select(SchoolMajorOfferingRow).where(
            SchoolMajorOfferingRow.school == "信阳农林学院"
        ).where(SchoolMajorOfferingRow.major == "计算机科学与技术")).first()
        assert r2 is None  # 信阳农林无计算机专业


def test_data_granularity_major_for_real_majors(client):
    """真实专业名(major字段)的录取数据标为 major 粒度。"""
    with Session(get_engine()) as s:
        r = s.exec(select(AdmissionRow).where(AdmissionRow.major == "计算机科学与技术")).first()
        assert r is not None
        assert r.data_granularity == "major"


def test_data_granularity_school_for_generic(client):
    """'普通类'占位的录取数据标为 school 粒度（专业未确认）。"""
    with Session(get_engine()) as s:
        r = s.exec(select(AdmissionRow).where(AdmissionRow.major == "普通类")).first()
        if r:  # 若存在普通类记录
            assert r.data_granularity == "school"


def test_data_granularity_enum_validation():
    """DataGranularity 枚举值正确。"""
    assert DataGranularity("major") == DataGranularity.MAJOR
    assert DataGranularity("group") == DataGranularity.GROUP
    assert DataGranularity("school") == DataGranularity.SCHOOL


def test_admission_api_exposes_granularity(client):
    """录取API返回data_granularity字段（前端用于显示数据可信度）。"""
    r = client.get("/api/v1/volunteer/admissions", params={"province": "河南", "track": "理科"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) > 0
    for a in body:
        assert "data_granularity" in a
        assert a["data_granularity"] in ("major", "group", "school")
