"""
Tests for KaufvertragExtractor - Various Format Variations

Tests the extractor's ability to handle different Austrian Kaufvertrag formats
including regional variations, notary-specific templates, and OCR edge cases.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from backend.app.services.kaufvertrag_extractor import KaufvertragExtractor


class TestKaufvertragFormatVariations:
    """Test suite for various Kaufvertrag format variations"""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance"""
        return KaufvertragExtractor()
    
    # --- Address Format Variations ---
    
    def test_address_with_top_number(self, extractor):
        """Test address with Top (apartment) number"""
        text = """
        KAUFVERTRAG
        
        Liegenschaft: Hauptstraße 123 Top 5, 1010 Wien
        Kaufpreis: EUR 250.000,00
        """
        
        result = extractor.extract(text)
        
        assert result.property_address is not None
        assert "Hauptstraße 123 Top 5" in result.property_address
        assert result.street == "Hauptstraße 123 Top 5"
        assert result.postal_code == "1010"
        assert result.city == "Wien"
    
    def test_address_with_range(self, extractor):
        """Test address with number range (e.g., 123-125)"""
        text = """
        Liegenschaft: Mariahilfer Straße 123-125, 1060 Wien
        Kaufpreis: 500.000 EUR
        """
        
        result = extractor.extract(text)
        
        assert result.street == "Mariahilfer Straße 123-125"
        assert result.postal_code == "1060"
        assert result.city == "Wien"
    
    def test_address_reversed_format(self, extractor):
        """Test reversed address format: postal code first"""
        text = """
        Liegenschaft: 1020 Wien, Praterstraße 45
        Kaufpreis: 300.000,00 EUR
        """
        
        result = extractor.extract(text)
        
        assert result.postal_code == "1020"
        assert result.city == "Wien"
        assert result.street == "Praterstraße 45"
    
    def test_address_with_land_registry_format(self, extractor):
        """Test Austrian land registry format (EZ, GB, KG)"""
        text = """
        KAUFVERTRAG
        
        EZ 123 GB 12345 KG Innere Stadt
        Liegenschaft gelegen in 1010 Wien, Stephansplatz 1
        
        Kaufpreis: EUR 1.000.000,00
        """
        
        result = extractor.extract(text)
        
        # Should extract city from land registry or address
        assert result.city is not None
        assert "Wien" in result.city or "Innere Stadt" in result.property_address
    
    def test_address_im_hause_format(self, extractor):
        """Test 'im Hause' address format"""
        text = """
        Objekt im Hause Kärntner Ring 12, 1010 Wien
        Kaufpreis: 450.000 EUR
        """
        
        result = extractor.extract(text)
        
        assert result.property_address is not None
        assert "Kärntner Ring" in result.property_address
    
    # --- Purchase Price Format Variations ---
    
    def test_purchase_price_with_betraegt(self, extractor):
        """Test 'Kaufpreis beträgt' format"""
        text = """
        Der Kaufpreis beträgt: EUR 350.000,00
        Liegenschaft: Teststraße 1, 1010 Wien
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_price == Decimal("350000.00")
    
    def test_purchase_price_with_von(self, extractor):
        """Test 'Kaufpreis von' format"""
        text = """
        Kaufpreis von EUR 275.500,00
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_price == Decimal("275500.00")
    
    def test_purchase_price_in_hoehe_von(self, extractor):
        """Test 'in Höhe von' format"""
        text = """
        Kaufpreis in Höhe von EUR 425.000,00
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_price == Decimal("425000.00")
    
    def test_verkaufspreis_alternative_term(self, extractor):
        """Test 'Verkaufspreis' instead of 'Kaufpreis'"""
        text = """
        Verkaufspreis: EUR 380.000,00
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_price == Decimal("380000.00")
    
    # --- Date Format Variations ---
    
    def test_date_with_vom(self, extractor):
        """Test 'vom' date format"""
        text = """
        KAUFVERTRAG vom 15.06.2023
        
        Kaufpreis: 200.000 EUR
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_date == datetime(2023, 6, 15)
    
    def test_date_with_geschlossen_am(self, extractor):
        """Test 'geschlossen am' format"""
        text = """
        Vertrag geschlossen am 20.03.2024
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_date == datetime(2024, 3, 20)
    
    def test_date_with_various_austrian_cities(self, extractor):
        """Test date extraction with different Austrian cities"""
        cities_and_dates = [
            ("Graz, am 10.05.2023", datetime(2023, 5, 10)),
            ("Linz, 15.07.2023", datetime(2023, 7, 15)),
            ("Salzburg, am 20.08.2023", datetime(2023, 8, 20)),
            ("Innsbruck, 25.09.2023", datetime(2023, 9, 25)),
        ]
        
        for text_fragment, expected_date in cities_and_dates:
            result = extractor.extract(text_fragment)
            assert result.purchase_date == expected_date, f"Failed for: {text_fragment}"
    
    # --- Buyer/Seller Name Variations ---
    
    def test_buyer_as_uebernehmer(self, extractor):
        """Test 'Übernehmer' instead of 'Käufer'"""
        text = """
        Übernehmer: Hans Müller, geboren 01.01.1980
        Verkäufer: Maria Schmidt
        """
        
        result = extractor.extract(text)
        
        assert "Hans Müller" in result.buyer_name
    
    def test_seller_as_uebergeber(self, extractor):
        """Test 'Übergeber' instead of 'Verkäufer'"""
        text = """
        Käufer: Anna Weber
        Übergeber: Josef Huber, geboren 15.05.1960
        """
        
        result = extractor.extract(text)
        
        assert "Josef Huber" in result.seller_name
    
    def test_buyer_als_kaeufer_format(self, extractor):
        """Test 'Name als Käufer' format"""
        text = """
        Max Mustermann als Käufer
        Maria Musterfrau als Verkäufer
        """
        
        result = extractor.extract(text)
        
        assert "Max Mustermann" in result.buyer_name
        assert "Maria Musterfrau" in result.seller_name
    
    def test_nachstehend_genannt_format(self, extractor):
        """Test 'nachstehend Käufer genannt' format"""
        text = """
        Peter Schmidt, nachstehend Käufer genannt
        Anna Huber, nachstehend Verkäufer genannt
        """
        
        result = extractor.extract(text)
        
        assert "Peter Schmidt" in result.buyer_name
        assert "Anna Huber" in result.seller_name

    def test_vehicle_contract_dual_company_header_extracts_parties(self, extractor):
        """Compact vehicle-contract headers should still extract seller and buyer companies."""
        text = """
        KAUFVERTRAG KFZ - ELEKTROFAHRZEUG
        Osterreichische Vertragsstruktur - rekonstruiert fur Testzwecke
        Verkaufer kaufer

        AUTOHAUS DONAUCITY GMBH, Wien ZH TECH SOLUTIONS E.U.

        Kaufpreis brutto

        EUR 38.000,00
        """

        result = extractor.extract(text)

        assert result.seller_name == "AUTOHAUS DONAUCITY GMBH"
        assert result.buyer_name == "ZH TECH SOLUTIONS E.U."
        assert result.purchase_price == Decimal("38000.00")

    def test_vehicle_contract_price_after_standalone_brutto_line(self, extractor):
        """Vehicle contracts sometimes split the 'brutto' header from the price line."""
        text = """
        KAUFVERTRAG KFZ - PKW
        Osterreichische Vertragsstruktur - rekonstruiert fur Testzwecke
        Verkaufer kaufer
        AUTOHAUS DONAUCITY GMBH, Wien ZH TECH SOLUTIONS E.U.
        brutto
        EUR 35.000,00
        """

        result = extractor.extract(text)

        assert result.purchase_price == Decimal("35000.00")
        assert result.seller_name == "AUTOHAUS DONAUCITY GMBH"
        assert result.buyer_name == "ZH TECH SOLUTIONS E.U."
    
    # --- Regional Notary Variations ---
    
    def test_vienna_notary_format(self, extractor):
        """Test Vienna notary format"""
        text = """
        KAUFVERTRAG
        
        Liegenschaft: Ringstraße 1, 1010 Wien
        Kaufpreis: EUR 800.000,00
        
        Wien, am 15.03.2024
        
        Dr. Johann Schmidt
        Notar in Wien
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_date == datetime(2024, 3, 15)
        assert "Johann Schmidt" in result.notary_name
        assert result.notary_location == "Wien"
    
    def test_graz_notary_format(self, extractor):
        """Test Graz notary format"""
        text = """
        Kaufpreis: 350.000 EUR
        
        Graz, 20.06.2023
        
        Mag. Maria Huber, Notarin in Graz
        """
        
        result = extractor.extract(text)
        
        assert result.purchase_date == datetime(2023, 6, 20)
        assert "Maria Huber" in result.notary_name
    
    # --- OCR Error Handling ---
    
    def test_ocr_error_umlauts_in_gebaude(self, extractor):
        """Test OCR errors with umlauts (ä, ö, ü)"""
        variations = [
            "Gebäudewert: 200.000 EUR",
            "Gebaudewert: 200.000 EUR",  # Missing umlaut
            "Gebaüdewert: 200.000 EUR",  # Wrong umlaut
        ]
        
        for text in variations:
            result = extractor.extract(text)
            # Should handle variations due to regex pattern .{1,2}
            assert result.building_value == Decimal("200000.00"), f"Failed for: {text}"
    
    def test_ocr_error_extra_spaces(self, extractor):
        """Test handling of extra spaces from OCR"""
        text = """
        Kaufpreis :   EUR   350.000 , 00
        Gebäudewert :   280.000 , 00
        """
        
        result = extractor.extract(text)
        
        # _parse_amount should handle extra spaces
        assert result.purchase_price == Decimal("350000.00")
        assert result.building_value == Decimal("280000.00")
    
    def test_ocr_error_missing_decimal_separator(self, extractor):
        """Test handling of missing decimal separator"""
        text = """
        Kaufpreis: EUR 350000
        """
        
        result = extractor.extract(text)
        
        # Should still parse as whole number
        assert result.purchase_price == Decimal("350000.00")
    
    # --- Complex Real-World Scenarios ---
    
    def test_complete_contract_vienna_format(self, extractor):
        """Test complete Vienna-style contract"""
        text = """
        KAUFVERTRAG
        
        Zwischen:
        
        Frau Maria Musterfrau, geboren am 15.05.1985, wohnhaft in 1020 Wien,
        nachstehend Käuferin genannt,
        
        und
        
        Herrn Max Mustermann, geboren am 01.01.1970, wohnhaft in 1010 Wien,
        nachstehend Verkäufer genannt,
        
        wird folgender Kaufvertrag geschlossen:
        
        § 1 Kaufgegenstand
        
        Gegenstand des Kaufes ist die Eigentumswohnung Top 12 im Hause
        Hauptstraße 123, 1010 Wien, EZ 456 GB 12345 KG Innere Stadt.
        
        § 2 Kaufpreis
        
        Der Kaufpreis beträgt EUR 450.000,00 (in Worten: vierhundertfünfzigtausend Euro).
        
        Aufteilung:
        Gebäudewert: EUR 360.000,00
        Bodenwert: EUR 90.000,00
        
        § 3 Nebenkosten
        
        Grunderwerbsteuer: EUR 15.750,00
        Notarkosten: EUR 5.000,00
        Eintragungsgebühr: EUR 1.500,00
        
        § 4 Bauangaben
        
        Baujahr: 1985
        Wohnfläche: 85 m²
        
        Wien, am 15.03.2024
        
        Dr. Johann Schmidt
        Notar in 1010 Wien
        """
        
        result = extractor.extract(text)
        
        # Property details
        assert result.property_address is not None
        assert "Hauptstraße 123" in result.property_address or result.street == "Hauptstraße 123"
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
        assert "Maria Musterfrau" in result.buyer_name
        assert "Max Mustermann" in result.seller_name
        
        # Notary
        assert "Johann Schmidt" in result.notary_name
        assert result.notary_location == "Wien"
        
        # Building details
        assert result.construction_year == 1985
        assert result.property_type == "Wohnung"
        
        # High confidence
        assert result.confidence >= 0.75
    
    def test_complete_contract_graz_format(self, extractor):
        """Test complete Graz-style contract with different formatting"""
        text = """
        K A U F V E R T R A G
        
        Verkäufer: Herr Josef Huber, geb. 10.10.1965
        Käufer: Frau Anna Weber, geb. 20.08.1990
        
        Kaufobjekt: Einfamilienhaus
        Adresse: Mozartgasse 45, 8010 Graz
        
        Verkaufspreis: EUR 520.000,00
        
        Wert des Gebäudes: EUR 416.000,00
        Wert des Grundstücks: EUR 104.000,00
        
        Errichtungsjahr: 1978
        
        Graz, 25.09.2023
        
        Mag. Maria Huber
        Notarin in Graz
        """
        
        result = extractor.extract(text)
        
        # Should handle different formatting
        assert result.purchase_price == Decimal("520000.00")
        assert result.building_value == Decimal("416000.00")
        assert result.land_value == Decimal("104000.00")
        assert result.construction_year == 1978
        assert result.property_type == "Haus"
        assert "Josef Huber" in result.seller_name
        assert "Anna Weber" in result.buyer_name
        assert result.purchase_date == datetime(2023, 9, 25)
    
    def test_minimal_contract_with_estimation(self, extractor):
        """Test minimal contract that triggers 80/20 estimation"""
        text = """
        Kaufvertrag vom 10.05.2024
        
        Objekt: Wohnung in 1030 Wien, Landstraße 78
        Preis: EUR 300.000,00
        
        Käufer: Peter Schmidt
        Verkäufer: Anna Müller
        """
        
        result = extractor.extract(text)
        
        # Should extract basic info
        assert result.purchase_price == Decimal("300000.00")
        assert result.purchase_date == datetime(2024, 5, 10)
        assert "Peter Schmidt" in result.buyer_name
        assert "Anna Müller" in result.seller_name
        
        # Should estimate building/land split
        assert result.building_value == Decimal("240000.00")  # 80%
        assert result.land_value == Decimal("60000.00")  # 20%
        assert result.field_confidence["building_value"] == 0.5  # Lower confidence for estimate
    
    # --- Edge Cases ---
    
    def test_multiple_properties_in_contract(self, extractor):
        """Test contract with multiple properties (should extract first)"""
        text = """
        Kaufvertrag
        
        Objekt 1: Hauptstraße 10, 1010 Wien
        Kaufpreis: EUR 200.000,00
        
        Objekt 2: Nebenstraße 5, 1020 Wien
        Kaufpreis: EUR 150.000,00
        
        Gesamtkaufpreis: EUR 350.000,00
        """
        
        result = extractor.extract(text)
        
        # Should extract Gesamtkaufpreis (total)
        assert result.purchase_price == Decimal("350000.00")
        # Should extract first address
        assert result.property_address is not None
    
    def test_contract_with_mixed_currency_symbols(self, extractor):
        """Test contract with both EUR and € symbols"""
        text = """
        Kaufpreis: € 300.000,00
        Gebäudewert: EUR 240.000,00
        Grunderwerbsteuer: € 10.500,00
        """
        
        result = extractor.extract(text)
        
        # Should handle both symbols
        assert result.purchase_price == Decimal("300000.00")
        assert result.building_value == Decimal("240000.00")
        assert result.grunderwerbsteuer == Decimal("10500.00")
    
    def test_confidence_scoring_with_complete_data(self, extractor):
        """Test that confidence is high with complete, well-formatted data"""
        text = """
        KAUFVERTRAG
        
        Liegenschaft: Teststraße 1, 1010 Wien
        Kaufpreis: EUR 400.000,00
        Gebäudewert: EUR 320.000,00
        Grundwert: EUR 80.000,00
        
        Datum: 15.06.2024
        Baujahr: 1990
        
        Käufer: Max Mustermann
        Verkäufer: Maria Musterfrau
        
        Notar: Dr. Hans Schmidt
        """
        
        result = extractor.extract(text)
        
        # With complete data, confidence should be high
        assert result.confidence >= 0.75
        
        # Individual field confidences should also be high
        assert result.field_confidence.get("purchase_price", 0) >= 0.85
        assert result.field_confidence.get("property_address", 0) >= 0.80
        assert result.field_confidence.get("building_value", 0) >= 0.80

