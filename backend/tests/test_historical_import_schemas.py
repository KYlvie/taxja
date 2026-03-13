"""Tests for historical import Pydantic schemas"""
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.historical_import import (
    HistoricalImportUploadRequest,
    HistoricalImportReviewRequest,
    ImportSessionRequest,
)


class TestHistoricalImportUploadRequest:
    """Tests for HistoricalImportUploadRequest schema"""

    def test_valid_upload_request(self):
        """Test valid upload request"""
        data = {
            "document_type": "e1_form",
            "tax_year": 2023,
        }
        request = HistoricalImportUploadRequest(**data)
        assert request.document_type == "e1_form"
        assert request.tax_year == 2023
        assert request.session_id is None

    def test_valid_upload_request_with_session(self):
        """Test valid upload request with session ID"""
        session_id = uuid4()
        data = {
            "document_type": "bescheid",
            "tax_year": 2022,
            "session_id": session_id,
        }
        request = HistoricalImportUploadRequest(**data)
        assert request.session_id == session_id

    def test_all_document_types(self):
        """Test all valid document types"""
        document_types = ["e1_form", "bescheid", "kaufvertrag", "saldenliste"]
        for doc_type in document_types:
            data = {"document_type": doc_type, "tax_year": 2023}
            request = HistoricalImportUploadRequest(**data)
            assert request.document_type == doc_type

    def test_invalid_document_type(self):
        """Test invalid document type raises validation error"""
        data = {"document_type": "invalid_type", "tax_year": 2023}
        with pytest.raises(ValidationError) as exc_info:
            HistoricalImportUploadRequest(**data)
        assert "document_type" in str(exc_info.value)

    def test_tax_year_in_future(self):
        """Test tax year in the future raises validation error"""
        future_year = date.today().year + 1
        data = {"document_type": "e1_form", "tax_year": future_year}
        with pytest.raises(ValidationError) as exc_info:
            HistoricalImportUploadRequest(**data)
        assert "cannot be in the future" in str(exc_info.value)

    def test_tax_year_too_old(self):
        """Test tax year more than 10 years old raises validation error"""
        old_year = date.today().year - 11
        data = {"document_type": "e1_form", "tax_year": old_year}
        with pytest.raises(ValidationError) as exc_info:
            HistoricalImportUploadRequest(**data)
        assert "too old" in str(exc_info.value)

    def test_tax_year_boundary_valid(self):
        """Test tax year at 10-year boundary is valid"""
        boundary_year = date.today().year - 10
        data = {"document_type": "e1_form", "tax_year": boundary_year}
        request = HistoricalImportUploadRequest(**data)
        assert request.tax_year == boundary_year

    def test_tax_year_below_minimum(self):
        """Test tax year below 2000 raises validation error"""
        data = {"document_type": "e1_form", "tax_year": 1999}
        with pytest.raises(ValidationError) as exc_info:
            HistoricalImportUploadRequest(**data)
        assert "tax_year" in str(exc_info.value)

    def test_tax_year_above_maximum(self):
        """Test tax year above 2030 raises validation error"""
        data = {"document_type": "e1_form", "tax_year": 2031}
        with pytest.raises(ValidationError) as exc_info:
            HistoricalImportUploadRequest(**data)
        assert "tax_year" in str(exc_info.value)


class TestHistoricalImportReviewRequest:
    """Tests for HistoricalImportReviewRequest schema"""

    def test_valid_approval_without_edits(self):
        """Test valid approval without edits"""
        data = {"approved": True}
        request = HistoricalImportReviewRequest(**data)
        assert request.approved is True
        assert request.edited_data is None
        assert request.notes is None

    def test_valid_approval_with_edits(self):
        """Test valid approval with edited data"""
        data = {
            "approved": True,
            "edited_data": {"kz_245": "50000"},
            "notes": "Corrected employment income",
        }
        request = HistoricalImportReviewRequest(**data)
        assert request.approved is True
        assert request.edited_data == {"kz_245": "50000"}
        assert request.notes == "Corrected employment income"

    def test_rejection_without_notes_fails(self):
        """Test rejection without notes raises validation error"""
        data = {"approved": False}
        with pytest.raises(ValidationError) as exc_info:
            HistoricalImportReviewRequest(**data)
        assert "Notes are required when rejecting" in str(exc_info.value)

    def test_rejection_with_notes_succeeds(self):
        """Test rejection with notes is valid"""
        data = {"approved": False, "notes": "Incorrect data extracted"}
        request = HistoricalImportReviewRequest(**data)
        assert request.approved is False
        assert request.notes == "Incorrect data extracted"

    def test_empty_notes_raises_error(self):
        """Test empty notes string raises validation error"""
        data = {"approved": True, "notes": "   "}
        with pytest.raises(ValidationError) as exc_info:
            HistoricalImportReviewRequest(**data)
        assert "cannot be empty" in str(exc_info.value)

    def test_notes_whitespace_trimmed(self):
        """Test notes whitespace is trimmed"""
        data = {"approved": True, "notes": "  Valid note  "}
        request = HistoricalImportReviewRequest(**data)
        assert request.notes == "Valid note"


