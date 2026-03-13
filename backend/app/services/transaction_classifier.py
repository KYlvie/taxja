"""Hybrid transaction classifier combining rule-based and ML approaches"""
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from .rule_based_classifier import RuleBasedClassifier, ClassificationResult as RuleResult
from .ml_classifier import MLClassifier, ClassificationResult as MLResult


class ClassificationResult:
    """Result of hybrid transaction classification"""
    
    def __init__(
        self,
        category: Optional[str],
        confidence: Decimal,
        category_type: Optional[str] = None,
        method: str = 'unknown'
    ):
        self.category = category
        self.confidence = confidence
        self.category_type = category_type
        self.method = method  # 'rule' or 'ml'
    
    def __repr__(self):
        return f"<ClassificationResult(category={self.category}, confidence={self.confidence}, method={self.method})>"


class TransactionClassifier:
    """
    Hybrid transaction classifier that combines rule-based and ML approaches.
    
    Strategy:
    1. Try rule-based classifier first
    2. If confidence is high (>= 0.8), use rule-based result
    3. Otherwise, fall back to ML classifier
    4. Return the result with higher confidence
    """
    
    HIGH_CONFIDENCE_THRESHOLD = Decimal('0.8')
    
    def __init__(self, model_path: Optional[str] = None, db: Optional[Session] = None):
        """
        Initialize hybrid classifier.
        
        Args:
            model_path: Path to ML models (optional)
            db: Database session for storing corrections (optional)
        """
        self.rule_classifier = RuleBasedClassifier()
        self.ml_classifier = MLClassifier(model_path=model_path)
        self.db = db
    
    def classify_transaction(
        self,
        transaction,
        user_context=None
    ) -> ClassificationResult:
        """
        Classify a transaction using hybrid approach.
        
        Args:
            transaction: Transaction object with description, amount, type
            user_context: Optional user context for ML classifier
        
        Returns:
            ClassificationResult with predicted category and confidence
        """
        if not transaction.description:
            return ClassificationResult(
                category=None,
                confidence=Decimal('0.0'),
                method='none'
            )
        
        # Step 1: Try rule-based classifier
        rule_result = self.rule_classifier.classify(transaction)
        
        # Step 2: If high confidence, use rule-based result
        if rule_result.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            return ClassificationResult(
                category=rule_result.category,
                confidence=rule_result.confidence,
                category_type=rule_result.category_type,
                method='rule'
            )
        
        # Step 3: Fall back to ML classifier
        ml_result = self.ml_classifier.classify(transaction, user_context)
        
        # Step 4: Return result with higher confidence
        if ml_result.confidence > rule_result.confidence:
            return ClassificationResult(
                category=ml_result.category,
                confidence=ml_result.confidence,
                category_type=ml_result.category_type,
                method='ml'
            )
        else:
            return ClassificationResult(
                category=rule_result.category,
                confidence=rule_result.confidence,
                category_type=rule_result.category_type,
                method='rule'
            )
    
    def get_confidence_score(self, transaction) -> Decimal:
        """Get confidence score for transaction classification"""
        result = self.classify_transaction(transaction)
        return result.confidence
    
    def learn_from_correction(
        self,
        transaction,
        correct_category: str,
        user_id: int
    ):
        """
        Learn from user correction.
        
        Stores the correction in the database for future ML model retraining.
        
        Args:
            transaction: Transaction object
            correct_category: Correct category from user
            user_id: User who made the correction
        """
        if self.db is None:
            # If no database session, just pass to ML classifier
            self.ml_classifier.add_training_example(
                transaction,
                correct_category,
                user_id
            )
            return
        
        # Store correction in database
        from app.models.classification_correction import ClassificationCorrection
        
        # Get original classification
        original_result = self.classify_transaction(transaction)
        
        correction = ClassificationCorrection(
            transaction_id=transaction.id,
            user_id=user_id,
            original_category=original_result.category or 'unknown',
            correct_category=correct_category,
            original_confidence=str(original_result.confidence)
        )
        
        self.db.add(correction)
        self.db.commit()
    
    def should_retrain(self) -> bool:
        """Check if ML model should be retrained"""
        return self.ml_classifier.should_retrain()
    
    def retrain(self, training_data):
        """
        Retrain ML model with new data.
        
        Args:
            training_data: List of tuples (description, amount, category, type)
        """
        return self.ml_classifier.train_model(training_data)
