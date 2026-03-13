"""Historical data import API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from uuid import UUID
import logging

from app.db.base import get_db
from app.models.user import User
from app.models.historical_import import (
    HistoricalImportSession,
    HistoricalImportUpload,
    HistoricalDocumentType,
    ImportStatus,
    ImportSessionStatus,
)
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# File upload constraints
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def validate_historical_file(file: UploadFile, document_type: str) -> None:
    """Validate uploaded file format and size for historical import"""
    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format. Allowed: PDF, CSV, Excel. Got: {file.content_type}",
        )
    
    # Saldenliste must be CSV or Excel
    if document_type == "saldenliste" and file.content_type == "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Saldenliste must be CSV or Excel format, not PDF",
        )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_historical_document(
    file: UploadFile = File(...),
    document_type: str = None,
    tax_year: int = None,
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document for historical data import
    
    - Validates file format and size
    - Creates HistoricalImportUpload record
    - Triggers OCR/extraction processing asynchronously
    - Returns upload confirmation with task ID
    
    **Parameters:**
    - file: Document file (PDF, CSV, or Excel)
    - document_type: Type of document (e1_form, bescheid, kaufvertrag, saldenliste)
    - tax_year: Tax year for the document (2000-2030)
    - session_id: Optional session ID for multi-document imports
    """
    # Validate required parameters
    if not document_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_type is required",
        )
    
    if not tax_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tax_year is required",
        )
    
    # Validate document type
    try:
        doc_type = HistoricalDocumentType(document_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type. Must be one of: {', '.join([t.value for t in HistoricalDocumentType])}",
        )
    
    # Validate tax year
    current_year = datetime.now().year
    if tax_year < 2000 or tax_year > 2030:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tax_year. Must be between 2000 and 2030. Got: {tax_year}",
        )
    
    if tax_year > current_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tax year cannot be in the future. Current year: {current_year}",
        )
    
    if tax_year < current_year - 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tax year too old (max 10 years). Minimum year: {current_year - 10}",
        )
    
    # Validate file
    validate_historical_file(file, document_type)
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Check file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: 50MB. Got: {file_size / 1024 / 1024:.2f}MB",
        )
    
    # Validate session if provided
    session = None
    if session_id:
        try:
            session_uuid = UUID(session_id)
            session = (
                db.query(HistoricalImportSession)
                .filter(
                    HistoricalImportSession.id == session_uuid,
                    HistoricalImportSession.user_id == current_user.id,
                )
                .first()
            )
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session not found: {session_id}",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid session_id format: {session_id}",
            )
    
    # TODO: Upload file to storage (will be implemented with StorageService integration)
    # For now, we'll create a placeholder document record
    
    # TODO: Create Document record (will be integrated with existing Document model)
    # Placeholder document_id for now
    document_id = 1
    
    # Create HistoricalImportUpload record
    upload = HistoricalImportUpload(
        session_id=session.id if session else None,
        user_id=current_user.id,
        document_id=document_id,
        document_type=doc_type,
        tax_year=tax_year,
        status=ImportStatus.UPLOADED,
    )
    
    db.add(upload)
    
    # Update session metrics if part of a session
    if session:
        session.total_documents += 1
    
    db.commit()
    db.refresh(upload)
    
    # Trigger OCR/extraction processing asynchronously
    from app.tasks.ocr_tasks import process_historical_import_ocr
    
    task = process_historical_import_ocr.delay(str(upload.id))
    
    # Update upload with task ID
    upload.ocr_task_id = task.id
    db.commit()
    
    logger.info(
        f"Historical import upload created: {upload.id} "
        f"(type={document_type}, year={tax_year}, user={current_user.id}, task={task.id})"
    )
    
    # Estimate completion time based on document type (rough estimates)
    from datetime import timedelta
    estimated_seconds = {
        "e1_form": 60,
        "bescheid": 60,
        "kaufvertrag": 45,
        "saldenliste": 30,
    }
    estimated_completion = datetime.utcnow() + timedelta(
        seconds=estimated_seconds.get(document_type, 60)
    )
    
    return {
        "upload_id": str(upload.id),
        "document_id": document_id,
        "status": upload.status.value,
        "task_id": task.id,
        "estimated_completion": estimated_completion.isoformat(),
        "message": "Document uploaded successfully. Processing has started.",
    }


