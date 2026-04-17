"""1차 분석기 - Haiku 4.5로 뉴스 분류/키워드/감성/중요도 분석"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import MODEL_FOR, call_llm
from backend.database.models import Article, ArticleAnalysis
from backend.prompts import CLASSIFIER_SYSTEM

logger = logging.getLogger(__name__)


async def classify_article(article: Article) -> dict:
    """단일 기사를 분류/분석"""
    user_message = f"""다음 뉴스 기사를 분석해주세요.

제목: {article.title}
매체: {article.source_name} ({article.source_type})
요약: {article.description or '없음'}
본문: {(article.content or '')[:1000]}"""

    result = await call_llm(
        system_prompt=CLASSIFIER_SYSTEM,
        user_message=user_message,
        model=MODEL_FOR["classify"],
        max_tokens=1024,
        temperature=0.1,
    )

    return result


async def classify_and_save(article: Article, db: AsyncSession) -> ArticleAnalysis:
    """기사를 분류하고 DB에 저장"""
    result = await classify_article(article)
    content = result["content"]

    analysis = ArticleAnalysis(
        article_id=article.id,
        category=content.get("category", "society"),
        keywords=content.get("keywords", []),
        entities=content.get("entities", []),
        sentiment=content.get("sentiment", "neutral"),
        importance_score=float(content.get("importance_score", 5.0)),
        analyzed_at=datetime.now(timezone.utc),
        model_used=result["model_used"],
    )

    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    return analysis


async def classify_batch(
    articles: list[Article],
    db: AsyncSession,
    max_concurrent: int = 5,
) -> list[ArticleAnalysis]:
    """여러 기사를 동시 분류 (Semaphore로 동시성 제한)"""
    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[ArticleAnalysis] = []

    async def _classify_one(article: Article):
        async with semaphore:
            try:
                analysis = await classify_and_save(article, db)
                results.append(analysis)
            except Exception as e:
                logger.warning(f"분류 실패 [{article.id}] {article.title[:30]}: {e}")

    tasks = [
        _classify_one(article)
        for article in articles
        if article.analysis is None
    ]

    if tasks:
        await asyncio.gather(*tasks)

    return results
