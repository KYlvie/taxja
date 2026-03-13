"""
Unit tests for localized error messages module.

Tests verify:
- Error message retrieval in all supported languages
- Parameter substitution
- Fallback behavior for invalid keys/languages
- All error keys are properly defined
"""

import pytest
from app.core.error_messages import (
    get_error_message,
    get_all_error_keys,
    get_error_dict,
    ERROR_MESSAGES,
)


class TestGetErrorMessage:
    """Test get_error_message function."""

    def test_get_error_message_german(self):
        """Test retrieving error message in German."""
        message = get_error_message("duplicate_transaction", "de")
        assert message == "Diese Transaktion wurde bereits importiert. Duplikat verhindert."

    def test_get_error_message_english(self):
        """Test retrieving error message in English."""
        message = get_error_message("duplicate_transaction", "en")
        assert message == "This transaction was already imported. Duplicate prevented."

    def test_get_error_message_chinese(self):
        """Test retrieving error message in Chinese."""
        message = get_error_message("duplicate_transaction", "zh")
        assert message == "此交易已导入。已防止重复。"

    def test_get_error_message_default_language(self):
        """Test that German is the default language."""
        message = get_error_message("duplicate_transaction")
        assert message == "Diese Transaktion wurde bereits importiert. Duplikat verhindert."

    def test_get_error_message_invalid_language(self):
        """Test that invalid language falls back to German."""
        message = get_error_message("duplicate_transaction", "fr")
        assert message == "Diese Transaktion wurde bereits importiert. Duplikat verhindert."

    def test_get_error_message_with_parameters(self):
        """Test error message with parameter substitution."""
        message = get_error_message(
            "extraction_low_confidence", "en", confidence=65
        )
        assert message == "Data extraction had low confidence (65%). Please review the extracted data manually."

    def test_get_error_message_with_multiple_parameters(self):
        """Test error message with multiple parameters."""
        message = get_error_message(
            "invalid_tax_year", "de", year=2035, min_year=2015, max_year=2024
        )
        assert message == "Ungültiges Steuerjahr: 2035. Muss zwischen 2015 und 2024 liegen."

    def test_get_error_message_invalid_key(self):
        """Test that invalid key returns unknown error message."""
        message = get_error_message("nonexistent_error", "en")
        assert "unknown error" in message.lower()

    def test_get_error_message_missing_parameter(self):
        """Test error message with missing parameter."""
        message = get_error_message("extraction_low_confidence", "en")
        # Should return template with error note about missing parameter
        assert "confidence" in message or "Missing parameter" in message


class TestParameterSubstitution:
    """Test parameter substitution in various error messages."""

    def test_extraction_low_confidence_parameters(self):
        """Test extraction_low_confidence with confidence parameter."""
        for lang in ["de", "en", "zh"]:
            message = get_error_message("extraction_low_confidence", lang, confidence=72)
            assert "72" in message

    def test_invalid_tax_year_parameters(self):
        """Test invalid_tax_year with year and range parameters."""
        message = get_error_message(
            "invalid_tax_year", "en", year=2040, min_year=2015, max_year=2024
        )
        assert "2040" in message
        assert "2015" in message
        assert "2024" in message

    def test_conflicting_amounts_parameters(self):
        """Test conflicting_amounts with multiple parameters."""
        message = get_error_message(
            "conflicting_amounts",
            "de",
            amount_1="10000",
            amount_2="11000",
            field_name="KZ 245",
            difference="10",
        )
        assert "10000" in message
        assert "11000" in message
        assert "KZ 245" in message
        assert "10" in message

    def test_file_too_large_parameters(self):
        """Test file_too_large with size parameters."""
        message = get_error_message("file_too_large", "en", size=75, max_size=50)
        assert "75" in message
        assert "50" in message

    def test_unmapped_accounts_parameters(self):
        """Test unmapped_accounts with count parameter."""
        message = get_error_message("unmapped_accounts", "zh", count=5)
        assert "5" in message


class TestAllErrorKeys:
    """Test that all error keys are properly defined."""

    def test_all_error_keys_have_three_languages(self):
        """Test that all error messages have de, en, zh translations."""
        for key, translations in ERROR_MESSAGES.items():
            assert "de" in translations, f"Missing German translation for {key}"
            assert "en" in translations, f"Missing English translation for {key}"
            assert "zh" in translations, f"Missing Chinese translation for {key}"

    def test_all_error_keys_non_empty(self):
        """Test that all error messages are non-empty strings."""
        for key, translations in ERROR_MESSAGES.items():
            for lang, message in translations.items():
                assert isinstance(message, str), f"{key}.{lang} is not a string"
                assert len(message) > 0, f"{key}.{lang} is empty"

    def test_get_all_error_keys_returns_list(self):
        """Test that get_all_error_keys returns a list."""
        keys = get_all_error_keys()
        assert isinstance(keys, list)
        assert len(keys) > 0

    def test_get_all_error_keys_matches_dict(self):
        """Test that get_all_error_keys matches ERROR_MESSAGES keys."""
        keys = get_all_error_keys()
        assert set(keys) == set(ERROR_MESSAGES.keys())


