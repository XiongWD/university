from app.loader.henan_verification import reconcile_group_from_api_items


def test_reconcile_group_from_api_items_accepts_unknown_tuition_placeholders():
    local_rows = [
        {
            "school_special_id": "57519",
            "special_group": "756942",
            "sp_name": "会展经济与管理",
            "num": "2",
            "tuition": "",
        }
    ]
    api_items = [
        {
            "school_special_id": "57519",
            "special_group": "756950",
            "sp_name": "会展经济与管理",
            "num": "2",
            "tuition": "-",
        }
    ]

    result = reconcile_group_from_api_items(local_rows, api_items)

    assert result is not None
    assert result["old_group"] == "756942"
    assert result["new_group"] == "756950"
    assert result["matched_count"] == 1


def test_reconcile_group_from_api_items_rejects_split_destination_groups():
    local_rows = [
        {
            "school_special_id": "1001",
            "special_group": "700001",
            "sp_name": "法学",
            "num": "2",
            "tuition": "5000",
        },
        {
            "school_special_id": "1002",
            "special_group": "700001",
            "sp_name": "汉语言文学",
            "num": "2",
            "tuition": "5000",
        },
    ]
    api_items = [
        {
            "school_special_id": "1001",
            "special_group": "700101",
            "sp_name": "法学",
            "num": "2",
            "tuition": "5000",
        },
        {
            "school_special_id": "1002",
            "special_group": "700102",
            "sp_name": "汉语言文学",
            "num": "2",
            "tuition": "5000",
        },
    ]

    assert reconcile_group_from_api_items(local_rows, api_items) is None


def test_reconcile_group_from_api_items_rejects_name_or_plan_mismatch():
    local_rows = [
        {
            "school_special_id": "1001",
            "special_group": "700001",
            "sp_name": "法学",
            "num": "2",
            "tuition": "5000",
        }
    ]
    api_items = [
        {
            "school_special_id": "1001",
            "special_group": "700101",
            "sp_name": "金融学",
            "num": "2",
            "tuition": "5000",
        }
    ]

    assert reconcile_group_from_api_items(local_rows, api_items) is None


def test_reconcile_group_from_api_items_chooses_best_match_among_duplicate_special_ids():
    local_rows = [
        {
            "school_special_id": "48912",
            "special_group": "755883",
            "sp_name": "特殊教育",
            "num": "35",
            "tuition": "4400",
        }
    ]
    api_items = [
        {
            "school_special_id": "48912",
            "special_group": "755883",
            "sp_name": "特殊教育",
            "num": "35",
            "tuition": "4400",
        },
        {
            "school_special_id": "48912",
            "special_group": "755883",
            "sp_name": "特殊教育",
            "num": "20",
            "tuition": "4400",
        },
    ]

    result = reconcile_group_from_api_items(local_rows, api_items)

    assert result is not None
    assert result["new_group"] == "755883"
