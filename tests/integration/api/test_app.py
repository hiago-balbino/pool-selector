"""Integration tests for the FastAPI app's startup wiring.

Covers: the app starts via `TestClient` without error; before the first
refresh completes, internal state reflects "not ready"; after startup,
`StatsStore.get_freshness()` is no longer `None`.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient

from pool_selector.api.app import create_app
from pool_selector.domain.recency import SlidingWindowStrategy
from pool_selector.store.stats_store import InMemoryStore

VALID_LINE = (
    '{"finished_at": "2026-07-17T12:00:00+00:00", "job_id": "job-1", '
    '"pool_id": "pool-r6.xlarge-us-east-1a", "status": "SUCCESS", "reason": null}'
)


class _FakeSource:
    """DataSource fake yielding a fixed set of raw NDJSON lines."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def iter_events(self) -> Iterator[str]:
        yield from self._lines


def test_app_starts_via_test_client_without_error() -> None:
    app = create_app(
        source=_FakeSource([]),
        store=InMemoryStore(),
        recency=SlidingWindowStrategy(window_minutes=60),
        interval_seconds=3600,
    )

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200


def test_state_reflects_not_ready_before_first_refresh_completes() -> None:
    store = InMemoryStore()
    create_app(
        source=_FakeSource([]),
        store=store,
        recency=SlidingWindowStrategy(window_minutes=60),
        interval_seconds=3600,
    )

    # No lifespan has run yet (TestClient context never entered) -- the
    # store must still report "never refreshed".
    assert store.get_freshness() is None


def test_freshness_is_no_longer_none_after_startup() -> None:
    store = InMemoryStore()
    app = create_app(
        source=_FakeSource([VALID_LINE]),
        store=store,
        recency=SlidingWindowStrategy(window_minutes=60),
        interval_seconds=3600,
    )

    with TestClient(app):
        assert store.get_freshness() is not None