class TestGetErrorDict:
    """Test get_error_dict function."""

    def test_get_error_dict_valid_key(self):
        """Test retrieving error dict for valid key."""
        error_dict = get_error_dict("duplicate_transaction")
        assert error_dict is not None
        assert "de" in error_dict
        assert "en" in error_dict
        assert "zh" in error_dict

    def test_get_error_dict_invalid_key(self):
        """Test retrieving error dict for invalid key."""
        error_dict = get_error_dict("nonexistent_error")
        assert error_dict is None

    def test_get_error_dict_returns_all_languages(self):
        """Test that get_error_dict returns all language translations."""
        error_dict = get_error_dict("extraction_low_confidence")
        assert len(error_dict) == 3
        assert all(lang in error_dict for lang in ["de", "en", "zh"])


class TestErrorMessageCategories:
    """Test that error messages exist for all major categories."""

    def test_extraction_errors_exist(self):
        """Test that extraction error messages exist."""
        extraction_errors = [
            "extraction_low_confidence",
            "extraction_failed",
            "ocr_failed",
            "ocr_timeout",
            "parsing_error",
            "missing_required_field",
            "invalid_document_format",
        ]
        for error_key in extraction_errors:
            assert error_key in ERROR_MESSAGES, f"Missing extraction error: {error_key}"

    def test_validation_errors_exist(self):
        """Test that validation error messages exist."""
        validation_errors = [
            "invalid_tax_year",
            "tax_year_future",
            "tax_year_too_old",
            "invalid_amount",
            "invalid_date",
            "invalid_category",
            "amount_exceeds_limit",
            "negative_amount_not_allowed",
        ]
        for error_key in validation_errors:
            assert error_key in ERROR_MESSAGES, f"Missing validation error: {error_key}"

    def test_duplicate_conflict_errors_exist(self):
        """Test that duplicate and conflict error messages exist."""
        duplicate_errors = [
            "duplicate_transaction",
            "duplicate_transaction_detected",
            "conflict_detected",
            "conflicting_amounts",
            "duplicate_property",
        ]
        for error_key in duplicate_errors:
            assert error_key in ERROR_MESSAGES, f"Missing duplicate/conflict error: {error_key}"

    def test_import_errors_exist(self):
        """Test that import error messages exist."""
        import_errors = [
            "import_failed",
            "transaction_creation_failed",
            "property_creation_failed",
            "property_linking_failed",
            "depreciation_schedule_failed",
        ]
        for error_key in import_errors:
            assert error_key in ERROR_MESSAGES, f"Missing import error: {error_key}"

    def test_file_errors_exist(self):
        """Test that file error messages exist."""
        file_errors = [
            "file_too_large",
            "file_type_not_supported",
            "file_corrupted",
            "file_not_found",
        ]
        for error_key in file_errors:
            assert error_key in ERROR_MESSAGES, f"Missing file error: {error_key}"

    def test_database_errors_exist(self):
        """Test that database error messages exist."""
        database_errors = [
            "user_not_found",
            "upload_not_found",
            "session_not_found",
            "property_not_found",
            "database_error",
        ]
        for error_key in database_errors:
            assert error_key in ERROR_MESSAGES, f"Missing database error: {error_key}"

    def test_review_errors_exist(self):
        """Test that review and approval error messages exist."""
        review_errors = [
            "invalid_review_state",
            "approval_failed",
            "rejection_failed",
            "finalization_failed",
        ]
        for error_key in review_errors:
            assert error_key in ERROR_MESSAGES, f"Missing review error: {error_key}"

    def test_saldenliste_errors_exist(self):
        """Test that Saldenliste-specific error messages exist."""
        saldenliste_errors = [
            "saldenliste_parse_error",
            "unmapped_accounts",
            "account_mapping_failed",
            "balance_mismatch",
            "continuity_check_failed",
        ]
        for error_key in saldenliste_errors:
            assert error_key in ERROR_MESSAGES, f"Missing Saldenliste error: {error_key}"

    def test_kaufvertrag_errors_exist(self):
        """Test that Kaufvertrag-specific error messages exist."""
        kaufvertrag_errors = [
            "missing_purchase_price",
            "missing_purchase_date",
            "missing_property_address",
            "invalid_building_value",
        ]
        for error_key in kaufvertrag_errors:
            assert error_key in ERROR_MESSAGES, f"Missing Kaufvertrag error: {error_key}"

    def test_e1_errors_exist(self):
        """Test that E1 Form-specific error messages exist."""
        e1_errors = [
            "invalid_kz_code",
            "kz_extraction_incomplete",
        ]
        for error_key in e1_errors:
            assert error_key in ERROR_MESSAGES, f"Missing E1 error: {error_key}"

    def test_bescheid_errors_exist(self):
        """Test that Bescheid-specific error messages exist."""
        bescheid_errors = [
            "address_matching_failed",
            "multiple_address_matches",
        ]
        for error_key in bescheid_errors:
            assert error_key in ERROR_MESSAGES, f"Missing Bescheid error: {error_key}"

    def test_session_errors_exist(self):
        """Test that session error messages exist."""
        session_errors = [
            "session_already_completed",
            "session_failed",
        ]
        for error_key in session_errors:
            assert error_key in ERROR_MESSAGES, f"Missing session error: {error_key}"

    def test_generic_errors_exist(self):
        """Test that generic error messages exist."""
        generic_errors = [
            "unknown_error",
            "operation_timeout",
            "permission_denied",
        ]
        for error_key in generic_errors:
            assert error_key in ERROR_MESSAGES, f"Missing generic error: {error_key}"


