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
    published_at: str | None = None  # recency 표시용 (ISO 문자열)


class DraftOut(BaseModel):
    """DRAFT_SYSTEM 응답 스키마"""
    title_candidates: list[str] = Field(min_length=1, max_length=5)
    lead: str
    body: str
    background: str = ""
    six_w_check: SixWCheckOut = Field(default_factory=SixWCheckOut)
    # 직접 인용 가능 원천 (자사 + 통신사 + 외신)
    sources: list[SourceRef] = Field(default_factory=list)
    # RAG: 자사(서울신문) 과거 보도 — 투명 공개 + 본문 직접 인용 가능
    references: list[SourceRef] = Field(default_factory=list)
    # 톤 앵커 — 동일 카테고리 자사 기사 1건, few-shot anchor
    style_anchor: SourceRef | None = None
    # 경쟁 일간지 기사 — 맥락 파악용, 직접 인용 금지. 투명성을 위해 메타로만 노출
    background_sources: list[SourceRef] = Field(default_factory=list)


# ── 워치리스트 ──

class WatchlistCreate(BaseModel):
    keyword: str = Field(min_length=1, max_length=100)


class WatchlistUpdate(BaseModel):
    is_active: bool


# ── 예비 기사 (Article Draft) ──

DraftStatus = Literal["draft", "in_review", "approved", "rejected"]


class ArticleDraftCreate(BaseModel):
    """DraftDialog 의 '예비 게시' 에서 DraftOut 스냅샷 + 기자가 선택한 제목을 받음."""
    title: str = Field(min_length=1, max_length=300)
    lead: str
    body: str
    background: str = ""
    category: str | None = None
    style: DraftStyle = "straight"
    topic_hint: str | None = None
    six_w_check: dict = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    references: list[SourceRef] = Field(default_factory=list)
    background_sources: list[SourceRef] = Field(default_factory=list)
    style_anchor: SourceRef | None = None
    origin_article_ids: list[str] = Field(default_factory=list)
    model_used: str | None = None


class ArticleDraftUpdate(BaseModel):
    """편집 — 필드 선택적 업데이트"""
    title: str | None = None
    lead: str | None = None
    body: str | None = None
    background: str | None = None
    category: str | None = None


class ArticleDraftTransition(BaseModel):
    """상태 전이 (결재 요청·승인·반려·초안으로 복귀)"""
    to: DraftStatus
    note: str | None = None


class FactIssueAcknowledge(BaseModel):
    """개별 팩트 경고 확인 처리 (HITL)"""
    acknowledged: bool = True
    acknowledged_by: str | None = None
    note: str | None = None
