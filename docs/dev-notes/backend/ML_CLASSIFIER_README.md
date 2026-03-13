# MLClassifier - Machine Learning Transaction Classifier

## Overview

The `MLClassifier` is a machine learning-based transaction classifier that uses scikit-learn to automatically categorize income and expense transactions. It complements the `RuleBasedClassifier` by learning from historical transaction data and user corrections.

## Features

### Core Capabilities

1. **Feature Extraction**
   - **Text Features**: Uses TF-IDF (Term Frequency-Inverse Document Frequency) to extract meaningful features from transaction descriptions
   - **Amount Features**: Normalizes transaction amounts using StandardScaler to capture spending patterns
   - **Combined Features**: Merges text and amount features for comprehensive classification

2. **Dual Model Architecture**
   - **Income Model**: Separate RandomForest classifier for income categories (employment, rental, self_employment, capital_gains)
   - **Expense Model**: Separate RandomForest classifier for expense categories (groceries, maintenance, office_supplies, travel, etc.)
   - **Independent Training**: Each model is trained on its respective transaction type

3. **Confidence Scoring**
   - Returns probability-based confidence scores (0.0 to 1.0)
   - Helps identify uncertain classifications that need review
   - Enables hybrid approach with rule-based classifier

4. **Graceful Degradation**
   - Returns low-confidence defaults when untrained
   - Handles empty descriptions safely
   - Requires minimum 10 samples per type to train

5. **Model Persistence**
   - Saves trained models to disk using pickle
   - Automatically loads existing models on initialization
   - Supports model updates and retraining

## Architecture

```
MLClassifier
├── Income Model (RandomForest)
│   ├── TF-IDF Vectorizer (text features)
│   ├── StandardScaler (amount features)
│   └── Categories: employment, rental, self_employment, capital_gains
│
└── Expense Model (RandomForest)
    ├── TF-IDF Vectorizer (text features)
    ├── StandardScaler (amount features)
    └── Categories: groceries, maintenance, office_supplies, travel, etc.
```

## Usage

### Basic Classification

```python
from app.services.ml_classifier import MLClassifier
from decimal import Decimal

# Initialize classifier
classifier = MLClassifier(model_path="models")

# Create a transaction
class Transaction:
    def __init__(self, description, amount, type):
        self.description = description
        self.amount = amount
        self.type = type

transaction = Transaction("BILLA supermarket", Decimal("45.50"), "expense")

# Classify
result = classifier.classify(transaction)
print(f"Category: {result.category}")
print(f"Confidence: {result.confidence}")
print(f"Type: {result.category_type}")
```

### Training the Model

```python
# Prepare training data
# Format: (description, amount, category, type)
training_data = [
    ("Monthly salary", 3000.0, "employment", "income"),
    ("Rent from tenant", 800.0, "rental", "income"),
    ("BILLA shopping", 45.0, "groceries", "expense"),
    ("OBI hardware", 120.0, "maintenance", "expense"),
    # ... more samples (minimum 10 per type)
]

# Train the model
success = classifier.train_model(training_data)
if success:
    print("Model trained successfully")
else:
    print("Insufficient training data")
```

### Hybrid Approach with RuleBasedClassifier

```python
from app.services.rule_based_classifier import RuleBasedClassifier
from app.services.ml_classifier import MLClassifier

rule_classifier = RuleBasedClassifier()
ml_classifier = MLClassifier()

def classify_transaction(transaction):
    # Try rule-based first
    rule_result = rule_classifier.classify(transaction)
    
    # If high confidence, use rule-based result
    if rule_result.confidence > 0.8:
        return rule_result
    
    # Otherwise, use ML classifier
    ml_result = ml_classifier.classify(transaction)
    
    # Return the result with higher confidence
    if ml_result.confidence > rule_result.confidence:
        return ml_result
    else:
        return rule_result
```

## Implementation Details

### Feature Extraction

The classifier extracts two types of features:

