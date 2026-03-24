"""Tests for VAT form extractor (U1 annual + U30 advance)."""
import pytest
from decimal import Decimal
from app.services.vat_form_extractor import VatFormExtractor, VatFormData


@pytest.fixture
def extractor():
    return VatFormExtractor()


class TestVatFormBasic:
    def test_empty_text_u1(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_empty_text_u30(self, extractor):
        assert extractor.extract_u30("").confidence == 0.0

    def test_u1_form_type(self, extractor):
        result = extractor.extract("Jahr: 2025 Gesamtumsatz 100.000,00")
        assert result.form_type == "u1"

    def test_u30_form_type(self, extractor):
        result = extractor.extract_u30("Zeitraum: Q1 2025 Gesamtumsatz 25.000,00")
        assert result.form_type == "u30"


class TestU1Extraction:
    def test_umsatz_20(self, extractor):
        text = "Jahr: 2025\n20% Umsatz                       80.000,00"
        result = extractor.extract(text)
        assert result.umsatz_20 == Decimal("80000.00")

    def test_umsatz_10(self, extractor):
        text = "Jahr: 2025\n10% Umsatz                       20.000,00"
        result = extractor.extract(text)
        assert result.umsatz_10 == Decimal("20000.00")

    def test_vorsteuer(self, extractor):
        text = "Jahr: 2025\nVorsteuer                        15.000,00"
        result = extractor.extract(text)
        assert result.vorsteuer == Decimal("15000.00")

    def test_zahllast(self, extractor):
        text = "Jahr: 2025\nZahllast                         5.000,00"
        result = extractor.extract(text)
        assert result.zahllast == Decimal("5000.00")

    def test_kz_extraction(self, extractor):
        text = "Jahr: 2025\nKZ 022: 80.000,00\nKZ 060: 15.000,00\nKZ 095: 5.000,00"
        result = extractor.extract(text)
        assert result.umsatz_20 == Decimal("80000.00")
        assert result.vorsteuer == Decimal("15000.00")
        assert result.zahllast == Decimal("5000.00")

    def test_period_u1(self, extractor):
        text = "Jahr: 2025\nGesamtumsatz 100.000,00"
        result = extractor.extract(text)
        assert result.period == "2025"


class TestU30Extraction:
    def test_u30_period(self, extractor):
        text = "Zeitraum: Q1 2025\nGesamtumsatz 25.000,00"
        result = extractor.extract_u30(text)
        assert result.period is not None

    def test_u30_amounts(self, extractor):
        text = "Jahr: 2025\nZeitraum: Jänner 2025\nKZ 022: 25.000,00\nKZ 060: 4.000,00\nKZ 095: 1.000,00"
        result = extractor.extract_u30(text)
        assert result.umsatz_20 == Decimal("25000.00")
        assert result.vorsteuer == Decimal("4000.00")
        assert result.zahllast == Decimal("1000.00")


class TestVatFormConfidence:
    def test_high_confidence(self, extractor):
        text = "Jahr: 2025\n20% Umsatz 80.000,00\nGesamtumsatz 100.000,00\nVorsteuer 15.000,00\nZahllast 5.000,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.7


class TestVatFormToDict:
    def test_to_dict(self, extractor):
        data = VatFormData(form_type="u1", tax_year=2025, umsatz_20=Decimal("80000.00"), confidence=0.7)
        result = extractor.to_dict(data)
        assert result["umsatz_20"] == 80000.0
        assert result["form_type"] == "u1"
