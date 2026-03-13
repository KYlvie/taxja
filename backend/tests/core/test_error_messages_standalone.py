"""
Standalone unit tests for localized error messages module.

This test file can run independently without requiring database or app configuration.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from app.core.error_messages import (
    get_error_message,
    get_all_error_keys,
    get_error_dict,
    ERROR_MESSAGES,
)


def test_get_error_message_german():
    """Test retrieving error message in German."""
    message = get_error_message("duplicate_transaction", "de")
    assert message == "Diese Transaktion wurde bereits importiert. Duplikat verhindert."
    print("✓ German message retrieval works")


def test_get_error_message_english():
    """Test retrieving error message in English."""
    message = get_error_message("duplicate_transaction", "en")
    assert message == "This transaction was already imported. Duplicate prevented."
    print("✓ English message retrieval works")


def test_get_error_message_chinese():
    """Test retrieving error message in Chinese."""
    message = get_error_message("duplicate_transaction", "zh")
    assert message == "此交易已导入。已防止重复。"
    print("✓ Chinese message retrieval works")


def test_parameter_substitution():
    """Test error message with parameter substitution."""
    message = get_error_message("extraction_low_confidence", "en", confidence=65)
    assert "65" in message
    assert "low confidence" in message.lower()
    print("✓ Parameter substitution works")


def test_multiple_parameters():
    """Test error message with multiple parameters."""
    message = get_error_message(
        "invalid_tax_year", "de", year=2035, min_year=2015, max_year=2024
    )
    assert "2035" in message
    assert "2015" in message
    assert "2024" in message
    print("✓ Multiple parameter substitution works")


def test_all_error_keys_have_three_languages():
    """Test that all error messages have de, en, zh translations."""
    for key, translations in ERROR_MESSAGES.items():
        assert "de" in translations, f"Missing German translation for {key}"
        assert "en" in translations, f"Missing English translation for {key}"
        assert "zh" in translations, f"Missing Chinese translation for {key}"
    print(f"✓ All {len(ERROR_MESSAGES)} error keys have 3 language translations")


def test_error_categories_exist():
    """Test that error messages exist for all major categories."""
    categories = {
        "extraction": ["extraction_low_confidence", "ocr_failed", "parsing_error"],
        "validation": ["invalid_tax_year", "invalid_amount", "invalid_date"],
        "duplicate": ["duplicate_transaction", "conflict_detected"],
        "import": ["import_failed", "transaction_creation_failed"],
        "file": ["file_too_large", "file_type_not_supported"],
        "database": ["user_not_found", "upload_not_found"],
        "review": ["invalid_review_state", "approval_failed"],
        "saldenliste": ["saldenliste_parse_error", "unmapped_accounts"],
        "kaufvertrag": ["missing_purchase_price", "missing_purchase_date"],
        "e1": ["invalid_kz_code", "kz_extraction_incomplete"],
        "bescheid": ["address_matching_failed", "multiple_address_matches"],
    }
    
    for category, error_keys in categories.items():
        for error_key in error_keys:
            assert error_key in ERROR_MESSAGES, f"Missing {category} error: {error_key}"
    
    print(f"✓ All {len(categories)} error categories have required messages")


def test_get_all_error_keys():
    """Test that get_all_error_keys returns correct list."""
    keys = get_all_error_keys()
    assert isinstance(keys, list)
    assert len(keys) == len(ERROR_MESSAGES)
    assert set(keys) == set(ERROR_MESSAGES.keys())
    print(f"✓ get_all_error_keys returns {len(keys)} keys")


def test_get_error_dict():
    """Test get_error_dict function."""
    error_dict = get_error_dict("duplicate_transaction")
    assert error_dict is not None
    assert len(error_dict) == 3
    assert all(lang in error_dict for lang in ["de", "en", "zh"])
    
    # Test invalid key
    error_dict = get_error_dict("nonexistent_error")
    assert error_dict is None
    print("✓ get_error_dict works correctly")


def test_fallback_behavior():
    """Test fallback behavior for invalid inputs."""
    # Invalid language falls back to German
    message = get_error_message("duplicate_transaction", "fr")
    assert message == "Diese Transaktion wurde bereits importiert. Duplikat verhindert."
    
    # Invalid key returns unknown error
    message = get_error_message("nonexistent_error", "en")
    assert "unknown error" in message.lower()
    
    print("✓ Fallback behavior works correctly")


def test_real_world_scenarios():
    """Test real-world usage scenarios."""
    # Extraction workflow
    msg = get_error_message("extraction_low_confidence", "de", confidence=55)
    assert "55" in msg and "Konfidenz" in msg
    
    # Validation workflow
    msg = get_error_message("invalid_tax_year", "en", year=2050, min_year=2015, max_year=2024)
    assert all(str(y) in msg for y in [2050, 2015, 2024])
    
    # Saldenliste workflow
    msg = get_error_message("unmapped_accounts", "zh", count=3)
    assert "3" in msg
    
    # Conflict detection
    msg = get_error_message(
        "conflicting_amounts",
        "de",
        amount_1="10000",
        amount_2="11000",
        field_name="KZ 245",
        difference="10",
    )
    assert all(val in msg for val in ["10000", "11000", "KZ 245", "10"])
    
    print("✓ Real-world scenarios work correctly")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Running Error Messages Module Tests")
    print("="*60 + "\n")
    
    try:
        test_get_error_message_german()
        test_get_error_message_english()
        test_get_error_message_chinese()
        test_parameter_substitution()
        test_multiple_parameters()
        test_all_error_keys_have_three_languages()
        test_error_categories_exist()
        test_get_all_error_keys()
        test_get_error_dict()
        test_fallback_behavior()
        test_real_world_scenarios()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        sys.exit(1)
