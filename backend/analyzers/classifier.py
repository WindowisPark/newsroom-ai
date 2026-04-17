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
    """여러 기사를 동시 분류 (LLM 호출만 병렬, DB 저장은 순차)"""
    semaphore = asyncio.Semaphore(max_concurrent)
    pending = [a for a in articles if a.analysis is None]

    # 1단계: LLM 호출만 병렬로 수행
    async def _classify_only(article: Article) -> tuple[Article, dict] | None:
        async with semaphore:
            try:
                result = await classify_article(article)
                return (article, result)
            except Exception as e:
                logger.warning(f"분류 실패 [{article.id}] {article.title[:30]}: {e}")
                return None

    llm_results = await asyncio.gather(*[_classify_only(a) for a in pending])

    # 2단계: DB 저장은 순차적으로 (commit 충돌 방지)
    results: list[ArticleAnalysis] = []
    for item in llm_results:
        if item is None:
            continue
        article, result = item
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
        results.append(analysis)

    # 3단계: 보도 빈도 기반 중요도 보정
    if results:
        await _boost_by_frequency(results, db)

    return results


async def _boost_by_frequency(analyses: list[ArticleAnalysis], db: AsyncSession):
    """동일 배치 내 키워드 빈도로 importance_score 보정

    같은 이슈를 여러 매체가 보도할수록 중요도가 올라가는 실제 편집 판단을 반영.
    """
    from collections import Counter

    keyword_freq: Counter = Counter()
    for a in analyses:
        for kw in (a.keywords or []):
            keyword_freq[kw] += 1

    for a in analyses:
        article_keywords = a.keywords or []
        if not article_keywords:
            continue
        # 해당 기사 키워드의 평균 빈도
        avg_freq = sum(keyword_freq[kw] for kw in article_keywords) / len(article_keywords)
        # 빈도 2 이상이면 보정 시작, 최대 +2.0
        boost = min(2.0, max(0, (avg_freq - 1)) * 0.5)
        if boost > 0:
            new_score = min(10.0, a.importance_score + boost)
            if new_score != a.importance_score:
                a.importance_score = new_score

    await db.commit()
    logger.info(f"보도 빈도 기반 중요도 보정 완료 ({len(analyses)}건)")
