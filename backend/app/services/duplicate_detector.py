"""Duplicate transaction detection service"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple, Any, Dict
from difflib import SequenceMatcher
from sqlalchemy.orm import Session


class DuplicateDetector:
    """
    Detects duplicate transactions based on date, amount, and description similarity.
    
    A transaction is considered a duplicate if:
    1. Same transaction date
    2. Same amount (exact match)
    3. Similar description (>80% similarity using SequenceMatcher)
    
    Cross-document detection extends this to:
    - Fuzzy date matching (within N days)
    - Category matching (same income/expense category)
    - Confidence scoring for duplicate likelihood
    """
    
    SIMILARITY_THRESHOLD = 0.80  # 80% similarity threshold
    DATE_TOLERANCE_DAYS = 3  # Days tolerance for fuzzy date matching
    
    def __init__(self, db: Session, transaction_model: Any = None):
        """
        Initialize duplicate detector.
        
        Args:
            db: Database session
            transaction_model: Transaction model class (optional, will import if not provided)
        """
        self.db = db
        if transaction_model is None:
            from app.models.transaction import Transaction
            self.transaction_model = Transaction
        else:
            self.transaction_model = transaction_model
    
    def check_duplicate(
        self,
        user_id: int,
        transaction_date: date,
        amount: Decimal,
        description: Optional[str],
        exclude_id: Optional[int] = None
    ) -> Tuple[bool, Optional[Any]]:
        """
        Check if a transaction is a duplicate of an existing transaction.
        
        Args:
            user_id: User ID
            transaction_date: Transaction date
            amount: Transaction amount
            description: Transaction description
            exclude_id: Transaction ID to exclude from check (for updates)
        
        Returns:
            Tuple of (is_duplicate, matching_transaction)
        """
        # Query existing transactions with same date and amount
        query = self.db.query(self.transaction_model).filter(
            self.transaction_model.user_id == user_id,
            self.transaction_model.transaction_date == transaction_date,
            self.transaction_model.amount == amount
        )
        
        # Exclude specific transaction if provided (for update operations)
        if exclude_id:
            query = query.filter(self.transaction_model.id != exclude_id)
        
        candidates = query.all()
        
        # If no candidates, not a duplicate
        if not candidates:
            return False, None
        
        # Check description similarity
        for candidate in candidates:
            if self._is_similar_description(description, candidate.description):
                return True, candidate
        
        return False, None
    
    def check_duplicates_batch(
        self,
        user_id: int,
        transactions: List[dict]
    ) -> List[dict]:
        """
        Check for duplicates in a batch of transactions.
        
        Args:
            user_id: User ID
            transactions: List of transaction dictionaries with keys:
                         transaction_date, amount, description
        
        Returns:
            List of dictionaries with original transaction data plus:
            - is_duplicate: bool
            - duplicate_of_id: Optional[int]
            - duplicate_confidence: Optional[float]
        """
        results = []
        
        for txn in transactions:
            is_duplicate, matching_txn = self.check_duplicate(
                user_id=user_id,
                transaction_date=txn['transaction_date'],
                amount=txn['amount'],
                description=txn.get('description')
            )
            
            result = {
                **txn,
                'is_duplicate': is_duplicate,
                'duplicate_of_id': matching_txn.id if matching_txn else None,
                'duplicate_confidence': None
            }
            
            # Calculate confidence score if duplicate found
            if is_duplicate and matching_txn:
                similarity = self._calculate_similarity(
                    txn.get('description'),
                    matching_txn.description
                )
                result['duplicate_confidence'] = round(similarity, 2)
            
            results.append(result)
        
        return results
    
    def find_duplicates_in_existing(
        self,
        user_id: int,
        limit: Optional[int] = None
    ) -> List[Tuple[Any, Any, float]]:
        """
        Find duplicate transactions in existing user transactions.
        
        Args:
            user_id: User ID
            limit: Maximum number of duplicate pairs to return
        
        Returns:
            List of tuples (transaction1, transaction2, similarity_score)
        """
        # Get all user transactions ordered by date
        transactions = self.db.query(self.transaction_model).filter(
            self.transaction_model.user_id == user_id
        ).order_by(self.transaction_model.transaction_date.desc()).all()
        
        duplicates = []
        checked_pairs = set()
        
        for i, txn1 in enumerate(transactions):
            for txn2 in transactions[i+1:]:
                # Skip if already checked
                pair_key = tuple(sorted([txn1.id, txn2.id]))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)
                
                # Check if duplicate
                if (txn1.transaction_date == txn2.transaction_date and
                    txn1.amount == txn2.amount):
                    
                    similarity = self._calculate_similarity(
                        txn1.description,
                        txn2.description
                    )
                    
                    if similarity >= self.SIMILARITY_THRESHOLD:
                        duplicates.append((txn1, txn2, similarity))
                        
                        if limit and len(duplicates) >= limit:
                            return duplicates
        
        return duplicates
    
    def detect_cross_document_duplicates(
        self,
        user_id: int,
        candidate_transactions: List[Dict[str, Any]],
        date_tolerance_days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect duplicates across different document sources (E1, Bescheid, Kaufvertrag, etc.)
        using fuzzy matching on amount, date, and category.
        
        This method is designed for historical data import to prevent double-counting
        when multiple documents contain the same transaction data.
        
        Args:
            user_id: User ID
            candidate_transactions: List of transaction dictionaries to check, each containing:
                - transaction_date: date
                - amount: Decimal
                - description: Optional[str]
                - type: str (income/expense)
                - income_category: Optional[str]
                - expense_category: Optional[str]
                - import_source: Optional[str] (e.g., 'e1_form', 'bescheid')
            date_tolerance_days: Days tolerance for fuzzy date matching (default: 3)
        
        Returns:
            List of dictionaries with original transaction data plus:
            - is_duplicate: bool
            - duplicate_of_id: Optional[int]
            - duplicate_confidence: float (0.0 to 1.0)
            - duplicate_match_reasons: List[str] (reasons for match)
        """
        if date_tolerance_days is None:
            date_tolerance_days = self.DATE_TOLERANCE_DAYS
        
        results = []
        
        for candidate in candidate_transactions:
            # Find potential duplicates in existing transactions
            match_result = self._find_cross_document_match(
                user_id=user_id,
                transaction_date=candidate['transaction_date'],
                amount=candidate['amount'],
                description=candidate.get('description'),
                transaction_type=candidate.get('type'),
                income_category=candidate.get('income_category'),
                expense_category=candidate.get('expense_category'),
                date_tolerance_days=date_tolerance_days
            )
            
            result = {
                **candidate,
                'is_duplicate': match_result['is_duplicate'],
                'duplicate_of_id': match_result['duplicate_of_id'],
                'duplicate_confidence': match_result['confidence'],
                'duplicate_match_reasons': match_result['match_reasons']
            }
            
            results.append(result)
        
        return results
    
    def _find_cross_document_match(
        self,
        user_id: int,
        transaction_date: date,
        amount: Decimal,
        description: Optional[str],
        transaction_type: Optional[str],
        income_category: Optional[str],
        expense_category: Optional[str],
        date_tolerance_days: int
    ) -> Dict[str, Any]:
        """
        Find a matching transaction using fuzzy matching criteria.
        
        Returns:
            Dictionary with:
            - is_duplicate: bool
            - duplicate_of_id: Optional[int]
            - confidence: float
            - match_reasons: List[str]
        """
        # Calculate date range for fuzzy matching
        date_min = transaction_date - timedelta(days=date_tolerance_days)
        date_max = transaction_date + timedelta(days=date_tolerance_days)
        
        # Query existing transactions within date range and exact amount
        query = self.db.query(self.transaction_model).filter(
            self.transaction_model.user_id == user_id,
            self.transaction_model.transaction_date >= date_min,
            self.transaction_model.transaction_date <= date_max,
            self.transaction_model.amount == amount
        )
        
        candidates = query.all()
        
        if not candidates:
            return {
                'is_duplicate': False,
                'duplicate_of_id': None,
                'confidence': 0.0,
                'match_reasons': []
            }
        
        # Score each candidate and find best match
        best_match = None
        best_confidence = 0.0
        best_reasons = []
        
        for candidate in candidates:
            confidence, reasons = self._calculate_cross_document_confidence(
                candidate=candidate,
                transaction_date=transaction_date,
                amount=amount,
                description=description,
                transaction_type=transaction_type,
                income_category=income_category,
                expense_category=expense_category
            )
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = candidate
                best_reasons = reasons
        
        # Consider it a duplicate if confidence >= 0.7 (70%)
        is_duplicate = best_confidence >= 0.70
        
        return {
            'is_duplicate': is_duplicate,
            'duplicate_of_id': best_match.id if is_duplicate else None,
            'confidence': round(best_confidence, 2),
            'match_reasons': best_reasons if is_duplicate else []
        }
    
    def _calculate_cross_document_confidence(
        self,
        candidate: Any,
        transaction_date: date,
        amount: Decimal,
        description: Optional[str],
        transaction_type: Optional[str],
        income_category: Optional[str],
        expense_category: Optional[str]
    ) -> Tuple[float, List[str]]:
        """
        Calculate confidence score for a potential duplicate match.
        
        Scoring criteria:
        - Exact amount match: 0.30 (always true if we got here)
        - Exact date match: 0.25, or 0.15 if within tolerance
        - Category match: 0.25
        - Description similarity: 0.20 (scaled by similarity score)
        
        Returns:
            Tuple of (confidence_score, match_reasons)
        """
        confidence = 0.0
        reasons = []
        
        # Amount match (always 0.30 since we filtered by exact amount)
        confidence += 0.30
        reasons.append("exact_amount_match")
        
        # Date match
        if candidate.transaction_date == transaction_date:
            confidence += 0.25
            reasons.append("exact_date_match")
        else:
            # Partial credit for date within tolerance
            confidence += 0.15
            days_diff = abs((candidate.transaction_date - transaction_date).days)
            reasons.append(f"date_within_{days_diff}_days")
        
        # Category match
        category_match = False
        if transaction_type:
            candidate_type = candidate.type.value if hasattr(candidate.type, 'value') else str(candidate.type)
            if candidate_type == transaction_type:
                # Check specific category
                if transaction_type == "income" and income_category:
                    candidate_category = (
                        candidate.income_category.value 
                        if hasattr(candidate.income_category, 'value') 
                        else str(candidate.income_category) if candidate.income_category else None
                    )
                    if candidate_category == income_category:
                        category_match = True
                        reasons.append(f"income_category_match_{income_category}")
                elif transaction_type == "expense" and expense_category:
                    candidate_category = (
                        candidate.expense_category.value 
                        if hasattr(candidate.expense_category, 'value') 
                        else str(candidate.expense_category) if candidate.expense_category else None
                    )
                    if candidate_category == expense_category:
                        category_match = True
                        reasons.append(f"expense_category_match_{expense_category}")
                else:
                    # Type matches but no specific category provided
                    category_match = True
                    reasons.append(f"transaction_type_match_{transaction_type}")
        
        if category_match:
            confidence += 0.25
        
        # Description similarity
        desc_similarity = self._calculate_similarity(description, candidate.description)
        if desc_similarity >= self.SIMILARITY_THRESHOLD:
            confidence += 0.20 * desc_similarity
            reasons.append(f"description_similarity_{int(desc_similarity * 100)}%")
        
        return confidence, reasons
    
    def _is_similar_description(
        self,
        desc1: Optional[str],
        desc2: Optional[str]
    ) -> bool:
        """
        Check if two descriptions are similar (>80% similarity).
        
        Args:
            desc1: First description
            desc2: Second description
        
        Returns:
            True if descriptions are similar, False otherwise
        """
        similarity = self._calculate_similarity(desc1, desc2)
        return similarity >= self.SIMILARITY_THRESHOLD
    
    def _calculate_similarity(
        self,
        desc1: Optional[str],
        desc2: Optional[str]
    ) -> float:
        """
        Calculate similarity between two descriptions using SequenceMatcher.
        
        Args:
            desc1: First description
            desc2: Second description
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Handle None cases
        if desc1 is None and desc2 is None:
            return 1.0  # Both None = identical
        if desc1 is None or desc2 is None:
            return 0.0  # One None = completely different
        
        # Normalize descriptions (lowercase, strip whitespace)
        desc1_normalized = desc1.lower().strip()
        desc2_normalized = desc2.lower().strip()
        
        # Handle empty strings
        if not desc1_normalized and not desc2_normalized:
            return 1.0  # Both empty = identical
        if not desc1_normalized or not desc2_normalized:
            return 0.0  # One empty = completely different
        
        # Calculate similarity using SequenceMatcher
        matcher = SequenceMatcher(None, desc1_normalized, desc2_normalized)
        return matcher.ratio()
