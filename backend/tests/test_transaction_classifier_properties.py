"""Property-based tests for transaction classification"""
import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from decimal import Decimal
from datetime import datetime
from backend.app.services.transaction_classifier import TransactionClassifier


# Mock transaction class for testing
class MockTransaction:
    def __init__(self, description: str, amount: Decimal, transaction_type: str):
        self.description = description
        self.amount = amount
        self.type = transaction_type
        self.date = datetime.now()


# Valid categories for income and expense
VALID_INCOME_CATEGORIES = [
    'employment',
    'rental',
    'self_employment',
    'capital_gains'
]

VALID_EXPENSE_CATEGORIES = [
    'groceries',
    'maintenance',
    'office_supplies',
    'equipment',
    'insurance',
    'utilities',
    'travel',
    'marketing',
    'professional_services',
    'property_tax',
    'loan_interest',
    'other'
]


class TestTransactionClassificationProperties:
    """
    Property 4: Transaction classification returns valid category
    
    **Validates: Requirements 2.1, 2.2, 2.3**
    
    This property ensures that the transaction classifier always returns
    a valid category from the predefined set of income or expense categories.
    """
    
    @given(
        description=st.text(min_size=1, max_size=200),
        amount=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('100000.00'),
            places=2
        ),
        transaction_type=st.sampled_from(['income', 'expense'])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_classification_returns_valid_category(
        self,
        description,
        amount,
        transaction_type
    ):
        """
        Property: Classification always returns a valid category
        
        For any transaction with a description, the classifier must return
        either a valid income category or a valid expense category depending
        on the transaction type.
        """
        # Filter out empty or whitespace-only descriptions
        assume(description.strip())
        
        # Create classifier instance
        classifier = TransactionClassifier()
        
        # Create mock transaction
        transaction = MockTransaction(description, amount, transaction_type)
        
        # Classify transaction
        result = classifier.classify_transaction(transaction)
        
        # Assert result has required attributes
        assert hasattr(result, 'category')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'category_type')
        
        # Assert category is valid for transaction type
        if transaction_type == 'income':
            assert result.category in VALID_INCOME_CATEGORIES, \
                f"Invalid income category: {result.category}"
        else:
            assert result.category in VALID_EXPENSE_CATEGORIES, \
                f"Invalid expense category: {result.category}"
        
        # Assert confidence is between 0 and 1
        assert Decimal('0.0') <= result.confidence <= Decimal('1.0'), \
            f"Confidence out of range: {result.confidence}"
    
    @given(
        description=st.text(min_size=1, max_size=200),
        amount=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('100000.00'),
            places=2
        ),
        transaction_type=st.sampled_from(['income', 'expense'])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_classification_confidence_consistency(
        self,
        description,
        amount,
        transaction_type
    ):
        """
        Property: Classification confidence is consistent across multiple calls
        
        Classifying the same transaction multiple times should return
        the same category and confidence score.
        """
        assume(description.strip())
        
        # Create classifier instance
        classifier = TransactionClassifier()
        
        # Create mock transaction
        transaction = MockTransaction(description, amount, transaction_type)
        
        # Classify multiple times
        result1 = classifier.classify_transaction(transaction)
        result2 = classifier.classify_transaction(transaction)
        result3 = classifier.classify_transaction(transaction)
        
        # Assert consistency
        assert result1.category == result2.category == result3.category, \
            "Category should be consistent across multiple classifications"
        assert result1.confidence == result2.confidence == result3.confidence, \
            "Confidence should be consistent across multiple classifications"
    
    @given(
        description=st.text(min_size=1, max_size=200),
        amount=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('100000.00'),
            places=2
        )
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_classification_type_matches_transaction_type(
        self,
        description,
        amount
    ):
        """
        Property: Classification type matches transaction type
        
        Income transactions should be classified as income categories,
        and expense transactions should be classified as expense categories.
        """
        assume(description.strip())
        
        # Create classifier instance
        classifier = TransactionClassifier()
        
        # Test income transaction
        income_transaction = MockTransaction(description, amount, 'income')
        income_result = classifier.classify_transaction(income_transaction)
        
        assert income_result.category_type == 'income', \
            "Income transaction should have income category_type"
        assert income_result.category in VALID_INCOME_CATEGORIES, \
            "Income transaction should have valid income category"
        
        # Test expense transaction
        expense_transaction = MockTransaction(description, amount, 'expense')
        expense_result = classifier.classify_transaction(expense_transaction)
        
        assert expense_result.category_type == 'expense', \
            "Expense transaction should have expense category_type"
        assert expense_result.category in VALID_EXPENSE_CATEGORIES, \
            "Expense transaction should have valid expense category"
    
    def test_known_merchants_high_confidence(self):
        """
        Property: Known Austrian merchants should have high confidence
        
        Transactions from well-known Austrian merchants should be classified
        with high confidence (>= 0.8).
        """
        classifier = TransactionClassifier()
        
        known_merchants = [
            ('BILLA Supermarkt', 'expense', 'groceries'),
            ('SPAR Markt', 'expense', 'groceries'),
            ('HOFER KG', 'expense', 'groceries'),
            ('OBI Baumarkt', 'expense', 'maintenance'),
            ('MediaMarkt', 'expense', 'equipment'),
        ]
        
        for description, txn_type, expected_category in known_merchants:
            transaction = MockTransaction(description, Decimal('50.00'), txn_type)
            result = classifier.classify_transaction(transaction)
            
            assert result.category == expected_category, \
                f"Expected {expected_category} for {description}, got {result.category}"
            assert result.confidence >= Decimal('0.8'), \
                f"Expected high confidence for {description}, got {result.confidence}"
    
    def test_empty_description_returns_none(self):
        """
        Property: Empty description returns None category
        
        Transactions with empty descriptions should return None category
        with zero confidence.
        """
        classifier = TransactionClassifier()
        
        transaction = MockTransaction('', Decimal('50.00'), 'expense')
        result = classifier.classify_transaction(transaction)
        
        assert result.category is None, \
            "Empty description should return None category"
        assert result.confidence == Decimal('0.0'), \
            "Empty description should return zero confidence"
    
    @given(
        amount=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('100000.00'),
            places=2
        )
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_classification_independent_of_amount(self, amount):
        """
        Property: Classification is primarily based on description, not amount
        
        The same description with different amounts should generally
        return the same category (though confidence may vary slightly).
        """
        classifier = TransactionClassifier()
        
        description = "BILLA Supermarkt"
        
        transaction1 = MockTransaction(description, amount, 'expense')
        transaction2 = MockTransaction(description, amount * 2, 'expense')
        
        result1 = classifier.classify_transaction(transaction1)
        result2 = classifier.classify_transaction(transaction2)
        
        assert result1.category == result2.category, \
            "Same description should return same category regardless of amount"
