"""Integration tests for the `DataSource` port and its adapters."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from pool_selector.ingestion.source import DataSource, LocalFileSource, S3Source

NOW = datetime(2026, 7, 19, 14, 30, tzinfo=UTC)


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _partition_key(prefix: str, moment: datetime, filename: str = "events.json") -> str:
    return f"{prefix}dt={moment.date().isoformat()}/hr={moment.hour:02d}/{filename}"


def _partition_path(directory: Path, moment: datetime, filename: str = "events.json") -> Path:
    return directory / f"dt={moment.date().isoformat()}" / f"hr={moment.hour:02d}" / filename


class _CountingClient:
    """Wraps a real (moto-mocked) boto3 S3 client, counting `get_object` calls."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.get_object_calls = 0

    def get_paginator(self, name: str) -> Any:
        return self._client.get_paginator(name)

    def get_object(self, **kwargs: Any) -> Any:
        self.get_object_calls += 1
        return self._client.get_object(**kwargs)


def test_local_file_source_iterates_multiple_json_files_in_the_current_partition(
    tmp_path: Path,
) -> None:
    _write(_partition_path(tmp_path, NOW, "a.json"), ['{"job_id": "a1"}', '{"job_id": "a2"}'])
    _write(_partition_path(tmp_path, NOW, "b.json"), ['{"job_id": "b1"}'])

    source = LocalFileSource(directory=tmp_path, window_minutes=60)

    result = list(source.iter_events(NOW))

    assert result == ['{"job_id": "a1"}', '{"job_id": "a2"}', '{"job_id": "b1"}']


def test_local_file_source_empty_directory_produces_empty_iterator(tmp_path: Path) -> None:
    source = LocalFileSource(directory=tmp_path, window_minutes=60)

    assert list(source.iter_events(NOW)) == []


def test_local_file_source_nonexistent_directory_raises_treatable_error(tmp_path: Path) -> None:
    source = LocalFileSource(directory=tmp_path / "does-not-exist", window_minutes=60)

    with pytest.raises(FileNotFoundError):
        list(source.iter_events(NOW))


def test_local_file_source_satisfies_data_source_protocol(tmp_path: Path) -> None:
    source = LocalFileSource(directory=tmp_path, window_minutes=60)

    assert isinstance(source, DataSource)


def test_local_file_source_ignores_partitions_outside_the_recency_window(tmp_path: Path) -> None:
    far_outside_window = NOW.replace(hour=0)
    _write(_partition_path(tmp_path, far_outside_window), ['{"job_id": "old"}'])
    _write(_partition_path(tmp_path, NOW), ['{"job_id": "recent"}'])

    source = LocalFileSource(directory=tmp_path, window_minutes=60)

    assert list(source.iter_events(NOW)) == ['{"job_id": "recent"}']


def test_local_file_source_spans_multiple_hour_partitions_within_the_window(
    tmp_path: Path,
) -> None:
    one_hour_ago = NOW.replace(hour=NOW.hour - 1, minute=0)
    _write(_partition_path(tmp_path, one_hour_ago), ['{"job_id": "earlier"}'])
    _write(_partition_path(tmp_path, NOW), ['{"job_id": "now"}'])

    source = LocalFileSource(directory=tmp_path, window_minutes=90)

    assert list(source.iter_events(NOW)) == ['{"job_id": "earlier"}', '{"job_id": "now"}']


def test_local_file_source_handles_day_boundary_crossing_partitions(tmp_path: Path) -> None:
    just_after_midnight = datetime(2026, 7, 19, 0, 15, tzinfo=UTC)
    late_previous_day = datetime(2026, 7, 18, 23, 30, tzinfo=UTC)
    _write(_partition_path(tmp_path, late_previous_day), ['{"job_id": "yesterday"}'])
    _write(_partition_path(tmp_path, just_after_midnight), ['{"job_id": "today"}'])

    source = LocalFileSource(directory=tmp_path, window_minutes=60)

    result = list(source.iter_events(just_after_midnight))

    assert result == ['{"job_id": "yesterday"}', '{"job_id": "today"}']


@mock_aws
def test_s3_source_reads_same_events_as_local_file_source_equivalent(tmp_path: Path) -> None:
    """S3Source (moto) produces the same events LocalFileSource would, for
    the current (`now`-hour) partition."""
    lines = ['{"job_id": "s3-1"}', '{"job_id": "s3-2"}']
    _write(_partition_path(tmp_path, NOW), lines)
    local_result = list(LocalFileSource(directory=tmp_path, window_minutes=60).iter_events(NOW))

    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="pool-events")
    client.put_object(Bucket="pool-events", Key=_partition_key("raw/", NOW), Body="\n".join(lines))

    s3_result = list(
        S3Source(bucket="pool-events", prefix="raw/", client=client, window_minutes=60).iter_events(
            NOW
        )
    )

    assert s3_result == local_result


@mock_aws
def test_s3_source_prefix_without_objects_produces_empty_iterator() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="pool-events")

    result = list(
        S3Source(
            bucket="pool-events", prefix="empty/", client=client, window_minutes=60
        ).iter_events(NOW)
    )

    assert result == []


