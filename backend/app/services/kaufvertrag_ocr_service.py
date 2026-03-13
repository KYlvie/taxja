"""
Kaufvertrag OCR Service - Integrates Tesseract OCR with pattern-based extraction

This service combines:
1. OCREngine (Tesseract) for text extraction from PDF/image documents
2. KaufvertragExtractor for pattern-based field extraction from text

Usage:
    service = KaufvertragOCRService()
    result = service.process_kaufvertrag(pdf_bytes)
"""
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from app.services.ocr_engine import OCREngine
from app.services.kaufvertrag_extractor import KaufvertragExtractor, KaufvertragData

logger = logging.getLogger(__name__)


class KaufvertragOCRResult:
    """Result of Kaufvertrag OCR processing"""

    def __init__(
        self,
        kaufvertrag_data: KaufvertragData,
        raw_text: str,
        ocr_confidence: float,
        extraction_confidence: float,
        overall_confidence: float,
    ):
        self.kaufvertrag_data = kaufvertrag_data
        self.raw_text = raw_text
        self.ocr_confidence = ocr_confidence  # Tesseract OCR quality
        self.extraction_confidence = extraction_confidence  # Pattern matching quality
        self.overall_confidence = overall_confidence  # Combined confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        extractor = KaufvertragExtractor()
        return {
            "extracted_data": extractor.to_dict(self.kaufvertrag_data),
            "raw_text": self.raw_text,
            "ocr_confidence": float(self.ocr_confidence),
            "extraction_confidence": float(self.extraction_confidence),
            "overall_confidence": float(self.overall_confidence),
            "confidence_breakdown": {
                "ocr_quality": float(self.ocr_confidence),
                "pattern_matching": float(self.extraction_confidence),
            },
        }


