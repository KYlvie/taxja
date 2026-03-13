"""
Example usage of TaxCalculationEngine

This example demonstrates how to use the unified TaxCalculationEngine
to calculate comprehensive tax liability for different user scenarios.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from decimal import Decimal
from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.vat_calculator import Transaction, PropertyType
from app.services.svs_calculator import UserType
from app.services.deduction_calculator import FamilyInfo


def print_tax_breakdown(breakdown_dict):
    """Pretty print tax breakdown"""
    print("\n" + "="*80)
    print("TAX CALCULATION BREAKDOWN")
    print("="*80)
    
    print(f"\nGross Income: €{breakdown_dict['gross_income']:,.2f}")
    print(f"Tax Year: {breakdown_dict['tax_year']}")
    print(f"User Type: {breakdown_dict['user_type']}")
    
    # Deductions
    print("\n--- DEDUCTIONS ---")
    deductions = breakdown_dict['deductions']
    if deductions['breakdown']:
        if 'commuting_allowance' in deductions['breakdown']:
            comm = deductions['breakdown']['commuting_allowance']
            print(f"  Commuting Allowance ({comm['type']}):")
            print(f"    Distance: {comm['distance_km']}km ({comm['distance_bracket']})")
            print(f"    Base Annual: €{comm['base_annual']:,.2f}")
            print(f"    Pendlereuro: €{comm['pendler_euro']:,.2f}")
            print(f"    Total: €{comm['total']:,.2f}")
        
        if 'home_office' in deductions['breakdown']:
            print(f"  Home Office Deduction: €{deductions['breakdown']['home_office']['amount']:,.2f}")
        
        if 'family_deductions' in deductions['breakdown']:
            fam = deductions['breakdown']['family_deductions']
            print(f"  Family Deductions:")
            print(f"    Children: {fam['num_children']}")
            print(f"    Child Deduction: €{fam['child_deduction']:,.2f}")
            if fam['is_single_parent']:
                print(f"    Single Parent Deduction: €{fam['single_parent_deduction']:,.2f}")
            print(f"    Total: €{fam['total']:,.2f}")
    
    print(f"\nTotal Deductions: €{deductions['total']:,.2f}")
    
    # Income Tax
    print("\n--- INCOME TAX ---")
    income_tax = breakdown_dict['income_tax']
    print(f"Taxable Income: €{income_tax['taxable_income']:,.2f}")
    print(f"Tax Brackets:")
    for bracket in income_tax['brackets']:
        print(f"  {bracket['range']} @ {bracket['rate']}: €{bracket['taxable_amount']:,.2f} → €{bracket['tax_amount']:,.2f}")
    print(f"Total Income Tax: €{income_tax['total']:,.2f}")
    print(f"Effective Rate: {income_tax['effective_rate']*100:.2f}%")
    
    if 'loss_carryforward_applied' in income_tax:
        print(f"Loss Carryforward Applied: €{income_tax['loss_carryforward_applied']:,.2f}")
        print(f"Remaining Loss Balance: €{income_tax['remaining_loss_balance']:,.2f}")
    
    # SVS
    print("\n--- SOCIAL INSURANCE (SVS) ---")
    svs = breakdown_dict['svs']
    if svs['total_annual'] > 0:
        print(f"Contribution Base: €{svs['contribution_base']:,.2f}/month")
        print(f"Breakdown:")
        for key, value in svs['breakdown'].items():
            print(f"  {key.capitalize()}: €{value:,.2f}/month")
        print(f"Monthly Total: €{svs['total_monthly']:,.2f}")
        print(f"Annual Total: €{svs['total_annual']:,.2f}")
        print(f"Deductible: {svs['deductible']}")
        if svs['note']:
            print(f"Note: {svs['note']}")
    else:
        print(f"No SVS contributions (Employee)")
    
    # VAT
    print("\n--- VALUE ADDED TAX (VAT) ---")
    vat = breakdown_dict['vat']
    if vat['exempt']:
        print(f"Status: EXEMPT")
        print(f"Reason: {vat['reason']}")
        if vat['warning']:
            print(f"⚠️  Warning: {vat['warning']}")
    else:
        print(f"Status: LIABLE")
        print(f"Output VAT: €{vat['output_vat']:,.2f}")
        print(f"Input VAT: €{vat['input_vat']:,.2f}")
        print(f"Net VAT Payable: €{vat['net_vat']:,.2f}")
    
    # Totals
    print("\n--- SUMMARY ---")
    print(f"Total Tax: €{breakdown_dict['total_tax']:,.2f}")
    print(f"Net Income: €{breakdown_dict['net_income']:,.2f}")
    print(f"Effective Tax Rate: {breakdown_dict['effective_tax_rate']*100:.2f}%")
    print("="*80 + "\n")


def example_1_employee_with_commute():
    """Example 1: Employee with commuting allowance"""
    print("\n### EXAMPLE 1: Employee with Commuting Allowance ###")
    
    # Tax configuration for 2026
    tax_config = {
        "tax_year": 2026,
        "exemption_amount": "13539.00",
        "tax_brackets": [
            {"lower": "0.00", "upper": "13539.00", "rate": "0.00"},
            {"lower": "13539.00", "upper": "21992.00", "rate": "0.20"},
            {"lower": "21992.00", "upper": "36458.00", "rate": "0.30"},
            {"lower": "36458.00", "upper": "70365.00", "rate": "0.40"},
            {"lower": "70365.00", "upper": "104859.00", "rate": "0.48"},
            {"lower": "104859.00", "upper": "1000000.00", "rate": "0.50"},
            {"lower": "1000000.00", "upper": None, "rate": "0.55"}
        ]
    }
    
    engine = TaxCalculationEngine(tax_config)
    
    breakdown = engine.generate_tax_breakdown(
        gross_income=Decimal('45000.00'),
        tax_year=2026,
        user_type=UserType.EMPLOYEE,
        commuting_distance_km=50,
        public_transport_available=False,  # Large Pendlerpauschale
        home_office_eligible=True
    )
    
    print_tax_breakdown(breakdown)


def example_2_gsvg_with_family():
    """Example 2: GSVG self-employed with family"""
    print("\n### EXAMPLE 2: GSVG Self-Employed with Family ###")
    
    tax_config = {
        "tax_year": 2026,
        "exemption_amount": "13539.00",
        "tax_brackets": [
            {"lower": "0.00", "upper": "13539.00", "rate": "0.00"},
            {"lower": "13539.00", "upper": "21992.00", "rate": "0.20"},
            {"lower": "21992.00", "upper": "36458.00", "rate": "0.30"},
            {"lower": "36458.00", "upper": "70365.00", "rate": "0.40"},
            {"lower": "70365.00", "upper": "104859.00", "rate": "0.48"},
            {"lower": "104859.00", "upper": "1000000.00", "rate": "0.50"},
            {"lower": "1000000.00", "upper": None, "rate": "0.55"}
        ]
    }
    
    engine = TaxCalculationEngine(tax_config)
    
    family_info = FamilyInfo(num_children=2, is_single_parent=True)
    
    breakdown = engine.generate_tax_breakdown(
        gross_income=Decimal('60000.00'),
        tax_year=2026,
        user_type=UserType.GSVG,
        family_info=family_info,
        home_office_eligible=True
    )
    
    print_tax_breakdown(breakdown)


def example_3_gsvg_with_vat():
    """Example 3: GSVG with VAT liability"""
    print("\n### EXAMPLE 3: GSVG Self-Employed with VAT Liability ###")
    
    tax_config = {
        "tax_year": 2026,
        "exemption_amount": "13539.00",
        "tax_brackets": [
            {"lower": "0.00", "upper": "13539.00", "rate": "0.00"},
            {"lower": "13539.00", "upper": "21992.00", "rate": "0.20"},
            {"lower": "21992.00", "upper": "36458.00", "rate": "0.30"},
            {"lower": "36458.00", "upper": "70365.00", "rate": "0.40"},
            {"lower": "70365.00", "upper": "104859.00", "rate": "0.48"},
            {"lower": "104859.00", "upper": "1000000.00", "rate": "0.50"},
            {"lower": "1000000.00", "upper": None, "rate": "0.55"}
        ]
    }
    
    engine = TaxCalculationEngine(tax_config)
    
    # Create transactions for VAT calculation
    transactions = [
        Transaction(amount=Decimal('80000.00'), is_income=True),
        Transaction(amount=Decimal('25000.00'), is_income=False),
        Transaction(amount=Decimal('10000.00'), is_income=False)
    ]
    
    breakdown = engine.generate_tax_breakdown(
        gross_income=Decimal('80000.00'),
        tax_year=2026,
        user_type=UserType.GSVG,
        transactions=transactions,
        gross_turnover=Decimal('80000.00')
    )
    
    print_tax_breakdown(breakdown)


def example_4_neue_selbstaendige():
    """Example 4: Neue Selbständige (freelancer)"""
    print("\n### EXAMPLE 4: Neue Selbständige (Freelancer) ###")
    
    tax_config = {
        "tax_year": 2026,
        "exemption_amount": "13539.00",
        "tax_brackets": [
            {"lower": "0.00", "upper": "13539.00", "rate": "0.00"},
            {"lower": "13539.00", "upper": "21992.00", "rate": "0.20"},
            {"lower": "21992.00", "upper": "36458.00", "rate": "0.30"},
            {"lower": "36458.00", "upper": "70365.00", "rate": "0.40"},
            {"lower": "70365.00", "upper": "104859.00", "rate": "0.48"},
            {"lower": "104859.00", "upper": "1000000.00", "rate": "0.50"},
            {"lower": "1000000.00", "upper": None, "rate": "0.55"}
        ]
    }
    
    engine = TaxCalculationEngine(tax_config)
    
    breakdown = engine.generate_tax_breakdown(
        gross_income=Decimal('35000.00'),
        tax_year=2026,
        user_type=UserType.NEUE_SELBSTAENDIGE,
        commuting_distance_km=25,
        public_transport_available=True,
        home_office_eligible=True
    )
    
    print_tax_breakdown(breakdown)


def example_5_quarterly_prepayment():
    """Example 5: Calculate quarterly prepayment"""
    print("\n### EXAMPLE 5: Quarterly Prepayment Calculation ###")
    
    tax_config = {
        "tax_year": 2026,
        "exemption_amount": "13539.00",
        "tax_brackets": [
            {"lower": "0.00", "upper": "13539.00", "rate": "0.00"},
            {"lower": "13539.00", "upper": "21992.00", "rate": "0.20"},
            {"lower": "21992.00", "upper": "36458.00", "rate": "0.30"},
            {"lower": "36458.00", "upper": "70365.00", "rate": "0.40"},
            {"lower": "70365.00", "upper": "104859.00", "rate": "0.48"},
            {"lower": "104859.00", "upper": "1000000.00", "rate": "0.50"},
            {"lower": "1000000.00", "upper": None, "rate": "0.55"}
        ]
    }
    
    engine = TaxCalculationEngine(tax_config)
    
    prepayment = engine.calculate_quarterly_prepayment(
        gross_income=Decimal('60000.00'),
        tax_year=2026,
        user_type=UserType.GSVG
    )
    
    print("\n" + "="*80)
    print("QUARTERLY PREPAYMENT CALCULATION")
    print("="*80)
    print(f"\nEstimated Annual Income: €60,000.00")
    print(f"User Type: GSVG")
    print(f"\nQuarterly Prepayments:")
    print(f"  Income Tax: €{prepayment['income_tax']:,.2f}")
    print(f"  SVS Contributions: €{prepayment['svs']:,.2f}")
    print(f"  Total per Quarter: €{prepayment['total']:,.2f}")
    print(f"\nAnnual Total: €{prepayment['total'] * 4:,.2f}")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Run all examples
    example_1_employee_with_commute()
    example_2_gsvg_with_family()
    example_3_gsvg_with_vat()
    example_4_neue_selbstaendige()
    example_5_quarterly_prepayment()
