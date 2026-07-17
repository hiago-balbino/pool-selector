"""Static instance family -> workload category catalog.

The catalog is a versioned constant populated from `instances.vantage.sh` at
design time (not a runtime call). Families absent from the catalog fall back
to the AWS naming convention (first letter of the family).
"""

from __future__ import annotations

from enum import StrEnum


class WorkloadCategory(StrEnum):
    """Workload category a pool's instance family serves best."""

    COMPUTE = "compute"
    MEMORY = "memory"
    GENERAL = "general"
    STORAGE = "storage"
    BURSTABLE = "burstable"
    UNKNOWN = "unknown"


_CATALOG: dict[str, WorkloadCategory] = {
    "c5": WorkloadCategory.COMPUTE,
    "c6": WorkloadCategory.COMPUTE,
    "c6i": WorkloadCategory.COMPUTE,
    "r5": WorkloadCategory.MEMORY,
    "r6": WorkloadCategory.MEMORY,
    "m5": WorkloadCategory.GENERAL,
    "m6": WorkloadCategory.GENERAL,
    "i3": WorkloadCategory.STORAGE,
    "t3": WorkloadCategory.BURSTABLE,
    "t3a": WorkloadCategory.BURSTABLE,
}

# AWS naming convention: first letter of the family implies its category.
_FIRST_LETTER_FALLBACK: dict[str, WorkloadCategory] = {
    "c": WorkloadCategory.COMPUTE,
    "r": WorkloadCategory.MEMORY,
    "m": WorkloadCategory.GENERAL,
    "i": WorkloadCategory.STORAGE,
    "t": WorkloadCategory.BURSTABLE,
}


def category_for_family(family: str) -> WorkloadCategory:
    """Resolve a workload category for an instance family.

    Lookup order: explicit catalog entry -> AWS naming-convention fallback
    (first letter) -> `WorkloadCategory.UNKNOWN` when neither applies. Never
    raises for an unrecognized family.
    """
    if family in _CATALOG:
        return _CATALOG[family]
    if family:
        fallback = _FIRST_LETTER_FALLBACK.get(family[0])
        if fallback is not None:
            return fallback
    return WorkloadCategory.UNKNOWN
