"""专业就业信号评分（design §4.6）。

阳光高考/官方专业定位优先；招聘数据仅作补充。样本不足时必须输出
"就业数据不足"，不得编造岗位数或薪资。
"""
from __future__ import annotations


def score_employment_signal(major_name: str, signals: list) -> dict:
    """返回某专业的就业信号摘要。无匹配信号时显式标注数据不足。"""
    signal = next((s for s in signals if s.major_name == major_name), None)
    if signal is None:
        return {
            "status": "就业数据不足",
            "summary": "暂无足够就业数据，不能用就业前景作为主要推荐依据",
            "confidence": 0.0,
        }
    return {
        "status": "有就业信号",
        "summary": signal.domestic_demand_summary,
        "policy_signal": signal.policy_signal,
        "evidence_level": signal.evidence_level,
        "confidence": signal.confidence,
    }
