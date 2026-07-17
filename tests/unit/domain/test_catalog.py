"""Unit tests for the instance catalog.

Covers the AWS naming convention fallback (c=compute, r=memory, m=general,
i=storage, t=burstable) for families absent from the catalog.
"""

import pytest

from pool_selector.domain.catalog import WorkloadCategory, category_for_family


def test_category_for_family_returns_explicit_catalog_entry() -> None:
    assert category_for_family("r6") == WorkloadCategory.MEMORY


@pytest.mark.parametrize(
    ("family", "expected"),
    [
        ("c9", WorkloadCategory.COMPUTE),
        ("r9", WorkloadCategory.MEMORY),
        ("m9", WorkloadCategory.GENERAL),
        ("i9", WorkloadCategory.STORAGE),
        ("t9", WorkloadCategory.BURSTABLE),
    ],
)
def test_category_for_family_falls_back_by_first_letter_when_absent_from_catalog(
    family: str, expected: WorkloadCategory
) -> None:
    """`family` is deliberately not in the static catalog, forcing the fallback path."""
    assert category_for_family(family) == expected


def test_category_for_family_unknown_first_letter_returns_defined_default() -> None:
    # "x" is not part of the AWS convention list (c/r/m/i/t) covered by the fallback.
    assert category_for_family("x2") == WorkloadCategory.UNKNOWN
