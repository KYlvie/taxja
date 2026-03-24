"""Tests for Grundsteuerbescheid (property tax notice) extractor."""
import pytest
from decimal import Decimal
from app.services.grundsteuer_extractor import GrundsteuerExtractor, GrundsteuerData


@pytest.fixture
def extractor():
    return GrundsteuerExtractor()


class TestGrundsteuerBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_data(self, extractor):
        result = extractor.extract("Vorschreibung: 2025 Grundsteuer 450,00")
        assert isinstance(result, GrundsteuerData)


class TestGrundsteuerExtraction:
    def test_grundsteuer_betrag(self, extractor):
        text = "Vorschreibung: 2025\nGrundsteuer                      450,00"
        result = extractor.extract(text)
        assert result.grundsteuer_betrag == Decimal("450.00")

    def test_einheitswert(self, extractor):
        text = "Vorschreibung: 2025\nEinheitswert                     25.000,00"
        result = extractor.extract(text)
        assert result.einheitswert == Decimal("25000.00")

    def test_steuermessbetrag(self, extractor):
        text = "Vorschreibung: 2025\nSteuermessbetrag                 90,00"
        result = extractor.extract(text)
        assert result.steuermessbetrag == Decimal("90.00")

    def test_hebesatz(self, extractor):
        text = "Vorschreibung: 2025\nHebesatz: 500%\nGrundsteuer 450,00"
        result = extractor.extract(text)
        assert result.hebesatz == 500


class TestGrundsteuerAddress:
    def test_extract_address(self, extractor):
        text = "Vorschreibung: 2025\nLiegenschaft: Hauptstraße 12, 1010 Wien\nGrundsteuer 450,00"
        result = extractor.extract(text)
        assert "Hauptstraße 12" in result.property_address

    def test_extract_postal_code_city(self, extractor):
        text = "Grundsteuerbescheid\nLiegenschaft: 1010 Wien Hauptstraße 12\nGrundsteuer 450,00"
        result = extractor.extract(text)
        assert result.postal_code == "1010"
        assert "Wien" in result.city


class TestGrundsteuerConfidence:
    def test_high_confidence(self, extractor):
        text = "Vorschreibung: 2025\nLiegenschaft: Hauptstraße 12\nGrundsteuer 450,00\nEinheitswert 25.000,00\nSteuermessbetrag 90,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.8


class TestGrundsteuerToDict:
    def test_to_dict(self, extractor):
        data = GrundsteuerData(tax_year=2025, grundsteuer_betrag=Decimal("450.00"), confidence=0.7)
        result = extractor.to_dict(data)
        assert result["grundsteuer_betrag"] == 450.0
