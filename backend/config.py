from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""

    # NewsAPI
    newsapi_key: str = ""

    # Naver
    naver_client_id: str = ""
    naver_client_secret: str = ""

    # Supabase PostgreSQL
    database_url: str = ""

    # Scheduler
    collect_interval_minutes: int = 15
    auto_report_enabled: bool = True
    auto_report_min_articles: int = 5
    # 일일 브리핑/의제를 자동 생성할 시각 — 콤마 구분 HH:MM 목록 (서버 로컬 타임존).
    # 실제 편집국처럼 오전·저녁 다회성 브리핑을 지원한다.
    # 빈 문자열이면 cron 미사용 → 수집 파이프라인 말단에서 하루 1회(최초 도달 시) 생성하는
    # 기존 동작으로 폴백.
    briefing_schedule: str = "09:00,18:00"

    @property
    def briefing_schedule_list(self) -> list[tuple[int, int]]:
        """"09:00,18:00" → [(9, 0), (18, 0)]. 잘못된 토큰은 조용히 스킵."""
        out: list[tuple[int, int]] = []
        for raw in self.briefing_schedule.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                h_str, m_str = raw.split(":", 1)
                h, m = int(h_str), int(m_str)
                if 0 <= h <= 23 and 0 <= m <= 59:
                    out.append((h, m))
            except ValueError:
                continue
        return out

    # App — 콤마 구분 문자열. JSON 배열 대신 이 형식을 쓰는 이유는 PowerShell 등
    # 셸에서 따옴표 이스케이프가 깨지는 문제를 피하기 위함.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
