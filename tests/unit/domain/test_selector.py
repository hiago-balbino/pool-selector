"""Unit tests for the pool selector."""

from pool_selector.domain.catalog import WorkloadCategory
from pool_selector.domain.models import PoolId, PoolStats
from pool_selector.domain.selector import PoolFilter, select_best_pools


def _stats(
    raw_pool_id: str, total_events: int, availability_failures: int, recent_events: int
) -> PoolStats:
    return PoolStats(
        pool_id=PoolId.parse(raw_pool_id),
        total_events=total_events,
        availability_failures=availability_failures,
        recent_events=recent_events,
    )


def test_filter_by_instance_type_reduces_eligible_set() -> None:
    r6 = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    c5 = _stats("pool-c5.large-us-east-1a", 10, 0, 10)

    result = select_best_pools([r6, c5], PoolFilter(instance_type="r6.xlarge"), top_n=2)

    assert [ranked.pool_id.instance_type for ranked in result] == ["r6.xlarge"]


def test_filter_by_family_reduces_eligible_set() -> None:
    r6 = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    r6_2xl = _stats("pool-r6.2xlarge-us-east-1b", 10, 0, 10)
    c5 = _stats("pool-c5.large-us-east-1a", 10, 0, 10)

    result = select_best_pools([r6, r6_2xl, c5], PoolFilter(family="r6"), top_n=3)

    assert {ranked.pool_id.family for ranked in result} == {"r6"}
    assert len(result) == 2


def test_filter_by_category_reduces_eligible_set() -> None:
    memory_pool = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    compute_pool = _stats("pool-c5.large-us-east-1a", 10, 0, 10)

    result = select_best_pools(
        [memory_pool, compute_pool], PoolFilter(category=WorkloadCategory.MEMORY), top_n=2
    )

    assert [ranked.pool_id.raw for ranked in result] == ["pool-r6.xlarge-us-east-1a"]


def test_no_eligible_pool_returns_empty_list() -> None:
    r6 = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)

    result = select_best_pools([r6], PoolFilter(instance_type="m5.2xlarge"))

    assert result == []


def test_ranking_prioritizes_confidence_score_wilson_over_raw_score() -> None:
    """small_perfect has a higher raw_score (1.0, 0 failures) but a much smaller
    sample. large_reliable has a lower raw_score (0.95) but a huge sample. The
    Wilson lower bound favors the large reliable pool.
    """
    small_perfect = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    large_reliable = _stats("pool-r6.2xlarge-us-east-1b", 1000, 50, 1000)

    result = select_best_pools([small_perfect, large_reliable], PoolFilter(), top_n=2)

    assert [ranked.pool_id.raw for ranked in result] == [
        "pool-r6.2xlarge-us-east-1b",
        "pool-r6.xlarge-us-east-1a",
    ]
    assert result[0].score == 0.95
    assert result[1].score == 1.0


def test_top_n_exceeds_eligible_pools_returns_all_without_error() -> None:
    a = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    b = _stats("pool-c5.large-us-east-1a", 10, 1, 10)

    result = select_best_pools([a, b], PoolFilter(), top_n=50)

    assert len(result) == 2


def test_exact_tie_in_confidence_score_resolved_by_recent_activity() -> None:
    more_recent = _stats("pool-r6.xlarge-us-east-1a", 20, 4, recent_events=15)
    less_recent = _stats("pool-r6.xlarge-us-east-1b", 20, 4, recent_events=5)

    result = select_best_pools([less_recent, more_recent], PoolFilter(), top_n=2)

    assert result[0].pool_id.raw == "pool-r6.xlarge-us-east-1a"


def test_exact_tie_resolved_deterministically_by_seed_same_seed_same_result() -> None:
    x = _stats("pool-r6.xlarge-us-east-1a", 20, 4, recent_events=10)
    y = _stats("pool-r6.xlarge-us-east-1b", 20, 4, recent_events=10)

    first_call = select_best_pools([x, y], PoolFilter(), top_n=2, seed=42)
    second_call = select_best_pools([x, y], PoolFilter(), top_n=2, seed=42)

    assert [r.pool_id.raw for r in first_call] == [r.pool_id.raw for r in second_call]


def test_different_seeds_can_change_the_tie_break_order() -> None:
    """The seed factor actually participates in ordering (load distribution),
    not just that results are internally consistent."""
    x = _stats("pool-r6.xlarge-us-east-1a", 20, 4, recent_events=10)
    y = _stats("pool-r6.xlarge-us-east-1b", 20, 4, recent_events=10)

    orders_seen = set()
    for seed in range(20):
        result = select_best_pools([x, y], PoolFilter(), top_n=2, seed=seed)
        orders_seen.add(tuple(r.pool_id.raw for r in result))

    assert len(orders_seen) == 2


def test_ranked_pool_payload_fully_populated_on_happy_path() -> None:
    stats = _stats("pool-r6.xlarge-us-east-1a", 20, 2, recent_events=15)

    result = select_best_pools([stats], PoolFilter(), top_n=1, window_description="60m sliding")

    assert len(result) == 1
    ranked = result[0]
    assert ranked.pool_id == PoolId.parse("pool-r6.xlarge-us-east-1a")
    assert ranked.score == 0.9
    assert ranked.sample_size == 20
    assert ranked.confidence == "normal"
    assert ranked.window == "60m sliding"


def test_low_sample_size_flags_low_confidence() -> None:
    low_sample = _stats("pool-r6.xlarge-us-east-1a", 3, 0, recent_events=3)

    result = select_best_pools([low_sample], PoolFilter(), top_n=1, low_confidence_threshold=5)

    assert result[0].confidence == "low"
