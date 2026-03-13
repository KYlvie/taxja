"""
Error logging service for comprehensive error tracking.
Logs all errors with context for debugging and monitoring.
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import TaxjaException
from app.models.audit_log import AuditLog, AuditAction

logger = logging.getLogger(__name__)


class ErrorLoggingService:
    """Service for logging errors with context"""

    def __init__(self, db: Session):
        self.db = db

    def log_error(
        self,
        error: Exception,
        user_id: Optional[int] = None,
        request_path: Optional[str] = None,
        request_method: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an error with full context.
        
        Args:
            error: Exception that occurred
            user_id: ID of user who encountered the error
            request_path: API endpoint path
            request_method: HTTP method
            additional_context: Additional context information
        """
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "request_path": request_path,
            "request_method": request_method,
            "traceback": traceback.format_exc(),
        }

        # Add Taxja-specific error details
        if isinstance(error, TaxjaException):
            error_data.update(
                {
                    "error_code": error.error_code,
                    "error_details": error.details,
                    "suggestion": error.suggestion,
                }
            )

        # Add additional context
        if additional_context:
            error_data["context"] = additional_context

        # Log to application logger
        logger.error(
            f"Error occurred: {error_data['error_type']} - {error_data['error_message']}",
            extra=error_data,
        )

        # Log to audit log if user is identified
        if user_id:
            try:
                audit_entry = AuditLog(
                    user_id=user_id,
                    action=AuditAction.ERROR,
                    resource_type="error",
                    resource_id=None,
                    details=error_data,
                    ip_address=additional_context.get("ip_address") if additional_context else None,
                    user_agent=additional_context.get("user_agent") if additional_context else None,
                )
                self.db.add(audit_entry)
                self.db.commit()
            except Exception as audit_error:
                logger.error(f"Failed to log error to audit log: {audit_error}")

    def log_validation_error(
        self,
        field: str,
        message: str,
        value: Any,
        user_id: Optional[int] = None,
    ) -> None:
        """
        Log a validation error.
        
        Args:
            field: Field that failed validation
            message: Validation error message
            value: Invalid value
            user_id: ID of user who submitted invalid data
        """
        logger.warning(
            f"Validation error on field '{field}': {message}",
            extra={
                "field": field,
                "message": message,
                "value": str(value),
                "user_id": user_id,
            },
        )

    def log_authentication_failure(
        self,
        username: str,
        reason: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Log an authentication failure.
        
        Args:
            username: Username that failed authentication
            reason: Reason for failure
            ip_address: IP address of request
        """
        logger.warning(
            f"Authentication failure for user '{username}': {reason}",
            extra={
                "username": username,
                "reason": reason,
                "ip_address": ip_address,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def log_ocr_error(
        self,
        document_id: Optional[int],
        error_message: str,
        confidence: Optional[float] = None,
        user_id: Optional[int] = None,
    ) -> None:
        """
        Log an OCR processing error.
        
        Args:
            document_id: ID of document that failed OCR
            error_message: Error message
            confidence: OCR confidence score if available
            user_id: ID of user who uploaded document
        """
        logger.error(
            f"OCR error for document {document_id}: {error_message}",
            extra={
                "document_id": document_id,
                "error_message": error_message,
                "confidence": confidence,
                "user_id": user_id,
            },
        )

    def log_tax_calculation_error(
        self,
        user_id: int,
        tax_year: int,
        error_message: str,
        calculation_type: str,
    ) -> None:
        """
        Log a tax calculation error.
        
        Args:
            user_id: ID of user
            tax_year: Tax year being calculated
            error_message: Error message
            calculation_type: Type of calculation (income_tax, vat, svs)
        """
        logger.error(
            f"Tax calculation error for user {user_id}, year {tax_year}: {error_message}",
            extra={
                "user_id": user_id,
                "tax_year": tax_year,
                "error_message": error_message,
                "calculation_type": calculation_type,
            },
        )


def get_error_logging_service(db: Session) -> ErrorLoggingService:
    """Get error logging service instance"""
    return ErrorLoggingService(db)
