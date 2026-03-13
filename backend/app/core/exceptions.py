"""
Custom exceptions for Taxja application.
Provides domain-specific exceptions with clear error messages.
"""

from typing import Any, Dict, Optional


class TaxjaException(Exception):
    """Base exception for all Taxja errors"""

    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestion = suggestion
        super().__init__(self.message)


# Validation Errors
class ValidationError(TaxjaException):
    """Raised when input validation fails"""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field, **(details or {})},
            suggestion="Please check your input and try again.",
        )


class TransactionValidationError(ValidationError):
    """Raised when transaction validation fails"""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message=message, field=field)
        self.error_code = "TRANSACTION_VALIDATION_ERROR"


# Authentication/Authorization Errors
class AuthenticationError(TaxjaException):
    """Raised when authentication fails"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            suggestion="Please check your credentials and try again.",
        )


class AuthorizationError(TaxjaException):
    """Raised when user lacks permission"""

    def __init__(self, message: str = "You don't have permission to perform this action"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            suggestion="Contact an administrator if you believe you should have access.",
        )


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired"""

    def __init__(self):
        super().__init__(message="Your session has expired")
        self.error_code = "TOKEN_EXPIRED"
        self.suggestion = "Please log in again."


class TwoFactorRequiredError(AuthenticationError):
    """Raised when 2FA is required but not provided"""

    def __init__(self):
        super().__init__(message="Two-factor authentication is required")
        self.error_code = "TWO_FACTOR_REQUIRED"
        self.suggestion = "Please provide your 2FA code."


# OCR Errors
class OCRError(TaxjaException):
    """Base class for OCR-related errors"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="OCR_ERROR",
            details=details,
            suggestion=suggestion or "Please ensure the image is clear and well-lit.",
        )


class OCRProcessingError(OCRError):
    """Raised when OCR processing fails"""

    def __init__(self, message: str = "Failed to process document"):
        super().__init__(
            message=message,
            suggestion="Please ensure the image is clear, well-lit, and in a supported format (JPEG, PNG, PDF).",
        )


class OCRLowConfidenceError(OCRError):
    """Raised when OCR confidence is too low"""

    def __init__(self, confidence: float):
        super().__init__(
            message=f"OCR confidence too low: {confidence:.1%}",
            details={"confidence": confidence},
            suggestion="Please retake the photo with better lighting or manually enter the data.",
        )


class UnsupportedDocumentFormatError(OCRError):
    """Raised when document format is not supported"""

    def __init__(self, format: str):
        super().__init__(
            message=f"Unsupported document format: {format}",
            details={"format": format},
            suggestion="Supported formats: JPEG, PNG, PDF. Please convert your document and try again.",
        )


class DocumentTooLargeError(OCRError):
    """Raised when document file size exceeds limit"""

    def __init__(self, size_mb: float, max_size_mb: float = 10):
        super().__init__(
            message=f"Document too large: {size_mb:.1f}MB (max: {max_size_mb}MB)",
            details={"size_mb": size_mb, "max_size_mb": max_size_mb},
            suggestion="Please compress the image or reduce its resolution.",
        )


# Tax Calculation Errors
class TaxCalculationError(TaxjaException):
    """Base class for tax calculation errors"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="TAX_CALCULATION_ERROR",
            details=details,
            suggestion="Please verify your transaction data and try again.",
        )


class MissingTaxConfigurationError(TaxCalculationError):
    """Raised when tax configuration is missing for a year"""

    def __init__(self, tax_year: int):
        super().__init__(
            message=f"Tax configuration not found for year {tax_year}",
            details={"tax_year": tax_year},
        )
        self.suggestion = "Please contact support to add tax rates for this year."


class InvalidTaxYearError(TaxCalculationError):
    """Raised when tax year is invalid"""

    def __init__(self, tax_year: int):
        super().__init__(
            message=f"Invalid tax year: {tax_year}",
            details={"tax_year": tax_year},
        )
        self.suggestion = "Please select a valid tax year."


class NegativeIncomeError(TaxCalculationError):
    """Raised when income is negative (should be handled as loss)"""

    def __init__(self, income: float):
        super().__init__(
            message=f"Negative income detected: €{income:,.2f}",
            details={"income": income},
        )
        self.suggestion = "Negative income will be treated as a loss and carried forward."


# Data Errors
class DataNotFoundError(TaxjaException):
    """Raised when requested data is not found"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
        )


class DuplicateDataError(TaxjaException):
    """Raised when duplicate data is detected"""

    def __init__(self, resource: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Duplicate {resource} detected",
            error_code="DUPLICATE_ERROR",
            details=details,
            suggestion="This record may already exist. Please check and try again.",
        )


# Backup/Recovery Errors
class BackupError(TaxjaException):
    """Raised when backup operation fails"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="BACKUP_ERROR",
            details=details,
            suggestion="Please check backup storage availability and try again.",
        )


class RestoreError(TaxjaException):
    """Raised when restore operation fails"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="RESTORE_ERROR",
            details=details,
            suggestion="Please verify backup file integrity and try again.",
        )


# External Service Errors
class ExternalServiceError(TaxjaException):
    """Raised when external service call fails"""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service} service error: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service},
            suggestion="The external service is temporarily unavailable. Please try again later.",
        )
