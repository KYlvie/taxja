"""
Tests for MietvertragExtractor (Rental Contract Extractor)

Tests extraction of structured data from Austrian rental contracts (Mietverträge).
"""
import pytest
from decimal import Decimal
from datetime import datetime
from backend.app.services.mietvertrag_extractor import MietvertragExtractor, MietvertragData


class TestMietvertragExtractor:
    """Test suite for MietvertragExtractor"""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance"""
        return MietvertragExtractor()
    
    # --- Property address extraction tests ---
    
    def test_extract_property_address_standard_format(self, extractor):
        """Test extraction of property address in standard format"""
        text = """
        MIETVERTRAG
        
        Mietobjekt: Hauptstraße 123, 1010 Wien
        
        Mietzins: EUR 850,00
        """
        
        data = extractor.extract(text)
        
        assert data.property_address == "Hauptstraße 123, 1010 Wien"
        assert data.street == "Hauptstraße 123"
        assert data.city == "Wien"
        assert data.postal_code == "1010"
        assert data.field_confidence["property_address"] >= 0.8
    
    def test_extract_property_address_with_apartment_number(self, extractor):
        """Test extraction of address with apartment number"""
        text = """
        Bestandobjekt: Mariahilfer Straße 45/12, 1060 Wien
        """
        
        data = extractor.extract(text)
        
        assert data.property_address == "Mariahilfer Straße 45/12, 1060 Wien"
        assert data.street == "Mariahilfer Straße 45/12"
        assert data.postal_code == "1060"
        assert data.city == "Wien"
    
    def test_extract_property_address_with_top_number(self, extractor):
        """Test extraction of address with Top number"""
        text = """
        Wohnung: Top 5, Ringstraße 88, 1010 Wien
        """
        
        data = extractor.extract(text)
        
        assert data.property_address is not None
        assert "Ringstraße" in data.property_address
        assert data.postal_code == "1010"
    
    def test_extract_property_address_reversed_format(self, extractor):
        """Test extraction of address in reversed format (postal code first)"""
        text = """
        Objekt: 1030 Wien, Landstraßer Hauptstraße 100
        """
        
        data = extractor.extract(text)
        
        assert data.postal_code == "1030"
        assert data.city == "Wien"
        assert "Landstraßer Hauptstraße" in (data.street or "")
    
    # --- Monthly rent extraction tests ---
    
    def test_extract_monthly_rent_standard_format(self, extractor):
        """Test extraction of monthly rent in standard format"""
        text = """
        Mietzins: EUR 850,00
        """
        
        data = extractor.extract(text)
        
        assert data.monthly_rent == Decimal("850.00")
        assert data.field_confidence["monthly_rent"] >= 0.85
    
    def test_extract_monthly_rent_hauptmietzins(self, extractor):
        """Test extraction of Hauptmietzins"""
        text = """
        Hauptmietzins: € 1.200,50
        """
        
        data = extractor.extract(text)
        
        assert data.monthly_rent == Decimal("1200.50")
    
    def test_extract_monthly_rent_nettomiete(self, extractor):
        """Test extraction of Nettomiete"""
        text = """
        Nettomiete: 950,00 EUR
        """
        
        data = extractor.extract(text)
        
        assert data.monthly_rent == Decimal("950.00")
    
    def test_extract_monthly_rent_with_thousand_separator(self, extractor):
        """Test extraction of rent with thousand separator"""
        text = """
        Monatliche Miete: EUR 2.500,00
        """
        
        data = extractor.extract(text)
        
        assert data.monthly_rent == Decimal("2500.00")
    
    def test_extract_monthly_rent_pro_monat_format(self, extractor):
        """Test extraction of rent in 'pro Monat' format"""
        text = """
        Der Mieter zahlt EUR 750,00 pro Monat.
        """
        
        data = extractor.extract(text)
        
        assert data.monthly_rent == Decimal("750.00")
    
    def test_extract_monthly_rent_sanity_check(self, extractor):
        """Test that unrealistic rent amounts are rejected"""
        text = """
        Mietzins: EUR 50,00
        """
        
        data = extractor.extract(text)
        
        # Should reject rent below 100 EUR
        assert data.monthly_rent is None
    
    # --- Contract dates extraction tests ---
    
    def test_extract_start_date_standard_format(self, extractor):
        """Test extraction of contract start date"""
        text = """
        Mietbeginn: 01.03.2024
        """
        
        data = extractor.extract(text)
        
        assert data.start_date == datetime(2024, 3, 1)
        assert data.field_confidence["start_date"] >= 0.8
    
    def test_extract_start_date_ab_format(self, extractor):
        """Test extraction of start date with 'ab' format"""
        text = """
        Das Mietverhältnis beginnt ab 15.06.2024.
        """
        
        data = extractor.extract(text)
        
        assert data.start_date == datetime(2024, 6, 15)
    
    def test_extract_end_date_befristet(self, extractor):
        """Test extraction of end date for fixed-term contract"""
        text = """
        Mietbeginn: 01.01.2024
        Mietende: 31.12.2026
        """
        
        data = extractor.extract(text)
        
        assert data.start_date == datetime(2024, 1, 1)
        assert data.end_date == datetime(2026, 12, 31)
    
    def test_extract_end_date_bis_format(self, extractor):
        """Test extraction of end date with 'bis' format"""
        text = """
        Vertragsbeginn: 01.04.2024
        Befristet bis: 31.03.2027
        """
        
        data = extractor.extract(text)
        
        assert data.start_date == datetime(2024, 4, 1)
        assert data.end_date == datetime(2027, 3, 31)
    
    def test_no_end_date_for_unlimited_contract(self, extractor):
        """Test that unlimited contracts have no end date"""
        text = """
        Mietbeginn: 01.01.2024
        Unbefristeter Mietvertrag
        """
        
        data = extractor.extract(text)
        
        assert data.start_date == datetime(2024, 1, 1)
        assert data.end_date is None
    
    # --- Additional costs extraction tests ---
    
    def test_extract_betriebskosten(self, extractor):
        """Test extraction of Betriebskosten (operating costs)"""
        text = """
        Mietzins: EUR 800,00
        Betriebskosten: EUR 150,00
        """
        
        data = extractor.extract(text)
        
        assert data.betriebskosten == Decimal("150.00")
        assert data.field_confidence["betriebskosten"] >= 0.8
    
    def test_extract_heating_costs(self, extractor):
        """Test extraction of Heizkosten"""
        text = """
        Heizkosten: EUR 80,00
        """
        
        data = extractor.extract(text)
        
        assert data.heating_costs == Decimal("80.00")
    
    def test_extract_deposit_kaution(self, extractor):
        """Test extraction of Kaution (deposit)"""
        text = """
        Kaution: EUR 2.400,00
        """
        
        data = extractor.extract(text)
        
        assert data.deposit_amount == Decimal("2400.00")
        assert data.field_confidence["deposit_amount"] >= 0.8
    
    def test_extract_deposit_sicherheitsleistung(self, extractor):
        """Test extraction of Sicherheitsleistung (security deposit)"""
        text = """
        Sicherheitsleistung in Höhe von EUR 3.000,00
        """
        
        data = extractor.extract(text)
        
        assert data.deposit_amount == Decimal("3000.00")
    
    # --- Utilities information extraction tests ---
    
    def test_utilities_included_inkludiert(self, extractor):
        """Test detection of utilities included"""
        text = """
        Mietzins: EUR 900,00 inkl. Betriebskosten
        """
        
        data = extractor.extract(text)
        
        assert data.utilities_included is True
        assert data.field_confidence["utilities_included"] >= 0.7
    
    def test_utilities_included_warmmiete(self, extractor):
        """Test detection of Warmmiete (utilities included)"""
        text = """
        Warmmiete: EUR 1.100,00
        """
        
        data = extractor.extract(text)
        
        assert data.utilities_included is True
    
    def test_utilities_excluded_exkludiert(self, extractor):
        """Test detection of utilities excluded"""
        text = """
        Mietzins: EUR 800,00 exkl. Betriebskosten
        """
        
        data = extractor.extract(text)
        
        assert data.utilities_included is False
    
    def test_utilities_excluded_kaltmiete(self, extractor):
        """Test detection of Kaltmiete (utilities excluded)"""
        text = """
        Kaltmiete: EUR 750,00
        Betriebskosten: EUR 120,00
        """
        
        data = extractor.extract(text)
        
        assert data.utilities_included is False
    
    # --- Parties extraction tests ---
    
    def test_extract_tenant_name_standard_format(self, extractor):
        """Test extraction of tenant name"""
        text = """
        Mieter: Max Mustermann, geboren am 15.05.1985
        """
        
        data = extractor.extract(text)
        
        assert data.tenant_name == "Max Mustermann"
        assert data.field_confidence["tenant_name"] >= 0.7
    
    def test_extract_tenant_name_with_title(self, extractor):
        """Test extraction of tenant name with title"""
        text = """
        Mieter: Dr. Anna Schmidt, wohnhaft in Wien
        """
        
        data = extractor.extract(text)
        
        assert data.tenant_name == "Anna Schmidt"
    
    def test_extract_tenant_bestandnehmer(self, extractor):
        """Test extraction of Bestandnehmer (tenant)"""
        text = """
        Bestandnehmer: Johann Huber
        """
        
        data = extractor.extract(text)
        
        assert data.tenant_name == "Johann Huber"
    
    def test_extract_landlord_name_standard_format(self, extractor):
        """Test extraction of landlord name"""
        text = """
        Vermieter: Maria Müller, geboren am 20.03.1970
        """
        
        data = extractor.extract(text)
        
        assert data.landlord_name == "Maria Müller"
        assert data.field_confidence["landlord_name"] >= 0.7
    
    def test_extract_landlord_bestandgeber(self, extractor):
        """Test extraction of Bestandgeber (landlord)"""
        text = """
        Bestandgeber: Peter Wagner
        """
        
        data = extractor.extract(text)
        
        assert data.landlord_name == "Peter Wagner"
    
    def test_extract_both_parties(self, extractor):
        """Test extraction of both tenant and landlord"""
        text = """
        Vermieter: Maria Müller
        Mieter: Max Mustermann
        """
        
        data = extractor.extract(text)
        
        assert data.landlord_name == "Maria Müller"
        assert data.tenant_name == "Max Mustermann"
    
    # --- Contract type extraction tests ---
    
    def test_contract_type_unbefristet_explicit(self, extractor):
        """Test detection of unlimited contract (explicit)"""
        text = """
        Unbefristeter Mietvertrag
        Mietbeginn: 01.01.2024
        """
        
        data = extractor.extract(text)
        
        assert data.contract_type == "Unbefristet"
        assert data.field_confidence["contract_type"] >= 0.8
    
    def test_contract_type_befristet_explicit(self, extractor):
        """Test detection of fixed-term contract (explicit)"""
        text = """
        Befristeter Mietvertrag
        Mietbeginn: 01.01.2024
        Mietende: 31.12.2026
        """
        
        data = extractor.extract(text)
        
        assert data.contract_type == "Befristet"
        assert data.field_confidence["contract_type"] >= 0.8
    
    def test_contract_type_inferred_from_end_date(self, extractor):
        """Test contract type inferred from presence of end date"""
        text = """
        Mietbeginn: 01.01.2024
        Mietende: 31.12.2026
        """
        
        data = extractor.extract(text)
        
        assert data.contract_type == "Befristet"
    
    def test_contract_type_default_unbefristet(self, extractor):
        """Test default contract type is Unbefristet"""
        text = """
        Mietbeginn: 01.01.2024
        Mietzins: EUR 800,00
        """
        
        data = extractor.extract(text)
        
        assert data.contract_type == "Unbefristet"
    
    # --- Complete contract extraction tests ---
    
    def test_extract_complete_rental_contract(self, extractor):
        """Test extraction of a complete rental contract"""
        text = """
        MIETVERTRAG
        
        Vermieter: Maria Müller, geboren am 20.03.1970, wohnhaft in Wien
        Mieter: Max Mustermann, geboren am 15.05.1985, wohnhaft in Graz
        
        Mietobjekt: Hauptstraße 123/5, 1010 Wien
        
        Mietbeginn: 01.03.2024
        Unbefristeter Mietvertrag
        
        Mietzins: EUR 850,00
        Betriebskosten: EUR 150,00
        Heizkosten: EUR 80,00
        
        Kaution: EUR 2.550,00 (3 Monatsmieten)
        
        Die Betriebskosten sind im Mietzins nicht inkludiert.
        """
        
        data = extractor.extract(text)
        
        # Property information
        assert data.property_address == "Hauptstraße 123/5, 1010 Wien"
        assert data.street == "Hauptstraße 123/5"
        assert data.city == "Wien"
        assert data.postal_code == "1010"
        
        # Rental terms
        assert data.monthly_rent == Decimal("850.00")
        assert data.start_date == datetime(2024, 3, 1)
        assert data.end_date is None
        
        # Additional costs
        assert data.betriebskosten == Decimal("150.00")
        assert data.heating_costs == Decimal("80.00")
        assert data.deposit_amount == Decimal("2550.00")
        
        # Utilities
        assert data.utilities_included is False
        
        # Parties
        assert data.tenant_name == "Max Mustermann"
        assert data.landlord_name == "Maria Müller"
        
        # Contract type
        assert data.contract_type == "Unbefristet"
        
        # Overall confidence should be high
        assert data.confidence >= 0.7
    
    def test_extract_befristeter_contract(self, extractor):
        """Test extraction of a fixed-term rental contract"""
        text = """
        BEFRISTETER MIETVERTRAG
        
        Vermieter: Peter Wagner
        Mieter: Anna Schmidt
        
        Wohnung: Mariahilfer Straße 88/12, 1060 Wien
        
        Vertragsbeginn: 01.06.2024
        Vertragsende: 31.05.2027
        
        Nettomiete: EUR 1.200,00
        Betriebskosten inkludiert
        
        Barkaution: EUR 3.600,00
        """
        
        data = extractor.extract(text)
        
        assert data.property_address is not None
        assert "Mariahilfer Straße" in data.property_address
        assert data.monthly_rent == Decimal("1200.00")
        assert data.start_date == datetime(2024, 6, 1)
        assert data.end_date == datetime(2027, 5, 31)
        assert data.utilities_included is True
        assert data.deposit_amount == Decimal("3600.00")
        assert data.contract_type == "Befristet"
    
    # --- Edge cases and error handling ---
    
    def test_extract_from_empty_text(self, extractor):
        """Test extraction from empty text"""
        data = extractor.extract("")
        
        assert data.property_address is None
        assert data.monthly_rent is None
        assert data.confidence == 0.0
    
    def test_extract_with_minimal_information(self, extractor):
        """Test extraction with minimal information"""
        text = """
        Mietobjekt: Teststraße 1, 1010 Wien
        Mietzins: EUR 500,00
        """
        
        data = extractor.extract(text)
        
        assert data.property_address is not None
        assert data.monthly_rent == Decimal("500.00")
        assert data.confidence > 0.0
    
    def test_to_dict_conversion(self, extractor):
        """Test conversion of MietvertragData to dictionary"""
        text = """
        Mietobjekt: Hauptstraße 123, 1010 Wien
        Mietzins: EUR 850,00
        Mietbeginn: 01.03.2024
        """
        
        data = extractor.extract(text)
        result = extractor.to_dict(data)
        
        assert isinstance(result, dict)
        assert result["property_address"] == "Hauptstraße 123, 1010 Wien"
        assert result["monthly_rent"] == 850.00
        assert result["start_date"] == "2024-03-01T00:00:00"
        assert "field_confidence" in result
        assert "confidence" in result
    
    # --- Confidence scoring tests ---
    
    def test_high_confidence_with_all_critical_fields(self, extractor):
        """Test high confidence when all critical fields are present"""
        text = """
        Mietobjekt: Hauptstraße 123, 1010 Wien
        Mietzins: EUR 850,00
        Mietbeginn: 01.03.2024
        Mieter: Max Mustermann
        Vermieter: Maria Müller
        Kaution: EUR 2.550,00
        """
        
        data = extractor.extract(text)
        
        assert data.confidence >= 0.75
    
    def test_medium_confidence_with_some_fields(self, extractor):
        """Test medium confidence with some fields missing"""
        text = """
        Mietobjekt: Hauptstraße 123, 1010 Wien
        Mietzins: EUR 850,00
        """
        
        data = extractor.extract(text)
        
        assert 0.4 <= data.confidence < 0.75
    
    def test_low_confidence_with_minimal_fields(self, extractor):
        """Test low confidence with minimal fields"""
        text = """
        Mietzins: EUR 850,00
        """
        
        data = extractor.extract(text)
        
        assert data.confidence < 0.5
