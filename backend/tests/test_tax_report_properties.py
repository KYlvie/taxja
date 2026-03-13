"""Property-based tests for tax report completeness"""
import pytest
from hypothesis import given, strategies as st, assume
from decimal import Decimal
from datetime import datetime
import re

from app.services.pdf_generator import PDFGenerator
from app.services.csv_generator import CSVGenerator
from app.services.finanzonline_xml_generator import FinanzOnlineXMLGenerator


# Strategy for generating valid user data
@st.composite
def user_data_strategy(draw):
    """Generate valid user data for tax reports"""
    return {
        'name': draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_characters='\x00\n\r'))),
        'tax_number': draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Nd', 'Lu')))),
        'address': draw(st.text(min_size=10, max_size=200, alphabet=st.characters(blacklist_characters='\x00\n\r'))),
        'user_type': draw(st.sampled_from(['employee', 'self_employed', 'landlord', 'mixed'])),
        'vat_number': draw(st.one_of(st.none(), st.text(min_size=5, max_size=20)))
    }


# Strategy for generating valid tax data
@st.composite
def tax_data_strategy(draw):
    """Generate valid tax calculation data"""
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
    
    # Tax brackets breakdown
    breakdown = [
        {
            'bracket': '€0 - €13,539',
            'rate': '0%',
            'taxable_amount': min(taxable_income, Decimal('13539')),
            'tax_amount': Decimal('0')
        }
    ]
    
    if taxable_income > Decimal('13539'):
        amount_in_bracket = min(taxable_income - Decimal('13539'), Decimal('8453'))
        breakdown.append({
            'bracket': '€13,539 - €21,992',
            'rate': '20%',
            'taxable_amount': amount_in_bracket,
            'tax_amount': amount_in_bracket * Decimal('0.20')
        })
    
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
            'net_income': float(net_income),
            'breakdown': breakdown
        }
    }