@mock_aws
def test_s3_source_nonexistent_bucket_raises_treatable_error() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    source = S3Source(bucket="does-not-exist", prefix="", client=client, window_minutes=60)

    with pytest.raises(ClientError):
        list(source.iter_events(NOW))


@mock_aws
def test_s3_source_satisfies_data_source_protocol() -> None:
    client = boto3.client("s3", region_name="us-east-1")

    source = S3Source(bucket="pool-events", prefix="", client=client, window_minutes=60)

    assert isinstance(source, DataSource)


@mock_aws
def test_s3_source_ignores_objects_outside_the_recency_window() -> None:
    """Only partitions within `window_minutes` of `now` are read. An object
    sitting hours outside the window is never fetched."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="pool-events")
    far_outside_window = NOW.replace(hour=0)
    client.put_object(
        Bucket="pool-events",
        Key=_partition_key("raw/", far_outside_window),
        Body='{"job_id": "old"}',
    )
    client.put_object(
        Bucket="pool-events", Key=_partition_key("raw/", NOW), Body='{"job_id": "recent"}'
    )

    result = list(
        S3Source(bucket="pool-events", prefix="raw/", client=client, window_minutes=60).iter_events(
            NOW
        )
    )

    assert result == ['{"job_id": "recent"}']


@mock_aws
def test_s3_source_spans_multiple_hour_partitions_within_the_window() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="pool-events")
    one_hour_ago = NOW.replace(hour=NOW.hour - 1, minute=0)
    client.put_object(
        Bucket="pool-events", Key=_partition_key("raw/", one_hour_ago), Body='{"job_id": "earlier"}'
    )
    client.put_object(
        Bucket="pool-events", Key=_partition_key("raw/", NOW), Body='{"job_id": "now"}'
    )

    result = list(
        S3Source(bucket="pool-events", prefix="raw/", client=client, window_minutes=90).iter_events(
            NOW
        )
    )

    assert result == ['{"job_id": "earlier"}', '{"job_id": "now"}']


@mock_aws
def test_s3_source_handles_day_boundary_crossing_partitions() -> None:
    just_after_midnight = datetime(2026, 7, 19, 0, 15, tzinfo=UTC)
    late_previous_day = datetime(2026, 7, 18, 23, 30, tzinfo=UTC)
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="pool-events")
    client.put_object(
        Bucket="pool-events",
        Key=_partition_key("raw/", late_previous_day),
        Body='{"job_id": "yesterday"}',
    )
    client.put_object(
        Bucket="pool-events",
        Key=_partition_key("raw/", just_after_midnight),
        Body='{"job_id": "today"}',
    )

    result = list(
        S3Source(bucket="pool-events", prefix="raw/", client=client, window_minutes=60).iter_events(
            just_after_midnight
        )
    )

    assert result == ['{"job_id": "yesterday"}', '{"job_id": "today"}']


@mock_aws
def test_s3_source_caches_closed_partitions_across_calls_without_refetching() -> None:
    """A partition whose hour has already passed relative to `now` is fetched
    once and served from an in-memory cache afterwards. The current
    (still-open) hour is always re-fetched, since it may still be receiving
    new events."""
    real_client = boto3.client("s3", region_name="us-east-1")
    real_client.create_bucket(Bucket="pool-events")
    closed_hour = NOW.replace(hour=NOW.hour - 1, minute=0)
    real_client.put_object(
        Bucket="pool-events", Key=_partition_key("raw/", closed_hour), Body='{"job_id": "closed"}'
    )
    real_client.put_object(
        Bucket="pool-events", Key=_partition_key("raw/", NOW), Body='{"job_id": "current"}'
    )
    counting_client = _CountingClient(real_client)
    source = S3Source(
        bucket="pool-events", prefix="raw/", client=counting_client, window_minutes=90
    )

    first = list(source.iter_events(NOW))
    calls_after_first = counting_client.get_object_calls
    second = list(source.iter_events(NOW))

    assert first == second == ['{"job_id": "closed"}', '{"job_id": "current"}']
    assert calls_after_first == 2
    assert counting_client.get_object_calls == 3  # only the current hour re-fetched


@mock_aws
def test_s3_source_evicts_cached_partitions_once_they_leave_the_window() -> None:
    """Once the window slides past a cached partition, its entry is dropped.
    Memory stays bounded to the current window, not to the bucket's full
    history."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="pool-events")
    closed_hour = NOW.replace(hour=NOW.hour - 2, minute=0)
    client.put_object(
        Bucket="pool-events",
        Key=_partition_key("raw/", closed_hour),
        Body='{"job_id": "aging-out"}',
    )
    source = S3Source(bucket="pool-events", prefix="raw/", client=client, window_minutes=150)
    closed_partition = f"dt={closed_hour.date().isoformat()}/hr={closed_hour.hour:02d}/"

    list(source.iter_events(NOW))
    assert closed_partition in source._partition_cache  # white-box: verifying eviction

    later = NOW.replace(hour=NOW.hour + 2)
    result = list(source.iter_events(later))

    assert '{"job_id": "aging-out"}' not in result
    assert closed_partition not in source._partition_cache
