"""Bank import API endpoints and bank-statement workbench routes."""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.error_messages import get_error_message
from app.core.security import get_current_user
from app.db.base import get_db
from app.models.bank_statement_import import BankStatementImport, BankStatementLine
from app.models.document import Document
from app.models.user import User
from app.services.bank_import_service import BankImportService, ImportFormat
from app.services.credit_service import CreditService, InsufficientCreditsError
from app.services.csv_parser import BankFormat

logger = logging.getLogger(__name__)

router = APIRouter()


class MatchExistingRequest(BaseModel):
    transaction_id: Optional[int] = None


def _serialize_transaction_summary(transaction) -> Optional[Dict[str, Any]]:
    if transaction is None:
        return None
    return {
        "id": transaction.id,
        "type": transaction.type.value if getattr(transaction, "type", None) is not None else None,
        "amount": str(transaction.amount),
        "transaction_date": transaction.transaction_date.isoformat() if transaction.transaction_date else None,
        "description": transaction.description,
        "income_category": getattr(transaction, "income_category", None),
        "expense_category": getattr(transaction, "expense_category", None),
        "classification_confidence": (
            str(transaction.classification_confidence)
            if getattr(transaction, "classification_confidence", None) is not None
            else None
        ),
        "bank_reconciled": bool(getattr(transaction, "bank_reconciled", False)),
        "bank_reconciled_at": (
            transaction.bank_reconciled_at.isoformat()
            if getattr(transaction, "bank_reconciled_at", None) is not None
            else None
        ),
    }


def _serialize_line(line: BankStatementLine) -> Dict[str, Any]:
    return {
        "id": line.id,
        "line_date": line.line_date.isoformat() if line.line_date else None,
        "amount": str(line.amount if isinstance(line.amount, Decimal) else Decimal(str(line.amount))),
        "counterparty": line.counterparty,
        "purpose": line.purpose,
        "raw_reference": line.raw_reference,
        "normalized_fingerprint": line.normalized_fingerprint,
        "review_status": line.review_status.value if line.review_status else None,
        "suggested_action": line.suggested_action.value if line.suggested_action else None,
        "confidence_score": (
            str(line.confidence_score)
            if line.confidence_score is not None
            else None
        ),
        "linked_transaction_id": line.linked_transaction_id,
        "created_transaction_id": line.created_transaction_id,
        "reviewed_at": line.reviewed_at.isoformat() if line.reviewed_at else None,
        "reviewed_by": line.reviewed_by,
        "linked_transaction": _serialize_transaction_summary(line.linked_transaction),
        "created_transaction": _serialize_transaction_summary(line.created_transaction),
    }


def _build_import_summary(statement_import: BankStatementImport) -> Dict[str, int]:
    lines = list(statement_import.lines)
    return {
        "total_count": len(lines),
        "auto_created_count": sum(1 for line in lines if line.review_status and line.review_status.value == "auto_created"),
        "matched_existing_count": sum(1 for line in lines if line.review_status and line.review_status.value == "matched_existing"),
        "pending_review_count": sum(1 for line in lines if line.review_status and line.review_status.value == "pending_review"),
        "ignored_count": sum(1 for line in lines if line.review_status and line.review_status.value == "ignored_duplicate"),
    }


def _serialize_import(statement_import: BankStatementImport) -> Dict[str, Any]:
    summary = _build_import_summary(statement_import)
    return {
        "id": statement_import.id,
        "source_type": statement_import.source_type.value if statement_import.source_type else None,
        "source_document_id": statement_import.source_document_id,
        "bank_name": statement_import.bank_name,
        "iban": statement_import.iban,
        "statement_period": statement_import.statement_period,
        "tax_year": statement_import.tax_year,
        "created_at": statement_import.created_at.isoformat() if statement_import.created_at else None,
        "updated_at": statement_import.updated_at.isoformat() if statement_import.updated_at else None,
        **summary,
    }


