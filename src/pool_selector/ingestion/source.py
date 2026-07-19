"""`DataSource` port + adapters. `DataSource` isolates the ingestion pipeline
from where raw JSON lines come from (local filesystem vs S3).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DataSource(Protocol):
    """Common protocol for raw event line sources."""

    def iter_events(self) -> Iterator[str]:
        """Yield raw JSON lines, one per event."""
        ...


@dataclass(frozen=True)
class LocalFileSource:
    directory: Path

    def iter_events(self) -> Iterator[str]:
        if not self.directory.exists():
            raise FileNotFoundError(f"data directory not found: {self.directory}")
        for path in sorted(self.directory.rglob("*.json")):
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

    def iter_events(self) -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for entry in sorted(page.get("Contents", []), key=lambda obj: obj["Key"]):
                response = self.client.get_object(Bucket=self.bucket, Key=entry["Key"])
                body = response["Body"].read().decode("utf-8")
                for line in body.splitlines():
                    stripped = line.strip()
                    if stripped:
                        yield stripped
