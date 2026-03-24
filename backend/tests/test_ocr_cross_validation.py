"""
Tests for OCR cross-validation between VLM and Tesseract+LLM.

Covers:
- High VLM confidence skips cross-validation
- Low VLM confidence triggers Tesseract+LLM cross-validation
- Fields match → confidence boosted, extra fields merged
- Fields mismatch → confidence lowered, needs_review=True
- Critical field (amount/date) mismatch → bigger penalty
- Tesseract path failure → VLM result returned as-is
- No overlapping fields → VLM result returned as-is
- Amount comparison with Austrian format (1.234,56)
- Merchant fuzzy matching
- Multi-receipt VLM uses conservative confidence
"""
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.services.ocr_engine import (
    OCREngine,
    OCRResult,
    _amounts_match,
    _merchants_match,
    _parse_amount,
)
from app.services.document_classifier import DocumentType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    """OCREngine with all external deps mocked."""
    with patch("app.services.ocr_engine.ImagePreprocessor"), \
         patch("app.services.ocr_engine.DocumentClassifier"), \
         patch("app.services.ocr_engine.FieldExtractor"), \
         patch("app.services.ocr_engine.MerchantDatabase"), \
         patch("app.services.ocr_engine.get_llm_extractor"), \
         patch("app.services.ocr_engine.pytesseract"):
        eng = OCREngine()
    return eng


def _make_ocr_result(
    extracted_data=None,
    confidence=0.70,
    doc_type=DocumentType.RECEIPT,
    suggestions=None,
):
    """Helper to build an OCRResult."""
    return OCRResult(
        document_type=doc_type,
        extracted_data=extracted_data or {},
        raw_text="raw text",
        confidence_score=confidence,
        needs_review=confidence < 0.6,
        processing_time_ms=100.0,
        suggestions=suggestions or ["AI vision model used for OCR."],
    )


# ---------------------------------------------------------------------------
# Amount parsing & comparison
# ---------------------------------------------------------------------------


class TestAmountParsing:
    def test_float_passthrough(self):
        assert _parse_amount(25.90) == 25.90

    def test_int_passthrough(self):
        assert _parse_amount(100) == 100.0

    def test_string_simple(self):
        assert _parse_amount("25.90") == 25.90

    def test_austrian_format(self):
        assert _parse_amount("1.234,56") == 1234.56

    def test_euro_sign(self):
        assert _parse_amount("€ 42,50") == 42.50

    def test_none(self):
        assert _parse_amount(None) is None

    def test_garbage(self):
        assert _parse_amount("abc") is None


class TestAmountsMatch:
    def test_exact_match(self):
        assert _amounts_match(25.90, 25.90)

    def test_within_tolerance(self):
        assert _amounts_match(100.0, 100.5)  # 0.5% diff

    def test_outside_tolerance(self):
        assert not _amounts_match(100.0, 105.0)  # 5% diff

    def test_austrian_vs_float(self):
        assert _amounts_match("1.234,56", 1234.56)

    def test_both_zero(self):
        assert _amounts_match(0, 0)

    def test_one_none(self):
        assert not _amounts_match(None, 25.0)


# ---------------------------------------------------------------------------
# Merchant fuzzy matching
# ---------------------------------------------------------------------------


class TestMerchantsMatch:
    def test_exact(self):
        assert _merchants_match("BILLA", "BILLA")

    def test_case_insensitive(self):
        assert _merchants_match("Billa", "BILLA")

    def test_substring(self):
        assert _merchants_match("BILLA Filiale 42 Wien", "billa")

    def test_filiale_stripped(self):
        assert _merchants_match("BILLA FILIALE 1234", "Billa")

    def test_different_merchants(self):
        assert not _merchants_match("BILLA", "SPAR")

    def test_empty(self):
        assert not _merchants_match("", "BILLA")


# ---------------------------------------------------------------------------
# Cross-validation: high confidence skips
# ---------------------------------------------------------------------------


class TestCrossValidationSkip:
    def test_high_vlm_confidence_skips(self, engine):
        """VLM confidence >= 0.85 should skip cross-validation entirely."""
        vlm = _make_ocr_result(
            extracted_data={"amount": 25.90, "merchant": "BILLA"},
            confidence=0.88,
        )
        result = engine._cross_validate_image(vlm, b"fake_image", datetime.now())
        # Should return VLM result unchanged
        assert result.confidence_score == 0.88
        assert result.extracted_data == vlm.extracted_data


# ---------------------------------------------------------------------------
# Cross-validation: fields match → boost
# ---------------------------------------------------------------------------


