from app.engine.henan_target_evaluation import evaluate_target_school


def _candidate(school, major, group, bucket, rank_gap=0, qualified=True):
    return {
        "school_name": school,
        "major_name": major,
        "major_group_code": group,
        "major_group_name": f"{group}组",
        "bucket": bucket,
        "rank_gap": rank_gap,
        "qualified": qualified,
        "blocked_reasons": [] if qualified else ["选科或语种不符合"],
        "bucket_reason": "复用首页专业推荐冲稳保逻辑",
    }


def test_target_school_returns_reachable_majors_by_bucket():
    result = evaluate_target_school(
        profile={"score": 610, "rank": 12000, "track": "历史类", "source_province": "河南"},
        target_school="郑州大学",
        target_majors=[],
        target_group=None,
        candidates=[
            _candidate("郑州大学", "法学", "101", "冲", rank_gap=800),
            _candidate("郑州大学", "历史学", "102", "稳", rank_gap=-500),
            _candidate("河南大学", "汉语言文学", "201", "稳", rank_gap=-1000),
        ],
    )

    assert result["school_name"] == "郑州大学"
    assert result["overall_bucket"] == "可评估"
    assert [item["bucket"] for item in result["items"]] == ["冲", "稳"]
    assert {item["major_group_code"] for item in result["items"]} == {"101", "102"}


def test_target_school_filters_to_selected_majors():
    result = evaluate_target_school(
        profile={"score": 610, "rank": 12000, "track": "历史类", "source_province": "河南"},
        target_school="郑州大学",
        target_majors=["历史学"],
        target_group=None,
        candidates=[
            _candidate("郑州大学", "法学", "101", "冲", rank_gap=800),
            _candidate("郑州大学", "历史学", "102", "稳", rank_gap=-500),
        ],
    )

    assert len(result["items"]) == 1
    assert result["items"][0]["major_name"] == "历史学"
    assert result["items"][0]["bucket"] == "稳"


def test_target_school_rejects_when_no_major_or_group_is_reachable():
    result = evaluate_target_school(
        profile={"score": 480, "rank": 85000, "track": "历史类", "source_province": "河南"},
        target_school="郑州大学",
        target_majors=[],
        target_group=None,
        candidates=[
            _candidate("郑州大学", "法学", "101", "不推荐", rank_gap=35000, qualified=True),
            _candidate("郑州大学", "历史学", "102", "不推荐", rank_gap=32000, qualified=True),
        ],
    )

    assert result["school_name"] == "郑州大学"
    assert result["overall_bucket"] == "不推荐"
    assert result["items"] == []
    assert "没有达到冲稳保条件的专业或专业组" in result["reasons"]


def test_target_evaluation_keeps_group_and_major_risk_separate():
    result = evaluate_target_school(
        profile={"score": 500, "rank": 52000, "track": "历史类", "source_province": "河南"},
        target_school="河南牧业经济学院",
        target_majors=["会计学"],
        target_group=None,
        candidates=[
            {
                "school_name": "河南牧业经济学院",
                "major_name": "会计学",
                "major_group_code": "101",
                "major_group_name": "历史不限组",
                "bucket": "冲",
                "qualified": True,
                "group_bucket": "冲",
                "major_bucket": "不推荐",
                "selected_majors": ["会计学", "财务管理"],
                "bucket_reason": "专业组可冲，但会计学历史专业位次不足",
                "blocked_reasons": [],
            }
        ],
    )

    assert result["items"][0]["group_bucket"] == "冲"
    assert result["items"][0]["major_bucket"] == "不推荐"
    assert "专业组可冲" in result["items"][0]["bucket_reason"]
