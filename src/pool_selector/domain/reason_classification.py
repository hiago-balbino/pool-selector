"""Configurable classification of `JobEvent.reason` into categories."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Category(StrEnum):
    AVAILABILITY_FAILURE = "AVAILABILITY_FAILURE"
    JOB_FAILURE = "JOB_FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ReasonClassification:
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
    if reason is None:
        return Category.UNKNOWN
    if reason in config.availability_failure:
        return Category.AVAILABILITY_FAILURE
    if reason in config.job_failure:
        return Category.JOB_FAILURE
    return Category.UNKNOWN
