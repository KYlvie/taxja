"""Machine learning-based transaction classifier using scikit-learn"""
from decimal import Decimal
from typing import List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import pickle
import os


class ClassificationResult:
    """Result of ML classification"""
    
    def __init__(
        self,
        category: Optional[str],
        confidence: Decimal,
        category_type: Optional[str] = None
    ):
        self.category = category
        self.confidence = confidence
        self.category_type = category_type
    
    def __repr__(self):
        return f"<ClassificationResult(category={self.category}, confidence={self.confidence})>"


class MLClassifier:
    """
    Machine learning classifier for transaction categorization.
    
    Uses TF-IDF for text features and RandomForest for classification.
    Handles both income and expense categories with separate models.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize ML classifier.
        
        Args:
            model_path: Path to load/save trained models
        """
        self.model_path = model_path or "models"
        self.income_model = None
        self.expense_model = None
        self.income_vectorizer = None
        self.expense_vectorizer = None
        self.amount_scaler = StandardScaler()
        self.min_training_samples = 10  # Minimum samples needed to train
        
        # Try to load existing models
        self._load_models()
    
    def classify(self, transaction, user_context=None) -> ClassificationResult:
        """
        Classify a transaction using ML model.
        
        Args:
            transaction: Transaction object with description and amount
            user_context: Optional user context (not used in current implementation)
        
        Returns:
            ClassificationResult with predicted category and confidence
        """
        if not transaction.description:
            return ClassificationResult(None, Decimal('0.0'))
        
        transaction_type = str(transaction.type).lower() if hasattr(transaction.type, 'value') else str(transaction.type).lower()
        
        if 'income' in transaction_type:
            return self._classify_income(transaction)
        else:
            return self._classify_expense(transaction)
    
    def _classify_income(self, transaction) -> ClassificationResult:
        """Classify income transaction"""
        if self.income_model is None or self.income_vectorizer is None:
            # Model not trained yet, return low confidence default
            return ClassificationResult(
                category='employment',
                confidence=Decimal('0.3'),
                category_type='income'
            )
        
        try:
            # Extract features
            features = self._extract_features(
                transaction.description,
                float(transaction.amount),
                self.income_vectorizer
            )
            
            # Predict
            prediction = self.income_model.predict(features)[0]
            probabilities = self.income_model.predict_proba(features)[0]
            confidence = float(max(probabilities))
            
            return ClassificationResult(
                category=prediction,
                confidence=Decimal(str(round(confidence, 2))),
                category_type='income'
            )
        except Exception as e:
            # If prediction fails, return low confidence default
            return ClassificationResult(
                category='employment',
                confidence=Decimal('0.3'),
                category_type='income'
            )
    
    def _classify_expense(self, transaction) -> ClassificationResult:
        """Classify expense transaction"""
        if self.expense_model is None or self.expense_vectorizer is None:
            # Model not trained yet, return low confidence default
            return ClassificationResult(
                category='other',
                confidence=Decimal('0.3'),
                category_type='expense'
            )
        
        try:
            # Extract features
            features = self._extract_features(
                transaction.description,
                float(transaction.amount),
                self.expense_vectorizer
            )
            
            # Predict
            prediction = self.expense_model.predict(features)[0]
            probabilities = self.expense_model.predict_proba(features)[0]
            confidence = float(max(probabilities))
            
            return ClassificationResult(
                category=prediction,
                confidence=Decimal(str(round(confidence, 2))),
                category_type='expense'
            )
        except Exception as e:
            # If prediction fails, return low confidence default
            return ClassificationResult(
                category='other',
                confidence=Decimal('0.3'),
                category_type='expense'
            )
    
    def _extract_features(
        self,
        description: str,
        amount: float,
        vectorizer: TfidfVectorizer
    ) -> np.ndarray:
        """
        Extract features from transaction.
        
        Combines TF-IDF text features with normalized amount.
        
        Args:
            description: Transaction description
            amount: Transaction amount
            vectorizer: Fitted TF-IDF vectorizer
        
        Returns:
            Feature vector as numpy array
        """
        # Text features using TF-IDF
        text_features = vectorizer.transform([description.lower()]).toarray()
        
        # Amount feature (normalized)
        amount_feature = np.array([[amount]])
        amount_normalized = self.amount_scaler.transform(amount_feature)
        
        # Combine features
        features = np.hstack([text_features, amount_normalized])
        
        return features
    
    def train_model(
        self,
        transactions: List[Tuple[str, float, str, str]]
    ) -> bool:
        """
        Train classification models on transaction data.
        
        Args:
            transactions: List of tuples (description, amount, category, type)
                         where type is 'income' or 'expense'
        
        Returns:
            True if training successful, False otherwise
        """
        if len(transactions) < self.min_training_samples:
            return False
        
        # Separate income and expense transactions
        income_data = [(desc, amt, cat) for desc, amt, cat, typ in transactions if typ == 'income']
        expense_data = [(desc, amt, cat) for desc, amt, cat, typ in transactions if typ == 'expense']
        
        # Train income model if enough data
        if len(income_data) >= self.min_training_samples:
            self._train_income_model(income_data)
        
        # Train expense model if enough data
        if len(expense_data) >= self.min_training_samples:
            self._train_expense_model(expense_data)
        
        # Save models
        self._save_models()
        
        return True
    
    def _train_income_model(self, data: List[Tuple[str, float, str]]):
        """Train income classification model"""
        descriptions = [desc.lower() for desc, _, _ in data]
        amounts = np.array([[amt] for _, amt, _ in data])
        categories = [cat for _, _, cat in data]
        
        # Fit TF-IDF vectorizer
        self.income_vectorizer = TfidfVectorizer(
            max_features=100,
            ngram_range=(1, 2),
            min_df=1
        )
        text_features = self.income_vectorizer.fit_transform(descriptions).toarray()
        
        # Fit amount scaler
        self.amount_scaler.fit(amounts)
        amount_features = self.amount_scaler.transform(amounts)
        
        # Combine features
        X = np.hstack([text_features, amount_features])
        y = categories
        
        # Train RandomForest classifier
        self.income_model = RandomForestClassifier(
            n_estimators=50,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        )
        self.income_model.fit(X, y)
    
    def _train_expense_model(self, data: List[Tuple[str, float, str]]):
        """Train expense classification model"""
        descriptions = [desc.lower() for desc, _, _ in data]
        amounts = np.array([[amt] for _, amt, _ in data])
        categories = [cat for _, _, cat in data]
        
        # Fit TF-IDF vectorizer
        self.expense_vectorizer = TfidfVectorizer(
            max_features=100,
            ngram_range=(1, 2),
            min_df=1
        )
        text_features = self.expense_vectorizer.fit_transform(descriptions).toarray()
        
        # Fit amount scaler (reuse the same scaler)
        if not hasattr(self.amount_scaler, 'mean_'):
            self.amount_scaler.fit(amounts)
        amount_features = self.amount_scaler.transform(amounts)
        
        # Combine features
        X = np.hstack([text_features, amount_features])
        y = categories
        
        # Train RandomForest classifier
        self.expense_model = RandomForestClassifier(
            n_estimators=50,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        )
        self.expense_model.fit(X, y)
    
    def update_model(self, new_data: List[Tuple[str, float, str, str]]):
        """
        Update models with new training data.
        
        This is a simplified implementation that retrains from scratch.
        In production, consider incremental learning approaches.
        
        Args:
            new_data: List of tuples (description, amount, category, type)
        """
        # For now, just retrain with new data
        # In production, you might want to combine with existing training data
        self.train_model(new_data)
    
    def should_retrain(self) -> bool:
        """
        Check if model should be retrained.
        
        This is a placeholder for more sophisticated logic.
        Could check:
        - Number of corrections since last training
        - Model age
        - Performance metrics
        
        Returns:
            True if retraining recommended
        """
        # Simple heuristic: always allow retraining if requested
        return True
    
    def add_training_example(self, transaction, correct_category: str, user_id: int):
        """
        Add a single training example from user correction.
        
        This stores the correction for future batch retraining.
        In production, you'd store this in a database.
        
        Args:
            transaction: Transaction object
            correct_category: Correct category from user
            user_id: User who made the correction
        """
        # This is a placeholder - in production, store in database
        # For now, we'll just note that this would be stored
        pass
    
    def _save_models(self):
        """Save trained models to disk"""
        os.makedirs(self.model_path, exist_ok=True)
        
        if self.income_model is not None:
            with open(os.path.join(self.model_path, 'income_model.pkl'), 'wb') as f:
                pickle.dump(self.income_model, f)
        
        if self.income_vectorizer is not None:
            with open(os.path.join(self.model_path, 'income_vectorizer.pkl'), 'wb') as f:
                pickle.dump(self.income_vectorizer, f)
        
        if self.expense_model is not None:
            with open(os.path.join(self.model_path, 'expense_model.pkl'), 'wb') as f:
                pickle.dump(self.expense_model, f)
        
        if self.expense_vectorizer is not None:
            with open(os.path.join(self.model_path, 'expense_vectorizer.pkl'), 'wb') as f:
                pickle.dump(self.expense_vectorizer, f)
        
        # Save scaler
        with open(os.path.join(self.model_path, 'amount_scaler.pkl'), 'wb') as f:
            pickle.dump(self.amount_scaler, f)
    
    def _load_models(self):
        """Load trained models from disk"""
        try:
            income_model_path = os.path.join(self.model_path, 'income_model.pkl')
            if os.path.exists(income_model_path):
                with open(income_model_path, 'rb') as f:
                    self.income_model = pickle.load(f)
            
            income_vectorizer_path = os.path.join(self.model_path, 'income_vectorizer.pkl')
            if os.path.exists(income_vectorizer_path):
                with open(income_vectorizer_path, 'rb') as f:
                    self.income_vectorizer = pickle.load(f)
            
            expense_model_path = os.path.join(self.model_path, 'expense_model.pkl')
            if os.path.exists(expense_model_path):
                with open(expense_model_path, 'rb') as f:
                    self.expense_model = pickle.load(f)
            
            expense_vectorizer_path = os.path.join(self.model_path, 'expense_vectorizer.pkl')
            if os.path.exists(expense_vectorizer_path):
                with open(expense_vectorizer_path, 'rb') as f:
                    self.expense_vectorizer = pickle.load(f)
            
            scaler_path = os.path.join(self.model_path, 'amount_scaler.pkl')
            if os.path.exists(scaler_path):
                with open(scaler_path, 'rb') as f:
                    self.amount_scaler = pickle.load(f)
        except Exception as e:
            # If loading fails, start with fresh models
            pass
    
    def get_confidence_score(self, transaction) -> Decimal:
        """Get confidence score for transaction classification"""
        result = self.classify(transaction)
        return result.confidence
