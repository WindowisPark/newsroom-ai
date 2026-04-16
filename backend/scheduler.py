"""APScheduler - 주기적 뉴스 수집 + 분석 파이프라인"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.collectors.service import collect_all
from backend.analyzers.classifier import classify_batch
from backend.database import async_session
from backend.database.models import Article, ArticleAnalysis
from backend.routers.sse import broadcast_event

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_stats = {
    "total_collections": 0,
    "last_run": None,
}


def get_scheduler_stats() -> dict:
    jobs = scheduler.get_jobs()
    next_run = jobs[0].next_run_time if jobs else None
    return {
        "running": scheduler.running,
        "interval_minutes": 15,
        "next_run": next_run,
        "last_run": _stats["last_run"],
        "total_collections": _stats["total_collections"],
    }


async def collection_pipeline():
    """수집 → 1차 분석 파이프라인"""
    logger.info("Starting scheduled collection pipeline...")

    async with async_session() as db:
        # 1. 뉴스 수집
        result = await collect_all(db)
        _stats["total_collections"] += 1
        _stats["last_run"] = datetime.now(timezone.utc)

        logger.info(
            f"Collected: {result['collected_count']} articles, "
            f"{result['new_count']} new, "
            f"{result['duplicate_count']} duplicates"
        )

        # SSE 알림
        if result["new_count"] > 0:
            broadcast_event("new_articles", {
                "count": result["new_count"],
                "sources": result["sources"],
            })

        # 2. 미분석 기사에 대해 1차 분석 (Haiku)
        stmt = (
            select(Article)
            .outerjoin(ArticleAnalysis)
            .where(ArticleAnalysis.id.is_(None))
            .limit(30)  # 배치 크기 제한
        )
        unanalyzed = await db.execute(stmt)
        articles = list(unanalyzed.scalars().all())

        if articles:
            logger.info(f"Classifying {len(articles)} unanalyzed articles...")
            analyses = await classify_batch(articles, db)
            logger.info(f"Classified {len(analyses)} articles")

            broadcast_event("analysis_complete", {
                "type": "classification",
                "count": len(analyses),
            })


def start_scheduler(interval_minutes: int = 15):
    """스케줄러 시작"""
    scheduler.add_job(
        collection_pipeline,
        "interval",
        minutes=interval_minutes,
        id="collection_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started with {interval_minutes}min interval")


def stop_scheduler():
    """스케줄러 중지"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
