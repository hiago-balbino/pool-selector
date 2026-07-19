"""`DataSource` port + adapters. `DataSource` isolates the ingestion pipeline
from where raw JSON lines come from (local filesystem vs S3).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DataSource(Protocol):
    """Common protocol for raw event line sources."""

    def iter_events(self, now: datetime) -> Iterator[str]:
        """Yield raw JSON lines relevant as of `now`, one per event."""
        ...


def _relevant_partitions(now: datetime, window_minutes: int) -> list[str]:
    """Hour-partition prefixes (`dt=.../hr=.../`) touching `[now - window, now]`,
    oldest first. The last entry is always `now`'s own (still-open) hour."""
    cursor = (now - timedelta(minutes=window_minutes)).replace(minute=0, second=0, microsecond=0)
    partitions = []
    while cursor <= now:
        partitions.append(f"dt={cursor.date().isoformat()}/hr={cursor.hour:02d}/")
        cursor += timedelta(hours=1)
    return partitions


@dataclass(frozen=True)
class LocalFileSource:
    directory: Path
    window_minutes: int

    def iter_events(self, now: datetime) -> Iterator[str]:
        if not self.directory.exists():
            raise FileNotFoundError(f"data directory not found: {self.directory}")
        for partition in _relevant_partitions(now, self.window_minutes):
            partition_dir = self.directory / partition
            if not partition_dir.exists():
                continue
            for path in sorted(partition_dir.glob("*.json")):
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        stripped = line.strip()
                        if stripped:
                            yield stripped


@dataclass(frozen=True)
class S3Source:
    bucket: str
    prefix: str
    client: Any
    window_minutes: int
    _partition_cache: dict[str, list[str]] = field(default_factory=dict, repr=False, compare=False)

    def iter_events(self, now: datetime) -> Iterator[str]:
        partitions = _relevant_partitions(now, self.window_minutes)
        current = partitions[-1]

        for cached_partition in list(self._partition_cache):
            if cached_partition not in partitions:
                del self._partition_cache[cached_partition]

        for partition in partitions:
            if partition != current and partition in self._partition_cache:
                yield from self._partition_cache[partition]
                continue
            lines = list(self._fetch_partition(partition))
            if partition != current:
                self._partition_cache[partition] = lines
            yield from lines

    def _fetch_partition(self, partition: str) -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=f"{self.prefix}{partition}"):
            for entry in sorted(page.get("Contents", []), key=lambda obj: obj["Key"]):
                response = self.client.get_object(Bucket=self.bucket, Key=entry["Key"])
                body = response["Body"].read().decode("utf-8")
                for line in body.splitlines():
                    stripped = line.strip()
                    if stripped:
                        yield stripped
