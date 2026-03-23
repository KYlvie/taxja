"""Tests for E1kv Beilage (capital gains supplement) extractor."""
import pytest
from decimal import Decimal
from app.services.e1kv_extractor import E1kvExtractor, E1kvData


@pytest.fixture
def extractor():
    return E1kvExtractor()


class TestE1kvBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_e1kvdata(self, extractor):
        result = extractor.extract("Veranlagung: 2025 Aktien 5.000,00")
        assert isinstance(result, E1kvData)


class TestE1kvExtraction:
    def test_aktien_gewinne(self, extractor):
        text = "Veranlagung: 2025\nAktien                           5.000,00"
        result = extractor.extract(text)
        assert result.aktien_gewinne == Decimal("5000.00")

    def test_krypto_gewinne(self, extractor):
        text = "Veranlagung: 2025\nKryptowährung                    3.200,00"
        result = extractor.extract(text)
        assert result.krypto_gewinne == Decimal("3200.00")

    def test_dividenden(self, extractor):
        text = "Veranlagung: 2025\nDividenden                       1.500,00"
        result = extractor.extract(text)
        assert result.dividenden == Decimal("1500.00")

    def test_kest_einbehalten(self, extractor):
        text = "Veranlagung: 2025\nKapitalertragsteuer              1.375,00"
        result = extractor.extract(text)
        assert result.kest_einbehalten == Decimal("1375.00")

    def test_kz_981(self, extractor):
        text = "Veranlagung: 2025\nKZ 981: 5.000,00\nKZ 994: 1.375,00"
        result = extractor.extract(text)
        assert result.aktien_gewinne == Decimal("5000.00")
        assert result.kest_einbehalten == Decimal("1375.00")

    def test_zinsen(self, extractor):
        text = "Veranlagung: 2025\nZinserträge                      800,00"
        result = extractor.extract(text)
        assert result.zinsen == Decimal("800.00")


class TestE1kvConfidence:
    def test_high_confidence(self, extractor):
        text = "Veranlagung: 2025\nAktien 5.000,00\nDividenden 1.500,00\nKapitalertragsteuer 1.375,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.7


class TestE1kvToDict:
    def test_to_dict(self, extractor):
        data = E1kvData(tax_year=2025, aktien_gewinne=Decimal("5000.00"), confidence=0.7)
        result = extractor.to_dict(data)
        assert result["aktien_gewinne"] == 5000.0
