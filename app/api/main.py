from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import (
    admissions, careers, cities, insurance, majors, universities,
)
from app.config import settings
from app.db import get_engine, get_session, init_db
from app.loader.seed_loader import is_db_empty, load_all_seeds

_state = {"seed_loaded": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时若 DB 空则自动加载种子。"""
    init_db()
    with get_session() as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
        _state["seed_loaded"] = True
    yield
    _state["seed_loaded"] = False


app = FastAPI(title="人生经济模型模拟器 — 数据底座", lifespan=lifespan)
prefix = settings.api_prefix
app.include_router(careers.router, prefix=prefix)
app.include_router(cities.router, prefix=prefix)
app.include_router(universities.router, prefix=prefix)
app.include_router(majors.router, prefix=prefix)
app.include_router(admissions.router, prefix=prefix)
app.include_router(insurance.router, prefix=prefix)


@app.get(f"{prefix}/health", tags=["meta"])
def health():
    return {"status": "ok", "seed_loaded": _state["seed_loaded"]}