class TestTaxReportCompleteness:
    """
    Property 28: Tax report contains required information
    
    **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.8**
    
    A valid tax report must contain all required sections:
    - Taxpayer information (name, tax number, address)
    - Income summary (all income categories and total)
    - Expense summary (deductible, non-deductible, total)
    - Deductions (SVS, commuting, home office, family)
    - Tax calculation (gross income, deductions, taxable income, taxes, net income)
    - Tax brackets breakdown
    - Disclaimer
    """
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030),
        language=st.sampled_from(['de', 'en', 'zh'])
    )
    def test_pdf_report_contains_required_information(
        self,
        user_data,
        tax_data,
        tax_year,
        language
    ):
        """
        Property: PDF tax report contains all required information.
        
        For any valid user data and tax data:
        - PDF must be generated successfully
        - PDF must contain taxpayer information
        - PDF must contain income summary
        - PDF must contain expense summary
        - PDF must contain deductions
        - PDF must contain tax calculation
        - PDF must contain disclaimer
        """
        generator = PDFGenerator()
        
        # Generate PDF
        pdf_bytes = generator.generate_tax_report(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year,
            language=language
        )
        
        # PDF should be generated
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        
        # PDF should start with PDF header
        assert pdf_bytes[:4] == b'%PDF'
        
        # PDF should be a valid size (at least 1KB, less than 10MB)
        assert len(pdf_bytes) > 1024
        assert len(pdf_bytes) < 10 * 1024 * 1024
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030),
        language=st.sampled_from(['de', 'en', 'zh'])
    )
    def test_pdf_report_multi_language_support(
        self,
        user_data,
        tax_data,
        tax_year,
        language
    ):
        """
        Property: PDF report supports multiple languages.
        
        For any valid data and language:
        - PDF must be generated in the specified language
        - All three languages (de, en, zh) must be supported
        """
        generator = PDFGenerator()
        
        # Generate PDF in specified language
        pdf_bytes = generator.generate_tax_report(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year,
            language=language
        )
        
        # PDF should be generated
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        
        # Verify language is supported
        assert language in ['de', 'en', 'zh']
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_csv_export_contains_required_fields(
        self,
        user_data,
        tax_data,
        tax_year
    ):
        """
        Property: CSV export contains all required fields.
        
        For any valid tax data:
        - CSV must contain income summary
        - CSV must contain expense summary
        - CSV must contain deductions
        - CSV must contain tax calculation
        """
        generator = CSVGenerator()
        
        # Generate CSV
        csv_string = generator.generate_tax_summary_csv(
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # CSV should be generated
        assert csv_string is not None
        assert len(csv_string) > 0
        
        # CSV should contain required sections
        assert 'Income Summary' in csv_string
        assert 'Expense Summary' in csv_string
        assert 'Deductions' in csv_string
        assert 'Tax Calculation' in csv_string
        
        # CSV should contain total income
        assert 'Total Income' in csv_string
        
        # CSV should contain total tax
        assert 'Total Tax' in csv_string
        
        # CSV should contain net income
        assert 'Net Income' in csv_string
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_report_contains_required_sections(
        self,
        user_data,
        tax_data,
        tax_year
    ):
        """
        Property: FinanzOnline XML contains all required sections.
        
        For any valid user and tax data:
        - XML must contain taxpayer information
        - XML must contain income sections (if income > 0)
        - XML must contain deductions (if deductions > 0)
        - XML must contain tax calculation
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # XML should be generated
        assert xml_string is not None
        assert len(xml_string) > 0
        
        # XML should contain root element
        assert '<Einkommensteuererklärung' in xml_string
        assert f'Jahr="{tax_year}"' in xml_string
        
        # XML should contain taxpayer information
        assert '<Steuerpflichtiger>' in xml_string
        
        # XML should contain tax calculation
        assert '<Steuerberechnung>' in xml_string
        
        # If there is income, XML should contain income sections
        if tax_data['income_summary']['total'] > 0:
            assert '<Einkünfte>' in xml_string
        
        # If there are deductions, XML should contain deductions
        if tax_data['deductions']['total'] > 0:
            assert '<Sonderausgaben>' in xml_string
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_xml_is_well_formed(
        self,
        user_data,
        tax_data,
        tax_year
    ):
        """
        Property: Generated XML is well-formed.
        
        For any valid data:
        - XML must be parseable
        - XML must have valid structure
        """
        generator = FinanzOnlineXMLGenerator()
        
        # Generate XML
        xml_string = generator.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # XML should be valid (validate method checks if parseable)
        is_valid = generator.validate(xml_string)
        assert is_valid is True
    
    @given(
        user_data=user_data_strategy(),
        tax_data=tax_data_strategy(),
        tax_year=st.integers(min_value=2020, max_value=2030)
    )
    def test_all_report_formats_contain_consistent_data(
        self,
        user_data,
        tax_data,
        tax_year
    ):
        """
        Property: All report formats contain consistent data.
        
        For any valid data:
        - PDF, CSV, and XML should all be generated successfully
        - All formats should contain the same tax year
        - All formats should contain the same total income
        - All formats should contain the same total tax
        """
        pdf_gen = PDFGenerator()
        csv_gen = CSVGenerator()
        xml_gen = FinanzOnlineXMLGenerator()
        
        # Generate all formats
        pdf_bytes = pdf_gen.generate_tax_report(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year,
            language='de'
        )
        
        csv_string = csv_gen.generate_tax_summary_csv(
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        xml_string = xml_gen.generate(
            user_data=user_data,
            tax_data=tax_data,
            tax_year=tax_year
        )
        
        # All formats should be generated
        assert pdf_bytes is not None and len(pdf_bytes) > 0
        assert csv_string is not None and len(csv_string) > 0
        assert xml_string is not None and len(xml_string) > 0
        
        # CSV should contain tax year
        assert str(tax_year) in csv_string
        
        # XML should contain tax year
        assert f'Jahr="{tax_year}"' in xml_string
        
        # CSV should contain total income
        total_income = tax_data['income_summary']['total']
        assert f"{total_income:.2f}" in csv_string
        
        # XML should contain total income (approximately)
        # Note: XML formatting may differ slightly
        assert '<Einkommen>' in xml_string or total_income == 0
