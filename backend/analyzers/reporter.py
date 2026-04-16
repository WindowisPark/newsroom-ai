"""브리핑 리포트 생성기 - Sonnet 4.6"""

from datetime import date, datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import SONNET_MODEL, call_llm
from backend.database.models import Article, ArticleAnalysis, BriefingReport
from backend.prompts import BRIEFING_SYSTEM


async def generate_briefing(
    db: AsyncSession,
    target_date: date | None = None,
) -> BriefingReport:
    """종합 브리핑 리포트 생성"""
    if target_date is None:
        target_date = date.today()

    # 분석 완료된 기사 중요도순 조회
    stmt = (
        select(Article, ArticleAnalysis)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(func.date(Article.collected_at) == target_date)
        .order_by(ArticleAnalysis.importance_score.desc())
        .limit(30)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        raise ValueError(f"No analyzed articles found for {target_date}")

    # 카테고리별 그룹핑
    by_category: dict[str, list] = {}
    for article, analysis in rows:
        cat = analysis.category
        by_category.setdefault(cat, []).append((article, analysis))

    user_message = _build_briefing_prompt(target_date, rows, by_category)

    llm_result = await call_llm(
        system_prompt=BRIEFING_SYSTEM,
        user_message=user_message,
        model=SONNET_MODEL,
        max_tokens=4096,
    )

    content = llm_result["content"]

    report = BriefingReport(
        date=target_date,
        headline=content.get("headline", ""),
        summary=content.get("summary", ""),
        sections=content.get("sections", []),
        generated_at=datetime.now(timezone.utc),
        model_used=llm_result["model_used"],
        prompt_tokens=llm_result["prompt_tokens"],
        completion_tokens=llm_result["completion_tokens"],
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return report


def _build_briefing_prompt(
    target_date: date,
    all_rows: list,
    by_category: dict[str, list],
) -> str:
    """브리핑 리포트 생성용 프롬프트"""
    lines = [
        f"오늘({target_date}) 수집/분석된 주요 뉴스 {len(all_rows)}건을 바탕으로",
        "종합 브리핑 리포트를 작성해주세요.\n",
    ]

    for cat, items in by_category.items():
        lines.append(f"=== {cat.upper()} ({len(items)}건) ===")
        for article, analysis in items[:5]:
            lines.append(
                f"- {article.title} (중요도: {analysis.importance_score}, "
                f"감성: {analysis.sentiment})"
            )
            if article.description:
                lines.append(f"  요약: {article.description[:150]}")
        lines.append("")

    return "\n".join(lines)
