"""기사 초안 생성 API - Sonnet 4.6 기반"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.drafter import generate_draft
from backend.analyzers.schemas import DraftStyle
from backend.database import get_db
from backend.models.schemas import APIResponse

router = APIRouter(prefix="/drafts", tags=["drafts"])


class DraftRequest(BaseModel):
    article_ids: list[UUID] = Field(min_length=1)
    style: DraftStyle = "straight"
    topic_hint: str | None = None


@router.post("/generate", response_model=APIResponse)
async def create_draft(
    req: DraftRequest,
    db: AsyncSession = Depends(get_db),
):
    """관련 기사 기반 기사 초안 생성"""
    try:
        result = await generate_draft(
            db,
            article_ids=req.article_ids,
            style=req.style,
            topic_hint=req.topic_hint,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return APIResponse(data={
        **result["draft"],
        "generated_at": result["generated_at"],
        "model_used": result["model_used"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
    })
