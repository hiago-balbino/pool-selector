"""Pydantic API schemas mirroring the domain's `RankedPool`.

`PoolResponse` is the default single-pool response body (`top_n` unset);
`PoolRankingResponse` wraps a list of `PoolResponse` for `top_n > 1`.
`ErrorResponse` is the explanatory body used for 400/404 responses.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from pool_selector.domain.models import RankedPool


class PoolResponse(BaseModel):
    """A single ranked pool, enriched for the API response.

    `RankedPool.score` reports `raw_score` (not the internal Wilson
    `confidence_score` used only for ranking order) -- see
    `domain/selector.py`'s `select_best_pools`. This schema mirrors that
    field as-is; it does not expose the internal ranking score.
    """

    pool_id: str
    instance_type: str
    az: str
    score: float
    sample_size: int
    confidence: Literal["low", "normal"]
    window: str

    @classmethod
    def from_ranked_pool(cls, ranked: RankedPool) -> PoolResponse:
        return cls(
            pool_id=ranked.pool_id.raw,
            instance_type=ranked.pool_id.instance_type,
            az=ranked.pool_id.az,
            score=ranked.score,
            sample_size=ranked.sample_size,
            confidence=ranked.confidence,
            window=ranked.window,
        )


class PoolRankingResponse(BaseModel):
    """Ordered list of pools returned when `top_n` is requested."""

    pools: list[PoolResponse]


class ErrorResponse(BaseModel):
    """Explanatory error body for 400/404 responses."""

    detail: str
