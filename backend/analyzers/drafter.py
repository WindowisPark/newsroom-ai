"""기사 초안 생성기 - Sonnet 4.6 + RAG (서울신문 자사 기사 참조)

다중 기사를 교차 참조하여 역피라미드·6하원칙 기반 초안 1건을 생성한다.
서울신문 자사 기사를 retrieval 해 참고 자료·톤 앵커로 LLM에 주입한다.
저장하지 않고 응답만 반환 (stateless).

근거: docs/REFERENCES.md §1 (RAG 정석), §2 (few-shot style).
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import String, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.agenda import _title_contains
from backend.analyzers.llm_client import MODEL_FOR, call_llm
from backend.analyzers.schemas import DraftOut, SourceRef
from backend.database.models import Article, ArticleAnalysis
from backend.prompts import DRAFT_SYSTEM


# ── 매체 분류 ──
# 한국 언론 관행상 자사·통신사·외신은 본문에 매체명 인용 가능.
# 국내 경쟁 일간지는 직접 인용하지 않고 '업계에 따르면' 등 익명 처리하거나
# 자사에서 별도 취재·확인한 것처럼 서술한다. 근거: docs/REFERENCES.md §3.
OWN_SOURCE_NAMES = ["서울신문"]
AGENCY_SOURCE_NAMES = [
    "연합뉴스",
    # 외신·통신사 (NewsAPI source_name 과 RSS FOREIGN_FEEDS 키)
    "Reuters", "AP", "AFP",
    "BBC", "The Guardian", "Al Jazeera", "NYT",
    "CNN", "BBC News", "Associated Press",
]
COMPETITOR_DAILY_NAMES = [
    "한겨레", "한국경제", "조선일보", "동아일보",
    "중앙일보", "경향신문", "매일경제", "국민일보", "광주일보", "서울경제",
]

# Retrieval 파라미터
_RECENCY_WINDOW_DAYS = 90
_TOP_REFERENCES = 3
_TOP_BACKGROUND = 3
_SNIPPET_CHARS_DESC = 200
_SNIPPET_CHARS_LEAD = 300
# Python rerank 전 SQL 레벨에서 축소할 후보 상한 — 수만 건 기사 중
# 티어·키워드·recency 필터로 이 수 이하로 줄인 뒤 Python 재랭킹.
_RETRIEVAL_CANDIDATE_LIMIT = 200

# _source_tier 와 동일한 티어 → 매체명 리스트 매핑.
# SQL 레벨 source_name 필터에 사용.
_TIER_TO_SOURCE_NAMES: dict[str, list[str]] = {
    "own": OWN_SOURCE_NAMES,
    "agency": AGENCY_SOURCE_NAMES,
    "competitor": COMPETITOR_DAILY_NAMES,
}


def _source_tier(source_name: str) -> str:
    """매체명 → 'own' / 'agency' / 'competitor' / 'other' 층위 반환"""
    if source_name in OWN_SOURCE_NAMES:
        return "own"
    if source_name in AGENCY_SOURCE_NAMES:
        return "agency"
    if source_name in COMPETITOR_DAILY_NAMES:
        return "competitor"
    # 부분 매칭 (naver 추출 도메인 대응)
    lowered = source_name.lower()
    for name in AGENCY_SOURCE_NAMES:
        if name.lower() in lowered:
            return "agency"
    for name in COMPETITOR_DAILY_NAMES:
        if name.lower() in lowered or name in source_name:
            return "competitor"
    return "other"


async def generate_draft(
    db: AsyncSession,
    article_ids: list[UUID],
    style: str = "straight",
    topic_hint: str | None = None,
) -> dict:
    """주어진 기사들을 바탕으로 초안 1건 생성 (RAG 적용)."""
    if not article_ids:
        raise ValueError("article_ids must not be empty")

    # 기사 조회
    stmt = select(Article).where(Article.id.in_(article_ids))
    result = await db.execute(stmt)
    articles = list(result.scalars().all())

    if not articles:
        raise LookupError("no matching articles found")

    missing = set(article_ids) - {a.id for a in articles}
    if missing:
        raise LookupError(f"articles not found: {sorted(missing)}")

    # ── RAG: 자사·통신사(references) + 경쟁 일간지(background) 분리 검색 ──
    query_keywords = _collect_query_keywords(articles, topic_hint)
    dominant_category = _dominant_category(articles)
    references = await _retrieve_by_tier(
        db, query_keywords, article_ids,
        tiers=("own", "agency"),
        top_n=_TOP_REFERENCES,
    )
    exclude_ids = article_ids + [r["id"] for r in references]
    background = await _retrieve_by_tier(
        db, query_keywords, exclude_ids,
        tiers=("competitor",),
        top_n=_TOP_BACKGROUND,
    )
    style_anchor = await _retrieve_style_anchor(
        db, dominant_category, [r["id"] for r in references]
    )

    # LLM 입력 구성
    articles_text = _build_articles_block(articles)
    refs_text = _build_references_block(references)
    background_text = _build_background_block(background)
    anchor_text = _build_style_anchor_block(style_anchor)
    topic_line = f"\n진입 맥락(선택 헤드라인/주제): {topic_hint}\n" if topic_hint else ""

    user_message = f"""다음 관련 기사들을 바탕으로 서울신문 편집국 기준 초안 1건을 작성해주세요.

