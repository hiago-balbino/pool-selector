"""Integration tests for the tolerant JSON parser."""

import logging
from datetime import datetime

import pytest

from pool_selector.domain.models import JobEvent
from pool_selector.ingestion.parser import parse_events, parse_line

VALID_LINE = (
    '{"finished_at": "2026-07-17T12:00:00+00:00", "job_id": "job-1", '
    '"pool_id": "pool-r6.xlarge-us-east-1a", "status": "FAILED", '
    '"reason": "SPOT_INSTANCE_TERMINATION"}'
)


def test_valid_json_with_all_required_fields_produces_correct_job_event() -> None:
    event = parse_line(VALID_LINE)

    assert event == JobEvent(
        finished_at=datetime.fromisoformat("2026-07-17T12:00:00+00:00"),
        job_id="job-1",
        pool_id="pool-r6.xlarge-us-east-1a",
        status="FAILED",
        reason="SPOT_INSTANCE_TERMINATION",
    )


def test_invalid_json_syntax_returns_none_without_raising() -> None:
    result = parse_line("{not valid json")

    assert result is None


def test_valid_json_missing_required_field_returns_none() -> None:
    line = '{"job_id": "job-1", "pool_id": "pool-r6.xlarge-us-east-1a", "status": "FAILED"}'

    result = parse_line(line)

    assert result is None


def test_json_that_is_not_an_object_returns_none() -> None:
    result = parse_line("[1, 2, 3]")

    assert result is None


def test_reason_absent_defaults_to_none() -> None:
    line = (
        '{"finished_at": "2026-07-17T12:00:00+00:00", "job_id": "job-2", '
        '"pool_id": "pool-c5.large-us-east-1a", "status": "SUCCESS"}'
    )

    event = parse_line(line)

    assert event is not None
    assert event.reason is None


def test_parse_events_over_mixed_list_returns_only_valid_preserving_order() -> None:
    second_valid = (
        '{"finished_at": "2026-07-17T13:00:00+00:00", "job_id": "job-3", '
        '"pool_id": "pool-c5.large-us-east-1b", "status": "SUCCESS", "reason": null}'
    )
    lines = [VALID_LINE, "{broken", second_valid, '{"missing": "fields"}']

    result = list(parse_events(lines))

    assert [event.job_id for event in result] == ["job-1", "job-3"]


def test_malformed_line_logs_warning_instead_of_raising(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        result = parse_line("{not valid json")

    assert result is None
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_finished_at_with_wrong_type_returns_none_without_raising() -> None:
    """`finished_at` present but not a string (e.g. a JSON number) makes
    `datetime.fromisoformat` raise TypeError rather than ValueError. The
    parser must catch that too and skip the line, not propagate."""
    line = (
        '{"finished_at": 1234567890, "job_id": "job-1", '
        '"pool_id": "pool-r6.xlarge-us-east-1a", "status": "FAILED"}'
    )

    result = parse_line(line)

    assert result is None
