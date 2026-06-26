"""advisory 河南 2026 主链路回归测试（design §7 验收样本）。"""
from tests.api.test_advisory_api import client


def _post(client, payload):
    r = client.post("/api/v1/volunteer/advisory", json=payload)
    assert r.status_code == 200
    return r.json()


def test_history_460_reports_undergrad_risk(client):
    """河南历史 460（低于本科线 459 附近）：必须提示本科线风险。"""
    body = _post(client, {
        "province": "河南",
        "data_year": 2026,
        "risk_preference": "中",
        "total_score": 460,
        "primary_subject": "历史",
        "math_score": 95,
        "exam_foreign_language": "英语",
        "foreign_language_score": 120,
        "english_actual_level": "advanced",
        "elective_subjects": ["政治", "地理"],
    })
    assert body["batch_line_decision"]["batch_position"] in {"below_undergrad", "junior_college_only", "above_undergrad"}
    assert "本科" in body["batch_line_decision"]["recommendation_policy_note"]


def test_physics_without_chemistry_does_not_safe_recommend_computer(client):
    """河南物理 540 不选化学：安全推荐里不应出现计算机（物化硬要求）。"""
    body = _post(client, {
        "province": "河南",
        "data_year": 2026,
        "risk_preference": "中",
        "total_score": 540,
        "primary_subject": "物理",
        "math_score": 110,
        "exam_foreign_language": "日语",
        "foreign_language_score": 115,
        "english_actual_level": "basic",
        "elective_subjects": ["生物", "地理"],
    })
    safe_text = str(body["school_options"]["safe"])
    assert "计算机" not in safe_text


def test_history_520_not_all_safe_when_data_exists(client):
    """河南历史 520：不应只有兜底，应有冲稳候选或数据不足说明。"""
    body = _post(client, {
        "province": "河南",
        "data_year": 2026,
        "risk_preference": "中",
        "total_score": 520,
        "primary_subject": "历史",
        "math_score": 105,
        "exam_foreign_language": "英语",
        "foreign_language_score": 125,
        "english_actual_level": "advanced",
        "elective_subjects": ["政治", "地理"],
    })
    total = sum(len(body["school_options"][k]) for k in ("reach", "match", "safe"))
    assert total > 0
    assert len(body["school_options"]["reach"]) + len(body["school_options"]["match"]) > 0 or body["review_warnings"]


def test_advisory_exposes_batch_line_decision_and_policy(client):
    """advisory 响应必须暴露批次线判断、风险说明和推荐策略字段。"""
    body = _post(client, {
        "province": "河南",
        "data_year": 2026,
        "risk_preference": "中",
        "total_score": 520,
        "primary_subject": "历史",
        "math_score": 105,
        "exam_foreign_language": "英语",
        "foreign_language_score": 125,
        "elective_subjects": ["政治", "地理"],
    })
    assert body["batch_line_decision"] is not None
    assert body["batch_line_decision"]["undergrad_line"] is not None
    assert body["recommendation_policy"]
    assert isinstance(body["review_warnings"], list)
