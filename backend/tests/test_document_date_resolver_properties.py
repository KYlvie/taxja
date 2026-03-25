"""
Property-based tests for document date resolver.

Uses Hypothesis to verify correctness properties of resolve_document_date.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**
"""
from datetime import date

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from app.services.document_date_resolver import (
    DATE_FIELD_PRIORITY,
    resolve_document_date,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid ISO date strings (YYYY-MM-DD)
valid_date_strategy = st.dates(
    min_value=date(1900, 1, 1),
    max_value=date(2099, 12, 31),
).map(lambda d: d.isoformat())

# Invalid date strings that should NOT parse
invalid_date_strategy = st.sampled_from([
    "",
    "not-a-date",
    "2024-13-01",
    "2024-00-15",
    "2024-02-30",
    "abcd-ef-gh",
    "31-12-2024",
    "12/31/2024",
    "0000-00-00",
])


# ===========================================================================
# Property 1: Priority chain ordering
# ===========================================================================


class TestProperty1_PriorityChainOrdering:
    """
    **Validates: Requirements 2.1, 2.2**

    Property 1: Given an OCR result with multiple date fields populated,
    resolve_document_date always returns the value of the highest-priority field.

    Priority chain: document_date, date, invoice_date, receipt_date,
    purchase_date, start_date.
    """

    @given(
        dates=st.lists(
            st.dates(min_value=date(1900, 1, 1), max_value=date(2099, 12, 31)),
            min_size=len(DATE_FIELD_PRIORITY),
            max_size=len(DATE_FIELD_PRIORITY),
        ),
        subset_mask=st.lists(
            st.booleans(),
            min_size=len(DATE_FIELD_PRIORITY),
            max_size=len(DATE_FIELD_PRIORITY),
        ),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_returns_highest_priority_field(self, dates, subset_mask):
        """
        For any subset of populated date fields (at least one present),
        the resolver returns the value from the highest-priority field.
        """
        # Ensure at least one field is present
        assume(any(subset_mask))

        ocr_result = {}
        expected = None
        for i, field in enumerate(DATE_FIELD_PRIORITY):
            if subset_mask[i]:
                ocr_result[field] = dates[i].isoformat()
                if expected is None:
                    expected = dates[i]

        result = resolve_document_date(ocr_result)
        assert result == expected, (
            f"Expected {expected} (from highest-priority populated field), "
            f"got {result}. OCR fields: {ocr_result}"
        )

    @given(
        high_date=st.dates(min_value=date(1900, 1, 1), max_value=date(2099, 12, 31)),
        low_date=st.dates(min_value=date(1900, 1, 1), max_value=date(2099, 12, 31)),
        high_idx=st.integers(min_value=0, max_value=len(DATE_FIELD_PRIORITY) - 2),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_higher_priority_always_wins(self, high_date, low_date, high_idx):
        """
        When two fields are populated, the one earlier in the priority chain wins,
        regardless of the actual date values.
        """
        low_idx = high_idx + 1
        assume(low_idx < len(DATE_FIELD_PRIORITY))

        ocr_result = {
            DATE_FIELD_PRIORITY[high_idx]: high_date.isoformat(),
            DATE_FIELD_PRIORITY[low_idx]: low_date.isoformat(),
        }

        result = resolve_document_date(ocr_result)
        assert result == high_date, (
            f"Expected higher-priority field '{DATE_FIELD_PRIORITY[high_idx]}' "
            f"value {high_date}, got {result}"
        )


# ===========================================================================
# Property 2: Fallback to None
# ===========================================================================


class TestProperty2_FallbackToNone:
    """
    **Validates: Requirements 2.2, 2.3, 2.4**

    Property 2: Given an OCR result with no valid date fields (empty strings,
    invalid dates, missing keys), resolve_document_date returns None.
    """

    @given(
        invalid_values=st.lists(
            invalid_date_strategy,
            min_size=0,
            max_size=len(DATE_FIELD_PRIORITY),
        ),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_returns_none_for_invalid_dates(self, invalid_values):
        """
        When all populated fields contain invalid date strings,
        the resolver returns None.
        """
        ocr_result = {}
        for i, val in enumerate(invalid_values):
            if i < len(DATE_FIELD_PRIORITY):
                ocr_result[DATE_FIELD_PRIORITY[i]] = val

        result = resolve_document_date(ocr_result)
        assert result is None, (
            f"Expected None for invalid date fields, got {result}. "
            f"OCR fields: {ocr_result}"
        )

    def test_returns_none_for_none_input(self):
        """resolve_document_date(None) returns None."""
        assert resolve_document_date(None) is None

    def test_returns_none_for_empty_dict(self):
        """resolve_document_date({}) returns None."""
        assert resolve_document_date({}) is None

    def test_returns_none_for_non_dict(self):
        """resolve_document_date with non-dict input returns None."""
        assert resolve_document_date("not a dict") is None
        assert resolve_document_date(42) is None
        assert resolve_document_date([]) is None

    @given(
        non_string_values=st.lists(
            st.one_of(
                st.integers(),
                st.floats(allow_nan=False),
                st.booleans(),
                st.none(),
                st.lists(st.integers(), max_size=2),
            ),
            min_size=1,
            max_size=len(DATE_FIELD_PRIORITY),
        ),
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_returns_none_for_non_string_field_values(self, non_string_values):
        """
        When date fields contain non-string values (ints, floats, bools, None, lists),
        the resolver returns None.
        """
        ocr_result = {}
        for i, val in enumerate(non_string_values):
            if i < len(DATE_FIELD_PRIORITY):
                ocr_result[DATE_FIELD_PRIORITY[i]] = val

        result = resolve_document_date(ocr_result)
        assert result is None, (
            f"Expected None for non-string field values, got {result}. "
            f"OCR fields: {ocr_result}"
        )
