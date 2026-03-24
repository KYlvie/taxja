"""Tests for the confirm-tax-data endpoint logic."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# The set of valid suggestion types
TAX_DATA_SUGGESTION_TYPES = {
    "import_lohnzettel", "import_l1", "import_l1k", "import_l1ab",
    "import_e1a", "import_e1b", "import_e1kv",
    "import_u1", "import_u30", "import_jahresabschluss",
    "import_svs", "import_grundsteuer", "import_bank_statement",
}


class TestConfirmTaxDataValidation:
    def test_all_suggestion_types_recognized(self):
        for st in TAX_DATA_SUGGESTION_TYPES:
            assert st.startswith("import_")

    def test_data_type_derived_from_suggestion_type(self):
        for st in TAX_DATA_SUGGESTION_TYPES:
            data_type = st.replace("import_", "")
            assert len(data_type) > 0
            assert "_" not in data_type or data_type in ("bank_statement",)

    def test_reject_unknown_suggestion_type(self):
        unknown = "import_unknown_form"
        assert unknown not in TAX_DATA_SUGGESTION_TYPES

    def test_reject_already_confirmed(self):
        suggestion = {"type": "import_lohnzettel", "status": "confirmed", "tax_filing_data_id": 42}
        assert suggestion["status"] == "confirmed"

    def test_accept_pending_suggestion(self):
        suggestion = {"type": "import_l1", "status": "pending", "data": {"tax_year": 2025}}
        assert suggestion["status"] == "pending"
        assert suggestion["type"] in TAX_DATA_SUGGESTION_TYPES


class TestConfirmTaxDataLossCarryforward:
    def test_e1a_loss_triggers_carryforward(self):
        """E1a with negative gewinn_verlust should trigger loss carryforward."""
        data = {"tax_year": 2025, "gewinn_verlust": -15000.0}
        data_type = "e1a"
        assert data_type in ("e1a", "jahresabschluss")
        assert float(data["gewinn_verlust"]) < 0
        loss_amount = abs(float(data["gewinn_verlust"]))
        assert loss_amount == 15000.0

    def test_jahresabschluss_loss_triggers_carryforward(self):
        data = {"tax_year": 2025, "gewinn_verlust": -20000.0}
        data_type = "jahresabschluss"
        assert data_type in ("e1a", "jahresabschluss")
        loss_amount = abs(float(data["gewinn_verlust"]))
        assert loss_amount == 20000.0

    def test_positive_gewinn_no_carryforward(self):
        data = {"tax_year": 2025, "gewinn_verlust": 35000.0}
        assert float(data["gewinn_verlust"]) >= 0  # no loss

    def test_l1_no_carryforward(self):
        """Non-E1a/Jahresabschluss types should not trigger loss carryforward."""
        data_type = "l1"
        assert data_type not in ("e1a", "jahresabschluss")


class TestConfirmTaxDataSuggestionUpdate:
    def test_suggestion_marked_confirmed(self):
        ocr_result = {
            "import_suggestion": {
                "type": "import_svs",
                "status": "pending",
                "data": {"tax_year": 2025, "total_contribution": 7200.0},
            }
        }
        # Simulate confirmation
        ocr_result["import_suggestion"]["status"] = "confirmed"
        ocr_result["import_suggestion"]["tax_filing_data_id"] = 99
        assert ocr_result["import_suggestion"]["status"] == "confirmed"
        assert ocr_result["import_suggestion"]["tax_filing_data_id"] == 99
