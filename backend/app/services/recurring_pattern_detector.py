"""Automatic detection of recurring transaction patterns"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from collections import defaultdict

from app.models.transaction import Transaction, TransactionType
from app.models.recurring_transaction import RecurringTransaction, RecurrenceFrequency


class RecurringPattern:
    """Detected recurring transaction pattern"""
    
    def __init__(
        self,
        description: str,
        amount: Decimal,
        transaction_type: str,
        category: str,
        frequency: RecurrenceFrequency,
        occurrences: int,
        confidence: float,
        sample_transactions: List[int],
        suggested_day_of_month: int,
        property_id: Optional[str] = None,
    ):
        self.description = description
        self.amount = amount
        self.transaction_type = transaction_type
        self.category = category
        self.frequency = frequency
        self.occurrences = occurrences
        self.confidence = confidence
        self.sample_transactions = sample_transactions
        self.suggested_day_of_month = suggested_day_of_month
        self.property_id = property_id


class RecurringPatternDetector:
    """
    Detects recurring transaction patterns from user's transaction history.
    
    Strategy:
    1. Group similar transactions by description and amount
    2. Analyze time intervals between transactions
    3. Detect monthly, quarterly, or annual patterns
    4. Calculate confidence based on consistency
    5. Suggest automatic recurring transaction setup
    """
    
    # Thresholds
    MIN_OCCURRENCES = 2  # Minimum 2 occurrences to suggest
    AMOUNT_TOLERANCE = Decimal('0.05')  # 5% tolerance for amount variation
    DESCRIPTION_SIMILARITY_THRESHOLD = 0.8  # 80% similarity for description matching
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_patterns(
        self,
        user_id: int,
        lookback_months: int = 6,
        min_confidence: float = 0.7
    ) -> List[RecurringPattern]:
        """
        Detect recurring transaction patterns for a user.
        
        Args:
            user_id: User ID to analyze
            lookback_months: How many months to look back
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of detected recurring patterns
        """
        # Get user's transactions from the last N months
        cutoff_date = date.today() - timedelta(days=lookback_months * 30)
        
        transactions = self.db.query(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= cutoff_date,
                Transaction.is_system_generated == False  # Exclude auto-generated
            )
        ).order_by(Transaction.transaction_date).all()
        
        if len(transactions) < self.MIN_OCCURRENCES:
            return []
        
        # Group transactions by similarity
        groups = self._group_similar_transactions(transactions)
        
        # Analyze each group for recurring patterns
        patterns = []
        for group in groups:
            if len(group) < self.MIN_OCCURRENCES:
                continue
            
            pattern = self._analyze_group_for_pattern(group)
            if pattern and pattern.confidence >= min_confidence:
                patterns.append(pattern)
        
        # Sort by confidence (highest first)
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        
        return patterns
    
    def _group_similar_transactions(
        self,
        transactions: List[Transaction]
    ) -> List[List[Transaction]]:
        """
        Group transactions by similarity (description + amount).
        
        Uses fuzzy matching for descriptions and amount tolerance.
        """
        groups = []
        used = set()
        
        for i, txn in enumerate(transactions):
            if i in used:
                continue
            
            # Start a new group
            group = [txn]
            used.add(i)
            
            # Find similar transactions
            for j, other in enumerate(transactions[i+1:], start=i+1):
                if j in used:
                    continue
                
                if self._are_similar(txn, other):
                    group.append(other)
                    used.add(j)
            
            groups.append(group)
        
        return groups
    
    def _are_similar(self, txn1: Transaction, txn2: Transaction) -> bool:
        """Check if two transactions are similar"""
        # Must be same type
        if txn1.type != txn2.type:
            return False
        
        # Must be same category
        if txn1.income_category != txn2.income_category:
            return False
        if txn1.expense_category != txn2.expense_category:
            return False
        
        # Amount must be within tolerance
        amount_diff = abs(txn1.amount - txn2.amount)
        amount_tolerance = txn1.amount * self.AMOUNT_TOLERANCE
        if amount_diff > amount_tolerance:
            return False
        
        # Description similarity (simple approach)
        if txn1.description and txn2.description:
            similarity = self._calculate_description_similarity(
                txn1.description,
                txn2.description
            )
            if similarity < self.DESCRIPTION_SIMILARITY_THRESHOLD:
                return False
        
        return True
    
    def _calculate_description_similarity(self, desc1: str, desc2: str) -> float:
        """Calculate similarity between two descriptions (0.0 to 1.0)"""
        # Simple approach: normalize and compare
        d1 = desc1.lower().strip()
        d2 = desc2.lower().strip()
        
        if d1 == d2:
            return 1.0
        
        # Check if one contains the other
        if d1 in d2 or d2 in d1:
            return 0.9
        
        # Token-based similarity
        tokens1 = set(d1.split())
        tokens2 = set(d2.split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union)
    
    def _analyze_group_for_pattern(
        self,
        group: List[Transaction]
    ) -> Optional[RecurringPattern]:
        """Analyze a group of transactions for recurring pattern"""
        if len(group) < self.MIN_OCCURRENCES:
            return None
        
        # Sort by date
        group.sort(key=lambda t: t.transaction_date)
        
        # Calculate intervals between transactions
        intervals = []
        for i in range(len(group) - 1):
            days = (group[i+1].transaction_date - group[i].transaction_date).days
            intervals.append(days)
        
        if not intervals:
            return None
        
        # Detect frequency pattern
        frequency, confidence = self._detect_frequency(intervals)
        
        if frequency is None:
            return None
        
        # Calculate average amount
        avg_amount = sum(t.amount for t in group) / len(group)
        
        # Get most common day of month
        days_of_month = [t.transaction_date.day for t in group]
        suggested_day = max(set(days_of_month), key=days_of_month.count)
        
        # Get category
        category = None
        if group[0].type == TransactionType.INCOME:
            category = group[0].income_category.value if group[0].income_category else None
        else:
            category = group[0].expense_category.value if group[0].expense_category else None
        
        # Check if property-related
        property_id = group[0].property_id if group[0].property_id else None
        
        return RecurringPattern(
            description=group[0].description or "Unnamed transaction",
            amount=avg_amount,
            transaction_type=group[0].type.value,
            category=category or "other",
            frequency=frequency,
            occurrences=len(group),
            confidence=confidence,
            sample_transactions=[t.id for t in group],
            suggested_day_of_month=suggested_day,
            property_id=str(property_id) if property_id else None,
        )
    
    def _detect_frequency(
        self,
        intervals: List[int]
    ) -> Tuple[Optional[RecurrenceFrequency], float]:
        """
        Detect frequency pattern from intervals.
        
        Returns:
            (frequency, confidence) tuple
        """
        if not intervals:
            return None, 0.0
        
        avg_interval = sum(intervals) / len(intervals)
        
        # Calculate consistency (lower std dev = higher confidence)
        variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
        std_dev = variance ** 0.5
        
        # Determine frequency
        frequency = None
        expected_interval = 0
        
        if 25 <= avg_interval <= 35:  # Monthly (28-31 days)
            frequency = RecurrenceFrequency.MONTHLY
            expected_interval = 30
        elif 85 <= avg_interval <= 95:  # Quarterly (~90 days)
            frequency = RecurrenceFrequency.QUARTERLY
            expected_interval = 90
        elif 360 <= avg_interval <= 370:  # Annually (~365 days)
            frequency = RecurrenceFrequency.ANNUALLY
            expected_interval = 365
        elif 12 <= avg_interval <= 16:  # Biweekly (14 days)
            frequency = RecurrenceFrequency.BIWEEKLY
            expected_interval = 14
        elif 6 <= avg_interval <= 8:  # Weekly (7 days)
            frequency = RecurrenceFrequency.WEEKLY
            expected_interval = 7
        else:
            return None, 0.0
        
        # Calculate confidence based on consistency
        # Lower deviation = higher confidence
        max_acceptable_deviation = expected_interval * 0.15  # 15% tolerance
        
        if std_dev <= max_acceptable_deviation * 0.3:
            confidence = 0.95
        elif std_dev <= max_acceptable_deviation * 0.5:
            confidence = 0.85
        elif std_dev <= max_acceptable_deviation:
            confidence = 0.75
        else:
            confidence = 0.60
        
        return frequency, confidence
    
    def check_if_already_automated(
        self,
        user_id: int,
        pattern: RecurringPattern
    ) -> bool:
        """Check if this pattern is already automated"""
        # Check if there's an active recurring transaction matching this pattern
        existing = self.db.query(RecurringTransaction).filter(
            and_(
                RecurringTransaction.user_id == user_id,
                RecurringTransaction.is_active == True,
                RecurringTransaction.description.ilike(f"%{pattern.description}%"),
                RecurringTransaction.amount.between(
                    pattern.amount * Decimal('0.95'),
                    pattern.amount * Decimal('1.05')
                )
            )
        ).first()
        
        return existing is not None
