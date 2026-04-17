"""헤드라인 추천 + 배경 타임라인 생성기 - Sonnet 4.6"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import MODEL_FOR, call_llm
from backend.database.models import Article, HeadlineRecommendation
from backend.prompts import HEADLINE_SYSTEM, TIMELINE_SYSTEM


async def recommend_headlines(
    db: AsyncSession,
    topic: str,
    article_ids: list[UUID] | None = None,
    style: str = "neutral",
) -> dict:
    """이슈에 대한 헤드라인 3선 추천"""
    articles_text = await _gather_article_context(db, topic, article_ids)

    user_message = f"""다음 이슈에 대해 기사 제목 3가지를 추천해주세요.

이슈/주제: {topic}
톤앤매너: {style}

=== 관련 기사 ===
{articles_text}"""

    llm_result = await call_llm(
        system_prompt=HEADLINE_SYSTEM,
        user_message=user_message,
        model=MODEL_FOR["headline"],
        max_tokens=2048,
    )

    content = llm_result["content"]
    return {
        "topic": topic,
        "generated_at": datetime.now(timezone.utc),
        "headlines": content.get("headlines", []),
        "model_used": llm_result["model_used"],
    }


async def generate_timeline(
    db: AsyncSession,
    topic: str,
    article_ids: list[UUID] | None = None,
) -> dict:
    """이슈 배경 타임라인 생성"""
    articles_text = await _gather_article_context(db, topic, article_ids)

    user_message = f"""다음 이슈의 배경 타임라인을 작성해주세요.

이슈/주제: {topic}

=== 관련 기사 ===
{articles_text}"""

    llm_result = await call_llm(
        system_prompt=TIMELINE_SYSTEM,
        user_message=user_message,
        model=MODEL_FOR["timeline"],
        max_tokens=4096,
    )

    content = llm_result["content"]
    return {
        "topic": topic,
        "generated_at": datetime.now(timezone.utc),
        "timeline": content.get("timeline", []),
        "context_summary": content.get("context_summary", ""),
        "model_used": llm_result["model_used"],
    }


async def recommend_and_save(
    db: AsyncSession,
    topic: str,
    article_ids: list[UUID] | None = None,
    style: str = "neutral",
    include_timeline: bool = True,
) -> HeadlineRecommendation:
    """헤드라인 추천 + 타임라인을 생성하고 DB 저장"""
    headline_result = await recommend_headlines(db, topic, article_ids, style)

    timeline_data = None
    context_summary = None
    if include_timeline:
        timeline_result = await generate_timeline(db, topic, article_ids)
        timeline_data = timeline_result.get("timeline")
        context_summary = timeline_result.get("context_summary")

    rec = HeadlineRecommendation(
        topic=topic,
        headlines=headline_result.get("headlines", []),
        timeline=timeline_data,
        context_summary=context_summary,
        generated_at=datetime.now(timezone.utc),
        model_used=headline_result.get("model_used", ""),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)

    return rec


async def _gather_article_context(
    db: AsyncSession,
    topic: str,
    article_ids: list[UUID] | None = None,
) -> str:
    """관련 기사 텍스트 수집"""
    if article_ids:
        stmt = select(Article).where(Article.id.in_(article_ids))
    else:
        keywords = topic.split()
        from sqlalchemy import or_
        conditions = [Article.title.ilike(f"%{kw}%") for kw in keywords]
        stmt = (
            select(Article)
            .where(or_(*conditions))
            .order_by(Article.published_at.desc())
            .limit(10)
        )

    result = await db.execute(stmt)
    articles = result.scalars().all()

    if not articles:
        return "(관련 기사 없음 - 주제에 대한 일반적 지식을 바탕으로 작성해주세요)"

    lines = []
    for a in articles:
        lines.append(f"- [{a.source_name}] {a.title}")
        if a.description:
            lines.append(f"  {a.description[:200]}")
    return "\n".join(lines)