def _read_uploaded_text(file_content: bytes) -> str:
    try:
        return file_content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return file_content.decode("iso-8859-1")
        except Exception as exc:
            logger.exception("Failed to decode uploaded bank file")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_decode_error",
            ) from exc


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
    """Import a bank statement and create a persisted workbench batch."""

    language = getattr(current_user, "language", "de") or "de"
    if import_format == ImportFormat.CSV and not file.filename.endswith((".csv", ".CSV")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_error_message("file_must_have_csv_extension", language),
        )
    if import_format == ImportFormat.MT940 and not file.filename.endswith((".mt940", ".MT940", ".sta", ".STA", ".txt", ".TXT")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_error_message("file_must_have_mt940_extension", language),
        )

    credit_service = CreditService(db, redis_client=None)
    try:
        deduction = credit_service.check_and_deduct(
            user_id=current_user.id,
            operation="bank_import",
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: {exc.required} required, {exc.available} available",
        ) from exc

    try:
        text_content = _read_uploaded_text(await file.read())
        result = BankImportService(db=db).import_transactions(
            file_content=text_content,
            import_format=import_format,
            user=current_user,
            tax_year=tax_year,
            auto_classify=auto_classify,
            skip_duplicates=skip_duplicates,
            bank_format=bank_format,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Bank import failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="import_failed",
        ) from exc

    response.headers["X-Credits-Remaining"] = str(deduction.balance_after.available_without_overage)
    return {
        "success": True,
        "message": f"Imported {result.total_count} bank statement lines",
        **result.to_dict(),
    }


@router.post("/preview", summary="Preview bank statement import")
async def preview_import(
    file: UploadFile = File(..., description="Bank statement file (CSV or MT940)"),
    import_format: ImportFormat = Form(..., description="File format (csv or mt940)"),
    bank_format: Optional[BankFormat] = Form(None, description="Specific bank format for CSV"),
    current_user: User = Depends(get_current_user),
):
    """Preview a bank import without persisting it."""

    try:
        text_content = _read_uploaded_text(await file.read())
        preview = BankImportService(db=None).preview_import(
            file_content=text_content,
            import_format=import_format,
            bank_format=bank_format,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Bank import preview failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="import_failed",
        ) from exc

    if not preview["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=preview.get("error", "Invalid file format"),
        )

    return {
        "success": True,
        "preview": preview,
    }


@router.post("/document/{document_id}/initialize", summary="Initialize bank-statement workbench from a document")
def initialize_document_import(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        statement_import = BankImportService(db=db).initialize_document_import(document=document, user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to initialize bank-statement workbench")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="import_failed") from exc

    return {
        "success": True,
        "import": _serialize_import(statement_import),
    }


@router.get("/imports/{import_id}", summary="Get bank statement import summary")
def get_import(
    import_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        statement_import = BankImportService(db=db).get_import_for_user(import_id=import_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {
        "success": True,
        "import": _serialize_import(statement_import),
    }


@router.get("/imports/{import_id}/lines", summary="Get bank statement import lines")
def get_import_lines(
    import_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        lines = BankImportService(db=db).get_lines_for_import(import_id=import_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {
        "success": True,
        "lines": [_serialize_line(line) for line in lines],
    }


@router.post("/lines/{line_id}/confirm-create", summary="Confirm creating a new transaction from a bank line")
def confirm_create_line(
    line_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        line, transaction = BankImportService(db=db).confirm_create_line(line_id=line_id, user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "success": True,
        "line": _serialize_line(line),
        "transaction": _serialize_transaction_summary(transaction),
    }


@router.post("/lines/{line_id}/match-existing", summary="Match a bank line to an existing transaction")
def match_existing_line(
    line_id: int,
    payload: MatchExistingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        line, transaction = BankImportService(db=db).match_existing_line(
            line_id=line_id,
            user=current_user,
            transaction_id=payload.transaction_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "success": True,
        "line": _serialize_line(line),
        "transaction": _serialize_transaction_summary(transaction),
    }


@router.post("/lines/{line_id}/ignore", summary="Ignore a bank line as duplicate")
def ignore_line(
    line_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        line = BankImportService(db=db).ignore_line(line_id=line_id, user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "success": True,
        "line": _serialize_line(line),
    }


@router.get("/formats", summary="Get supported bank formats")
async def get_supported_formats():
    """Get supported bank import formats."""

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
