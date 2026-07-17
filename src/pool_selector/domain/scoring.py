"""Availability scoring: configurable failure rate + Wilson confidence bound.

What counts as an "availability failure" is delegated entirely to
`reason_classification.classify` via `is_availability_failure` — never a
hardcoded string comparison in this module. Changing the
`AVAILABILITY_FAILURE` category (e.g. to also include `TIMED_OUT`) changes
`raw_score`'s result purely through the injected `ReasonClassification`
config, with no code change here.
"""

from __future__ import annotations

import math

from pool_selector.domain.models import PoolStats
from pool_selector.domain.reason_classification import (
    Category,
    ReasonClassification,
    classify,
)


def is_availability_failure(reason: str | None, config: ReasonClassification) -> bool:
    """True when `reason` classifies as an availability failure under `config`."""
    return classify(reason, config) is Category.AVAILABILITY_FAILURE


def raw_score(stats: PoolStats) -> float:
    """`1 - availability_failures / total_events`.

    A pool with no events at all has no evidence of failure, so it scores
    1.0 rather than dividing by zero.
    """
    if stats.total_events == 0:
        return 1.0
    return 1 - (stats.availability_failures / stats.total_events)


def wilson_lower_bound(successes: int, total: int, z: float = 1.96) -> float:
    """Lower bound of the Wilson score confidence interval for a proportion.

    Returns 0.0 for `total == 0` (no evidence => no confidence).
    """
    if total == 0:
        return 0.0
    phat = successes / total
    z_squared = z**2
    denominator = 1 + z_squared / total
    center = phat + z_squared / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + z_squared / (4 * total)) / total)
    return (center - margin) / denominator


def confidence_score(stats: PoolStats) -> float:
    """Ranking score: Wilson lower bound of the pool's success rate.

    Successes are `total_events - availability_failures` — this is the
    score used for tie-breaking: larger samples at the same failure
    rate yield a higher (more confident) lower bound.
    """
    successes = stats.total_events - stats.availability_failures
    return wilson_lower_bound(successes, stats.total_events)
