"""Integration tests for the `StatsStore` port and `InMemoryStore`.

Covers `InMemoryStore` concurrency: atomic reference swap, never
incremental mutation of the dict in use.
"""

import threading

from pool_selector.domain.models import PoolId, PoolStats
from pool_selector.store.stats_store import InMemoryStore, StatsStore


def _stats_dict(prefix: str, count: int) -> dict[PoolId, PoolStats]:
    result: dict[PoolId, PoolStats] = {}
    for i in range(count):
        pool_id = PoolId.parse(f"pool-r6.xlarge-us-east-{prefix}{i}")
        result[pool_id] = PoolStats(
            pool_id=pool_id, total_events=10, availability_failures=0, recent_events=10
        )
    return result


def test_get_stats_before_any_upsert_returns_empty() -> None:
    store = InMemoryStore()

    assert store.get_stats() == {}


def test_get_freshness_before_any_upsert_returns_none() -> None:
    store = InMemoryStore()

    assert store.get_freshness() is None


def test_upsert_stats_updates_the_aggregate() -> None:
    store = InMemoryStore()
    stats = _stats_dict("a", 2)

    store.upsert_stats(stats)

    assert store.get_stats() == stats


def test_upsert_stats_sets_freshness_to_a_timestamp() -> None:
    store = InMemoryStore()

    store.upsert_stats(_stats_dict("a", 1))

    assert store.get_freshness() is not None


def test_upsert_stats_fully_replaces_previous_aggregate_not_merges() -> None:
    store = InMemoryStore()
    first = _stats_dict("a", 2)
    second = _stats_dict("b", 3)

    store.upsert_stats(first)
    store.upsert_stats(second)

    assert store.get_stats() == second
    assert set(store.get_stats().keys()).isdisjoint(first.keys())


def test_mutating_caller_dict_after_upsert_does_not_affect_store() -> None:
    """Proves upsert_stats copies rather than aliasing the caller's dict --
    a prerequisite for true atomic-swap (not incremental mutation) semantics."""
    store = InMemoryStore()
    stats = _stats_dict("a", 1)
    original_pool_id = next(iter(stats))

    store.upsert_stats(stats)
    stats.clear()

    assert store.get_stats() != {}
    assert original_pool_id in store.get_stats()


def test_concurrent_reads_during_upsert_never_observe_partial_state() -> None:
    store = InMemoryStore()
    dict_a = _stats_dict("a", 200)
    dict_b = _stats_dict("b", 200)
    keys_a = frozenset(dict_a.keys())
    keys_b = frozenset(dict_b.keys())

    violations: list[frozenset[PoolId]] = []
    stop = threading.Event()

    def writer() -> None:
        while not stop.is_set():
            store.upsert_stats(dict_a)
            store.upsert_stats(dict_b)

    def reader() -> None:
        for _ in range(2000):
            observed = frozenset(store.get_stats().keys())
            if observed not in (frozenset(), keys_a, keys_b):
                violations.append(observed)

    writer_thread = threading.Thread(target=writer)
    reader_thread = threading.Thread(target=reader)
    writer_thread.start()
    reader_thread.start()
    reader_thread.join()
    stop.set()
    writer_thread.join()

    assert violations == []


def test_in_memory_store_satisfies_stats_store_protocol() -> None:
    store = InMemoryStore()

    assert isinstance(store, StatsStore)
