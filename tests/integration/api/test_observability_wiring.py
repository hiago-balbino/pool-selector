"""Integration tests for logging wired into the app.

`JsonFormatter`'s own JSON-correctness is already covered by
`tests/unit/observability/test_logging.py` -- this test only proves the
*wiring*: that the middleware actually runs on every request and feeds the
logger with the request's method/path/status/duration.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from fastapi.testclient import TestClient

from pool_selector.api.app import create_app
from pool_selector.domain.recency import SlidingWindowStrategy
from pool_selector.store.stats_store import InMemoryStore


class _EmptySource:
    def iter_events(self) -> Iterator[str]:
        return iter(())


class _RecordCollector(logging.Handler):
    """Collects emitted `LogRecord`s directly, bypassing whatever handler
    `configure_logging()` installs on the root logger -- attaching straight
    to the app's own logger keeps this test independent of that global
    (root-wide) side effect."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _client() -> TestClient:
    app = create_app(
        source=_EmptySource(),
        store=InMemoryStore(),
        recency=SlidingWindowStrategy(window_minutes=60),
        interval_seconds=3600,
    )
    return TestClient(app)


def test_real_request_produces_structured_log() -> None:
    collector = _RecordCollector()
    app_logger = logging.getLogger("pool_selector.api.app")
    app_logger.addHandler(collector)
    app_logger.setLevel(logging.INFO)
    try:
        with _client() as client:
            response = client.get("/health")
    finally:
        app_logger.removeHandler(collector)

    assert response.status_code == 200

    matching = [r for r in collector.records if getattr(r, "path", None) == "/health"]
    assert len(matching) == 1
    assert matching[0].method == "GET"
    assert matching[0].status_code == 200
