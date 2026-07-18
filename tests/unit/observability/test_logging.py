"""Unit tests for structured JSON logging."""

from __future__ import annotations

import io
import json
import logging

from pool_selector.observability.logging import JsonFormatter, configure_logging


def _emit_and_capture(
    level: int = logging.INFO, msg: str = "hello", extra: dict[str, object] | None = None
) -> str:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test.pool_selector.logging")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
    logger.log(level, msg, extra=extra)
    return stream.getvalue().strip()


def test_emitted_log_line_is_valid_json() -> None:
    line = _emit_and_capture()

    json.loads(line)  # must not raise -- test fails if this is not parseable JSON


def test_emitted_log_line_has_required_fields() -> None:
    line = _emit_and_capture(msg="something happened")

    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["message"] == "something happened"
    assert "timestamp" in payload


def test_emitted_log_line_includes_extra_fields() -> None:
    line = _emit_and_capture(extra={"pool_id": "pool-r6.xlarge-us-east-1a"})

    payload = json.loads(line)
    assert payload["pool_id"] == "pool-r6.xlarge-us-east-1a"


def test_configure_logging_installs_json_formatter_on_root_logger() -> None:
    configure_logging()

    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
