"""Document management API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import io
import logging
import threading

logger = logging.getLogger(__name__)

from app.db.base import get_db
from app.models.document import Document, DocumentType
from app.models.user import User
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentDetail,
    DocumentList,
    DocumentSearchParams,
    BatchUploadResponse,
)
from app.schemas.ocr_review import (
    OCRReviewResponse,
    OCRCorrectionRequest,
    OCRCorrectionResponse,
    OCRConfirmRequest,
    OCRConfirmResponse,
    OCRFieldConfidence,
    OCRQualityFeedback,
    OCRErrorResponse,
    OCRRetakeGuidance,
)
from app.services.storage_service import StorageService
from app.tasks.ocr_tasks import process_document_ocr, run_ocr_sync, run_ocr_pipeline
from app.core.security import get_current_user

router = APIRouter()

# Lazy initialization of storage service
_storage_service = None


def get_storage_service() -> StorageService:
    """Get or create the storage service instance"""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


# Allowed file types
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/pdf",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_file(file: UploadFile) -> None:
    """Validate uploaded file format and size"""
    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format. Allowed: JPEG, PNG, PDF. Got: {file.content_type}",
        )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a single document (JPEG, PNG, or PDF)
    
    - Validates file format and size
    - Stores file in MinIO with AES-256 encryption
    - Saves document metadata in database
    - Triggers OCR processing asynchronously
    """
    # Validate file
    validate_file(file)
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Check file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: 10MB. Got: {file_size / 1024 / 1024:.2f}MB",
        )
    
    # Generate unique file path
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = f"users/{current_user.id}/documents/{unique_filename}"
    
    # Upload to storage
    storage_service = get_storage_service()
    success = storage_service.upload_file(
        file_bytes=file_content,
        file_path=file_path,
        content_type=file.content_type,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage",
        )
    
    # Create document record
    document = Document(
        user_id=current_user.id,
        document_type=DocumentType.OTHER,  # Will be classified by OCR
        file_path=file_path,
        file_name=file.filename,
        file_size=file_size,
        mime_type=file.content_type,
        uploaded_at=datetime.utcnow(),
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Run OCR in background via FastAPI BackgroundTasks (reliable, not killed on reload)
    def _background_ocr(doc_id: int):
        try:
            logger.info(f"Background OCR pipeline starting for document {doc_id}")
            run_ocr_pipeline(doc_id)
            logger.info(f"Background OCR pipeline completed for document {doc_id}")
        except Exception as ocr_err:
            logger.warning(f"Pipeline failed for document {doc_id}, falling back to legacy: {ocr_err}")
            try:
                run_ocr_sync(doc_id)
            except Exception as legacy_err:
                logger.error(f"Legacy OCR also failed for document {doc_id}: {legacy_err}")

    background_tasks.add_task(_background_ocr, document.id)
    
    return DocumentUploadResponse(
        id=document.id,
        file_name=document.file_name,
        file_size=document.file_size,
        mime_type=document.mime_type,
        document_type=document.document_type,
        uploaded_at=document.uploaded_at,
        message="Document uploaded successfully. OCR processing started.",
    )


@router.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload multiple documents in batch
    
    - Processes multiple files in parallel
    - Returns individual status for each file
    - Continues processing even if some files fail
    """
    successful = []
    failed = []
    
    for file in files:
        try:
            # Validate file
            validate_file(file)
            
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            
            # Check file size
            if file_size > MAX_FILE_SIZE:
                failed.append({
                    "file_name": file.filename,
                    "error": f"File too large: {file_size / 1024 / 1024:.2f}MB (max 10MB)",
                })
                continue
            
            # Generate unique file path
            file_extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_path = f"users/{current_user.id}/documents/{unique_filename}"
            
            # Upload to storage
            storage_service = get_storage_service()
            success = storage_service.upload_file(
                file_bytes=file_content,
                file_path=file_path,
                content_type=file.content_type,
            )
            
            if not success:
                failed.append({
                    "file_name": file.filename,
                    "error": "Failed to upload to storage",
                })
                continue
            
            # Create document record
            document = Document(
                user_id=current_user.id,
                document_type=DocumentType.OTHER,
                file_path=file_path,
                file_name=file.filename,
                file_size=file_size,
                mime_type=file.content_type,
                uploaded_at=datetime.utcnow(),
            )
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            # Run OCR in background via FastAPI BackgroundTasks
            def _batch_ocr(doc_id: int):
                try:
                    logger.info(f"Background OCR pipeline starting for batch document {doc_id}")
                    run_ocr_pipeline(doc_id)
                    logger.info(f"Background OCR pipeline completed for batch document {doc_id}")
                except Exception as ocr_err:
                    logger.warning(f"Pipeline failed for batch doc {doc_id}, falling back: {ocr_err}")
                    try:
                        run_ocr_sync(doc_id)
                    except Exception as legacy_err:
                        logger.error(f"Legacy OCR also failed for batch doc {doc_id}: {legacy_err}")

            background_tasks.add_task(_batch_ocr, document.id)
            
            successful.append(
                DocumentUploadResponse(
                    id=document.id,
                    file_name=document.file_name,
                    file_size=document.file_size,
                    mime_type=document.mime_type,
                    document_type=document.document_type,
                    uploaded_at=document.uploaded_at,
                )
            )
            
        except HTTPException as e:
            failed.append({
                "file_name": file.filename,
                "error": e.detail,
            })
        except Exception as e:
            failed.append({
                "file_name": file.filename,
                "error": str(e),
            })
    
    return BatchUploadResponse(
        total_uploaded=len(successful),
        successful=successful,
        failed=failed,
        message=f"Uploaded {len(successful)} of {len(files)} documents successfully",
    )


@router.get("", response_model=DocumentList)
def get_documents(
    document_type: Optional[DocumentType] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    transaction_id: Optional[int] = Query(None),
    search_text: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get list of documents with filtering and search
    
    - Filter by document type, date range, transaction
    - Full-text search on OCR text
    - Paginated results
    """
    query = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.is_archived == False,
    )
    
    # Apply filters
    if document_type:
        query = query.filter(Document.document_type == document_type)
    
    if start_date:
        query = query.filter(Document.uploaded_at >= start_date)
    
    if end_date:
        query = query.filter(Document.uploaded_at <= end_date)
    
    if transaction_id:
        query = query.filter(Document.transaction_id == transaction_id)
    
    if search_text:
        # Full-text search on raw OCR text
        query = query.filter(Document.raw_text.ilike(f"%{search_text}%"))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    documents = query.order_by(Document.uploaded_at.desc()).offset(offset).limit(page_size).all()
    
    return DocumentList(
        documents=[DocumentDetail.from_orm(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/archived", response_model=DocumentList)
def get_archived_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all archived documents for the current user"""
    from app.services.document_archival_service import DocumentArchivalService
    
    archival_service = DocumentArchivalService(db)
    
    # Get archived documents
    offset = (page - 1) * page_size
    query = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .filter(Document.is_archived == True)
        .order_by(Document.archived_at.desc())
    )
    
    total = query.count()
    documents = query.offset(offset).limit(page_size).all()
    
    return DocumentList(
        documents=[DocumentDetail.from_orm(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/retention-stats")
def get_retention_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get document retention statistics for the current user"""
    from app.services.document_archival_service import DocumentArchivalService
    
    archival_service = DocumentArchivalService(db)
    stats = archival_service.get_retention_statistics(user_id=current_user.id)
    
    return stats


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific document"""
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return DocumentDetail.from_orm(document)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download original document file
    
    - Streams file from MinIO storage
    - Returns file with original filename
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Download from storage
    storage_service = get_storage_service()
    file_bytes = storage_service.download_file(document.file_path)
    
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file from storage",
        )
    
    # Stream file
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.file_name}"'
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    delete_mode: str = Query(
        "document_only",
        description="Deletion mode: 'document_only' (keep data) or 'with_data' (delete all related data)"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a document with optional data cleanup.
    
    **Deletion Modes:**
    
    1. **document_only** (default, recommended):
       - Deletes the document file and record
       - Keeps all related data (property, transactions, recurring transactions)
       - Unlinks the document from related records
       - Safe option for cleaning up files while preserving tax data
    
    2. **with_data** (destructive):
       - Deletes the document file and record
       - Deletes all related data:
         - Property records (for Kaufvertrag)
         - Recurring transactions (for Mietvertrag)
         - Linked transactions
       - Use when you want to completely remove all traces
    
    **Example Requests:**
    ```
    # Delete document only (safe)
    DELETE /api/v1/documents/123?delete_mode=document_only
    
    # Delete document and all data (destructive)
    DELETE /api/v1/documents/123?delete_mode=with_data
    ```
    
    **Returns:**
    - 204 No Content on success
    - 404 if document not found
    """
    from app.models.transaction import Transaction
    from app.models.property import Property
    from app.models.recurring_transaction import RecurringTransaction
    from app.services.property_service import PropertyService

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if delete_mode == "with_data":
        # Destructive mode: delete all related data
        logger.info(f"Deleting document {document_id} WITH related data")
        
        # Delete related property if it's a Kaufvertrag
        if document.document_type == "kaufvertrag":
            # Find property linked to this document
            property = db.query(Property).filter(
                Property.kaufvertrag_document_id == document_id
            ).first()
            
            if property:
                logger.info(f"Deleting property {property.id} linked to document {document_id}")
                try:
                    property_service = PropertyService(db)
                    property_service.delete_property(property.id, current_user.id)
                except Exception as e:
                    logger.error(f"Failed to delete property {property.id}: {e}")
                    # Continue with document deletion even if property deletion fails
        
        # Delete related recurring transaction if it's a Mietvertrag
        if document.document_type == "mietvertrag":
            # Find recurring transaction linked to this document
            recurring = db.query(RecurringTransaction).filter(
                RecurringTransaction.mietvertrag_document_id == document_id
            ).first()
            
            if recurring:
                logger.info(f"Deleting recurring transaction {recurring.id} linked to document {document_id}")
                db.delete(recurring)
        
        # Delete all transactions linked to this document
        linked_txns = db.query(Transaction).filter(
            Transaction.document_id == document_id
        ).all()
        
        for txn in linked_txns:
            logger.info(f"Deleting transaction {txn.id} linked to document {document_id}")
            db.delete(txn)
        
        # Also delete transaction that document points to
        if document.transaction_id:
            txn = db.query(Transaction).filter(
                Transaction.id == document.transaction_id
            ).first()
            if txn:
                logger.info(f"Deleting transaction {txn.id} referenced by document {document_id}")
                db.delete(txn)
    
    else:  # document_only mode (default, safe)
        # Safe mode: only unlink, don't delete data
        logger.info(f"Deleting document {document_id} WITHOUT related data (unlink only)")
        
        # Unlink property if it's a Kaufvertrag
        if document.document_type == "kaufvertrag":
            property = db.query(Property).filter(
                Property.kaufvertrag_document_id == document_id
            ).first()
            
            if property:
                logger.info(f"Unlinking property {property.id} from document {document_id}")
                property.kaufvertrag_document_id = None
        
        # Unlink recurring transaction if it's a Mietvertrag
        if document.document_type == "mietvertrag":
            recurring = db.query(RecurringTransaction).filter(
                RecurringTransaction.mietvertrag_document_id == document_id
            ).first()
            
            if recurring:
                logger.info(f"Unlinking recurring transaction {recurring.id} from document {document_id}")
                recurring.mietvertrag_document_id = None
        
        # Unlink all transactions but keep them
        linked_txns = db.query(Transaction).filter(
            Transaction.document_id == document_id
        ).all()
        
        for txn in linked_txns:
            logger.info(f"Unlinking transaction {txn.id} from document {document_id}")
            txn.document_id = None
        
        # Unlink document's own transaction reference
        if document.transaction_id:
            document.transaction_id = None

    db.flush()

    # Try to remove file from storage (best-effort)
    try:
        storage_service = get_storage_service()
        storage_service.delete_file(document.file_path)
        logger.info(f"Deleted file from storage: {document.file_path}")
    except Exception as e:
        logger.warning(f"Failed to delete file from storage for doc {document_id}: {e}")

    # Delete document record
    db.delete(document)
    db.commit()
    
    logger.info(f"Document {document_id} deleted successfully (mode: {delete_mode})")

    return None


@router.get("/{document_id}/related-data")
def get_document_related_data(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get information about data related to a document.
    
    This endpoint helps users understand what data will be affected
    when deleting a document.
    
    **Returns:**
    ```json
    {
      "document_id": 123,
      "document_type": "kaufvertrag",
      "has_related_data": true,
      "related_data": {
        "property": {
          "id": "uuid",
          "address": "Hauptstraße 123, 1010 Wien",
          "purchase_price": 350000.00
        },
        "transactions": [
          {
            "id": 456,
            "description": "Kaufpreis",
            "amount": 350000.00
          }
        ],
        "recurring_transaction": null
      }
    }
    ```
    """
    from app.models.transaction import Transaction
    from app.models.property import Property
    from app.models.recurring_transaction import RecurringTransaction
    from decimal import Decimal

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    related_data = {
        "property": None,
        "transactions": [],
        "recurring_transaction": None
    }
    
    has_related_data = False

    # Check for related property (Kaufvertrag)
    if document.document_type == "kaufvertrag":
        property = db.query(Property).filter(
            Property.kaufvertrag_document_id == document_id
        ).first()
        
        if property:
            has_related_data = True
            related_data["property"] = {
                "id": str(property.id),
                "address": property.address,
                "purchase_price": float(property.purchase_price),
                "purchase_date": property.purchase_date.isoformat()
            }

    # Check for related recurring transaction (Mietvertrag)
    if document.document_type == "mietvertrag":
        recurring = db.query(RecurringTransaction).filter(
            RecurringTransaction.mietvertrag_document_id == document_id
        ).first()
        
        if recurring:
            has_related_data = True
            related_data["recurring_transaction"] = {
                "id": recurring.id,
                "description": recurring.description,
                "amount": float(recurring.amount),
                "frequency": recurring.frequency.value if recurring.frequency else None
            }

    # Check for linked transactions
    linked_txns = db.query(Transaction).filter(
        Transaction.document_id == document_id
    ).all()
    
    if linked_txns:
        has_related_data = True
        related_data["transactions"] = [
            {
                "id": txn.id,
                "description": txn.description,
                "amount": float(txn.amount),
                "date": txn.transaction_date.isoformat()
            }
            for txn in linked_txns
        ]

    # Also check document's own transaction reference
    if document.transaction_id:
        txn = db.query(Transaction).filter(
            Transaction.id == document.transaction_id
        ).first()
        if txn and txn not in linked_txns:
            has_related_data = True
            related_data["transactions"].append({
                "id": txn.id,
                "description": txn.description,
                "amount": float(txn.amount),
                "date": txn.transaction_date.isoformat()
            })

    return {
        "document_id": document_id,
        "document_type": document.document_type,
        "has_related_data": has_related_data,
        "related_data": related_data
    }



@router.post("/{document_id}/archive", status_code=status.HTTP_200_OK)
def archive_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Archive a document
    
    - Marks document as archived for retention
    - Document remains accessible but marked as archived
    """
    from app.services.document_archival_service import DocumentArchivalService
    
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    archival_service = DocumentArchivalService(db)
    success = archival_service.archive_document(document_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to archive document",
        )
    
    return {"message": "Document archived successfully"}


@router.post("/{document_id}/restore", status_code=status.HTTP_200_OK)
def restore_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restore an archived document"""
    from app.services.document_archival_service import DocumentArchivalService
    
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    archival_service = DocumentArchivalService(db)
    success = archival_service.restore_document(document_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore document",
        )
    
    return {"message": "Document restored successfully"}


# NOTE: /archived and /retention-stats moved before /{document_id} to avoid path conflict



@router.get("/{document_id}/transaction-suggestion")
def get_transaction_suggestion(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get transaction suggestion from OCR data
    
    - Analyzes OCR results
    - Suggests transaction type, amount, date, category
    - Indicates if expense is deductible
    - Returns confidence score
    """
    from app.services.ocr_transaction_service import OCRTransactionService
    
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if not document.ocr_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has not been processed by OCR yet",
        )
    
    ocr_service = OCRTransactionService(db)
    suggestion = ocr_service.create_transaction_suggestion(document_id, current_user.id)
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create transaction suggestion from OCR data",
        )
    
    return suggestion


@router.post("/{document_id}/create-transaction")
def create_transaction_from_document(
    document_id: int,
    suggestion: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a transaction from document OCR data
    
    - If suggestion provided, uses that data
    - Otherwise, generates suggestion from OCR and creates transaction
    - Links transaction to document
    """
    from app.services.ocr_transaction_service import OCRTransactionService
    
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    ocr_service = OCRTransactionService(db)
    
    # Generate suggestion if not provided
    if not suggestion:
        suggestion = ocr_service.create_transaction_suggestion(document_id, current_user.id)
        
        if not suggestion:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not create transaction suggestion from OCR data",
            )
    
    # Create transaction
    transaction = ocr_service.create_transaction_from_suggestion(suggestion, current_user.id)
    
    return {
        "message": "Transaction created successfully",
        "transaction_id": transaction.id,
        "document_id": document_id,
    }



# ============================================================================
# OCR Review and Correction Endpoints
# ============================================================================


@router.get("/{document_id}/review", response_model=OCRReviewResponse)
def review_ocr_results(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get OCR results for review
    
    Requirements: 23.1, 23.2
    
    - Returns extracted data with confidence scores
    - Highlights low-confidence fields
    - Provides quality feedback and suggestions
    - Indicates if retake is recommended
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if not document.ocr_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has not been processed by OCR yet. Please wait for processing to complete.",
        )
    
    # Extract field confidences from OCR result
    # The ocr_result may be flat (field: value, field_confidence: score)
    # or nested under "extracted_data"
    extracted_fields = []
    ocr_data = document.ocr_result
    if "extracted_data" in ocr_data:
        ocr_data = ocr_data["extracted_data"]

    # Build confidence map from *_confidence keys or field_confidence dict
    field_confidences = ocr_data.get("confidence", {})
    if not isinstance(field_confidences, dict):
        field_confidences = {}
    if not field_confidences and isinstance(ocr_data.get("field_confidence"), dict):
        field_confidences = ocr_data["field_confidence"]
    skip_keys = {"confidence", "field_confidence", "raw_text", "product_summary",
                 "line_items", "vat_summary", "tax_analysis", "import_suggestion"}

    for field_name, value in ocr_data.items():
        if field_name in skip_keys or field_name.endswith("_confidence"):
            continue
        # Skip non-scalar values (lists, dicts)
        if isinstance(value, (list, dict)):
            continue

        # Look for companion confidence key (e.g. date_confidence)
        conf_key = f"{field_name}_confidence"
        conf_val = ocr_data.get(conf_key)
        if conf_val is not None and isinstance(conf_val, (int, float)):
            field_confidence = float(conf_val)
        elif field_name in field_confidences:
            field_confidence = float(field_confidences[field_name])
        else:
            field_confidence = 0.5
        needs_review = field_confidence < 0.6

        # Convert datetime objects to string for JSON serialization
        display_value = value
        if hasattr(value, "isoformat"):
            display_value = value.isoformat()

        extracted_fields.append(
            OCRFieldConfidence(
                field_name=field_name,
                value=display_value,
                confidence=field_confidence,
                needs_review=needs_review,
            )
        )
    
    # Generate quality feedback
    overall_confidence = document.confidence_score or 0.0
    suggestions = []
    warnings = []
    quality_feedback = None
    
    is_pdf = document.mime_type == "application/pdf" if document.mime_type else False
    if overall_confidence < 0.6:
        quality_feedback = "Low confidence OCR result. Manual review recommended."
        if is_pdf:
            suggestions.append("This is a digital PDF — please verify the extracted fields manually")
            suggestions.append("Some PDF layouts (tables, multi-column) may not extract correctly")
        else:
            suggestions.append("Consider retaking the photo with better lighting")
            suggestions.append("Ensure the document is flat and not skewed")
        suggestions.append("Make sure all text is clearly visible")
        warnings.append("Some fields may be inaccurate")
    elif overall_confidence < 0.8:
        quality_feedback = "Fair OCR result. Please verify extracted data."
        suggestions.append("Double-check highlighted fields")
    else:
        quality_feedback = "Good OCR result. Data appears accurate."
    
    # Add field-specific suggestions
    for field in extracted_fields:
        if field.needs_review:
            suggestions.append(f"Please verify '{field.field_name}' field")
    
    return OCRReviewResponse(
        document_id=document.id,
        document_type=document.document_type,
        file_name=document.file_name,
        uploaded_at=document.uploaded_at,
        processed_at=document.processed_at,
        overall_confidence=overall_confidence,
        needs_review=overall_confidence < 0.6,
        raw_text=document.raw_text or "",
        extracted_fields=extracted_fields,
        suggestions=suggestions,
        warnings=warnings,
        quality_feedback=quality_feedback,
    )


@router.post("/{document_id}/confirm", response_model=OCRConfirmResponse)
def confirm_ocr_results(
    document_id: int,
    request: OCRConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm OCR results are correct
    
    Requirements: 23.3, 23.4, 23.5
    
    - Records user confirmation
    - Timestamps the confirmation
    - Enables transaction creation
    - Stores optional notes
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if not document.ocr_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has not been processed by OCR yet",
        )
    
    # Update OCR result with confirmation
    ocr_result = document.ocr_result or {}
    ocr_result["confirmed"] = request.confirmed
    ocr_result["confirmed_at"] = datetime.utcnow().isoformat()
    ocr_result["confirmed_by"] = current_user.id
    
    if request.notes:
        ocr_result["confirmation_notes"] = request.notes
    
    document.ocr_result = ocr_result
    db.commit()

    # Auto-create transaction if not already linked
    transaction_id = None
    if request.confirmed and not document.transaction_id:
        try:
            from app.services.ocr_transaction_service import OCRTransactionService
            ocr_service = OCRTransactionService(db)
            suggestion = ocr_service.create_transaction_suggestion(document_id, current_user.id)
            if suggestion:
                txn = ocr_service.create_transaction_from_suggestion(suggestion, current_user.id)
                transaction_id = txn.id
        except Exception as e:
            logger.warning(f"Auto-create transaction failed for doc {document_id}: {e}")

    msg = "OCR results confirmed successfully"
    if transaction_id:
        msg += f" and transaction #{transaction_id} created"

    return OCRConfirmResponse(
        document_id=document.id,
        message=msg,
        confirmed_at=datetime.utcnow(),
        can_create_transaction=transaction_id is None,
    )


@router.post("/{document_id}/correct", response_model=OCRCorrectionResponse)
def correct_ocr_results(
    document_id: int,
    request: OCRCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Correct OCR extracted data
    
    Requirements: 23.3, 23.4, 23.5
    
    - Allows user to edit extracted fields
    - Records correction history
    - Updates confidence scores
    - Learns from corrections for ML improvement
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if not document.ocr_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has not been processed by OCR yet",
        )
    
    # Store previous data for learning
    previous_confidence = float(document.confidence_score or 0.0)
    ocr_result = document.ocr_result or {}

    # Handle both flat and nested ocr_result structures
    if "extracted_data" in ocr_result:
        previous_data = ocr_result["extracted_data"].copy()
        extracted_data = ocr_result["extracted_data"]
    else:
        previous_data = {k: v for k, v in ocr_result.items() if not k.endswith("_confidence")}
        extracted_data = ocr_result

    # Extract special meta fields from corrected_data
    user_doc_type = request.corrected_data.pop("_document_type", None)
    user_txn_type = request.corrected_data.pop("_transaction_type", None)

    # Update with corrected data
    updated_fields = []

    for field_name, corrected_value in request.corrected_data.items():
        extracted_data[field_name] = corrected_value
        updated_fields.append(field_name)

    # Write back
    if "extracted_data" in ocr_result:
        ocr_result["extracted_data"] = extracted_data
    else:
        ocr_result.update(extracted_data)
    
    # Update document type from user selection or request field
    effective_doc_type = user_doc_type or (request.document_type if hasattr(request, 'document_type') and request.document_type else None)
    if effective_doc_type and effective_doc_type != str(document.document_type.value if hasattr(document.document_type, 'value') else document.document_type):
        try:
            document.document_type = DocumentType(effective_doc_type)
        except (ValueError, KeyError):
            pass
        updated_fields.append("document_type")
    
    # Record correction history
    if "correction_history" not in ocr_result:
        ocr_result["correction_history"] = []
    
    ocr_result["correction_history"].append({
        "corrected_at": datetime.utcnow().isoformat(),
        "corrected_by": current_user.id,
        "previous_data": previous_data,
        "corrected_fields": updated_fields,
        "notes": request.notes,
    })
    
    # Increase confidence after user correction
    new_confidence = min(1.0, float(previous_confidence) + 0.2)
    document.confidence_score = new_confidence
    document.ocr_result = ocr_result
    
    db.commit()
    
    # Learn from correction (for ML improvement)
    try:
        from app.services.classification_learning import ClassificationLearningService
        learning_service = ClassificationLearningService(db)
        learning_service.record_ocr_correction(
            document_id=document_id,
            previous_data=previous_data,
            corrected_data=request.corrected_data,
            user_id=current_user.id,
        )
    except Exception as e:
        # Don't fail the request if learning fails
        print(f"Failed to record OCR correction for learning: {e}")

    # Auto-create transaction if not already linked
    transaction_id = None
    if not document.transaction_id:
        try:
            from app.services.ocr_transaction_service import OCRTransactionService
            ocr_service = OCRTransactionService(db)
            suggestion = ocr_service.create_transaction_suggestion(document_id, current_user.id)
            if suggestion:
                # Override transaction type if user specified one
                if user_txn_type and user_txn_type in ("income", "expense"):
                    suggestion["transaction_type"] = user_txn_type
                    # Re-classify category based on new type
                    if user_txn_type == "income":
                        suggestion["category"] = "employment"
                        suggestion["is_deductible"] = False
                        suggestion["deduction_reason"] = "Income is not deductible"
                    # expense keeps the auto-classified category
                txn = ocr_service.create_transaction_from_suggestion(suggestion, current_user.id)
                transaction_id = txn.id
        except Exception as e:
            logger.warning(f"Auto-create transaction failed for doc {document_id}: {e}")

    msg = f"OCR data corrected successfully. Updated {len(updated_fields)} field(s)."
    if transaction_id:
        msg += f" Transaction #{transaction_id} created."

    return OCRCorrectionResponse(
        document_id=document.id,
        message=msg,
        updated_fields=updated_fields,
        previous_confidence=previous_confidence,
        new_confidence=new_confidence,
        correction_recorded=True,
    )


@router.get("/{document_id}/quality-feedback", response_model=OCRQualityFeedback)
def get_ocr_quality_feedback(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed quality feedback for OCR results
    
    Requirements: 25.2, 25.3, 25.4, 25.7
    
    - Analyzes OCR confidence scores
    - Provides actionable suggestions
    - Recommends retake if quality is poor
    - Offers manual input option
    """
    from app.services.ocr_quality_service import OCRQualityService
    
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    if not document.ocr_result:
        return OCRQualityFeedback(
            overall_quality="failed",
            confidence_score=0.0,
            issues=["OCR processing has not completed yet"],
            suggestions=["Please wait for OCR processing to complete"],
            retake_recommended=False,
            manual_input_recommended=True,
        )
    
    # Use OCR quality service for assessment
    quality_service = OCRQualityService()
    
    ocr_data = document.ocr_result
    if "extracted_data" in ocr_data:
        ocr_data = ocr_data["extracted_data"]
    field_confidences = {k: v for k, v in document.ocr_result.items() if k.endswith("_confidence")}
    # Normalize keys: remove _confidence suffix for lookup
    normalized_confidences = {k.replace("_confidence", ""): v for k, v in field_confidences.items()}
    if "confidence" in ocr_data and isinstance(ocr_data["confidence"], dict):
        normalized_confidences.update(ocr_data["confidence"])
    
    assessment = quality_service.assess_quality(
        confidence_score=document.confidence_score or 0.0,
        raw_text=document.raw_text,
        extracted_data=ocr_data,
        field_confidences=normalized_confidences,
    )
    
    return OCRQualityFeedback(**assessment)


@router.post("/{document_id}/retry-ocr")
async def retry_ocr_processing(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retry OCR processing for a document
    
    Requirements: 25.7
    
    - Allows user to retry OCR if initial attempt failed
    - Useful after user improves image quality
    - Clears previous OCR results
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Clear previous OCR results
    document.ocr_result = None
    document.raw_text = None
    document.confidence_score = None
    document.processed_at = None
    
    db.commit()
    
    # Trigger OCR processing again: try Celery first, fall back to background thread
    try:
        process_document_ocr.delay(document.id)
    except Exception as e:
        logger.warning(f"Celery unavailable for OCR retry on document {document.id}, running in background thread: {e}")

        def _run_ocr_retry(doc_id: int):
            try:
                run_ocr_pipeline(doc_id)
            except Exception as ocr_err:
                logger.warning(f"Pipeline retry failed for doc {doc_id}, falling back: {ocr_err}")
                try:
                    run_ocr_sync(doc_id)
                except Exception as legacy_err:
                    logger.error(f"Legacy OCR retry also failed for doc {doc_id}: {legacy_err}")

        thread = threading.Thread(target=_run_ocr_retry, args=(document.id,), daemon=True)
        thread.start()
    
    return {
        "message": "OCR processing restarted",
        "document_id": document.id,
    }


@router.get("/{document_id}/retake-guidance", response_model=OCRRetakeGuidance)
def get_retake_guidance(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get guidance for retaking document photo
    
    Requirements: 25.3, 25.4
    
    - Provides specific tips based on OCR issues
    - Helps user improve image quality
    """
    from app.services.ocr_quality_service import OCRQualityService
    
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    confidence = document.confidence_score or 0.0
    
    quality_service = OCRQualityService()
    guidance = quality_service.get_retake_guidance(confidence)
    
    return OCRRetakeGuidance(
        reason=guidance["reason"],
        tips=guidance["tips"],
    )


@router.post("/batch/reprocess-all")
def reprocess_all_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reprocess all documents that have no transactions yet.
    Useful when OCR pipeline was broken and documents need re-processing.
    """
    # Find all documents for this user that don't have a linked transaction
    documents = (
        db.query(Document)
        .filter(
            Document.user_id == current_user.id,
            Document.transaction_id.is_(None),
        )
        .all()
    )

    if not documents:
        return {
            "message": "No documents need reprocessing",
            "count": 0,
        }

    # Clear previous OCR results and re-queue
    queued = 0
    for doc in documents:
        doc.ocr_result = None
        doc.raw_text = None
        doc.confidence_score = None
        doc.processed_at = None

    db.commit()

    for doc in documents:
        try:
            process_document_ocr.delay(doc.id)
            queued += 1
        except Exception as e:
            logger.warning(f"Failed to queue OCR for document {doc.id}: {e}")

    return {
        "message": f"Queued {queued} documents for reprocessing",
        "count": queued,
        "document_ids": [doc.id for doc in documents],
    }


# ============================================================================
# OCR Import Suggestion Confirmation Endpoints
# ============================================================================


@router.post("/{document_id}/confirm-property")
def confirm_property_from_ocr(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm and create a property from Kaufvertrag OCR suggestion.

    The OCR pipeline stores a suggestion in ocr_result.import_suggestion
    with type='create_property'. This endpoint creates the actual property
    record after user confirmation.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    ocr_result = document.ocr_result or {}
    suggestion = ocr_result.get("import_suggestion")

    if not suggestion or suggestion.get("type") != "create_property":
        raise HTTPException(
            status_code=400,
            detail="No property creation suggestion found for this document",
        )

    if suggestion.get("status") == "confirmed":
        return {
            "message": "Property already created from this document",
            "property_id": suggestion.get("property_id"),
            "already_confirmed": True,
        }

    try:
        from app.tasks.ocr_tasks import create_property_from_suggestion

        result = create_property_from_suggestion(db, document, suggestion["data"])
        return {
            "message": "Property created successfully",
            **result,
        }
    except Exception as e:
        logger.error(f"Failed to create property from suggestion for doc {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/confirm-recurring")
def confirm_recurring_from_ocr(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm and create a recurring rental income from Mietvertrag OCR suggestion.

    The OCR pipeline stores a suggestion in ocr_result.import_suggestion
    with type='create_recurring_income'. This endpoint creates the actual
    recurring transaction after user confirmation.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    ocr_result = document.ocr_result or {}
    suggestion = ocr_result.get("import_suggestion")

    if not suggestion or suggestion.get("type") != "create_recurring_income":
        raise HTTPException(
            status_code=400,
            detail="No recurring income suggestion found for this document",
        )

    if suggestion.get("status") == "confirmed":
        return {
            "message": "Recurring income already created from this document",
            "recurring_id": suggestion.get("recurring_id"),
            "already_confirmed": True,
        }

    try:
        from app.tasks.ocr_tasks import create_recurring_from_suggestion

        result = create_recurring_from_suggestion(db, document, suggestion["data"])
        return {
            "message": "Recurring income created successfully",
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create recurring from suggestion for doc {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/dismiss-suggestion")
def dismiss_import_suggestion(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss an import suggestion without creating any records."""
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    ocr_result = document.ocr_result or {}
    suggestion = ocr_result.get("import_suggestion")

    if not suggestion:
        return {"message": "No suggestion to dismiss"}

    ocr_result = ocr_result.copy()
    ocr_result["import_suggestion"]["status"] = "dismissed"
    document.ocr_result = ocr_result
    db.commit()

    return {"message": "Suggestion dismissed"}







