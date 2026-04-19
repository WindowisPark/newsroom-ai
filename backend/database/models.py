import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.db import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    source_name: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(20))  # domestic / foreign
    source_api: Mapped[str] = mapped_column(String(20))  # newsapi / naver / rss
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analysis: Mapped["ArticleAnalysis | None"] = relationship(back_populates="article", uselist=False, lazy="joined")


class ArticleAnalysis(Base):
    __tablename__ = "article_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(30))
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    entities: Mapped[list] = mapped_column(JSONB, default=list)
    sentiment: Mapped[str] = mapped_column(String(20))  # positive / negative / neutral
    importance_score: Mapped[float] = mapped_column(Float, default=5.0)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model_used: Mapped[str] = mapped_column(String(50))

    article: Mapped["Article"] = relationship(back_populates="analysis")


class AgendaReport(Base):
    __tablename__ = "agenda_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date: Mapped[date] = mapped_column(Date, index=True)
    top_issues: Mapped[list] = mapped_column(JSONB, default=list)
    analysis_summary: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model_used: Mapped[str] = mapped_column(String(50))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)


class PerspectiveReport(Base):
    __tablename__ = "perspective_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(200))
    date: Mapped[date] = mapped_column(Date, index=True)
    domestic_analysis: Mapped[dict] = mapped_column(JSONB, default=dict)
    foreign_analysis: Mapped[dict] = mapped_column(JSONB, default=dict)
    comparison: Mapped[dict] = mapped_column(JSONB, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model_used: Mapped[str] = mapped_column(String(50))


class BriefingReport(Base):
    __tablename__ = "briefing_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date: Mapped[date] = mapped_column(Date, index=True)
    headline: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    sections: Mapped[list] = mapped_column(JSONB, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model_used: Mapped[str] = mapped_column(String(50))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)


class HeadlineRecommendation(Base):
    __tablename__ = "headline_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(200))
    headlines: Mapped[list] = mapped_column(JSONB, default=list)
    timeline: Mapped[list | None] = mapped_column(JSONB)
    context_summary: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model_used: Mapped[str] = mapped_column(String(50))


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    match_count: Mapped[int] = mapped_column(Integer, default=0)


class ArticleDraft(Base):
    """예비 기사 — DraftDialog 에서 '예비 게시' 한 초안.

    status: draft(작성 중) → in_review(결재 대기) → approved(승인) / rejected(반려)
    """
    __tablename__ = "article_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300))
    lead: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    background: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(30))
    style: Mapped[str] = mapped_column(String(20), default="straight")
    topic_hint: Mapped[str | None] = mapped_column(String(300))

    six_w_check: Mapped[dict] = mapped_column(JSONB, default=dict)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    references: Mapped[list] = mapped_column(JSONB, default=list)
    background_sources: Mapped[list] = mapped_column(JSONB, default=list)
    style_anchor: Mapped[dict | None] = mapped_column(JSONB)
    origin_article_ids: Mapped[list] = mapped_column(JSONB, default=list)

    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    review_note: Mapped[str | None] = mapped_column(Text)

    model_used: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
