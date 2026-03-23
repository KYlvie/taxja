"""Tests for E1b Beilage (rental income supplement) extractor."""
import pytest
from decimal import Decimal
from app.services.e1b_extractor import E1bExtractor, E1bData


@pytest.fixture
def extractor():
    return E1bExtractor()


class TestE1bBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_e1bdata(self, extractor):
        result = extractor.extract("Veranlagung: 2025 KZ 9460: 12.000,00")
        assert isinstance(result, E1bData)


class TestE1bSingleProperty:
    def test_extract_rental_income(self, extractor):
        text = "Veranlagung: 2025\nKZ 9460: 12.000,00\nKZ 9500: 3.000,00"
        result = extractor.extract(text)
        assert len(result.properties) == 1
        assert result.properties[0].einnahmen == Decimal("12000.00")
        assert result.properties[0].afa == Decimal("3000.00")

    def test_extract_address(self, extractor):
        text = "Veranlagung: 2025\nAdresse: Hauptstraße 12, 1010 Wien\nKZ 9460: 12.000,00"
        result = extractor.extract(text)
        assert len(result.properties) >= 1
        assert "Hauptstraße 12" in result.properties[0].address

    def test_extract_all_kz_fields(self, extractor):
        text = (
            "Veranlagung: 2025\n"
            "KZ 9460: 12.000,00\n"
            "KZ 9500: 3.000,00\n"
            "KZ 9510: 2.500,00\n"
            "KZ 9520: 1.200,00\n"
            "KZ 9530: 800,00\n"
            "KZ 9414: 4.500,00"
        )
        result = extractor.extract(text)
        prop = result.properties[0]
        assert prop.einnahmen == Decimal("12000.00")
        assert prop.afa == Decimal("3000.00")
        assert prop.fremdfinanzierung == Decimal("2500.00")
        assert prop.instandhaltung == Decimal("1200.00")
        assert prop.uebrige_werbungskosten == Decimal("800.00")
        assert prop.einkuenfte == Decimal("4500.00")


class TestE1bMultiProperty:
    def test_extract_multiple_properties(self, extractor):
        text = (
            "Veranlagung: 2025\n"
            "Objekt 1:\nAdresse: Hauptstraße 12\nKZ 9460: 12.000,00\n"
            "Objekt 2:\nAdresse: Nebenstraße 5\nKZ 9460: 8.000,00"
        )
        result = extractor.extract(text)
        assert len(result.properties) == 2


class TestE1bKeywordFallback:
    def test_mieteinnahmen_keyword(self, extractor):
        text = "Veranlagung: 2025\nMieteinnahmen                    12.000,00"
        result = extractor.extract(text)
        assert len(result.properties) >= 1
        assert result.properties[0].einnahmen == Decimal("12000.00")


class TestE1bMetadata:
    def test_tax_year(self, extractor):
        text = "Veranlagung: 2025\nKZ 9460: 12.000,00"
        result = extractor.extract(text)
        assert result.tax_year == 2025

    def test_steuernummer(self, extractor):
        text = "Veranlagung: 2025\nSteuernummer: 12-345/6789\nKZ 9460: 12.000,00"
        result = extractor.extract(text)
        assert result.steuernummer == "12-345/6789"


class TestE1bConfidence:
    def test_high_confidence(self, extractor):
        text = "Veranlagung: 2025\nAdresse: Hauptstraße 12\nKZ 9460: 12.000,00\nKZ 9414: 4.500,00\nGesamtbetrag 4.500,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.6


class TestE1bToDict:
    def test_to_dict_properties(self, extractor):
        text = "Veranlagung: 2025\nKZ 9460: 12.000,00"
        data = extractor.extract(text)
        result = extractor.to_dict(data)
        assert "properties" in result
        assert isinstance(result["properties"], list)
        if result["properties"]:
            assert isinstance(result["properties"][0]["einnahmen"], (float, type(None)))
