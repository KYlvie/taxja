"""
Tests for Task 4: Pipeline uses _upload_context for property association.

Covers:
  - _build_mietvertrag_suggestion uses context property_id directly
  - _build_kaufvertrag_suggestion uses context property_id to associate (not create)
  - Address mismatch warning when OCR address differs from target property
  - Fallback to address matching when no context property_id
"""
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_document(doc_id=1, user_id=1, ocr_result=None):
    """Create a mock Document for suggestion builders."""
    doc = MagicMock()
    doc.id = doc_id
    doc.user_id = user_id
    doc.ocr_result = ocr_result or {}
    doc.uploaded_at = datetime(2025, 6, 1)
    return doc


def _make_property(prop_id=None, user_id=1, address="Hauptstraße 10, 1010 Wien",
                   street="Hauptstraße 10", status_val="active"):
    """Create a mock Property model."""
    from unittest.mock import PropertyMock

    prop = MagicMock()
    prop.id = prop_id or uuid4()
    prop.user_id = user_id
    # address and street are hybrid properties, mock them as regular attributes
    prop.address = address
    prop.street = street
    prop.status = MagicMock()
    prop.status.value = status_val
    return prop


def _make_db_session(properties=None):
    """Create a mock DB session that returns given properties on query."""
    db = MagicMock()
    query_mock = MagicMock()
    filter_mock = MagicMock()

    if properties:
        filter_mock.first.return_value = properties[0] if len(properties) == 1 else properties[0]
        filter_mock.all.return_value = properties
    else:
        filter_mock.first.return_value = None
        filter_mock.all.return_value = []

    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock
    return db


# ---------------------------------------------------------------------------
# Mietvertrag: upload_context.property_id direct association
# ---------------------------------------------------------------------------

class TestMietvertragUploadContext:
    """Test _build_mietvertrag_suggestion with _upload_context.property_id."""

    def test_uses_context_property_id_directly(self):
        """When _upload_context.property_id exists, use it instead of address matching."""
        from app.tasks.ocr_tasks import _build_mietvertrag_suggestion

        prop_id = str(uuid4())
        prop = _make_property(prop_id=prop_id, address="Hauptstraße 10, 1010 Wien")
        db = _make_db_session(properties=[prop])

        ocr_data = {
            "monthly_rent": 850.00,
            "property_address": "Hauptstraße 10, 1010 Wien",
            "start_date": "2025-01-01",
            "_upload_context": {"property_id": prop_id},
        }
        doc = _make_document(ocr_result=ocr_data)

        result = MagicMock()
        suggestion_dict = _build_mietvertrag_suggestion(db, doc, result)
        suggestion = suggestion_dict["import_suggestion"]

        assert suggestion is not None
        assert suggestion["data"]["matched_property_id"] == str(prop_id)
        assert suggestion["data"]["no_property_match"] is False
        assert suggestion["data"]["address_mismatch_warning"] is False

    def test_address_mismatch_warning_when_addresses_differ(self):
        """When context property_id exists but OCR address doesn't match, set warning."""
        from app.tasks.ocr_tasks import _build_mietvertrag_suggestion

        prop_id = str(uuid4())
        prop = _make_property(
            prop_id=prop_id,
            address="Ringstraße 5, 1010 Wien",
        )
        db = _make_db_session(properties=[prop])

        ocr_data = {
            "monthly_rent": 1200.00,
            "property_address": "Bergweg 22, 3100 St. Pölten",
            "start_date": "2025-03-01",
            "_upload_context": {"property_id": prop_id},
        }
        doc = _make_document(ocr_result=ocr_data)

        result = MagicMock()
        suggestion_dict = _build_mietvertrag_suggestion(db, doc, result)
        suggestion = suggestion_dict["import_suggestion"]

        assert suggestion is not None
        assert suggestion["data"]["matched_property_id"] == str(prop_id)
        assert suggestion["data"]["address_mismatch_warning"] is True

    def test_no_warning_when_addresses_match(self):
        """When context property_id exists and OCR address matches, no warning."""
        from app.tasks.ocr_tasks import _build_mietvertrag_suggestion

        prop_id = str(uuid4())
        prop = _make_property(
            prop_id=prop_id,
            address="Hauptstraße 10, 1010 Wien",
        )
        db = _make_db_session(properties=[prop])

        ocr_data = {
            "monthly_rent": 950.00,
            "property_address": "Hauptstraße 10",
            "start_date": "2025-02-01",
            "_upload_context": {"property_id": prop_id},
        }
        doc = _make_document(ocr_result=ocr_data)

        result = MagicMock()
        suggestion_dict = _build_mietvertrag_suggestion(db, doc, result)
        suggestion = suggestion_dict["import_suggestion"]

        assert suggestion is not None
        assert suggestion["data"]["address_mismatch_warning"] is False

    def test_fallback_to_address_matching_when_context_property_not_found(self):
        """When context property_id doesn't match any active property, fall back."""
        from app.tasks.ocr_tasks import _build_mietvertrag_suggestion

        bogus_id = str(uuid4())
        db = _make_db_session(properties=[])  # No property found

        ocr_data = {
            "monthly_rent": 700.00,
            "property_address": "Testgasse 1, 1020 Wien",
            "start_date": "2025-01-01",
            "_upload_context": {"property_id": bogus_id},
        }
        doc = _make_document(ocr_result=ocr_data)

        result = MagicMock()
        with patch("app.services.address_matcher.AddressMatcher") as MockMatcher:
            mock_matcher_instance = MagicMock()
            mock_matcher_instance.match_address.return_value = []
            MockMatcher.return_value = mock_matcher_instance

            suggestion_dict = _build_mietvertrag_suggestion(db, doc, result)
            suggestion = suggestion_dict["import_suggestion"]

        assert suggestion is not None
        # Should have fallen back — no match found
        assert suggestion["data"]["matched_property_id"] is None
        assert suggestion["data"]["no_property_match"] is True

    def test_no_upload_context_uses_address_matching(self):
        """Without _upload_context, normal address matching is used."""
        from app.tasks.ocr_tasks import _build_mietvertrag_suggestion

        prop = _make_property(address="Testgasse 1, 1020 Wien")
        db = _make_db_session(properties=[prop])

        ocr_data = {
            "monthly_rent": 600.00,
            "property_address": "Testgasse 1, 1020 Wien",
            "start_date": "2025-01-01",
        }
        doc = _make_document(ocr_result=ocr_data)

        result = MagicMock()
        match_result = MagicMock()
        match_result.confidence = 0.9
        match_result.property = prop

        with patch("app.services.address_matcher.AddressMatcher") as MockMatcher:
            mock_matcher_instance = MagicMock()
            mock_matcher_instance.match_address.return_value = [match_result]
            MockMatcher.return_value = mock_matcher_instance

            suggestion_dict = _build_mietvertrag_suggestion(db, doc, result)
            suggestion = suggestion_dict["import_suggestion"]

        assert suggestion is not None
        assert suggestion["data"]["matched_property_id"] == str(prop.id)
        assert suggestion["data"]["address_mismatch_warning"] is False


