"""Deterministic synthetic data generator.

Produces NDJSON `JobEvent` records (one per line), partitioned into
`dt=YYYY-MM-DD/hr=HH/events.json` files under `--output-dir`, mimicking the
date/hour-partitioned layout of a real S3 bucket. Reuses `PoolId`'s format so
the output is guaranteed to parse cleanly via `ingestion/parser.py`.

Determinism: every random choice is drawn from a single `random.Random(seed)`
instance in a fixed order, so the same `--seed` always yields the same
sequence of events. The only external input is the "today" anchor date
(`--as-of`, defaulting to the current UTC date), which controls how far back
`--days` reaches -- output content itself never depends on wall-clock time.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from random import Random

from pool_selector.domain.models import PoolId

_INSTANCE_TYPES = (
    "c5.xlarge",
    "c6i.large",
    "r5.xlarge",
    "r6.xlarge",
    "m5.large",
    "m6.large",
    "i3.xlarge",
    "t3.medium",
    "t3a.medium",
)

_AVAILABILITY_ZONES = ("us-east-1a", "us-east-1b", "us-east-1c")

# Baseline availability-failure probability per AZ -- some AZs are
# systematically less reliable than others.
_AZ_BASE_FAILURE_RATE = {
    "us-east-1a": 0.05,
    "us-east-1b": 0.15,
    "us-east-1c": 0.30,
}

# reason -> relative weight among failed events (SPOT_INSTANCE_TERMINATION
# dominates, matching this feature's availability-failure category.
_FAILURE_REASON_WEIGHTS = {
    "SPOT_INSTANCE_TERMINATION": 0.7,
    "TIMED_OUT": 0.2,
    "SPARK_EXECUTION_ERROR": 0.1,
}


def _pool_ids() -> list[str]:
    return [
        f"pool-{instance_type}-{az}"
        for instance_type in _INSTANCE_TYPES
        for az in _AVAILABILITY_ZONES
    ]


@dataclass(frozen=True)
class _PoolProfile:
    """Per-pool generation parameters (uneven volume + AZ-driven failure rate)."""

    pool_id: str
    az: str
    volume_weight: float
    base_failure_rate: float


def _build_profiles(rng: Random) -> list[_PoolProfile]:
    """Build one profile per pool_id, weighted for uneven volume across pools."""
    profiles = []
    for pool_id in _pool_ids():
        parsed = PoolId.parse(pool_id)
        az_bias = _AZ_BASE_FAILURE_RATE[parsed.az]
        profiles.append(
            _PoolProfile(
                pool_id=pool_id,
                az=parsed.az,
                volume_weight=rng.uniform(0.2, 1.0),
                base_failure_rate=min(0.95, max(0.01, az_bias + rng.uniform(-0.05, 0.05))),
            )
        )
    return profiles


def _hour_multiplier(hour: int) -> float:
    """Business hours (09-18 UTC) see higher spot pressure than off-hours."""
    return 1.6 if 9 <= hour < 18 else 0.6


def generate_events(
    *,
    seed: int,
    num_events: int,
    days: int,
    as_of: date,
) -> list[dict[str, str | None]]:
    """Generate `num_events` synthetic events spread across `days` days ending `as_of`.

    Pure function of its arguments -- no wall-clock reads -- so the same
    arguments always produce the same event sequence.
    """
    rng = Random(seed)
    profiles = _build_profiles(rng)
    weights = [profile.volume_weight for profile in profiles]

    events: list[dict[str, str | None]] = []
    for index in range(num_events):
        profile = rng.choices(profiles, weights=weights, k=1)[0]
        day_offset = rng.randrange(days) if days > 0 else 0
        hour = rng.randrange(24)
        minute = rng.randrange(60)
        second = rng.randrange(60)
        event_date = as_of - timedelta(days=day_offset)
        finished_at = datetime(
            event_date.year,
            event_date.month,
            event_date.day,
            hour,
            minute,
            second,
            tzinfo=UTC,
        )

        effective_failure_rate = min(0.95, profile.base_failure_rate * _hour_multiplier(hour))
        if rng.random() < effective_failure_rate:
            status = "FAILED"
            reason = rng.choices(
                list(_FAILURE_REASON_WEIGHTS),
                weights=list(_FAILURE_REASON_WEIGHTS.values()),
                k=1,
            )[0]
        else:
            status = "SUCCESS"
            reason = None

        events.append(
            {
                "finished_at": finished_at.isoformat(),
                "job_id": f"job-{index:08d}",
                "pool_id": profile.pool_id,
                "status": status,
                "reason": reason,
            }
        )
    return events


def _partition_path(output_dir: Path, finished_at_iso: str) -> Path:
    finished_at = datetime.fromisoformat(finished_at_iso)
    return output_dir / f"dt={finished_at.date().isoformat()}" / f"hr={finished_at.hour:02d}"


def write_dataset(
    *,
    seed: int,
    num_events: int,
    days: int,
    output_dir: Path,
    as_of: date | None = None,
) -> list[Path]:
    """Generate events and write them as NDJSON, partitioned by date/hour.

    Each partition's `events.json` is opened in truncate ("w") mode, so
    re-running with identical arguments overwrites prior output with the
    same content instead of duplicating it.
    """
    resolved_as_of = as_of if as_of is not None else datetime.now(UTC).date()
    events = generate_events(seed=seed, num_events=num_events, days=days, as_of=resolved_as_of)

    by_partition: dict[Path, list[dict[str, str | None]]] = defaultdict(list)
    for event in events:
        partition = _partition_path(output_dir, event["finished_at"])  # type: ignore[arg-type]
        by_partition[partition].append(event)

    written_paths = []
    for partition, partition_events in sorted(by_partition.items(), key=lambda item: str(item[0])):
        partition.mkdir(parents=True, exist_ok=True)
        file_path = partition / "events.json"
        with file_path.open("w", encoding="utf-8") as handle:
            for event in partition_events:
                handle.write(json.dumps(event) + "\n")
        written_paths.append(file_path)
    return written_paths


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument(
        "--num-events", type=int, default=2000, help="Total number of events to generate"
    )
    parser.add_argument(
        "--days", type=int, default=3, help="Number of days ending today events are spread across"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./data"),
        help="Directory to write partitioned NDJSON files to",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    written = write_dataset(
        seed=args.seed,
        num_events=args.num_events,
        days=args.days,
        output_dir=args.output_dir,
    )
    print(f"wrote {args.num_events} events across {len(written)} partition file(s)")


if __name__ == "__main__":
    main()
