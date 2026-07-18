"""Integration tests for the `DataSource` port and its adapters."""

from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from pool_selector.ingestion.source import DataSource, LocalFileSource, S3Source


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_local_file_source_iterates_multiple_json_files_in_directory(tmp_path: Path) -> None:
    _write(tmp_path / "a.json", ['{"job_id": "a1"}', '{"job_id": "a2"}'])
    _write(tmp_path / "b.json", ['{"job_id": "b1"}'])

    source = LocalFileSource(directory=tmp_path)

    result = list(source.iter_events())

    assert result == ['{"job_id": "a1"}', '{"job_id": "a2"}', '{"job_id": "b1"}']


def test_local_file_source_empty_directory_produces_empty_iterator(tmp_path: Path) -> None:
    source = LocalFileSource(directory=tmp_path)

    assert list(source.iter_events()) == []


def test_local_file_source_nonexistent_directory_raises_treatable_error(tmp_path: Path) -> None:
    source = LocalFileSource(directory=tmp_path / "does-not-exist")

    with pytest.raises(FileNotFoundError):
        list(source.iter_events())


def test_local_file_source_satisfies_data_source_protocol(tmp_path: Path) -> None:
    source = LocalFileSource(directory=tmp_path)

    assert isinstance(source, DataSource)


@mock_aws
def test_s3_source_reads_same_events_as_local_file_source_equivalent(tmp_path: Path) -> None:
    """S3Source (moto) produces the same events LocalFileSource would."""
    lines = ['{"job_id": "s3-1"}', '{"job_id": "s3-2"}']
    _write(tmp_path / "events.json", lines)
    local_result = list(LocalFileSource(directory=tmp_path).iter_events())

    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="pool-events")
    client.put_object(Bucket="pool-events", Key="raw/events.json", Body="\n".join(lines))

    s3_result = list(S3Source(bucket="pool-events", prefix="raw/", client=client).iter_events())

    assert s3_result == local_result


@mock_aws
def test_s3_source_prefix_without_objects_produces_empty_iterator() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="pool-events")

    result = list(S3Source(bucket="pool-events", prefix="empty/", client=client).iter_events())

    assert result == []


@mock_aws
def test_s3_source_nonexistent_bucket_raises_treatable_error() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    source = S3Source(bucket="does-not-exist", prefix="", client=client)

    with pytest.raises(ClientError):
        list(source.iter_events())


@mock_aws
def test_s3_source_satisfies_data_source_protocol() -> None:
    client = boto3.client("s3", region_name="us-east-1")

    source = S3Source(bucket="pool-events", prefix="", client=client)

    assert isinstance(source, DataSource)
