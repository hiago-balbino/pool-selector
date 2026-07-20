"""Pydantic API schemas mirroring the domain's `RankedPool`."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from pool_selector.domain.models import RankedPool


class PoolResponse(BaseModel):
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
    pools: list[PoolResponse]


class ErrorResponse(BaseModel):
    detail: str
