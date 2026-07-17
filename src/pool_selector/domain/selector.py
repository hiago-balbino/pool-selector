"""Filter + scoring + recency-aware ranking + tie-break orchestration."""

from __future__ import annotations

import random
from dataclasses import dataclass

from pool_selector.domain.catalog import WorkloadCategory, category_for_family
from pool_selector.domain.models import PoolStats, RankedPool
from pool_selector.domain.scoring import confidence_score, raw_score


@dataclass(frozen=True)
class PoolFilter:
    """Optional eligibility filter dimensions for `select_best_pools`."""

    instance_type: str | None = None
    family: str | None = None
    category: WorkloadCategory | None = None


def _is_eligible(stats: PoolStats, pool_filter: PoolFilter) -> bool:
    pool_id = stats.pool_id
    if pool_filter.instance_type is not None and pool_id.instance_type != pool_filter.instance_type:
        return False
    if pool_filter.family is not None and pool_id.family != pool_filter.family:
        return False
    return not (
        pool_filter.category is not None
        and category_for_family(pool_id.family) != pool_filter.category
    )


def _tie_break_key(
    stats: PoolStats, score: float, seed: int | None
) -> tuple[float, int, float, str]:
    random_factor = 0.0
    if seed is not None:
        random_factor = random.Random(f"{seed}:{stats.pool_id.raw}").random()
    return (-score, -stats.recent_events, random_factor, stats.pool_id.raw)


def select_best_pools(
    stats: list[PoolStats],
    filter: PoolFilter,  # noqa: A002 - shadows the builtin, matches the domain's naming
    top_n: int = 1,
    seed: int | None = None,
    low_confidence_threshold: int = 5,
    window_description: str = "unknown",
) -> list[RankedPool]:
    """Filter, rank and tie-break pools, returning up to `top_n` results.

    Ranking is primarily by Wilson lower bound confidence (`confidence_score`),
    which already resolves raw failure-rate ties by favoring larger samples.
    Remaining exact ties are broken by recent activity, then by a seeded
    deterministic factor for load distribution across statistically
    equivalent pools, then by `pool_id` for full determinism when no seed is
    given.
    """
    eligible = [s for s in stats if _is_eligible(s, filter)]
    if not eligible:
        return []

    ranked_stats = sorted(eligible, key=lambda s: _tie_break_key(s, confidence_score(s), seed))

    results = [
        RankedPool(
            pool_id=s.pool_id,
            score=raw_score(s),
            sample_size=s.total_events,
            confidence="low" if s.total_events < low_confidence_threshold else "normal",
            window=window_description,
        )
        for s in ranked_stats
    ]
    return results[:top_n]
