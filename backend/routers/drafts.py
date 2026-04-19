"""기사 초안 생성 API - Sonnet 4.6 기반"""

import logging
from uuid import UUID

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.drafter import generate_draft
from backend.analyzers.schemas import DraftStyle
from backend.database import get_db
from backend.models.schemas import APIResponse

logger = logging.getLogger(__name__)
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
    """관련 기사 기반 기사 초안 생성.

    LLM provider 오류(크레딧 부족·rate limit·네트워크)는 500 대신 503 으로
    변환해 CORS 미들웨어를 통과시키고 프론트에 실제 에러 메시지를 전달.
    """
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
    except anthropic.BadRequestError as e:
        logger.error(f"Anthropic API 400: {e}")
        # 크레딧 부족 · 요청 포맷 오류 — 사용자에게 전달 가능한 메시지
        msg = getattr(getattr(e, "body", None), "get", lambda *_: None)("error", {})
        detail = msg.get("message") if isinstance(msg, dict) else str(e)
        raise HTTPException(status_code=503, detail=f"LLM 서비스 오류: {detail}")
    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API {e.status_code}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"LLM 서비스 일시 중단 ({e.status_code})",
        )
    except anthropic.APIConnectionError as e:
        logger.error(f"Anthropic 연결 실패: {e}")
        raise HTTPException(status_code=503, detail="LLM 서비스 연결 실패")

    return APIResponse(data={
        **result["draft"],
        "generated_at": result["generated_at"],
        "model_used": result["model_used"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
    })
