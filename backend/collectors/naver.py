"""네이버 뉴스 검색 API 수집기 - 국내 뉴스 수집"""

from datetime import datetime, timezone
from html import unescape
import re

import httpx

from backend.config import get_settings

NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"

# 비뉴스 도메인 필터 (블로그, SNS 등 노이즈 제거)
_NON_NEWS_DOMAINS = {
    "tistory.com", "blog.naver.com", "cafe.naver.com", "post.naver.com",
    "youtube.com", "instagram.com", "twitter.com", "x.com", "facebook.com",
    "brunch.co.kr", "medium.com", "velog.io", "notion.so",
}


async def fetch_news(
    query: str = "주요뉴스",
    display: int = 20,
    sort: str = "date",
    start: int = 1,
) -> list[dict]:
    """네이버 뉴스 검색 API로 국내 뉴스 수집

    Args:
        query: 검색 키워드
        display: 결과 개수 (max 100)
        sort: 정렬 기준 (date: 최신순, sim: 정확도순)
        start: 시작 위치
    """
    settings = get_settings()
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
    }
    params = {
        "query": query,
        "display": min(display, 100),
        "sort": sort,
        "start": start,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(NAVER_SEARCH_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    return _normalize_articles(data.get("items", []))


async def fetch_by_categories(
    categories: list[str] | None = None,
    display: int = 10,
) -> list[dict]:
    """주요 카테고리별 뉴스 수집"""
    if categories is None:
        categories = ["정치", "경제", "사회", "국제", "IT과학", "문화", "스포츠"]

    all_articles = []
    for cat in categories:
        articles = await fetch_news(query=cat, display=display, sort="date")
        all_articles.extend(articles)

    return all_articles


def _normalize_articles(raw_items: list[dict]) -> list[dict]:
    """네이버 API 응답을 공통 포맷으로 변환"""
    articles = []
    for item in raw_items:
        title = _strip_html(item.get("title", ""))
        if not title:
            continue
        url = item.get("originallink") or item.get("link", "")
        # 비뉴스 도메인 필터링
        if _is_non_news_domain(url):
            continue
        articles.append({
            "title": title,
            "description": _strip_html(item.get("description", "")),
            "content": None,
            "url": url,
            "source_name": _extract_source(url),
            "source_type": "domestic",
            "source_api": "naver",
            "published_at": _parse_naver_date(item.get("pubDate")),
        })
    return articles


def _is_non_news_domain(url: str) -> bool:
    """비뉴스 도메인 여부 확인"""
    if not url:
        return False
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower().replace("www.", "")
        return any(blocked in domain for blocked in _NON_NEWS_DOMAINS)
    except Exception:
        return False


def _strip_html(text: str) -> str:
    """HTML 태그 및 엔티티 제거"""
    clean = re.sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


def _extract_source(url: str) -> str:
    """URL에서 매체명 추출"""
    if not url:
        return "Unknown"
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        domain = domain.replace("www.", "")
        return domain.split(".")[0]
    except Exception:
        return "Unknown"


def _parse_naver_date(date_str: str | None) -> datetime | None:
    """네이버 날짜 형식 파싱 (RFC 822)"""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None
