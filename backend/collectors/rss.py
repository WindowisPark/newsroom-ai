"""RSS 피드 수집기 - 주요 언론사 피드 수집"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

# 주요 국내 언론사 RSS 피드
DEFAULT_FEEDS = {
    "연합뉴스": "https://www.yna.co.kr/rss/news.xml",
    "한겨레": "https://www.hani.co.kr/rss/",
    "한국경제": "https://www.hankyung.com/feed/all-news",
    "조선일보": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
    "동아일보": "https://rss.donga.com/total.xml",
}


async def fetch_feeds(
    feeds: dict[str, str] | None = None,
    max_per_feed: int = 10,
) -> list[dict]:
    """RSS 피드에서 뉴스 수집

    Args:
        feeds: {매체명: RSS URL} 딕셔너리. None이면 기본 피드 사용.
        max_per_feed: 피드당 최대 수집 개수
    """
    if feeds is None:
        feeds = DEFAULT_FEEDS

    all_articles = []

    async with httpx.AsyncClient(timeout=30) as client:
        for source_name, feed_url in feeds.items():
            try:
                resp = await client.get(feed_url, follow_redirects=True)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.text)
                articles = _normalize_entries(parsed.entries[:max_per_feed], source_name)
                all_articles.extend(articles)
            except Exception:
                # 개별 피드 실패 시 건너뛰고 계속
                continue

    return all_articles


def _normalize_entries(entries: list, source_name: str) -> list[dict]:
    """feedparser 엔트리를 공통 포맷으로 변환"""
    articles = []
    for entry in entries:
        title = entry.get("title", "").strip()
        if not title:
            continue
        articles.append({
            "title": title,
            "description": entry.get("summary", ""),
            "content": _extract_content(entry),
            "url": entry.get("link", ""),
            "source_name": source_name,
            "source_type": "domestic",
            "source_api": "rss",
            "published_at": _parse_entry_date(entry),
        })
    return articles


def _extract_content(entry) -> str | None:
    """RSS 엔트리에서 본문 추출"""
    content_list = entry.get("content", [])
    if content_list:
        return content_list[0].get("value", "")
    return None


def _parse_entry_date(entry) -> datetime | None:
    """RSS 엔트리 날짜 파싱"""
    date_str = entry.get("published") or entry.get("updated")
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
