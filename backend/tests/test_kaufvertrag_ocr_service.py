"""
Tests for KaufvertragOCRService

Tests the integration of OCR engine with Kaufvertrag extractor.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, patch

from app.services.kaufvertrag_ocr_service import (
    KaufvertragOCRService,
    KaufvertragOCRResult,
)
from app.services.kaufvertrag_extractor import KaufvertragData


# Sample Kaufvertrag text for testing
SAMPLE_KAUFVERTRAG_TEXT = """
KAUFVERTRAG

zwischen

Herr Max Mustermann, geboren am 15.03.1980, wohnhaft in Wien
nachstehend Käufer genannt

und

Frau Anna Schmidt, geboren am 22.07.1975, wohnhaft in Graz
nachstehend Verkäuferin genannt

wird folgender Kaufvertrag geschlossen:

§ 1 Kaufgegenstand

Liegenschaft: Hauptstraße 123, 1010 Wien
EZ 456 GB 12345 KG Innere Stadt

Baujahr: 1985
Wohnung im 3. Stock

§ 2 Kaufpreis

Der Kaufpreis beträgt EUR 350.000,00 (in Worten: dreihundertfünfzigtausend Euro).

Davon entfallen auf:
- Gebäudewert: EUR 280.000,00
- Grundwert: EUR 70.000,00

§ 3 Nebenkosten

Grunderwerbsteuer: EUR 12.250,00
Notarkosten: EUR 3.500,00
Eintragungsgebühr: EUR 1.050,00

§ 4 Übergabe

Die Übergabe erfolgt am 01.07.2024.

Wien, am 15.06.2024

