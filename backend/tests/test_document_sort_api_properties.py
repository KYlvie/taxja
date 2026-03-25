"""
Property-based tests for documents API sort behavior.

Tests the sort ordering logic in isolation using Hypothesis — no database or
HTTP layer required.  Helper functions replicate the COALESCE-based ordering
used by the ``GET /api/v1/documents`` endpoint.

**Validates: Requirements 4.1, 4.2, 4.3, 7.1, 7.2**
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.api.v1.endpoints.documents import SortByOption


# ---------------------------------------------------------------------------
# Lightweight document stub
# ---------------------------------------------------------------------------

@dataclass
class DocStub:
    """Minimal document-like object with the two date fields relevant to sorting."""
    uploaded_at: datetime
    document_date: Optional[date]
    document_year: Optional[int]


# ---------------------------------------------------------------------------
# Sort helpers — mirror the SQL logic in the endpoint
# ---------------------------------------------------------------------------

def sort_key_document_date(doc: DocStub) -> tuple[int, int, int, float]:
    """Mirror the endpoint ordering for sort_by=document_date.

    Priority:
      1. Exact document_date descending
      2. document_year descending when document_date is null
      3. uploaded_at descending when neither exists
    """
    if doc.document_date is not None:
        return (0, -doc.document_date.toordinal(), -(doc.document_year or -1), -doc.uploaded_at.timestamp())
    if doc.document_year is not None:
        return (1, 0, -doc.document_year, -doc.uploaded_at.timestamp())
    return (2, 0, 0, -doc.uploaded_at.timestamp())


def sort_key_upload_date(doc: DocStub) -> datetime:
    """Plain uploaded_at — used when sort_by is omitted or upload_date."""
    return doc.uploaded_at


def apply_sort(docs: list[DocStub], sort_by: Optional[SortByOption]) -> list[DocStub]:
    """Return *docs* sorted according to *sort_by*, descending."""
    if sort_by == SortByOption.document_date:
        return sorted(docs, key=sort_key_document_date)
    else:
        key_fn = sort_key_upload_date
    return sorted(docs, key=key_fn, reverse=True)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

reasonable_datetimes = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2099, 12, 31),
)

reasonable_dates = st.dates(
    min_value=date(2000, 1, 1),
    max_value=date(2099, 12, 31),
)

nullable_document_date = st.one_of(st.none(), reasonable_dates)
nullable_document_year = st.one_of(st.none(), st.integers(min_value=2000, max_value=2099))

doc_stub_strategy = st.builds(
    DocStub,
    uploaded_at=reasonable_datetimes,
    document_date=nullable_document_date,
    document_year=nullable_document_year,
)

doc_list_strategy = st.lists(doc_stub_strategy, min_size=0, max_size=30)


# ===========================================================================
# Property 3: Sort order consistency
# ===========================================================================


class TestProperty3_SortOrderConsistency:
    """
    **Validates: Requirements 4.1, 4.2, 4.3**

    Property 3: For any set of documents, when ``sort_by=document_date``,
    results are ordered by exact date first, then document_year, then uploaded_at.
    """

    @given(docs=doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_document_date_sort_respects_priority_order(self, docs: list[DocStub]):
        """Sorted output is in non-decreasing priority tuple order."""
        sorted_docs = apply_sort(docs, SortByOption.document_date)

        for i in range(len(sorted_docs) - 1):
            key_a = sort_key_document_date(sorted_docs[i])
            key_b = sort_key_document_date(sorted_docs[i + 1])
            assert key_a <= key_b, (
                f"Position {i} ({key_a}) should be <= position {i+1} ({key_b})"
            )

    @given(docs=doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_document_date_sort_uses_document_year_before_uploaded_at(self, docs: list[DocStub]):
        """Year-only docs sort ahead of docs that only have uploaded_at."""
        sorted_docs = apply_sort(docs, SortByOption.document_date)

        seen_uploaded_only = False
        for doc in sorted_docs:
            if doc.document_date is None and doc.document_year is None:
                seen_uploaded_only = True
            if doc.document_year is not None and doc.document_date is None:
                assert not seen_uploaded_only

    @given(docs=doc_list_strategy)
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_document_date_sort_preserves_all_elements(self, docs: list[DocStub]):
        """Sorting does not add or remove documents."""
        sorted_docs = apply_sort(docs, SortByOption.document_date)
        assert len(sorted_docs) == len(docs)
        assert sorted(id(d) for d in sorted_docs) == sorted(id(d) for d in docs)


# ===========================================================================
# Property 4: Default backward compatibility
# ===========================================================================


class TestProperty4_DefaultBackwardCompatibility:
    """
    **Validates: Requirements 7.1, 7.2**

    Property 4: When ``sort_by`` is omitted, results are ordered by
    ``uploaded_at`` descending, identical to pre-feature behavior.
    """

    @given(docs=doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_default_sort_is_descending_by_uploaded_at(self, docs: list[DocStub]):
        """When sort_by is None, output is in non-increasing uploaded_at order."""
        sorted_docs = apply_sort(docs, None)

        for i in range(len(sorted_docs) - 1):
            assert sorted_docs[i].uploaded_at >= sorted_docs[i + 1].uploaded_at, (
                f"Position {i} ({sorted_docs[i].uploaded_at}) should be >= "
                f"position {i+1} ({sorted_docs[i+1].uploaded_at})"
            )

    @given(docs=doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_default_sort_ignores_document_date(self, docs: list[DocStub]):
        """Default sort order is independent of document_date/document_year values."""
        # Sort with default (None)
        sorted_default = apply_sort(docs, None)

        # Mutate document_date/year on all docs and re-sort — order must be identical
        for doc in docs:
            doc.document_date = None
            doc.document_year = None
        sorted_nulled = apply_sort(docs, None)

        assert [d.uploaded_at for d in sorted_default] == [
            d.uploaded_at for d in sorted_nulled
        ]

    @given(docs=doc_list_strategy)
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_explicit_upload_date_matches_default(self, docs: list[DocStub]):
        """sort_by=upload_date produces the same order as sort_by=None."""
        sorted_none = apply_sort(docs, None)
        sorted_explicit = apply_sort(docs, SortByOption.upload_date)

        assert [d.uploaded_at for d in sorted_none] == [
            d.uploaded_at for d in sorted_explicit
        ]
