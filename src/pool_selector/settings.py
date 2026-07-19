"""Typed configuration loader."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables (or `.env`)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_source: Literal["local", "s3"] = "local"
    local_data_dir: Path = Path("./data")
    s3_bucket: str = ""
    s3_prefix: str = ""
    recency_window_minutes: int = 60
    low_confidence_threshold: int = 5
    refresh_interval_seconds: int = 60


def get_settings() -> Settings:
    """Build a fresh `Settings` instance from the current environment.

    Deliberately not cached: settings are read once at app startup, and
    tests rely on `monkeypatch.setenv` followed by a fresh call to observe
    overrides without process-wide caching getting in the way.
    """
    return Settings()