class KaufvertragOCRService:
    """
    Service for processing Kaufvertrag documents using Tesseract OCR + pattern matching

    This service:
    1. Uses OCREngine to extract text from PDF/image using Tesseract
    2. Uses KaufvertragExtractor to extract structured fields using pattern matching
    3. Combines confidence scores from both stages
    """

    def __init__(self):
        self.ocr_engine = OCREngine()
        self.extractor = KaufvertragExtractor()
        logger.info("KaufvertragOCRService initialized with Tesseract OCR + pattern matching")

    def process_kaufvertrag(self, document_bytes: bytes) -> KaufvertragOCRResult:
        """
        Process a Kaufvertrag document (PDF or image) and extract structured data

        Args:
            document_bytes: Raw bytes of PDF or image file

        Returns:
            KaufvertragOCRResult with extracted data and confidence scores

        Raises:
            ValueError: If OCR or extraction fails
        """
        try:
            # Stage 1: OCR text extraction using Tesseract
            logger.info("Stage 1: Extracting text using Tesseract OCR")
            ocr_result = self.ocr_engine.process_document(document_bytes)
            raw_text = ocr_result.raw_text
            ocr_confidence = ocr_result.confidence_score

            if not raw_text or len(raw_text.strip()) < 50:
                raise ValueError(
                    "OCR extracted insufficient text. Document may be unreadable or not a Kaufvertrag."
                )

            logger.info(
                f"OCR completed: {len(raw_text)} characters extracted, "
                f"confidence: {ocr_confidence:.2f}"
            )

            # Stage 2: Pattern-based field extraction
            logger.info("Stage 2: Extracting fields using pattern matching")
            kaufvertrag_data = self.extractor.extract(raw_text)
            extraction_confidence = kaufvertrag_data.confidence

            logger.info(
                f"Extraction completed: {len([f for f in self.extractor.to_dict(kaufvertrag_data).values() if f is not None])} fields extracted, "
                f"confidence: {extraction_confidence:.2f}"
            )

            # Stage 3: Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(
                ocr_confidence, extraction_confidence, kaufvertrag_data
            )

            logger.info(f"Overall confidence: {overall_confidence:.2f}")

            return KaufvertragOCRResult(
                kaufvertrag_data=kaufvertrag_data,
                raw_text=raw_text,
                ocr_confidence=ocr_confidence,
                extraction_confidence=extraction_confidence,
                overall_confidence=overall_confidence,
            )

        except Exception as e:
            logger.error(f"Kaufvertrag OCR processing failed: {str(e)}")
            raise ValueError(f"Failed to process Kaufvertrag: {str(e)}")

    def process_kaufvertrag_from_text(self, text: str) -> KaufvertragOCRResult:
        """
        Process pre-extracted text (skip OCR stage)

        Useful for testing or when text is already available.

        Args:
            text: Pre-extracted text from Kaufvertrag

        Returns:
            KaufvertragOCRResult with extracted data
        """
        try:
            logger.info("Processing Kaufvertrag from pre-extracted text")

            # Skip OCR, go directly to pattern extraction
            kaufvertrag_data = self.extractor.extract(text)
            extraction_confidence = kaufvertrag_data.confidence

            # No OCR confidence since we skipped that stage
            ocr_confidence = 1.0  # Assume perfect OCR since text is pre-extracted

            overall_confidence = self._calculate_overall_confidence(
                ocr_confidence, extraction_confidence, kaufvertrag_data
            )

            return KaufvertragOCRResult(
                kaufvertrag_data=kaufvertrag_data,
                raw_text=text,
                ocr_confidence=ocr_confidence,
                extraction_confidence=extraction_confidence,
                overall_confidence=overall_confidence,
            )

        except Exception as e:
            logger.error(f"Kaufvertrag text processing failed: {str(e)}")
            raise ValueError(f"Failed to process Kaufvertrag text: {str(e)}")

    def _calculate_overall_confidence(
        self, ocr_confidence: float, extraction_confidence: float, data: KaufvertragData
    ) -> float:
        """
        Calculate overall confidence combining OCR quality and extraction quality

        Formula:
        - OCR confidence: 40% weight (text quality)
        - Extraction confidence: 60% weight (field extraction quality)
        - Penalty for missing critical fields

        Args:
            ocr_confidence: Tesseract OCR confidence (0.0 to 1.0)
            extraction_confidence: Pattern matching confidence (0.0 to 1.0)
            data: Extracted Kaufvertrag data

        Returns:
            Overall confidence score (0.0 to 1.0)
        """
        # Weighted average: OCR 40%, extraction 60%
        base_confidence = (ocr_confidence * 0.4) + (extraction_confidence * 0.6)

        # Apply penalty for missing critical fields
        critical_fields = [
            data.property_address,
            data.purchase_price,
            data.purchase_date,
        ]
        missing_critical = sum(1 for field in critical_fields if field is None)

        if missing_critical > 0:
            penalty = missing_critical * 0.15  # 15% penalty per missing critical field
            base_confidence = max(0.0, base_confidence - penalty)

        # Bonus for having optional high-value fields
        bonus_fields = [
            data.buyer_name,
            data.seller_name,
            data.building_value,
            data.notary_name,
        ]
        present_bonus = sum(1 for field in bonus_fields if field is not None)

        if present_bonus > 0:
            bonus = present_bonus * 0.02  # 2% bonus per bonus field
            base_confidence = min(1.0, base_confidence + bonus)

        return round(base_confidence, 2)

    def validate_extraction(self, result: KaufvertragOCRResult) -> Dict[str, Any]:
        """
        Validate extraction result and provide recommendations

        Args:
            result: KaufvertragOCRResult to validate

        Returns:
            Dictionary with validation status and recommendations
        """
        data = result.kaufvertrag_data
        issues = []
        warnings = []
        recommendations = []

        # Check critical fields
        if not data.property_address:
            issues.append("Missing property address")
            recommendations.append("Manually enter property address")

        if not data.purchase_price:
            issues.append("Missing purchase price")
            recommendations.append("Manually enter purchase price")

        if not data.purchase_date:
            issues.append("Missing purchase date")
            recommendations.append("Manually enter purchase date")

        # Check confidence thresholds
        if result.overall_confidence < 0.5:
            warnings.append("Low overall confidence - manual review strongly recommended")
        elif result.overall_confidence < 0.7:
            warnings.append("Medium confidence - please verify extracted data")

        if result.ocr_confidence < 0.6:
            warnings.append("Low OCR quality - document may be scanned poorly")
            recommendations.append("Try rescanning document at higher resolution")

        # Check data consistency
        if data.purchase_price and data.building_value:
            if data.building_value > data.purchase_price:
                warnings.append(
                    f"Building value ({data.building_value}) exceeds purchase price ({data.purchase_price}). "
                    "Please verify."
                )

        if data.building_value and data.land_value:
            total = data.building_value + data.land_value
            if data.purchase_price and abs(total - data.purchase_price) > Decimal("100"):
                warnings.append(
                    f"Building value + land value ({total}) does not match purchase price ({data.purchase_price}). "
                    "Please verify."
                )

        # Check date reasonableness
        if data.purchase_date:
            from datetime import datetime
            if data.purchase_date > datetime.now():
                warnings.append("Purchase date is in the future. Please verify.")

        # Determine overall status
        if len(issues) > 0:
            status = "requires_manual_entry"
        elif len(warnings) > 0:
            status = "requires_review"
        else:
            status = "ready"

        return {
            "status": status,
            "overall_confidence": result.overall_confidence,
            "issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
            "critical_fields_present": {
                "property_address": data.property_address is not None,
                "purchase_price": data.purchase_price is not None,
                "purchase_date": data.purchase_date is not None,
            },
        }
