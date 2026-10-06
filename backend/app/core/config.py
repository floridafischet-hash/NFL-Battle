from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_PREFIX = "CHANGE_ME"


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

    # Uploads
    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 5

    # OpenClaw agent
    agent_trusted_domains: str = (
        "nfl.com,espn.com,cbssports.com,foxsports.com,apnews.com,reuters.com,"
        "pro-football-reference.com,sports.yahoo.com,nbcsports.com,profootballtalk.nbcsports.com"
    )
    agent_min_confirmations: int = Field(default=1, ge=1, le=5)
    agent_result_min_minutes_after_kickoff: int = 60
    openclaw_webhook_url: str | None = None
    openclaw_webhook_token: str | None = None

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

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if self.app_env == "production":
            for name in ("database_url", "secret_key", "admin_password"):
                value = getattr(self, name) or ""
                if PLACEHOLDER_PREFIX in value:
                    raise ValueError(
                        f"{name.upper()} still contains a '{PLACEHOLDER_PREFIX}' placeholder. "
                        "Run scripts/generate-secrets.sh or set real secrets in .env."
                    )
            if len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production.")
        return self

    @property
    def trusted_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.agent_trusted_domains.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
