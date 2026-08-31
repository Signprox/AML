import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "uat", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENVIRONMENT_DIR = PROJECT_ROOT / "environment"
SUPPORTED_ENVIRONMENTS = {"development", "uat", "production"}


class Settings(BaseSettings):
    app_name: str
    app_env: Environment
    debug: bool
    log_level: LogLevel
    security_headers_enabled: bool
    hsts_enabled: bool
    hsts_max_age: int = Field(ge=0)
    db_host: str
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str
    db_user: str
    db_password: SecretStr
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout: int = Field(default=30, ge=1)
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, ge=1)
    cors_origins: str = ""
    trusted_hosts: str = ""
    rate_limit: str = "100/minute"

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("db_host", "db_name", "db_user", mode="before")
    @classmethod
    def validate_database_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Database configuration value must not be empty")
        return value

    @property
    def database_url(self) -> str:
        username = quote(self.db_user, safe="")
        password = quote(self.db_password.get_secret_value(), safe="")
        database = quote(self.db_name, safe="")
        host = self.db_host

        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return (
            f"postgresql+asyncpg://{username}:{password}"
            f"@{host}:{self.db_port}/{database}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins.strip():
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        if not self.trusted_hosts.strip():
            return []
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    def validate_production_secrets(self) -> None:
        if self.app_env != "production":
            return
        weak_secrets = {"change-me", "dev-only-change-in-production", ""}
        if self.jwt_secret.get_secret_value() in weak_secrets:
            raise ValueError("JWT_SECRET must be set to a strong value in production")
        if self.db_password.get_secret_value() in weak_secrets:
            raise ValueError("DB_PASSWORD must be set to a strong value in production")


def _get_active_environment() -> str:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    if environment not in SUPPORTED_ENVIRONMENTS:
        supported = ", ".join(sorted(SUPPORTED_ENVIRONMENTS))
        raise ValueError(
            f"Unsupported APP_ENV '{environment}'. Expected one of: {supported}."
        )
    return environment


@lru_cache
def get_settings() -> Settings:
    environment = _get_active_environment()
    env_file = ENVIRONMENT_DIR / f".env.{environment}"
    return Settings(_env_file=env_file)
