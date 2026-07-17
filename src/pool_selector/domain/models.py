"""Pure domain models for the pool selector (no I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


class PoolIdParseError(ValueError):
    """Raised when a raw pool_id string does not match "pool-<instance-type>-<az>"."""


@dataclass(frozen=True)
class JobEvent:
    """A single validated NDJSON job execution event."""

    finished_at: datetime
    job_id: str
    pool_id: str
    status: str
    reason: str | None


@dataclass(frozen=True)
class PoolId:
    """Parsed representation of a `pool_id` string."""

    raw: str
    instance_type: str
    family: str
    az: str

    @staticmethod
    def parse(raw: str) -> PoolId:
        """Parse "pool-<instance-type>-<az>" into its components.

        `instance_type` never contains a hyphen (e.g. "r6.xlarge"), but `az`
        does (e.g. "us-east-1c", or even multi-hyphen regions like
        "eu-central-1a"). `maxsplit=2` guarantees the AZ segment is captured
        whole instead of being cut at its first internal hyphen.
        """
        parts = raw.split("-", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            raise PoolIdParseError(f"invalid pool_id format: {raw!r}")
        _, instance_type, az = parts
        family = instance_type.split(".", 1)[0]
        return PoolId(raw=raw, instance_type=instance_type, family=family, az=az)


@dataclass
class PoolStats:
    """Aggregated statistics for a pool over the active recency window."""

    pool_id: PoolId
    total_events: int
    availability_failures: int
    recent_events: int


@dataclass
class RankedPool:
    """A pool with its computed score, ready for API response mapping."""

    pool_id: PoolId
    score: float
    sample_size: int
    confidence: Literal["low", "normal"]
    window: str
