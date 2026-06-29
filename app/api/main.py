from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    admissions, careers, cities, henan, henan_ai, insurance, majors, my_volunteers, provincial,
    target, universities, volunteer,
)
from app.config import settings
from app.db import get_engine, get_session, init_db
from app.loader.dataset_importer import import_score_rank_csv
from app.loader.seed_loader import is_db_empty, load_all_seeds

_state = {"seed_loaded": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时若 DB 空则自动加载种子，并只导入河南主链路所需一分一段表。"""
    init_db()
    with get_session() as s:
        if is_db_empty(s):
            load_all_seeds(settings.seed_dir, s)
        # 主链路范围：河南 2026 历史类普通本科批。
        # 运行时仅导入河南 2024/2025/2026 一分一段表；
        # 不再把广东或通用旧 gaokao_raw.csv 灌入主程序数据库。
        for csv_name in ["henan_2024_score_rank.csv", "henan_2025_score_rank.csv", "henan_2026_score_rank.csv"]:
            import_score_rank_csv(
                settings.data_dir / "datasets" / csv_name,
                s, ["河南"], [2024, 2025, 2026],
            )
        _state["seed_loaded"] = True
    yield
    _state["seed_loaded"] = False


app = FastAPI(title="河南志愿推 — 河南 2026 历史类普通本科批", lifespan=lifespan)

# CORS：前端 dev (Vite 5173) 跨域调用。
# 前端 API 用相对路径 /api 经 vite proxy 转发（同源，不触发 CORS），
# 此处放开是为允许局域网设备直连后端或生产单端口部署场景。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # allow_origins=["*"] 时必须 False
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = settings.api_prefix
app.include_router(careers.router, prefix=prefix)
app.include_router(cities.router, prefix=prefix)
app.include_router(universities.router, prefix=prefix)
app.include_router(majors.router, prefix=prefix)
app.include_router(admissions.router, prefix=prefix)
app.include_router(insurance.router, prefix=prefix)
app.include_router(provincial.router, prefix=prefix)
app.include_router(volunteer.router, prefix=prefix)
app.include_router(target.router, prefix=prefix)
app.include_router(henan.router, prefix=prefix)
app.include_router(henan_ai.router, prefix=prefix)
app.include_router(my_volunteers.router, prefix=prefix)


@app.get(f"{prefix}/health", tags=["meta"])
def health():
    return {"status": "ok", "seed_loaded": _state["seed_loaded"]}
