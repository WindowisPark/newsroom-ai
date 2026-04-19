"""워치리스트 CRUD API"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.schemas import WatchlistCreate, WatchlistUpdate
from backend.database import get_db
from backend.database.models import Watchlist
from backend.models.schemas import APIResponse

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def _serialize(w: Watchlist) -> dict:
    return {
        "id": str(w.id),
        "keyword": w.keyword,
        "is_active": w.is_active,
        "created_at": w.created_at,
        "last_matched_at": w.last_matched_at,
        "match_count": w.match_count,
    }


@router.get("", response_model=APIResponse)
async def list_watchlist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Watchlist).order_by(Watchlist.created_at.desc()))
    items = [_serialize(w) for w in result.scalars().all()]
    return APIResponse(data=items)


@router.post("", response_model=APIResponse)
async def add_watchlist(req: WatchlistCreate, db: AsyncSession = Depends(get_db)):
    keyword = req.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=422, detail="keyword must not be empty")

    existing = await db.execute(select(Watchlist).where(Watchlist.keyword == keyword))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="keyword already exists")

    item = Watchlist(keyword=keyword)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return APIResponse(data=_serialize(item))


@router.patch("/{item_id}", response_model=APIResponse)
async def update_watchlist(
    item_id: UUID,
    req: WatchlistUpdate,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Watchlist, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    item.is_active = req.is_active
    await db.commit()
    await db.refresh(item)
    return APIResponse(data=_serialize(item))


@router.delete("/{item_id}", response_model=APIResponse)
async def delete_watchlist(item_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(Watchlist, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    await db.delete(item)
    await db.commit()
    return APIResponse(data={"deleted": True})
