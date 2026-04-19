"""기사 초안 생성기 - Sonnet 4.6

다중 기사를 교차 참조하여 역피라미드·6하원칙 기반 초안 1건을 생성한다.
저장하지 않고 응답만 반환 (stateless).
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.llm_client import MODEL_FOR, call_llm
from backend.analyzers.schemas import DraftOut, SourceRef
from backend.database.models import Article
from backend.prompts import DRAFT_SYSTEM


async def generate_draft(
    db: AsyncSession,
    article_ids: list[UUID],
    style: str = "straight",
    topic_hint: str | None = None,
) -> dict:
    """주어진 기사들을 바탕으로 초안 1건 생성"""
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

    articles_text = _build_articles_block(articles)
    topic_line = f"\n진입 맥락(선택 헤드라인/주제): {topic_hint}\n" if topic_hint else ""

    user_message = f"""다음 관련 기사들을 바탕으로 서울신문 편집국 기준 초안 1건을 작성해주세요.

style: {style}{topic_line}

=== 관련 기사 ({len(articles)}건) ===
{articles_text}"""

    llm_result = await call_llm(
        system_prompt=DRAFT_SYSTEM,
        user_message=user_message,
        model=MODEL_FOR["draft"],
        max_tokens=3072,
        temperature=0.4,
    )

    # 스키마 검증 — 실패 시 ValueError raise → 라우터가 500 처리
    parsed = DraftOut.model_validate(llm_result["content"])

    # 출처가 비어 있으면 입력 기사에서 자동 채움
    if not parsed.sources:
        parsed.sources = [
            SourceRef(name=a.source_name, url=a.url) for a in articles
        ]

    return {
        "draft": parsed.model_dump(),
        "generated_at": datetime.now(timezone.utc),
        "model_used": llm_result["model_used"],
        "prompt_tokens": llm_result["prompt_tokens"],
        "completion_tokens": llm_result["completion_tokens"],
    }


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
