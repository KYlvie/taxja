"""
Bank Import API Endpoints

Endpoints for importing transactions from bank statements.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from typing import Optional

from app.services.bank_import_service import BankImportService, ImportFormat
from app.services.csv_parser import BankFormat
from app.models.user import User
from app.core.security import get_current_user


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
    if import_format == ImportFormat.CSV:
        if not file.filename.endswith(('.csv', '.CSV')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must have .csv extension for CSV format"
            )
    elif import_format == ImportFormat.MT940:
        if not file.filename.endswith(('.mt940', '.MT940', '.sta', '.STA', '.txt', '.TXT')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must have .mt940, .sta, or .txt extension for MT940 format"
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to decode file: {str(e)}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )
    
    # Import transactions
    import_service = BankImportService()
    
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to decode file: {str(e)}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )
    
    # Preview import
    import_service = BankImportService()
    
    try:
        preview = import_service.preview_import(
            file_content=file_content,
            import_format=import_format,
            bank_format=bank_format,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview failed: {str(e)}"
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
