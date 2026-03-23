"""Tests for L1ab Beilage (deductions supplement) extractor."""
import pytest
from decimal import Decimal
from app.services.l1ab_extractor import L1abExtractor, L1abData


@pytest.fixture
def extractor():
    return L1abExtractor()


class TestL1abBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_l1abdata(self, extractor):
        result = extractor.extract("Veranlagung: 2025 Alleinverdiener ja")
        assert isinstance(result, L1abData)


class TestL1abDeductions:
    def test_alleinverdiener_detected(self, extractor):
        text = "Veranlagung: 2025\nAlleinverdiener: ja\nSonstige Angaben"
        result = extractor.extract(text)
        assert result.alleinverdiener is True

    def test_alleinerzieher_detected(self, extractor):
        text = "Veranlagung: 2025\nAlleinerzieher: ja"
        result = extractor.extract(text)
        assert result.alleinerzieher is True

    def test_alleinverdiener_nein(self, extractor):
        text = "Veranlagung: 2025\nAlleinverdiener nein"
        result = extractor.extract(text)
        assert result.alleinverdiener is False

    def test_pendlerpauschale_amount(self, extractor):
        text = "Veranlagung: 2025\nPendlerpauschale                 696,00"
        result = extractor.extract(text)
        assert result.pendlerpauschale_betrag == Decimal("696.00")

    def test_pendlereuro(self, extractor):
        text = "Veranlagung: 2025\nPendlereuro                      58,00"
        result = extractor.extract(text)
        assert result.pendlereuro == Decimal("58.00")

    def test_kz_718_regex(self, extractor):
        text = "Veranlagung: 2025\nKZ 718: 696,00\nKZ 719: 58,00"
        result = extractor.extract(text)
        assert result.pendlerpauschale_betrag == Decimal("696.00")
        assert result.pendlereuro == Decimal("58.00")


class TestL1abConfidence:
    def test_high_confidence(self, extractor):
        text = "Veranlagung: 2025\nAlleinverdiener: ja\nPendlerpauschale 696,00\nPendlereuro 58,00\nUnterhaltsabsetzbetrag 350,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.7


class TestL1abToDict:
    def test_to_dict(self, extractor):
        data = L1abData(tax_year=2025, pendlerpauschale_betrag=Decimal("696.00"), confidence=0.6)
        result = extractor.to_dict(data)
        assert result["pendlerpauschale_betrag"] == 696.0
