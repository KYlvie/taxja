"""Tests for E1a Beilage (self-employment income) extractor."""
import pytest
from decimal import Decimal
from app.services.e1a_extractor import E1aExtractor, E1aData


@pytest.fixture
def extractor():
    return E1aExtractor()


class TestE1aBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_e1adata(self, extractor):
        result = extractor.extract("Veranlagung: 2025 Betriebseinnahmen 80.000,00")
        assert isinstance(result, E1aData)


class TestE1aExtraction:
    def test_betriebseinnahmen(self, extractor):
        text = "Veranlagung: 2025\nBetriebseinnahmen                80.000,00"
        result = extractor.extract(text)
        assert result.betriebseinnahmen == Decimal("80000.00")

    def test_gewinn(self, extractor):
        text = "Veranlagung: 2025\nBetriebseinnahmen 80.000,00\nGewinn 25.000,00"
        result = extractor.extract(text)
        assert result.gewinn_verlust == Decimal("25000.00")
        assert result.has_loss is False

    def test_loss_detection(self, extractor):
        text = "Veranlagung: 2025\nBetriebseinnahmen 10.000,00\nVerlust -5.000,00"
        result = extractor.extract(text)
        assert result.gewinn_verlust == Decimal("-5000.00")
        assert result.has_loss is True

    def test_steuernummer(self, extractor):
        text = "Veranlagung: 2025\nSteuernummer: 12-345/6789\nBetriebseinnahmen 80.000,00"
        result = extractor.extract(text)
        assert result.steuernummer == "12-345/6789"

    def test_betriebsausgabenpauschale(self, extractor):
        text = "Veranlagung: 2025\nBetriebsausgabenpauschale 12%\nBetriebseinnahmen 80.000,00"
        result = extractor.extract(text)
        assert result.betriebsausgabenpauschale is True
        assert result.pauschale_prozent == 12

    def test_kz_extraction(self, extractor):
        text = "Veranlagung: 2025\nKZ 9040: 80.000,00\nKZ 9230: 55.000,00"
        result = extractor.extract(text)
        assert result.betriebseinnahmen == Decimal("80000.00")
        assert result.betriebsausgaben_gesamt == Decimal("55000.00")


class TestE1aConfidence:
    def test_high_confidence(self, extractor):
        text = "Veranlagung: 2025\nBetriebseinnahmen 80.000,00\nBetriebsausgaben gesamt 55.000,00\nGewinn 25.000,00\nWareneinkauf 20.000,00\nPersonalaufwand 15.000,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.8


class TestE1aToDict:
    def test_to_dict(self, extractor):
        data = E1aData(tax_year=2025, betriebseinnahmen=Decimal("80000.00"), has_loss=False, confidence=0.8)
        result = extractor.to_dict(data)
        assert result["betriebseinnahmen"] == 80000.0
        assert result["has_loss"] is False
