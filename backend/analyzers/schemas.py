"""LLM 출력 검증용 Pydantic 스키마

call_llm이 반환한 JSON을 이 모델로 validate하여 타입/범위/enum을
조기에 강제한다. 실패 시 ValidationError → 호출부가 기존 예외 경로로 처리.

`Category` / `Sentiment` / `EntityType` / `Trend` Literal 은 파이프라인 전역의
단일 진실 원천. 프롬프트 문구와 프론트 필터 라벨도 이 목록에 맞추어야 한다.
추가/변경 시: get_args(Category) 로 런타임 조회하는 곳들도 함께 갱신됨.
"""

from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator


Category = Literal["politics", "economy", "society", "world", "tech", "culture", "sports"]
Sentiment = Literal["positive", "negative", "neutral"]
EntityType = Literal["person", "organization", "location"]
Trend = Literal["rising", "stable", "falling"]

CATEGORIES: tuple[str, ...] = get_args(Category)
SENTIMENTS: tuple[str, ...] = get_args(Sentiment)


class EntityOut(BaseModel):
    name: str
    type: EntityType


class ClassificationOut(BaseModel):
    """CLASSIFIER_SYSTEM 응답 스키마 (Haiku 1차 분석)"""
    category: Category
    keywords: list[str] = Field(min_length=1, max_length=10)
    entities: list[EntityOut] = Field(default_factory=list)
    sentiment: Sentiment
    importance_score: float = Field(ge=1.0, le=10.0)

    @field_validator("keywords", mode="before")
    @classmethod
    def _strip_empty_keywords(cls, v):
        if not isinstance(v, list):
            return v
        return [k.strip() for k in v if isinstance(k, str) and k.strip()]


class AgendaIssueOut(BaseModel):
    """AGENDA_SYSTEM top_issues[] 개별 아이템"""
    rank: int = Field(ge=1)
    topic: str
    summary: str
    importance_score: float = Field(ge=1.0, le=10.0)
    trend: Trend
    categories: list[str] = Field(default_factory=list)
    key_keywords: list[str] = Field(default_factory=list)


class AgendaOut(BaseModel):
    """AGENDA_SYSTEM 전체 응답"""
    top_issues: list[AgendaIssueOut] = Field(default_factory=list)
    analysis_summary: str = ""


# ── 기사 초안 생성 (Sonnet 4.6) ──

DraftStyle = Literal["straight", "analysis", "feature"]


class SixWCheckOut(BaseModel):
    """6하원칙 self-check. 누락 항목은 None."""
    who: str | None = None
    when: str | None = None
    where: str | None = None
    what: str | None = None
    how: str | None = None
    why: str | None = None


class SourceRef(BaseModel):
    name: str
    url: str


class DraftOut(BaseModel):
    """DRAFT_SYSTEM 응답 스키마"""
    title_candidates: list[str] = Field(min_length=1, max_length=5)
    lead: str
    body: str
    background: str = ""
    six_w_check: SixWCheckOut = Field(default_factory=SixWCheckOut)
    sources: list[SourceRef] = Field(default_factory=list)


# ── 워치리스트 ──

class WatchlistCreate(BaseModel):
    keyword: str = Field(min_length=1, max_length=100)


class WatchlistUpdate(BaseModel):
    is_active: bool
