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

    # App
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
