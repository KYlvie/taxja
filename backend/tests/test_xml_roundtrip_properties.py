"""Property-based tests for FinanzOnline XML roundtrip validation"""
import pytest
from hypothesis import given, strategies as st
import xml.etree.ElementTree as ET
from decimal import Decimal

from app.services.finanzonline_xml_generator import FinanzOnlineXMLGenerator


# Strategy for generating valid user data
@st.composite
def user_data_strategy(draw):
    """Generate valid user data for XML generation"""
    return {
        'name': draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_characters='<>&"\'\x00\n\r'))),
        'tax_number': draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Nd', 'Lu')))),
        'address': draw(st.text(min_size=10, max_size=200, alphabet=st.characters(blacklist_characters='<>&"\'\x00\n\r'))),
        'user_type': draw(st.sampled_from(['employee', 'self_employed', 'landlord', 'mixed'])),
        'vat_number': draw(st.one_of(st.none(), st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Nd', 'Lu')))))
    }


# Strategy for generating valid tax data
@st.composite
def tax_data_strategy(draw):
    """Generate valid tax calculation data for XML"""
    # Income summary
    employment = draw(st.decimals(min_value=0, max_value=200000, places=2))
    rental = draw(st.decimals(min_value=0, max_value=100000, places=2))
    self_employment = draw(st.decimals(min_value=0, max_value=150000, places=2))
    capital_gains = draw(st.decimals(min_value=0, max_value=50000, places=2))
    total_income = employment + rental + self_employment + capital_gains
    
    # Expense summary
    deductible = draw(st.decimals(min_value=0, max_value=float(total_income), places=2))
    non_deductible = draw(st.decimals(min_value=0, max_value=50000, places=2))
    total_expenses = deductible + non_deductible
    
    # Deductions
    svs_contributions = draw(st.decimals(min_value=0, max_value=20000, places=2))
    commuting_allowance = draw(st.decimals(min_value=0, max_value=5000, places=2))
    home_office = draw(st.decimals(min_value=0, max_value=300, places=2))
    family_deductions = draw(st.decimals(min_value=0, max_value=2000, places=2))
    total_deductions = svs_contributions + commuting_allowance + home_office + family_deductions
    
    # Tax calculation
    taxable_income = max(Decimal('0'), total_income - total_deductions)
    income_tax = draw(st.decimals(min_value=0, max_value=float(taxable_income) * 0.55, places=2))
    vat = draw(st.decimals(min_value=0, max_value=10000, places=2))
    svs = svs_contributions
    total_tax = income_tax + vat + svs
    net_income = total_income - total_tax
    
    return {
        'income_summary': {
            'employment': float(employment),
            'rental': float(rental),
            'self_employment': float(self_employment),
            'capital_gains': float(capital_gains),
            'total': float(total_income)
        },
        'expense_summary': {
            'deductible': float(deductible),
            'non_deductible': float(non_deductible),
            'total': float(total_expenses)
        },
        'deductions': {
            'svs_contributions': float(svs_contributions),
            'commuting_allowance': float(commuting_allowance),
            'home_office': float(home_office),
            'family_deductions': float(family_deductions),
            'total': float(total_deductions)
        },
        'tax_calculation': {
            'gross_income': float(total_income),
            'deductions': float(total_deductions),
            'taxable_income': float(taxable_income),
            'income_tax': float(income_tax),
            'vat': float(vat),
            'vat_exempt': vat == 0,
            'svs': float(svs),
            'total_tax': float(total_tax),
            'net_income': float(net_income)
        }
    }


class TestXMLRoundtripValidation:
    """
    Property 15: FinanzOnline XML roundtrip validation
    
    **Validates: Requirements 15.1, 15.2, 15.3, 15.4**
    
    For all valid tax report data:
    - Generate XML → Parse XML → Extract data should preserve all information
    - XML must be well-formed and parseable
    - All required sections must be present
    - Data values must be preserved accurately
    """
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_generation_is_well_formed(self, user_data, tax_data, tax_year):
        """
        Property: Generated XML is always well-formed and parseable.
        
        For any valid user and tax data:
        - XML must be parseable without errors
        - XML must have valid structure
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # XML should be parseable
        try:
            root = ET.fromstring(xml_string)
            assert root is not None
        except ET.ParseError as e:
            pytest.fail(f"XML parsing failed: {e}")
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_contains_required_root_element(self, user_data, tax_data, tax_year):
        """
        Property: XML contains required root element with correct attributes.
        
        For any valid data:
        - Root element must be 'Einkommensteuererklärung'
        - Must have 'Jahr' attribute with correct tax year
        - Must have 'Version' attribute
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # Parse XML
        root = ET.fromstring(xml_string)
        
        # Check root element
        assert root.tag == 'Einkommensteuererklärung'
        
        # Check Jahr attribute
        assert root.get('Jahr') == str(tax_year)
        
        # Check Version attribute
        assert root.get('Version') is not None
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_contains_taxpayer_information(self, user_data, tax_data, tax_year):
        """
        Property: XML contains taxpayer information section.
        
        For any valid user data:
        - Must have 'Steuerpflichtiger' section
        - Must contain taxpayer name
        - Must contain tax number (if provided)
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # Parse XML
        root = ET.fromstring(xml_string)
        
        # Find taxpayer section
        taxpayer = root.find('Steuerpflichtiger')
        assert taxpayer is not None, "Steuerpflichtiger section must be present"
        
        # Check name
        name_elem = taxpayer.find('Name')
        if user_data.get('name'):
            assert name_elem is not None
            assert name_elem.text == user_data['name']
        
        # Check tax number
        if user_data.get('tax_number'):
            tax_num_elem = taxpayer.find('Steuernummer')
            assert tax_num_elem is not None
            assert tax_num_elem.text == user_data['tax_number']
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_contains_tax_calculation(self, user_data, tax_data, tax_year):
        """
        Property: XML contains tax calculation section.
        
        For any valid tax data:
        - Must have 'Steuerberechnung' section
        - Must contain income tax amount
        - Must contain total tax amount
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # Parse XML
        root = ET.fromstring(xml_string)
        
        # Find tax calculation section
        tax_calc = root.find('Steuerberechnung')
        assert tax_calc is not None, "Steuerberechnung section must be present"
        
        # Check income tax
        income_tax_elem = tax_calc.find('Einkommensteuer')
        assert income_tax_elem is not None
        
        # Check total tax
        total_tax_elem = tax_calc.find('Gesamtsteuer')
        assert total_tax_elem is not None
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_roundtrip_preserves_numeric_values(self, user_data, tax_data, tax_year):
        """
        Property: XML roundtrip preserves numeric values accurately.
        
        For any valid tax data:
        - Generate XML
        - Parse XML and extract values
        - Values should match original data (within floating point precision)
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # Parse XML
        root = ET.fromstring(xml_string)
        
        # Extract and verify tax calculation values
        tax_calc = root.find('Steuerberechnung')
        if tax_calc is not None:
            # Check income tax
            income_tax_elem = tax_calc.find('Einkommensteuer')
            if income_tax_elem is not None and income_tax_elem.text:
                parsed_income_tax = float(income_tax_elem.text)
                original_income_tax = tax_data['tax_calculation']['income_tax']
                assert abs(parsed_income_tax - original_income_tax) < 0.01
            
            # Check total tax
            total_tax_elem = tax_calc.find('Gesamtsteuer')
            if total_tax_elem is not None and total_tax_elem.text:
                parsed_total_tax = float(total_tax_elem.text)
                original_total_tax = tax_data['tax_calculation']['total_tax']
                assert abs(parsed_total_tax - original_total_tax) < 0.01
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_validation_succeeds_for_well_formed_xml(self, user_data, tax_data, tax_year):
        """
        Property: Validation succeeds for all generated XML.
        
        For any valid data:
        - Generated XML should pass validation
        - No validation errors should occur
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # Validate XML (basic well-formedness check)
        is_valid = generator.validate(xml_string)
        assert is_valid is True
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_contains_income_sections_when_income_exists(self, user_data, tax_data, tax_year):
        """
        Property: XML contains income sections when income > 0.
        
        For any tax data with income:
        - If total income > 0, must have 'Einkünfte' section
        - Appropriate income subsections must be present
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # Parse XML
        root = ET.fromstring(xml_string)
        
        # Check if income exists
        total_income = tax_data['income_summary']['total']
        
        if total_income > 0:
            # Should have Einkünfte section
            income_section = root.find('Einkünfte')
            assert income_section is not None, "Einkünfte section must be present when income > 0"
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_contains_deductions_when_deductions_exist(self, user_data, tax_data, tax_year):
        """
        Property: XML contains deductions section when deductions > 0.
        
        For any tax data with deductions:
        - If total deductions > 0, must have 'Sonderausgaben' section
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # Parse XML
        root = ET.fromstring(xml_string)
        
        # Check if deductions exist
        total_deductions = tax_data['deductions']['total']
        
        if total_deductions > 0:
            # Should have Sonderausgaben section
            deductions_section = root.find('Sonderausgaben')
            assert deductions_section is not None, "Sonderausgaben section must be present when deductions > 0"
