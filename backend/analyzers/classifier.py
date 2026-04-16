"""1차 분석기 - Haiku 4.5로 뉴스 분류/키워드/감성/중요도 분석"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import HAIKU_MODEL, call_llm
from backend.database.models import Article, ArticleAnalysis
from backend.prompts import CLASSIFIER_SYSTEM


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
        model=HAIKU_MODEL,
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


async def classify_batch(articles: list[Article], db: AsyncSession) -> list[ArticleAnalysis]:
    """여러 기사를 순차 분류 (API rate limit 고려)"""
    results = []
    for article in articles:
        if article.analysis is not None:
            continue  # 이미 분석된 기사 스킵
        try:
            analysis = await classify_and_save(article, db)
            results.append(analysis)
        except Exception:
            continue  # 개별 실패 시 건너뛰기
    return results
