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
