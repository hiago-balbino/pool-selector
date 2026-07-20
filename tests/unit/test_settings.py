"""Unit tests for `pool_selector.settings`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pool_selector.settings import Settings

_ENV_VARS = (
    "DATA_SOURCE",
    "LOCAL_DATA_DIR",
    "S3_BUCKET",
    "S3_PREFIX",
    "RECENCY_WINDOW_MINUTES",
    "LOW_CONFIDENCE_THRESHOLD",
    "REFRESH_INTERVAL_SECONDS",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no leftover env vars from the running shell leak into a test."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults_match_spec_when_no_env_vars_set() -> None:
    settings = Settings(_env_file=None)

    assert settings.recency_window_minutes == 60
    assert settings.low_confidence_threshold == 5
    assert settings.data_source == "local"
    assert settings.local_data_dir == Path("./data")
    assert settings.refresh_interval_seconds == 60


def test_recency_window_minutes_override_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECENCY_WINDOW_MINUTES", "120")

    settings = Settings(_env_file=None)

    assert settings.recency_window_minutes == 120


def test_low_confidence_threshold_override_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOW_CONFIDENCE_THRESHOLD", "10")

    settings = Settings(_env_file=None)

    assert settings.low_confidence_threshold == 10


def test_refresh_interval_seconds_override_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFRESH_INTERVAL_SECONDS", "30")

    settings = Settings(_env_file=None)

    assert settings.refresh_interval_seconds == 30


def test_data_source_and_s3_overrides_are_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_SOURCE", "s3")
    monkeypatch.setenv("S3_BUCKET", "spot-events-bucket")
    monkeypatch.setenv("S3_PREFIX", "events/")

    settings = Settings(_env_file=None)

    assert settings.data_source == "s3"
    assert settings.s3_bucket == "spot-events-bucket"
    assert settings.s3_prefix == "events/"


def test_local_data_dir_override_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_DATA_DIR", "/tmp/custom-data")

    settings = Settings(_env_file=None)

    assert settings.local_data_dir == Path("/tmp/custom-data")
