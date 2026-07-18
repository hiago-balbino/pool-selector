"""FastAPI app + startup wiring.

The app instantiates its `DataSource`/`StatsStore`/`RefreshTask` from
`pool_selector.settings.Settings` (a `pydantic-settings` loader over the
environment variables documented in `.env.example`), triggers a
synchronous initial refresh at startup so `StatsStore.get_freshness()` is
populated before traffic is served, and then keeps `RefreshTask.start()`
running as a background loop for the app's lifetime.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from starlette.responses import Response

from pool_selector.api import routes
from pool_selector.domain.recency import RecencyStrategy, SlidingWindowStrategy
from pool_selector.ingestion.source import DataSource, LocalFileSource, S3Source
from pool_selector.observability.logging import configure_logging
from pool_selector.settings import Settings, get_settings
from pool_selector.store.refresh import RefreshTask
from pool_selector.store.stats_store import InMemoryStore, StatsStore

logger = logging.getLogger(__name__)


def _source_from_settings(settings: Settings) -> DataSource:
    if settings.data_source == "s3":
        import boto3  # type: ignore[import-untyped]

        return S3Source(
            bucket=settings.s3_bucket,
            prefix=settings.s3_prefix,
            client=boto3.client("s3"),
        )
    return LocalFileSource(directory=settings.local_data_dir)


def _describe_window(recency: RecencyStrategy) -> str:
    """Human-readable description of the active window, for `RankedPool.window`."""
    if isinstance(recency, SlidingWindowStrategy):
        return f"{recency.window_minutes}m sliding"
    return type(recency).__name__


def create_app(
    *,
    source: DataSource | None = None,
    store: StatsStore | None = None,
    recency: RecencyStrategy | None = None,
    interval_seconds: int | None = None,
    low_confidence_threshold: int | None = None,
) -> FastAPI:
    """Build the FastAPI app and wire `RefreshTask` into its lifespan.

    All dependencies are optional and injectable (default: built from
    `Settings`), so tests can supply fakes without touching real
    filesystem/S3/env state.
    """
    settings = get_settings()
    resolved_store: StatsStore = store if store is not None else InMemoryStore()
    resolved_source = source if source is not None else _source_from_settings(settings)
    resolved_recency: RecencyStrategy = (
        recency
        if recency is not None
        else SlidingWindowStrategy(window_minutes=settings.recency_window_minutes)
    )
    resolved_interval = (
        interval_seconds if interval_seconds is not None else settings.refresh_interval_seconds
    )
    resolved_threshold = (
        low_confidence_threshold
        if low_confidence_threshold is not None
        else settings.low_confidence_threshold
    )

    refresh_task = RefreshTask(
        source=resolved_source,
        store=resolved_store,
        recency=resolved_recency,
        interval_seconds=resolved_interval,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Synchronous initial refresh: freshness must be populated before the
        # app starts accepting traffic, so /ready doesn't report healthy too early.
        refresh_task.run_once()
        background = asyncio.create_task(refresh_task.start())
        try:
            yield
        finally:
            background.cancel()
            with suppress(asyncio.CancelledError):
                await background

    configure_logging()

    app = FastAPI(lifespan=lifespan)
    app.state.store = resolved_store
    app.state.low_confidence_threshold = resolved_threshold
    app.state.window_description = _describe_window(resolved_recency)

    @app.middleware("http")
    async def _logging_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Structured log line for every request."""
        start = time.monotonic()
        response = await call_next(request)
        duration_seconds = time.monotonic() - start
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_seconds": duration_seconds,
            },
        )
        return response

    app.include_router(routes.router)
    return app


app = create_app()
