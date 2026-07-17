"""Configurable classification of `JobEvent.reason` into categories.

Categories are data (a `ReasonClassification` instance), never hardcoded string
comparisons inside `classify`. Extending a category (e.g. adding a new reason
to `AVAILABILITY_FAILURE`) is a one-line change to the constant, not a code
change to the classification logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Category(StrEnum):
    """Classification outcome for a `JobEvent.reason`."""

    AVAILABILITY_FAILURE = "AVAILABILITY_FAILURE"
    JOB_FAILURE = "JOB_FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ReasonClassification:
    """Configurable mapping of reason strings to categories."""

    availability_failure: frozenset[str] = field(
        default_factory=lambda: frozenset({"SPOT_INSTANCE_TERMINATION"})
    )
    job_failure: frozenset[str] = field(
        default_factory=lambda: frozenset({"TIMED_OUT", "SPARK_EXECUTION_ERROR"})
    )


DEFAULT_CLASSIFICATION = ReasonClassification()


def classify(
    reason: str | None,
    config: ReasonClassification = DEFAULT_CLASSIFICATION,
) -> Category:
    """Classify a reason into a `Category` using the given (or default) config.

    `reason=None` (typical of successful events) and any reason not present
    in either configured set both resolve to `Category.UNKNOWN` — a defined
    outcome, never an exception.
    """
    if reason is None:
        return Category.UNKNOWN
    if reason in config.availability_failure:
        return Category.AVAILABILITY_FAILURE
    if reason in config.job_failure:
        return Category.JOB_FAILURE
    return Category.UNKNOWN
