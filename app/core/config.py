import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


Environment = Literal["development", "uat", "production"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_DIR = PROJECT_ROOT / "environment"
SUPPORTED_ENVIRONMENTS = {"development", "uat", "production"}


class Settings(BaseSettings):
    app_name: str
    app_env: Environment
    debug: bool

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )


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

