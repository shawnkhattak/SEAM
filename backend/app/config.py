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
    database_url: str = "postgresql+psycopg://seam_app:changeme_app@localhost:5432/seam"

    # MPA OceansX base URL (not the API key — key lives in app_config)
    oceansx_base_url: str = "https://oceans-x.mpa.gov.sg"

    # Encryption key for app_config secrets (Fernet base64 key)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = ""

    # Bootstrap admin token — used only if app_config has no admin_token set.
    # In production, set the token via admin UI; this env var is then ignored.
    admin_token: str = ""

    # Scheduler cadences (overridden by app_config if set there)
    poll_positions_seconds: int = 900      # 15 minutes
    enrich_particulars_seconds: int = 60   # per-minute enrichment worker
    max_enrich_per_minute: int = 10        # vessels enriched per minute
    pull_weather_seconds: int = 3600
    refresh_news_seconds: int = 3600

    # Timezone default
    display_timezone: str = "America/Chicago"

    # Server
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    # Agent cost cap
    agent_daily_cost_cap_usd: float = 5.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
