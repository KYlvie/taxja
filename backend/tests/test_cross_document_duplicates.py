"""Unit tests for cross-document duplicate detection"""
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from tests.test_duplicate_detector import (
    User, Transaction, TransactionType, IncomeCategory, ExpenseCategory,
    db_engine, db, test_user, duplicate_detector
)


class TestCrossDocumentDuplicateDetection:
    """Test suite for cross-document duplicate detection"""
    
    def test_exact_cross_document_duplicate(
        self,
        db: Session,
        test_user: User,
        duplicate_detector
    ):
        """Test exact duplicate detection across documents (same date, amount, category)"""
        # Create existing transaction
        existing = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal('50000.00'),
            transaction_date=date(2023, 12, 31),
            description="Employment income",
            income_category=IncomeCategory.EMPLOYMENT
        )
        db.add(existing)
        db.commit()
        
        # Check candidate
        candidates = [
            {
                'transaction_date': date(2023, 12, 31),
                'amount': Decimal('50000.00'),
                'description': 'Employment income',
                'type': 'income',
                'income_category': 'employment'
            }
        ]
        
        results = duplicate_detector.detect_cross_document_duplicates(
            user_id=test_user.id,
            candidate_transactions=candidates
        )
        
        assert len(results) == 1
        assert results[0]['is_duplicate'] is True
        assert results[0]['duplicate_of_id'] == existing.id
        assert results[0]['duplicate_confidence'] >= 0.90
        assert 'exact_amount_match' in results[0]['duplicate_match_reasons']
        assert 'exact_date_match' in results[0]['duplicate_match_reasons']
    
    def test_fuzzy_date_matching(
        self,
        db: Session,
        test_user: User,
        duplicate_detector
    ):
        """Test fuzzy date matching within tolerance (3 days)"""
        # Create existing transaction
        existing = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal('1500.00'),
            transaction_date=date(2023, 6, 15),
            description="Tax payment",
            expense_category=ExpenseCategory.OTHER
        )
        db.add(existing)
        db.commit()
        
        # Check candidate with date 2 days later
        candidates = [
            {
                'transaction_date': date(2023, 6, 17),  # 2 days later
                'amount': Decimal('1500.00'),
                'description': 'Tax',
                'type': 'expense',
                'expense_category': 'other'
            }
        ]
        
        results = duplicate_detector.detect_cross_document_duplicates(
            user_id=test_user.id,
            candidate_transactions=candidates
        )
        
        assert len(results) == 1
        assert results[0]['is_duplicate'] is True
        assert results[0]['duplicate_of_id'] == existing.id
        assert results[0]['duplicate_confidence'] >= 0.70
        assert 'date_within_2_days' in results[0]['duplicate_match_reasons']
    
    def test_date_outside_tolerance_not_duplicate(
        self,
        db: Session,
        test_user: User,
        duplicate_detector
    ):
        """Test that dates outside tolerance are not considered duplicates"""
        # Create existing transaction
        existing = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal('2000.00'),
            transaction_date=date(2023, 1, 1),
            description="Rental income",
            income_category=IncomeCategory.RENTAL
        )
        db.add(existing)
        db.commit()
        
        # Check candidate with date 5 days later (outside default 3-day tolerance)
        candidates = [
            {
                'transaction_date': date(2023, 1, 6),  # 5 days later
                'amount': Decimal('2000.00'),
                'description': 'Rental income',
                'type': 'income',
                'income_category': 'rental'
            }
        ]
        
        results = duplicate_detector.detect_cross_document_duplicates(
            user_id=test_user.id,
            candidate_transactions=candidates
        )
        
        assert len(results) == 1
        assert results[0]['is_duplicate'] is False
        assert results[0]['duplicate_of_id'] is None
    
    def test_custom_date_tolerance(
        self,
        db: Session,
        test_user: User,
        duplicate_detector
    ):
        """Test custom date tolerance parameter"""
        # Create existing transaction
        existing = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal('3000.00'),
            transaction_date=date(2023, 3, 1),
            description="Business income",
            income_category=IncomeCategory.BUSINESS
        )
        db.add(existing)
        db.commit()
        
        # Check candidate with date 7 days later
        candidates = [
            {
                'transaction_date': date(2023, 3, 8),  # 7 days later
                'amount': Decimal('3000.00'),
                'description': 'Business income',
                'type': 'income',
                'income_category': 'business'
            }
        ]
        
        # Should not match with default tolerance (3 days)
        results_default = duplicate_detector.detect_cross_document_duplicates(
            user_id=test_user.id,
            candidate_transactions=candidates
        )
        assert results_default[0]['is_duplicate'] is False
        
        # Should match with custom tolerance (7 days)
        results_custom = duplicate_detector.detect_cross_document_duplicates(
            user_id=test_user.id,
            candidate_transactions=candidates,
            date_tolerance_days=7
        )
        assert results_custom[0]['is_duplicate'] is True
        assert results_custom[0]['duplicate_of_id'] == existing.id
    
    def test_category_matching_income(
        self,
        db: Session,
        test_user: User,
        duplicate_detector
    ):
        """Test that income category matching increases confidence"""
        # Create existing transaction
        existing = Transaction(
            user_id=test_user.id,
            type=TransactionType.INCOME,
            amount=Decimal('5000.00'),
            transaction_date=date(2023, 5, 1),
            description="Self-employment income",
            income_category=IncomeCategory.SELF_EMPLOYMENT
        )
        db.add(existing)
        db.commit()
        
        # Check candidate with matching category
        candidates = [
            {
                'transaction_date': date(2023, 5, 1),
                'amount': Decimal('5000.00'),
                'description': 'Self-employment',
                'type': 'income',
                'income_category': 'self_employment'
            }
        ]
        
        results = duplicate_detector.detect_cross_document_duplicates(
            user_id=test_user.id,
            candidate_transactions=candidates
        )
        
        assert len(results) == 1
        assert results[0]['is_duplicate'] is True
        assert results[0]['duplicate_confidence'] >= 0.80
        assert any('income_category_match' in reason for reason in results[0]['duplicate_match_reasons'])
    
    def test_no_existing_transactions(
        self,
        db: Session,
        test_user: User,
        duplicate_detector
    ):
        """Test behavior when no existing transactions exist"""
        candidates = [
            {
                'transaction_date': date(2023, 1, 1),
                'amount': Decimal('1000.00'),
                'description': 'First transaction',
                'type': 'income',
                'income_category': 'employment'
            }
        ]
        
        results = duplicate_detector.detect_cross_document_duplicates(
            user_id=test_user.id,
            candidate_transactions=candidates
        )
        
        assert len(results) == 1
        assert results[0]['is_duplicate'] is False
        assert results[0]['duplicate_of_id'] is None
        assert results[0]['duplicate_confidence'] == 0.0