1. **Text Features (TF-IDF)**
   - Converts transaction descriptions to numerical vectors
   - Captures word importance and frequency
   - Uses 1-gram and 2-gram combinations
   - Limited to top 100 features for efficiency

2. **Amount Features**
   - Normalizes amounts using StandardScaler
   - Helps distinguish between high-value and low-value transactions
   - Example: Equipment purchases typically have higher amounts than groceries

### Model Configuration

**RandomForest Parameters:**
- `n_estimators=50`: 50 decision trees in the forest
- `max_depth=10`: Maximum tree depth to prevent overfitting
- `min_samples_split=5`: Minimum samples required to split a node
- `random_state=42`: Fixed seed for reproducibility

**TF-IDF Parameters:**
- `max_features=100`: Limit to top 100 features
- `ngram_range=(1, 2)`: Use both single words and word pairs
- `min_df=1`: Include all terms (even if they appear once)

### Training Requirements

- **Minimum Samples**: 10 transactions per type (income/expense)
- **Recommended**: 50+ samples per category for better accuracy
- **Data Quality**: Clean, descriptive transaction descriptions improve performance

## Performance Characteristics

### Strengths

1. **Adaptability**: Learns from user's specific transaction patterns
2. **Generalization**: Can classify new merchants not in rule-based patterns
3. **Continuous Improvement**: Can be retrained with user corrections
4. **Context-Aware**: Considers both description and amount

### Limitations

1. **Training Data Required**: Needs minimum 10 samples to train
2. **Cold Start**: Returns low confidence when untrained
3. **Computational Cost**: Slower than rule-based (but still fast)
4. **Model Size**: Requires disk space for saved models

### Typical Confidence Scores

- **High Confidence (>0.7)**: Strong match with training patterns
- **Medium Confidence (0.4-0.7)**: Reasonable match, may need review
- **Low Confidence (<0.4)**: Uncertain, should be reviewed by user

## Integration with Transaction Classifier

The MLClassifier is designed to work alongside the RuleBasedClassifier in a hybrid approach:

```python
class TransactionClassifier:
    def __init__(self):
        self.rule_classifier = RuleBasedClassifier()
        self.ml_classifier = MLClassifier()
    
    def classify_transaction(self, transaction, user_context):
        # 1. Try rule-based classification
        rule_result = self.rule_classifier.classify(transaction)
        
        # 2. If high confidence, use it
        if rule_result.confidence > 0.8:
            return rule_result
        
        # 3. Otherwise, try ML classification
        ml_result = self.ml_classifier.classify(transaction, user_context)
        
        # 4. Return the better result
        if ml_result.confidence > rule_result.confidence:
            return ml_result
        else:
            return rule_result
```

## Future Enhancements

1. **Incremental Learning**: Update models without full retraining
2. **User-Specific Models**: Train separate models per user
3. **Deep Learning**: Explore neural networks for better text understanding
4. **Multi-Language Support**: Better handling of German/English mixed descriptions
5. **Active Learning**: Intelligently select transactions for user review
6. **Feature Engineering**: Add more features (day of week, merchant location, etc.)

## Testing

Run the test suite:

```bash
pytest backend/tests/test_ml_classifier.py -v
```

Run the demonstration:

```bash
cd backend
python ml_classifier_demo.py
```

## Requirements

- Python 3.11+
- scikit-learn 1.4.0+
- numpy
- scipy

All dependencies are included in `requirements.txt`.

## Model Files

Trained models are saved in the specified `model_path` directory:

```
models/
├── income_model.pkl          # Income RandomForest model
├── income_vectorizer.pkl     # Income TF-IDF vectorizer
├── expense_model.pkl         # Expense RandomForest model
├── expense_vectorizer.pkl    # Expense TF-IDF vectorizer
└── amount_scaler.pkl         # Amount StandardScaler
```

## References

- **Requirements**: 2.1, 2.2, 2.3 (Automatic transaction classification)
- **Design Document**: Section 2.3 (Transaction Classifier)
- **Task**: 9.2 (Implement MLClassifier with scikit-learn)
