"""Tests for property expense categories"""
import pytest
from decimal import Decimal
from app.models.transaction import ExpenseCategory, TransactionType
from app.services.rule_based_classifier import RuleBasedClassifier


class MockTransaction:
    """Mock transaction for testing"""
    def __init__(self, description: str, transaction_type: TransactionType):
        self.description = description
        self.type = transaction_type


def test_expense_category_enum_has_property_categories():
    """Test that ExpenseCategory enum includes all property-related categories"""
    # Verify new property categories exist
    assert hasattr(ExpenseCategory, 'PROPERTY_MANAGEMENT_FEES')
    assert hasattr(ExpenseCategory, 'PROPERTY_INSURANCE')
    assert hasattr(ExpenseCategory, 'DEPRECIATION_AFA')
    
    # Verify existing categories still exist
    assert hasattr(ExpenseCategory, 'LOAN_INTEREST')
    assert hasattr(ExpenseCategory, 'PROPERTY_TAX')
    assert hasattr(ExpenseCategory, 'MAINTENANCE')
    assert hasattr(ExpenseCategory, 'UTILITIES')
    
    # Verify enum values
    assert ExpenseCategory.PROPERTY_MANAGEMENT_FEES.value == "property_management_fees"
    assert ExpenseCategory.PROPERTY_INSURANCE.value == "property_insurance"
    assert ExpenseCategory.DEPRECIATION_AFA.value == "depreciation_afa"


def test_classifier_recognizes_property_management_fees():
    """Test that classifier recognizes property management fee keywords"""
    classifier = RuleBasedClassifier()
    
    test_cases = [
        ("Hausverwaltung Müller GmbH", "property_management_fees"),
        ("Immobilienverwaltung Rechnung", "property_management_fees"),
        ("Verwaltungskosten Wohnung", "property_management_fees"),
        ("Hausmeister Service", "property_management_fees"),
    ]
    
    for description, expected_category in test_cases:
        transaction = MockTransaction(description, TransactionType.EXPENSE)
        result = classifier.classify(transaction)
        assert result.category == expected_category, \
            f"Expected '{expected_category}' for '{description}', got '{result.category}'"
        assert result.confidence >= Decimal("0.80")


def test_classifier_recognizes_property_insurance():
    """Test that classifier recognizes property insurance keywords"""
    classifier = RuleBasedClassifier()
    
    test_cases = [
        ("Gebäudeversicherung Allianz", "property_insurance"),
        ("Immobilienversicherung Uniqa", "property_insurance"),
        ("Eigenheimversicherung Generali", "property_insurance"),
        ("Wohnungsversicherung Prämie", "property_insurance"),
    ]
    
    for description, expected_category in test_cases:
        transaction = MockTransaction(description, TransactionType.EXPENSE)
        result = classifier.classify(transaction)
        assert result.category == expected_category, \
            f"Expected '{expected_category}' for '{description}', got '{result.category}'"
        assert result.confidence >= Decimal("0.80")


def test_classifier_recognizes_depreciation_afa():
    """Test that classifier recognizes depreciation (AfA) keywords"""
    classifier = RuleBasedClassifier()
    
    test_cases = [
        ("AfA Berechnung 2026", "depreciation_afa"),
        ("Abschreibung Gebäude", "depreciation_afa"),
        ("Absetzung für Abnutzung", "depreciation_afa"),
    ]
    
    for description, expected_category in test_cases:
        transaction = MockTransaction(description, TransactionType.EXPENSE)
        result = classifier.classify(transaction)
        assert result.category == expected_category, \
            f"Expected '{expected_category}' for '{description}', got '{result.category}'"
        assert result.confidence >= Decimal("0.80")


def test_classifier_recognizes_loan_interest():
    """Test that classifier recognizes loan interest keywords (existing category)"""
    classifier = RuleBasedClassifier()
    
    test_cases = [
        ("Kredit Zinsen Bank Austria", "loan_interest"),
        ("Darlehen Zinszahlung", "loan_interest"),
        ("Hypothek Zinsen", "loan_interest"),
    ]
    
    for description, expected_category in test_cases:
        transaction = MockTransaction(description, TransactionType.EXPENSE)
        result = classifier.classify(transaction)
        assert result.category == expected_category, \
            f"Expected '{expected_category}' for '{description}', got '{result.category}'"
        assert result.confidence >= Decimal("0.80")


def test_classifier_recognizes_utilities():
    """Test that classifier recognizes utilities keywords (existing category with enhancements)"""
    classifier = RuleBasedClassifier()
    
    test_cases = [
        ("Strom Wien Energie", "utilities"),
        ("Gas Rechnung EVN", "utilities"),
        ("Wasser Verbrauch", "utilities"),
        ("Heizkosten Dezember", "utilities"),
        ("Energie Abrechnung", "utilities"),
    ]
    
    for description, expected_category in test_cases:
        transaction = MockTransaction(description, TransactionType.EXPENSE)
        result = classifier.classify(transaction)
        assert result.category == expected_category, \
            f"Expected '{expected_category}' for '{description}', got '{result.category}'"
        assert result.confidence >= Decimal("0.80")


def test_classifier_recognizes_maintenance():
    """Test that classifier still recognizes maintenance keywords (existing category)"""
    classifier = RuleBasedClassifier()
    
    test_cases = [
        ("Reparatur Heizung", "maintenance"),
        ("Wartung Aufzug", "maintenance"),
        ("Reinigung Treppenhaus", "maintenance"),
    ]
    
    for description, expected_category in test_cases:
        transaction = MockTransaction(description, TransactionType.EXPENSE)
        result = classifier.classify(transaction)
        assert result.category == expected_category, \
            f"Expected '{expected_category}' for '{description}', got '{result.category}'"
        assert result.confidence >= Decimal("0.80")


def test_all_property_categories_are_valid_enum_values():
    """Test that all property-related categories are valid ExpenseCategory enum values"""
    property_categories = [
        "loan_interest",
        "property_management_fees",
        "property_insurance",
        "property_tax",
        "depreciation_afa",
        "maintenance",
        "utilities"
    ]
    
    valid_values = [e.value for e in ExpenseCategory]
    
    for category in property_categories:
        assert category in valid_values, \
            f"Property category '{category}' is not a valid ExpenseCategory enum value"
