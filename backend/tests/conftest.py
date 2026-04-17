"""테스트 공통 fixture - SQLite 인메모리 DB + FastAPI TestClient"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.db import Base
from backend.database.models import Article, ArticleAnalysis


# ── SQLite에서 JSONB → JSON 매핑 ──

@event.listens_for(Base.metadata, "column_reflect")
def _fix_jsonb(inspector, table, column_info):
    if str(column_info["type"]) == "JSONB":
        column_info["type"] = JSON()


# ── DB Fixtures ──

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)

    # JSONB 컬럼을 JSON으로 치환하여 테이블 생성
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_JSONB):
                col.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ── FastAPI TestClient ──

@pytest_asyncio.fixture
async def client(db_session):
    from backend.database import get_db
    from backend.main import app

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── 테스트 데이터 팩토리 ──

def make_article(**overrides) -> dict:
    defaults = {
        "title": "테스트 기사 제목",
        "description": "테스트 기사 요약",
        "content": "테스트 기사 본문 내용",
        "url": f"https://test.com/article/{uuid.uuid4().hex[:8]}",
        "source_name": "테스트뉴스",
        "source_type": "domestic",
        "source_api": "naver",
        "published_at": datetime.now(timezone.utc),
        "collected_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return defaults


async def insert_article(db: AsyncSession, **overrides) -> Article:
    data = make_article(**overrides)
    article = Article(**data)
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


_ANALYSIS_KEYS = {"category", "keywords", "entities", "sentiment", "importance_score"}


async def insert_article_with_analysis(db: AsyncSession, **overrides) -> Article:
    analysis_kwargs = {k: overrides.pop(k) for k in list(overrides) if k in _ANALYSIS_KEYS}
    article = await insert_article(db, **overrides)
    analysis = ArticleAnalysis(
        article_id=article.id,
        category=analysis_kwargs.get("category", "politics"),
        keywords=analysis_kwargs.get("keywords", ["테스트", "키워드"]),
        entities=analysis_kwargs.get("entities", [{"name": "홍길동", "type": "person"}]),
        sentiment=analysis_kwargs.get("sentiment", "neutral"),
        importance_score=analysis_kwargs.get("importance_score", 7.5),
        model_used="test-model",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(article)
    return article
