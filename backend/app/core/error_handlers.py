"""
Global error handlers for FastAPI application.
Handles all exceptions and returns consistent error responses.
"""

import logging
import traceback
from typing import Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BackupError,
    DataNotFoundError,
    DuplicateDataError,
    ExternalServiceError,
    OCRError,
    RestoreError,
    TaxCalculationError,
    TaxjaException,
    TokenExpiredError,
    TwoFactorRequiredError,
    ValidationError,
)

logger = logging.getLogger(__name__)


def setup_error_handlers(app: FastAPI) -> None:
    """
    Register all error handlers with the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(TaxjaException)
    async def taxja_exception_handler(request: Request, exc: TaxjaException) -> JSONResponse:
        """Handle all Taxja custom exceptions"""
        logger.error(
            f"Taxja exception: {exc.error_code} - {exc.message}",
            extra={
                "error_code": exc.error_code,
                "details": exc.details,
                "path": request.url.path,
                "method": request.method,
            },
        )

        status_code = _get_status_code_for_exception(exc)

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    "suggestion": exc.suggestion,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle FastAPI request validation errors"""
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append(
                {
                    "field": field,
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        logger.warning(
            f"Validation error on {request.url.path}",
            extra={"errors": errors, "method": request.method},
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Input validation failed",
                    "details": {"errors": errors},
                    "suggestion": "Please check your input and try again.",
                }
            },
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
        """Handle Pydantic validation errors"""
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append(
                {
                    "field": field,
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        logger.warning(
            f"Pydantic validation error on {request.url.path}",
            extra={"errors": errors, "method": request.method},
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Data validation failed",
                    "details": {"errors": errors},
                    "suggestion": "Please check your data format and try again.",
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """Handle database errors"""
        logger.error(
            f"Database error on {request.url.path}: {str(exc)}",
            extra={
                "error_type": type(exc).__name__,
                "method": request.method,
                "traceback": traceback.format_exc(),
            },
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "A database error occurred",
                    "details": {},
                    "suggestion": "Please try again later. If the problem persists, contact support.",
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all unhandled exceptions"""
        logger.critical(
            f"Unhandled exception on {request.url.path}: {str(exc)}",
            extra={
                "error_type": type(exc).__name__,
                "method": request.method,
                "traceback": traceback.format_exc(),
            },
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                    "suggestion": "Please try again later. If the problem persists, contact support.",
                }
            },
        )


def _get_status_code_for_exception(exc: TaxjaException) -> int:
    """
    Map exception types to HTTP status codes.
    
    Args:
        exc: Taxja exception instance
        
    Returns:
        HTTP status code
    """
    status_map = {
        AuthenticationError: status.HTTP_401_UNAUTHORIZED,
        TokenExpiredError: status.HTTP_401_UNAUTHORIZED,
        TwoFactorRequiredError: status.HTTP_401_UNAUTHORIZED,
        AuthorizationError: status.HTTP_403_FORBIDDEN,
        DataNotFoundError: status.HTTP_404_NOT_FOUND,
        ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
        DuplicateDataError: status.HTTP_409_CONFLICT,
        OCRError: status.HTTP_422_UNPROCESSABLE_ENTITY,
        TaxCalculationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
        BackupError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        RestoreError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ExternalServiceError: status.HTTP_503_SERVICE_UNAVAILABLE,
    }

    for exc_type, status_code in status_map.items():
        if isinstance(exc, exc_type):
            return status_code

    return status.HTTP_500_INTERNAL_SERVER_ERROR
