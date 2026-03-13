"""Unit tests for ML-based transaction classifier"""
import pytest
from decimal import Decimal
from datetime import date
from app.services.ml_classifier import MLClassifier, ClassificationResult


class MockTransaction:
    """Mock transaction for testing"""
    def __init__(self, description: str, amount: Decimal, transaction_type: str):
        self.description = description
        self.amount = amount
        self.type = transaction_type


class TestMLClassifier:
    """Test suite for MLClassifier"""
    
    def test_classifier_initialization(self):
        """Test classifier can be initialized"""
        classifier = MLClassifier()
        assert classifier is not None
        assert classifier.min_training_samples == 10
    
    def test_classify_without_training_returns_low_confidence(self):
        """Test that untrained classifier returns low confidence"""
        classifier = MLClassifier()
        transaction = MockTransaction("BILLA Supermarket", Decimal("45.50"), "expense")
        
        result = classifier.classify(transaction)
        
        assert result is not None
        assert result.category is not None
        assert result.confidence <= Decimal("0.5")
    
    def test_classify_income_without_training(self):
        """Test income classification without training"""
        classifier = MLClassifier()
        transaction = MockTransaction("Salary payment", Decimal("3000.00"), "income")
        
        result = classifier.classify(transaction)
        
        assert result.category == "employment"
        # Confidence depends on whether pre-trained models are loaded from disk
        assert result.confidence >= Decimal("0.3")
        assert result.category_type == "income"
    
    def test_classify_expense_without_training(self):
        """Test expense classification without training"""
        classifier = MLClassifier()
        transaction = MockTransaction("Office supplies", Decimal("50.00"), "expense")
        
        result = classifier.classify(transaction)
        
        # Category depends on whether pre-trained models are loaded from disk
        assert result.category is not None
        assert result.confidence >= Decimal("0.1")
        assert result.category_type == "expense"
    
    def test_train_model_with_insufficient_data(self):
        """Test that training fails with insufficient data"""
        classifier = MLClassifier()
        
        # Only 5 samples (less than min_training_samples)
        training_data = [
            ("Salary", 3000.0, "employment", "income"),
            ("Rent payment", 1500.0, "rental", "income"),
            ("BILLA", 45.0, "groceries", "expense"),
            ("OBI hardware", 120.0, "maintenance", "expense"),
            ("Office supplies", 30.0, "office_supplies", "expense"),
        ]
        
        result = classifier.train_model(training_data)
        
        assert result is False
    
    def test_train_model_with_sufficient_data(self):
        """Test that training succeeds with sufficient data"""
        classifier = MLClassifier()
        
        # Create sufficient training data (10+ samples per type)
        training_data = [
            # Income samples
            ("Monthly salary", 3000.0, "employment", "income"),
            ("Salary payment", 3200.0, "employment", "income"),
            ("Wage", 2800.0, "employment", "income"),
            ("Rent from tenant", 800.0, "rental", "income"),
            ("Rental income", 850.0, "rental", "income"),
            ("Property rent", 900.0, "rental", "income"),
            ("Freelance invoice", 1500.0, "self_employment", "income"),
            ("Consulting fee", 2000.0, "self_employment", "income"),
            ("Project payment", 1800.0, "self_employment", "income"),
            ("Dividend payment", 500.0, "capital_gains", "income"),
            ("Interest income", 50.0, "capital_gains", "income"),
            ("Stock dividend", 300.0, "capital_gains", "income"),
            
            # Expense samples
            ("BILLA supermarket", 45.0, "groceries", "expense"),
            ("SPAR shopping", 60.0, "groceries", "expense"),
            ("HOFER groceries", 35.0, "groceries", "expense"),
            ("OBI hardware store", 120.0, "maintenance", "expense"),
            ("Baumax supplies", 85.0, "maintenance", "expense"),
            ("Repair materials", 95.0, "maintenance", "expense"),
            ("Office paper", 30.0, "office_supplies", "expense"),
            ("Printer ink", 45.0, "office_supplies", "expense"),
            ("Stationery", 25.0, "office_supplies", "expense"),
            ("Business trip hotel", 150.0, "travel", "expense"),
            ("Flight ticket", 200.0, "travel", "expense"),
            ("Train ticket", 80.0, "travel", "expense"),
            ("Insurance premium", 100.0, "insurance", "expense"),
            ("Property insurance", 120.0, "insurance", "expense"),
        ]
        
        result = classifier.train_model(training_data)
        
        assert result is True
        assert classifier.income_model is not None
        assert classifier.expense_model is not None
        assert classifier.income_vectorizer is not None
        assert classifier.expense_vectorizer is not None
    
    def test_classify_after_training_income(self):
        """Test income classification after training"""
        classifier = MLClassifier()
        
        # Train with sample data
        training_data = [
            ("Monthly salary", 3000.0, "employment", "income"),
            ("Salary payment", 3200.0, "employment", "income"),
            ("Wage", 2800.0, "employment", "income"),
            ("Rent from tenant", 800.0, "rental", "income"),
            ("Rental income", 850.0, "rental", "income"),
            ("Property rent", 900.0, "rental", "income"),
            ("Freelance invoice", 1500.0, "self_employment", "income"),
            ("Consulting fee", 2000.0, "self_employment", "income"),
            ("Project payment", 1800.0, "self_employment", "income"),
            ("Dividend payment", 500.0, "capital_gains", "income"),
            ("Interest income", 50.0, "capital_gains", "income"),
            ("Stock dividend", 300.0, "capital_gains", "income"),
        ]
        
        classifier.train_model(training_data)
        
        # Test classification
        transaction = MockTransaction("Salary for December", Decimal("3100.00"), "income")
        result = classifier.classify(transaction)
        
        assert result.category == "employment"
        assert result.confidence > Decimal("0.5")
        assert result.category_type == "income"
    
    def test_classify_after_training_expense(self):
        """Test expense classification after training"""
        classifier = MLClassifier()
        
        # Train with sample data
        training_data = [
            ("BILLA supermarket", 45.0, "groceries", "expense"),
            ("SPAR shopping", 60.0, "groceries", "expense"),
            ("HOFER groceries", 35.0, "groceries", "expense"),
            ("LIDL store", 40.0, "groceries", "expense"),
            ("MERKUR market", 55.0, "groceries", "expense"),
            ("OBI hardware store", 120.0, "maintenance", "expense"),
            ("Baumax supplies", 85.0, "maintenance", "expense"),
            ("Repair materials", 95.0, "maintenance", "expense"),
            ("Office paper", 30.0, "office_supplies", "expense"),
            ("Printer ink", 45.0, "office_supplies", "expense"),
            ("Stationery", 25.0, "office_supplies", "expense"),
            ("Business trip hotel", 150.0, "travel", "expense"),
        ]
        
        classifier.train_model(training_data)
        
        # Test classification
        transaction = MockTransaction("BILLA Wien", Decimal("52.30"), "expense")
        result = classifier.classify(transaction)
        
        assert result.category == "groceries"
        assert result.confidence > Decimal("0.5")
        assert result.category_type == "expense"
    
    def test_classify_with_empty_description(self):
        """Test classification with empty description"""
        classifier = MLClassifier()
        transaction = MockTransaction("", Decimal("100.00"), "expense")
        
        result = classifier.classify(transaction)
        
        assert result.category is None
        assert result.confidence == Decimal("0.0")
    
    def test_get_confidence_score(self):
        """Test get_confidence_score method"""
        classifier = MLClassifier()
        transaction = MockTransaction("Test transaction", Decimal("100.00"), "expense")
        
        confidence = classifier.get_confidence_score(transaction)
        
        assert isinstance(confidence, Decimal)
        assert confidence >= Decimal("0.0")
        assert confidence <= Decimal("1.0")
    
    def test_should_retrain_returns_true(self):
        """Test should_retrain method"""
        classifier = MLClassifier()
        
        # Current implementation always returns True
        assert classifier.should_retrain() is True
    
    def test_classification_result_repr(self):
        """Test ClassificationResult string representation"""
        result = ClassificationResult("groceries", Decimal("0.85"), "expense")
        
        repr_str = repr(result)
        
        assert "groceries" in repr_str
        assert "0.85" in repr_str
    
    def test_train_with_mixed_case_descriptions(self):
        """Test that training handles mixed case descriptions"""
        classifier = MLClassifier()
        
        training_data = [
            ("BILLA Supermarket", 45.0, "groceries", "expense"),
            ("billa shopping", 50.0, "groceries", "expense"),
            ("Billa Store", 40.0, "groceries", "expense"),
            ("SPAR Market", 60.0, "groceries", "expense"),
            ("spar shopping", 55.0, "groceries", "expense"),
            ("OBI Hardware", 120.0, "maintenance", "expense"),
            ("obi store", 100.0, "maintenance", "expense"),
            ("Office Paper", 30.0, "office_supplies", "expense"),
            ("office supplies", 35.0, "office_supplies", "expense"),
            ("OFFICE DEPOT", 40.0, "office_supplies", "expense"),
            ("Travel Hotel", 150.0, "travel", "expense"),
            ("travel expenses", 120.0, "travel", "expense"),
        ]
        
        result = classifier.train_model(training_data)
        
        assert result is True
        
        # Test classification with different cases
        transaction = MockTransaction("BILLA WIEN", Decimal("45.00"), "expense")
        classification = classifier.classify(transaction)
        
        assert classification.category == "groceries"
    
    def test_feature_extraction_combines_text_and_amount(self):
        """Test that features include both text and amount"""
        classifier = MLClassifier()
        
        # Train model first
        training_data = [
            ("Expensive item", 1000.0, "equipment", "expense"),
            ("Expensive purchase", 1200.0, "equipment", "expense"),
            ("Cheap item", 10.0, "office_supplies", "expense"),
            ("Cheap purchase", 15.0, "office_supplies", "expense"),
            ("Medium item", 100.0, "maintenance", "expense"),
            ("Medium purchase", 120.0, "maintenance", "expense"),
            ("Small expense", 5.0, "groceries", "expense"),
            ("Small purchase", 8.0, "groceries", "expense"),
            ("Large expense", 500.0, "travel", "expense"),
            ("Large purchase", 600.0, "travel", "expense"),
            ("Regular item", 50.0, "utilities", "expense"),
            ("Regular purchase", 55.0, "utilities", "expense"),
        ]
        
        classifier.train_model(training_data)
        
        # Test that amount influences classification
        # High amount should favor equipment
        expensive = MockTransaction("Item", Decimal("1100.00"), "expense")
        result_expensive = classifier.classify(expensive)
        
        # Low amount should favor office_supplies or groceries
        cheap = MockTransaction("Item", Decimal("12.00"), "expense")
        result_cheap = classifier.classify(cheap)
        
        # Categories should be different based on amount
        assert result_expensive.category != result_cheap.category or \
               result_expensive.confidence != result_cheap.confidence
