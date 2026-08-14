from enum import Enum
from typing import Annotated, Literal

from pydantic import BeforeValidator, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    development = "development"
    testing = "testing"
    production = "production"

def parse_cors_origins(v: str | list[str]) -> list[str]:
    if isinstance(v, str):
        if v.startswith("[") and v.endswith("]"):
            import json
            try:
                return list(json.loads(v))
            except Exception:
                pass
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list):
        return [str(i) for i in v]
    return []

def parse_debug_flag(v: object) -> object:
    if isinstance(v, str) and v.lower() in {"release", "prod", "production"}:
        return False
    return v

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "SIET Portal API"
    APP_VERSION: str = "1.0.0"
    ENV: Environment = Environment.development
    DEBUG: Annotated[bool, BeforeValidator(parse_debug_flag)] = False
    API_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    NEWS_ARCHIVE_AFTER_DAYS: int = 90

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/siet_db"
    POSTGRES_POOL_SIZE: int = 10
    POSTGRES_MAX_OVERFLOW: int = 20

    JWT_SECRET: SecretStr = SecretStr("supersecretjwtkey")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    EMAIL_PROVIDER: str = "resend"
    EMAIL_API_KEY: SecretStr = SecretStr("")

    MEILI_URL: str = "http://localhost:7700"
    MEILI_MASTER_KEY: SecretStr = SecretStr("")

    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    R2_BUCKET_NAME: str = ""

    INTERNAL_API_KEY: SecretStr = SecretStr("internal-api-key-secret")
    CONTACT_RECEIVER_EMAIL: str = "ai.lab@siet.ac.in"

    RSS_FEEDS: list[dict[str, str]] = [
        {
            "feed_url": "https://news.google.com/rss/search?q=machine+learning",
            "domain_slug": "machine-learning",
            "source_name": "Google News ML",
        },
        {
            "feed_url": "https://news.google.com/rss/search?q=robotics",
            "domain_slug": "robotics",
            "source_name": "Google News Robotics",
        },
    ]

    ALLOWED_ORIGINS: Annotated[
        list[str] | str,
        BeforeValidator(parse_cors_origins),
    ] = ["http://localhost:3000"]

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None
    ACCESS_COOKIE_NAME: str = "access_token"
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REQUEST_TIMEOUT: int = 30

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        if self.ENV == Environment.production:
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production mode.")
            jwt_val = self.JWT_SECRET.get_secret_value()
            if not jwt_val or jwt_val == "supersecretjwtkey":
                raise ValueError("JWT_SECRET must be set and cannot be the default value in production.")
            internal_val = self.INTERNAL_API_KEY.get_secret_value()
            if not internal_val or internal_val == "internal-api-key-secret":
                raise ValueError("INTERNAL_API_KEY must be set and cannot be the default value in production.")
            if not self.EMAIL_API_KEY.get_secret_value():
                raise ValueError("EMAIL_API_KEY must be configured in production.")
        return self

settings = Settings()
