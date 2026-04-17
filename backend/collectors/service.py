"""뉴스 수집 통합 서비스 - 수집 → 중복 제거 → DB 저장"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.collectors import newsapi, naver, rss
from backend.database.models import Article

logger = logging.getLogger(__name__)


async def collect_all(
    db: AsyncSession,
    sources: list[str] | None = None,
    query: str | None = None,
) -> dict:
    """모든 소스에서 뉴스를 병렬 수집하고 DB에 저장

    Returns:
        {"collected_count": int, "new_count": int, "duplicate_count": int, "sources": dict}
    """
    if sources is None:
        sources = ["newsapi", "naver", "rss"]

    all_articles: list[dict] = []
    source_counts: dict[str, int] = {}

    # 각 소스를 병렬로 수집
    tasks = {}
    if "newsapi" in sources:
        tasks["newsapi"] = _fetch_newsapi(query)
    if "naver" in sources:
        tasks["naver"] = _fetch_naver(query)
    if "rss" in sources:
        tasks["rss"] = _fetch_rss()

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    for source_name, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            logger.error(f"[{source_name}] 수집 실패: {result}")
            source_counts[source_name] = 0
        else:
            all_articles.extend(result)
            source_counts[source_name] = len(result)
            logger.info(f"[{source_name}] {len(result)}건 수집 완료")

    collected_count = len(all_articles)

    # 중복 제거 후 DB 저장
    new_count = await _save_articles(db, all_articles)
    duplicate_count = collected_count - new_count

    return {
        "collected_count": collected_count,
        "new_count": new_count,
        "duplicate_count": duplicate_count,
        "sources": source_counts,
    }


async def _fetch_newsapi(query: str | None) -> list[dict]:
    articles = await newsapi.fetch_top_headlines(page_size=30)
    if query:
        articles += await newsapi.fetch_everything(query=query, page_size=20)
    return articles


async def _fetch_naver(query: str | None) -> list[dict]:
    if query:
        return await naver.fetch_news(query=query, display=30)
    return await naver.fetch_by_categories(display=10)


async def _fetch_rss() -> list[dict]:
    return await rss.fetch_feeds(max_per_feed=15)


async def _save_articles(db: AsyncSession, articles: list[dict]) -> int:
    """기사를 DB에 저장하고 새로 저장된 개수를 반환 (URL 기반 중복 제거)"""
    if not articles:
        return 0

    # 이미 존재하는 URL 조회
    urls = [a["url"] for a in articles if a.get("url")]
    existing_result = await db.execute(
        select(Article.url).where(Article.url.in_(urls))
    )
    existing_urls = set(existing_result.scalars().all())

    # 새 기사만 필터
    new_articles = [a for a in articles if a.get("url") and a["url"] not in existing_urls]

    # 동일 배치 내 URL 중복도 제거
    seen_urls = set()
    unique_articles = []
    for a in new_articles:
        if a["url"] not in seen_urls:
            seen_urls.add(a["url"])
            unique_articles.append(a)

    if not unique_articles:
        return 0

    # DB 삽입
    now = datetime.now(timezone.utc)
    db_articles = [
        Article(
            title=a["title"],
            description=a.get("description"),
            content=a.get("content"),
            url=a["url"],
            source_name=a.get("source_name", "Unknown"),
            source_type=a.get("source_type", "domestic"),
            source_api=a.get("source_api", "unknown"),
            published_at=a.get("published_at"),
            collected_at=now,
        )
        for a in unique_articles
    ]

    db.add_all(db_articles)
    await db.commit()

    return len(db_articles)
