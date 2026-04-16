"""NewsAPI 수집기 - 글로벌/외신 뉴스 수집"""

from datetime import datetime, timezone

import httpx

from backend.config import get_settings

NEWSAPI_BASE = "https://newsapi.org/v2"


async def fetch_top_headlines(
    country: str | None = None,
    category: str | None = None,
    query: str | None = None,
    page_size: int = 20,
) -> list[dict]:
    """NewsAPI Top Headlines 수집"""
    settings = get_settings()
    params = {
        "apiKey": settings.newsapi_key,
        "pageSize": min(page_size, 100),
        "language": "en",
    }
    if country:
        params["country"] = country
    if category:
        params["category"] = category
    if query:
        params["q"] = query

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{NEWSAPI_BASE}/top-headlines", params=params)
        resp.raise_for_status()
        data = resp.json()

    return _normalize_articles(data.get("articles", []))


async def fetch_everything(
    query: str,
    from_date: str | None = None,
    to_date: str | None = None,
    sort_by: str = "publishedAt",
    page_size: int = 20,
) -> list[dict]:
    """NewsAPI Everything 수집 (키워드 기반)"""
    settings = get_settings()
    params = {
        "apiKey": settings.newsapi_key,
        "q": query,
        "sortBy": sort_by,
        "pageSize": min(page_size, 100),
        "language": "en",
    }
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{NEWSAPI_BASE}/everything", params=params)
        resp.raise_for_status()
        data = resp.json()

    return _normalize_articles(data.get("articles", []))


def _normalize_articles(raw_articles: list[dict]) -> list[dict]:
    """NewsAPI 응답을 공통 포맷으로 변환"""
    articles = []
    for raw in raw_articles:
        if not raw.get("title") or raw["title"] == "[Removed]":
            continue
        articles.append({
            "title": raw["title"],
            "description": raw.get("description"),
            "content": raw.get("content"),
            "url": raw["url"],
            "source_name": raw.get("source", {}).get("name", "Unknown"),
            "source_type": "foreign",
            "source_api": "newsapi",
            "published_at": _parse_datetime(raw.get("publishedAt")),
        })
    return articles


def _parse_datetime(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
