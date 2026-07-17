"""Unit tests for reason classification."""

import pytest

from pool_selector.domain.reason_classification import (
    Category,
    ReasonClassification,
    classify,
)


def test_classify_spot_instance_termination_is_availability_failure() -> None:
    assert classify("SPOT_INSTANCE_TERMINATION") == Category.AVAILABILITY_FAILURE


@pytest.mark.parametrize("reason", ["TIMED_OUT", "SPARK_EXECUTION_ERROR"])
def test_classify_timed_out_and_spark_execution_error_are_job_failure(reason: str) -> None:
    assert classify(reason) == Category.JOB_FAILURE


def test_classify_none_returns_unknown_without_raising() -> None:
    assert classify(None) == Category.UNKNOWN


def test_classify_unrecognized_reason_returns_unknown_without_raising() -> None:
    assert classify("SOME_UNMAPPED_REASON") == Category.UNKNOWN


def test_classify_extensibility_new_reason_is_one_line_config_change() -> None:
    """Proves adding a reason to a category is a config change, not a code change.

    `classify` itself is untouched here — only the `ReasonClassification`
    instance passed in differs, demonstrating extensibility.
    """
    extended_config = ReasonClassification(
        availability_failure=frozenset({"SPOT_INSTANCE_TERMINATION", "CAPACITY_NOT_AVAILABLE"})
    )

    assert classify("CAPACITY_NOT_AVAILABLE", extended_config) == Category.AVAILABILITY_FAILURE
    # Default config remains unaffected by the extended one.
    assert classify("CAPACITY_NOT_AVAILABLE") == Category.UNKNOWN