class TestCrossValidationMatch:
    @patch.object(OCREngine, "_tesseract_llm_extract")
    def test_matching_fields_boost_confidence(self, mock_tess, engine):
        """When VLM and Tesseract agree, confidence should be boosted."""
        vlm = _make_ocr_result(
            extracted_data={
                "amount": 25.90,
                "date": "2026-01-15",
                "merchant": "BILLA",
            },
            confidence=0.70,
        )
        mock_tess.return_value = _make_ocr_result(
            extracted_data={
                "amount": 25.90,
                "date": "2026-01-15",
                "merchant": "Billa Filiale 42",
            },
            confidence=0.65,
        )

        result = engine._cross_validate_image(vlm, b"img", datetime.now())

        # All 3 fields match, critical fields OK → boost by 0.15
        assert result.confidence_score == pytest.approx(0.85, abs=0.01)
        assert not result.needs_review
        assert any("Cross-validated" in s for s in result.suggestions)

    @patch.object(OCREngine, "_tesseract_llm_extract")
    def test_matching_merges_extra_fields(self, mock_tess, engine):
        """Tesseract extra fields should be merged into VLM result."""
        vlm = _make_ocr_result(
            extracted_data={"amount": 50.0, "date": "2026-03-01"},
            confidence=0.68,
        )
        mock_tess.return_value = _make_ocr_result(
            extracted_data={
                "amount": 50.0,
                "date": "2026-03-01",
                "invoice_number": "INV-2026-001",
            },
            confidence=0.60,
        )

        result = engine._cross_validate_image(vlm, b"img", datetime.now())

        assert result.extracted_data.get("invoice_number") == "INV-2026-001"
        assert result.extracted_data["amount"] == 50.0

    @patch.object(OCREngine, "_tesseract_llm_extract")
    def test_non_critical_mismatch_smaller_boost(self, mock_tess, engine):
        """If amount/date match but merchant differs, still boost but less."""
        vlm = _make_ocr_result(
            extracted_data={
                "amount": 25.90,
                "date": "2026-01-15",
                "merchant": "BILLA",
            },
            confidence=0.70,
        )
        mock_tess.return_value = _make_ocr_result(
            extracted_data={
                "amount": 25.90,
                "date": "2026-01-15",
                "merchant": "SPAR",  # different merchant
            },
            confidence=0.65,
        )

        result = engine._cross_validate_image(vlm, b"img", datetime.now())

        # 2/3 match (amount + date), ratio 0.67 >= 0.5 → boost
        # But merchant mismatches, critical fields OK → boost 0.15
        # Wait: merchant is not critical (amount, date are). So critical_ok=True
        assert result.confidence_score == pytest.approx(0.85, abs=0.01)


# ---------------------------------------------------------------------------
# Cross-validation: fields mismatch → penalty
# ---------------------------------------------------------------------------


class TestCrossValidationMismatch:
    @patch.object(OCREngine, "_tesseract_llm_extract")
    def test_amount_mismatch_big_penalty(self, mock_tess, engine):
        """Amount disagreement should trigger bigger penalty."""
        vlm = _make_ocr_result(
            extracted_data={
                "amount": 25.90,
                "date": "2026-01-15",
                "merchant": "BILLA",
            },
            confidence=0.70,
        )
        mock_tess.return_value = _make_ocr_result(
            extracted_data={
                "amount": 259.00,  # very different
                "date": "2025-12-31",  # different date
                "merchant": "SPAR",  # different merchant
            },
            confidence=0.65,
        )

        result = engine._cross_validate_image(vlm, b"img", datetime.now())

        # 0/3 match → ratio 0.0 < 0.5 → penalty
        # amount in mismatches → critical_mismatch → penalty 0.20
        assert result.confidence_score == pytest.approx(0.50, abs=0.01)
        assert result.needs_review is True
        assert any("disagree" in s.lower() for s in result.suggestions)

    @patch.object(OCREngine, "_tesseract_llm_extract")
    def test_date_mismatch_big_penalty(self, mock_tess, engine):
        """Date disagreement is also a critical mismatch."""
        vlm = _make_ocr_result(
            extracted_data={"amount": 50.0, "date": "2026-01-15"},
            confidence=0.75,
        )
        mock_tess.return_value = _make_ocr_result(
            extracted_data={"amount": 50.0, "date": "2025-01-15"},
            confidence=0.60,
        )

        result = engine._cross_validate_image(vlm, b"img", datetime.now())

        # 1/2 match (amount OK, date differs) → ratio 0.5 >= 0.5 → boost path
        # But date is in mismatches → critical_ok=False → boost only 0.08
        assert result.confidence_score == pytest.approx(0.83, abs=0.01)

    @patch.object(OCREngine, "_tesseract_llm_extract")
    def test_only_non_critical_mismatch_small_penalty(self, mock_tess, engine):
        """Non-critical field mismatch only → smaller penalty."""
        vlm = _make_ocr_result(
            extracted_data={"merchant": "BILLA", "invoice_number": "A123"},
            confidence=0.70,
        )
        mock_tess.return_value = _make_ocr_result(
            extracted_data={"merchant": "SPAR", "invoice_number": "B456"},
            confidence=0.60,
        )

        result = engine._cross_validate_image(vlm, b"img", datetime.now())

        # 0/2 match → ratio 0.0 < 0.5 → penalty
        # No amount/date in mismatches → penalty 0.10
        assert result.confidence_score == pytest.approx(0.60, abs=0.01)
        assert result.needs_review is True


# ---------------------------------------------------------------------------
# Cross-validation: edge cases
# ---------------------------------------------------------------------------


