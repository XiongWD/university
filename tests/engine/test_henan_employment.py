from app.engine.henan_employment import score_employment_signal
from app.models.henan_data import MajorEmploymentSignal


def test_missing_employment_data_is_explicit():
    result = score_employment_signal("历史学", [])
    assert result["status"] == "就业数据不足"


def test_signal_returns_summary():
    signal = MajorEmploymentSignal(
        major_name="计算机科学与技术",
        direction="计算机",
        policy_signal="数字经济相关",
        domestic_demand_summary="软件开发岗位较多",
        job_market_city_scope="北上广深",
        evidence_level="C",
        source_name="阳光高考专业库",
        source_url="https://gaokao.chsi.com.cn/",
        as_of="2026-06-26",
        confidence=0.5,
    )
    result = score_employment_signal("计算机科学与技术", [signal])
    assert result["status"] == "有就业信号"
    assert "软件开发" in result["summary"]
