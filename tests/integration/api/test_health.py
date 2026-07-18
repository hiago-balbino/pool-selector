"""Integration tests for `/health` (liveness) and `/ready` (readiness).

`/health` is always 200 while the process is alive; `/ready`
fails (503) until the first refresh has completed successfully -- i.e. until
`StatsStore.get_freshness()` is no longer `None` -- and succeeds afterwards.

A `_FailingSource` (mirrors `tests/integration/store/test_refresh.py`'s fake)
keeps the store's freshness at `None` even after the app's synchronous
startup refresh runs, since `RefreshTask.run_once()` swallows the exception
without advancing freshness -- this is what makes the "not ready" state
observable through a real, fully-started `TestClient` app rather than
inspecting internal state before startup.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient

from pool_selector.api.app import create_app
from pool_selector.domain.recency import SlidingWindowStrategy
from pool_selector.store.stats_store import InMemoryStore


class _EmptySource:
    """DataSource fake with nothing to yield -- refresh succeeds with {} stats."""

    def iter_events(self) -> Iterator[str]:
        return iter(())


class _FailingSource:
    """DataSource fake simulating a source that never becomes available."""

    def iter_events(self) -> Iterator[str]:
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
    """Liveness must not be coupled to data readiness -- a source outage
    should never make `/health` fail, only `/ready`."""
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