# ---------------------------------------------------------------------------
# Kaufvertrag: upload_context.property_id association
# ---------------------------------------------------------------------------

class TestKaufvertragUploadContext:
    """Test _build_kaufvertrag_suggestion with _upload_context.property_id."""

    def test_associates_to_existing_property_with_context(self):
        """When _upload_context.property_id exists, suggestion type is associate_property."""
        from app.tasks.ocr_tasks import _build_kaufvertrag_suggestion

        prop_id = str(uuid4())
        prop = _make_property(prop_id=prop_id, address="Wienerstraße 20, 2700 Wr. Neustadt")
        db = _make_db_session(properties=[prop])

        ocr_data = {
            "purchase_price": 350000,
            "property_address": "Wienerstraße 20, 2700 Wr. Neustadt",
            "purchase_date": "2024-06-15",
            "_upload_context": {"property_id": prop_id},
        }
        doc = _make_document(ocr_result=ocr_data)

        result = MagicMock()
        suggestion_dict = _build_kaufvertrag_suggestion(db, doc, result)
        suggestion = suggestion_dict["import_suggestion"]

        assert suggestion is not None
        assert suggestion["type"] == "associate_property"
        assert suggestion["data"]["existing_property_id"] == str(prop_id)
        assert suggestion["data"]["existing_property_address"] == "Wienerstraße 20, 2700 Wr. Neustadt"
        assert suggestion["data"]["address_mismatch_warning"] is False

    def test_creates_new_property_without_context(self):
        """Without _upload_context, suggestion type is create_property."""
        from app.tasks.ocr_tasks import _build_kaufvertrag_suggestion

        db = _make_db_session(properties=[])

        ocr_data = {
            "purchase_price": 250000,
            "property_address": "Feldgasse 3, 8010 Graz",
            "purchase_date": "2024-09-01",
        }
        doc = _make_document(ocr_result=ocr_data)

        result = MagicMock()
        suggestion_dict = _build_kaufvertrag_suggestion(db, doc, result)
        suggestion = suggestion_dict["import_suggestion"]

        assert suggestion is not None
        assert suggestion["type"] == "create_property"
        assert suggestion["data"]["existing_property_id"] is None
        assert suggestion["data"]["address_mismatch_warning"] is False

    def test_address_mismatch_warning_on_kaufvertrag(self):
        """When context property address differs from OCR address, set warning."""
        from app.tasks.ocr_tasks import _build_kaufvertrag_suggestion

        prop_id = str(uuid4())
        prop = _make_property(prop_id=prop_id, address="Mozartstraße 8, 5020 Salzburg")
        db = _make_db_session(properties=[prop])

        ocr_data = {
            "purchase_price": 500000,
            "property_address": "Linzer Straße 44, 4020 Linz",
            "purchase_date": "2024-03-20",
            "_upload_context": {"property_id": prop_id},
        }
        doc = _make_document(ocr_result=ocr_data)

        result = MagicMock()
        suggestion_dict = _build_kaufvertrag_suggestion(db, doc, result)
        suggestion = suggestion_dict["import_suggestion"]

        assert suggestion is not None
        assert suggestion["type"] == "associate_property"
        assert suggestion["data"]["address_mismatch_warning"] is True

    def test_context_property_not_found_falls_back_to_create(self):
        """When context property_id doesn't exist, fall back to create_property."""
        from app.tasks.ocr_tasks import _build_kaufvertrag_suggestion

        bogus_id = str(uuid4())
        db = _make_db_session(properties=[])

        ocr_data = {
            "purchase_price": 180000,
            "property_address": "Dorfstraße 1, 6020 Innsbruck",
            "purchase_date": "2024-11-10",
            "_upload_context": {"property_id": bogus_id},
        }
        doc = _make_document(ocr_result=ocr_data)

        result = MagicMock()
        suggestion_dict = _build_kaufvertrag_suggestion(db, doc, result)
        suggestion = suggestion_dict["import_suggestion"]

        assert suggestion is not None
        assert suggestion["type"] == "create_property"
        assert suggestion["data"]["existing_property_id"] is None
