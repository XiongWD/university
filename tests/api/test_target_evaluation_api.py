"""目标评估 API 测试（design §7 验收标准）。"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("target_api") / "target_api.db"
    import app.db as db_module
    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
    with TestClient(app) as c:
        yield c


def test_target_evaluate_requires_source_province(client):
    """source_province 必填，缺失应返回 422。"""
    r = client.post("/api/v1/target/evaluate", json={
        "target_school": "郑州大学",
        "total_score": 620,
        "primary_subject": "物理",
    })
    assert r.status_code == 422


def test_target_evaluate_returns_structure(client):
    """合法请求应返回完整评估结构。"""
    r = client.post("/api/v1/target/evaluate", json={
        "source_province": "河南",
        "target_school": "郑州大学",
        "target_major": "计算机科学与技术",
        "total_score": 620,
        "primary_subject": "物理",
        "elective_subjects": ["化学", "生物"],
        "exam_foreign_language": "英语",
        "foreign_language_score": 125,
        "math_score": 130,
    })
    assert r.status_code == 200
    body = r.json()
    assert "eligibility" in body
    assert "group_admission" in body
    assert "major_admission" in body
    assert "missing_data" in body
    assert "sources" in body


def test_target_evaluate_physics_without_chemistry_is_ineligible(client):
    """物理不选化学报郑大计算机：必须不可报，原因含化学（真实 seed 数据集成）。"""
    r = client.post("/api/v1/target/evaluate", json={
        "source_province": "河南",
        "target_school": "郑州大学",
        "target_major": "计算机科学与技术",
        "total_score": 620,
        "primary_subject": "物理",
        "elective_subjects": ["生物", "地理"],
        "exam_foreign_language": "英语",
        "foreign_language_score": 125,
        "math_score": 130,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["eligibility"]["eligible"] is False
    assert any("化学" in x for x in body["eligibility"]["blocked_reasons"])
    assert body["group_admission"]["risk_band"] == "不可报"


def test_target_evaluate_out_of_province_school_is_data_insufficient(client):
    """外省院校无河南计划：必须数据不足，不使用全国计划。"""
    r = client.post("/api/v1/target/evaluate", json={
        "source_province": "河南",
        "target_school": "某外省大学",
        "target_major": "计算机科学与技术",
        "total_score": 620,
        "primary_subject": "物理",
        "elective_subjects": ["化学", "生物"],
        "exam_foreign_language": "英语",
        "foreign_language_score": 125,
        "math_score": 130,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["group_admission"]["risk_band"] == "数据不足"
    assert "2026_enrollment_plan" in body["missing_data"]


def test_target_evaluate_eligible_reports_major_plan(client):
    """资格满足且有计划：报告目标专业可报与计划数（真实 seed 集成）。"""
    r = client.post("/api/v1/target/evaluate", json={
        "source_province": "河南",
        "target_school": "郑州大学",
        "target_major": "计算机科学与技术",
        "total_score": 620,
        "primary_subject": "物理",
        "elective_subjects": ["化学", "生物"],
        "exam_foreign_language": "英语",
        "foreign_language_score": 125,
        "math_score": 130,
    })
    body = r.json()
    assert body["eligibility"]["eligible"] is True
    assert body["major_admission"]["target_major_available"] is True
    assert body["major_admission"]["plan_count"] is not None
    assert body["major_admission"]["plan_count"] > 0
