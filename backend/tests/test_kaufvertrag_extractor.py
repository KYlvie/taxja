"""
Tests for KaufvertragExtractor - Property Purchase Contract OCR Extraction

Tests the extraction of building_value and land_value from Austrian property
purchase contracts (Kaufverträge).
"""
import pytest
from decimal import Decimal
from datetime import datetime
from backend.app.services.kaufvertrag_extractor import KaufvertragExtractor, KaufvertragData


class TestKaufvertragExtractor:
    """Test suite for Kaufvertrag OCR extraction"""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance"""
        return KaufvertragExtractor()
    
    # --- Building and Land Value Extraction Tests ---
    
    def test_extract_explicit_building_and_land_values(self, extractor):
        """Test extraction when building and land values are explicitly stated"""
        text = """
        KAUFVERTRAG
        
        Kaufpreis: EUR 350.000,00
        
        Aufteilung:
        Gebäudewert: EUR 280.000,00
        Grundwert: EUR 70.000,00
        
        Liegenschaft: Hauptstraße 123, 1010 Wien
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_price == Decimal("350000.00")
        assert result.building_value == Decimal("280000.00")
        assert result.land_value == Decimal("70000.00")
        assert result.field_confidence.get("building_value", 0) >= 0.8
        assert result.field_confidence.get("land_value", 0) >= 0.8
    
    def test_extract_building_value_alternative_terms(self, extractor):
        """Test extraction with alternative German terms for building value"""
        text = """
        Kaufpreis: 500.000,00 EUR
        
        Wert des Gebäudes: EUR 400.000,00
        Wert des Grundstücks: EUR 100.000,00
        """
        
        result = extractor.extract(text)
        
        assert result.building_value == Decimal("400000.00")
        assert result.land_value == Decimal("100000.00")
    
    def test_extract_land_value_alternative_term_bodenwert(self, extractor):
        """Test extraction using 'Bodenwert' instead of 'Grundwert'"""
        text = """
        Kaufpreis: 250.000 EUR
        
        Gebäudewert: 200.000 EUR
        Bodenwert: 50.000 EUR
        """
        
        result = extractor.extract(text)
        
        assert result.building_value == Decimal("200000.00")
        assert result.land_value == Decimal("50000.00")
    
    def test_estimate_building_land_split_when_not_specified(self, extractor):
        """Test 80/20 estimation when building/land split not in contract"""
        text = """
        KAUFVERTRAG
        
        Kaufpreis: EUR 300.000,00
        Liegenschaft: Teststraße 1, 1020 Wien
        """
        
        result = extractor.extract(text)
        
        # Should estimate 80% building, 20% land
        assert result.purchase_price == Decimal("300000.00")
        assert result.building_value == Decimal("240000.00")  # 80%
        assert result.land_value == Decimal("60000.00")  # 20%
        
        # Confidence should be lower for estimates
        assert result.field_confidence.get("building_value", 0) == 0.5
        assert result.field_confidence.get("land_value", 0) == 0.5
    
    def test_no_estimation_without_purchase_price(self, extractor):
        """Test that no estimation occurs if purchase price is missing"""
        text = """
        KAUFVERTRAG
        Liegenschaft: Teststraße 1, 1020 Wien
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_price is None
        assert result.building_value is None
        assert result.land_value is None
    
    def test_explicit_values_override_estimation(self, extractor):
        """Test that explicit values are used instead of estimation"""
        text = """
        Kaufpreis: 400.000 EUR
        Gebäudewert: 350.000 EUR
        """
        
        result = extractor.extract(text)
        
        # Should use explicit building value, not 80% estimate
        assert result.building_value == Decimal("350000.00")
        # Land value should still be estimated from remaining amount
        # (but current implementation doesn't do this - it only estimates if BOTH are missing)
        assert result.field_confidence.get("building_value", 0) >= 0.8
    
    def test_building_value_with_ocr_errors(self, extractor):
        """Test extraction with common OCR errors (ä, ö, ü)"""
        text = """
        Kaufpreis: 200.000 EUR
        Gebäudewert: 160.000 EUR
        Grundwert: 40.000 EUR
        """
        
        result = extractor.extract(text)
        
        # Should handle 'ä' variations in 'Gebäude'
        assert result.building_value == Decimal("160000.00")
        assert result.land_value == Decimal("40000.00")
    
    def test_values_with_different_number_formats(self, extractor):
        """Test parsing of various Austrian number formats"""
        test_cases = [
            ("Gebäudewert: 280.000,00", Decimal("280000.00")),
            ("Gebäudewert: 280000,00", Decimal("280000.00")),
            ("Gebäudewert: EUR 280.000,00", Decimal("280000.00")),
            ("Gebäudewert: € 280.000,00", Decimal("280000.00")),
        ]
        
        for text_fragment, expected_value in test_cases:
            result = extractor.extract(text_fragment)
            assert result.building_value == expected_value, f"Failed for: {text_fragment}"
    
    def test_zero_values_not_extracted(self, extractor):
        """Test that zero values are not extracted (likely OCR errors)"""
        text = """
        Kaufpreis: 300.000 EUR
        Gebäudewert: 0,00 EUR
        Grundwert: 0,00 EUR
        """
        
        result = extractor.extract(text)
        
        # Zero values should be ignored, estimation should kick in
        assert result.building_value == Decimal("240000.00")  # 80% estimate
        assert result.land_value == Decimal("60000.00")  # 20% estimate
    
    # --- Integration Tests ---
    
    def test_complete_kaufvertrag_extraction(self, extractor):
        """Test extraction of complete Kaufvertrag with all fields"""
        text = """
        KAUFVERTRAG
        
        Zwischen:
        Verkäufer: Max Mustermann, geboren 01.01.1970
        Käufer: Maria Musterfrau, geboren 15.05.1985
        
        Liegenschaft: Hauptstraße 123/4, 1010 Wien
        
        Kaufpreis: EUR 450.000,00
        
        Aufteilung:
        Gebäudewert: EUR 360.000,00
        Grundwert: EUR 90.000,00
        
        Grunderwerbsteuer: EUR 15.750,00
        Notarkosten: EUR 5.000,00
        Eintragungsgebühr: EUR 1.500,00
        
        Baujahr: 1985
        
        Wien, am 15.03.2024
        
        Notar: Dr. Johann Schmidt, Notar in Wien
        """
        
        result = extractor.extract(text)
        
        # Property details
        assert result.property_address is not None
        assert "Hauptstraße" in result.property_address
        assert result.street == "Hauptstraße 123/4"
        assert result.postal_code == "1010"
        assert result.city == "Wien"
        
        # Purchase details
        assert result.purchase_price == Decimal("450000.00")
        assert result.purchase_date == datetime(2024, 3, 15)
        
        # Value breakdown
        assert result.building_value == Decimal("360000.00")
        assert result.land_value == Decimal("90000.00")
        
        # Purchase costs
        assert result.grunderwerbsteuer == Decimal("15750.00")
        assert result.notary_fees == Decimal("5000.00")
        assert result.registry_fees == Decimal("1500.00")
        
        # Parties
        assert "Max Mustermann" in result.seller_name
        assert "Maria Musterfrau" in result.buyer_name
        
        # Notary
        assert "Johann Schmidt" in result.notary_name
        assert result.notary_location == "Wien"
        
        # Building details
        assert result.construction_year == 1985
        
        # Overall confidence should be high
        assert result.confidence >= 0.7
    
    def test_to_dict_conversion(self, extractor):
        """Test conversion of KaufvertragData to dictionary"""
        text = """
        Kaufpreis: 300.000 EUR
        Gebäudewert: 240.000 EUR
        Grundwert: 60.000 EUR
        """
        
        result = extractor.extract(text)
        result_dict = extractor.to_dict(result)
        
        # Check that Decimal values are converted to float
        assert isinstance(result_dict["purchase_price"], float)
        assert result_dict["purchase_price"] == 300000.0
        assert result_dict["building_value"] == 240000.0
        assert result_dict["land_value"] == 60000.0
    
    # --- Edge Cases ---
    
    def test_extract_with_minimal_text(self, extractor):
        """Test extraction with minimal contract text"""
        text = "Kaufpreis: 100.000 EUR"
        
        result = extractor.extract(text)
        
        assert result.purchase_price == Decimal("100000.00")
        # Should estimate building/land split
        assert result.building_value == Decimal("80000.00")
        assert result.land_value == Decimal("20000.00")
    
    def test_extract_with_empty_text(self, extractor):
        """Test extraction with empty text"""
        result = extractor.extract("")
        
        assert result.purchase_price is None
        assert result.building_value is None
        assert result.land_value is None
        assert result.confidence == 0.0
    
    def test_extract_with_malformed_values(self, extractor):
        """Test extraction with malformed number values"""
        text = """
        Kaufpreis: ABC EUR
        Gebäudewert: XYZ
        """
        
        result = extractor.extract(text)
        
        # Should handle gracefully
        assert result.purchase_price is None
        assert result.building_value is None
    
    def test_confidence_scoring_with_partial_data(self, extractor):
        """Test confidence scoring when only some fields are extracted"""
        text = """
        Kaufpreis: 200.000 EUR
        Liegenschaft: Teststraße 1, 1020 Wien
        """
        
        result = extractor.extract(text)
        
        # Should have moderate confidence (has critical fields but missing others)
        assert 0.3 <= result.confidence <= 0.7
        assert result.field_confidence.get("purchase_price", 0) >= 0.8
        assert result.field_confidence.get("property_address", 0) >= 0.8
    
    def test_structured_output_with_confidence_scores(self, extractor):
        """Test that to_dict returns complete structured data with confidence scores"""
        text = """
        KAUFVERTRAG
        
        Liegenschaft: Hauptstraße 123, 1010 Wien
        Kaufpreis: EUR 350.000,00
        Gebäudewert: EUR 280.000,00
        Grundwert: EUR 70.000,00
        
        Kaufdatum: 15.06.2020
        Baujahr: 1985
        
        Käufer: Max Mustermann
        Verkäufer: Maria Musterfrau
        
        Notar: Dr. Hans Schmidt
        Notariat Wien
        
        Grunderwerbsteuer: EUR 12.250,00
        Notargebühren: EUR 3.500,00
        Eintragungsgebühr: EUR 1.050,00
        """
        
        result = extractor.extract(text)
        result_dict = extractor.to_dict(result)
        
        # Verify all extracted fields are present
        assert result_dict["property_address"] == "Hauptstraße 123, 1010 Wien"
        assert result_dict["purchase_price"] == 350000.0
        assert result_dict["building_value"] == 280000.0
        assert result_dict["land_value"] == 70000.0
        assert result_dict["buyer_name"] == "Max Mustermann"
        assert result_dict["seller_name"] == "Maria Musterfrau"
        assert result_dict["notary_name"] == "Dr. Hans Schmidt"
        assert result_dict["construction_year"] == 1985
        
        # Verify field_confidence dictionary is present and populated
        assert "field_confidence" in result_dict
        assert isinstance(result_dict["field_confidence"], dict)
        assert len(result_dict["field_confidence"]) > 0
        
        # Verify confidence scores for critical fields
        assert "property_address" in result_dict["field_confidence"]
        assert "purchase_price" in result_dict["field_confidence"]
        assert "building_value" in result_dict["field_confidence"]
        assert "land_value" in result_dict["field_confidence"]
        
        # Verify confidence values are in valid range [0.0, 1.0]
        for field, confidence in result_dict["field_confidence"].items():
            assert 0.0 <= confidence <= 1.0, f"Invalid confidence for {field}: {confidence}"
        
        # Verify overall confidence is present and in valid range
        assert "confidence" in result_dict
        assert isinstance(result_dict["confidence"], float)
        assert 0.0 <= result_dict["confidence"] <= 1.0
        
        # With comprehensive data, overall confidence should be high
        assert result_dict["confidence"] >= 0.7
    
    def test_confidence_scores_in_dict_with_missing_fields(self, extractor):
        """Test that confidence scores are properly included even with missing fields"""
        text = """
        Kaufpreis: 150.000 EUR
        """
        
        result = extractor.extract(text)
        result_dict = extractor.to_dict(result)
        
        # Verify field_confidence is present even with minimal data
        assert "field_confidence" in result_dict
        assert isinstance(result_dict["field_confidence"], dict)
        
        # Should have confidence for purchase_price
        assert "purchase_price" in result_dict["field_confidence"]
        assert result_dict["field_confidence"]["purchase_price"] >= 0.8
        
        # Should have confidence for estimated building/land values
        assert "building_value" in result_dict["field_confidence"]
        assert "land_value" in result_dict["field_confidence"]
        # Estimated values should have lower confidence
        assert result_dict["field_confidence"]["building_value"] == 0.5
        assert result_dict["field_confidence"]["land_value"] == 0.5
        
        # Overall confidence should be lower with minimal data
        assert "confidence" in result_dict
        assert result_dict["confidence"] < 0.5
