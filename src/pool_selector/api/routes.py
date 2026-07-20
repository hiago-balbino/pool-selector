"""`GET /get-pools`, `/health` and `/ready` routes."""

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
    return {"status": "ok"}


@router.get("/ready", responses={503: {"model": ErrorResponse}})
def ready(request: Request) -> dict[str, str]:
    if request.app.state.store.get_freshness() is None:
        raise HTTPException(status_code=503, detail="aggregate not yet loaded")
    return {"status": "ready"}
