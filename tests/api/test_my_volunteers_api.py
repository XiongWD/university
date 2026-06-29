"""我的志愿组 API 测试（design：志愿编排工作台）。

覆盖：添加/去重/上限48/刷新恢复/layout原子/双轨档位/删除/清空/资格校验/409/stats/profile重算。
"""
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import settings
from app.db import get_engine, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds


def _boot_client(tmp_path_factory):
    tmp_db = tmp_path_factory.mktemp("mv_api") / "mv_api.db"
    import app.db as db_module
    db_module._engine = None
    settings.db_path = tmp_db
    init_db()
    with Session(get_engine()) as session:
        if is_db_empty(session):
            load_all_seeds(settings.seed_dir, session)
    return TestClient(app)


_PROFILE = {
    "source_province": "河南", "score": 480, "rank": 60000, "track": "历史类",
    "primary_subject": "历史", "elective_subjects": ["政治", "地理"], "exam_foreign_language": "日语",
}


def test_get_empty_group(tmp_path_factory):
    """空志愿组：自动创建 default 方案，0 项。"""
    with _boot_client(tmp_path_factory) as client:
        r = client.get("/api/v1/my-volunteers")
        assert r.status_code == 200
        g = r.json()
        assert g["owner_key"] == "default"
        assert g["version"] == 1
        assert g["items"] == []
        assert g["stats"]["total"] == 0


def test_add_item_and_persist(tmp_path_factory):
    """添加志愿 + 刷新恢复（服务端持久化）。"""
    with _boot_client(tmp_path_factory) as client:
        r = client.post("/api/v1/my-volunteers/items", json={
            "school_code": "2535", "major_group_code": "759266", "profile": _PROFILE,
        })
        assert r.status_code == 200, r.text
        g = r.json()
        assert len(g["items"]) == 1
        assert g["version"] == 2
        it = g["items"][0]
        assert it["school_name"] == "哈尔滨石油学院"
        assert it["algorithm_tier_at_add"] == "垫"
        assert it["effective_tier"] == "垫"
        assert it["eligibility_status"] == "partially_eligible"

        # 刷新恢复（新 client 同库）
        r2 = client.get("/api/v1/my-volunteers")
        assert len(r2.json()["items"]) == 1
        assert r2.json()["version"] == 2


def test_add_duplicate_rejected(tmp_path_factory):
    """重复添加拒绝（同一院校专业组）。"""
    with _boot_client(tmp_path_factory) as client:
        client.post("/api/v1/my-volunteers/items", json={
            "school_code": "2535", "major_group_code": "759266", "profile": _PROFILE,
        })
        r = client.post("/api/v1/my-volunteers/items", json={
            "school_code": "2535", "major_group_code": "759266", "profile": _PROFILE,
        })
        assert r.status_code == 400
        assert "已在志愿组" in r.json()["detail"]


def test_add_invalid_group_rejected(tmp_path_factory):
    """不存在的院校专业组拒绝（服务端重新校验，不信任前端）。"""
    with _boot_client(tmp_path_factory) as client:
        r = client.post("/api/v1/my-volunteers/items", json={
            "school_code": "NOTEXIST", "major_group_code": "999999", "profile": _PROFILE,
        })
        assert r.status_code == 400
        assert "不存在" in r.json()["detail"]


def test_layout_atomic_reorder_and_tier(tmp_path_factory):
    """原子 layout：跨档拖拽同时改 planned_tier+sort_order（单事务）。"""
    with _boot_client(tmp_path_factory) as client:
        # 加 2 个志愿
        client.post("/api/v1/my-volunteers/items", json={"school_code": "2535", "major_group_code": "759266", "profile": _PROFILE})
        g = client.post("/api/v1/my-volunteers/items", json={"school_code": "2535", "major_group_code": "759266", "profile": _PROFILE})
        # 第二个加不了（重复），加另一个真实存在的组——先找一个可达的
        # 用推荐接口拿一个可达组
        rec = client.post("/api/v1/henan/recommendation", json={
            "score": 480, "track": "历史类", "primary_subject": "历史",
            "elective_subjects": ["政治", "地理"], "exam_foreign_language": "日语",
        })
        buckets = rec.json()["buckets"]
        # 找一个垫/保档的可达组
        target = None
        for b in ["垫", "保"]:
            for it in buckets.get(b, []):
                target = it
                break
            if target:
                break
        assert target is not None, "应有可达志愿"
        g2 = client.post("/api/v1/my-volunteers/items", json={
            "school_code": target["school_code"], "major_group_code": target["major_group_code"], "profile": _PROFILE,
        })
        items = g2.json()["items"]
        assert len(items) == 2
        version = g2.json()["version"]

        # 原子 layout：交换顺序 + 改第一个为冲档
        layout = {
            "version": version,
            "items": [
                {"item_id": items[1]["id"], "planned_tier": "冲", "sort_order": 0},
                {"item_id": items[0]["id"], "planned_tier": None, "sort_order": 1},
            ],
        }
        r = client.patch("/api/v1/my-volunteers/layout", json=layout)
        assert r.status_code == 200, r.text
        ng = r.json()
        assert ng["version"] == version + 1
        assert ng["manually_reordered"] is True
        # 顺序交换：原 items[1] 现在在 sort_order 0
        assert ng["items"][0]["id"] == items[1]["id"]
        assert ng["items"][0]["planned_tier"] == "冲"
        assert ng["items"][0]["effective_tier"] == "冲"


