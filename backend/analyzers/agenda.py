"""의제 설정(Agenda Setting) 분석기 - Sonnet 4.6"""

from datetime import date, datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import MODEL_FOR, call_llm
from backend.database.models import Article, ArticleAnalysis, AgendaReport
from backend.prompts import AGENDA_SYSTEM


async def analyze_agenda(
    db: AsyncSession,
    target_date: date | None = None,
    top_n: int = 5,
) -> AgendaReport:
    """의제 설정 분석 수행 및 저장"""
    if target_date is None:
        target_date = date.today()

    # 해당 날짜 분석 완료된 기사 조회
    stmt = (
        select(Article, ArticleAnalysis)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(func.date(Article.collected_at) == target_date)
        .order_by(ArticleAnalysis.importance_score.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        raise ValueError(f"No analyzed articles found for {target_date}")

    # LLM에 전달할 기사 요약 데이터 구성
    articles_summary = _build_articles_summary(rows)

    user_message = f"""오늘({target_date}) 수집된 뉴스 {len(rows)}건을 분석하여
뉴스룸이 주목해야 할 상위 {top_n}개 핵심 의제를 도출해주세요.

=== 수집 기사 분석 데이터 ===
{articles_summary}"""

    llm_result = await call_llm(
        system_prompt=AGENDA_SYSTEM,
        user_message=user_message,
        model=MODEL_FOR["agenda"],
        max_tokens=4096,
    )

    content = llm_result["content"]

    # 관련 기사 ID 매핑
    top_issues = content.get("top_issues", [])
    for issue in top_issues:
        matched_ids = _match_article_ids(issue, rows)
        issue["related_article_ids"] = [str(aid) for aid in matched_ids]
        issue["article_count"] = len(matched_ids)
        issue["source_count"] = len(set(
            row[0].source_name for row in rows
            if any(kw in (row[0].title + (row[0].description or ""))
                   for kw in issue.get("key_keywords", []))
        ))

    # DB 저장
    report = AgendaReport(
        date=target_date,
        top_issues=top_issues,
        analysis_summary=content.get("analysis_summary", ""),
        generated_at=datetime.now(timezone.utc),
        model_used=llm_result["model_used"],
        prompt_tokens=llm_result["prompt_tokens"],
        completion_tokens=llm_result["completion_tokens"],
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return report


def _build_articles_summary(rows: list) -> str:
    """기사 데이터를 LLM 입력용 텍스트로 요약"""
    lines = []
    for article, analysis in rows[:50]:  # 최대 50건
        lines.append(
            f"- [{analysis.category}] {article.title} "
            f"(매체: {article.source_name}, 중요도: {analysis.importance_score}, "
            f"감성: {analysis.sentiment}, "
            f"키워드: {', '.join(analysis.keywords[:3])})"
        )
    return "\n".join(lines)


def _match_article_ids(issue: dict, rows: list) -> list:
    """이슈 키워드와 매칭되는 기사 ID 추출"""
    keywords = issue.get("key_keywords", [])
    matched = []
    for article, analysis in rows:
        text = article.title + " " + (article.description or "")
        if any(kw in text for kw in keywords):
            matched.append(article.id)
    return matched[:10]  # 최대 10건
