"""Tests for SVS (social insurance) notice extractor."""
import pytest
from decimal import Decimal
from app.services.svs_extractor import SvsExtractor, SvsData


@pytest.fixture
def extractor():
    return SvsExtractor()


class TestSvsBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_svsdata(self, extractor):
        result = extractor.extract("Beitragsjahr: 2025 Pensionsversicherung 5.000,00")
        assert isinstance(result, SvsData)


class TestSvsExtraction:
    def test_pensionsversicherung(self, extractor):
        text = "Beitragsjahr: 2025\nPensionsversicherung             5.000,00"
        result = extractor.extract(text)
        assert result.pensionsversicherung == Decimal("5000.00")

    def test_krankenversicherung(self, extractor):
        text = "Beitragsjahr: 2025\nKrankenversicherung              2.800,00"
        result = extractor.extract(text)
        assert result.krankenversicherung == Decimal("2800.00")

    def test_unfallversicherung(self, extractor):
        text = "Beitragsjahr: 2025\nUnfallversicherung               130,00"
        result = extractor.extract(text)
        assert result.unfallversicherung == Decimal("130.00")

    def test_beitrag_gesamt(self, extractor):
        text = "Beitragsjahr: 2025\nGesamtbeitrag                    7.930,00"
        result = extractor.extract(text)
        assert result.beitrag_gesamt == Decimal("7930.00")

    def test_beitragsgrundlage(self, extractor):
        text = "Beitragsjahr: 2025\nBeitragsgrundlage                35.000,00"
        result = extractor.extract(text)
        assert result.beitragsgrundlage == Decimal("35000.00")

    def test_versicherungsnummer(self, extractor):
        text = "Beitragsjahr: 2025\nVersicherungsnummer: 1234 010190\nPensionsversicherung 5.000,00"
        result = extractor.extract(text)
        assert result.versicherungsnummer is not None


class TestSvsConfidence:
    def test_high_confidence(self, extractor):
        text = "Beitragsjahr: 2025\nBeitragsgrundlage 35.000,00\nPensionsversicherung 5.000,00\nKrankenversicherung 2.800,00\nUnfallversicherung 130,00\nGesamtbeitrag 7.930,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.8


class TestSvsToDict:
    def test_to_dict(self, extractor):
        data = SvsData(tax_year=2025, beitrag_gesamt=Decimal("7930.00"), confidence=0.7)
        result = extractor.to_dict(data)
        assert result["beitrag_gesamt"] == 7930.0
