"""advisory 主接口 API 测试。"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("adv_api") / "adv_api.db"
    import app.db as db_module
    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
    with TestClient(app) as c:
        yield c


_REQ = {
    "total_score": 543, "primary_subject": "历史",
    "math_score": 75, "exam_foreign_language": "英语",
    "foreign_language_score": 120, "english_actual_level": "intermediate",
    "elective_subjects": ["政治", "地理"],
    "family_annual_income": 80000, "family_savings": 20000,
    "max_annual_education_budget": 25000,
}


def test_advisory_returns_full_structure(client):
    r = client.post("/api/v1/volunteer/advisory", json=_REQ)
    assert r.status_code == 200
    body = r.json()
    for k in ("major_directions", "school_options", "ineligible_options",
              "budget_summary", "notes", "student_rank", "data_year"):
        assert k in body, f"missing {k}"
    so = body["school_options"]
    for bk in ("reach", "match", "safe"):
        assert bk in so


def test_advisory_no_forbidden_narrative(client):
    """遵守 narrative-policy：不出现禁止词。"""
    body = client.post("/api/v1/volunteer/advisory", json=_REQ).json()
    forbidden = ["人生路径", "人生轨迹", "回本", "ROI", "投资回报", "15年净收益", "赛道", "命运"]
    text = json.dumps(body, ensure_ascii=False)
    for w in forbidden:
        assert w not in text, f"advisory 响应含禁止词 {w}"
