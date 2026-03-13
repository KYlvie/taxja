"""Classification learning service for managing user corrections and model retraining"""
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.classification_correction import ClassificationCorrection
from app.models.transaction import Transaction
from app.services.ml_classifier import MLClassifier


class ClassificationLearningService:
    """
    Service for managing classification corrections and ML model retraining.
    
    This service:
    1. Stores user corrections in the database
    2. Retrieves correction data for retraining
    3. Triggers ML model retraining when sufficient data is available
    """
    
    def __init__(self, db: Session, model_path: Optional[str] = None):
        """
        Initialize the learning service.
        
        Args:
            db: Database session
            model_path: Path to ML models
        """
        self.db = db
        self.ml_classifier = MLClassifier(model_path=model_path)
        self.min_corrections_for_retrain = 50  # Minimum corrections before retraining
    
    def store_correction(
        self,
        transaction_id: int,
        user_id: int,
        original_category: str,
        correct_category: str,
        original_confidence: Optional[str] = None
    ) -> ClassificationCorrection:
        """
        Store a user correction in the database.
        
        Args:
            transaction_id: ID of the transaction
            user_id: ID of the user who made the correction
            original_category: Original classification category
            correct_category: Corrected category from user
            original_confidence: Original confidence score (optional)
        
        Returns:
            ClassificationCorrection object
        """
        correction = ClassificationCorrection(
            transaction_id=transaction_id,
            user_id=user_id,
            original_category=original_category,
            correct_category=correct_category,
            original_confidence=original_confidence
        )
        
        self.db.add(correction)
        self.db.commit()
        self.db.refresh(correction)
        
        return correction
    
    def get_corrections_count(self) -> int:
        """
        Get the total number of corrections in the database.
        
        Returns:
            Number of corrections
        """
        return self.db.query(ClassificationCorrection).count()
    
    def get_corrections_since_last_training(self) -> int:
        """
        Get the number of corrections since the last model training.
        
        This is a simplified implementation. In production, you would track
        the last training timestamp and count corrections after that.
        
        Returns:
            Number of corrections since last training
        """
        # For now, return total count
        # In production, filter by created_at > last_training_timestamp
        return self.get_corrections_count()
    
    def should_retrain(self) -> bool:
        """
        Check if the model should be retrained.
        
        Returns:
            True if retraining is recommended
        """
        corrections_count = self.get_corrections_since_last_training()
        return corrections_count >= self.min_corrections_for_retrain
    
    def get_training_data(self) -> List[Tuple[str, float, str, str]]:
        """
        Get training data from corrections.
        
        Returns:
            List of tuples (description, amount, category, type)
        """
        training_data = []
        
        # Query all corrections with their transactions
        corrections = self.db.query(ClassificationCorrection).join(
            Transaction,
            ClassificationCorrection.transaction_id == Transaction.id
        ).all()
        
        for correction in corrections:
            transaction = correction.transaction
            
            # Determine transaction type
            txn_type = 'income' if transaction.type.value == 'income' else 'expense'
            
            # Add to training data
            training_data.append((
                transaction.description or '',
                float(transaction.amount),
                correction.correct_category,
                txn_type
            ))
        
        return training_data
    
    def retrain_model(self) -> bool:
        """
        Retrain the ML model with correction data.
        
        Returns:
            True if retraining was successful, False otherwise
        """
        # Get training data
        training_data = self.get_training_data()
        
        if len(training_data) < self.ml_classifier.min_training_samples:
            return False
        
        # Train the model
        success = self.ml_classifier.train_model(training_data)
        
        return success
    
    def get_correction_stats(self) -> dict:
        """
        Get statistics about corrections.
        
        Returns:
            Dictionary with correction statistics
        """
        total_corrections = self.get_corrections_count()
        
        # Get most corrected categories
        from sqlalchemy import func
        most_corrected = self.db.query(
            ClassificationCorrection.original_category,
            func.count(ClassificationCorrection.id).label('count')
        ).group_by(
            ClassificationCorrection.original_category
        ).order_by(
            func.count(ClassificationCorrection.id).desc()
        ).limit(5).all()
        
        return {
            'total_corrections': total_corrections,
            'most_corrected_categories': [
                {'category': cat, 'count': count}
                for cat, count in most_corrected
            ],
            'should_retrain': self.should_retrain()
        }
    
    def auto_retrain_if_needed(self) -> dict:
        """
        Automatically retrain the model if enough corrections are available.
        
        Returns:
            Dictionary with retraining status
        """
        if not self.should_retrain():
            return {
                'retrained': False,
                'reason': 'Not enough corrections for retraining',
                'corrections_count': self.get_corrections_count(),
                'min_required': self.min_corrections_for_retrain
            }
        
        success = self.retrain_model()
        
        if success:
            return {
                'retrained': True,
                'corrections_count': self.get_corrections_count(),
                'message': 'Model retrained successfully'
            }
        else:
            return {
                'retrained': False,
                'reason': 'Retraining failed',
                'corrections_count': self.get_corrections_count()
            }
    
    def record_ocr_correction(
        self,
        document_id: int,
        previous_data: dict,
        corrected_data: dict,
        user_id: int
    ) -> bool:
        """
        Record OCR correction for learning.
        
        This stores OCR corrections to improve future OCR accuracy and
        field extraction. The data can be used to retrain OCR models or
        improve extraction patterns.
        
        Args:
            document_id: ID of the document
            previous_data: Original OCR extracted data
            corrected_data: User-corrected data
            user_id: ID of the user who made the correction
        
        Returns:
            True if correction was recorded successfully
        """
        from app.models.document import Document
        
        # Get the document
        document = self.db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            return False
        
        # Store OCR correction metadata in document
        ocr_result = document.ocr_result or {}
        
        if "learning_data" not in ocr_result:
            ocr_result["learning_data"] = []
        
        ocr_result["learning_data"].append({
            "corrected_by": user_id,
            "previous_data": previous_data,
            "corrected_data": corrected_data,
            "correction_timestamp": str(self.db.execute("SELECT NOW()").scalar())
        })
        
        document.ocr_result = ocr_result
        self.db.commit()
        
        return True
