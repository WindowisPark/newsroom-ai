from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── 공통 ──


class Meta(BaseModel):
    total: int
    page: int
    limit: int


class APIResponse(BaseModel):
    status: str = "success"
    data: object = None
    meta: Meta | None = None


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    code: str


# ── 뉴스 ──


class EntityOut(BaseModel):
    name: str
    type: str  # person / organization / location

    model_config = {"from_attributes": True}


class AnalysisOut(BaseModel):
    category: str
    keywords: list[str]
    entities: list[EntityOut]
    sentiment: str
    importance_score: float

    model_config = {"from_attributes": True}


class ArticleOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    content: str | None
    url: str
    source_name: str
    source_type: str
    published_at: datetime | None
    collected_at: datetime
    analysis: AnalysisOut | None = None

    model_config = {"from_attributes": True}


class CollectRequest(BaseModel):
    sources: list[str] = Field(default=["newsapi", "naver", "rss"])
    query: str | None = None


class CollectResult(BaseModel):
    collected_count: int
    new_count: int
    duplicate_count: int
    sources: dict[str, int]


# ── 의제 설정 ──


class AgendaIssue(BaseModel):
    rank: int
    topic: str
    summary: str
    importance_score: float
    article_count: int
    source_count: int
    trend: str  # rising / stable / falling
    categories: list[str]
    key_keywords: list[str]
    related_article_ids: list[UUID]


class AgendaOut(BaseModel):
    date: date
    generated_at: datetime
    top_issues: list[AgendaIssue]
    analysis_summary: str


# ── 관점 비교 ──


class ArticleBrief(BaseModel):
    id: UUID
    title: str
    source_name: str
    url: str


class PerspectiveSide(BaseModel):
    frame: str
    tone: str
    key_points: list[str]
    representative_articles: list[ArticleBrief]


class PerspectiveComparison(BaseModel):
    frame_difference: str
    background_context: str
    editorial_insight: str


class PerspectiveOut(BaseModel):
    topic: str
    generated_at: datetime
    domestic: PerspectiveSide
    foreign: PerspectiveSide
    comparison: PerspectiveComparison


# ── 트렌드 ──


class TrendDataPoint(BaseModel):
    time: datetime
    count: int


class TrendSeries(BaseModel):
    label: str
    values: list[TrendDataPoint]


class TrendOut(BaseModel):
    period: str
    type: str
    data_points: list[TrendSeries]


# ── 브리핑 리포트 ──


class BriefingSection(BaseModel):
    category: str
    title: str
    content: str


class BriefingContent(BaseModel):
    headline: str
    summary: str
    sections: list[BriefingSection]


class BriefingOut(BaseModel):
    id: UUID
    date: date
    generated_at: datetime
    briefing: BriefingContent
    model_used: str
    prompt_tokens: int | None
    completion_tokens: int | None


# ── 헤드라인 추천 ──


class HeadlineItem(BaseModel):
    headline: str
    reason: str
    tone: str


class HeadlineRequest(BaseModel):
    topic: str
    article_ids: list[UUID] = []
    style: str = "neutral"


class HeadlineOut(BaseModel):
    topic: str
    generated_at: datetime
    headlines: list[HeadlineItem]


# ── 배경 타임라인 ──


class TimelineEvent(BaseModel):
    date: str
    event: str
    significance: str


class TimelineRequest(BaseModel):
    topic: str
    article_ids: list[UUID] = []


class TimelineOut(BaseModel):
    topic: str
    generated_at: datetime
    timeline: list[TimelineEvent]
    context_summary: str


# ── 시스템 ──


class HealthOut(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    database: str
    scheduler: str
    last_collection: datetime | None


class SchedulerOut(BaseModel):
    running: bool
    interval_minutes: int
    next_run: datetime | None
    last_run: datetime | None
    total_collections: int
