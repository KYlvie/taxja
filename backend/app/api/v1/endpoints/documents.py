"""Document management API endpoints"""
import hashlib
import io
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, status, Query, BackgroundTasks, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from PIL import Image, ImageOps

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
    ProcessStatusResponse,
    FollowUpAnswerRequest,
    FollowUpAnswerResponse,
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
from app.schemas.asset_recognition import AssetSuggestionConfirmationRequest
from app.services.storage_service import StorageService
from app.tasks.ocr_tasks import process_document_ocr, run_ocr_sync, run_ocr_pipeline
from app.core.security import get_current_user
from app.api.deps import require_feature
from app.services.feature_gate_service import Feature
from app.services.document_tax_review_service import backfill_document_tax_review
from app.services.credit_service import CreditService, InsufficientCreditsError

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


@dataclass
class UploadProcessingResult:
    """Internal result for single uploaded file processing."""

    response: DocumentUploadResponse
    document_id: int
    created_new: bool
    should_schedule_ocr: bool
    stored_file_path: Optional[str] = None


def validate_file(file: UploadFile) -> None:
    """Validate uploaded file format and size"""
    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format. Allowed: JPEG, PNG, PDF. Got: {file.content_type}",
        )


def validate_group_image_file(file: UploadFile) -> None:
    """Validate a file that will be merged into a multi-page image document."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only image files can be combined into one document. Got: {file.content_type}",
        )


def _compute_file_hash(file_content: bytes) -> str:
    """Compute a stable SHA-256 hash for exact file deduplication."""
    return hashlib.sha256(file_content).hexdigest()


def _compute_group_file_hash(file_contents: List[bytes]) -> str:
    """Compute a stable hash for a multi-page image document based on page order and content."""
    hasher = hashlib.sha256()

    for index, content in enumerate(file_contents):
        hasher.update(index.to_bytes(4, "big", signed=False))
        hasher.update(len(content).to_bytes(8, "big", signed=False))
        hasher.update(content)

    return hasher.hexdigest()


def _find_existing_document_by_hash(db: Session, user_id: int, file_hash: str) -> Optional[Document]:
    """Return the newest existing document with the same file hash for this user."""
    return (
        db.query(Document)
        .filter(Document.user_id == user_id, Document.file_hash == file_hash)
        .order_by(Document.uploaded_at.desc(), Document.id.desc())
        .first()
    )


def _backfill_legacy_document_hashes_and_match(
    db: Session,
    *,
    user_id: int,
    desired_hash: str,
    uploaded_content: bytes,
    file_size: int,
    content_type: str,
    limit: int = 25,
) -> Optional[Document]:
    """
    Lazily backfill file hashes for legacy documents and match exact duplicates.

    This mainly covers documents uploaded before the `file_hash` column existed.
    We compare the uploaded binary against stored legacy files, then persist the
    current dedup hash onto the matched document so future uploads short-circuit.
    """
    uploaded_binary_hash = _compute_file_hash(uploaded_content)
    storage_service = get_storage_service()

    candidates = (
        db.query(Document)
        .filter(Document.user_id == user_id, Document.file_hash.is_(None))
        .filter(or_(Document.file_size == file_size, Document.file_size.is_(None)))
        .filter(or_(Document.mime_type == content_type, Document.mime_type.is_(None)))
        .order_by(Document.uploaded_at.desc(), Document.id.desc())
        .limit(limit)
        .all()
    )

    updated_any = False
    matched_document: Optional[Document] = None

    for candidate in candidates:
        if not candidate.file_path:
            continue

        stored_bytes = storage_service.download_file(candidate.file_path)
        if not stored_bytes:
            continue

        stored_binary_hash = _compute_file_hash(stored_bytes)
        if stored_binary_hash == uploaded_binary_hash:
            candidate.file_hash = desired_hash
            matched_document = candidate
            updated_any = True
            break

        candidate.file_hash = stored_binary_hash
        updated_any = True

    if updated_any:
        db.flush()

    return matched_document


def _document_needs_reprocessing(document: Document) -> bool:
    """Allow duplicate upload to retrigger OCR only if the existing document never produced data."""
    return document.processed_at is not None and not bool(document.ocr_result or document.raw_text)


def _store_upload_context(document: Document, property_id: Optional[str], db: Session) -> None:
    """Persist upload context needed by downstream OCR pipeline steps."""
    if not property_id:
        return

    ocr_result = document.ocr_result or {}
    ocr_result["_upload_context"] = {"property_id": property_id}
    document.ocr_result = ocr_result
    db.flush()


def _build_upload_response(
    document: Document,
    *,
    message: str,
    deduplicated: bool = False,
    duplicate_of_document_id: Optional[int] = None,
) -> DocumentUploadResponse:
    """Build the API response for a processed upload."""
    return DocumentUploadResponse(
        id=document.id,
        file_name=document.file_name,
        file_size=document.file_size,
        mime_type=document.mime_type,
        document_type=document.document_type,
        uploaded_at=document.uploaded_at,
        message=message,
        deduplicated=deduplicated,
        duplicate_of_document_id=duplicate_of_document_id,
    )


def _process_uploaded_content(
    *,
    file_name: str,
    content_type: str,
    file_content: bytes,
    property_id: Optional[str],
    current_user: User,
    db: Session,
    file_hash: Optional[str] = None,
) -> UploadProcessingResult:
    """Validate size, deduplicate, store, and persist one uploaded document payload."""
    file_size = len(file_content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: 10MB. Got: {file_size / 1024 / 1024:.2f}MB",
        )

    resolved_hash = file_hash or _compute_file_hash(file_content)
    existing_document = _find_existing_document_by_hash(db, current_user.id, resolved_hash)
    if not existing_document:
        existing_document = _backfill_legacy_document_hashes_and_match(
            db,
            user_id=current_user.id,
            desired_hash=resolved_hash,
            uploaded_content=file_content,
            file_size=file_size,
            content_type=content_type,
        )
    if existing_document:
        should_schedule_ocr = _document_needs_reprocessing(existing_document)
        if should_schedule_ocr:
            message = "Duplicate document detected. Existing document reused and OCR processing restarted."
        else:
            message = "Duplicate document detected. Existing document reused."

        return UploadProcessingResult(
            response=_build_upload_response(
                existing_document,
                message=message,
                deduplicated=True,
                duplicate_of_document_id=existing_document.id,
            ),
            document_id=existing_document.id,
            created_new=False,
            should_schedule_ocr=should_schedule_ocr,
        )

    file_extension = file_name.split(".")[-1] if "." in file_name else "bin"
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = f"users/{current_user.id}/documents/{unique_filename}"

    storage_service = get_storage_service()
    success = storage_service.upload_file(
        file_bytes=file_content,
        file_path=file_path,
        content_type=content_type,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage",
        )

    try:
        document = Document(
            user_id=current_user.id,
            document_type=DocumentType.OTHER,
            file_path=file_path,
            file_name=file_name,
            file_hash=resolved_hash,
            file_size=file_size,
            mime_type=content_type,
            uploaded_at=datetime.utcnow(),
        )

        db.add(document)
        db.flush()
        _store_upload_context(document, property_id, db)
    except Exception:
        db.rollback()
        storage_service.delete_file(file_path)
        raise

    return UploadProcessingResult(
        response=_build_upload_response(
            document,
            message="Document uploaded successfully. OCR processing started.",
        ),
        document_id=document.id,
        created_new=True,
        should_schedule_ocr=True,
        stored_file_path=file_path,
    )


async def _process_uploaded_file(
    file: UploadFile,
    *,
    property_id: Optional[str],
    current_user: User,
    db: Session,
) -> UploadProcessingResult:
    """Validate, deduplicate, store, and persist one uploaded file."""
    validate_file(file)

    file_content = await file.read()
    return _process_uploaded_content(
        file_name=file.filename,
        content_type=file.content_type,
        file_content=file_content,
        property_id=property_id,
        current_user=current_user,
        db=db,
    )


def _merge_images_to_pdf(file_contents: List[bytes]) -> bytes:
    """Merge multiple image payloads into a single PDF document."""
    if len(file_contents) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least two images are required to create a multi-page document.",
        )

    pdf_buffer = io.BytesIO()
    prepared_images: List[Image.Image] = []

    try:
        for content in file_contents:
            with Image.open(io.BytesIO(content)) as image:
                normalized = ImageOps.exif_transpose(image)
                if normalized.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", normalized.size, "white")
                    background.paste(normalized, mask=normalized.getchannel("A"))
                    prepared_images.append(background)
                else:
                    prepared_images.append(normalized.convert("RGB"))

        first_image, *rest_images = prepared_images
        first_image.save(pdf_buffer, format="PDF", save_all=True, append_images=rest_images)
        return pdf_buffer.getvalue()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to combine images into one document: {exc}",
        ) from exc
    finally:
        for image in prepared_images:
            image.close()


def _run_ocr_pipeline_with_fallback(document_id: int) -> None:
    """Run the orchestrated OCR pipeline, then fall back to legacy OCR if needed."""
    try:
        logger.info(f"OCR pipeline starting for document {document_id}")
        run_ocr_pipeline(document_id)
        logger.info(f"OCR pipeline completed for document {document_id}")
    except Exception as ocr_err:
        logger.warning(f"Pipeline failed for document {document_id}, falling back to legacy: {ocr_err}")
        try:
            run_ocr_sync(document_id)
        except Exception as legacy_err:
            logger.error(f"Legacy OCR also failed for document {document_id}: {legacy_err}")


def _is_celery_worker_available() -> bool:
    """Check if at least one Celery worker is online."""
    try:
        from app.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=1.0)
        active = inspector.active_queues()
        return bool(active)
    except Exception:
        return False


def _schedule_ocr_processing(background_tasks: BackgroundTasks, document_id: int) -> None:
    """
    Queue OCR in Celery when a worker is available, otherwise fall back to
    FastAPI background tasks.

    Previous bug: Redis accepted the .delay() message (no exception), but no
    Celery worker was running to pick it up — tasks sat in queue forever.
    Now we explicitly check for a live worker before queuing.
    """
    if _is_celery_worker_available():
        try:
            task = process_document_ocr.delay(document_id)
            logger.info(f"Queued OCR task {task.id} for document {document_id}")
            return
        except Exception as queue_err:
            logger.warning(
                f"Celery queue failed for document {document_id}: {queue_err}"
            )

    logger.info(
        f"No Celery worker available for document {document_id}, using FastAPI background task"
    )
    background_tasks.add_task(_run_ocr_pipeline_with_fallback, document_id)


def _cleanup_uploaded_file(file_path: Optional[str]) -> None:
    """Best-effort cleanup for a newly uploaded file when DB work is rolled back."""
    if not file_path:
        return

    try:
        deleted = get_storage_service().delete_file(file_path)
        if not deleted:
            logger.warning("Failed to clean up uploaded file after rollback: %s", file_path)
    except Exception as exc:
        logger.warning("Failed to clean up uploaded file %s: %s", file_path, exc)


def _rollback_upload_state(db: Session, file_path: Optional[str]) -> None:
    """Rollback pending DB work and remove any just-uploaded file."""
    try:
        db.rollback()
    finally:
        _cleanup_uploaded_file(file_path)


def _deduct_ocr_scan_credits(db: Session, user_id: int, document_id: int):
    """Deduct OCR scan credits or raise HTTP 402."""
    credit_service = CreditService(db, redis_client=None)
    try:
        return credit_service.check_and_deduct(
            user_id=user_id,
            operation="ocr_scan",
            context_type="document",
            context_id=document_id,
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: required {e.required}, available {e.available}",
        ) from e


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_feature(Feature.OCR_SCANNING))],
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    property_id: Optional[str] = Query(None, description="Optional property ID to associate the document with"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """
    Upload a single document (JPEG, PNG, or PDF)

    - Validates file format and size
    - Stores file in MinIO with AES-256 encryption
    - Saves document metadata in database
    - Triggers OCR processing asynchronously
    - Optionally accepts property_id to associate the document with a property
    """
    result: Optional[UploadProcessingResult] = None
    try:
        result = await _process_uploaded_file(
            file,
            property_id=property_id,
            current_user=current_user,
            db=db,
        )

        if result.created_new:
            deduction = _deduct_ocr_scan_credits(db, current_user.id, result.document_id)
            if response is not None:
                response.headers["X-Credits-Remaining"] = str(
                    deduction.balance_after.available_without_overage
                )

        db.commit()
    except HTTPException:
        _rollback_upload_state(db, result.stored_file_path if result else None)
        raise
    except Exception:
        _rollback_upload_state(db, result.stored_file_path if result else None)
        raise

    if result.should_schedule_ocr:
        _schedule_ocr_processing(background_tasks, result.document_id)

    return result.response


@router.post(
    "/upload-image-group",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_feature(Feature.OCR_SCANNING))],
)
async def upload_image_group(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    property_id: Optional[str] = Query(None, description="Optional property ID to associate the document with"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """
    Upload multiple photos as one multi-page document.

    - Accepts two or more image files
    - Merges them into a single PDF document
    - Reuses existing deduplication and OCR scheduling
    """
    if len(files) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide at least two images to create one combined document.",
        )

    page_contents: List[bytes] = []
    for file in files:
        validate_group_image_file(file)
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: 10MB. Got: {len(content) / 1024 / 1024:.2f}MB",
            )
        page_contents.append(content)

    group_hash = _compute_group_file_hash(page_contents)
    existing_document = _find_existing_document_by_hash(db, current_user.id, group_hash)
    if existing_document:
        should_schedule_ocr = _document_needs_reprocessing(existing_document)
        if should_schedule_ocr:
            _schedule_ocr_processing(background_tasks, existing_document.id)

        return _build_upload_response(
            existing_document,
            message=(
                "Duplicate document detected. Existing document reused and OCR processing restarted."
                if should_schedule_ocr
                else "Duplicate document detected. Existing document reused."
            ),
            deduplicated=True,
            duplicate_of_document_id=existing_document.id,
        )

    combined_pdf = _merge_images_to_pdf(page_contents)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    merged_file_name = f"taxja-scan-{timestamp}-{len(files)}-pages.pdf"
    result: Optional[UploadProcessingResult] = None
    try:
        result = _process_uploaded_content(
            file_name=merged_file_name,
            content_type="application/pdf",
            file_content=combined_pdf,
            property_id=property_id,
            current_user=current_user,
            db=db,
            file_hash=group_hash,
        )

        if result.created_new:
            deduction = _deduct_ocr_scan_credits(db, current_user.id, result.document_id)
            if response is not None:
                response.headers["X-Credits-Remaining"] = str(
                    deduction.balance_after.available_without_overage
                )

        db.commit()
    except HTTPException:
        _rollback_upload_state(db, result.stored_file_path if result else None)
        raise
    except Exception:
        _rollback_upload_state(db, result.stored_file_path if result else None)
        raise

    if result.should_schedule_ocr:
        _schedule_ocr_processing(background_tasks, result.document_id)

    return result.response


@router.post(
    "/batch-upload",
    response_model=BatchUploadResponse,
    dependencies=[Depends(require_feature(Feature.OCR_SCANNING))],
)
async def batch_upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    property_id: Optional[str] = Query(None, description="Optional property ID to associate the documents with"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload multiple documents in batch
    
    - Processes multiple files in parallel
    - Returns individual status for each file
    - Continues processing even if some files fail
    - Optionally accepts property_id to associate all documents with a property
    """
    successful = []
    failed = []
    created_count = 0
    deduplicated_count = 0
    credits_exhausted = False
    
    for file in files:
        result: Optional[UploadProcessingResult] = None
        try:
            # If credits were exhausted on a previous file, skip remaining new files
            if credits_exhausted:
                failed.append({
                    "file_name": file.filename,
                    "error": "Insufficient credits for additional uploads",
                })
                continue

            result = await _process_uploaded_file(
                file,
                property_id=property_id,
                current_user=current_user,
                db=db,
            )

            if result.created_new:
                _deduct_ocr_scan_credits(db, current_user.id, result.document_id)
            else:
                deduplicated_count += 1

            db.commit()

            if result.created_new:
                created_count += 1

            if result.should_schedule_ocr:
                _schedule_ocr_processing(background_tasks, result.document_id)

            successful.append(result.response)
             
        except HTTPException as e:
            _rollback_upload_state(db, result.stored_file_path if result else None)
            if e.status_code == 402:
                credits_exhausted = True
            failed.append({
                "file_name": file.filename,
                "error": e.detail,
            })
        except Exception as e:
            _rollback_upload_state(db, result.stored_file_path if result else None)
            failed.append({
                "file_name": file.filename,
                "error": str(e),
            })
    
    return BatchUploadResponse(
        total_uploaded=created_count,
        successful=successful,
        failed=failed,
        message=(
            f"Uploaded {created_count} new document(s), reused {deduplicated_count} duplicate(s), "
            f"failed {len(failed)} of {len(files)} file(s)."
        ),
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


@router.get("/{document_id}")
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific document"""
    from app.models.transaction import Transaction

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

    backfill_document_tax_review(db, document, current_user)

    # Query linked transactions for this document
    linked_txns = (
        db.query(Transaction)
        .filter(Transaction.document_id == document_id)
        .all()
    )
    linked_transactions = [
        {
            "transaction_id": txn.id,
            "description": txn.description,
            "amount": float(txn.amount),
            "date": txn.transaction_date.isoformat() if txn.transaction_date else None,
            "has_line_items": bool(txn.line_items),
        }
        for txn in linked_txns
    ]

    result = DocumentDetail.from_orm(document)
    result_dict = result.dict() if hasattr(result, "dict") else result.model_dump()
    result_dict["linked_transactions"] = linked_transactions

    return result_dict


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
        if document.document_type == DocumentType.PURCHASE_CONTRACT:
            # Find property linked to this document
            property = db.query(Property).filter(
                Property.kaufvertrag_document_id == document_id
            ).first()
            
            if property:
                logger.info(f"Cascade deleting property {property.id} linked to Kaufvertrag {document_id}")

                # 1. Delete all recurring transactions for this property + generated txns
                recurrings = db.query(RecurringTransaction).filter(
                    RecurringTransaction.property_id == property.id
                ).all()
                if recurrings:
                    recurring_ids = [r.id for r in recurrings]
                    # Delete transactions generated by these recurring transactions
                    generated_txns = db.query(Transaction).filter(
                        Transaction.source_recurring_id.in_(recurring_ids)
                    ).all()
                    for gtxn in generated_txns:
                        db.query(Document).filter(
                            Document.transaction_id == gtxn.id
                        ).update({Document.transaction_id: None}, synchronize_session="fetch")
                        gtxn.source_recurring_id = None
                        gtxn.parent_recurring_id = None
                        db.flush()
                        db.delete(gtxn)
                    for rec in recurrings:
                        logger.info(f"Deleting recurring {rec.id} for property {property.id}")
                        db.delete(rec)
                    db.flush()

                # 2. Delete linked mietvertrag document if cascade requested
                if property.mietvertrag_document_id and property.mietvertrag_document_id != document_id:
                    miet_doc = db.query(Document).filter(
                        Document.id == property.mietvertrag_document_id
                    ).first()
                    if miet_doc:
                        logger.info(
                            f"Cascade deleting linked Mietvertrag doc {miet_doc.id} "
                            f"for property {property.id}"
                        )
                        # Unlink transactions from mietvertrag doc
                        miet_txns = db.query(Transaction).filter(
                            Transaction.document_id == miet_doc.id
                        ).all()
                        for mt in miet_txns:
                            mt.document_id = None
                        if miet_doc.transaction_id:
                            miet_doc.transaction_id = None
                        db.flush()
                        # Delete mietvertrag file from storage
                        try:
                            storage_service = get_storage_service()
                            storage_service.delete_file(miet_doc.file_path)
                        except Exception as e:
                            logger.warning(f"Failed to delete mietvertrag file: {e}")
                        property.mietvertrag_document_id = None
                        db.flush()
                        db.delete(miet_doc)
                        db.flush()

                # 3. Unlink all transactions from this property
                prop_txns = db.query(Transaction).filter(
                    Transaction.property_id == property.id
                ).all()
                for pt in prop_txns:
                    pt.property_id = None
                db.flush()

                # 4. Clear kaufvertrag reference and delete property
                property.kaufvertrag_document_id = None
                db.flush()
                db.delete(property)
                db.flush()
                logger.info(f"Property {property.id} cascade deleted")
        
        # Delete related recurring transactions if it's a Mietvertrag
        # Also delete all transactions generated by those recurring transactions
        if document.document_type == DocumentType.RENTAL_CONTRACT:
            # Find property linked to this document via mietvertrag_document_id
            linked_property = db.query(Property).filter(
                Property.mietvertrag_document_id == document_id
            ).first()

            recurring_ids_to_delete = []

            if linked_property:
                # Find all recurring transactions for this property
                recurrings = db.query(RecurringTransaction).filter(
                    RecurringTransaction.property_id == linked_property.id
                ).all()
                recurring_ids_to_delete = [r.id for r in recurrings]
            else:
                # Fallback: find recurring via document's linked transaction
                if document.transaction_id:
                    txn = db.query(Transaction).filter(
                        Transaction.id == document.transaction_id
                    ).first()
                    if txn and txn.source_recurring_id:
                        recurring_ids_to_delete = [txn.source_recurring_id]

            # Delete transactions generated by these recurring transactions
            if recurring_ids_to_delete:
                generated_txns = db.query(Transaction).filter(
                    Transaction.source_recurring_id.in_(recurring_ids_to_delete)
                ).all()
                for gtxn in generated_txns:
                    logger.info(
                        f"Deleting generated transaction {gtxn.id} "
                        f"(source_recurring_id={gtxn.source_recurring_id})"
                    )
                    # Clear any document references pointing to this transaction
                    db.query(Document).filter(
                        Document.transaction_id == gtxn.id
                    ).update({Document.transaction_id: None}, synchronize_session="fetch")
                    gtxn.source_recurring_id = None
                    gtxn.parent_recurring_id = None
                    db.flush()
                    db.delete(gtxn)

                # Now delete the recurring transactions themselves
                for rid in recurring_ids_to_delete:
                    rec = db.query(RecurringTransaction).filter(
                        RecurringTransaction.id == rid
                    ).first()
                    if rec:
                        logger.info(
                            f"Deleting recurring transaction {rec.id} linked to document {document_id}"
                        )
                        db.delete(rec)

            # Clear mietvertrag_document_id on property and recalculate rental percentage
            if linked_property:
                linked_property.mietvertrag_document_id = None
                try:
                    property_service = PropertyService(db)
                    property_service.recalculate_rental_percentage(
                        str(linked_property.id), current_user.id
                    )
                except Exception as e:
                    logger.warning(f"Failed to recalculate rental percentage: {e}")

        # Collect all transaction IDs to delete (direct document links)
        txn_ids_to_delete = set()
        
        linked_txns = db.query(Transaction).filter(
            Transaction.document_id == document_id
        ).all()
        for txn in linked_txns:
            txn_ids_to_delete.add(txn.id)
        
        if document.transaction_id:
            txn_ids_to_delete.add(document.transaction_id)
        
        if txn_ids_to_delete:
            # First: clear document.transaction_id on THIS document to avoid FK violation
            document.transaction_id = None
            
            # Clear transaction_id on ANY other documents pointing to these transactions
            db.query(Document).filter(
                Document.transaction_id.in_(txn_ids_to_delete)
            ).update({Document.transaction_id: None}, synchronize_session="fetch")
            
            # Clear document_id on any other documents referencing these transactions
            # (documents linked via document_id on the transaction side are fine,
            #  but other docs might point to same txn)
            
            db.flush()
            
            # Now safe to delete the transactions
            for txn_id in txn_ids_to_delete:
                txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
                if txn:
                    logger.info(f"Deleting transaction {txn.id} linked to document {document_id}")
                    db.delete(txn)
    
    else:  # document_only mode (default, safe)
        # Safe mode: only unlink, don't delete data
        logger.info(f"Deleting document {document_id} WITHOUT related data (unlink only)")
        
        # Unlink property if it's a Kaufvertrag
        if document.document_type == DocumentType.PURCHASE_CONTRACT:
            property = db.query(Property).filter(
                Property.kaufvertrag_document_id == document_id
            ).first()
            
            if property:
                logger.info(f"Unlinking property {property.id} from document {document_id}")
                property.kaufvertrag_document_id = None
        
        # Unlink recurring transaction if it's a Mietvertrag
        if document.document_type == DocumentType.RENTAL_CONTRACT:
            # mietvertrag_document_id is on Property, not RecurringTransaction
            linked_property = db.query(Property).filter(
                Property.mietvertrag_document_id == document_id
            ).first()
            if linked_property:
                logger.info(f"Unlinking mietvertrag from property {linked_property.id}")
                linked_property.mietvertrag_document_id = None
        
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
    if document.document_type == DocumentType.PURCHASE_CONTRACT:
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

            # Check if property also has a linked rental contract (Mietvertrag)
            if property.mietvertrag_document_id:
                mietvertrag_doc = db.query(Document).filter(
                    Document.id == property.mietvertrag_document_id
                ).first()
                if mietvertrag_doc:
                    related_data["linked_mietvertrag"] = {
                        "document_id": mietvertrag_doc.id,
                        "file_name": mietvertrag_doc.file_name,
                    }

            # Check for recurring transactions on this property
            recurrings = db.query(RecurringTransaction).filter(
                RecurringTransaction.property_id == property.id
            ).all()
            if recurrings:
                related_data["recurring_transactions"] = [
                    {
                        "id": r.id,
                        "description": r.description,
                        "amount": float(r.amount),
                        "frequency": r.frequency.value if r.frequency else None,
                        "is_active": r.is_active,
                    }
                    for r in recurrings
                ]

    # Check for related recurring transactions (Mietvertrag)
    if document.document_type == DocumentType.RENTAL_CONTRACT:
        linked_property = db.query(Property).filter(
            Property.mietvertrag_document_id == document_id
        ).first()

        if linked_property:
            recurrings = db.query(RecurringTransaction).filter(
                RecurringTransaction.property_id == linked_property.id
            ).all()

            if recurrings:
                has_related_data = True
                related_data["recurring_transactions"] = [
                    {
                        "id": r.id,
                        "description": r.description,
                        "amount": float(r.amount),
                        "frequency": r.frequency.value if r.frequency else None,
                    }
                    for r in recurrings
                ]

                # Count transactions generated by these recurring transactions
                recurring_ids = [r.id for r in recurrings]
                generated_count = db.query(Transaction).filter(
                    Transaction.source_recurring_id.in_(recurring_ids)
                ).count()
                if generated_count > 0:
                    related_data["generated_transactions_count"] = generated_count

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
    
    creation_result = ocr_service.create_transaction_from_suggestion_with_result(
        suggestion, current_user.id
    )
    transaction = creation_result.transaction
    
    return {
        "message": (
            "Transaction created successfully"
            if creation_result.created
            else "Duplicate prevented. Existing transaction reused."
        ),
        "transaction_id": transaction.id,
        "document_id": document_id,
        "deduplicated": not creation_result.created,
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
                 "line_items", "vat_summary", "tax_analysis", "import_suggestion", "asset_outcome"}

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
    
    # Update OCR result with confirmation. Use a detached copy so SQLAlchemy's
    # JSON column reliably detects the persisted change across SQLite/Postgres.
    import json as _json
    from sqlalchemy.orm.attributes import flag_modified

    ocr_result = _json.loads(_json.dumps(document.ocr_result or {}))
    ocr_result["confirmed"] = request.confirmed
    ocr_result["confirmed_at"] = datetime.utcnow().isoformat()
    ocr_result["confirmed_by"] = current_user.id
    
    if request.notes:
        ocr_result["confirmation_notes"] = request.notes
    
    document.ocr_result = ocr_result
    db.commit()

    # Auto-create transaction if not already linked
    transaction_id = None
    transaction_created = False
    if request.confirmed and not document.transaction_id:
        try:
            from app.services.ocr_transaction_service import OCRTransactionService
            ocr_service = OCRTransactionService(db)
            suggestion = ocr_service.create_transaction_suggestion(document_id, current_user.id)
            if suggestion:
                creation_result = ocr_service.create_transaction_from_suggestion_with_result(
                    suggestion, current_user.id
                )
                transaction_id = creation_result.transaction.id
                transaction_created = creation_result.created
        except Exception as e:
            logger.warning(f"Auto-create transaction failed for doc {document_id}: {e}")

    msg = "OCR results confirmed successfully"
    if transaction_id:
        if transaction_created:
            msg += f" and transaction #{transaction_id} created"
        else:
            msg += f" and duplicate was prevented by reusing transaction #{transaction_id}"

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
        previous_data = {
            k: v for k, v in ocr_result.items()
            if not k.endswith("_confidence") and k != "correction_history" and k != "learning_data"
        }
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
        "previous_values": {k: previous_data.get(k) for k in updated_fields if k in previous_data},
        "corrected_fields": updated_fields,
        "notes": request.notes,
    })
    
    # Increase confidence after user correction
    new_confidence = min(1.0, float(previous_confidence) + 0.2)
    document.confidence_score = new_confidence
    # Deep copy to trigger SQLAlchemy JSON change detection
    import json as _json
    document.ocr_result = _json.loads(_json.dumps(ocr_result))
    # Explicitly mark JSON column as modified — SQLAlchemy JSON type
    # does not track mutations and may miss even full reassignment
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(document, "ocr_result")
    
    db.commit()
    
    # Sync document corrections to linked recurring transactions.
    # Any document that created a recurring transaction (rental contracts,
    # insurance, subscriptions, etc.) can propagate field edits.
    # Uses the direct source_document_id link on recurring_transactions.
    sync_msg = ""
    syncable_fields = {"monthly_rent", "amount", "start_date", "end_date"}
    if syncable_fields & set(updated_fields):
        try:
            from app.models.recurring_transaction import RecurringTransaction
            from app.services.recurring_transaction_service import RecurringTransactionService
            from datetime import datetime as dt, date as date_cls

            linked_recurrings = db.query(RecurringTransaction).filter(
                RecurringTransaction.source_document_id == document_id
            ).all()
            if linked_recurrings:
                svc = RecurringTransactionService(db)
                for rec in linked_recurrings:
                    changed = False
                    # Sync amount: monthly_rent (rental) or amount (expense/other)
                    for amt_field in ("monthly_rent", "amount"):
                        if amt_field in updated_fields:
                            new_val = request.corrected_data.get(amt_field)
                            if new_val is not None:
                                from decimal import Decimal
                                rec.amount = Decimal(str(new_val))
                                changed = True
                                break
                    if "start_date" in updated_fields:
                        sd = request.corrected_data.get("start_date")
                        if sd:
                            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                                try:
                                    rec.start_date = dt.strptime(sd, fmt).date()
                                    break
                                except ValueError:
                                    continue
                            changed = True
                    if "end_date" in updated_fields:
                        ed = request.corrected_data.get("end_date")
                        if ed:
                            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                                try:
                                    rec.end_date = dt.strptime(ed, fmt).date()
                                    break
                                except ValueError:
                                    continue
                        else:
                            rec.end_date = None
                        changed = True
                    if changed:
                        # Reset generation state and regenerate transactions
                        rec.next_generation_date = rec.start_date
                        rec.last_generated_date = None
                        from app.models.transaction import Transaction
                        db.query(Transaction).filter(
                            Transaction.source_recurring_id == rec.id
                        ).delete(synchronize_session="fetch")
                        # Temporarily activate for generation if needed
                        was_inactive = not rec.is_active
                        if was_inactive:
                            rec.is_active = True
                        db.flush()
                        if rec.end_date and rec.end_date < date_cls.today():
                            # End date is in the past → generate up to end_date, deactivate
                            generated = svc.generate_due_transactions(
                                target_date=rec.end_date, user_id=current_user.id
                            )
                            rec.is_active = False
                        else:
                            # End date is in the future (or no end date) → keep active
                            generated = svc.generate_due_transactions(
                                target_date=date_cls.today(), user_id=current_user.id
                            )
                            rec.is_active = True
                        db.commit()
                        sync_msg += f" Recurring #{rec.id} synced, {len(generated)} transactions regenerated."
                        logger.info(
                            f"Synced document correction to recurring {rec.id}: "
                            f"{len(generated)} transactions regenerated"
                        )
        except Exception as e:
            logger.warning(f"Failed to sync document correction to recurring: {e}")

    # Sync document corrections to linked regular transactions.
    # A document may have created one or more transactions (multi-receipt, split).
    # When the user edits OCR fields (amount, date, merchant/description), propagate.
    txn_sync_msg = ""
    txn_syncable = {"amount", "date", "merchant", "supplier", "description", "product_summary"}
    if txn_syncable & set(updated_fields):
        try:
            from app.models.transaction import Transaction as TxnModel
            from decimal import Decimal as Dec

            linked_txns = db.query(TxnModel).filter(
                TxnModel.document_id == document_id,
                TxnModel.user_id == current_user.id,
            ).all()

            if linked_txns:
                new_amount = request.corrected_data.get("amount")
                new_date = request.corrected_data.get("date")
                new_merchant = (
                    request.corrected_data.get("merchant")
                    or request.corrected_data.get("supplier")
                )
                new_desc = request.corrected_data.get("description")
                new_product = request.corrected_data.get("product_summary")

                synced_count = 0
                for txn in linked_txns:
                    changed = False
                    if new_amount is not None:
                        try:
                            txn.amount = Dec(str(new_amount))
                            changed = True
                        except Exception:
                            pass
                    if new_date is not None:
                        from datetime import datetime as dt_cls
                        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                            try:
                                txn.transaction_date = dt_cls.strptime(
                                    str(new_date), fmt
                                ).date()
                                changed = True
                                break
                            except ValueError:
                                continue
                    # Update description from merchant/description/product_summary
                    desc_parts = []
                    if new_merchant:
                        desc_parts.append(str(new_merchant))
                    if new_desc and len(str(new_desc)) > 10:
                        desc_parts.append(str(new_desc))
                    elif new_product:
                        desc_parts.append(str(new_product))
                    if desc_parts:
                        txn.description = ": ".join(desc_parts)
                        changed = True

                    if changed:
                        txn.needs_review = False
                        synced_count += 1

                if synced_count:
                    db.commit()
                    txn_sync_msg = f" {synced_count} linked transaction(s) updated."
                    logger.info(
                        f"Synced document correction to {synced_count} transaction(s) "
                        f"for document {document_id}"
                    )
        except Exception as e:
            logger.warning(f"Failed to sync document correction to transactions: {e}")

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

    # Auto-create transaction(s) if no transactions linked to this document
    transaction_id = None
    transaction_created = False
    from app.models.transaction import Transaction as TxnCheck
    has_linked_txns = db.query(
        db.query(TxnCheck).filter(
            TxnCheck.document_id == document_id,
            TxnCheck.user_id == current_user.id,
        ).exists()
    ).scalar()
    if not has_linked_txns:
        try:
            from app.services.ocr_transaction_service import OCRTransactionService
            ocr_service = OCRTransactionService(db)
            suggestions = ocr_service.create_split_suggestions(document_id, current_user.id)
            created_count = 0
            for suggestion in suggestions:
                # Override transaction type if user specified one
                if user_txn_type and user_txn_type in ("income", "expense"):
                    suggestion["transaction_type"] = user_txn_type
                    if user_txn_type == "income":
                        suggestion["category"] = "employment"
                        suggestion["is_deductible"] = False
                        suggestion["deduction_reason"] = "Income is not deductible"
                creation_result = ocr_service.create_transaction_from_suggestion_with_result(
                    suggestion, current_user.id
                )
                if transaction_id is None:
                    transaction_id = creation_result.transaction.id
                    transaction_created = creation_result.created
                if creation_result.created:
                    created_count += 1
        except Exception as e:
            logger.warning(f"Auto-create transaction failed for doc {document_id}: {e}")

    msg = f"OCR data corrected successfully. Updated {len(updated_fields)} field(s).{sync_msg}{txn_sync_msg}"
    if transaction_id:
        if transaction_created:
            msg += f" Transaction #{transaction_id} created."
        else:
            msg += f" Duplicate prevented by reusing transaction #{transaction_id}."

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


@router.post("/{document_id}/confirm-loan")
def confirm_loan_from_ocr(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm and create a PropertyLoan + loan_interest RecurringTransaction
    from a Kreditvertrag OCR suggestion.

    The OCR pipeline stores a suggestion in ocr_result.import_suggestion
    with type='create_loan'. This endpoint creates the actual PropertyLoan
    and RecurringTransaction records after user confirmation, then generates
    historical due transactions.
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

    if not suggestion or suggestion.get("type") != "create_loan":
        raise HTTPException(
            status_code=400,
            detail="No loan creation suggestion found for this document",
        )

    if suggestion.get("status") == "confirmed":
        return {
            "message": "Loan already created from this document",
            "loan_id": suggestion.get("loan_id"),
            "recurring_id": suggestion.get("recurring_id"),
            "already_confirmed": True,
        }

    try:
        from app.tasks.ocr_tasks import create_loan_from_suggestion

        result = create_loan_from_suggestion(db, document, suggestion["data"])
        return {
            "message": "Loan and recurring interest created successfully",
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create loan from suggestion for doc {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/confirm-insurance-recurring")
def confirm_insurance_recurring_from_ocr(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm and create an insurance premium RecurringTransaction
    from a Versicherungsbestätigung OCR suggestion.

    The OCR pipeline stores a suggestion in ocr_result.import_suggestion
    with type='create_insurance_recurring'. This endpoint creates the actual
    RecurringTransaction record after user confirmation, then generates
    historical due transactions.
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

    if not suggestion or suggestion.get("type") != "create_insurance_recurring":
        raise HTTPException(
            status_code=400,
            detail="No insurance recurring suggestion found for this document",
        )

    if suggestion.get("status") == "confirmed":
        return {
            "message": "Insurance recurring already created from this document",
            "recurring_id": suggestion.get("recurring_id"),
            "already_confirmed": True,
        }

    try:
        from app.tasks.ocr_tasks import create_insurance_recurring_from_suggestion

        result = create_insurance_recurring_from_suggestion(db, document, suggestion["data"])
        return {
            "message": "Insurance premium recurring created successfully",
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create insurance recurring from suggestion for doc {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/confirm-loan-repayment")
def confirm_loan_repayment_from_ocr(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm and create a standalone loan repayment RecurringTransaction
    from a Kreditvertrag OCR suggestion (for loans not associated with a property).

    The OCR pipeline stores a suggestion in ocr_result.import_suggestion
    with type='create_loan_repayment'. This endpoint creates the actual
    RecurringTransaction record after user confirmation, then generates
    historical due transactions.
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

    if not suggestion or suggestion.get("type") != "create_loan_repayment":
        raise HTTPException(
            status_code=400,
            detail="No loan repayment suggestion found for this document",
        )

    if suggestion.get("status") == "confirmed":
        return {
            "message": "Loan repayment recurring already created from this document",
            "recurring_id": suggestion.get("recurring_id"),
            "already_confirmed": True,
        }

    try:
        from app.tasks.ocr_tasks import create_standalone_loan_repayment

        result = create_standalone_loan_repayment(db, document, suggestion["data"])
        return {
            "message": "Standalone loan repayment recurring created successfully",
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create loan repayment from suggestion for doc {document_id}: {e}")
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
    if suggestion.get("type") == "create_asset":
        existing_outcome = (
            ocr_result.get("asset_outcome")
            if isinstance(ocr_result.get("asset_outcome"), dict)
            else {}
        )
        ocr_result.pop("import_suggestion", None)
        ocr_result["asset_outcome"] = {
            "contract_version": "v1",
            "type": "create_asset",
            "status": "dismissed",
            "decision": (
                existing_outcome.get("decision")
                or suggestion.get("data", {}).get("decision")
                or "create_asset_suggestion"
            ),
            "asset_id": existing_outcome.get("asset_id"),
            "source": "user_confirmation",
            "quality_gate_decision": (
                existing_outcome.get("quality_gate_decision")
                or suggestion.get("data", {}).get("quality_gate_decision")
            ),
        }
    else:
        ocr_result["import_suggestion"]["status"] = "dismissed"
    document.ocr_result = ocr_result
    flag_modified(document, "ocr_result")
    db.commit()

    return {"message": "Suggestion dismissed"}


@router.post("/{document_id}/confirm-recurring-expense")
def confirm_recurring_expense_from_ocr(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm and create a recurring expense from invoice/insurance OCR suggestion.

    The OCR pipeline stores a suggestion in ocr_result.import_suggestion
    with type='create_recurring_expense'. This endpoint creates the actual
    recurring transaction after user confirmation, and backfills past-due entries.
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

    if not suggestion or suggestion.get("type") != "create_recurring_expense":
        raise HTTPException(
            status_code=400,
            detail="No recurring expense suggestion found for this document",
        )

    if suggestion.get("status") == "confirmed":
        return {
            "message": "Recurring expense already created from this document",
            "recurring_id": suggestion.get("recurring_id"),
            "already_confirmed": True,
        }

    try:
        from app.services.recurring_transaction_service import RecurringTransactionService
        from app.models.recurring_transaction import (
            RecurringTransaction as RT,
            RecurringTransactionType,
            RecurrenceFrequency,
        )
        from decimal import Decimal
        from datetime import datetime as dt, date as date_type

        data = suggestion["data"]
        amount = Decimal(str(data["amount"]))
        description = data.get("description", "Recurring expense")
        category = data.get("category", "other")
        txn_type = data.get("transaction_type", "expense")
        frequency_str = data.get("frequency", "monthly")

        freq_map = {
            "monthly": RecurrenceFrequency.MONTHLY,
            "quarterly": RecurrenceFrequency.QUARTERLY,
            "annually": RecurrenceFrequency.ANNUALLY,
            "weekly": RecurrenceFrequency.WEEKLY,
        }
        freq = freq_map.get(frequency_str, RecurrenceFrequency.MONTHLY)

        # Parse dates
        sd_raw = data.get("start_date")
        start_date = None
        if sd_raw:
            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    start_date = dt.strptime(sd_raw, fmt).date()
                    break
                except ValueError:
                    continue
        if not start_date:
            start_date = document.uploaded_at.date()

        ed_raw = data.get("end_date")
        end_date = None
        if ed_raw:
            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    end_date = dt.strptime(ed_raw, fmt).date()
                    break
                except ValueError:
                    continue

        if txn_type == "income":
            rec_type = RecurringTransactionType.OTHER_INCOME
        else:
            rec_type = RecurringTransactionType.OTHER_EXPENSE

        recurring = RT(
            user_id=current_user.id,
            recurring_type=rec_type,
            description=description,
            amount=amount,
            transaction_type=txn_type,
            category=category,
            frequency=freq,
            start_date=start_date,
            end_date=end_date,
            day_of_month=data.get("day_of_month") or start_date.day,
            is_active=True,
            next_generation_date=start_date,
            source_document_id=document_id,
        )
        db.add(recurring)
        db.commit()
        db.refresh(recurring)

        # Generate past-due transactions
        service = RecurringTransactionService(db)
        generated = service.generate_due_transactions(
            target_date=date_type.today(), user_id=current_user.id
        )
        db.refresh(recurring)

        # Mark suggestion as confirmed
        import json as _json

        updated_ocr = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
        if updated_ocr.get("import_suggestion"):
            updated_ocr["import_suggestion"]["status"] = "confirmed"
            updated_ocr["import_suggestion"]["recurring_id"] = recurring.id
            document.ocr_result = updated_ocr
            db.commit()

        logger.info(
            f"Created recurring expense {recurring.id} from doc {document_id}: "
            f"€{amount} {frequency_str}, generated {len(generated)} past transactions"
        )

        return {
            "message": "Recurring expense created successfully",
            "recurring_id": recurring.id,
            "amount": float(amount),
            "frequency": frequency_str,
            "generated_count": len(generated),
        }
    except Exception as e:
        logger.error(f"Failed to create recurring expense from doc {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/confirm-asset")
def confirm_asset_from_ocr(
    document_id: int,
    confirmation: Optional[AssetSuggestionConfirmationRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Confirm and create a depreciable asset from a vehicle/equipment Kaufvertrag OCR suggestion.

    The OCR pipeline stores a suggestion in ocr_result.import_suggestion
    with type='create_asset'. This endpoint creates the actual asset record.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    ocr_result = document.ocr_result or {}
    asset_outcome = (
        ocr_result.get("asset_outcome")
        if isinstance(ocr_result.get("asset_outcome"), dict)
        else None
    )
    suggestion = ocr_result.get("import_suggestion")

    if asset_outcome and asset_outcome.get("status") in {"confirmed", "auto_created"}:
        return {
            "message": "Asset already created from this document",
            "asset_id": asset_outcome.get("asset_id"),
            "already_confirmed": True,
        }

    if not suggestion or suggestion.get("type") != "create_asset":
        raise HTTPException(
            status_code=400,
            detail="No asset creation suggestion found for this document",
        )

    if suggestion.get("status") == "confirmed":
        return {
            "message": "Asset already created from this document",
            "asset_id": suggestion.get("asset_id"),
            "already_confirmed": True,
        }

    try:
        from app.tasks.ocr_tasks import create_asset_from_suggestion

        result = create_asset_from_suggestion(
            db,
            document,
            suggestion.get("data", {}),
            confirmation.model_dump(exclude_none=True) if confirmation else None,
            trigger_source="user",
        )
        return {
            "message": "Asset created successfully",
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create asset from suggestion for doc {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))








# ---------------------------------------------------------------------------
# Tax filing data confirmation (unified endpoint for L16, L1, E1a, E1b, etc.)
# ---------------------------------------------------------------------------

TAX_DATA_SUGGESTION_TYPES = {
    "import_lohnzettel", "import_l1", "import_l1k", "import_l1ab",
    "import_e1a", "import_e1b", "import_e1kv",
    "import_u1", "import_u30", "import_jahresabschluss",
    "import_svs", "import_grundsteuer", "import_bank_statement",
}


@router.post("/{document_id}/confirm-tax-data")
def confirm_tax_data_from_ocr(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Unified endpoint to confirm and store tax filing data extracted from documents.

    Handles all tax form types: L16, L1, L1k, L1ab, E1a, E1b, E1kv, U1, U30,
    Jahresabschluss, SVS, Grundsteuer.

    The OCR pipeline stores a suggestion in ocr_result.import_suggestion
    with type like 'import_lohnzettel', 'import_l1', etc.
    This endpoint creates a TaxFilingData record after user confirmation.
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

    if not suggestion or suggestion.get("type") not in TAX_DATA_SUGGESTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail="No tax data import suggestion found for this document",
        )

    if suggestion.get("status") == "confirmed":
        return {
            "message": "Tax data already confirmed from this document",
            "tax_filing_data_id": suggestion.get("tax_filing_data_id"),
            "already_confirmed": True,
        }

    try:
        from app.models.tax_filing_data import TaxFilingData
        import json as _json

        suggestion_type = suggestion["type"]
        data = suggestion.get("data", {})
        tax_year = data.get("tax_year") or data.get("year")

        # Map suggestion type to data_type
        data_type = suggestion_type.replace("import_", "")

        merged_into = None  # track if we merged into existing L16

        # --- L16 merge logic: accumulate KZ fields when same tax year ---
        if data_type == "lohnzettel" and tax_year:
            existing_l16 = (
                db.query(TaxFilingData)
                .filter(
                    TaxFilingData.user_id == current_user.id,
                    TaxFilingData.tax_year == tax_year,
                    TaxFilingData.data_type == "lohnzettel",
                    TaxFilingData.status == "confirmed",
                )
                .first()
            )
            if existing_l16:
                # Merge: accumulate numeric KZ fields
                KZ_FIELDS = [
                    "kz_210", "kz_215", "kz_220", "kz_225", "kz_226",
                    "kz_230", "kz_245", "kz_260", "kz_718", "kz_719",
                ]
                merged_data = dict(existing_l16.data)
                for kz in KZ_FIELDS:
                    old_val = float(merged_data.get(kz) or 0)
                    new_val = float(data.get(kz) or 0)
                    if new_val:
                        merged_data[kz] = round(old_val + new_val, 2)
                # Track merged sources
                sources = merged_data.get("merged_sources", [])
                if not sources and existing_l16.source_document_id:
                    sources.append(existing_l16.source_document_id)
                sources.append(document_id)
                merged_data["merged_sources"] = sources
                merged_data["employer_count"] = len(sources)
                # Keep non-KZ fields from new data if missing in old
                for k, v in data.items():
                    if k not in merged_data or merged_data[k] is None:
                        merged_data[k] = v
                existing_l16.data = merged_data
                from sqlalchemy.orm.attributes import flag_modified as _fm
                _fm(existing_l16, "data")
                merged_into = existing_l16.id
                tax_filing = existing_l16  # reuse for response

        if not merged_into:
            # Create new TaxFilingData record
            tax_filing = TaxFilingData(
                user_id=current_user.id,
                tax_year=tax_year,
                data_type=data_type,
                source_document_id=document_id,
                data=data,
                status="confirmed",
                confirmed_at=datetime.utcnow(),
            )
            db.add(tax_filing)

        # Handle loss carryforward for E1a / Jahresabschluss with losses
        if data_type in ("e1a", "jahresabschluss"):
            gewinn_verlust = data.get("gewinn_verlust")
            if gewinn_verlust is not None and float(gewinn_verlust) < 0:
                try:
                    from app.models.loss_carryforward import LossCarryforward

                    existing = (
                        db.query(LossCarryforward)
                        .filter(
                            LossCarryforward.user_id == current_user.id,
                            LossCarryforward.loss_year == tax_year,
                        )
                        .first()
                    )
                    loss_amount = abs(float(gewinn_verlust))
                    if existing:
                        existing.loss_amount = loss_amount
                        existing.remaining_amount = loss_amount - float(
                            existing.used_amount or 0
                        )
                    else:
                        lcf = LossCarryforward(
                            user_id=current_user.id,
                            loss_year=tax_year,
                            loss_amount=loss_amount,
                            used_amount=0,
                            remaining_amount=loss_amount,
                        )
                        db.add(lcf)
                except Exception as lcf_err:
                    logger.warning(
                        f"Could not update loss carryforward for doc {document_id}: {lcf_err}"
                    )

        # Mark suggestion as confirmed
        updated_ocr = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
        if updated_ocr.get("import_suggestion"):
            updated_ocr["import_suggestion"]["status"] = "confirmed"
            updated_ocr["import_suggestion"]["tax_filing_data_id"] = tax_filing.id
            if merged_into:
                updated_ocr["import_suggestion"]["merged_into"] = merged_into
            document.ocr_result = updated_ocr
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(document, "ocr_result")

        db.commit()

        resp = {
            "message": f"Tax data ({data_type}) confirmed successfully",
            "tax_filing_data_id": tax_filing.id,
            "data_type": data_type,
            "tax_year": tax_year,
        }
        if merged_into:
            resp["merged"] = True
            resp["message"] = f"L16 data merged with existing record for {tax_year}"
        return resp
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to confirm tax data for doc {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Task 4.8: Bank transaction batch import from Kontoauszug OCR
# ---------------------------------------------------------------------------


class BankTransactionImportRequest(BaseModel):
    """Request body for batch bank transaction import."""
    transaction_indices: List[int] = []  # indices into the extracted transactions array


@router.post("/{document_id}/confirm-bank-transactions")
def confirm_bank_transactions(
    document_id: int,
    body: BankTransactionImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Batch-import selected transactions from a bank statement OCR result.

    Reads the extracted transactions from ocr_result.import_suggestion.data.transactions,
    creates Transaction records for the selected indices, and auto-classifies each one.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    ocr_result = document.ocr_result or {}
    suggestion = ocr_result.get("import_suggestion", {})
    if suggestion.get("type") != "import_bank_statement":
        raise HTTPException(status_code=400, detail="Document is not a bank statement")

    extracted_txns = (suggestion.get("data") or {}).get("transactions", [])
    if not extracted_txns:
        raise HTTPException(status_code=400, detail="No transactions found in OCR result")

    from app.models.transaction import Transaction as TxnModel, TransactionType
    from datetime import date as date_type

    indices = body.transaction_indices
    if not indices:
        indices = list(range(len(extracted_txns)))

    created_ids = []
    skipped = 0

    for idx in indices:
        if idx < 0 or idx >= len(extracted_txns):
            continue
        txn = extracted_txns[idx]
        if txn.get("is_duplicate"):
            skipped += 1
            continue

        amount = abs(float(txn.get("amount", 0)))
        if amount == 0:
            continue

        raw_amount = float(txn.get("amount", 0))
        txn_type = TransactionType.INCOME if raw_amount > 0 else TransactionType.EXPENSE

        # Parse date
        txn_date = None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                txn_date = datetime.strptime(txn.get("date", ""), fmt).date()
                break
            except (ValueError, TypeError):
                continue
        if not txn_date:
            txn_date = date_type.today()

        desc = txn.get("description") or txn.get("purpose") or txn.get("counterparty") or ""
        new_txn = TxnModel(
            user_id=current_user.id,
            type=txn_type,
            amount=amount,
            transaction_date=txn_date,
            description=desc[:500],
            document_id=document_id,
            import_source="ocr",
            needs_review=True,
        )
        db.add(new_txn)
        db.flush()
        created_ids.append(new_txn.id)

    # Auto-classify created transactions
    classified = 0
    try:
        from app.services.transaction_classifier import TransactionClassifier
        classifier = TransactionClassifier(db)
        for txn_id in created_ids:
            try:
                t = db.query(TxnModel).get(txn_id)
                if t:
                    classifier.classify(t)
                    classified += 1
            except Exception:
                pass
    except Exception as cls_err:
        logger.warning(f"Auto-classification failed for bank import: {cls_err}")

    # Mark suggestion as confirmed
    import json as _json2
    updated_ocr = _json2.loads(_json2.dumps(document.ocr_result)) if document.ocr_result else {}
    if updated_ocr.get("import_suggestion"):
        updated_ocr["import_suggestion"]["status"] = "confirmed"
        updated_ocr["import_suggestion"]["imported_count"] = len(created_ids)
        document.ocr_result = updated_ocr
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(document, "ocr_result")

    db.commit()

    return {
        "message": f"Imported {len(created_ids)} transactions, classified {classified}",
        "created_transaction_ids": created_ids,
        "imported": len(created_ids),
        "skipped_duplicates": skipped,
        "classified": classified,
    }


# =============================================================================
# AI Unified Interaction — Process Status & Follow-Up Endpoints
# =============================================================================

# --- Action Descriptor Builder ---

_ACTION_MAP = {
    "create_property": {"kind": "confirm_property", "endpoint_suffix": "confirm-property"},
    "create_asset": {"kind": "confirm_asset", "endpoint_suffix": "confirm-asset"},
    "create_recurring_income": {"kind": "confirm_recurring", "endpoint_suffix": "confirm-recurring"},
    "create_recurring_expense": {"kind": "confirm_recurring_expense", "endpoint_suffix": "confirm-recurring-expense"},
    "create_loan": {"kind": "confirm_loan", "endpoint_suffix": "confirm-loan"},
}

_CONFIRM_LABELS = {
    "confirm_property": {"de": "Immobilie erstellen", "en": "Create Property", "zh": "创建房产"},
    "confirm_asset": {"de": "Anlage erstellen", "en": "Create Asset", "zh": "创建资产"},
    "confirm_recurring": {"de": "Dauerauftrag bestätigen", "en": "Confirm Recurring", "zh": "确认定期交易"},
    "confirm_recurring_expense": {"de": "Wiederkehrende Ausgabe bestätigen", "en": "Confirm Recurring Expense", "zh": "确认定期支出"},
    "confirm_tax_data": {"de": "Steuerdaten importieren", "en": "Import Tax Data", "zh": "导入税务数据"},
    "confirm_loan": {"de": "Kredit erstellen", "en": "Create Loan", "zh": "创建贷款"},
}

_DISMISS_LABELS = {
    "confirm_property": {"de": "Keine Immobilie", "en": "Not a Property", "zh": "不是房产"},
    "confirm_asset": {"de": "Keine Anlage", "en": "Not an Asset", "zh": "不是资产"},
    "confirm_recurring": {"de": "Nicht wiederkehrend", "en": "Not Recurring", "zh": "不是定期交易"},
    "confirm_recurring_expense": {"de": "Nicht wiederkehrend", "en": "Not Recurring", "zh": "不是定期支出"},
    "confirm_tax_data": {"de": "Überspringen", "en": "Skip", "zh": "跳过"},
    "confirm_loan": {"de": "Kein Kredit", "en": "Not a Loan", "zh": "不是贷款"},
}


def _build_action_descriptor(suggestion_type: str, document_id: int) -> Optional[Dict[str, Any]]:
    """Build a unified action descriptor for the frontend."""
    if suggestion_type.startswith("import_"):
        kind = "confirm_tax_data"
        endpoint_suffix = "confirm-tax-data"
    elif suggestion_type in _ACTION_MAP:
        kind = _ACTION_MAP[suggestion_type]["kind"]
        endpoint_suffix = _ACTION_MAP[suggestion_type]["endpoint_suffix"]
    else:
        return None

    return {
        "kind": kind,
        "target_id": str(document_id),
        "endpoint": f"/api/v1/documents/{document_id}/{endpoint_suffix}",
        "method": "POST",
        "confirm_label": _CONFIRM_LABELS.get(kind),
        "dismiss_label": _DISMISS_LABELS.get(kind),
    }


# --- UI State Derivation ---

_PHASE_MESSAGES = {
    "processing_phase_1": {
        "de": "Dokument wird analysiert...",
        "en": "Analyzing your document...",
        "zh": "正在分析您的文档...",
    },
    "first_result_available": {
        "de": "Erste Ergebnisse verfügbar, Daten werden extrahiert...",
        "en": "First results available, extracting details...",
        "zh": "初步结果已出，正在提取详情...",
    },
    "finalizing": {
        "de": "Verarbeitung wird abgeschlossen...",
        "en": "Finalizing processing...",
        "zh": "正在完成处理...",
    },
    "completed": {
        "de": "Verarbeitung abgeschlossen.",
        "en": "Processing complete.",
        "zh": "处理完成。",
    },
    "phase_2_failed": {
        "de": "Verarbeitung fehlgeschlagen. Bitte versuchen Sie es erneut.",
        "en": "Processing failed. Please try again.",
        "zh": "处理失败，请重试。",
    },
}


def _derive_ui_state(current_state: str, suggestion: Optional[Dict]) -> str:
    """Single source of truth for frontend UI state."""
    if current_state in ("processing_phase_1", "first_result_available", "finalizing"):
        return "processing"
    if current_state == "phase_2_failed":
        return "error"
    if not suggestion:
        return "confirmed"  # No suggestion = already processed or nothing to suggest
    status = suggestion.get("status", "")
    if status == "confirmed":
        return "confirmed"
    if status == "dismissed":
        return "dismissed"
    if suggestion.get("follow_up_questions") and len(suggestion["follow_up_questions"]) > 0:
        return "needs_input"
    return "ready_to_confirm"


def _get_phase_message(current_state: str, lang: str, doc_type: Optional[str] = None) -> str:
    """Get human-readable phase message in the user's language."""
    messages = _PHASE_MESSAGES.get(current_state, _PHASE_MESSAGES["processing_phase_1"])
    base_msg = messages.get(lang, messages.get("en", "Processing..."))

    # If we know the doc type in first_result_available, include it
    if current_state == "first_result_available" and doc_type:
        type_prefix = {
            "de": f"Erkannt als {doc_type}. ",
            "en": f"Identified as {doc_type}. ",
            "zh": f"识别为 {doc_type}。",
        }
        prefix = type_prefix.get(lang, type_prefix["en"])
        return prefix + base_msg

    return base_msg


@router.get("/{document_id}/process-status", response_model=ProcessStatusResponse)
def get_process_status(
    document_id: int,
    lang: str = Query("en", description="Language: en, de, zh"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return current processing phase for a document.
    Frontend polls this endpoint to show real-time progress in the chat panel.

    Returns ui_state (single stable enum), idempotency_key (backend-generated),
    phase timestamps, suggestion version, and action descriptor.
    """
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    ocr_result = document.ocr_result or {}
    pipeline_meta = ocr_result.get("_pipeline", {})
    current_state = pipeline_meta.get("current_state", "processing_phase_1")

    # Get suggestion if processing is complete
    suggestion = ocr_result.get("import_suggestion") if current_state == "completed" else None

    # Derive UI state
    ui_state = _derive_ui_state(current_state, suggestion)

    # Build action descriptor if suggestion exists
    action = None
    if suggestion:
        action = _build_action_descriptor(suggestion.get("type", ""), document_id)

    # Build idempotency key — BACKEND is source of truth
    suggestion_type = suggestion.get("type", "none") if suggestion else "none"
    idempotency_key = f"{document_id}:{suggestion_type}:{current_state}"

    # Phase timestamps from checkpoints
    phase_started_at = None
    phase_updated_at = None
    current_phase_attempt = 1
    checkpoints = pipeline_meta.get("phase_checkpoints", [])
    if checkpoints:
        last_cp = checkpoints[-1] if isinstance(checkpoints[-1], dict) else {}
        phase_started_at = last_cp.get("started_at")
        phase_updated_at = last_cp.get("completed_at") or last_cp.get("started_at")

    # Suggestion version
    suggestion_version = suggestion.get("version", 0) if suggestion else None

    # Follow-up questions
    follow_up_questions = None
    if suggestion and suggestion.get("follow_up_questions"):
        follow_up_questions = suggestion["follow_up_questions"]

    # Human-readable message
    doc_type_str = document.document_type.value if document.document_type else None
    message = _get_phase_message(current_state, lang, doc_type_str)

    return ProcessStatusResponse(
        phase=current_state,
        document_type=doc_type_str,
        message=message,
        ui_state=ui_state,
        suggestion=suggestion,
        phase_started_at=phase_started_at,
        phase_updated_at=phase_updated_at,
        current_phase_attempt=current_phase_attempt,
        suggestion_version=suggestion_version,
        idempotency_key=idempotency_key,
        action=action,
        follow_up_questions=follow_up_questions,
    )


@router.post("/{document_id}/follow-up", response_model=FollowUpAnswerResponse)
def submit_follow_up_answers(
    document_id: int,
    body: FollowUpAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit user answers to follow-up questions for a document suggestion.

    Supports three modes:
    1. Full answers: All questions answered → suggestion becomes ready_to_confirm
    2. Partial answers: Some answered → remaining questions re-presented (order preserved)
    3. Use defaults: apply default_value for all unanswered questions

    Enforces optimistic concurrency via suggestion_version.
    """
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    import json as _json
    ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
    suggestion = ocr_result.get("import_suggestion")

    if not suggestion:
        raise HTTPException(status_code=400, detail="No pending suggestion for this document")

    # Optimistic concurrency check
    current_version = suggestion.get("version", 0)
    if body.suggestion_version is not None and body.suggestion_version != current_version:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "suggestion_version_mismatch",
                "current_version": current_version,
                "message": "Suggestion was modified by another session. Please refresh and try again.",
            },
        )

    suggestion_data = suggestion.get("data", {})
    all_questions = suggestion.get("follow_up_questions", [])

    # Apply explicit user answers
    suggestion_data.update(body.answers)

    # Track which defaults were applied (for chat feedback message)
    applied_defaults: Dict[str, Any] = {}

    if body.use_defaults:
        # Apply default_value for all questions NOT in body.answers
        for q in all_questions:
            if q["field_key"] not in body.answers and q.get("default_value") is not None:
                suggestion_data[q["field_key"]] = q["default_value"]
                applied_defaults[q["field_key"]] = {
                    "value": q["default_value"],
                    "question": q.get("question", {}),
                }
        remaining_questions = []
    else:
        # Only clear answered questions, preserve order of remaining
        answered_keys = set(body.answers.keys())
        remaining_questions = [
            q for q in all_questions
            if q["field_key"] not in answered_keys
        ]

    suggestion["follow_up_questions"] = remaining_questions
    suggestion["data"] = suggestion_data

    # Derive new status
    if not remaining_questions:
        suggestion["status"] = "ready_to_confirm"
    else:
        suggestion["status"] = "needs_input"

    # Bump version for optimistic concurrency
    suggestion["version"] = current_version + 1

    ocr_result["import_suggestion"] = suggestion
    document.ocr_result = ocr_result

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(document, "ocr_result")
    db.commit()

    return FollowUpAnswerResponse(
        status="updated",
        ui_state="ready_to_confirm" if not remaining_questions else "needs_input",
        suggestion_version=suggestion["version"],
        remaining_questions=len(remaining_questions),
        remaining_question_list=remaining_questions,
        applied_defaults=applied_defaults,
    )
