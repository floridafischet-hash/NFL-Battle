from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_PREFIX = "CHANGE_ME"


def is_placeholder(value: str | None) -> bool:
    return not value or PLACEHOLDER_PREFIX in value


class Settings(BaseSettings):
    """Runtime configuration. Every value can be set via environment variable (see .env.example)."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_env: Literal["development", "production", "test"] = "development"
    app_name: str = "NFL Bracket Battle"
    app_timezone: str = "Europe/Berlin"
    log_level: str = "INFO"

    public_url: str = "http://localhost:8080"
    database_url: str = "postgresql+psycopg://nfl:nfl@localhost:5432/nfl"
    db_pool_size: int = 10
    db_disable_pool: bool = False

    # Authentication (built-in users, no external identity provider)
    secret_key: str = "CHANGE_ME_secret_key"
    token_ttl_days: int = Field(default=30, ge=1, le=365)
    password_hash_iterations: int = Field(default=210_000, ge=1_000)
    admin_username: str = "admin"
    admin_password: str | None = None
    admin_display_name: str = "Admin"
    demo_user_password: str | None = None

    # Persistent data (uploads, generated secrets)
    data_dir: str = "/data"
    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 5

    # ChatGPT result agent. "chatgpt" uses the Codex CLI signed in with a ChatGPT plan (Plus/Pro, no
    # API key; login once with `docker compose exec backend codex login --device-auth`), "openai_api"
    # uses the OpenAI API with OPENAI_API_KEY.
    result_agent_provider: Literal["chatgpt", "openai_api"] = "chatgpt"
    codex_bin: str = "codex"
    codex_home: str = "/data/codex"
    codex_model: str = ""
    codex_timeout_seconds: int = Field(default=300, ge=30, le=1800)

    # OpenAI API (provider "openai_api"). The key is a secret: set it only in .env or as a file
    # (Docker secret) via OPENAI_API_KEY_FILE – never in the repository.
    openai_api_key: SecretStr | None = None
    openai_api_key_file: str | None = None
    openai_model: str = "gpt-5.4-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_reasoning_effort: Literal["", "none", "minimal", "low", "medium", "high"] = "low"
    openai_timeout_seconds: int = Field(default=120, ge=10, le=600)
    result_agent_enabled: bool = True
    result_agent_tick_seconds: int = Field(default=60, ge=2, le=3600)
    result_agent_first_check_minutes: int = Field(default=200, ge=0, le=1440)
    result_agent_retry_minutes: int = Field(default=20, ge=1, le=1440)
    result_agent_max_calls_per_day: int = Field(default=40, ge=1, le=1000)
    result_agent_max_matches_per_run: int = Field(default=3, ge=1, le=13)

    # Validation of reported results (applies to every ChatGPT answer)
    agent_trusted_domains: str = (
        "nfl.com,espn.com,cbssports.com,foxsports.com,apnews.com,reuters.com,"
        "pro-football-reference.com,sports.yahoo.com,nbcsports.com"
    )
    agent_min_confirmations: int = Field(default=2, ge=1, le=5)
    agent_result_min_minutes_after_kickoff: int = 60

    # Background jobs
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 30
    reminder_hours_before_lock: int = 24

    rate_limit_enabled: bool = True
    seed_demo_data: bool = False

    @field_validator("public_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("openai_base_url")
    @classmethod
    def _http_base_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("OPENAI_BASE_URL muss eine http(s)-URL sein")
        return v.rstrip("/")

    def openai_key(self) -> str | None:
        """The OpenAI API key from OPENAI_API_KEY_FILE or OPENAI_API_KEY (placeholders count as unset)."""
        value: str | None = None
        if self.openai_api_key_file:
            try:
                value = Path(self.openai_api_key_file).read_text().strip()
            except OSError:
                value = None
        elif self.openai_api_key is not None:
            value = self.openai_api_key.get_secret_value().strip()
        return None if is_placeholder(value) else value

    @property
    def has_placeholder_db_password(self) -> bool:
        return PLACEHOLDER_PREFIX in self.database_url

    @property
    def trusted_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.agent_trusted_domains.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
