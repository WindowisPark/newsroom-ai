"""초안 품질 판독 — Gemini 3 Flash 이종(heterogeneous) judge.

drafter 가 Sonnet 으로 생성한 기사 초안을 별개 회사·별개 학습 데이터 모델이
독립 판정하여 self-critique 편향을 피한다. fact_check(규칙) 와 HITL(사람) 사이의
"편집 품질 게이트" 공백을 메운다.

판독 7축: lead_strength / six_w_coverage / inverted_pyramid /
         tone_consistency / citation_compliance / factual_specificity /
         source_dependency (자사 저널리즘 독자성 — 통신사 의존도)
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.analyzers.gemini_client import GEMINI_JUDGE_MODEL, call_gemini
from backend.prompts import REVIEWER_SYSTEM

logger = logging.getLogger(__name__)


Recommendation = Literal["publish", "revise", "reject"]


class CriterionScore(BaseModel):
    score: float = Field(ge=0, le=10)
    note: str = ""


class ReviewOut(BaseModel):
    overall_score: float = Field(ge=0, le=10)
    recommendation: Recommendation
    criteria: dict[str, CriterionScore]
    critical_issues: list[str] = Field(default_factory=list)
    suggested_revisions: list[str] = Field(default_factory=list)


# google-genai Structured Output 용 JSON Schema
# (Gemini 는 Pydantic 을 직접 받지 않고 OpenAPI 형식 schema 를 요구)
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "overall_score": {"type": "number"},
        "recommendation": {"type": "string", "enum": ["publish", "revise", "reject"]},
        "criteria": {
            "type": "object",
            "properties": {
                axis: {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number"},
                        "note": {"type": "string"},
                    },
                    "required": ["score", "note"],
                }
                for axis in (
                    "lead_strength",
                    "six_w_coverage",
                    "inverted_pyramid",
                    "tone_consistency",
                    "citation_compliance",
                    "factual_specificity",
                    "source_dependency",
                )
            },
        },
        "critical_issues": {"type": "array", "items": {"type": "string"}},
        "suggested_revisions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "overall_score",
        "recommendation",
        "criteria",
        "critical_issues",
        "suggested_revisions",
    ],
}


def _format_draft_for_review(draft: dict) -> str:
    """drafter 결과 dict 를 Gemini 입력용 텍스트로 직렬화."""
    title_candidates = draft.get("title_candidates") or []
    six_w = draft.get("six_w_check") or {}
    sources = draft.get("sources") or []
    references = draft.get("references") or []
    background_sources = draft.get("background_sources") or []

    lines: list[str] = []
    lines.append("=== 기사 초안 ===")
    lines.append("제목 후보:")
    for i, t in enumerate(title_candidates, 1):
        lines.append(f"  {i}. {t}")
    lines.append("")
    lines.append(f"리드:\n{draft.get('lead', '')}")
    lines.append("")
    lines.append(f"본문:\n{draft.get('body', '')}")
    lines.append("")
    lines.append(f"배경:\n{draft.get('background', '')}")
    lines.append("")
    lines.append("6하원칙 자가 체크:")
    for k in ("who", "when", "where", "what", "how", "why"):
        lines.append(f"  - {k}: {six_w.get(k) or '(null)'}")
    lines.append("")
    lines.append("sources(인용 매체):")
    if sources:
        for s in sources:
            lines.append(f"  - {s.get('name')} {s.get('url') or ''}")
    else:
        lines.append("  (없음)")
    lines.append("")
    lines.append("references(자사·통신사 참고):")
    for r in references or []:
        lines.append(f"  - {r.get('name')} {r.get('url') or ''}")
    lines.append("")
    lines.append("background_sources(경쟁 일간지 — 직접 인용 금지):")
    for b in background_sources or []:
        lines.append(f"  - {b.get('name')} {b.get('url') or ''}")
    return "\n".join(lines)


async def review_draft(draft: dict) -> dict:
    """초안 1건을 6축으로 판독해 리뷰 리포트 반환.

    Returns:
        {
            "review": {overall_score, recommendation, criteria, critical_issues, suggested_revisions},
            "model_used": "gemini-3-flash-preview",
            "prompt_tokens": int,
            "completion_tokens": int,
        }
    """
    user_message = _format_draft_for_review(draft)

    llm_result = await call_gemini(
        system_prompt=REVIEWER_SYSTEM,
        user_message=user_message,
        model=GEMINI_JUDGE_MODEL,
        max_output_tokens=2048,
        temperature=0.2,
        response_schema=_RESPONSE_SCHEMA,
    )

    # Pydantic 검증 — Gemini structured mode 에서도 혹시 모를 변이 방어
    parsed = ReviewOut.model_validate(llm_result["content"])

    return {
        "review": parsed.model_dump(),
        "model_used": llm_result["model_used"],
        "prompt_tokens": llm_result["prompt_tokens"],
        "completion_tokens": llm_result["completion_tokens"],
    }
