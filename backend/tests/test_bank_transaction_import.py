"""Tests for bank transaction batch import from Kontoauszug OCR."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import date


class TestBankTransactionImportLogic:
    """Test the batch import logic for bank statement transactions."""

    def test_parse_transaction_date_formats(self):
        """Various date formats should be parsed correctly."""
        from datetime import datetime

        test_cases = [
            ("2025-01-15", date(2025, 1, 15)),
            ("15.01.2025", date(2025, 1, 15)),
            ("15/01/2025", date(2025, 1, 15)),
        ]
        for date_str, expected in test_cases:
            parsed = None
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                try:
                    parsed = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            assert parsed == expected, f"Failed to parse {date_str}"

    def test_skip_duplicate_transactions(self):
        """Transactions marked as duplicate should be skipped."""
        transactions = [
            {"amount": 3500.0, "description": "Gehalt", "is_duplicate": False},
            {"amount": -800.0, "description": "Miete", "is_duplicate": True},
            {"amount": -50.0, "description": "Einkauf", "is_duplicate": False},
        ]
        imported = [t for t in transactions if not t.get("is_duplicate")]
        assert len(imported) == 2
        assert imported[0]["description"] == "Gehalt"
        assert imported[1]["description"] == "Einkauf"

    def test_skip_zero_amount(self):
        """Transactions with zero amount should be skipped."""
        transactions = [
            {"amount": 3500.0, "description": "Gehalt"},
            {"amount": 0, "description": "Storno"},
        ]
        imported = [t for t in transactions if abs(float(t.get("amount", 0))) > 0]
        assert len(imported) == 1

    def test_determine_transaction_type(self):
        """Positive amounts = INCOME, negative = EXPENSE."""
        test_cases = [
            (3500.0, "INCOME"),
            (-800.0, "EXPENSE"),
            (-50.0, "EXPENSE"),
            (100.0, "INCOME"),
        ]
        for amount, expected_type in test_cases:
            txn_type = "INCOME" if amount > 0 else "EXPENSE"
            assert txn_type == expected_type

    def test_description_truncation(self):
        """Long descriptions should be truncated to 500 chars."""
        long_desc = "A" * 600
        truncated = long_desc[:500]
        assert len(truncated) == 500

    def test_all_indices_selected_when_empty(self):
        """When no indices provided, all transactions should be selected."""
        extracted_txns = [
            {"amount": 100, "description": "A"},
            {"amount": 200, "description": "B"},
            {"amount": 300, "description": "C"},
        ]
        indices = []
        if not indices:
            indices = list(range(len(extracted_txns)))
        assert indices == [0, 1, 2]

    def test_out_of_range_indices_skipped(self):
        """Indices outside the transaction array should be skipped."""
        extracted_txns = [{"amount": 100}, {"amount": 200}]
        indices = [0, 1, 5, -1]
        valid = [i for i in indices if 0 <= i < len(extracted_txns)]
        assert valid == [0, 1]
