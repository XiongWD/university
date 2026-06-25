"""测试 fixture：为需要 DB 的测试提供隔离的临时数据库。

避免测试间共享全局 data/llm_sim.db 导致状态污染。
monkeypatch settings.db_path 指向 tmp，并 reset engine 单例。
db_url 是 property，基于 db_path 自动重算，无需单独 patch。
"""

import pytest

import app.db as db_module
from app.config import settings


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """提供隔离的临时 DB：重定向 db_path 并 reset engine 单例。"""
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(settings, "db_path", tmp_db)
    # reset engine 单例，下次 get_engine 重建指向新路径
    monkeypatch.setattr(db_module, "_engine", None)
    return tmp_db
