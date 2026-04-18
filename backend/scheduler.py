"""APScheduler - 주기적 뉴스 수집 + 분석 + 자동 보고 파이프라인"""

import logging
from datetime import date, datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.collectors.service import collect_all
from backend.analyzers.classifier import classify_batch, get_blocked_article_ids
from backend.analyzers.reporter import generate_briefing
from backend.analyzers.agenda import analyze_agenda
from backend.config import get_settings
from backend.database import async_session
from backend.database.models import Article, ArticleAnalysis, BriefingReport, AgendaReport
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
        # 반복 실패한 기사는 blocklist로 제외하여 토큰 낭비 방지
        import uuid as _uuid
        blocked_ids = [_uuid.UUID(aid) for aid in get_blocked_article_ids()]
        stmt = (
            select(Article)
            .outerjoin(ArticleAnalysis)
            .where(ArticleAnalysis.id.is_(None))
            .limit(30)  # 배치 크기 제한
        )
        if blocked_ids:
            stmt = stmt.where(~Article.id.in_(blocked_ids))
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

            # 속보 감지: 높은 중요도(>=8.5) + 다수 매체(>=2곳) 공통 보도만 속보로 간주
            # 단독 기사의 자극적 보도가 속보로 승격되는 오탐을 방지한다.
            breaking = [
                a for a in analyses
                if a.importance_score >= 8.5 and getattr(a, "_source_count", 1) >= 2
            ]
            if breaking:
                broadcast_event("breaking_alert", {
                    "count": len(breaking),
                    "titles": [a.article.title if a.article else "" for a in breaking][:3],
                })

        # 3. 자동 보고: 충분한 기사가 분석되면 브리핑 + 의제 자동 생성
        settings = get_settings()
        if settings.auto_report_enabled:
            await _auto_generate_reports(db)


async def _auto_generate_reports(db: AsyncSession):
    """오늘 분석된 기사가 충분하면 브리핑/의제 자동 생성"""
    settings = get_settings()
    today = date.today()

    # 오늘 분석된 기사 수 확인
    count_stmt = (
        select(func.count())
        .select_from(ArticleAnalysis)
        .join(Article)
        .where(func.date(Article.collected_at) == today)
    )
    result = await db.execute(count_stmt)
    analyzed_count = result.scalar() or 0

    if analyzed_count < settings.auto_report_min_articles:
        return

    # 오늘 브리핑이 이미 있는지 확인
    briefing_stmt = select(BriefingReport).where(BriefingReport.date == today)
    existing_briefing = (await db.execute(briefing_stmt)).scalar_one_or_none()

    if not existing_briefing:
        try:
            logger.info("Auto-generating daily briefing report...")
            await generate_briefing(db, today)
            broadcast_event("report_generated", {
                "type": "briefing",
                "date": today.isoformat(),
            })
            logger.info("Daily briefing report generated successfully")
        except Exception as e:
            logger.error(f"Auto briefing generation failed: {e}")

    # 오늘 의제가 이미 있는지 확인
    agenda_stmt = select(AgendaReport).where(AgendaReport.date == today)
    existing_agenda = (await db.execute(agenda_stmt)).scalar_one_or_none()

    if not existing_agenda:
        try:
            logger.info("Auto-generating daily agenda analysis...")
            await analyze_agenda(db, today)
            broadcast_event("report_generated", {
                "type": "agenda",
                "date": today.isoformat(),
            })
            logger.info("Daily agenda analysis generated successfully")
        except Exception as e:
            logger.error(f"Auto agenda generation failed: {e}")


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
