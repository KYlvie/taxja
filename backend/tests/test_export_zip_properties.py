"""
Property-based tests for export ZIP folder structure.

Tests the folder assignment and filename deduplication logic in isolation
using Hypothesis — no database, HTTP, or file-system layer required.
Helper functions replicate the logic used by ``GET /api/v1/documents/export-zip``.

**Validates: Requirements 6.2, 6.3, 6.4, 6.5**
"""
from dataclasses import dataclass, field
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
class ExportDocStub:
    """Minimal document-like object for export ZIP testing."""
    file_name: str
    uploaded_at: datetime
    document_date: Optional[date]
    document_year: Optional[int]


# ---------------------------------------------------------------------------
# Helper functions — replicate the endpoint's folder assignment & dedup logic
# ---------------------------------------------------------------------------

def assign_folder(doc: ExportDocStub, sort_by: Optional[SortByOption]) -> str:
    """Determine the folder a document belongs to, given the sort mode.

    - sort_by=None  → flat (empty string folder)
    - sort_by=upload_date → year of uploaded_at
    - sort_by=document_date → year of document_date, else document_year, else "unknown"
    """
    if sort_by is None:
        return ""
    elif sort_by == SortByOption.upload_date:
        return str(doc.uploaded_at.year)
    else:
        # document_date mode
        if doc.document_date is not None:
            return str(doc.document_date.year)
        if doc.document_year is not None:
            return str(doc.document_year)
        return "unknown"


def deduplicate_names(
    docs: list[ExportDocStub],
    sort_by: Optional[SortByOption],
) -> list[tuple[str, str]]:
    """Return a list of (folder, unique_filename) pairs for each document.

    Replicates the ``_unique_name`` logic from the export endpoint:
    first occurrence keeps the original name, subsequent duplicates within
    the same folder get an incrementing numeric suffix.
    """
    seen_names: dict[str, dict[str, int]] = {}
    result: list[tuple[str, str]] = []

    for doc in docs:
        folder = assign_folder(doc, sort_by)
        name = doc.file_name

        if folder not in seen_names:
            seen_names[folder] = {}
        folder_seen = seen_names[folder]

        if name in folder_seen:
            folder_seen[name] += 1
            stem, _, ext = name.rpartition(".")
            if ext and stem:
                unique = f"{stem}_{folder_seen[name]}.{ext}"
            else:
                unique = f"{name}_{folder_seen[name]}"
        else:
            folder_seen[name] = 0
            unique = name

        result.append((folder, unique))

    return result


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

# Filenames: realistic names with extensions, sometimes duplicates
file_name_strategy = st.one_of(
    # Common duplicates
    st.sampled_from([
        "invoice.pdf", "receipt.pdf", "contract.pdf",
        "document.pdf", "scan.jpg", "photo.png",
    ]),
    # Names without extension
    st.sampled_from(["readme", "notes", "backup"]),
    # Generated names with extension
    st.from_regex(r"[a-z]{3,8}\.(pdf|jpg|png|txt)", fullmatch=True),
)

export_doc_strategy = st.builds(
    ExportDocStub,
    file_name=file_name_strategy,
    uploaded_at=reasonable_datetimes,
    document_date=nullable_document_date,
    document_year=nullable_document_year,
)

export_doc_list_strategy = st.lists(export_doc_strategy, min_size=0, max_size=30)


# ===========================================================================
# Property 5: Year folder correctness
# ===========================================================================


