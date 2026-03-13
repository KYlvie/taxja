"""
Mietvertrag OCR Service - Integrates Tesseract OCR with pattern-based extraction

This service combines:
1. OCREngine (Tesseract) for text extraction from PDF/image documents
2. MietvertragExtractor for pattern-based field extraction from text

Usage:
    service = MietvertragOCRService()
    result = service.process_mietvertrag(pdf_bytes)
"""
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from app.services.ocr_engine import OCREngine
from app.services.mietvertrag_extractor import MietvertragExtractor, MietvertragData

logger = logging.getLogger(__name__)


class MietvertragOCRResult:
    """Result of Mietvertrag OCR processing"""

    def __init__(
        self,
        mietvertrag_data: MietvertragData,
        raw_text: str,
        ocr_confidence: float,
        extraction_confidence: float,
        overall_confidence: float,
    ):
        self.mietvertrag_data = mietvertrag_data
        self.raw_text = raw_text
        self.ocr_confidence = ocr_confidence  # Tesseract OCR quality
        self.extraction_confidence = extraction_confidence  # Pattern matching quality
        self.overall_confidence = overall_confidence  # Combined confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        extractor = MietvertragExtractor()
        return {
            "extracted_data": extractor.to_dict(self.mietvertrag_data),
            "raw_text": self.raw_text,
            "ocr_confidence": float(self.ocr_confidence),
            "extraction_confidence": float(self.extraction_confidence),
            "overall_confidence": float(self.overall_confidence),
            "confidence_breakdown": {
                "ocr_quality": float(self.ocr_confidence),
                "pattern_matching": float(self.extraction_confidence),
            },
        }


class MietvertragOCRService:
    """
    Service for processing Mietvertrag documents using Tesseract OCR + pattern matching

    This service:
    1. Uses OCREngine to extract text from PDF/image using Tesseract
    2. Uses MietvertragExtractor to extract structured fields using pattern matching
    3. Combines confidence scores from both stages
    """

    def __init__(self):
        self.ocr_engine = OCREngine()
        self.extractor = MietvertragExtractor()
        logger.info("MietvertragOCRService initialized with Tesseract OCR + pattern matching")

    def process_mietvertrag(self, document_bytes: bytes) -> MietvertragOCRResult:
        """
        Process a Mietvertrag document (PDF or image) and extract structured data

        Args:
            document_bytes: Raw bytes of PDF or image file

        Returns:
            MietvertragOCRResult with extracted data and confidence scores

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
                    "OCR extracted insufficient text. Document may be unreadable or not a Mietvertrag."
                )

            logger.info(
                f"OCR completed: {len(raw_text)} characters extracted, "
                f"confidence: {ocr_confidence:.2f}"
            )

            # Stage 2: Pattern-based field extraction
            logger.info("Stage 2: Extracting fields using pattern matching")
            mietvertrag_data = self.extractor.extract(raw_text)
            extraction_confidence = mietvertrag_data.confidence

            logger.info(
                f"Extraction completed: {len([f for f in self.extractor.to_dict(mietvertrag_data).values() if f is not None])} fields extracted, "
                f"confidence: {extraction_confidence:.2f}"
            )

            # Stage 3: Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(
                ocr_confidence, extraction_confidence, mietvertrag_data
            )

            logger.info(f"Overall confidence: {overall_confidence:.2f}")

            return MietvertragOCRResult(
                mietvertrag_data=mietvertrag_data,
                raw_text=raw_text,
                ocr_confidence=ocr_confidence,
                extraction_confidence=extraction_confidence,
                overall_confidence=overall_confidence,
            )

        except Exception as e:
            logger.error(f"Mietvertrag OCR processing failed: {str(e)}")
            raise ValueError(f"Failed to process Mietvertrag: {str(e)}")

    def process_mietvertrag_from_text(self, text: str) -> MietvertragOCRResult:
        """
        Process pre-extracted text (skip OCR stage)

        Useful for testing or when text is already available.

        Args:
            text: Pre-extracted text from Mietvertrag

        Returns:
            MietvertragOCRResult with extracted data
        """
        try:
            logger.info("Processing Mietvertrag from pre-extracted text")

            # Skip OCR, go directly to pattern extraction
            mietvertrag_data = self.extractor.extract(text)
            extraction_confidence = mietvertrag_data.confidence

            # No OCR confidence since we skipped that stage
            ocr_confidence = 1.0  # Assume perfect OCR since text is pre-extracted

            overall_confidence = self._calculate_overall_confidence(
                ocr_confidence, extraction_confidence, mietvertrag_data
            )

            return MietvertragOCRResult(
                mietvertrag_data=mietvertrag_data,
                raw_text=text,
                ocr_confidence=ocr_confidence,
                extraction_confidence=extraction_confidence,
                overall_confidence=overall_confidence,
            )

        except Exception as e:
            logger.error(f"Mietvertrag text processing failed: {str(e)}")
            raise ValueError(f"Failed to process Mietvertrag text: {str(e)}")

    def _calculate_overall_confidence(
        self, ocr_confidence: float, extraction_confidence: float, data: MietvertragData
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
            data: Extracted Mietvertrag data

        Returns:
            Overall confidence score (0.0 to 1.0)
        """
        # Weighted average: OCR 40%, extraction 60%
        base_confidence = (ocr_confidence * 0.4) + (extraction_confidence * 0.6)

        # Apply penalty for missing critical fields
        critical_fields = [
            data.property_address,
            data.monthly_rent,
            data.start_date,
        ]
        missing_critical = sum(1 for field in critical_fields if field is None)

        if missing_critical > 0:
            penalty = missing_critical * 0.15  # 15% penalty per missing critical field
            base_confidence = max(0.0, base_confidence - penalty)

        # Bonus for having optional high-value fields
        bonus_fields = [
            data.tenant_name,
            data.landlord_name,
            data.betriebskosten,
            data.heating_costs,
        ]
        present_bonus = sum(1 for field in bonus_fields if field is not None)

        if present_bonus > 0:
            bonus = present_bonus * 0.02  # 2% bonus per bonus field
            base_confidence = min(1.0, base_confidence + bonus)

        return round(base_confidence, 2)

    def validate_extraction(self, result: MietvertragOCRResult) -> Dict[str, Any]:
        """
        Validate extraction result and provide recommendations

        Args:
            result: MietvertragOCRResult to validate

        Returns:
            Dictionary with validation status and recommendations
        """
        data = result.mietvertrag_data
        issues = []
        warnings = []
        recommendations = []

        # Check critical fields
        if not data.property_address:
            issues.append("Missing property address")
            recommendations.append("Manually enter property address")

        if not data.monthly_rent:
            issues.append("Missing monthly rent")
            recommendations.append("Manually enter monthly rent")

        if not data.start_date:
            issues.append("Missing rental start date")
            recommendations.append("Manually enter rental start date")

        # Check confidence thresholds
        if result.overall_confidence < 0.5:
            warnings.append("Low overall confidence - manual review strongly recommended")
        elif result.overall_confidence < 0.7:
            warnings.append("Medium confidence - please verify extracted data")

        if result.ocr_confidence < 0.6:
            warnings.append("Low OCR quality - document may be scanned poorly")
            recommendations.append("Try rescanning document at higher resolution")

        # Check data consistency
        if data.monthly_rent and data.betriebskosten:
            if data.betriebskosten > data.monthly_rent:
                warnings.append(
                    f"Betriebskosten ({data.betriebskosten}) exceeds monthly rent ({data.monthly_rent}). "
                    "Please verify."
                )

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
                "monthly_rent": data.monthly_rent is not None,
                "start_date": data.start_date is not None,
            },
        }
