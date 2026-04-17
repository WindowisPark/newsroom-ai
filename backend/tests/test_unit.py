"""순수 함수 단위 테스트 - 외부 의존성 없음"""

import pytest
from datetime import datetime, timezone


# ── LLM Client: JSON 파싱 ──

class TestParseJson:
    """llm_client._parse_json 단위 테스트"""

    def setup_method(self):
        from backend.analyzers.llm_client import _parse_json
        self.parse = _parse_json

    def test_직접_json(self):
        result = self.parse('{"category": "politics", "score": 8.5}')
        assert result["category"] == "politics"
        assert result["score"] == 8.5

    def test_코드블록_json(self):
        text = '```json\n{"category": "economy"}\n```'
        result = self.parse(text)
        assert result["category"] == "economy"

    def test_코드블록_lang_없음(self):
        text = '```\n{"category": "society"}\n```'
        result = self.parse(text)
        assert result["category"] == "society"

    def test_텍스트_포함_json(self):
        text = 'Here is the analysis:\n{"category": "tech", "keywords": ["AI"]}\nDone.'
        result = self.parse(text)
        assert result["category"] == "tech"

    def test_파싱_실패_시_에러_마커_반환(self):
        result = self.parse("no json here at all")
        assert result.get("parse_error") is True

    def test_빈_json_객체(self):
        result = self.parse("{}")
        assert result == {}

    def test_중첩_json(self):
        text = '{"issues": [{"rank": 1, "topic": "test"}]}'
        result = self.parse(text)
        assert len(result["issues"]) == 1


# ── NewsAPI: 정규화 ──

class TestNewsapiNormalize:
    """newsapi._normalize_articles 단위 테스트"""

    def setup_method(self):
        from backend.collectors.newsapi import _normalize_articles, _parse_datetime
        self.normalize = _normalize_articles
        self.parse_dt = _parse_datetime

    def test_정상_기사_변환(self):
        raw = [{
            "title": "Test Article",
            "description": "Desc",
            "content": "Content",
            "url": "https://example.com/1",
            "source": {"name": "Reuters"},
            "publishedAt": "2026-04-16T09:00:00Z",
        }]
        result = self.normalize(raw)
        assert len(result) == 1
        assert result[0]["title"] == "Test Article"
        assert result[0]["source_name"] == "Reuters"
        assert result[0]["source_type"] == "foreign"
        assert result[0]["source_api"] == "newsapi"

    def test_Removed_기사_필터링(self):
        raw = [{"title": "[Removed]", "url": "https://example.com/2"}]
        result = self.normalize(raw)
        assert len(result) == 0

    def test_타이틀_없는_기사_필터링(self):
        raw = [{"title": None, "url": "https://example.com/3"}]
        result = self.normalize(raw)
        assert len(result) == 0

    def test_날짜_파싱_Z(self):
        dt = self.parse_dt("2026-04-16T09:00:00Z")
        assert dt is not None
        assert dt.year == 2026
        assert dt.tzinfo is not None

    def test_날짜_파싱_None(self):
        assert self.parse_dt(None) is None

    def test_날짜_파싱_잘못된_형식(self):
        assert self.parse_dt("not-a-date") is None


# ── Naver: 정규화 ──

class TestNaverNormalize:
    """naver._normalize_articles, _strip_html, _extract_source 단위 테스트"""

    def setup_method(self):
        from backend.collectors.naver import _normalize_articles, _strip_html, _extract_source
        self.normalize = _normalize_articles
        self.strip = _strip_html
        self.extract = _extract_source

    def test_html_태그_제거(self):
        assert self.strip("<b>강조</b> 텍스트") == "강조 텍스트"

    def test_html_엔티티_디코딩(self):
        assert self.strip("&amp; &lt;tag&gt;") == "& <tag>"

    def test_소스_추출_정상(self):
        assert self.extract("https://www.chosun.com/article/123") == "chosun"

    def test_소스_추출_빈_URL(self):
        assert self.extract("") == "Unknown"

    def test_정상_변환(self):
        raw = [{
            "title": "<b>테스트</b> 기사",
            "description": "요약",
            "originallink": "https://www.hani.co.kr/123",
            "link": "https://n.news.naver.com/123",
            "pubDate": "Thu, 16 Apr 2026 09:00:00 +0900",
        }]
        result = self.normalize(raw)
        assert len(result) == 1
        assert result[0]["title"] == "테스트 기사"  # HTML 제거
        assert result[0]["source_type"] == "domestic"
        assert result[0]["source_api"] == "naver"

    def test_빈_타이틀_필터링(self):
        raw = [{"title": "", "link": "https://n.news.naver.com/1"}]
        result = self.normalize(raw)
        assert len(result) == 0


# ── RSS: 정규화 ──

class TestRssNormalize:
    """rss._normalize_entries, _parse_entry_date 단위 테스트"""

    def setup_method(self):
        from backend.collectors.rss import _normalize_entries, _parse_entry_date, _extract_content
        self.normalize = _normalize_entries
        self.parse_date = _parse_entry_date
        self.extract = _extract_content

    def test_정상_엔트리_변환(self):
        entries = [{"title": "RSS 기사", "summary": "요약", "link": "https://yna.co.kr/1"}]
        result = self.normalize(entries, "연합뉴스")
        assert len(result) == 1
        assert result[0]["source_name"] == "연합뉴스"
        assert result[0]["source_api"] == "rss"

    def test_빈_타이틀_필터링(self):
        entries = [{"title": "", "link": "https://yna.co.kr/2"}]
        result = self.normalize(entries, "연합뉴스")
        assert len(result) == 0

    def test_날짜_파싱_RFC822(self):
        entry = {"published": "Thu, 16 Apr 2026 09:00:00 +0900"}
        dt = self.parse_date(entry)
        assert dt is not None

    def test_날짜_파싱_ISO(self):
        entry = {"published": "2026-04-16T09:00:00Z"}
        dt = self.parse_date(entry)
        assert dt is not None

    def test_날짜_없으면_None(self):
        dt = self.parse_date({})
        assert dt is None

    def test_content_추출(self):
        entry = {"content": [{"value": "본문 내용"}]}
        assert self.extract(entry) == "본문 내용"

    def test_content_없으면_None(self):
        assert self.extract({}) is None


# ── Schemas: Pydantic 검증 ──

class TestSchemas:
    """Pydantic 스키마 직렬화/역직렬화 테스트"""

    def test_api_response_기본(self):
        from backend.models.schemas import APIResponse
        resp = APIResponse(data={"key": "value"})
        assert resp.status == "success"
        assert resp.data == {"key": "value"}
        assert resp.meta is None

    def test_api_response_메타(self):
        from backend.models.schemas import APIResponse, Meta
        resp = APIResponse(data=[], meta=Meta(total=100, page=1, limit=20))
        assert resp.meta.total == 100

    def test_collect_request_기본값(self):
        from backend.models.schemas import CollectRequest
        req = CollectRequest()
        assert req.sources == ["newsapi", "naver", "rss"]
        assert req.query is None

    def test_headline_request(self):
        from backend.models.schemas import HeadlineRequest
        import uuid
        req = HeadlineRequest(topic="경제 위기", article_ids=[uuid.uuid4()], style="analytical")
        assert req.topic == "경제 위기"
        assert req.style == "analytical"
