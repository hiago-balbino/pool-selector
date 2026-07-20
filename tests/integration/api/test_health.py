"""Integration tests for `/health` (liveness) and `/ready` (readiness)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from fastapi.testclient import TestClient

from pool_selector.api.app import create_app
from pool_selector.domain.recency import SlidingWindowStrategy
from pool_selector.store.stats_store import InMemoryStore


class _EmptySource:
    """DataSource fake with nothing to yield. Refresh succeeds with {} stats."""

    def iter_events(self, now: datetime) -> Iterator[str]:
        return iter(())


class _FailingSource:
    """DataSource fake simulating a source that never becomes available."""

    def iter_events(self, now: datetime) -> Iterator[str]:
        raise ConnectionError("simulated data source outage")
        yield  # pragma: no cover - unreachable, satisfies generator typing


def _app_with(source: object) -> TestClient:
    app = create_app(
        source=source,  # type: ignore[arg-type]
        store=InMemoryStore(),
        recency=SlidingWindowStrategy(window_minutes=60),
        interval_seconds=3600,
    )
    return TestClient(app)


def test_health_returns_200_when_ready() -> None:
    with _app_with(_EmptySource()) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_health_returns_200_even_when_not_ready() -> None:
    """Liveness must not be coupled to data readiness. A source outage should
    never make `/health` fail, only `/ready`."""
    with _app_with(_FailingSource()) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_ready_returns_503_when_no_refresh_has_ever_succeeded() -> None:
    with _app_with(_FailingSource()) as client:
        response = client.get("/ready")

    assert response.status_code == 503


def test_ready_returns_200_after_first_refresh_succeeds() -> None:
    with _app_with(_EmptySource()) as client:
        response = client.get("/ready")

    assert response.status_code == 200