class TestErrorMessageConsistency:
    """Test consistency across language translations."""

    def test_parameter_placeholders_consistent(self):
        """Test that parameter placeholders are consistent across languages."""
        import re

        for key, translations in ERROR_MESSAGES.items():
            # Extract placeholders from each language
            placeholders_by_lang = {}
            for lang, message in translations.items():
                # Find all {parameter} placeholders
                placeholders = set(re.findall(r"\{(\w+)\}", message))
                placeholders_by_lang[lang] = placeholders

            # Check that all languages have the same placeholders
            de_placeholders = placeholders_by_lang.get("de", set())
            en_placeholders = placeholders_by_lang.get("en", set())
            zh_placeholders = placeholders_by_lang.get("zh", set())

            assert de_placeholders == en_placeholders == zh_placeholders, (
                f"Inconsistent placeholders for {key}: "
                f"de={de_placeholders}, en={en_placeholders}, zh={zh_placeholders}"
            )


class TestRealWorldUsage:
    """Test real-world usage scenarios."""

    def test_extraction_workflow_errors(self):
        """Test error messages for extraction workflow."""
        # Low confidence extraction
        msg = get_error_message("extraction_low_confidence", "de", confidence=55)
        assert "55" in msg
        assert "Konfidenz" in msg

        # OCR failed
        msg = get_error_message("ocr_failed", "en")
        assert "OCR" in msg
        assert "failed" in msg.lower()

        # Missing required field
        msg = get_error_message("missing_required_field", "zh", field_name="purchase_price")
        assert "purchase_price" in msg

    def test_validation_workflow_errors(self):
        """Test error messages for validation workflow."""
        # Invalid tax year
        msg = get_error_message(
            "invalid_tax_year", "de", year=2050, min_year=2015, max_year=2024
        )
        assert "2050" in msg
        assert "2015" in msg
        assert "2024" in msg

        # Invalid amount
        msg = get_error_message("invalid_amount", "en", amount="-1000")
        assert "-1000" in msg

    def test_import_workflow_errors(self):
        """Test error messages for import workflow."""
        # Transaction creation failed
        msg = get_error_message(
            "transaction_creation_failed", "de", error="Database constraint violation"
        )
        assert "Database constraint violation" in msg

        # Property linking failed
        msg = get_error_message(
            "property_linking_failed", "en", error="Property not found"
        )
        assert "Property not found" in msg

    def test_saldenliste_workflow_errors(self):
        """Test error messages for Saldenliste workflow."""
        # Unmapped accounts
        msg = get_error_message("unmapped_accounts", "de", count=3)
        assert "3" in msg

        # Balance mismatch
        msg = get_error_message(
            "balance_mismatch",
            "en",
            debit="100000",
            credit="99500",
            difference="500",
        )
        assert "100000" in msg
        assert "99500" in msg
        assert "500" in msg

        # Continuity check failed
        msg = get_error_message(
            "continuity_check_failed",
            "zh",
            year=2022,
            closing_balance="50000",
            next_year=2023,
            opening_balance="51000",
        )
        assert "2022" in msg
        assert "2023" in msg
        assert "50000" in msg
        assert "51000" in msg
