"""OCR processing tasks"""
from celery import Task, group
from typing import List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
import logging

from app.celery_app import celery_app
from app.services.ocr_engine import OCREngine

logger = logging.getLogger(__name__)


def _make_json_safe(obj):
    """Recursively convert datetime/Decimal objects to JSON-safe types."""
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_json_safe(v) for v in obj]
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


class OCRTask(Task):
    """Base OCR task with error handling"""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"OCR task {task_id} failed: {exc}")
        logger.error(f"Traceback: {einfo}")


def run_ocr_sync(document_id: int, db=None) -> Dict[str, Any]:
    """
    Run OCR processing synchronously (used as fallback when Celery is unavailable).
    Can also be called from the Celery task.
    """
    from app.db.base import SessionLocal
    from app.models.document import Document

    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return {"error": "Document not found", "document_id": document_id}

        from app.services.storage_service import StorageService

        storage = StorageService()
        image_bytes = storage.download_file(document.file_path)

        ocr_engine = OCREngine()
        result = ocr_engine.process_document(image_bytes, mime_type=document.mime_type)

        document.ocr_result = _make_json_safe(result.extracted_data)
        document.raw_text = result.raw_text
        document.confidence_score = result.confidence_score

        from app.models.document import DocumentType as DBDocumentType
        from app.services.document_classifier import DocumentType as OCRDocumentType

        OCR_TO_DB_TYPE_MAP = {
            OCRDocumentType.KAUFVERTRAG: DBDocumentType.PURCHASE_CONTRACT,
            OCRDocumentType.MIETVERTRAG: DBDocumentType.RENTAL_CONTRACT,
            OCRDocumentType.RENTAL_CONTRACT: DBDocumentType.RENTAL_CONTRACT,
            OCRDocumentType.E1_FORM: DBDocumentType.E1_FORM,
            OCRDocumentType.EINKOMMENSTEUERBESCHEID: DBDocumentType.EINKOMMENSTEUERBESCHEID,
            OCRDocumentType.UNKNOWN: DBDocumentType.OTHER,
        }

        ocr_type = result.document_type
        if ocr_type in OCR_TO_DB_TYPE_MAP:
            document.document_type = OCR_TO_DB_TYPE_MAP[ocr_type]
        else:
            try:
                document.document_type = DBDocumentType[ocr_type.name]
            except KeyError:
                logger.warning(
                    f"Unknown OCR document type '{ocr_type.value}' for document {document_id}, "
                    f"keeping as OTHER"
                )
                document.document_type = DBDocumentType.OTHER

        # Filename-based classification boost
        fname_lower = (document.file_name or "").lower()
        current_dt = document.document_type
        if current_dt in (DBDocumentType.OTHER,):
            if "kaufvertrag" in fname_lower:
                document.document_type = DBDocumentType.PURCHASE_CONTRACT
            elif "mietvertrag" in fname_lower or "miete" in fname_lower or "pacht" in fname_lower:
                document.document_type = DBDocumentType.RENTAL_CONTRACT
            elif "gehalt" in fname_lower or "lohn" in fname_lower:
                document.document_type = DBDocumentType.LOHNZETTEL
            elif "rechnung" in fname_lower or "invoice" in fname_lower:
                document.document_type = DBDocumentType.INVOICE
            elif "beleg" in fname_lower or "receipt" in fname_lower or "bon" in fname_lower:
                document.document_type = DBDocumentType.RECEIPT
            elif "svs" in fname_lower:
                document.document_type = DBDocumentType.SVS_NOTICE
            elif "kontoauszug" in fname_lower:
                document.document_type = DBDocumentType.BANK_STATEMENT
            elif "einkommensteuererkl" in fname_lower or "e1" in fname_lower:
                document.document_type = DBDocumentType.E1_FORM
            elif "bescheid" in fname_lower:
                document.document_type = DBDocumentType.EINKOMMENSTEUERBESCHEID

        document.processed_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"OCR processing completed for document {document_id} "
            f"(confidence: {result.confidence_score:.2f})"
        )

        # Build import suggestions based on document type
        result_dict = result.to_dict()

        if document.document_type == DBDocumentType.PURCHASE_CONTRACT:
            try:
                result_dict.update(_build_kaufvertrag_suggestion(db, document, result))
            except Exception as e:
                logger.warning(f"Build Kaufvertrag suggestion failed for document {document_id}: {e}")
                result_dict["import_suggestion"] = None

        elif document.document_type == DBDocumentType.RENTAL_CONTRACT:
            try:
                result_dict.update(_build_mietvertrag_suggestion(db, document, result))
            except Exception as e:
                logger.warning(f"Build Mietvertrag suggestion failed for document {document_id}: {e}")
                result_dict["import_suggestion"] = None

        else:
            try:
                from app.services.ocr_transaction_service import OCRTransactionService
                ocr_transaction_service = OCRTransactionService(db)
                suggestion = ocr_transaction_service.create_transaction_suggestion(
                    document_id, document.user_id
                )
                if suggestion:
                    logger.info(f"Created transaction suggestion for document {document_id}")
                    try:
                        transaction = ocr_transaction_service.create_transaction_from_suggestion(
                            suggestion, document.user_id
                        )
                        logger.info(
                            f"Auto-created transaction {transaction.id} from document "
                            f"{document_id}"
                        )
                        result_dict["transaction_suggestion"] = suggestion
                        result_dict["transaction_created"] = True
                        result_dict["transaction_id"] = transaction.id
                    except Exception as e:
                        logger.warning(f"Could not auto-create transaction from document {document_id}: {e}")
                        result_dict["transaction_suggestion"] = suggestion
                        result_dict["transaction_created"] = False
            except Exception as e:
                logger.warning(f"Could not create transaction suggestion: {e}")

        return result_dict

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing document {document_id}: {str(e)}")
        # Mark document as processed even on failure so frontend stops polling
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document and not document.processed_at:
                document.processed_at = datetime.utcnow()
                document.confidence_score = 0.0
                db.commit()
                logger.info(f"Marked failed document {document_id} as processed")
        except Exception as mark_err:
            logger.warning(f"Could not mark document {document_id} as processed: {mark_err}")
        raise
    finally:
        if own_session:
            db.close()


