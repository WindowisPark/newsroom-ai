"""예비 기사(Article Draft) API

초안 저장·목록·편집·상태 전이(결재 요청·승인·반려). DraftDialog 의
'예비 게시' 에서 저장된 기사를 편집국 워크플로에 올린다.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.schemas import (
    ArticleDraftCreate,
    ArticleDraftTransition,
    ArticleDraftUpdate,
    DraftStatus,
)
from backend.database import get_db
from backend.database.models import ArticleDraft
from backend.models.schemas import APIResponse

router = APIRouter(prefix="/article-drafts", tags=["article-drafts"])


# 상태 전이 허용 매트릭스 — 잘못된 전이는 409
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft":     {"in_review"},               # 결재 요청
    "in_review": {"approved", "rejected", "draft"},  # 승인/반려/재작성
    "approved":  {"draft"},                   # (수정 원할 시 초안으로 복귀)
    "rejected":  {"draft"},                   # 재작성
}


def _serialize(d: ArticleDraft) -> dict:
    return {
        "id": str(d.id),
        "title": d.title,
        "lead": d.lead,
        "body": d.body,
        "background": d.background or "",
        "category": d.category,
        "style": d.style,
        "topic_hint": d.topic_hint,
        "six_w_check": d.six_w_check or {},
        "sources": d.sources or [],
        "references": d.references or [],
        "background_sources": d.background_sources or [],
        "style_anchor": d.style_anchor,
        "origin_article_ids": d.origin_article_ids or [],
        "status": d.status,
        "review_note": d.review_note,
        "model_used": d.model_used,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
        "submitted_at": d.submitted_at,
        "reviewed_at": d.reviewed_at,
    }


@router.get("", response_model=APIResponse)
async def list_drafts(
    status: DraftStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """예비 기사 목록 — 상태별 필터 가능"""
    stmt = select(ArticleDraft).order_by(ArticleDraft.updated_at.desc())
    if status:
        stmt = stmt.where(ArticleDraft.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return APIResponse(data=[_serialize(d) for d in rows])


@router.post("", response_model=APIResponse)
async def create_draft(
    req: ArticleDraftCreate,
    db: AsyncSession = Depends(get_db),
):
    """DraftDialog 에서 '예비 게시' — 초안 스냅샷 저장"""
    item = ArticleDraft(
        title=req.title.strip(),
        lead=req.lead,
        body=req.body,
        background=req.background or None,
        category=req.category,
        style=req.style,
        topic_hint=req.topic_hint,
        six_w_check=req.six_w_check,
        sources=[s.model_dump() for s in req.sources],
        references=[r.model_dump() for r in req.references],
        background_sources=[b.model_dump() for b in req.background_sources],
        style_anchor=req.style_anchor.model_dump() if req.style_anchor else None,
        origin_article_ids=req.origin_article_ids,
        status="draft",
        model_used=req.model_used,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return APIResponse(data=_serialize(item))


@router.get("/{item_id}", response_model=APIResponse)
async def get_draft(item_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(ArticleDraft, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="article draft not found")
    return APIResponse(data=_serialize(item))


@router.patch("/{item_id}", response_model=APIResponse)
async def update_draft(
    item_id: UUID,
    req: ArticleDraftUpdate,
    db: AsyncSession = Depends(get_db),
):
    """제목·리드·본문·배경·카테고리 부분 편집. draft/rejected 상태에서만 허용."""
    item = await db.get(ArticleDraft, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="article draft not found")
    if item.status not in ("draft", "rejected"):
        raise HTTPException(
            status_code=409,
            detail=f"cannot edit in status={item.status}; move to draft first",
        )

    payload = req.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if value is not None and value != "":
            setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return APIResponse(data=_serialize(item))


@router.post("/{item_id}/transition", response_model=APIResponse)
async def transition_draft(
    item_id: UUID,
    req: ArticleDraftTransition,
    db: AsyncSession = Depends(get_db),
):
    """상태 전이 — 결재 요청(draft→in_review) / 승인 / 반려 등"""
    item = await db.get(ArticleDraft, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="article draft not found")

    allowed = _ALLOWED_TRANSITIONS.get(item.status, set())
    if req.to not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"transition {item.status} → {req.to} not allowed",
        )

    item.status = req.to
    now = datetime.now(timezone.utc)
    if req.to == "in_review":
        item.submitted_at = now
    elif req.to in ("approved", "rejected"):
        item.reviewed_at = now
    if req.note is not None:
        item.review_note = req.note
    await db.commit()
    await db.refresh(item)
    return APIResponse(data=_serialize(item))


@router.delete("/{item_id}", response_model=APIResponse)
async def delete_draft(item_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(ArticleDraft, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="article draft not found")
    await db.delete(item)
    await db.commit()
    return APIResponse(data={"deleted": True})
