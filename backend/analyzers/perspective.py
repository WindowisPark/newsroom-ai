"""관점 비교 분석기 - Sonnet 4.6 (국내 vs 외신)"""

import logging
from datetime import date, datetime, timezone

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import MODEL_FOR, call_llm
from backend.database.models import Article, ArticleAnalysis, PerspectiveReport
from backend.prompts import PERSPECTIVE_SYSTEM

logger = logging.getLogger(__name__)


# 외신 검색 키워드 생성용 — Haiku 에 직접 system prompt 로 주입.
# LLM_client.call_llm 이 JSON 응답을 요구하므로 구조화 JSON 로 받음.
_TRANSLATE_SYSTEM = """\
You convert a Korean news topic into English search keywords for foreign news.

Rules:
- Produce 3~5 English keywords/phrases (people, places, organizations, events).
- Always use the standard English spelling used by Reuters/BBC/AP.
  Korean president names, country names, currencies etc. should map to their
  English equivalents (e.g. "호르무즈 해협" → "Strait of Hormuz", "윤석열" → "Yoon Suk-yeol").
- If the Korean topic contains a proper noun with no common English form, transliterate.
- Return STRICT JSON only:
{"english_terms": ["term1", "term2", ...]}
"""


async def _expand_foreign_search_terms(topic: str) -> list[str]:
    """Korean topic → 외신 검색용 English 키워드 리스트.

    Haiku 1회 호출. 실패 시 한국어 원문을 그대로 폴백(매칭 0건일 가능성 높음).
    """
    try:
        result = await call_llm(
            system_prompt=_TRANSLATE_SYSTEM,
            user_message=f"Korean topic: {topic}\n\nReturn English search keywords as JSON.",
            model=MODEL_FOR["classify"],  # Haiku — 번역 수준에 충분
            max_tokens=256,
            temperature=0.1,
        )
        terms = result["content"].get("english_terms", [])
        terms = [t.strip() for t in terms if isinstance(t, str) and t.strip()]
        if not terms:
            return [topic]
        logger.info(f"Perspective topic '{topic}' → foreign terms: {terms}")
        return terms
    except Exception as e:
        logger.warning(f"외신 키워드 번역 실패, 한국어 폴백 ({e})")
        return [topic]


async def compare_perspectives(
    db: AsyncSession,
    topic: str,
    target_date: date | None = None,
) -> PerspectiveReport:
    """동일 주제에 대한 국내 vs 외신 관점 비교 분석"""
    if target_date is None:
        target_date = date.today()

    # 국내는 한국어 topic 그대로 split
    domestic_terms = [t for t in topic.split() if t]
    domestic_articles = await _fetch_articles_by_topic(
        db, domestic_terms, target_date, source_type="domestic"
    )

    # 외신은 한국어 → 영어 번역 키워드로 검색 (언어 장벽 해결)
    foreign_terms = await _expand_foreign_search_terms(topic)
    foreign_articles = await _fetch_articles_by_topic(
        db, foreign_terms, target_date, source_type="foreign"
    )

    if not domestic_articles and not foreign_articles:
        raise ValueError(f"No articles found for topic '{topic}' on {target_date}")

    # LLM 분석 요청
    user_message = _build_comparison_prompt(topic, domestic_articles, foreign_articles)

    llm_result = await call_llm(
        system_prompt=PERSPECTIVE_SYSTEM,
        user_message=user_message,
        model=MODEL_FOR["perspective"],
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
    search_terms: list[str],
    target_date: date,
    source_type: str,
) -> list[Article]:
    """주어진 검색어 리스트와 소스 타입으로 기사 조회.

    search_terms 는 domestic 은 한국어, foreign 은 영어로 미리 분기된 상태.
    """
    if not search_terms:
        return []
    conditions = [Article.title.ilike(f"%{t}%") for t in search_terms if t]
    if not conditions:
        return []

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
