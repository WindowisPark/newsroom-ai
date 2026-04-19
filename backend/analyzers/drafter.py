"""기사 초안 생성기 - Sonnet 4.6 + RAG (서울신문 자사 기사 참조)

다중 기사를 교차 참조하여 역피라미드·6하원칙 기반 초안 1건을 생성한다.
서울신문 자사 기사를 retrieval 해 참고 자료·톤 앵커로 LLM에 주입한다.
저장하지 않고 응답만 반환 (stateless).

근거: docs/REFERENCES.md §1 (RAG 정석), §2 (few-shot style).
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
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
        max_tokens=3072,
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

    return {
        "draft": parsed.model_dump(),
        "generated_at": datetime.now(timezone.utc),
        "model_used": llm_result["model_used"],
        "prompt_tokens": llm_result["prompt_tokens"],
        "completion_tokens": llm_result["completion_tokens"],
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
    """
    if not keywords or not tiers:
        return []

    window_start = datetime.now(timezone.utc) - timedelta(days=_RECENCY_WINDOW_DAYS)

    stmt = select(Article).where(~Article.id.in_(exclude_ids))
    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return []

    kw_set = set(keywords)
    scored: list[tuple[float, Article, int]] = []

    for art in rows:
        if _source_tier(art.source_name) not in tiers:
            continue
        match_count = 0
        if art.analysis and art.analysis.keywords:
            match_count = len(kw_set & set(art.analysis.keywords))
        if match_count == 0:
            # 제목 경계 매칭 fallback (3자+ 한글, 영숫자 단어경계)
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
