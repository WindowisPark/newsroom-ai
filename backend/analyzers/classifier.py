"""1차 분석기 - Haiku 4.5로 뉴스 분류/키워드/감성/중요도 분석"""

import asyncio
import logging
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import MODEL_FOR, call_llm
from backend.analyzers.schemas import ClassificationOut
from backend.database.models import Article, ArticleAnalysis
from backend.prompts import CLASSIFIER_SYSTEM

logger = logging.getLogger(__name__)


def _truncate_content(content: str, limit: int = 1000) -> str:
    """긴 본문을 머리+꼬리 구조로 자른다.

    한국 뉴스는 도입부에서 사실 요약, 결론부에서 맥락/수치를 제시하는 경우가 많아
    앞 1000자만 남기면 결론 정보가 잘린다. limit 초과 시 앞 60% + 뒤 40% 유지.
    """
    if len(content) <= limit:
        return content
    head = int(limit * 0.6)
    tail = limit - head
    return content[:head] + "\n…\n" + content[-tail:]


async def classify_article(article: Article) -> dict:
    """단일 기사를 분류/분석"""
    body = _truncate_content(article.content or "", limit=1000)
    user_message = f"""다음 뉴스 기사를 분석해주세요.

제목: {article.title}
매체: {article.source_name} ({article.source_type})
요약: {article.description or '없음'}
본문: {body}"""

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
    parsed = ClassificationOut.model_validate(result["content"])

    analysis = ArticleAnalysis(
        article_id=article.id,
        category=parsed.category,
        keywords=parsed.keywords,
        entities=[e.model_dump() for e in parsed.entities],
        sentiment=parsed.sentiment,
        importance_score=parsed.importance_score,
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
        try:
            parsed = ClassificationOut.model_validate(result["content"])
        except Exception as e:
            logger.warning(f"스키마 검증 실패 [{article.id}] {article.title[:30]}: {e}")
            continue
        analysis = ArticleAnalysis(
            article_id=article.id,
            category=parsed.category,
            keywords=parsed.keywords,
            entities=[e.model_dump() for e in parsed.entities],
            sentiment=parsed.sentiment,
            importance_score=parsed.importance_score,
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
    """오늘 DB 전체 기준, 키워드를 보도한 '고유 매체 수'로 importance_score 보정.

    편집국 관행상 '주요 이슈'는 단일 기사의 주관적 중요도가 아니라 '여러 매체가
    교차 보도한 사안'으로 판단된다. 배치 로컬이 아닌 하루 단위 DB 집계를 써야
    시간에 걸쳐 누적되는 consensus가 점수에 반영된다.

    각 분석 건에 transient 속성 `_source_count` 를 부여해 스케줄러의 속보 판정
    조건(source_count >= 2)에서 사용할 수 있도록 한다.
    """
    today = date.today()

    stmt = (
        select(ArticleAnalysis.keywords, Article.source_name)
        .join(Article, Article.id == ArticleAnalysis.article_id)
        .where(func.date(Article.collected_at) == today)
    )
    result = await db.execute(stmt)
    keyword_sources: dict[str, set] = {}
    for keywords, source_name in result.all():
        if not keywords:
            continue
        for kw in keywords:
            keyword_sources.setdefault(kw, set()).add(source_name)

    for a in analyses:
        article_keywords = a.keywords or []
        if not article_keywords:
            a._source_count = 1  # type: ignore[attr-defined]
            continue
        # 해당 기사 키워드 중 가장 많은 매체가 공통 보도한 수
        max_src = max(
            (len(keyword_sources.get(kw, set())) for kw in article_keywords),
            default=1,
        )
        a._source_count = max_src  # type: ignore[attr-defined]
        # 매체 2곳: +0.7, 3곳: +1.4, 4+곳: +2.0
        boost = min(2.0, max(0, max_src - 1) * 0.7)
        if boost > 0:
            new_score = min(10.0, a.importance_score + boost)
            if new_score != a.importance_score:
                a.importance_score = new_score

    await db.commit()
    logger.info(
        f"매체수 기반 중요도 보정 완료 ({len(analyses)}건, "
        f"키워드 {len(keyword_sources)}종)"
    )
