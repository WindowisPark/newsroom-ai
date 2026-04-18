"""의제 설정(Agenda Setting) 분석기

1단계: DB 기반 키워드 클러스터링 + 빈도/매체 수 사전 집계
2단계: 집계 결과를 LLM에 전달하여 의제 도출 (Sonnet 4.6)
"""

import logging
import re
from collections import Counter
from datetime import date, datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import MODEL_FOR, call_llm
from backend.analyzers.schemas import AgendaOut
from backend.database.models import Article, ArticleAnalysis, AgendaReport
from backend.prompts import AGENDA_SYSTEM

logger = logging.getLogger(__name__)


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

    # ── 1단계: DB 기반 사전 집계 ──
    pre_analysis = _pre_aggregate(rows)

    # ── 2단계: 집계 결과 + 기사 목록을 LLM에 전달 ──
    articles_summary = _build_articles_summary(rows)

    user_message = f"""오늘({target_date}) 수집된 뉴스 {len(rows)}건을 분석하여
뉴스룸이 주목해야 할 상위 {top_n}개 핵심 의제를 도출해주세요.

=== 사전 집계 (키워드 빈도 + 매체 수) ===
{pre_analysis}

=== 수집 기사 분석 데이터 ===
{articles_summary}"""

    llm_result = await call_llm(
        system_prompt=AGENDA_SYSTEM,
        user_message=user_message,
        model=MODEL_FOR["agenda"],
        max_tokens=4096,
    )

    parsed = AgendaOut.model_validate(llm_result["content"])

    # 관련 기사 ID 매핑
    top_issues: list[dict] = []
    for issue_model in parsed.top_issues:
        issue = issue_model.model_dump()
        matched_ids = _match_article_ids(issue, rows)
        issue["related_article_ids"] = [str(aid) for aid in matched_ids]
        issue["article_count"] = len(matched_ids)
        issue["source_count"] = _count_sources(issue, rows)
        top_issues.append(issue)

    # DB 저장
    report = AgendaReport(
        date=target_date,
        top_issues=top_issues,
        analysis_summary=parsed.analysis_summary,
        generated_at=datetime.now(timezone.utc),
        model_used=llm_result["model_used"],
        prompt_tokens=llm_result["prompt_tokens"],
        completion_tokens=llm_result["completion_tokens"],
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return report


def _pre_aggregate(rows: list) -> str:
    """DB 데이터 기반 키워드 빈도, 카테고리 분포, 매체 다양성 사전 집계"""
    keyword_counter: Counter = Counter()
    keyword_sources: dict[str, set] = {}
    category_counter: Counter = Counter()
    sentiment_counter: Counter = Counter()
    total_importance = 0.0

    for article, analysis in rows:
        # 키워드 빈도 + 해당 키워드를 보도한 매체 수
        for kw in analysis.keywords:
            keyword_counter[kw] += 1
            keyword_sources.setdefault(kw, set()).add(article.source_name)

        category_counter[analysis.category] += 1
        sentiment_counter[analysis.sentiment] += 1
        total_importance += analysis.importance_score

    lines = []

    # 상위 키워드 (빈도 + 매체 수)
    lines.append("▶ 상위 키워드 (빈도순, 매체수 표시):")
    for kw, count in keyword_counter.most_common(15):
        src_count = len(keyword_sources[kw])
        lines.append(f"  - {kw}: {count}건, {src_count}개 매체")

    # 카테고리 분포
    lines.append(f"\n▶ 카테고리 분포:")
    for cat, count in category_counter.most_common():
        lines.append(f"  - {cat}: {count}건")

    # 감성 분포
    lines.append(f"\n▶ 감성 분포:")
    for sent, count in sentiment_counter.most_common():
        lines.append(f"  - {sent}: {count}건")

    # 평균 중요도
    avg_importance = total_importance / len(rows) if rows else 0
    lines.append(f"\n▶ 평균 중요도: {avg_importance:.1f}/10")
    lines.append(f"▶ 총 기사: {len(rows)}건, 매체: {len(set(r[0].source_name for r in rows))}곳")

    return "\n".join(lines)


def _build_articles_summary(rows: list) -> str:
    """기사 데이터를 LLM 입력용 텍스트로 요약 (제목 + 키워드 중심, 토큰 절약)"""
    lines = []
    for article, analysis in rows[:50]:
        lines.append(
            f"- [{analysis.category}] {article.title} "
            f"(매체: {article.source_name}, 중요도: {analysis.importance_score}, "
            f"감성: {analysis.sentiment}, "
            f"키워드: {', '.join(analysis.keywords[:3])})"
        )
    return "\n".join(lines)


def _title_contains(title: str, kw: str) -> bool:
    """제목에 키워드가 '의미 있게' 포함되는지 판정.

    원래 코드는 `kw in title` 로 단순 substring 매칭이라 "정" 이 "정치/정부/정책" 을
    모두 매치하여 article_count / source_count 가 부풀려지는 문제가 있었다.
    -   영숫자 키워드 ("AI", "IT", "2026"): 단어 경계 매칭
    -   한글 키워드: 3자 이상만 substring 매칭 (2자 이하는 analysis.keywords 교집합만 허용)
    """
    if not kw:
        return False
    if kw.isascii():
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(kw)}(?![A-Za-z0-9])", title))
    if len(kw) < 3:
        return False
    return kw in title


def _match_article_ids(issue: dict, rows: list) -> list:
    """이슈 키워드와 매칭되는 기사 ID 추출 (키워드 + 분석 키워드 교차 매칭)"""
    issue_keywords = set(issue.get("key_keywords", []))
    if not issue_keywords:
        return []

    matched = []
    for article, analysis in rows:
        # 분석 키워드와의 교집합 확인 (정확한 매칭)
        article_keywords = set(analysis.keywords)
        if issue_keywords & article_keywords:
            matched.append(article.id)
            continue
        # fallback: 제목 경계 매칭 (한글 ≥3자 또는 영숫자 단어 경계)
        title = article.title
        if any(_title_contains(title, kw) for kw in issue_keywords):
            matched.append(article.id)

    return matched[:10]


def _count_sources(issue: dict, rows: list) -> int:
    """이슈 관련 기사를 보도한 매체 수 (키워드 교차 매칭 기반)"""
    issue_keywords = set(issue.get("key_keywords", []))
    if not issue_keywords:
        return 0

    sources = set()
    for article, analysis in rows:
        article_keywords = set(analysis.keywords)
        if issue_keywords & article_keywords:
            sources.add(article.source_name)
        elif any(_title_contains(article.title, kw) for kw in issue_keywords):
            sources.add(article.source_name)

    return len(sources)
