"""FastAPI 앱 진입점"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import init_db
from backend.models.schemas import APIResponse, HealthOut, SchedulerOut
from backend.routers import (
    news, analysis, reports, headlines, sse, dashboard,
    drafts, watchlist, article_drafts,
)
from backend.scheduler import start_scheduler, stop_scheduler, get_scheduler_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 라이프사이클"""
    settings = get_settings()

    # DB 테이블 생성
    await init_db()
    logger.info("Database initialized")

    # 스케줄러 시작
    start_scheduler(settings.collect_interval_minutes)

    yield

    # 종료
    stop_scheduler()


app = FastAPI(
    title="Newsroom AI",
    description="실시간 뉴스 수집/분석 자동 보고 시스템",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
API_PREFIX = "/api/v1"
app.include_router(news.router, prefix=API_PREFIX)
app.include_router(analysis.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(headlines.router, prefix=API_PREFIX)
app.include_router(sse.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(drafts.router, prefix=API_PREFIX)
app.include_router(watchlist.router, prefix=API_PREFIX)
app.include_router(article_drafts.router, prefix=API_PREFIX)


@app.get("/api/v1/health", response_model=APIResponse)
async def health_check():
    """헬스 체크"""
    stats = get_scheduler_stats()
    return APIResponse(data=HealthOut(
        database="connected",
        scheduler="running" if stats["running"] else "stopped",
        last_collection=stats["last_run"],
    ))


@app.get("/api/v1/system/scheduler", response_model=APIResponse)
async def scheduler_status():
    """스케줄러 상태"""
    stats = get_scheduler_stats()
    return APIResponse(data=SchedulerOut(**stats))