def _build_kaufvertrag_suggestion(db, document, result) -> dict:
    """
    Build a property creation suggestion from Kaufvertrag OCR data.
    Does NOT create any records — only stores suggestion data for user confirmation.
    Returns dict with suggestion keys to merge into ocr_result.
    """
    ocr_data = document.ocr_result or {}
    if not isinstance(ocr_data, dict):
        return {"import_suggestion": None}

    purchase_price = ocr_data.get("purchase_price")
    property_address = ocr_data.get("property_address")

    if not purchase_price or not property_address:
        logger.info(
            f"Kaufvertrag doc {document.id}: missing purchase_price or address, "
            f"skipping suggestion"
        )
        return {"import_suggestion": None}

    from decimal import Decimal
    from datetime import datetime as dt

    purchase_price_dec = Decimal(str(purchase_price))
    address = str(property_address)
    street = str(ocr_data.get("street") or address)
    city = str(ocr_data.get("city") or "Unbekannt")
    postal_code = str(ocr_data.get("postal_code") or "0000")

    # purchase_date: try OCR, fallback to document upload date
    pd_raw = ocr_data.get("purchase_date")
    if pd_raw:
        if isinstance(pd_raw, str):
            purchase_date = None
            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    purchase_date = dt.strptime(pd_raw, fmt).date().isoformat()
                    break
                except ValueError:
                    continue
            if not purchase_date:
                purchase_date = document.uploaded_at.date().isoformat()
        else:
            purchase_date = pd_raw.isoformat() if hasattr(pd_raw, "isoformat") else str(pd_raw)
    else:
        purchase_date = document.uploaded_at.date().isoformat()

    building_value = (
        float(ocr_data["building_value"])
        if ocr_data.get("building_value")
        else float((purchase_price_dec * Decimal("0.8")).quantize(Decimal("0.01")))
    )
    land_value = float(purchase_price_dec) - building_value

    suggestion = {
        "type": "create_property",
        "status": "pending",
        "data": {
            "address": address,
            "street": street,
            "city": city,
            "postal_code": postal_code,
            "purchase_date": purchase_date,
            "purchase_price": float(purchase_price_dec),
            "building_value": building_value,
            "land_value": land_value,
            "construction_year": ocr_data.get("construction_year"),
            "grunderwerbsteuer": float(ocr_data["grunderwerbsteuer"]) if ocr_data.get("grunderwerbsteuer") else None,
            "notary_fees": float(ocr_data["notary_fees"]) if ocr_data.get("notary_fees") else None,
            "registry_fees": float(ocr_data["registry_fees"]) if ocr_data.get("registry_fees") else None,
        },
    }

    logger.info(
        f"Built property suggestion for Kaufvertrag doc {document.id}: "
        f"address={address}, price={purchase_price}"
    )

    # Save suggestion into document's ocr_result
    updated_ocr = document.ocr_result.copy() if document.ocr_result else {}
    updated_ocr["import_suggestion"] = suggestion
    document.ocr_result = updated_ocr
    db.commit()

    return {"import_suggestion": suggestion}


