"""브리핑 리포트 API"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.database.models import BriefingReport
from backend.models.schemas import APIResponse, BriefingOut, BriefingContent
from backend.analyzers.reporter import generate_briefing

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/briefing", response_model=APIResponse)
async def get_briefing(
    date_str: str | None = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
):
    """브리핑 리포트 조회"""
    target_date = date.fromisoformat(date_str) if date_str else date.today()

    stmt = (
        select(BriefingReport)
        .where(BriefingReport.date == target_date)
        .order_by(BriefingReport.generated_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail=f"No briefing found for {target_date}")

    return APIResponse(data=BriefingOut(
        id=report.id,
        date=report.date,
        generated_at=report.generated_at,
        briefing=BriefingContent(
            headline=report.headline or "",
            summary=report.summary or "",
            sections=report.sections or [],
        ),
        model_used=report.model_used,
        prompt_tokens=report.prompt_tokens,
        completion_tokens=report.completion_tokens,
    ))


@router.post("/briefing/generate", response_model=APIResponse)
async def create_briefing(
    date_str: str | None = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
):
    """브리핑 리포트 수동 생성"""
    target_date = date.fromisoformat(date_str) if date_str else date.today()

    try:
        report = await generate_briefing(db, target_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return APIResponse(data=BriefingOut(
        id=report.id,
        date=report.date,
        generated_at=report.generated_at,
        briefing=BriefingContent(
            headline=report.headline or "",
            summary=report.summary or "",
            sections=report.sections or [],
        ),
        model_used=report.model_used,
        prompt_tokens=report.prompt_tokens,
        completion_tokens=report.completion_tokens,
    ))
