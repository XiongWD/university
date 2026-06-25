"""SQLite 引擎 + Session 工厂。

get_session 为 @contextmanager（支持 with），get_session_dep 为 FastAPI 依赖（generator）。
"""

from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
    return _engine


def init_db():
    """建表（导入 tables 触发模型注册）。返回 engine。"""
    import app.models.tables  # noqa: F401  确保表模型注册
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    return engine


@contextmanager
def get_session(engine=None):
    engine = engine or get_engine()
    with Session(engine) as session:
        yield session


def get_session_dep():
    """FastAPI 依赖专用（generator）。"""
    engine = get_engine()
    with Session(engine) as session:
        yield session