class TestImportSessionRequest:
    """Tests for ImportSessionRequest schema"""

    def test_valid_session_request(self):
        """Test valid session request"""
        data = {
            "tax_years": [2021, 2022, 2023],
            "document_types": ["e1_form", "bescheid"],
        }
        request = ImportSessionRequest(**data)
        assert request.tax_years == [2021, 2022, 2023]
        assert request.document_types == ["e1_form", "bescheid"]

    def test_tax_years_sorted(self):
        """Test tax years are sorted"""
        data = {
            "tax_years": [2023, 2021, 2022],
            "document_types": ["e1_form"],
        }
        request = ImportSessionRequest(**data)
        assert request.tax_years == [2021, 2022, 2023]

    def test_duplicate_tax_years_fails(self):
        """Test duplicate tax years raises validation error"""
        data = {
            "tax_years": [2021, 2022, 2021],
            "document_types": ["e1_form"],
        }
        with pytest.raises(ValidationError) as exc_info:
            ImportSessionRequest(**data)
        assert "must be unique" in str(exc_info.value)

    def test_duplicate_document_types_fails(self):
        """Test duplicate document types raises validation error"""
        data = {
            "tax_years": [2021, 2022],
            "document_types": ["e1_form", "bescheid", "e1_form"],
        }
        with pytest.raises(ValidationError) as exc_info:
            ImportSessionRequest(**data)
        assert "must be unique" in str(exc_info.value)

    def test_empty_tax_years_fails(self):
        """Test empty tax years list raises validation error"""
        data = {
            "tax_years": [],
            "document_types": ["e1_form"],
        }
        with pytest.raises(ValidationError) as exc_info:
            ImportSessionRequest(**data)
        assert "tax_years" in str(exc_info.value)

    def test_empty_document_types_fails(self):
        """Test empty document types list raises validation error"""
        data = {
            "tax_years": [2021],
            "document_types": [],
        }
        with pytest.raises(ValidationError) as exc_info:
            ImportSessionRequest(**data)
        assert "document_types" in str(exc_info.value)

    def test_too_many_tax_years_fails(self):
        """Test more than 10 tax years raises validation error"""
        data = {
            "tax_years": list(range(2010, 2022)),  # 12 years
            "document_types": ["e1_form"],
        }
        with pytest.raises(ValidationError) as exc_info:
            ImportSessionRequest(**data)
        assert "tax_years" in str(exc_info.value)

    def test_invalid_tax_year_in_list(self):
        """Test invalid tax year in list raises validation error"""
        future_year = date.today().year + 1
        data = {
            "tax_years": [2021, 2022, future_year],
            "document_types": ["e1_form"],
        }
        with pytest.raises(ValidationError) as exc_info:
            ImportSessionRequest(**data)
        assert "cannot be in the future" in str(exc_info.value)

    def test_tax_year_out_of_range_in_list(self):
        """Test tax year out of range in list raises validation error"""
        data = {
            "tax_years": [1999, 2021, 2022],
            "document_types": ["e1_form"],
        }
        with pytest.raises(ValidationError) as exc_info:
            ImportSessionRequest(**data)
        assert "out of valid range" in str(exc_info.value)

    def test_all_document_types_in_session(self):
        """Test all document types can be included in session"""
        data = {
            "tax_years": [2023],
            "document_types": ["e1_form", "bescheid", "kaufvertrag", "saldenliste"],
        }
        request = ImportSessionRequest(**data)
        assert len(request.document_types) == 4
