"""
Demonstration of MLClassifier usage

This script shows how to:
1. Train the MLClassifier with sample data
2. Use it to classify transactions
3. Compare with RuleBasedClassifier
"""
from decimal import Decimal
from app.services.ml_classifier import MLClassifier
from app.services.rule_based_classifier import RuleBasedClassifier


class MockTransaction:
    """Mock transaction for demonstration"""
    def __init__(self, description: str, amount: Decimal, transaction_type: str):
        self.description = description
        self.amount = amount
        self.type = transaction_type


def main():
    print("=" * 80)
    print("MLClassifier Demonstration")
    print("=" * 80)
    
    # Initialize classifiers
    ml_classifier = MLClassifier(model_path="demo_models")
    rule_classifier = RuleBasedClassifier()
    
    # Prepare training data
    print("\n1. Preparing training data...")
    training_data = [
        # Income samples
        ("Monthly salary payment", 3000.0, "employment", "income"),
        ("Salary for December", 3200.0, "employment", "income"),
        ("Wage payment", 2800.0, "employment", "income"),
        ("Gehalt Januar", 3100.0, "employment", "income"),
        ("Rent from tenant apartment 1", 800.0, "rental", "income"),
        ("Rental income property", 850.0, "rental", "income"),
        ("Miete Wohnung", 900.0, "rental", "income"),
        ("Freelance consulting invoice", 1500.0, "self_employment", "income"),
        ("Project payment client A", 2000.0, "self_employment", "income"),
        ("Honorar Beratung", 1800.0, "self_employment", "income"),
        ("Dividend from stocks", 500.0, "capital_gains", "income"),
        ("Interest income savings", 50.0, "capital_gains", "income"),
        ("Zinsen Sparkonto", 75.0, "capital_gains", "income"),
        
        # Expense samples
        ("BILLA supermarket Vienna", 45.0, "groceries", "expense"),
        ("SPAR shopping center", 60.0, "groceries", "expense"),
        ("HOFER discount store", 35.0, "groceries", "expense"),
        ("LIDL groceries", 40.0, "groceries", "expense"),
        ("MERKUR market", 55.0, "groceries", "expense"),
        ("OBI hardware store materials", 120.0, "maintenance", "expense"),
        ("Baumax building supplies", 85.0, "maintenance", "expense"),
        ("Repair materials hardware", 95.0, "maintenance", "expense"),
        ("Reparatur Werkzeug", 110.0, "maintenance", "expense"),
        ("Office paper and supplies", 30.0, "office_supplies", "expense"),
        ("Printer ink cartridges", 45.0, "office_supplies", "expense"),
        ("Stationery items", 25.0, "office_supplies", "expense"),
        ("Büromaterial Libro", 35.0, "office_supplies", "expense"),
        ("Business trip hotel Vienna", 150.0, "travel", "expense"),
        ("Flight ticket business", 200.0, "travel", "expense"),
        ("Train ticket ÖBB", 80.0, "travel", "expense"),
        ("Reisekosten Hotel", 140.0, "travel", "expense"),
        ("Insurance premium property", 100.0, "insurance", "expense"),
        ("Versicherung Gebäude", 120.0, "insurance", "expense"),
    ]
    
    print(f"   Training data: {len(training_data)} samples")
    
    # Train the model
    print("\n2. Training ML model...")
    success = ml_classifier.train_model(training_data)
    if success:
        print("   ✓ Model trained successfully")
    else:
        print("   ✗ Training failed (insufficient data)")
        return
    
    # Test transactions
    test_transactions = [
        MockTransaction("BILLA Wien Hauptbahnhof", Decimal("52.30"), "expense"),
        MockTransaction("Salary payment March", Decimal("3150.00"), "income"),
        MockTransaction("OBI Baumarkt Linz", Decimal("145.00"), "expense"),
        MockTransaction("Freelance project XYZ", Decimal("1750.00"), "income"),
        MockTransaction("SPAR Graz", Decimal("38.50"), "expense"),
        MockTransaction("Miete Wohnung 2", Decimal("820.00"), "income"),
    ]
    
    print("\n3. Classifying test transactions...")
    print("\n" + "-" * 80)
    print(f"{'Description':<40} {'Amount':>10} {'Rule-Based':<20} {'ML-Based':<20}")
    print("-" * 80)
    
    for txn in test_transactions:
        # Classify with both methods
        rule_result = rule_classifier.classify(txn)
        ml_result = ml_classifier.classify(txn)
        
        # Format results
        rule_str = f"{rule_result.category} ({rule_result.confidence})"
        ml_str = f"{ml_result.category} ({ml_result.confidence})"
        
        print(f"{txn.description:<40} €{txn.amount:>8} {rule_str:<20} {ml_str:<20}")
    
    print("-" * 80)
    
    # Show comparison
    print("\n4. Comparison Summary:")
    print("   - Rule-Based Classifier: Fast, deterministic, requires manual rules")
    print("   - ML Classifier: Learns from data, adapts to patterns, requires training")
    print("   - Hybrid Approach: Use rule-based for high confidence, ML for uncertain cases")
    
    print("\n5. Key Features of MLClassifier:")
    print("   ✓ Extracts features from description (TF-IDF) and amount")
    print("   ✓ Uses RandomForest for robust classification")
    print("   ✓ Separate models for income and expense categories")
    print("   ✓ Returns confidence scores for each prediction")
    print("   ✓ Handles limited training data gracefully")
    print("   ✓ Can be retrained with user corrections")
    
    print("\n" + "=" * 80)
    print("Demo completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
