"""
Employee Refund Calculator Demo

This script demonstrates how to use the employee refund calculator
to calculate potential tax refunds (Arbeitnehmerveranlagung).

Requirements: 37.1, 37.2, 37.3, 37.4, 37.5, 37.6, 37.7
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.employee_refund_calculator import (
    EmployeeRefundCalculator,
    LohnzettelData,
)
from app.models.user import User, FamilyInfo


def demo_basic_refund():
    """Demo: Basic refund calculation"""
    print("=" * 80)
    print("Demo 1: Basic Employee Refund Calculation")
    print("=" * 80)

    # Create calculator
    calculator = EmployeeRefundCalculator()

    # Create Lohnzettel data
    lohnzettel = LohnzettelData(
        gross_income=Decimal("45000.00"),  # €45,000 annual gross income
        withheld_tax=Decimal("9500.00"),  # €9,500 withheld tax
        withheld_svs=Decimal("6750.00"),  # €6,750 social insurance
        employer_name="Example GmbH",
        tax_year=2026,
    )

    # Create user with no special deductions
    user = User()
    user.id = 1
    user.email = "employee@example.com"
    user.commuting_distance = 0
    user.family_info = FamilyInfo(num_children=0, is_single_parent=False)

    # Calculate refund
    result = calculator.calculate_refund(lohnzettel, user)

    # Display results
    print(f"\nGross Income: €{result.gross_income:,.2f}")
    print(f"Withheld Tax: €{result.withheld_tax:,.2f}")
    print(f"Actual Tax Liability: €{result.actual_tax_liability:,.2f}")
    print(f"\n{'REFUND' if result.is_refund else 'PAYMENT'}: €{result.refund_amount:,.2f}")
    print(f"\nDeductions Applied:")
    for key, value in result.deductions_applied.items():
        print(f"  - {key.replace('_', ' ').title()}: €{value:,.2f}")
    print(f"\nExplanation:\n{result.explanation}")


def demo_refund_with_commuting():
    """Demo: Refund with commuting allowance"""
    print("\n\n" + "=" * 80)
    print("Demo 2: Refund with Commuting Allowance (Pendlerpauschale)")
    print("=" * 80)

    calculator = EmployeeRefundCalculator()

    lohnzettel = LohnzettelData(
        gross_income=Decimal("45000.00"),
        withheld_tax=Decimal("9500.00"),
        withheld_svs=Decimal("6750.00"),
        employer_name="Example GmbH",
        tax_year=2026,
    )

    # User with 45km commute, public transport available
    user = User()
    user.id = 2
    user.email = "commuter@example.com"
    user.commuting_distance = 45  # 45km commute
    user.public_transport_available = True  # Public transport available
    user.family_info = FamilyInfo(num_children=0, is_single_parent=False)

    result = calculator.calculate_refund(lohnzettel, user)

    print(f"\nGross Income: €{result.gross_income:,.2f}")
    print(f"Withheld Tax: €{result.withheld_tax:,.2f}")
    print(f"Actual Tax Liability: €{result.actual_tax_liability:,.2f}")
    print(f"\n{'REFUND' if result.is_refund else 'PAYMENT'}: €{result.refund_amount:,.2f}")
    print(f"\nDeductions Applied:")
    for key, value in result.deductions_applied.items():
        print(f"  - {key.replace('_', ' ').title()}: €{value:,.2f}")


def demo_refund_with_family():
    """Demo: Refund with family deductions"""
    print("\n\n" + "=" * 80)
    print("Demo 3: Refund with Family Deductions (Kinderabsetzbetrag)")
    print("=" * 80)

    calculator = EmployeeRefundCalculator()

    lohnzettel = LohnzettelData(
        gross_income=Decimal("50000.00"),
        withheld_tax=Decimal("11000.00"),
        withheld_svs=Decimal("7500.00"),
        employer_name="Example GmbH",
        tax_year=2026,
    )

    # Single parent with 2 children
    user = User()
    user.id = 3
    user.email = "parent@example.com"
    user.commuting_distance = 0
    user.family_info = FamilyInfo(num_children=2, is_single_parent=True)

    result = calculator.calculate_refund(lohnzettel, user)

    print(f"\nGross Income: €{result.gross_income:,.2f}")
    print(f"Withheld Tax: €{result.withheld_tax:,.2f}")
    print(f"Actual Tax Liability: €{result.actual_tax_liability:,.2f}")
    print(f"\n{'REFUND' if result.is_refund else 'PAYMENT'}: €{result.refund_amount:,.2f}")
    print(f"\nDeductions Applied:")
    for key, value in result.deductions_applied.items():
        print(f"  - {key.replace('_', ' ').title()}: €{value:,.2f}")


def demo_refund_with_all_deductions():
    """Demo: Refund with all possible deductions"""
    print("\n\n" + "=" * 80)
    print("Demo 4: Refund with All Deductions")
    print("=" * 80)

    calculator = EmployeeRefundCalculator()

    lohnzettel = LohnzettelData(
        gross_income=Decimal("60000.00"),
        withheld_tax=Decimal("14000.00"),
        withheld_svs=Decimal("9000.00"),
        employer_name="Example GmbH",
        tax_year=2026,
    )

    # User with commuting, family, and additional deductions
    user = User()
    user.id = 4
    user.email = "maxdeductions@example.com"
    user.commuting_distance = 65  # 65km commute (large Pendlerpauschale)
    user.public_transport_available = False  # No public transport
    user.family_info = FamilyInfo(num_children=3, is_single_parent=True)

    # Additional deductions
    additional_deductions = {
        "donations": Decimal("500.00"),  # Charitable donations
        "church_tax": Decimal("200.00"),  # Church tax
    }

    result = calculator.calculate_refund(lohnzettel, user, additional_deductions)

    print(f"\nGross Income: €{result.gross_income:,.2f}")
    print(f"Withheld Tax: €{result.withheld_tax:,.2f}")
    print(f"Actual Tax Liability: €{result.actual_tax_liability:,.2f}")
    print(f"\n{'REFUND' if result.is_refund else 'PAYMENT'}: €{result.refund_amount:,.2f}")
    print(f"\nDeductions Applied:")
    for key, value in result.deductions_applied.items():
        print(f"  - {key.replace('_', ' ').title()}: €{value:,.2f}")
    print(f"\nTotal Deductions: €{sum(result.deductions_applied.values()):,.2f}")


def demo_refund_estimate():
    """Demo: Estimate refund potential without Lohnzettel"""
    print("\n\n" + "=" * 80)
    print("Demo 5: Estimate Refund Potential (Dashboard Widget)")
    print("=" * 80)

    calculator = EmployeeRefundCalculator()

    # User with commuting and family
    user = User()
    user.id = 5
    user.email = "estimate@example.com"
    user.commuting_distance = 30
    user.public_transport_available = True
    user.family_info = FamilyInfo(num_children=1, is_single_parent=False)

    # Estimate refund with estimated income
    estimate = calculator.estimate_refund_potential(
        user, tax_year=2026, estimated_gross_income=Decimal("48000.00")
    )

    print(f"\nEstimated Refund: €{estimate['estimated_refund']:,.2f}")
    print(f"Is Refund: {estimate['is_refund']}")
    print(f"Confidence: {estimate['confidence']}")
    print(f"\nSuggestions:")
    for suggestion in estimate["suggestions"]:
        print(f"  - {suggestion}")
    print(f"\nMessage: {estimate['message']}")


def demo_low_income_full_refund():
    """Demo: Low income below exemption threshold"""
    print("\n\n" + "=" * 80)
    print("Demo 6: Low Income - Full Refund (Below Exemption)")
    print("=" * 80)

    calculator = EmployeeRefundCalculator()

    lohnzettel = LohnzettelData(
        gross_income=Decimal("12000.00"),  # Below €13,539 exemption
        withheld_tax=Decimal("800.00"),  # Some tax was withheld
        withheld_svs=Decimal("1800.00"),
        employer_name="Part-time Employer",
        tax_year=2026,
    )

    user = User()
    user.id = 6
    user.email = "parttime@example.com"
    user.commuting_distance = 0
    user.family_info = FamilyInfo(num_children=0, is_single_parent=False)

    result = calculator.calculate_refund(lohnzettel, user)

    print(f"\nGross Income: €{result.gross_income:,.2f}")
    print(f"Withheld Tax: €{result.withheld_tax:,.2f}")
    print(f"Actual Tax Liability: €{result.actual_tax_liability:,.2f}")
    print(f"\n{'REFUND' if result.is_refund else 'PAYMENT'}: €{result.refund_amount:,.2f}")
    print(f"\nNote: Income below exemption threshold (€13,539) - full refund!")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "EMPLOYEE REFUND CALCULATOR DEMO" + " " * 31 + "║")
    print("║" + " " * 20 + "(Arbeitnehmerveranlagung)" + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")

    demo_basic_refund()
    demo_refund_with_commuting()
    demo_refund_with_family()
    demo_refund_with_all_deductions()
    demo_refund_estimate()
    demo_low_income_full_refund()

    print("\n\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print("\n⚠️  Disclaimer: These calculations are estimates only.")
    print("Final refund amounts may vary based on FinanzOnline calculation.")
    print("For complex situations, consult a Steuerberater.")
    print("\n")
