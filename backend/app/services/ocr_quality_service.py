"""OCR quality assessment and feedback service"""
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal


class OCRQualityService:
    """
    Service for assessing OCR quality and providing feedback.
    
    Requirements: 25.2, 25.3, 25.4, 25.7
    
    This service:
    1. Analyzes OCR confidence scores
    2. Provides actionable suggestions for improvement
    3. Recommends retake when quality is poor
    4. Offers manual input option when OCR fails
    """
    
    # Quality thresholds
    EXCELLENT_THRESHOLD = 0.9
    GOOD_THRESHOLD = 0.75
    FAIR_THRESHOLD = 0.6
    POOR_THRESHOLD = 0.0
    
    # Field confidence thresholds
    FIELD_LOW_CONFIDENCE = 0.6
    FIELD_VERY_LOW_CONFIDENCE = 0.4
    
    def __init__(self):
        """Initialize OCR quality service"""
        pass
    
    def assess_quality(
        self,
        confidence_score: float,
        raw_text: Optional[str],
        extracted_data: Dict[str, Any],
        field_confidences: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Assess overall OCR quality and provide feedback.
        
        Args:
            confidence_score: Overall OCR confidence (0.0 to 1.0)
            raw_text: Raw OCR text
            extracted_data: Extracted structured data
            field_confidences: Confidence scores for individual fields
        
        Returns:
            Dictionary with quality assessment and feedback
        """
        # Determine overall quality level
        quality_level = self._determine_quality_level(confidence_score)
        
        # Identify issues
        issues = self._identify_issues(
            confidence_score,
            raw_text,
            extracted_data,
            field_confidences
        )
        
        # Generate suggestions
        suggestions = self._generate_suggestions(
            quality_level,
            issues,
            field_confidences
        )
        
        # Determine recommendations
        retake_recommended = quality_level == "poor"
        manual_input_recommended = quality_level in ["poor", "failed"]
        
        return {
            "overall_quality": quality_level,
            "confidence_score": confidence_score,
            "issues": issues,
            "suggestions": suggestions,
            "retake_recommended": retake_recommended,
            "manual_input_recommended": manual_input_recommended,
        }
    
    def _determine_quality_level(self, confidence: float) -> str:
        """
        Determine quality level based on confidence score.
        
        Args:
            confidence: Overall confidence score
        
        Returns:
            Quality level: excellent, good, fair, poor, or failed
        """
        if confidence >= self.EXCELLENT_THRESHOLD:
            return "excellent"
        elif confidence >= self.GOOD_THRESHOLD:
            return "good"
        elif confidence >= self.FAIR_THRESHOLD:
            return "fair"
        elif confidence > 0:
            return "poor"
        else:
            return "failed"
    
    def _identify_issues(
        self,
        confidence: float,
        raw_text: Optional[str],
        extracted_data: Dict[str, Any],
        field_confidences: Dict[str, float]
    ) -> List[str]:
        """
        Identify specific issues with OCR results.
        
        Args:
            confidence: Overall confidence score
            raw_text: Raw OCR text
            extracted_data: Extracted data
            field_confidences: Field confidence scores
        
        Returns:
            List of identified issues
        """
        issues = []
        
        # Check overall confidence
        if confidence < self.FAIR_THRESHOLD:
            issues.append("Low overall OCR confidence")
        
        # Check if text was detected
        if not raw_text or len(raw_text.strip()) < 10:
            issues.append("Very little text detected in image")
        
        # Check for low confidence fields
        low_confidence_fields = [
            field for field, conf in field_confidences.items()
            if conf < self.FIELD_LOW_CONFIDENCE
        ]
        
        if low_confidence_fields:
            issues.append(
                f"Low confidence in fields: {', '.join(low_confidence_fields)}"
            )
        
        # Check for very low confidence fields
        very_low_fields = [
            field for field, conf in field_confidences.items()
            if conf < self.FIELD_VERY_LOW_CONFIDENCE
        ]
        
        if very_low_fields:
            issues.append(
                f"Very low confidence in critical fields: {', '.join(very_low_fields)}"
            )
        
        # Check for missing critical fields
        critical_fields = ["date", "amount"]
        missing_fields = [
            field for field in critical_fields
            if field not in extracted_data or not extracted_data[field]
        ]
        
        if missing_fields:
            issues.append(
                f"Missing critical fields: {', '.join(missing_fields)}"
            )
        
        return issues
    
    def _generate_suggestions(
        self,
        quality_level: str,
        issues: List[str],
        field_confidences: Dict[str, float]
    ) -> List[str]:
        """
        Generate actionable suggestions based on quality assessment.
        
        Args:
            quality_level: Overall quality level
            issues: List of identified issues
            field_confidences: Field confidence scores
        
        Returns:
            List of suggestions
        """
        suggestions = []
        
        # Quality-specific suggestions
        if quality_level == "excellent":
            suggestions.append("✓ OCR results are highly accurate")
            suggestions.append("You can proceed with confidence")
        
        elif quality_level == "good":
            suggestions.append("✓ OCR results are reliable")
            suggestions.append("Please verify key fields before proceeding")
        
        elif quality_level == "fair":
            suggestions.append("⚠ Please carefully review all extracted data")
            suggestions.append("Pay special attention to highlighted fields")
            suggestions.append("Consider retaking if critical fields are unclear")
        
        elif quality_level == "poor":
            suggestions.append("❌ Retake photo with better lighting and clarity")
            suggestions.append("Ensure document is flat and not skewed")
            suggestions.append("Hold camera directly above document")
            suggestions.append("Alternatively, use manual input option")
        
        elif quality_level == "failed":
            suggestions.append("❌ OCR processing failed")
            suggestions.append("Please retake photo following best practices")
            suggestions.append("Or use manual input to enter data")
        
        # Field-specific suggestions
        low_confidence_fields = [
            field for field, conf in field_confidences.items()
            if conf < self.FIELD_LOW_CONFIDENCE
        ]
        
        if low_confidence_fields:
            suggestions.append(
                f"⚠ Verify these fields carefully: {', '.join(low_confidence_fields)}"
            )
        
        # Issue-specific suggestions
        if "Very little text detected" in " ".join(issues):
            suggestions.append("Ensure the document is clearly visible in the image")
            suggestions.append("Check that the image is not blurry or too dark")
        
        return suggestions
    
    def get_retake_guidance(self, confidence: float) -> Dict[str, Any]:
        """
        Get detailed guidance for retaking document photo.
        
        Requirements: 25.3, 25.4
        
        Args:
            confidence: Current OCR confidence score
        
        Returns:
            Dictionary with retake guidance
        """
        if confidence >= self.FAIR_THRESHOLD:
            return {
                "reason": "OCR quality is acceptable, but you can improve it",
                "tips": [
                    "Use natural daylight or bright indoor lighting",
                    "Place document on a flat, contrasting surface",
                    "Hold camera parallel to document (avoid angles)",
                    "Ensure all text is in focus",
                    "Avoid shadows on the document",
                ],
                "severity": "optional"
            }
        else:
            return {
                "reason": "OCR quality is poor and retake is strongly recommended",
                "tips": [
                    "✓ Use bright, even lighting (avoid shadows)",
                    "✓ Place document flat on a dark surface",
                    "✓ Hold camera directly above document (not at an angle)",
                    "✓ Ensure entire document fits in frame",
                    "✓ Make sure text is sharp and in focus",
                    "✓ Avoid glare from glossy paper",
                    "✓ Clean camera lens if blurry",
                    "✓ Use a document scanning app if available",
                ],
                "severity": "required"
            }
    
    def should_suggest_manual_input(
        self,
        confidence: float,
        retry_count: int = 0
    ) -> Tuple[bool, str]:
        """
        Determine if manual input should be suggested.
        
        Requirements: 25.7
        
        Args:
            confidence: OCR confidence score
            retry_count: Number of times OCR has been retried
        
        Returns:
            Tuple of (should_suggest, reason)
        """
        # Always suggest manual input if OCR completely failed
        if confidence == 0:
            return True, "OCR processing failed completely"
        
        # Suggest after multiple retries with poor results
        if retry_count >= 2 and confidence < self.FAIR_THRESHOLD:
            return True, "Multiple OCR attempts with poor results"
        
        # Suggest for very poor confidence
        if confidence < 0.3:
            return True, "OCR confidence is very low"
        
        # Don't suggest for acceptable results
        if confidence >= self.FAIR_THRESHOLD:
            return False, "OCR quality is acceptable"
        
        # For poor results on first try, suggest retake first
        return False, "Try retaking photo first"
    
    def generate_error_message(
        self,
        error_type: str,
        confidence: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate user-friendly error message for OCR failures.
        
        Requirements: 25.2, 25.3
        
        Args:
            error_type: Type of error (low_confidence, no_text_found, etc.)
            confidence: OCR confidence score if available
        
        Returns:
            Dictionary with error details and suggestions
        """
        error_messages = {
            "low_confidence": {
                "message": "The document image quality is too low for accurate text recognition.",
                "suggestions": [
                    "Retake the photo with better lighting",
                    "Ensure the document is flat and in focus",
                    "Try using a document scanner app",
                ],
                "can_retry": True,
            },
            "no_text_found": {
                "message": "No text could be detected in the image.",
                "suggestions": [
                    "Make sure the document is clearly visible",
                    "Check that you uploaded the correct file",
                    "Ensure the image is not blank or corrupted",
                ],
                "can_retry": True,
            },
            "invalid_format": {
                "message": "The uploaded file format is not supported or is corrupted.",
                "suggestions": [
                    "Upload a JPEG, PNG, or PDF file",
                    "Ensure the file is not corrupted",
                    "Try converting the file to a different format",
                ],
                "can_retry": True,
            },
            "processing_failed": {
                "message": "OCR processing encountered an unexpected error.",
                "suggestions": [
                    "Try uploading the document again",
                    "If the problem persists, use manual input",
                    "Contact support if you continue to experience issues",
                ],
                "can_retry": True,
            },
        }
        
        error_info = error_messages.get(error_type, {
            "message": "An unknown error occurred during OCR processing.",
            "suggestions": ["Please try again or use manual input"],
            "can_retry": True,
        })
        
        result = {
            "error_type": error_type,
            "error_message": error_info["message"],
            "suggestions": error_info["suggestions"],
            "can_retry": error_info["can_retry"],
        }
        
        # Add confidence-specific guidance
        if confidence is not None and confidence < self.FAIR_THRESHOLD:
            result["retake_guidance"] = self.get_retake_guidance(confidence)
        
        return result
