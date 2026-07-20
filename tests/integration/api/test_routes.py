"""Integration/e2e tests for `GET /get-pools`."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pool_selector.api.app import create_app
from pool_selector.domain.catalog import WorkloadCategory
from pool_selector.domain.models import PoolId, PoolStats
from pool_selector.domain.recency import SlidingWindowStrategy
from pool_selector.store.stats_store import InMemoryStore


class _EmptySource:
    """DataSource fake with nothing to yield. Refresh always aggregates to {}."""

    def iter_events(self, now: datetime) -> Iterator[str]:
        return iter(())


def _stats(
    raw_pool_id: str, total_events: int, availability_failures: int, recent_events: int
) -> PoolStats:
    return PoolStats(
        pool_id=PoolId.parse(raw_pool_id),
        total_events=total_events,
        availability_failures=availability_failures,
        recent_events=recent_events,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    store = InMemoryStore()
    app: FastAPI = create_app(
        source=_EmptySource(),
        store=store,
        recency=SlidingWindowStrategy(window_minutes=60),
        interval_seconds=3600,
        low_confidence_threshold=5,
    )
    with TestClient(app) as test_client:
        test_client.app.state.store = store  # type: ignore[attr-defined]
        yield test_client


def _seed(client: TestClient, stats: dict[PoolId, PoolStats]) -> None:
    client.app.state.store.upsert_stats(stats)  # type: ignore[attr-defined]


def test_happy_path_no_filter_returns_enriched_best_pool(client: TestClient) -> None:
    best = _stats("pool-r6.xlarge-us-east-1a", 20, 0, recent_events=20)
    worse = _stats("pool-c5.large-us-east-1b", 20, 5, recent_events=15)
    _seed(client, {best.pool_id: best, worse.pool_id: worse})

    response = client.get("/get-pools")

    assert response.status_code == 200
    body = response.json()
    assert body["pool_id"] == "pool-r6.xlarge-us-east-1a"
    assert body["instance_type"] == "r6.xlarge"
    assert body["az"] == "us-east-1a"
    assert body["score"] == 1.0
    assert body["sample_size"] == 20
    assert body["confidence"] == "normal"
    assert body["window"] == "60m sliding"


def test_filter_by_instance_type(client: TestClient) -> None:
    r6 = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    c5 = _stats("pool-c5.large-us-east-1a", 10, 0, 10)
    _seed(client, {r6.pool_id: r6, c5.pool_id: c5})

    response = client.get("/get-pools", params={"instance_type": "r6.xlarge"})

    assert response.status_code == 200
    assert response.json()["instance_type"] == "r6.xlarge"


def test_filter_by_family(client: TestClient) -> None:
    r6 = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    c5 = _stats("pool-c5.large-us-east-1a", 10, 0, 10)
    _seed(client, {r6.pool_id: r6, c5.pool_id: c5})

    response = client.get("/get-pools", params={"family": "r6"})

    assert response.status_code == 200
    assert response.json()["pool_id"] == "pool-r6.xlarge-us-east-1a"


def test_filter_by_category(client: TestClient) -> None:
    memory_pool = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    compute_pool = _stats("pool-c5.large-us-east-1a", 10, 0, 10)
    _seed(client, {memory_pool.pool_id: memory_pool, compute_pool.pool_id: compute_pool})

    response = client.get("/get-pools", params={"category": WorkloadCategory.MEMORY.value})

    assert response.status_code == 200
    assert response.json()["pool_id"] == "pool-r6.xlarge-us-east-1a"


def test_filter_with_no_matching_pool_returns_404_with_explanatory_body(
    client: TestClient,
) -> None:
    r6 = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    _seed(client, {r6.pool_id: r6})

    response = client.get("/get-pools", params={"instance_type": "m5.2xlarge"})

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert response.json()["detail"] != ""


def test_no_data_in_window_returns_404(client: TestClient) -> None:
    # No seeding at all -- the empty-source refresh already left the store empty.
    response = client.get("/get-pools")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert response.json()["detail"] != ""


def test_low_sample_size_returns_200_with_low_confidence(client: TestClient) -> None:
    low_sample = _stats("pool-r6.xlarge-us-east-1a", 2, 0, recent_events=2)
    _seed(client, {low_sample.pool_id: low_sample})

    response = client.get("/get-pools")

    assert response.status_code == 200
    assert response.json()["confidence"] == "low"


def test_top_n_returns_ordered_ranking(client: TestClient) -> None:
    best = _stats("pool-r6.xlarge-us-east-1a", 100, 0, recent_events=100)
    worst = _stats("pool-c5.large-us-east-1b", 100, 20, recent_events=80)
    _seed(client, {best.pool_id: best, worst.pool_id: worst})

    response = client.get("/get-pools", params={"top_n": 2})

    assert response.status_code == 200
    pools = response.json()["pools"]
    assert [p["pool_id"] for p in pools] == [
        "pool-r6.xlarge-us-east-1a",
        "pool-c5.large-us-east-1b",
    ]


def test_top_n_exceeding_eligible_pools_returns_all_without_error(client: TestClient) -> None:
    a = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    b = _stats("pool-c5.large-us-east-1a", 10, 1, 10)
    _seed(client, {a.pool_id: a, b.pool_id: b})

    response = client.get("/get-pools", params={"top_n": 50})

    assert response.status_code == 200
    assert len(response.json()["pools"]) == 2


def test_top_n_zero_returns_400(client: TestClient) -> None:
    a = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    _seed(client, {a.pool_id: a})

    response = client.get("/get-pools", params={"top_n": 0})

    assert response.status_code == 400


def test_top_n_negative_returns_400(client: TestClient) -> None:
    a = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    _seed(client, {a.pool_id: a})

    response = client.get("/get-pools", params={"top_n": -1})

    assert response.status_code == 400


def test_top_n_absent_defaults_to_single_pool_response_shape(client: TestClient) -> None:
    a = _stats("pool-r6.xlarge-us-east-1a", 10, 0, 10)
    _seed(client, {a.pool_id: a})

    response = client.get("/get-pools")

    assert response.status_code == 200
    assert "pools" not in response.json()
    assert response.json()["pool_id"] == "pool-r6.xlarge-us-east-1a"
