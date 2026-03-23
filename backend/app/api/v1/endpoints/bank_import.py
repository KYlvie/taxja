"""
Bank Import API Endpoints

Endpoints for importing transactions from bank statements.
"""

import logging
from fastapi import APIRouter, Depends, Response, UploadFile, File, Form, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.error_messages import get_error_message
from app.services.bank_import_service import BankImportService, ImportFormat
from app.services.csv_parser import BankFormat
from app.services.credit_service import CreditService, InsufficientCreditsError
from app.models.user import User
from app.core.security import get_current_user
from app.db.base import get_db


router = APIRouter()


@router.post("/import", summary="Import transactions from bank statement")
async def import_transactions(
    file: UploadFile = File(..., description="Bank statement file (CSV or MT940)"),
    import_format: ImportFormat = Form(..., description="File format (csv or mt940)"),
    tax_year: int = Form(..., description="Tax year for imported transactions"),
    auto_classify: bool = Form(True, description="Auto-classify transactions"),
    skip_duplicates: bool = Form(True, description="Skip duplicate transactions"),
    bank_format: Optional[BankFormat] = Form(None, description="Specific bank format for CSV"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """
    Import transactions from bank statement file
    
    Supports:
    - CSV format (Raiffeisen, Erste Bank, Sparkasse, Bank Austria, Generic)
    - MT940 format (SWIFT standard)
    
    Features:
    - Auto-classification of transactions
    - Duplicate detection
    - Validation and error reporting
    
    Returns:
    - Import summary with counts
    - List of imported transactions
    - List of duplicates (if any)
    - List of errors (if any)
    """
    
    # Validate file format
    language = getattr(current_user, 'language', 'de') or 'de'
    if import_format == ImportFormat.CSV:
        if not file.filename.endswith(('.csv', '.CSV')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_error_message("file_must_have_csv_extension", language)
            )
    elif import_format == ImportFormat.MT940:
        if not file.filename.endswith(('.mt940', '.MT940', '.sta', '.STA', '.txt', '.TXT')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_error_message("file_must_have_mt940_extension", language)
            )
    
    # --- Credit deduction ---
    credit_service = CreditService(db, redis_client=None)
    try:
        deduction = credit_service.check_and_deduct(
            user_id=current_user.id,
            operation="bank_import",
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: {e.required} required, {e.available} available",
        )

    # Read file content
    try:
        content = await file.read()
        file_content = content.decode('utf-8')
    except UnicodeDecodeError:
        # Try with different encodings
        try:
            file_content = content.decode('iso-8859-1')
        except Exception as e:
            logger.exception("Failed to decode uploaded bank file")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_decode_error"
            )
    except Exception as e:
        logger.exception("Failed to read uploaded bank file")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="import_failed"
        )

    # Import transactions
    import_service = BankImportService(db=db)
    
    try:
        result = import_service.import_transactions(
            file_content=file_content,
            import_format=import_format,
            user=current_user,
            tax_year=tax_year,
            auto_classify=auto_classify,
            skip_duplicates=skip_duplicates,
            bank_format=bank_format,
        )
    except Exception as e:
        logger.exception("Bank import failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="import_failed"
        )
    
    response.headers["X-Credits-Remaining"] = str(
        deduction.balance_after.available_without_overage
    )

    return {
        "success": True,
        "message": f"Imported {result.imported_count} of {result.total_count} transactions",
        "result": result.to_dict(),
    }


@router.post("/preview", summary="Preview bank statement import")
async def preview_import(
    file: UploadFile = File(..., description="Bank statement file (CSV or MT940)"),
    import_format: ImportFormat = Form(..., description="File format (csv or mt940)"),
    bank_format: Optional[BankFormat] = Form(None, description="Specific bank format for CSV"),
    current_user: User = Depends(get_current_user),
):
    """
    Preview bank statement import without saving to database
    
    Returns:
    - Transaction count
    - Date range
    - Total income and expenses
    - Sample transactions
    - Detected format (for CSV)
    
    Use this endpoint to validate the file before importing.
    """
    
    # Read file content
    try:
        content = await file.read()
        file_content = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            file_content = content.decode('iso-8859-1')
        except Exception as e:
            logger.exception("Failed to decode uploaded bank file for preview")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_decode_error"
            )
    except Exception as e:
        logger.exception("Failed to read uploaded bank file for preview")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="import_failed"
        )

    # Preview import
    import_service = BankImportService(db=None)
    
    try:
        preview = import_service.preview_import(
            file_content=file_content,
            import_format=import_format,
            bank_format=bank_format,
        )
    except Exception as e:
        logger.exception("Bank import preview failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="import_failed"
        )
    
    if not preview["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=preview.get("error", "Invalid file format")
        )
    
    return {
        "success": True,
        "preview": preview,
    }


@router.get("/formats", summary="Get supported bank formats")
async def get_supported_formats():
    """
    Get list of supported bank formats and import formats
    
    Returns:
    - List of supported CSV bank formats
    - List of supported import formats
    - Format descriptions
    """
    
    return {
        "import_formats": [
            {
                "value": "csv",
                "label": "CSV",
                "description": "Comma-separated values format",
                "extensions": [".csv"],
            },
            {
                "value": "mt940",
                "label": "MT940",
                "description": "SWIFT MT940 standard format",
                "extensions": [".mt940", ".sta", ".txt"],
            },
        ],
        "bank_formats": [
            {
                "value": "raiffeisen",
                "label": "Raiffeisen",
                "description": "Raiffeisen Bank CSV format",
            },
            {
                "value": "erste_bank",
                "label": "Erste Bank",
                "description": "Erste Bank CSV format",
            },
            {
                "value": "sparkasse",
                "label": "Sparkasse",
                "description": "Sparkasse CSV format",
            },
            {
                "value": "bank_austria",
                "label": "Bank Austria",
                "description": "Bank Austria CSV format",
            },
            {
                "value": "generic",
                "label": "Generic",
                "description": "Generic CSV format (auto-detect)",
            },
        ],
    }
