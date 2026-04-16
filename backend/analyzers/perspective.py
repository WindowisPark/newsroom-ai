"""관점 비교 분석기 - Sonnet 4.6 (국내 vs 외신)"""

from datetime import date, datetime, timezone

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import SONNET_MODEL, call_llm
from backend.database.models import Article, ArticleAnalysis, PerspectiveReport
from backend.prompts import PERSPECTIVE_SYSTEM


async def compare_perspectives(
    db: AsyncSession,
    topic: str,
    target_date: date | None = None,
) -> PerspectiveReport:
    """동일 주제에 대한 국내 vs 외신 관점 비교 분석"""
    if target_date is None:
        target_date = date.today()

    # 국내 기사 조회
    domestic_articles = await _fetch_articles_by_topic(
        db, topic, target_date, source_type="domestic"
    )

    # 외신 기사 조회
    foreign_articles = await _fetch_articles_by_topic(
        db, topic, target_date, source_type="foreign"
    )

    if not domestic_articles and not foreign_articles:
        raise ValueError(f"No articles found for topic '{topic}' on {target_date}")

    # LLM 분석 요청
    user_message = _build_comparison_prompt(topic, domestic_articles, foreign_articles)

    llm_result = await call_llm(
        system_prompt=PERSPECTIVE_SYSTEM,
        user_message=user_message,
        model=SONNET_MODEL,
        max_tokens=4096,
    )

    content = llm_result["content"]

    # 대표 기사 ID 매핑
    domestic_data = content.get("domestic", {})
    domestic_data["representative_articles"] = [
        {"id": str(a.id), "title": a.title, "source_name": a.source_name, "url": a.url}
        for a in domestic_articles[:3]
    ]

    foreign_data = content.get("foreign", {})
    foreign_data["representative_articles"] = [
        {"id": str(a.id), "title": a.title, "source_name": a.source_name, "url": a.url}
        for a in foreign_articles[:3]
    ]

    # DB 저장
    report = PerspectiveReport(
        topic=topic,
        date=target_date,
        domestic_analysis=domestic_data,
        foreign_analysis=foreign_data,
        comparison=content.get("comparison", {}),
        generated_at=datetime.now(timezone.utc),
        model_used=llm_result["model_used"],
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return report


async def _fetch_articles_by_topic(
    db: AsyncSession,
    topic: str,
    target_date: date,
    source_type: str,
) -> list[Article]:
    """주제 키워드와 소스 타입으로 기사 조회"""
    keywords = topic.split()
    conditions = [Article.title.ilike(f"%{kw}%") for kw in keywords]

    stmt = (
        select(Article)
        .where(
            func.date(Article.collected_at) == target_date,
            Article.source_type == source_type,
            or_(*conditions),
        )
        .order_by(Article.published_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _build_comparison_prompt(
    topic: str,
    domestic: list[Article],
    foreign: list[Article],
) -> str:
    """관점 비교용 LLM 프롬프트 구성"""
    lines = [f"주제: {topic}\n"]

    lines.append("=== 국내 매체 보도 ===")
    if domestic:
        for a in domestic[:10]:
            lines.append(f"- [{a.source_name}] {a.title}")
            if a.description:
                lines.append(f"  요약: {a.description[:200]}")
    else:
        lines.append("(관련 국내 기사 없음)")

    lines.append("\n=== 외신 보도 ===")
    if foreign:
        for a in foreign[:10]:
            lines.append(f"- [{a.source_name}] {a.title}")
            if a.description:
                lines.append(f"  요약: {a.description[:200]}")
    else:
        lines.append("(관련 외신 기사 없음)")

    lines.append("\n위 기사들을 바탕으로 국내 매체와 외신의 관점 차이를 분석해주세요.")
    return "\n".join(lines)
