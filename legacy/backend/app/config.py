from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+psycopg://oceansx_app:changeme_app@localhost:5432/oceansx"

    # MPA OceansX API
    oceansx_base_url: str = "https://oceans-x.mpa.gov.sg"
    oceansx_api_key: str = ""
    oceansx_mock_mode: Literal["auto", "always", "never"] = "auto"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_mock_mode: bool = True  # flip to False in production

    # Admin
    admin_token: str = ""

    # RSS.app feed URLs and HMAC secrets
    rss_app_feed_1_url: str = ""
    rss_app_feed_2_url: str = ""
    rss_app_feed_3_url: str = ""
    rss_app_feed_1_hmac: str = ""
    rss_app_feed_2_hmac: str = ""
    rss_app_feed_3_hmac: str = ""

    # OpenSanctions
    opensanctions_api_key: str = ""
    opensanctions_mock_mode: bool = True  # flip to False in production

    # Scheduler cadences
    poll_positions_seconds: int = 900  # 15 minutes
    enrich_particulars_seconds: int = 3600
    pull_weather_seconds: int = 3600
    refresh_news_seconds: int = 3600

    # Timezone
    display_timezone: str = "America/Chicago"

    # Server
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    # Agent cost cap
    agent_daily_cost_cap_usd: float = 5.0

    @property
    def use_mocks(self) -> bool:
        if self.oceansx_mock_mode == "always":
            return True
        if self.oceansx_mock_mode == "never":
            return False
        return not bool(self.oceansx_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
