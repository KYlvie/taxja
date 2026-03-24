"""Tests for TaxFilingData model CRUD operations."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.models.tax_filing_data import TaxFilingData


class TestTaxFilingDataModel:
    def test_create_instance(self):
        tfd = TaxFilingData(
            user_id=1,
            tax_year=2025,
            data_type="lohnzettel",
            source_document_id=10,
            data={"kz_245": 42500.0, "kz_260": 8750.0},
            status="pending",
        )
        assert tfd.user_id == 1
        assert tfd.tax_year == 2025
        assert tfd.data_type == "lohnzettel"
        assert tfd.data["kz_245"] == 42500.0
        assert tfd.status == "pending"

    def test_default_status_column(self):
        """Column default is 'pending' — applied by DB, not Python constructor."""
        from sqlalchemy import inspect as sa_inspect
        mapper = sa_inspect(TaxFilingData)
        status_col = mapper.columns["status"]
        assert status_col.default.arg == "pending"

    def test_confirmed_at_nullable(self):
        tfd = TaxFilingData(user_id=1, tax_year=2025, data_type="e1a", data={})
        assert tfd.confirmed_at is None

    def test_confirmed_at_set(self):
        now = datetime.utcnow()
        tfd = TaxFilingData(
            user_id=1, tax_year=2025, data_type="e1a", data={},
            status="confirmed", confirmed_at=now,
        )
        assert tfd.confirmed_at == now
        assert tfd.status == "confirmed"

    def test_repr(self):
        tfd = TaxFilingData(id=5, user_id=1, tax_year=2025, data_type="svs", data={}, status="confirmed")
        r = repr(tfd)
        assert "svs" in r
        assert "2025" in r
        assert "confirmed" in r

    def test_data_json_field(self):
        complex_data = {
            "kz_210": 55000.0,
            "kz_245": 42500.0,
            "employer_name": "Test GmbH",
            "merged_sources": [1, 2],
        }
        tfd = TaxFilingData(user_id=1, tax_year=2025, data_type="lohnzettel", data=complex_data)
        assert tfd.data["merged_sources"] == [1, 2]
        assert tfd.data["employer_name"] == "Test GmbH"

    def test_all_data_types(self):
        """Verify all expected data types can be set."""
        types = [
            "lohnzettel", "l1", "l1k", "l1ab", "e1a", "e1b", "e1kv",
            "u1", "u30", "jahresabschluss", "svs", "grundsteuer", "bank_statement",
        ]
        for dt in types:
            tfd = TaxFilingData(user_id=1, tax_year=2025, data_type=dt, data={})
            assert tfd.data_type == dt

    def test_source_document_id_nullable(self):
        tfd = TaxFilingData(user_id=1, tax_year=2025, data_type="l1", data={})
        assert tfd.source_document_id is None
