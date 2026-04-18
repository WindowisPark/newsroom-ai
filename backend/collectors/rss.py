"""RSS 피드 수집기 - 주요 언론사 피드 수집"""

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape

import feedparser
import httpx

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    """HTML 태그 및 엔티티 제거.

    한겨레 RSS 등 일부 피드는 description에 썸네일용 <table><img> 만 담아
    본문 텍스트가 비어 있는 경우가 있어, 태그 제거 후 공백만 남으면 빈 문자열
    반환해 분류기(LLM)가 HTML 덩어리를 본문으로 오해하지 않도록 한다.
    """
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()

# 주요 국내 언론사 RSS 피드
DEFAULT_FEEDS = {
    "연합뉴스": "https://www.yna.co.kr/rss/news.xml",
    "한겨레": "https://www.hani.co.kr/rss/",
    "한국경제": "https://www.hankyung.com/feed/all-news",
    "조선일보": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
    "동아일보": "https://rss.donga.com/total.xml",
}

# 외신 RSS 피드 - 국제 보도 프레임 비교 및 국내외 균형 수집
FOREIGN_FEEDS = {
    "BBC": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
}


async def fetch_feeds(
    feeds: dict[str, str] | None = None,
    max_per_feed: int = 10,
    source_type: str = "domestic",
) -> list[dict]:
    """RSS 피드에서 뉴스 수집

    Args:
        feeds: {매체명: RSS URL} 딕셔너리. None이면 기본 국내 피드 사용.
        max_per_feed: 피드당 최대 수집 개수
        source_type: "domestic" (국내) | "foreign" (외신). 의제/관점 분석에서 사용.
    """
    if feeds is None:
        feeds = DEFAULT_FEEDS

    all_articles = []

    async with httpx.AsyncClient(timeout=30) as client:
        for source_name, feed_url in feeds.items():
            try:
                resp = await client.get(feed_url, follow_redirects=True)
                resp.raise_for_status()
                # XML은 바이너리로 파싱해야 인코딩을 feedparser가 올바르게 감지
                parsed = feedparser.parse(resp.content)
                articles = _normalize_entries(
                    parsed.entries[:max_per_feed],
                    source_name,
                    source_type=source_type,
                )
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[RSS] {source_name} 피드 수집 실패: {e}")
                continue

    return all_articles


def _normalize_entries(
    entries: list,
    source_name: str,
    source_type: str = "domestic",
) -> list[dict]:
    """feedparser 엔트리를 공통 포맷으로 변환"""
    articles = []
    for entry in entries:
        title = _strip_html(entry.get("title", ""))
        if not title:
            continue
        articles.append({
            "title": title,
            "description": _strip_html(entry.get("summary", "")),
            "content": _extract_content(entry),
            "url": entry.get("link", ""),
            "source_name": source_name,
            "source_type": source_type,
            "source_api": "rss",
            "published_at": _parse_entry_date(entry),
        })
    return articles


def _extract_content(entry) -> str | None:
    """RSS 엔트리에서 본문 추출 (HTML 제거)"""
    content_list = entry.get("content", [])
    if not content_list:
        return None
    raw = content_list[0].get("value", "")
    stripped = _strip_html(raw)
    return stripped or None


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
