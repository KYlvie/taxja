"""Tests for L16 Lohnzettel extractor."""
import pytest
from decimal import Decimal
from app.services.l16_extractor import L16Extractor, L16Data


@pytest.fixture
def extractor():
    return L16Extractor()


class TestL16ExtractorBasic:
    def test_empty_text_returns_zero_confidence(self, extractor):
        result = extractor.extract("")
        assert result.confidence == 0.0

    def test_short_text_returns_zero_confidence(self, extractor):
        result = extractor.extract("short")
        assert result.confidence == 0.0

    def test_extract_returns_l16data(self, extractor):
        result = extractor.extract("Lohnzettel Kalenderjahr: 2025 KZ 245: 42.500,00")
        assert isinstance(result, L16Data)


class TestL16KZRegex:
    def test_extract_kz_245(self, extractor):
        text = "Lohnzettel 2025\nKZ 245: 42.500,00\nKZ 260: 8.750,00"
        result = extractor.extract(text)
        assert result.kz_245 == Decimal("42500.00")
        assert result.kz_260 == Decimal("8750.00")

    def test_extract_kz_210_brutto(self, extractor):
        text = "Kalenderjahr: 2025\nKZ 210: 55.000,00\nKZ 230: 9.200,00"
        result = extractor.extract(text)
        assert result.kz_210 == Decimal("55000.00")
        assert result.kz_230 == Decimal("9200.00")

    def test_extract_kz_718_719(self, extractor):
        text = "Lohnzettel 2025\nKZ 718: 696,00\nKZ 719: 58,00\nKZ 245: 30.000,00"
        result = extractor.extract(text)
        assert result.kz_718 == Decimal("696.00")
        assert result.kz_719 == Decimal("58.00")


class TestL16AcroForm:
    def test_extract_acroform_fields(self, extractor):
        text = (
            "--- FORM FIELDS ---\n"
            "Kz245: 42500,00\n"
            "Kz260: 8750,00\n"
            "Kz210: 55000,00\n"
            "---\n"
            "Kalenderjahr: 2025"
        )
        result = extractor.extract(text)
        assert result.kz_245 == Decimal("42500.00")
        assert result.kz_260 == Decimal("8750.00")
        assert result.kz_210 == Decimal("55000.00")


class TestL16KeywordContext:
    def test_extract_by_keyword_brutto(self, extractor):
        text = "Kalenderjahr: 2025\nBruttobezüge                    55.000,00"
        result = extractor.extract(text)
        assert result.kz_210 == Decimal("55000.00")

    def test_extract_by_keyword_lohnsteuer(self, extractor):
        text = "Kalenderjahr: 2025\nEinbehaltene Lohnsteuer          8.750,00"
        result = extractor.extract(text)
        assert result.kz_260 == Decimal("8750.00")


class TestL16Metadata:
    def test_extract_tax_year(self, extractor):
        text = "Kalenderjahr: 2025\nKZ 245: 30.000,00"
        result = extractor.extract(text)
        assert result.tax_year == 2025

    def test_extract_employer_name(self, extractor):
        text = "Kalenderjahr: 2025\nArbeitgeber: Muster GmbH\nKZ 245: 30.000,00"
        result = extractor.extract(text)
        assert result.employer_name == "Muster GmbH"

    def test_extract_sv_nummer(self, extractor):
        text = "Kalenderjahr: 2025\n1234 010190\nKZ 245: 30.000,00"
        result = extractor.extract(text)
        assert result.sv_nummer == "1234 010190"


class TestL16Confidence:
    def test_high_confidence_with_critical_fields(self, extractor):
        text = "Kalenderjahr: 2025\nKZ 245: 42.500,00\nKZ 260: 8.750,00\nKZ 210: 55.000,00\nKZ 230: 9.200,00\nArbeitgeber: Test GmbH"
        result = extractor.extract(text)
        assert result.confidence >= 0.9

    def test_low_confidence_without_key_fields(self, extractor):
        text = "Kalenderjahr: 2025\nSome random text about taxes"
        result = extractor.extract(text)
        assert result.confidence < 0.5


class TestL16ToDict:
    def test_to_dict_converts_decimals(self, extractor):
        data = L16Data(tax_year=2025, kz_245=Decimal("42500.00"), confidence=0.9)
        result = extractor.to_dict(data)
        assert result["kz_245"] == 42500.0
        assert result["tax_year"] == 2025
        assert isinstance(result["kz_245"], float)