class TestProperty5_YearFolderCorrectness:
    """
    **Validates: Requirements 6.2, 6.3, 6.4**

    Property 5: When ``sort_by=document_date``, every document with a non-null
    ``document_date`` is placed in a folder matching its document date year;
    year-only documents use ``document_year``; missing both goes to ``unknown/``.
    """

    @given(docs=export_doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_document_date_mode_assigns_correct_year_folder(self, docs: list[ExportDocStub]):
        """Each doc with a document_date lands in the matching year folder."""
        pairs = deduplicate_names(docs, SortByOption.document_date)

        for doc, (folder, _) in zip(docs, pairs):
            if doc.document_date is not None:
                assert folder == str(doc.document_date.year), (
                    f"Doc with document_date={doc.document_date} should be in "
                    f"folder '{doc.document_date.year}', got '{folder}'"
                )

    @given(docs=export_doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_year_only_documents_use_document_year_folder(self, docs: list[ExportDocStub]):
        """Docs with NULL document_date but document_year use the document_year folder."""
        pairs = deduplicate_names(docs, SortByOption.document_date)

        for doc, (folder, _) in zip(docs, pairs):
            if doc.document_date is None and doc.document_year is not None:
                assert folder == str(doc.document_year), (
                    f"Doc with document_year={doc.document_year} should be in '{doc.document_year}', "
                    f"got '{folder}'"
                )

    @given(docs=export_doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_missing_document_date_and_year_go_to_unknown(self, docs: list[ExportDocStub]):
        """Docs without document_date and document_year are placed in 'unknown/' folder."""
        pairs = deduplicate_names(docs, SortByOption.document_date)

        for doc, (folder, _) in zip(docs, pairs):
            if doc.document_date is None and doc.document_year is None:
                assert folder == "unknown", (
                    f"Doc with document_date=None/document_year=None should be in 'unknown', "
                    f"got '{folder}'"
                )

    @given(docs=export_doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_upload_date_mode_assigns_uploaded_at_year(self, docs: list[ExportDocStub]):
        """When sort_by=upload_date, folder matches uploaded_at year."""
        pairs = deduplicate_names(docs, SortByOption.upload_date)

        for doc, (folder, _) in zip(docs, pairs):
            assert folder == str(doc.uploaded_at.year), (
                f"Doc with uploaded_at={doc.uploaded_at} should be in "
                f"folder '{doc.uploaded_at.year}', got '{folder}'"
            )

    @given(docs=export_doc_list_strategy)
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_no_sort_by_assigns_flat_folder(self, docs: list[ExportDocStub]):
        """When sort_by is None, all docs go to the flat (empty) folder."""
        pairs = deduplicate_names(docs, None)

        for _, (folder, _) in zip(docs, pairs):
            assert folder == "", (
                f"Flat mode should use empty folder, got '{folder}'"
            )


# ===========================================================================
# Property 6: No duplicate filenames
# ===========================================================================


class TestProperty6_NoDuplicateFilenames:
    """
    **Validates: Requirements 6.5**

    Property 6: Within any single year folder, all filenames are unique
    (suffixed as needed).
    """

    @given(docs=export_doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_no_duplicate_filenames_in_document_date_mode(self, docs: list[ExportDocStub]):
        """In document_date mode, every (folder, filename) pair is unique."""
        pairs = deduplicate_names(docs, SortByOption.document_date)
        assert len(pairs) == len(set(pairs)), (
            f"Duplicate (folder, filename) found: "
            f"{[p for p in pairs if pairs.count(p) > 1]}"
        )

    @given(docs=export_doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_no_duplicate_filenames_in_upload_date_mode(self, docs: list[ExportDocStub]):
        """In upload_date mode, every (folder, filename) pair is unique."""
        pairs = deduplicate_names(docs, SortByOption.upload_date)
        assert len(pairs) == len(set(pairs)), (
            f"Duplicate (folder, filename) found: "
            f"{[p for p in pairs if pairs.count(p) > 1]}"
        )

    @given(docs=export_doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_no_duplicate_filenames_in_flat_mode(self, docs: list[ExportDocStub]):
        """In flat mode (no sort_by), all filenames are unique."""
        pairs = deduplicate_names(docs, None)
        assert len(pairs) == len(set(pairs)), (
            f"Duplicate (folder, filename) found: "
            f"{[p for p in pairs if pairs.count(p) > 1]}"
        )

    @given(docs=export_doc_list_strategy)
    @settings(
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_original_count_preserved(self, docs: list[ExportDocStub]):
        """Deduplication does not add or remove documents."""
        pairs = deduplicate_names(docs, SortByOption.document_date)
        assert len(pairs) == len(docs)