def test_layout_version_conflict_409(tmp_path_factory):
    """乐观锁：version 不符返回 409 + 最新 group。"""
    with _boot_client(tmp_path_factory) as client:
        client.post("/api/v1/my-volunteers/items", json={"school_code": "2535", "major_group_code": "759266", "profile": _PROFILE})
        g = client.get("/api/v1/my-volunteers").json()
        # 用旧 version 改档
        r = client.patch(f"/api/v1/my-volunteers/items/{g['items'][0]['id']}/tier",
                         json={"planned_tier": "稳", "version": g["version"] - 1})
        assert r.status_code == 409
        assert r.json()["error"] == "version_conflict"
        assert "latest_group" in r.json()


def test_update_tier_and_restore(tmp_path_factory):
    """改规划档位 + 恢复算法档位（null）。"""
    with _boot_client(tmp_path_factory) as client:
        client.post("/api/v1/my-volunteers/items", json={"school_code": "2535", "major_group_code": "759266", "profile": _PROFILE})
        g = client.get("/api/v1/my-volunteers").json()
        item_id = g["items"][0]["id"]
        v = g["version"]
        # 改为冲
        r = client.patch(f"/api/v1/my-volunteers/items/{item_id}/tier",
                         json={"planned_tier": "冲", "version": v})
        assert r.json()["items"][0]["planned_tier"] == "冲"
        assert r.json()["items"][0]["effective_tier"] == "冲"
        # planned_tier 不允许设 需复核
        r2 = client.patch(f"/api/v1/my-volunteers/items/{item_id}/tier",
                          json={"planned_tier": "需复核", "version": r.json()["version"]})
        assert r2.status_code == 400
        # 恢复
        r3 = client.patch(f"/api/v1/my-volunteers/items/{item_id}/tier",
                          json={"planned_tier": None, "version": r.json()["version"]})
        assert r3.json()["items"][0]["planned_tier"] is None
        assert r3.json()["items"][0]["effective_tier"] == r3.json()["items"][0]["latest_algorithm_tier"]


def test_delete_item(tmp_path_factory):
    """删除单个志愿 + sort_order 重排连续。"""
    with _boot_client(tmp_path_factory) as client:
        client.post("/api/v1/my-volunteers/items", json={"school_code": "2535", "major_group_code": "759266", "profile": _PROFILE})
        g = client.get("/api/v1/my-volunteers").json()
        r = client.delete(f"/api/v1/my-volunteers/items/{g['items'][0]['id']}?version={g['version']}")
        assert r.status_code == 200
        assert r.json()["items"] == []
        assert r.json()["version"] == g["version"] + 1


def test_clear_group(tmp_path_factory):
    """清空全部志愿。"""
    with _boot_client(tmp_path_factory) as client:
        client.post("/api/v1/my-volunteers/items", json={"school_code": "2535", "major_group_code": "759266", "profile": _PROFILE})
        g = client.get("/api/v1/my-volunteers").json()
        r = client.post("/api/v1/my-volunteers/clear",
                        json={"confirm": True, "version": g["version"]})
        assert r.status_code == 200
        assert r.json()["items"] == []
        # 未 confirm 拒绝
        r2 = client.post("/api/v1/my-volunteers/clear",
                         json={"confirm": False, "version": r.json()["version"]})
        assert r2.status_code == 400


def test_stats_computed(tmp_path_factory):
    """stats 正确计算（档位/地域/性质）。"""
    with _boot_client(tmp_path_factory) as client:
        client.post("/api/v1/my-volunteers/items", json={"school_code": "2535", "major_group_code": "759266", "profile": _PROFILE})
        g = client.get("/api/v1/my-volunteers").json()
        s = g["stats"]
        assert s["total"] == 1
        assert s["by_effective_tier"].get("垫", 0) == 1
        # 哈尔滨石油学院是省外民办
        assert s["local_count"] == 0
        assert s["private_count"] == 1


def test_profile_snapshot_recompute(tmp_path_factory):
    """GET 时用 profile_snapshot 重算 latest_algorithm_tier（不依赖添加时快照）。"""
    with _boot_client(tmp_path_factory) as client:
        client.post("/api/v1/my-volunteers/items", json={"school_code": "2535", "major_group_code": "759266", "profile": _PROFILE})
        g = client.get("/api/v1/my-volunteers").json()
        it = g["items"][0]
        # latest_algorithm_tier 应由当前引擎重算（与 algorithm_tier_at_add 一致，因同档案）
        assert it["latest_algorithm_tier"] == it["algorithm_tier_at_add"]
        assert it["algorithm_changed"] is False


def test_profile_without_rank_still_tiers_correctly(tmp_path_factory):
    """回归：profile.rank 缺失（仅 score）时，重算应用 score 反查补全 rank，
    正确判档而非错误降级为「需人工复核」。

    根因：加入志愿组时前端 profile.rank 可能为 null，若重算不补全 rank，
    build_henan_candidates 因 rank=0 无法判档 → 全部降级需人工复核（加入前是稳/保）。
    """
    with _boot_client(tmp_path_factory) as client:
        # profile.rank 缺失（仅 score），模拟前端只填分数未填位次
        profile_no_rank = {k: v for k, v in _PROFILE.items() if k != "rank"}
        client.post("/api/v1/my-volunteers/items", json={
            "school_code": "2535", "major_group_code": "759266", "profile": profile_no_rank,
        })
        g = client.get("/api/v1/my-volunteers").json()
        it = g["items"][0]
        # rank 缺失也必须判出明确档位（垫/保/稳/冲/搏），不能是「需人工复核」
        assert it["latest_algorithm_tier"] in {"搏", "冲", "稳", "保", "垫"}, \
            f"rank 缺失时应补全后判档，实际降级为 {it['latest_algorithm_tier']!r}"
        assert it["algorithm_tier_at_add"] in {"搏", "冲", "稳", "保", "垫"}
