"""Tolerant JSON parser."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Iterator
from datetime import datetime

from pool_selector.domain.models import JobEvent

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = ("finished_at", "job_id", "pool_id", "status")


def parse_line(raw: str) -> JobEvent | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("skipping malformed JSON line: %r", raw)
        return None

    if not isinstance(payload, dict):
        logger.warning("skipping non-object JSON line: %r", raw)
        return None

    missing = [field for field in _REQUIRED_FIELDS if field not in payload]
    if missing:
        logger.warning("skipping line missing required fields %s: %r", missing, raw)
        return None

    try:
        finished_at = datetime.fromisoformat(payload["finished_at"])
        return JobEvent(
            finished_at=finished_at,
            job_id=payload["job_id"],
            pool_id=payload["pool_id"],
            status=payload["status"],
            reason=payload.get("reason"),
        )
    except ValueError:
        logger.warning("skipping line with invalid field values: %r", raw)
        return None
    except TypeError:
        logger.warning("skipping line with invalid field values: %r", raw)
        return None


def parse_events(lines: Iterable[str]) -> Iterator[JobEvent]:
    """Parse each line, yielding only the successfully-parsed `JobEvent`s."""
    for line in lines:
        event = parse_line(line)
        if event is not None:
            yield event
