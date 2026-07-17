"""Pluggable recency (temporal weighting) strategies.

`RecencyStrategy` implementations decide which `JobEvent`s count towards a
pool's stats "now". `SlidingWindowStrategy` applies a hard cutoff at
`window_minutes`, always a constructor parameter (configurable via
settings/env upstream), never hardcoded in this module.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from pool_selector.domain.models import JobEvent


@runtime_checkable
class RecencyStrategy(Protocol):
    """Common protocol for binary (include/exclude) recency filtering strategies."""

    def select_window(self, events: Iterable[JobEvent], now: datetime) -> Iterable[JobEvent]:
        """Return the subset of `events` that count as of `now`."""
        ...


@dataclass(frozen=True)
class SlidingWindowStrategy:
    """Hard cutoff: only events within the last `window_minutes` count.

    `window_minutes` is a construction parameter so different environments
    (or call sites) can use different windows without touching this code.
    """

    window_minutes: int

    def select_window(self, events: Iterable[JobEvent], now: datetime) -> Iterable[JobEvent]:
        cutoff = now - timedelta(minutes=self.window_minutes)
        return [event for event in events if event.finished_at >= cutoff]