@router.get("/status/{upload_id}")
def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check the status of a document import
    
    - Returns current processing status
    - Includes extracted data if available
    - Shows confidence scores and errors
    
    **Parameters:**
    - upload_id: UUID of the upload to check
    """
    # Parse and validate upload_id
    try:
        upload_uuid = UUID(upload_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid upload_id format: {upload_id}",
        )
    
    # Fetch upload record
    upload = (
        db.query(HistoricalImportUpload)
        .filter(
            HistoricalImportUpload.id == upload_uuid,
            HistoricalImportUpload.user_id == current_user.id,
        )
        .first()
    )
    
    if not upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload not found: {upload_id}",
        )
    
    # Calculate progress percentage based on status
    progress_map = {
        ImportStatus.UPLOADED: 10,
        ImportStatus.PROCESSING: 50,
        ImportStatus.EXTRACTED: 80,
        ImportStatus.REVIEW_REQUIRED: 90,
        ImportStatus.APPROVED: 100,
        ImportStatus.REJECTED: 100,
        ImportStatus.FAILED: 0,
    }
    progress = progress_map.get(upload.status, 0)
    
    # Prepare response
    response = {
        "upload_id": str(upload.id),
        "status": upload.status.value,
        "progress": progress,
        "extraction_data": upload.edited_data or upload.extracted_data,
        "confidence": float(upload.extraction_confidence) if upload.extraction_confidence else None,
        "errors": upload.errors,
        "requires_review": upload.requires_review,
        "created_at": upload.created_at.isoformat(),
        "updated_at": upload.updated_at.isoformat(),
    }
    
    return response


@router.post("/session", status_code=status.HTTP_201_CREATED)
def create_import_session(
    tax_years: list[int],
    document_types: Optional[list[str]] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a multi-document import session
    
    - Groups related documents together
    - Tracks overall import progress
    - Enables batch operations and conflict detection
    
    **Parameters:**
    - tax_years: List of tax years to import (e.g., [2021, 2022, 2023])
    - document_types: Optional list of expected document types
    """
    # Validate tax years
    if not tax_years or len(tax_years) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one tax year is required",
        )
    
    current_year = datetime.now().year
    for year in tax_years:
        if year < 2000 or year > 2030:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tax year: {year}. Must be between 2000 and 2030",
            )
        if year > current_year:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tax year cannot be in the future: {year}",
            )
    
    # Validate document types if provided
    if document_types:
        for doc_type in document_types:
            try:
                HistoricalDocumentType(doc_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid document_type: {doc_type}",
                )
    
    # Create session
    session = HistoricalImportSession(
        user_id=current_user.id,
        status=ImportSessionStatus.ACTIVE,
        tax_years=tax_years,
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Calculate expected documents if document types provided
    expected_documents = len(tax_years) * len(document_types) if document_types else 0
    
    logger.info(
        f"Historical import session created: {session.id} "
        f"(years={tax_years}, user={current_user.id})"
    )
    
    return {
        "session_id": str(session.id),
        "status": session.status.value,
        "tax_years": session.tax_years,
        "expected_documents": expected_documents,
        "uploaded_documents": 0,
        "created_at": session.created_at.isoformat(),
    }


@router.get("/session/{session_id}")
def get_session_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get session status and summary
    
    - Shows all documents in the session
    - Provides aggregate metrics
    - Lists any conflicts detected
    
    **Parameters:**
    - session_id: UUID of the session to retrieve
    """
    # Parse and validate session_id
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid session_id format: {session_id}",
        )
    
    # Fetch session record
    session = (
        db.query(HistoricalImportSession)
        .filter(
            HistoricalImportSession.id == session_uuid,
            HistoricalImportSession.user_id == current_user.id,
        )
        .first()
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    
    # Build document list
    documents = []
    for upload in session.uploads:
        documents.append({
            "upload_id": str(upload.id),
            "document_type": upload.document_type.value,
            "tax_year": upload.tax_year,
            "status": upload.status.value,
            "confidence": float(upload.extraction_confidence) if upload.extraction_confidence else None,
            "requires_review": upload.requires_review,
            "created_at": upload.created_at.isoformat(),
        })
    
    # Build conflicts list
    conflicts = []
    for conflict in session.conflicts:
        conflicts.append({
            "conflict_id": conflict.id,
            "conflict_type": conflict.conflict_type,
            "field_name": conflict.field_name,
            "upload_id_1": str(conflict.upload_id_1),
            "upload_id_2": str(conflict.upload_id_2),
            "value_1": conflict.value_1,
            "value_2": conflict.value_2,
            "resolution": conflict.resolution,
            "resolved": conflict.resolved_at is not None,
        })
    
    # Build summary
    summary = {
        "total_transactions": session.transactions_created,
        "total_properties": session.properties_created,
        "properties_linked": session.properties_linked,
        "successful_imports": session.successful_imports,
        "failed_imports": session.failed_imports,
        "conflicts_detected": len(conflicts),
    }
    
    return {
        "session_id": str(session.id),
        "status": session.status.value,
        "tax_years": session.tax_years,
        "documents": documents,
        "conflicts": conflicts,
        "summary": summary,
        "created_at": session.created_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
    }


@router.post("/review/{upload_id}")
def review_upload(
    upload_id: str,
    approved: bool,
    edited_data: Optional[dict] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Review and approve/reject an import
    
    - Allows user to edit extracted data
    - Approves import to create transactions/properties
    - Rejects import to clean up and allow re-import
    
    **Parameters:**
    - upload_id: UUID of the upload to review
    - approved: True to approve, False to reject
    - edited_data: Optional corrected extraction data
    - notes: Optional review notes
    """
    # Parse and validate upload_id
    try:
        upload_uuid = UUID(upload_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid upload_id format: {upload_id}",
        )
    
    # Fetch upload record
    upload = (
        db.query(HistoricalImportUpload)
        .filter(
            HistoricalImportUpload.id == upload_uuid,
            HistoricalImportUpload.user_id == current_user.id,
        )
        .first()
    )
    
    if not upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload not found: {upload_id}",
        )
    
    # Check if upload is in a reviewable state
    if upload.status not in [ImportStatus.EXTRACTED, ImportStatus.REVIEW_REQUIRED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload cannot be reviewed in current status: {upload.status.value}",
        )
    
    # Store edited data if provided
    if edited_data:
        upload.edited_data = edited_data
    
    # Store review metadata
    upload.reviewed_at = datetime.utcnow()
    upload.reviewed_by = current_user.id
    upload.approval_notes = notes
    
    if approved:
        upload.status = ImportStatus.APPROVED

        # Finalize import — create transactions from extracted/edited data
        final_data = upload.edited_data or upload.extracted_data or {}
        created_txn_ids = []

        try:
            from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
            from decimal import Decimal
            from datetime import date as date_type

            items = final_data.get("transactions") or final_data.get("items") or []
            # If the extracted data is a flat dict (e.g. Bescheid), wrap it as a single item
            if not items and final_data.get("amount"):
                items = [final_data]

            for item in items:
                amount = item.get("amount")
                if amount is None:
                    continue

                txn_type_str = item.get("type", item.get("transaction_type", "expense"))
                txn_type = (
                    TransactionType.INCOME if txn_type_str == "income" else TransactionType.EXPENSE
                )

                # Parse date
                txn_date_str = item.get("date", item.get("transaction_date"))
                if txn_date_str:
                    try:
                        txn_date = date_type.fromisoformat(str(txn_date_str)[:10])
                    except (ValueError, TypeError):
                        txn_date = date_type(upload.tax_year, 12, 31)
                else:
                    txn_date = date_type(upload.tax_year, 12, 31)

                # Resolve categories
                income_cat = None
                expense_cat = None
                cat_str = item.get("category", "")
                if txn_type == TransactionType.INCOME:
                    try:
                        income_cat = IncomeCategory(cat_str)
                    except ValueError:
                        income_cat = IncomeCategory.OTHER_INCOME if hasattr(IncomeCategory, "OTHER_INCOME") else None
                else:
                    try:
                        expense_cat = ExpenseCategory(cat_str)
                    except ValueError:
                        expense_cat = ExpenseCategory.OTHER if hasattr(ExpenseCategory, "OTHER") else None

                txn = Transaction(
                    user_id=current_user.id,
                    type=txn_type,
                    amount=Decimal(str(abs(float(amount)))),
                    transaction_date=txn_date,
                    description=item.get("description", f"Historical import ({upload.document_type.value})"),
                    income_category=income_cat,
                    expense_category=expense_cat,
                    is_deductible=item.get("is_deductible", False),
                    document_id=upload.document_id,
                    classification_confidence=Decimal("1.00"),
                    needs_review=False,
                )
                db.add(txn)
                db.flush()
                created_txn_ids.append(txn.id)

            upload.transactions_created = created_txn_ids
        except Exception as e:
            logger.error(f"Error creating transactions for import {upload.id}: {e}", exc_info=True)
            upload.errors = list(upload.errors or []) + [{"stage": "finalize", "error": str(e)}]

        # Update session metrics if part of a session
        if upload.session:
            upload.session.successful_imports += 1

        db.commit()
        logger.info(f"Historical import approved: {upload.id} (user={current_user.id}), {len(created_txn_ids)} transactions created")

        return {
            "import_id": str(upload.id),
            "transactions_created": len(created_txn_ids),
            "properties_created": len(upload.properties_created),
            "properties_linked": len(upload.properties_linked),
            "summary": {
                "status": "approved",
                "message": f"Import approved. {len(created_txn_ids)} transactions created.",
            },
        }
    else:
        upload.status = ImportStatus.REJECTED

        # Clean up any previously created entities
        if upload.transactions_created:
            from app.models.transaction import Transaction

            db.query(Transaction).filter(
                Transaction.id.in_(upload.transactions_created)
            ).delete(synchronize_session=False)
            upload.transactions_created = []

        # Update session metrics if part of a session
        if upload.session:
            upload.session.failed_imports += 1

        db.commit()
        logger.info(f"Historical import rejected: {upload.id} (user={current_user.id})")

        return {
            "import_id": str(upload.id),
            "summary": {
                "status": "rejected",
                "message": "Import rejected. You can re-upload the document to try again.",
            },
        }
