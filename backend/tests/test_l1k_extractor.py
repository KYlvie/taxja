"""Tests for L1k Beilage (child supplement) extractor."""
import pytest
from decimal import Decimal
from app.services.l1k_extractor import L1kExtractor, L1kData


@pytest.fixture
def extractor():
    return L1kExtractor()


class TestL1kBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_l1kdata(self, extractor):
        result = extractor.extract("Veranlagung: 2025 Familienbonus 2.000,00")
        assert isinstance(result, L1kData)


class TestL1kChildExtraction:
    def test_extract_child_info(self, extractor):
        text = "Veranlagung: 2025\nKind: Max Mustermann\nGeburtsdatum: 15.03.2018\nFamilienbonus 2.000,00"
        result = extractor.extract(text)
        assert len(result.children) >= 1
        assert result.children[0].name == "Max Mustermann"

    def test_extract_familienbonus_total(self, extractor):
        text = "Veranlagung: 2025\nFamilienbonus                    2.000,00"
        result = extractor.extract(text)
        assert result.total_familienbonus == Decimal("2000.00")

    def test_extract_kindermehrbetrag(self, extractor):
        text = "Veranlagung: 2025\nKindermehrbetrag                 550,00"
        result = extractor.extract(text)
        assert result.total_kindermehrbetrag == Decimal("550.00")


class TestL1kConfidence:
    def test_high_confidence(self, extractor):
        text = "Veranlagung: 2025\nKind: Max Mustermann\nGeburtsdatum: 15.03.2018\nFamilienbonus 2.000,00\nKindermehrbetrag 550,00"
        result = extractor.extract(text)
        assert result.confidence >= 0.7

    def test_low_confidence_no_children(self, extractor):
        result = extractor.extract("Veranlagung: 2025\nSome text")
        assert result.confidence < 0.5


class TestL1kToDict:
    def test_to_dict(self, extractor):
        data = L1kData(tax_year=2025, total_familienbonus=Decimal("2000.00"), confidence=0.7)
        result = extractor.to_dict(data)
        assert result["total_familienbonus"] == 2000.0
