"""Tests for L1 Form (Arbeitnehmerveranlagung) extractor."""
import pytest
from decimal import Decimal
from app.services.l1_form_extractor import L1FormExtractor, L1FormData


@pytest.fixture
def extractor():
    return L1FormExtractor()


class TestL1FormBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_l1formdata(self, extractor):
        result = extractor.extract("Veranlagung: 2025 KZ 717: 120,00")
        assert isinstance(result, L1FormData)


class TestL1FormKZExtraction:
    def test_werbungskosten_fields(self, extractor):
        text = "Veranlagung: 2025\nKZ 717: 120,00\nKZ 719: 350,00\nKZ 722: 1.200,00"
        result = extractor.extract(text)
        assert result.kz_717 == Decimal("120.00")
        assert result.kz_719 == Decimal("350.00")
        assert result.kz_722 == Decimal("1200.00")

    def test_sonderausgaben_fields(self, extractor):
        text = "Veranlagung: 2025\nKZ 458: 400,00\nKZ 459: 200,00"
        result = extractor.extract(text)
        assert result.kz_458 == Decimal("400.00")
        assert result.kz_459 == Decimal("200.00")

    def test_aussergewoehnliche_belastungen(self, extractor):
        text = "Veranlagung: 2025\nKZ 730: 3.500,00\nKZ 740: 1.200,00"
        result = extractor.extract(text)
        assert result.kz_730 == Decimal("3500.00")
        assert result.kz_740 == Decimal("1200.00")


class TestL1FormKeywordContext:
    def test_kirchenbeitrag_keyword(self, extractor):
        text = "Veranlagung: 2025\nKirchenbeitrag                   400,00"
        result = extractor.extract(text)
        assert result.kz_458 == Decimal("400.00")

    def test_spenden_keyword(self, extractor):
        text = "Veranlagung: 2025\nSpenden                          200,00"
        result = extractor.extract(text)
        assert result.kz_459 == Decimal("200.00")


class TestL1FormMetadata:
    def test_extract_tax_year(self, extractor):
        result = extractor.extract("Veranlagung: 2025\nKZ 717: 100,00")
        assert result.tax_year == 2025

    def test_extract_steuernummer(self, extractor):
        result = extractor.extract("Veranlagung: 2025\nSteuernummer: 12-345/6789\nKZ 717: 100,00")
        assert result.steuernummer == "12-345/6789"


class TestL1FormConfidence:
    def test_high_confidence(self, extractor):
        text = "Veranlagung: 2025\nSteuernummer: 12-345/6789\nKZ 717: 120,00\nKZ 719: 350,00\nKZ 722: 1.200,00\nKZ 458: 400,00\nKZ 730: 3.500,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.8

    def test_low_confidence_minimal(self, extractor):
        result = extractor.extract("Veranlagung: 2025\nSome text here")
        assert result.confidence < 0.5


class TestL1FormToDict:
    def test_to_dict(self, extractor):
        data = L1FormData(tax_year=2025, kz_458=Decimal("400.00"), confidence=0.7)
        result = extractor.to_dict(data)
        assert result["kz_458"] == 400.0
        assert result["tax_year"] == 2025
