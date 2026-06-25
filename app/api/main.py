from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import (
    admissions, careers, cities, insurance, majors, provincial, universities,
)
from app.config import settings
from app.db import get_engine, get_session, init_db
from app.loader.dataset_importer import import_score_rank_csv
from app.loader.seed_loader import is_db_empty, load_all_seeds

_state = {"seed_loaded": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时若 DB 空则自动加载种子，并触发一分一段表 CSV 导入（缺失降级）。"""
    init_db()
    with get_session() as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
        # 一分一段表 CSV 运行时导入（CSV 缺失降级为空，不阻断启动）
        # - gaokao_raw.csv: 历史数据集(至2024, 文/理科)
        # - henan_2026_score_rank.csv: 河南2026(物理类/历史类, OCR自官方PDF)
        for csv_name in ["gaokao_raw.csv", "henan_2026_score_rank.csv"]:
            import_score_rank_csv(
                settings.data_dir / "datasets" / csv_name,
                s, ["河南", "广东"], [2022, 2023, 2024, 2026],
            )
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
app.include_router(provincial.router, prefix=prefix)


@app.get(f"{prefix}/health", tags=["meta"])
def health():
    return {"status": "ok", "seed_loaded": _state["seed_loaded"]}
