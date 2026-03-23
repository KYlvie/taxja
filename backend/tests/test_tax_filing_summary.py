"""Tests for tax filing summary API logic."""
import pytest

# Import the helper functions from the tax_filing endpoint
from app.api.v1.endpoints.tax_filing import (
    _sum_income, _sum_deductions, _sum_vat, _estimate_tax, _empty_totals,
    _build_entry, INCOME_TYPES, DEDUCTION_TYPES, VAT_TYPES, OTHER_TYPES,
)
from app.models.tax_filing_data import TaxFilingData
from datetime import datetime


class TestCategoryGrouping:
    def test_income_types(self):
        assert "lohnzettel" in INCOME_TYPES
        assert "e1a" in INCOME_TYPES
        assert "e1b" in INCOME_TYPES
        assert "e1kv" in INCOME_TYPES

    def test_deduction_types(self):
        assert "l1" in DEDUCTION_TYPES
        assert "l1k" in DEDUCTION_TYPES
        assert "l1ab" in DEDUCTION_TYPES

    def test_vat_types(self):
        assert "u1" in VAT_TYPES
        assert "u30" in VAT_TYPES

    def test_other_types(self):
        assert "jahresabschluss" in OTHER_TYPES
        assert "svs" in OTHER_TYPES
        assert "grundsteuer" in OTHER_TYPES
        assert "bank_statement" in OTHER_TYPES

    def test_no_overlap(self):
        all_types = INCOME_TYPES | DEDUCTION_TYPES | VAT_TYPES | OTHER_TYPES
        assert len(all_types) == len(INCOME_TYPES) + len(DEDUCTION_TYPES) + len(VAT_TYPES) + len(OTHER_TYPES)


class TestSumIncome:
    def test_empty(self):
        assert _sum_income([]) == 0.0

    def test_lohnzettel(self):
        items = [{"data_type": "lohnzettel", "data": {"kz_245": 42500.0}}]
        assert _sum_income(items) == 42500.0

    def test_e1a_profit(self):
        items = [{"data_type": "e1a", "data": {"gewinn_verlust": 35000.0}}]
        assert _sum_income(items) == 35000.0

    def test_e1a_loss_clamped_to_zero(self):
        items = [{"data_type": "e1a", "data": {"gewinn_verlust": -15000.0}}]
        assert _sum_income(items) == 0.0

    def test_multiple_sources(self):
        items = [
            {"data_type": "lohnzettel", "data": {"kz_245": 42500.0}},
            {"data_type": "e1a", "data": {"gewinn_verlust": 10000.0}},
        ]
        assert _sum_income(items) == 52500.0


class TestSumDeductions:
    def test_empty(self):
        assert _sum_deductions([]) == 0.0

    def test_l1_werbungskosten(self):
        items = [{"data_type": "l1", "data": {"kz_717": 120.0, "kz_724": 300.0}}]
        assert _sum_deductions(items) == 420.0

    def test_l1k_familienbonus(self):
        items = [{"data_type": "l1k", "data": {"familienbonus_total": 2000.0}}]
        assert _sum_deductions(items) == 2000.0


class TestSumVat:
    def test_empty(self):
        assert _sum_vat([]) == 0.0

    def test_u1_zahllast(self):
        items = [{"data_type": "u1", "data": {"zahllast": 5000.0}}]
        assert _sum_vat(items) == 5000.0


class TestEstimateTax:
    def test_zero_income(self):
        assert _estimate_tax(0) == 0

    def test_below_threshold(self):
        assert _estimate_tax(10000) == 0

    def test_first_bracket(self):
        tax = _estimate_tax(15000)
        assert tax > 0
        assert tax < 5000

    def test_higher_income(self):
        tax = _estimate_tax(50000)
        assert tax > 5000

    def test_very_high_income(self):
        tax = _estimate_tax(200000)
        assert tax > 50000


class TestEmptyTotals:
    def test_all_zeros(self):
        totals = _empty_totals()
        assert totals["total_income"] == 0
        assert totals["estimated_tax"] == 0
        assert totals["estimated_refund"] == 0


class TestBuildEntry:
    def test_build_entry(self):
        rec = TaxFilingData(
            id=1, user_id=1, tax_year=2025, data_type="lohnzettel",
            source_document_id=10, data={"kz_245": 42500.0},
            status="confirmed", confirmed_at=datetime(2025, 6, 1),
        )
        entry = _build_entry(rec)
        assert entry["id"] == 1
        assert entry["data_type"] == "lohnzettel"
        assert entry["data"]["kz_245"] == 42500.0
        assert entry["confirmed_at"] is not None