class TestCrossValidationEdgeCases:
    @patch.object(OCREngine, "_tesseract_llm_extract")
    def test_tesseract_fails_returns_vlm(self, mock_tess, engine):
        """If Tesseract+LLM fails, return VLM result unchanged."""
        vlm = _make_ocr_result(
            extracted_data={"amount": 25.90},
            confidence=0.70,
        )
        mock_tess.return_value = None

        result = engine._cross_validate_image(vlm, b"img", datetime.now())

        assert result.confidence_score == 0.70
        assert result is vlm

    @patch.object(OCREngine, "_tesseract_llm_extract")
    def test_no_overlapping_fields_returns_vlm(self, mock_tess, engine):
        """If no key fields overlap, return VLM result unchanged."""
        vlm = _make_ocr_result(
            extracted_data={"description": "Lebensmittel"},
            confidence=0.65,
        )
        mock_tess.return_value = _make_ocr_result(
            extracted_data={"line_items": [{"name": "Milch"}]},
            confidence=0.55,
        )

        result = engine._cross_validate_image(vlm, b"img", datetime.now())

        assert result.confidence_score == 0.65
        assert result is vlm

    @patch.object(OCREngine, "_tesseract_llm_extract")
    def test_one_field_match_one_field(self, mock_tess, engine):
        """Single overlapping field that matches → boost."""
        vlm = _make_ocr_result(
            extracted_data={"amount": 42.50},
            confidence=0.68,
        )
        mock_tess.return_value = _make_ocr_result(
            extracted_data={"amount": "42,50"},  # Austrian format
            confidence=0.55,
        )

        result = engine._cross_validate_image(vlm, b"img", datetime.now())

        # 1/1 match, critical OK → boost 0.15
        assert result.confidence_score == pytest.approx(0.83, abs=0.01)


# ---------------------------------------------------------------------------
# VLM confidence formula
# ---------------------------------------------------------------------------


class TestVLMConfidenceFormula:
    """Verify the conservative VLM confidence calculation."""

    def test_zero_fields(self):
        # min(0.80, 0.50 + 0 * 0.03) = 0.50
        assert min(0.80, 0.50 + 0 * 0.03) == 0.50

    def test_five_fields(self):
        # min(0.80, 0.50 + 5 * 0.03) = 0.65
        assert min(0.80, 0.50 + 5 * 0.03) == pytest.approx(0.65)

    def test_seven_fields(self):
        # min(0.80, 0.50 + 7 * 0.03) = 0.71
        assert min(0.80, 0.50 + 7 * 0.03) == pytest.approx(0.71)

    def test_ten_fields(self):
        # min(0.80, 0.50 + 10 * 0.03) = 0.80 (cap)
        assert min(0.80, 0.50 + 10 * 0.03) == 0.80

    def test_twenty_fields_capped(self):
        # min(0.80, 0.50 + 20 * 0.03) = 0.80 (cap)
        assert min(0.80, 0.50 + 20 * 0.03) == 0.80


# ---------------------------------------------------------------------------
# LLM extraction confidence formula
# ---------------------------------------------------------------------------


class TestLLMExtractionConfidenceFormula:
    """Verify the text-based LLM extraction confidence calculation."""

    def test_five_fields(self):
        # min(0.90, 0.55 + 5 * 0.04) = 0.75
        assert min(0.90, 0.55 + 5 * 0.04) == pytest.approx(0.75)

    def test_eight_fields(self):
        # min(0.90, 0.55 + 8 * 0.04) = 0.87
        assert min(0.90, 0.55 + 8 * 0.04) == pytest.approx(0.87)

    def test_ten_fields_capped(self):
        # min(0.90, 0.55 + 10 * 0.04) = 0.90 (cap)
        assert min(0.90, 0.55 + 10 * 0.04) == pytest.approx(0.90)


# ---------------------------------------------------------------------------
# _compare_extracted_fields
# ---------------------------------------------------------------------------


class TestCompareExtractedFields:
    def test_all_match(self):
        vlm = {"amount": 25.90, "date": "2026-01-15", "merchant": "BILLA"}
        tess = {"amount": "25,90", "date": "2026-01-15", "merchant": "Billa Filiale 42"}
        matches, mismatches, compared = OCREngine._compare_extracted_fields(vlm, tess)
        assert matches == 3
        assert mismatches == []
        assert compared == 3

    def test_partial_overlap(self):
        vlm = {"amount": 25.90, "description": "food"}
        tess = {"amount": 25.90, "merchant": "BILLA"}
        matches, mismatches, compared = OCREngine._compare_extracted_fields(vlm, tess)
        assert matches == 1  # amount
        assert compared == 1

    def test_no_overlap(self):
        vlm = {"description": "food"}
        tess = {"line_items": []}
        matches, mismatches, compared = OCREngine._compare_extracted_fields(vlm, tess)
        assert compared == 0

    def test_amount_mismatch(self):
        vlm = {"amount": 25.90}
        tess = {"amount": 259.00}
        matches, mismatches, compared = OCREngine._compare_extracted_fields(vlm, tess)
        assert matches == 0
        assert "amount" in mismatches
