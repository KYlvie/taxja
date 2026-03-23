"""Tests for Jahresabschluss (annual financial statement) extractor."""
import pytest
from decimal import Decimal
from app.services.jahresabschluss_extractor import JahresabschlussExtractor, JahresabschlussData


@pytest.fixture
def extractor():
    return JahresabschlussExtractor()


class TestJahresabschlussBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_data(self, extractor):
        result = extractor.extract("Geschäftsjahr: 2025 Betriebseinnahmen 120.000,00")
        assert isinstance(result, JahresabschlussData)


class TestJahresabschlussExtraction:
    def test_einnahmen(self, extractor):
        text = "Geschäftsjahr: 2025\nBetriebseinnahmen                120.000,00"
        result = extractor.extract(text)
        assert result.einnahmen_gesamt == Decimal("120000.00")

    def test_ausgaben(self, extractor):
        text = "Geschäftsjahr: 2025\nBetriebsausgaben                 85.000,00"
        result = extractor.extract(text)
        assert result.ausgaben_gesamt == Decimal("85000.00")

    def test_gewinn(self, extractor):
        text = "Geschäftsjahr: 2025\nBetriebseinnahmen 120.000,00\nGewinn 35.000,00"
        result = extractor.extract(text)
        assert result.gewinn_verlust == Decimal("35000.00")
        assert result.has_loss is False

    def test_loss_detection(self, extractor):
        text = "Geschäftsjahr: 2025\nBetriebseinnahmen 50.000,00\nVerlust -10.000,00"
        result = extractor.extract(text)
        assert result.gewinn_verlust == Decimal("-10000.00")
        assert result.has_loss is True

    def test_afa(self, extractor):
        text = "Geschäftsjahr: 2025\nAbschreibung                     8.000,00"
        result = extractor.extract(text)
        assert result.afa_gesamt == Decimal("8000.00")


class TestJahresabschlussFormat:
    def test_ea_format(self, extractor):
        text = "Geschäftsjahr: 2025\nEinnahmen-Ausgaben-Rechnung\nBetriebseinnahmen 120.000,00"
        result = extractor.extract(text)
        assert result.format_type == "ea"

    def test_bilanz_format(self, extractor):
        text = "Geschäftsjahr: 2025\nBilanz zum 31.12.2025\nBilanzsumme 500.000,00"
        result = extractor.extract(text)
        assert result.format_type == "bilanz"


class TestJahresabschlussExpenseDetail:
    def test_expense_categories(self, extractor):
        text = "Geschäftsjahr: 2025\nBetriebseinnahmen 120.000,00\nWareneinkauf 30.000,00\nPersonalaufwand 25.000,00\nMiete 12.000,00"
        result = extractor.extract(text)
        assert "wareneinkauf" in result.ausgaben_detail
        assert "personalaufwand" in result.ausgaben_detail


class TestJahresabschlussConfidence:
    def test_high_confidence(self, extractor):
        text = "Geschäftsjahr: 2025\nBetriebseinnahmen 120.000,00\nBetriebsausgaben 85.000,00\nGewinn 35.000,00\nWareneinkauf 30.000,00\nPersonalaufwand 25.000,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.7


class TestJahresabschlussToDict:
    def test_to_dict(self, extractor):
        data = JahresabschlussData(tax_year=2025, einnahmen_gesamt=Decimal("120000.00"), confidence=0.8)
        result = extractor.to_dict(data)
        assert result["einnahmen_gesamt"] == 120000.0
