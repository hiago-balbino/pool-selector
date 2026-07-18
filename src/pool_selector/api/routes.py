"""`GET /get-pools`, `/health` and `/ready` routes.

`/get-pools` response shape: `PoolResponse` (single best pool) when `top_n`
is not supplied; `PoolRankingResponse` (a `pools` list, up to `top_n`
entries) when `top_n` is supplied.

`/health` is liveness (always 200 while the process is alive); `/ready` is
readiness (503 until `StatsStore.get_freshness()` is no longer `None`, i.e.
until the first refresh cycle has completed successfully).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from pool_selector.api.schemas import ErrorResponse, PoolRankingResponse, PoolResponse
from pool_selector.domain.catalog import WorkloadCategory
from pool_selector.domain.selector import PoolFilter, select_best_pools

router = APIRouter()


@router.get(
    "/get-pools",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def get_pools(
    request: Request,
    instance_type: str | None = None,
    family: str | None = None,
    category: WorkloadCategory | None = None,
    top_n: int | None = None,
) -> PoolResponse | PoolRankingResponse:
    # Validated manually (rather than via FastAPI/Pydantic query constraints)
    # so the failure is exactly HTTP 400 --
    # FastAPI's built-in query validation would otherwise return 422.
    if top_n is not None and top_n <= 0:
        raise HTTPException(status_code=400, detail="top_n must be a positive integer")

    stats_by_pool = request.app.state.store.get_stats()
    if not stats_by_pool:
        raise HTTPException(status_code=404, detail="no pool data available in the current window")

    pool_filter = PoolFilter(instance_type=instance_type, family=family, category=category)
    ranked = select_best_pools(
        list(stats_by_pool.values()),
        pool_filter,
        top_n=top_n if top_n is not None else 1,
        low_confidence_threshold=request.app.state.low_confidence_threshold,
        window_description=request.app.state.window_description,
    )
    if not ranked:
        raise HTTPException(status_code=404, detail="no pool matches the given filter")

    if top_n is None:
        return PoolResponse.from_ranked_pool(ranked[0])
    return PoolRankingResponse(pools=[PoolResponse.from_ranked_pool(r) for r in ranked])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: 200 whenever the process can handle a request."""
    return {"status": "ok"}


@router.get("/ready", responses={503: {"model": ErrorResponse}})
def ready(request: Request) -> dict[str, str]:
    """Readiness: fails until the first successful refresh has populated the store."""
    if request.app.state.store.get_freshness() is None:
        raise HTTPException(status_code=503, detail="aggregate not yet loaded")
    return {"status": "ready"}
