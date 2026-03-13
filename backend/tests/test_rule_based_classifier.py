"""Unit tests for RuleBasedClassifier"""
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from decimal import Decimal
from datetime import date
from app.services.rule_based_classifier import RuleBasedClassifier


class MockTransaction:
    """Mock transaction for testing without database"""
    def __init__(self, type_val, amount, description):
        self.type = type_val
        self.amount = amount
        self.transaction_date = date(2026, 1, 15)
        self.description = description


class TestRuleBasedClassifier:
    """Test suite for RuleBasedClassifier"""
    
    @pytest.fixture
    def classifier(self):
        """Create classifier instance"""
        return RuleBasedClassifier()
    
    # Test Austrian supermarkets
    def test_classify_billa(self, classifier):
        """Test BILLA classification"""
        transaction = MockTransaction('expense', Decimal('45.50'), "BILLA DANKT 1234")
        result = classifier.classify(transaction)
        
        assert result.category == 'groceries'
        assert result.confidence >= Decimal('0.85')
        assert result.category_type == 'expense'
    
    def test_classify_spar(self, classifier):
        """Test SPAR classification"""
        transaction = MockTransaction('expense', Decimal('32.80'), "SPAR MARKT WIEN")
        result = classifier.classify(transaction)
        
        assert result.category == 'groceries'
        assert result.confidence >= Decimal('0.85')
    
    def test_classify_hofer(self, classifier):
        """Test HOFER classification"""
        transaction = MockTransaction('expense', Decimal('28.90'), "HOFER KG SALZBURG")
        result = classifier.classify(transaction)
        
        assert result.category == 'groceries'
        assert result.confidence >= Decimal('0.85')
    
    def test_classify_lidl(self, classifier):
        """Test LIDL classification"""
        transaction = MockTransaction('expense', Decimal('19.99'), "Lidl Österreich")
        result = classifier.classify(transaction)
        
        assert result.category == 'groceries'
        assert result.confidence >= Decimal('0.85')
    
    def test_classify_merkur(self, classifier):
        """Test MERKUR classification"""
        transaction = MockTransaction('expense', Decimal('67.40'), "MERKUR MARKT")
        result = classifier.classify(transaction)
        
        assert result.category == 'groceries'
        assert result.confidence >= Decimal('0.85')
    
    # Test hardware stores
    def test_classify_obi(self, classifier):
        """Test OBI classification"""
        transaction = MockTransaction('expense', Decimal('125.00'), "OBI Bau- und Heimwerkermarkt")
        result = classifier.classify(transaction)
        
        assert result.category == 'maintenance'
        assert result.confidence >= Decimal('0.80')
    
    def test_classify_baumax(self, classifier):
        """Test bauMax classification"""
        transaction = MockTransaction('expense', Decimal('89.50'), "bauMax Wien")
        result = classifier.classify(transaction)
        
        assert result.category == 'maintenance'
        assert result.confidence >= Decimal('0.80')
    
    # Test office supplies
    def test_classify_libro(self, classifier):
        """Test Libro classification"""
        transaction = MockTransaction('expense', Decimal('45.90'), "LIBRO Filiale")
        result = classifier.classify(transaction)
        
        assert result.category == 'office_supplies'
        assert result.confidence >= Decimal('0.80')
    
    # Test electronics
    def test_classify_mediamarkt(self, classifier):
        """Test MediaMarkt classification"""
        transaction = MockTransaction('expense', Decimal('599.00'), "MediaMarkt Wien")
        result = classifier.classify(transaction)
        
        assert result.category == 'equipment'
        assert result.confidence >= Decimal('0.80')
    
    # Test insurance
    def test_classify_insurance(self, classifier):
        """Test insurance company classification"""
        transaction = MockTransaction('expense', Decimal('150.00'), "UNIQA Versicherung")
        result = classifier.classify(transaction)
        
        assert result.category == 'insurance'
        assert result.confidence >= Decimal('0.85')
    
    # Test utilities
    def test_classify_utilities(self, classifier):
        """Test utility company classification"""
        transaction = MockTransaction('expense', Decimal('85.00'), "Wien Energie Strom")
        result = classifier.classify(transaction)
        
        assert result.category == 'utilities'
        assert result.confidence >= Decimal('0.85')
    
    # Test income classification
    def test_classify_salary(self, classifier):
        """Test salary classification"""
        transaction = MockTransaction('income', Decimal('3500.00'), "Gehalt Januar 2026")
        result = classifier.classify(transaction)
        
        assert result.category == 'employment'
        assert result.confidence >= Decimal('0.80')
        assert result.category_type == 'income'
    
    def test_classify_rental_income(self, classifier):
        """Test rental income classification"""
        transaction = MockTransaction('income', Decimal('1200.00'), "Miete Wohnung Januar")
        result = classifier.classify(transaction)
        
        assert result.category == 'rental'
        assert result.confidence >= Decimal('0.80')
    
    def test_classify_self_employment_income(self, classifier):
        """Test self-employment income classification"""
        transaction = MockTransaction('income', Decimal('2500.00'), "Rechnung 2026-001 Honorar")
        result = classifier.classify(transaction)
        
        assert result.category == 'self_employment'
        assert result.confidence >= Decimal('0.80')
    
    # Test keyword-based classification
    def test_classify_travel_expense(self, classifier):
        """Test travel expense classification by keyword"""
        transaction = MockTransaction('expense', Decimal('450.00'), "Hotel Reise München")
        result = classifier.classify(transaction)
        
        assert result.category == 'travel'
        assert result.confidence >= Decimal('0.70')
    
    def test_classify_professional_services(self, classifier):
        """Test professional services classification"""
        transaction = MockTransaction('expense', Decimal('800.00'), "Steuerberater Beratung")
        result = classifier.classify(transaction)
        
        assert result.category == 'professional_services'
        assert result.confidence >= Decimal('0.70')
    
    # Test edge cases
    def test_classify_empty_description(self, classifier):
        """Test classification with empty description"""
        transaction = MockTransaction('expense', Decimal('50.00'), "")
        result = classifier.classify(transaction)
        
        assert result.category is None
        assert result.confidence == Decimal('0.0')
    
    def test_classify_no_match(self, classifier):
        """Test classification with no matching patterns"""
        transaction = MockTransaction('expense', Decimal('50.00'), "Unknown merchant XYZ")
        result = classifier.classify(transaction)
        
        assert result.category == 'other'
        assert result.confidence <= Decimal('0.5')
    
    def test_get_confidence_score(self, classifier):
        """Test get_confidence_score method"""
        transaction = MockTransaction('expense', Decimal('45.50'), "BILLA DANKT 1234")
        confidence = classifier.get_confidence_score(transaction)
        
        assert confidence >= Decimal('0.85')
        assert confidence <= Decimal('1.0')
    
    # Test case insensitivity
    def test_case_insensitive_matching(self, classifier):
        """Test that matching is case-insensitive"""
        transaction = MockTransaction('expense', Decimal('45.50'), "billa dankt 1234")
        result = classifier.classify(transaction)
        
        assert result.category == 'groceries'
        assert result.confidence >= Decimal('0.85')