Dr. Johann Weber
Notar in Wien
"""


class TestKaufvertragOCRService:
    """Test suite for KaufvertragOCRService"""

    def test_initialization(self):
        """Test service initialization"""
        service = KaufvertragOCRService()
        assert service.ocr_engine is not None
        assert service.extractor is not None

    def test_process_kaufvertrag_from_text(self):
        """Test processing Kaufvertrag from pre-extracted text"""
        service = KaufvertragOCRService()
        result = service.process_kaufvertrag_from_text(SAMPLE_KAUFVERTRAG_TEXT)

        # Check result structure
        assert isinstance(result, KaufvertragOCRResult)
        assert result.raw_text == SAMPLE_KAUFVERTRAG_TEXT
        assert result.ocr_confidence == 1.0  # Perfect since pre-extracted
        assert result.extraction_confidence > 0.0
        assert result.overall_confidence > 0.0

        # Check extracted data
        data = result.kaufvertrag_data
        assert data.property_address is not None
        assert "Hauptstraße 123" in data.property_address
        assert data.purchase_price == Decimal("350000.00")
        assert data.purchase_date == datetime(2024, 6, 15)
        assert data.building_value == Decimal("280000.00")
        assert data.land_value == Decimal("70000.00")
        assert data.buyer_name == "Max Mustermann"
        assert data.seller_name == "Anna Schmidt"
        assert "Johann Weber" in data.notary_name  # May include title like "Dr."
        assert data.notary_location == "Wien"
        assert data.construction_year == 1985

    def test_process_kaufvertrag_with_mock_ocr(self):
        """Test processing Kaufvertrag with mocked OCR engine"""
        service = KaufvertragOCRService()

        # Mock OCR result
        mock_ocr_result = Mock()
        mock_ocr_result.raw_text = SAMPLE_KAUFVERTRAG_TEXT
        mock_ocr_result.confidence_score = 0.85

        with patch.object(service.ocr_engine, "process_document", return_value=mock_ocr_result):
            result = service.process_kaufvertrag(b"fake_pdf_bytes")

            # Check result
            assert isinstance(result, KaufvertragOCRResult)
            assert result.ocr_confidence == 0.85
            assert result.extraction_confidence > 0.0
            assert result.overall_confidence > 0.0

            # Check extracted data
            data = result.kaufvertrag_data
            assert data.purchase_price == Decimal("350000.00")
            assert data.buyer_name == "Max Mustermann"

    def test_process_kaufvertrag_insufficient_text(self):
        """Test processing fails with insufficient OCR text"""
        service = KaufvertragOCRService()

        # Mock OCR result with very short text
        mock_ocr_result = Mock()
        mock_ocr_result.raw_text = "short"
        mock_ocr_result.confidence_score = 0.5

        with patch.object(service.ocr_engine, "process_document", return_value=mock_ocr_result):
            with pytest.raises(ValueError, match="insufficient text"):
                service.process_kaufvertrag(b"fake_pdf_bytes")

    def test_calculate_overall_confidence_all_fields(self):
        """Test confidence calculation with all fields present"""
        service = KaufvertragOCRService()

        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("350000.00"),
            purchase_date=datetime(2024, 6, 15),
            buyer_name="Max Mustermann",
            seller_name="Anna Schmidt",
            building_value=Decimal("280000.00"),
            notary_name="Dr. Weber",
        )

        confidence = service._calculate_overall_confidence(0.9, 0.85, data)

        # Should be high confidence with all fields
        assert confidence >= 0.8
        assert confidence <= 1.0

    def test_calculate_overall_confidence_missing_critical(self):
        """Test confidence calculation with missing critical fields"""
        service = KaufvertragOCRService()

        data = KaufvertragData(
            # Missing property_address, purchase_price, purchase_date
            buyer_name="Max Mustermann",
            seller_name="Anna Schmidt",
        )

        confidence = service._calculate_overall_confidence(0.9, 0.5, data)

        # Should have lower confidence due to missing critical fields
        assert confidence < 0.6

    def test_calculate_overall_confidence_with_bonus_fields(self):
        """Test confidence calculation with bonus fields"""
        service = KaufvertragOCRService()

        # Data with critical fields + bonus fields
        data_with_bonus = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("350000.00"),
            purchase_date=datetime(2024, 6, 15),
            buyer_name="Max Mustermann",
            seller_name="Anna Schmidt",
            building_value=Decimal("280000.00"),
            notary_name="Dr. Weber",
        )

        # Data with only critical fields
        data_without_bonus = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("350000.00"),
            purchase_date=datetime(2024, 6, 15),
        )

        confidence_with = service._calculate_overall_confidence(0.8, 0.8, data_with_bonus)
        confidence_without = service._calculate_overall_confidence(0.8, 0.8, data_without_bonus)

        # Bonus fields should increase confidence
        assert confidence_with > confidence_without

    def test_validate_extraction_ready(self):
        """Test validation with complete, high-confidence extraction"""
        service = KaufvertragOCRService()

        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("350000.00"),
            purchase_date=datetime(2024, 6, 15),
            buyer_name="Max Mustermann",
            seller_name="Anna Schmidt",
        )

        result = KaufvertragOCRResult(
            kaufvertrag_data=data,
            raw_text=SAMPLE_KAUFVERTRAG_TEXT,
            ocr_confidence=0.9,
            extraction_confidence=0.85,
            overall_confidence=0.87,
        )

        validation = service.validate_extraction(result)

        assert validation["status"] == "ready"
        assert len(validation["issues"]) == 0
        assert validation["critical_fields_present"]["property_address"] is True
        assert validation["critical_fields_present"]["purchase_price"] is True
        assert validation["critical_fields_present"]["purchase_date"] is True

    def test_validate_extraction_requires_manual_entry(self):
        """Test validation with missing critical fields"""
        service = KaufvertragOCRService()

        data = KaufvertragData(
            # Missing critical fields
            buyer_name="Max Mustermann",
        )

        result = KaufvertragOCRResult(
            kaufvertrag_data=data,
            raw_text="incomplete text",
            ocr_confidence=0.5,
            extraction_confidence=0.3,
            overall_confidence=0.38,
        )

        validation = service.validate_extraction(result)

        assert validation["status"] == "requires_manual_entry"
        assert len(validation["issues"]) == 3  # Missing address, price, date
        assert "Missing property address" in validation["issues"]
        assert "Missing purchase price" in validation["issues"]
        assert "Missing purchase date" in validation["issues"]
        assert validation["critical_fields_present"]["property_address"] is False

    def test_validate_extraction_requires_review(self):
        """Test validation with low confidence"""
        service = KaufvertragOCRService()

        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("350000.00"),
            purchase_date=datetime(2024, 6, 15),
        )

        result = KaufvertragOCRResult(
            kaufvertrag_data=data,
            raw_text=SAMPLE_KAUFVERTRAG_TEXT,
            ocr_confidence=0.55,  # Low OCR confidence
            extraction_confidence=0.65,
            overall_confidence=0.61,
        )

        validation = service.validate_extraction(result)

        assert validation["status"] == "requires_review"
        assert len(validation["issues"]) == 0  # All critical fields present
        assert len(validation["warnings"]) > 0
        assert any("Low OCR quality" in w for w in validation["warnings"])

    def test_validate_extraction_building_value_exceeds_price(self):
        """Test validation detects building value > purchase price"""
        service = KaufvertragOCRService()

        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("350000.00"),  # Exceeds purchase price!
            purchase_date=datetime(2024, 6, 15),
        )

        result = KaufvertragOCRResult(
            kaufvertrag_data=data,
            raw_text=SAMPLE_KAUFVERTRAG_TEXT,
            ocr_confidence=0.8,
            extraction_confidence=0.75,
            overall_confidence=0.77,
        )

        validation = service.validate_extraction(result)

        assert validation["status"] == "requires_review"
        assert any("exceeds purchase price" in w for w in validation["warnings"])

    def test_validate_extraction_value_mismatch(self):
        """Test validation detects building + land != purchase price"""
        service = KaufvertragOCRService()

        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("350000.00"),
            building_value=Decimal("200000.00"),
            land_value=Decimal("100000.00"),  # Total = 300k, not 350k
            purchase_date=datetime(2024, 6, 15),
        )

        result = KaufvertragOCRResult(
            kaufvertrag_data=data,
            raw_text=SAMPLE_KAUFVERTRAG_TEXT,
            ocr_confidence=0.8,
            extraction_confidence=0.75,
            overall_confidence=0.77,
        )

        validation = service.validate_extraction(result)

        assert validation["status"] == "requires_review"
        assert any("does not match purchase price" in w for w in validation["warnings"])

    def test_validate_extraction_future_date(self):
        """Test validation detects future purchase date"""
        service = KaufvertragOCRService()

        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("350000.00"),
            purchase_date=datetime(2030, 1, 1),  # Future date
        )

        result = KaufvertragOCRResult(
            kaufvertrag_data=data,
            raw_text=SAMPLE_KAUFVERTRAG_TEXT,
            ocr_confidence=0.8,
            extraction_confidence=0.75,
            overall_confidence=0.77,
        )

        validation = service.validate_extraction(result)

        assert validation["status"] == "requires_review"
        assert any("in the future" in w for w in validation["warnings"])

    def test_to_dict(self):
        """Test conversion to dictionary"""
        service = KaufvertragOCRService()
        result = service.process_kaufvertrag_from_text(SAMPLE_KAUFVERTRAG_TEXT)

        result_dict = result.to_dict()

        # Check structure
        assert "extracted_data" in result_dict
        assert "raw_text" in result_dict
        assert "ocr_confidence" in result_dict
        assert "extraction_confidence" in result_dict
        assert "overall_confidence" in result_dict
        assert "confidence_breakdown" in result_dict

        # Check data types
        assert isinstance(result_dict["ocr_confidence"], float)
        assert isinstance(result_dict["extraction_confidence"], float)
        assert isinstance(result_dict["overall_confidence"], float)

        # Check extracted data
        extracted = result_dict["extracted_data"]
        assert extracted["purchase_price"] == 350000.00
        assert extracted["buyer_name"] == "Max Mustermann"

    def test_process_kaufvertrag_ocr_failure(self):
        """Test handling of OCR engine failure"""
        service = KaufvertragOCRService()

        with patch.object(service.ocr_engine, "process_document", side_effect=Exception("OCR failed")):
            with pytest.raises(ValueError, match="Failed to process Kaufvertrag"):
                service.process_kaufvertrag(b"fake_pdf_bytes")

    def test_process_kaufvertrag_from_text_extraction_failure(self):
        """Test handling of extraction failure"""
        service = KaufvertragOCRService()

        with patch.object(service.extractor, "extract", side_effect=Exception("Extraction failed")):
            with pytest.raises(ValueError, match="Failed to process Kaufvertrag text"):
                service.process_kaufvertrag_from_text("some text")

    def test_minimal_kaufvertrag(self):
        """Test processing minimal Kaufvertrag with only critical fields"""
        minimal_text = """
        KAUFVERTRAG
        
        Liegenschaft: Teststraße 1, 1010 Wien
        Kaufpreis: EUR 200.000,00
        
        Wien, am 01.01.2024
        """

        service = KaufvertragOCRService()
        result = service.process_kaufvertrag_from_text(minimal_text)

        # Should extract critical fields
        data = result.kaufvertrag_data
        assert data.property_address is not None
        assert data.purchase_price == Decimal("200000.00")
        assert data.purchase_date == datetime(2024, 1, 1)

        # Confidence should be lower due to missing optional fields
        assert result.overall_confidence <= 0.85  # Adjusted threshold

    def test_recommendations_for_low_confidence(self):
        """Test that recommendations are provided for low confidence"""
        service = KaufvertragOCRService()

        data = KaufvertragData(
            property_address="Hauptstraße 123, 1010 Wien",
            purchase_price=Decimal("350000.00"),
            purchase_date=datetime(2024, 6, 15),
        )

        result = KaufvertragOCRResult(
            kaufvertrag_data=data,
            raw_text="poor quality text",
            ocr_confidence=0.4,  # Very low OCR confidence
            extraction_confidence=0.6,
            overall_confidence=0.52,
        )

        validation = service.validate_extraction(result)

        assert len(validation["recommendations"]) > 0
        assert any("rescanning" in r.lower() for r in validation["recommendations"])


# Integration test with real extractor
class TestKaufvertragOCRServiceIntegration:
    """Integration tests with real KaufvertragExtractor"""

    def test_full_extraction_pipeline(self):
        """Test complete extraction pipeline from text to validated result"""
        service = KaufvertragOCRService()

        # Process text
        result = service.process_kaufvertrag_from_text(SAMPLE_KAUFVERTRAG_TEXT)

        # Validate
        validation = service.validate_extraction(result)

        # Check that extraction worked
        assert result.kaufvertrag_data.purchase_price == Decimal("350000.00")
        assert result.kaufvertrag_data.buyer_name == "Max Mustermann"
        assert result.kaufvertrag_data.seller_name == "Anna Schmidt"

        # Check validation
        assert validation["status"] in ["ready", "requires_review"]
        assert validation["critical_fields_present"]["property_address"] is True
        assert validation["critical_fields_present"]["purchase_price"] is True
        assert validation["critical_fields_present"]["purchase_date"] is True

    def test_confidence_scores_are_reasonable(self):
        """Test that confidence scores are in reasonable ranges"""
        service = KaufvertragOCRService()
        result = service.process_kaufvertrag_from_text(SAMPLE_KAUFVERTRAG_TEXT)

        # All confidence scores should be between 0 and 1
        assert 0.0 <= result.ocr_confidence <= 1.0
        assert 0.0 <= result.extraction_confidence <= 1.0
        assert 0.0 <= result.overall_confidence <= 1.0

        # With complete sample text, confidence should be reasonably high
        assert result.overall_confidence >= 0.7