style: {style}{topic_line}

=== 관련 기사 ({len(articles)}건) ===
{articles_text}
{refs_text}{background_text}{anchor_text}"""

    llm_result = await call_llm(
        system_prompt=DRAFT_SYSTEM,
        user_message=user_message,
        model=MODEL_FOR["draft"],
        max_tokens=8192,
        temperature=0.4,
    )

    # 스키마 검증 — 실패 시 ValueError raise → 라우터가 400/500 처리
    parsed = DraftOut.model_validate(llm_result["content"])

    # sources 가 비면 입력 기사로 자동 채움 — 단, 경쟁 일간지는 제외
    # (한국 편집 관행: 국내 일간지 간 상호 인용 지양)
    if not parsed.sources:
        parsed.sources = [
            SourceRef(
                name=a.source_name,
                url=a.url,
                published_at=a.published_at.isoformat() if a.published_at else None,
            )
            for a in articles
            if _source_tier(a.source_name) != "competitor"
        ]

    # references/background 는 LLM 출력을 신뢰하지 않고 서버 검색 결과로 덮어쓴다 (투명성)
    parsed.references = [_ref_to_source(r) for r in references]
    parsed.background_sources = [_ref_to_source(r) for r in background]
    parsed.style_anchor = _ref_to_source(style_anchor) if style_anchor else None

    draft_dict = parsed.model_dump()

    # 이종 judge(Gemini) 품질 판독 — 실패해도 초안 생성은 보존
    quality_review: dict | None = None
    review_model: str | None = None
    review_prompt_tokens = 0
    review_completion_tokens = 0
    try:
        from backend.analyzers.reviewer import review_draft

        review_result = await review_draft(draft_dict)
        quality_review = review_result["review"]
        review_model = review_result["model_used"]
        review_prompt_tokens = review_result["prompt_tokens"]
        review_completion_tokens = review_result["completion_tokens"]
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).warning(f"Draft 판독 실패 (초안은 유지): {e}")

    return {
        "draft": draft_dict,
        "generated_at": datetime.now(timezone.utc),
        "model_used": llm_result["model_used"],
        "prompt_tokens": llm_result["prompt_tokens"],
        "completion_tokens": llm_result["completion_tokens"],
        "quality_review": quality_review,
        "review_model": review_model,
        "review_prompt_tokens": review_prompt_tokens,
        "review_completion_tokens": review_completion_tokens,
    }


# ── RAG: 검색 ───────────────────────────────────────────────

def _collect_query_keywords(articles: list[Article], topic_hint: str | None) -> list[str]:
    """입력 기사 + topic_hint 에서 검색 키워드 후보 수집"""
    counter: Counter = Counter()
    for a in articles:
        if a.analysis and a.analysis.keywords:
            for kw in a.analysis.keywords:
                counter[kw] += 1
    # 상위 키워드 6개 + topic_hint 토큰
    keywords = [kw for kw, _ in counter.most_common(6)]
    if topic_hint:
        # 공백 기준 단순 분할 (한글·영문 섞여도 substring 검색이라 OK)
        keywords.extend([t for t in topic_hint.split() if len(t) >= 2])
    # 중복 제거 (순서 유지)
    seen = set()
    dedup = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            dedup.append(k)
    return dedup


def _dominant_category(articles: list[Article]) -> str | None:
    """입력 기사들의 가장 많이 등장한 카테고리 반환 (톤 앵커 선택용)"""
    counter: Counter = Counter()
    for a in articles:
        if a.analysis and a.analysis.category:
            counter[a.analysis.category] += 1
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _build_tier_filter(tiers: tuple[str, ...]):
    """티어 → source_name SQL 필터.

    own 은 정확 일치(서울신문 브랜드 혼재 방지), agency/competitor 는
    naver 추출 도메인 변이(예: 'BBC News' → BBC) 수용을 위해 ILIKE.
    """
    conditions = []
    for tier in tiers:
        for name in _TIER_TO_SOURCE_NAMES.get(tier, []):
            if tier == "own":
                conditions.append(Article.source_name == name)
            else:
                conditions.append(Article.source_name.ilike(f"%{name}%"))
    return conditions


def _build_keyword_filter(keywords: list[str], dialect_name: str):
    """키워드 매칭 SQL 필터 — postgres 는 JSONB has_any, 그 외는 ILIKE fallback.

    analysis.keywords 배열에 주어진 키워드 중 하나라도 포함되거나,
    기사 제목에 키워드가 substring 으로 등장하는 경우를 후보로 선별한다.
    """
    title_conditions = [Article.title.ilike(f"%{kw}%") for kw in keywords if kw]
    if dialect_name == "postgresql":
        # JSONB has_any(키워드 배열) — GIN 인덱스(ix_article_analyses_keywords_gin) 활용
        overlap = ArticleAnalysis.keywords.cast(JSONB).has_any(pg_array(keywords, type_=String))
        return [overlap, *title_conditions]
    # SQLite 테스트 환경: JSON 컬럼 텍스트 substring 으로 근사 — 수만 건이 없으므로 OK
    json_like_conditions = [
        ArticleAnalysis.keywords.cast(String).ilike(f'%"{kw}"%') for kw in keywords if kw
    ]
    return [*json_like_conditions, *title_conditions]


async def _retrieve_by_tier(
    db: AsyncSession,
    keywords: list[str],
    exclude_ids: list[UUID],
    tiers: tuple[str, ...],
    top_n: int,
) -> list[dict]:
    """지정된 소스 층위 내에서 키워드 매칭 + recency 점수 상위 N건 반환.

    tiers: ('own', 'agency') → references 용 / ('competitor',) → background 용
    Reranking: score = 0.6 × (키워드 매칭 수) + 0.4 × recency_score

    파이프라인:
      1) SQL 레벨에서 티어(source_name) + exclude_ids + recency window
         + 키워드 후보 필터(postgres 는 JSONB has_any + ILIKE, 그 외는 ILIKE fallback)
         로 후보를 _RETRIEVAL_CANDIDATE_LIMIT 이하로 축소.
      2) Python 에서 정확 매칭 수 계산 + recency 가중 재랭킹 → top_n.

    개선 이유: 이전 구현은 기사 테이블 전체를 메모리로 로드한 뒤 Python
    으로 티어·키워드를 걸러내 수만 건 이상에서 OOM·지연 발생.
    """
    if not keywords or not tiers:
        return []

    window_start = datetime.now(timezone.utc) - timedelta(days=_RECENCY_WINDOW_DAYS)
    tier_conditions = _build_tier_filter(tiers)
    if not tier_conditions:
        return []

    dialect_name = db.bind.dialect.name if db.bind else "postgresql"
    kw_conditions = _build_keyword_filter(keywords, dialect_name)

    stmt = (
        select(Article, ArticleAnalysis)
        .outerjoin(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(or_(*tier_conditions))
        .where(
            (Article.published_at.is_(None)) | (Article.published_at >= window_start)
        )
    )
    if exclude_ids:
        stmt = stmt.where(~Article.id.in_(exclude_ids))
    if kw_conditions:
        stmt = stmt.where(or_(*kw_conditions))
    stmt = stmt.order_by(Article.published_at.desc().nullslast()).limit(
        _RETRIEVAL_CANDIDATE_LIMIT
    )

    rows = list((await db.execute(stmt)).all())
    if not rows:
        return []

    kw_set = set(keywords)
    scored: list[tuple[float, Article, int]] = []

    for art, analysis in rows:
        # SQL 필터가 approximate matching 이므로 Python 에서 정확 재검사
        match_count = 0
        if analysis and analysis.keywords:
            match_count = len(kw_set & set(analysis.keywords))
        if match_count == 0:
            if any(_title_contains(art.title, kw) for kw in keywords):
                match_count = 1
        if match_count == 0:
            continue

        pub = art.published_at or art.collected_at
        if pub and pub >= window_start:
            elapsed = (datetime.now(timezone.utc) - pub).total_seconds()
            recency = max(0.0, 1.0 - elapsed / (_RECENCY_WINDOW_DAYS * 86400))
        else:
            recency = 0.0

        score = 0.6 * match_count + 0.4 * recency
        scored.append((score, art, match_count))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_article_to_dict(art) for _, art, _ in scored[:top_n]]


async def _retrieve_style_anchor(
    db: AsyncSession,
    category: str | None,
    exclude_ids: list[str],
) -> dict | None:
    """동일 카테고리 자사 최근 기사 1건 (톤 샘플용).

    근거: docs/REFERENCES.md §2-3 — in-context 예시 선택이 style transfer 핵심.
    주제 무관하게 카테고리만 일치시켜 문체·어휘·구성 패턴을 전달한다.
    """
    if not category:
        return None

    stmt = (
        select(Article)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(Article.source_name.in_(OWN_SOURCE_NAMES))
        .where(ArticleAnalysis.category == category)
        .order_by(Article.published_at.desc().nullslast())
        .limit(5)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    for art in rows:
        if str(art.id) not in exclude_ids:
            return _article_to_dict(art)
    return None


# ── 포맷팅 ──────────────────────────────────────────────────

def _article_to_dict(a: Article) -> dict:
    return {
        "id": str(a.id),
        "title": a.title,
        "url": a.url,
        "source_name": a.source_name,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "description": (a.description or "").strip(),
        "content": (a.content or "").strip(),
    }


def _ref_to_source(r: dict) -> SourceRef:
    return SourceRef(name=r["source_name"], url=r["url"], published_at=r.get("published_at"))


def _build_articles_block(articles: list[Article]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        pub = a.published_at.isoformat() if a.published_at else "미상"
        desc = (a.description or "").strip()
        content = (a.content or "").strip()
        body_snippet = (content or desc)[:800]
        lines.append(
            f"[{i}] {a.title}\n"
            f"   매체: {a.source_name} ({a.source_type}) · 발행: {pub}\n"
            f"   URL: {a.url}\n"
            f"   본문: {body_snippet}"
        )
    return "\n\n".join(lines)


def _build_references_block(refs: list[dict]) -> str:
    if not refs:
        return "\n=== 자사·통신사 참고 기사 ===\n(매칭된 자사/통신사 기사 없음)\n"
    lines = ["\n=== 자사·통신사 참고 기사 — 본문 인용 가능 ==="]
    for i, r in enumerate(refs, 1):
        pub = r.get("published_at") or "미상"
        snippet = (r.get("description") or "")[:_SNIPPET_CHARS_DESC]
        tier = _source_tier(r["source_name"])
        tier_mark = "자사" if tier == "own" else "통신사/외신"
        lines.append(
            f"[R{i}] ({tier_mark}) {r['source_name']} — {r['title']}\n"
            f"     발행: {pub} · URL: {r['url']}\n"
            f"     요약: {snippet}"
        )
    lines.append(
        "\n※ 자사 기사는 '본사 보도에 따르면', 통신사·외신은 매체명(예: '연합뉴스에 따르면',"
        " 'BBC에 따르면')으로 직접 인용하고 sources 에 반드시 포함하세요."
        " 참고 기사에 없는 사실은 추측하지 마세요."
    )
    return "\n".join(lines)


def _build_background_block(bgs: list[dict]) -> str:
    """경쟁 일간지 기사 — 맥락 파악용. 본문 직접 인용 금지."""
    if not bgs:
        return ""
    lines = ["\n=== 경쟁 일간지 맥락 (직접 인용 금지) ==="]
    for i, r in enumerate(bgs, 1):
        pub = r.get("published_at") or "미상"
        snippet = (r.get("description") or "")[:_SNIPPET_CHARS_DESC]
        lines.append(
            f"[B{i}] {r['source_name']} — {r['title']} ({pub})\n"
            f"     요약: {snippet}"
        )
    lines.append(
        "\n※ 위는 다른 국내 일간지 보도입니다. 매체명 직접 인용을 하지 마세요."
        " 사실 자체를 가져다 쓸 경우 '업계에 따르면', '관계자에 따르면' 또는 자사가"
        " 별도로 확인한 사실처럼 서술하세요. sources 에는 절대 포함하지 마세요."
    )
    return "\n".join(lines)


def _build_style_anchor_block(anchor: dict | None) -> str:
    if not anchor:
        return ""
    lead = (anchor.get("description") or anchor.get("content") or "")[:_SNIPPET_CHARS_LEAD]
    if not lead:
        return ""
    return (
        "\n=== 톤 샘플 (서울신문, 동일 카테고리) ===\n"
        f"제목: {anchor['title']}\n"
        f"도입부: {lead}\n"
        "※ 위 샘플의 문장 길이·어휘 레벨·구성 패턴을 참고해 초안 본문의 톤을 맞추세요.\n"
    )