def create_property_from_suggestion(db, document, suggestion_data: dict) -> dict:
    """
    Create property from a confirmed suggestion.
    Called by the confirmation API endpoint after user approves.
    Uses PropertyService to ensure proper validation and encryption.
    """
    from app.services.property_service import PropertyService
    from app.schemas.property import PropertyCreate
    from app.models.property import PropertyType
    from decimal import Decimal
    from datetime import datetime as dt

    data = suggestion_data
    user_id = int(document.user_id)
    
    # Extract and validate required fields
    purchase_price = Decimal(str(data["purchase_price"]))
    
    # Parse address fields - ensure all required fields are present
    address = str(data.get("address", ""))
    street = str(data.get("street") or address or "Unbekannt")
    city = str(data.get("city") or "Unbekannt")
    postal_code = str(data.get("postal_code") or "0000")
    
    # Parse purchase_date
    pd_raw = data.get("purchase_date")
    if pd_raw:
        if isinstance(pd_raw, str):
            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    purchase_date = dt.strptime(pd_raw, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                purchase_date = document.uploaded_at.date()
        else:
            purchase_date = pd_raw
    else:
        purchase_date = document.uploaded_at.date()

    # Optional fields
    building_value = (
        Decimal(str(data["building_value"]))
        if data.get("building_value")
        else None  # Let PropertyCreate schema auto-calculate
    )
    
    construction_year = data.get("construction_year")
    
    grunderwerbsteuer = (
        Decimal(str(data["grunderwerbsteuer"])) if data.get("grunderwerbsteuer") else None
    )
    notary_fees = Decimal(str(data["notary_fees"])) if data.get("notary_fees") else None
    registry_fees = (
        Decimal(str(data["registry_fees"])) if data.get("registry_fees") else None
    )

    # Build PropertyCreate schema for validation
    property_data = PropertyCreate(
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street=street,
        city=city,
        postal_code=postal_code,
        purchase_date=purchase_date,
        purchase_price=purchase_price,
        building_value=building_value,
        construction_year=construction_year,
        depreciation_rate=None,  # Let schema auto-determine
        grunderwerbsteuer=grunderwerbsteuer,
        notary_fees=notary_fees,
        registry_fees=registry_fees,
    )

    # Use PropertyService to create property with proper validation
    property_service = PropertyService(db)
    prop = property_service.create_property(user_id, property_data)
    
    # Link to kaufvertrag document
    prop.kaufvertrag_document_id = int(document.id)
    db.commit()
    db.refresh(prop)

    logger.info(
        f"Created property {prop.id} from confirmed suggestion for doc {document.id}"
    )

    # Mark suggestion as confirmed (deep copy to trigger SQLAlchemy change detection)
    import json as _json
    ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
    if ocr_result.get("import_suggestion"):
        ocr_result["import_suggestion"]["status"] = "confirmed"
        ocr_result["import_suggestion"]["property_id"] = str(prop.id)
        document.ocr_result = ocr_result
        db.commit()

    return {
        "property_created": True,
        "property_id": str(prop.id),
        "address": prop.address,
        "purchase_price": float(prop.purchase_price),
    }


def _build_mietvertrag_suggestion(db, document, result) -> dict:
    """
    Build a recurring rental income suggestion from Mietvertrag OCR data.
    Does NOT create any records — only stores suggestion data for user confirmation.
    Returns dict with suggestion keys to merge into ocr_result.
    """
    from app.services.address_matcher import AddressMatcher
    from decimal import Decimal
    from datetime import date as date_type, datetime as dt

    ocr_data = document.ocr_result or {}
    if not isinstance(ocr_data, dict):
        return {"import_suggestion": None}

    monthly_rent = ocr_data.get("monthly_rent")
    if not monthly_rent:
        return {"import_suggestion": None}

    monthly_rent = Decimal(str(monthly_rent))
    address = ocr_data.get("property_address", "")

    # Parse start_date
    sd_raw = ocr_data.get("start_date")
    if sd_raw:
        if isinstance(sd_raw, str):
            start_date = None
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
                try:
                    start_date = dt.strptime(sd_raw, fmt).date()
                    break
                except ValueError:
                    continue
            if not start_date:
                start_date = document.uploaded_at.date()
        else:
            start_date = sd_raw
    else:
        start_date = document.uploaded_at.date()

    # Parse end_date
    ed_raw = ocr_data.get("end_date")
    end_date = None
    if ed_raw:
        if isinstance(ed_raw, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
                try:
                    end_date = dt.strptime(ed_raw, fmt).date()
                    break
                except ValueError:
                    continue

    # Try to match property by address
    matched_property_id = None
    matched_property_address = None
    if address:
        try:
            matcher = AddressMatcher(db)
            matches = matcher.match_address(address, document.user_id)
            if matches and matches[0].confidence > 0.3:
                matched_property_id = str(matches[0].property.id)
                matched_property_address = matches[0].property.address
            else:
                # Fallback: try matching by street name only
                from app.models.property import Property as PropertyModel, PropertyStatus
                user_props = (
                    db.query(PropertyModel)
                    .filter(
                        PropertyModel.user_id == document.user_id,
                        PropertyModel.status == PropertyStatus.ACTIVE,
                    )
                    .all()
                )
                addr_lower = address.lower()
                for p in user_props:
                    p_street = (p.street or "").lower()
                    if p_street and p_street in addr_lower:
                        matched_property_id = str(p.id)
                        matched_property_address = p.address
                        break
        except Exception as e:
            logger.warning(f"Address matching failed for Mietvertrag doc {document.id}: {e}")

    suggestion = {
        "type": "create_recurring_income",
        "status": "pending",
        "data": {
            "monthly_rent": float(monthly_rent),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat() if end_date else None,
            "address": address,
            "tenant_name": ocr_data.get("tenant_name"),
            "landlord_name": ocr_data.get("landlord_name"),
            "matched_property_id": matched_property_id,
            "matched_property_address": matched_property_address,
        },
    }

    logger.info(
        f"Built recurring income suggestion for Mietvertrag doc {document.id}: "
        f"rent=€{monthly_rent}, property_match={matched_property_id}"
    )

    # Save suggestion into document's ocr_result
    updated_ocr = document.ocr_result.copy() if document.ocr_result else {}
    updated_ocr["import_suggestion"] = suggestion
    document.ocr_result = updated_ocr
    db.commit()

    return {"import_suggestion": suggestion}


def create_recurring_from_suggestion(db, document, suggestion_data: dict) -> dict:
    """
    Create recurring rental income from a confirmed suggestion.
    Called by the confirmation API endpoint after user approves.
    """
    from app.services.recurring_transaction_service import RecurringTransactionService
    from decimal import Decimal
    from datetime import datetime as dt

    data = suggestion_data
    monthly_rent = Decimal(str(data["monthly_rent"]))
    property_id = data.get("matched_property_id")

    if not property_id:
        raise ValueError("No matching property found. Please create the property first.")

    # Parse start_date
    sd_raw = data.get("start_date")
    if sd_raw and isinstance(sd_raw, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                start_date = dt.strptime(sd_raw, fmt).date()
                break
            except ValueError:
                continue
        else:
            start_date = document.uploaded_at.date()
    else:
        start_date = document.uploaded_at.date()

    # Parse end_date
    ed_raw = data.get("end_date")
    end_date = None
    if ed_raw and isinstance(ed_raw, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                end_date = dt.strptime(ed_raw, fmt).date()
                break
            except ValueError:
                continue

    # Link mietvertrag document to property
    from app.models.property import Property as PropertyModel
    prop = db.query(PropertyModel).filter(PropertyModel.id == property_id).first()
    if prop:
        prop.mietvertrag_document_id = document.id

    service = RecurringTransactionService(db)
    recurring = service.create_rental_income_recurring(
        user_id=document.user_id,
        property_id=property_id,
        monthly_rent=monthly_rent,
        start_date=start_date,
        end_date=end_date,
    )

    logger.info(
        f"Created recurring rental income {recurring.id} from confirmed suggestion "
        f"for doc {document.id} (rent=€{monthly_rent}, property={property_id})"
    )

    # Mark suggestion as confirmed (deep copy to trigger SQLAlchemy change detection)
    import json as _json
    ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
    if ocr_result.get("import_suggestion"):
        ocr_result["import_suggestion"]["status"] = "confirmed"
        ocr_result["import_suggestion"]["recurring_id"] = recurring.id
        document.ocr_result = ocr_result
        db.commit()

    return {
        "recurring_created": True,
        "recurring_id": recurring.id,
        "property_id": property_id,
        "monthly_rent": float(monthly_rent),
    }


@celery_app.task(base=OCRTask, bind=True, soft_time_limit=300, time_limit=360)
def process_document_ocr(self, document_id: int) -> Dict[str, Any]:
    """
    Process single document OCR in background.
    Delegates to run_ocr_sync which contains the actual logic.
    """
    return run_ocr_sync(document_id)


@celery_app.task(base=OCRTask, bind=True)
def batch_process_documents(self, document_ids: List[int]) -> Dict[str, Any]:
    """
    Batch process multiple documents in parallel

    Args:
        document_ids: List of document IDs to process

    Returns:
        Dictionary with batch processing results
    """
    logger.info(f"Starting batch OCR processing for {len(document_ids)} documents")

    try:
        # Create parallel task group
        job = group(process_document_ocr.s(doc_id) for doc_id in document_ids)

        # Execute tasks in parallel
        result = job.apply_async()

        # Wait for all tasks to complete (with timeout)
        results = result.get(timeout=300)  # 5 minute timeout

        # Aggregate results
        success_count = sum(1 for r in results if "error" not in r)
        failure_count = len(results) - success_count

        logger.info(
            f"Batch OCR processing completed: "
            f"{success_count} succeeded, {failure_count} failed"
        )

        return {
            "total": len(document_ids),
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results,
        }

    except Exception as e:
        logger.error(f"Batch OCR processing failed: {str(e)}")
        raise


@celery_app.task(base=OCRTask, bind=True)
def process_document_ocr_from_bytes(self, image_bytes: bytes, user_id: int) -> Dict[str, Any]:
    """
    Process OCR directly from image bytes (for immediate processing)

    Args:
        image_bytes: Image file as bytes
        user_id: User ID for tracking

    Returns:
        Dictionary with OCR result
    """
    try:
        logger.info(f"Processing OCR from bytes for user {user_id}")

        ocr_engine = OCREngine()
        result = ocr_engine.process_document(image_bytes)

        logger.info(
            f"OCR processing completed for user {user_id} "
            f"(confidence: {result.confidence_score:.2f})"
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Error processing OCR from bytes: {str(e)}")
        raise


@celery_app.task(base=OCRTask, bind=True)
def batch_process_documents_from_bytes(
    self, images_data: List[Dict[str, Any]], user_id: int
) -> Dict[str, Any]:
    """
    Batch process multiple documents from bytes

    Args:
        images_data: List of dicts with 'image_bytes' and 'filename'
        user_id: User ID for tracking

    Returns:
        Dictionary with batch processing results
    """
    from app.services.ocr_engine import OCREngine

    logger.info(f"Starting batch OCR processing for {len(images_data)} images (user {user_id})")

    try:
        ocr_engine = OCREngine()

        # Extract image bytes
        image_bytes_list = [img["image_bytes"] for img in images_data]

        # Process batch
        batch_result = ocr_engine.process_batch(image_bytes_list)

        logger.info(
            f"Batch OCR processing completed for user {user_id}: "
            f"{batch_result.success_count} succeeded, {batch_result.failure_count} failed"
        )

        return batch_result.to_dict()

    except Exception as e:
        logger.error(f"Batch OCR processing from bytes failed: {str(e)}")
        raise


@celery_app.task(base=OCRTask, bind=True)
def reprocess_low_confidence_documents(self, threshold: float = 0.6) -> Dict[str, Any]:
    """
    Reprocess documents with low confidence scores

    Args:
        threshold: Confidence threshold (default 0.6)

    Returns:
        Dictionary with reprocessing results
    """
    from app.db.base import SessionLocal
    from app.models.document import Document

    db = SessionLocal()
    try:
        # Find documents with low confidence
        low_confidence_docs = (
            db.query(Document)
            .filter(Document.confidence_score < threshold)
            .filter(Document.confidence_score > 0)  # Exclude unprocessed
            .all()
        )

        document_ids = [doc.id for doc in low_confidence_docs]

        logger.info(
            f"Found {len(document_ids)} documents with confidence < {threshold} "
            f"for reprocessing"
        )

        if not document_ids:
            return {"message": "No documents need reprocessing", "count": 0}

        # Batch reprocess
        result = batch_process_documents.delay(document_ids)

        return {
            "message": f"Reprocessing {len(document_ids)} documents",
            "count": len(document_ids),
            "task_id": result.id,
        }

    except Exception as e:
        logger.error(f"Error reprocessing low confidence documents: {str(e)}")
        raise
    finally:
        db.close()


@celery_app.task(base=OCRTask, bind=True, max_retries=3, soft_time_limit=180, time_limit=240)
def process_historical_import_ocr(self, upload_id: str) -> Dict[str, Any]:
    """
    Process OCR for historical import document with task chaining
    
    This task:
    1. Extracts text from the PDF using Tesseract
    2. Chains to the appropriate extractor service based on document type
    3. Updates the HistoricalImportUpload record with progress and results
    4. Handles errors gracefully with retry logic for transient failures
    
    Args:
        upload_id: UUID of the HistoricalImportUpload record
        
    Returns:
        Dictionary with OCR and extraction results
    """
    from app.db.base import SessionLocal
    from app.models.historical_import import (
        HistoricalImportUpload,
        ImportStatus,
        HistoricalDocumentType,
    )
    from app.models.document import Document
    from app.services.storage_service import StorageService
    from app.services.e1_form_extractor import E1FormExtractor
    from app.services.bescheid_extractor import BescheidExtractor
    from app.services.kaufvertrag_extractor import KaufvertragExtractor
    from uuid import UUID
    from decimal import Decimal
    
    db = SessionLocal()
    
    try:
        # Parse upload_id
        try:
            upload_uuid = UUID(upload_id)
        except ValueError:
            logger.error(f"Invalid upload_id format: {upload_id}")
            return {"error": "Invalid upload_id format", "upload_id": upload_id}
        
        # Fetch HistoricalImportUpload record
        upload = db.query(HistoricalImportUpload).filter(
            HistoricalImportUpload.id == upload_uuid
        ).first()
        
        if not upload:
            logger.error(f"HistoricalImportUpload {upload_id} not found")
            return {"error": "Upload not found", "upload_id": upload_id}
        
        # Update status to processing
        upload.status = ImportStatus.PROCESSING
        upload.ocr_task_id = self.request.id
        db.commit()
        
        logger.info(
            f"Starting historical import OCR processing: {upload_id} "
            f"(type={upload.document_type.value}, year={upload.tax_year})"
        )
        
        # Fetch associated document
        document = db.query(Document).filter(Document.id == upload.document_id).first()
        
        if not document:
            error_msg = f"Document {upload.document_id} not found"
            logger.error(error_msg)
            upload.status = ImportStatus.FAILED
            upload.errors = upload.errors + [{"error": error_msg, "timestamp": datetime.utcnow().isoformat()}]
            db.commit()
            return {"error": error_msg, "upload_id": upload_id}
        
        # Get document file from storage
        storage = StorageService()
        
        try:
            file_bytes = storage.download_file(document.file_path)
        except Exception as e:
            error_msg = f"Failed to download file from storage: {str(e)}"
            logger.error(error_msg)
            
            # Retry for transient storage errors
            if self.request.retries < self.max_retries:
                logger.info(f"Retrying OCR task (attempt {self.request.retries + 1}/{self.max_retries})")
                raise self.retry(exc=e, countdown=2 ** self.request.retries)
            
            upload.status = ImportStatus.FAILED
            upload.errors = upload.errors + [{"error": error_msg, "timestamp": datetime.utcnow().isoformat()}]
            db.commit()
            return {"error": error_msg, "upload_id": upload_id}
        
        # Process OCR based on document type
        ocr_text = None
        
        # For Saldenliste (CSV/Excel), skip OCR and use direct parsing
        if upload.document_type == HistoricalDocumentType.SALDENLISTE:
            logger.info(f"Skipping OCR for Saldenliste (structured file): {upload_id}")
            ocr_text = None  # Will be handled by SaldenlisteParser
        else:
            # Process OCR for PDF documents
            try:
                ocr_engine = OCREngine()
                ocr_result = ocr_engine.process_document(file_bytes)
                ocr_text = ocr_result.raw_text
                
                logger.info(
                    f"OCR completed for {upload_id} "
                    f"(confidence: {ocr_result.confidence_score:.2f})"
                )
            except Exception as e:
                error_msg = f"OCR processing failed: {str(e)}"
                logger.error(error_msg)
                
                # Retry for transient OCR errors
                if self.request.retries < self.max_retries:
                    logger.info(f"Retrying OCR task (attempt {self.request.retries + 1}/{self.max_retries})")
                    raise self.retry(exc=e, countdown=2 ** self.request.retries)
                
                upload.status = ImportStatus.FAILED
                upload.errors = upload.errors + [{"error": error_msg, "timestamp": datetime.utcnow().isoformat()}]
                db.commit()
                return {"error": error_msg, "upload_id": upload_id}
        
        # Extract structured data based on document type
        extracted_data = None
        confidence = 0.0
        
        try:
            if upload.document_type == HistoricalDocumentType.E1_FORM:
                extractor = E1FormExtractor()
                e1_data = extractor.extract(ocr_text)
                extracted_data = extractor.to_dict(e1_data)
                confidence = e1_data.confidence
                
            elif upload.document_type == HistoricalDocumentType.BESCHEID:
                extractor = BescheidExtractor()
                bescheid_data = extractor.extract(ocr_text)
                extracted_data = extractor.to_dict(bescheid_data)
                confidence = bescheid_data.confidence
                
            elif upload.document_type == HistoricalDocumentType.KAUFVERTRAG:
                extractor = KaufvertragExtractor()
                kaufvertrag_data = extractor.extract(ocr_text)
                extracted_data = extractor.to_dict(kaufvertrag_data)
                confidence = kaufvertrag_data.confidence
                
            elif upload.document_type == HistoricalDocumentType.SALDENLISTE:
                # Saldenliste parsing will be handled by SaldenlisteImportService
                # For now, mark as extracted and let the import service handle it
                extracted_data = {"file_path": document.file_path, "file_name": document.file_name}
                confidence = 1.0  # Structured data has high confidence
            
            logger.info(
                f"Extraction completed for {upload_id} "
                f"(type={upload.document_type.value}, confidence={confidence:.2f})"
            )
            
        except Exception as e:
            error_msg = f"Data extraction failed: {str(e)}"
            logger.error(error_msg)
            
            upload.status = ImportStatus.FAILED
            upload.errors = upload.errors + [{"error": error_msg, "timestamp": datetime.utcnow().isoformat()}]
            db.commit()
            return {"error": error_msg, "upload_id": upload_id}
        
        # Store extracted data and update status
        upload.extracted_data = _make_json_safe(extracted_data)
        upload.extraction_confidence = Decimal(str(confidence))
        
        # Determine if review is required based on confidence threshold
        confidence_thresholds = {
            HistoricalDocumentType.E1_FORM: 0.7,
            HistoricalDocumentType.BESCHEID: 0.7,
            HistoricalDocumentType.KAUFVERTRAG: 0.6,
            HistoricalDocumentType.SALDENLISTE: 0.8,
        }
        
        threshold = confidence_thresholds.get(upload.document_type, 0.7)
        upload.requires_review = confidence < threshold
        
        if upload.requires_review:
            upload.status = ImportStatus.REVIEW_REQUIRED
            logger.info(
                f"Upload {upload_id} requires review "
                f"(confidence {confidence:.2f} < threshold {threshold})"
            )
        else:
            upload.status = ImportStatus.EXTRACTED
            logger.info(f"Upload {upload_id} extracted successfully (confidence {confidence:.2f})")
        
        db.commit()
        
        # Return result
        result = {
            "upload_id": upload_id,
            "status": upload.status.value,
            "extracted_data": extracted_data,
            "confidence": confidence,
            "requires_review": upload.requires_review,
            "document_type": upload.document_type.value,
            "tax_year": upload.tax_year,
        }
        
        logger.info(f"Historical import OCR task completed: {upload_id}")
        
        return result
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing historical import OCR {upload_id}: {str(e)}")
        
        # Try to update upload status if possible
        try:
            upload = db.query(HistoricalImportUpload).filter(
                HistoricalImportUpload.id == UUID(upload_id)
            ).first()
            
            if upload:
                upload.status = ImportStatus.FAILED
                upload.errors = upload.errors + [
                    {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
                ]
                db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update upload status: {str(update_error)}")
        
        # Retry for unexpected errors
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying OCR task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        
        raise
        
    finally:
        db.close()

