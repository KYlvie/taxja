"""
Historical Import Orchestrator

Coordinates multi-document historical data import sessions and routes documents
to the appropriate import service. Handles the complete workflow from upload
to finalization.

This orchestrator:
1. Creates and manages import sessions
2. Routes documents to appropriate import services (E1, Bescheid, Kaufvertrag, Saldenliste)
3. Coordinates extraction and import processes
4. Handles errors and sets review flags
5. Generates comprehensive session summaries
6. Integrates with DuplicateDetector for cross-document duplicate prevention
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.historical_import import (
    HistoricalImportSession,
    HistoricalImportUpload,
    ImportSessionStatus,
    ImportStatus,
    HistoricalDocumentType,
)
from app.services.e1_form_import_service import E1FormImportService
from app.services.bescheid_import_service import BescheidImportService
from app.services.kaufvertrag_import_service import KaufvertragImportService
from app.services.saldenliste_import_service import SaldenlisteImportService
from app.services.duplicate_detector import DuplicateDetector

logger = logging.getLogger(__name__)


class HistoricalImportOrchestrator:
    """Orchestrates multi-document historical data import sessions."""

    # Confidence thresholds for review requirements
    CONFIDENCE_THRESHOLD_E1 = Decimal("0.7")
    CONFIDENCE_THRESHOLD_BESCHEID = Decimal("0.7")
    CONFIDENCE_THRESHOLD_KAUFVERTRAG = Decimal("0.6")
    CONFIDENCE_THRESHOLD_SALDENLISTE = Decimal("0.7")

    def __init__(self, db: Session):
        """
        Initialize the orchestrator with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.e1_import = E1FormImportService(db)
        self.bescheid_import = BescheidImportService(db)
        self.kaufvertrag_import = KaufvertragImportService(db)
        self.saldenliste_import = SaldenlisteImportService(db)
        self.duplicate_detector = DuplicateDetector(db)

    def create_session(
        self, user_id: int, tax_years: List[int], document_types: List[str]
    ) -> HistoricalImportSession:
        """
        Create a new import session.

        Args:
            user_id: User ID creating the session
            tax_years: List of tax years to import
            document_types: List of expected document types

        Returns:
            Created HistoricalImportSession object
        """
        session = HistoricalImportSession(
            user_id=user_id,
            status=ImportSessionStatus.ACTIVE,
            tax_years=sorted(tax_years),
            total_documents=0,
            successful_imports=0,
            failed_imports=0,
            transactions_created=0,
            properties_created=0,
            properties_linked=0,
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(
            "Created historical import session",
            extra={
                "session_id": str(session.id),
                "user_id": user_id,
                "tax_years": tax_years,
                "document_types": document_types,
            },
        )

        return session

    def process_upload(
        self, upload_id: UUID, ocr_text: Optional[str] = None, file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a single document upload through extraction and import.

        Routes to appropriate service based on document_type:
        - e1_form -> E1FormImportService
        - bescheid -> BescheidImportService
        - kaufvertrag -> KaufvertragImportService
        - saldenliste -> SaldenlisteImportService

        Updates HistoricalImportUpload with results and handles errors.

        Args:
            upload_id: UUID of the HistoricalImportUpload
            ocr_text: OCR text from document (for PDF documents)
            file_path: File path (for CSV/Excel Saldenliste)

        Returns:
            Dictionary with processing results:
            {
                "upload_id": UUID,
                "status": str,
                "confidence": float,
                "requires_review": bool,
                "transactions_created": int,
                "properties_created": int,
                "properties_linked": int,
                "errors": List[Dict]
            }

        Raises:
            ValueError: If upload not found or invalid document type
        """
        # Get upload record
        upload = (
            self.db.query(HistoricalImportUpload)
            .filter(HistoricalImportUpload.id == upload_id)
            .first()
        )

        if not upload:
            raise ValueError(f"Upload not found: {upload_id}")

        logger.info(
            "Processing upload",
            extra={
                "upload_id": str(upload_id),
                "document_type": upload.document_type.value,
                "tax_year": upload.tax_year,
            },
        )

        try:
            # Update status to processing
            upload.status = ImportStatus.PROCESSING
            self.db.commit()

            # Track processing start time
            import time
            start_time = time.time()

            # Route to appropriate import service
            if upload.document_type == HistoricalDocumentType.E1_FORM:
                result = self._process_e1_form(upload, ocr_text)
            elif upload.document_type == HistoricalDocumentType.BESCHEID:
                result = self._process_bescheid(upload, ocr_text)
            elif upload.document_type == HistoricalDocumentType.KAUFVERTRAG:
                result = self._process_kaufvertrag(upload, ocr_text)
            elif upload.document_type == HistoricalDocumentType.SALDENLISTE:
                result = self._process_saldenliste(upload, file_path)
            else:
                raise ValueError(f"Unsupported document type: {upload.document_type}")

            # Calculate processing time
            extraction_time_ms = int((time.time() - start_time) * 1000)

            # Update upload with results
            self._update_upload_success(upload, result)

            # Log import metrics
            self._log_import_metrics(upload, result, extraction_time_ms)

            # Update session metrics if part of a session
            if upload.session_id:
                self._update_session_metrics(upload.session_id)

            logger.info(
                "Upload processed successfully",
                extra={
                    "upload_id": str(upload_id),
                    "status": upload.status.value,
                    "confidence": float(upload.extraction_confidence or 0),
                    "requires_review": upload.requires_review,
                },
            )

            return {
                "upload_id": upload_id,
                "status": upload.status.value,
                "confidence": float(upload.extraction_confidence or 0),
                "requires_review": upload.requires_review,
                "transactions_created": len(upload.transactions_created),
                "properties_created": len(upload.properties_created),
                "properties_linked": len(upload.properties_linked),
                "errors": upload.errors or [],
            }

        except Exception as e:
            # Handle errors
            error_msg = str(e)
            logger.error(
                "Upload processing failed",
                extra={
                    "upload_id": str(upload_id),
                    "error": error_msg,
                },
                exc_info=True,
            )

            self._update_upload_error(upload, error_msg)

            # Log metrics for failed import (with zero confidence and time)
            try:
                from app.models.historical_import import ImportMetrics
                from decimal import Decimal
                
                metrics = ImportMetrics(
                    upload_id=upload.id,
                    document_type=upload.document_type,
                    extraction_confidence=Decimal("0.0"),
                    fields_extracted=0,
                    fields_total=0,
                    extraction_time_ms=0,
                    field_accuracies={},
                    fields_corrected=0,
                    corrections=[],
                )
                self.db.add(metrics)
                self.db.commit()
            except Exception as metrics_error:
                logger.warning(
                    "Failed to log metrics for failed import",
                    extra={
                        "upload_id": str(upload_id),
                        "error": str(metrics_error),
                    },
                )

            # Update session metrics if part of a session
            if upload.session_id:
                self._update_session_metrics(upload.session_id)

            return {
                "upload_id": upload_id,
                "status": ImportStatus.FAILED.value,
                "confidence": 0.0,
                "requires_review": True,
                "transactions_created": 0,
                "properties_created": 0,
                "properties_linked": 0,
                "errors": upload.errors or [],
            }

    def _capture_user_corrections(
        self,
        upload: HistoricalImportUpload,
        extracted_data: Dict[str, Any],
        edited_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Capture user corrections by comparing extracted data with edited data.

        This method identifies fields that were corrected by the user and creates
        correction records for ML training. It handles nested data structures and
        different field types based on document type.

        Args:
            upload: HistoricalImportUpload record
            extracted_data: Original extracted data from OCR/extraction
            edited_data: User-corrected data from review interface

        Returns:
            List of correction dictionaries with format:
            [
                {
                    "field": "kz_245",
                    "extracted": "50000",
                    "corrected": "51000",
                    "correction_type": "amount_correction"
                }
            ]
        """
        corrections = []

        def normalize_value(value: Any) -> str:
            """Normalize a value to string for comparison"""
            if value is None:
                return ""
            if isinstance(value, (Decimal, float)):
                return str(Decimal(str(value)))
            if isinstance(value, (list, dict)):
                return str(value)
            return str(value)

        def determine_correction_type(field_name: str, extracted_val: Any, corrected_val: Any) -> str:
            """Determine the type of correction based on field name and values"""
            field_lower = field_name.lower()
            
            # Amount corrections
            if any(keyword in field_lower for keyword in ["kz_", "amount", "price", "value", "income", "expense", "steuer", "fee"]):
                return "amount_correction"
            
            # Date corrections
            if any(keyword in field_lower for keyword in ["date", "datum"]):
                return "date_correction"
            
            # Category corrections
            if any(keyword in field_lower for keyword in ["category", "kategorie", "type", "typ"]):
                return "category_correction"
            
            # Address corrections
            if any(keyword in field_lower for keyword in ["address", "adresse", "street", "strasse", "city", "stadt"]):
                return "address_correction"
            
            # Default to field correction
            return "field_correction"

        def compare_fields(extracted: Dict[str, Any], edited: Dict[str, Any], prefix: str = ""):
            """Recursively compare fields between extracted and edited data"""
            # Get all unique keys from both dictionaries
            all_keys = set(extracted.keys()) | set(edited.keys())
            
            for key in all_keys:
                field_name = f"{prefix}{key}" if prefix else key
                extracted_val = extracted.get(key)
                edited_val = edited.get(key)
                
                # Skip if both are None or empty
                if not extracted_val and not edited_val:
                    continue
                
                # Handle nested dictionaries (but not for all_kz_values which should be compared directly)
                if isinstance(edited_val, dict) and isinstance(extracted_val, dict) and key != "all_kz_values":
                    compare_fields(extracted_val, edited_val, f"{field_name}.")
                    continue
                
                # Handle lists (e.g., property_addresses)
                if isinstance(edited_val, list) and isinstance(extracted_val, list):
                    # Compare list lengths and contents
                    if len(edited_val) != len(extracted_val) or edited_val != extracted_val:
                        corrections.append({
                            "field": field_name,
                            "extracted": normalize_value(extracted_val),
                            "corrected": normalize_value(edited_val),
                            "correction_type": determine_correction_type(field_name, extracted_val, edited_val)
                        })
                    continue
                
                # Compare normalized values
                extracted_normalized = normalize_value(extracted_val)
                edited_normalized = normalize_value(edited_val)
                
                if extracted_normalized != edited_normalized:
                    corrections.append({
                        "field": field_name,
                        "extracted": extracted_normalized,
                        "corrected": edited_normalized,
                        "correction_type": determine_correction_type(field_name, extracted_val, edited_val)
                    })

        # Compare the data structures
        compare_fields(extracted_data, edited_data)

        logger.info(
            "Captured user corrections",
            extra={
                "upload_id": str(upload.id),
                "corrections_count": len(corrections),
                "document_type": upload.document_type.value,
            },
        )

        return corrections

    def _capture_user_corrections(
        self,
        upload: HistoricalImportUpload,
        extracted_data: Dict[str, Any],
        edited_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Capture user corrections by comparing extracted data with edited data.

        This method identifies fields that were corrected by the user and creates
        correction records for ML training. It handles nested data structures and
        different field types based on document type.

        Args:
            upload: HistoricalImportUpload record
            extracted_data: Original extracted data from OCR/extraction
            edited_data: User-corrected data from review interface

        Returns:
            List of correction dictionaries with format:
            [
                {
                    "field": "kz_245",
                    "extracted": "50000",
                    "corrected": "51000",
                    "correction_type": "amount_correction"
                }
            ]
        """
        corrections = []

        def normalize_value(value: Any) -> str:
            """Normalize a value to string for comparison"""
            if value is None:
                return ""
            if isinstance(value, (Decimal, float)):
                return str(Decimal(str(value)))
            if isinstance(value, (list, dict)):
                return str(value)
            return str(value)

        def determine_correction_type(field_name: str, extracted_val: Any, corrected_val: Any) -> str:
            """Determine the type of correction based on field name and values"""
            field_lower = field_name.lower()

            # Amount corrections
            if any(keyword in field_lower for keyword in ["kz_", "amount", "price", "value", "income", "expense", "steuer", "fee"]):
                return "amount_correction"

            # Date corrections
            if any(keyword in field_lower for keyword in ["date", "datum"]):
                return "date_correction"

            # Category corrections
            if any(keyword in field_lower for keyword in ["category", "kategorie", "type", "typ"]):
                return "category_correction"

            # Address corrections
            if any(keyword in field_lower for keyword in ["address", "adresse", "street", "strasse", "city", "stadt"]):
                return "address_correction"

            # Default to field correction
            return "field_correction"

        def compare_fields(extracted: Dict[str, Any], edited: Dict[str, Any], prefix: str = ""):
            """Recursively compare fields between extracted and edited data"""
            # Get all unique keys from both dictionaries
            all_keys = set(extracted.keys()) | set(edited.keys())

            for key in all_keys:
                field_name = f"{prefix}{key}" if prefix else key
                extracted_val = extracted.get(key)
                edited_val = edited.get(key)

                # Skip if both are None or empty
                if not extracted_val and not edited_val:
                    continue

                # Handle nested dictionaries (but not for all_kz_values which should be compared directly)
                if isinstance(edited_val, dict) and isinstance(extracted_val, dict) and key != "all_kz_values":
                    compare_fields(extracted_val, edited_val, f"{field_name}.")
                    continue

                # Handle lists (e.g., property_addresses)
                if isinstance(edited_val, list) and isinstance(extracted_val, list):
                    # Compare list lengths and contents
                    if len(edited_val) != len(extracted_val) or edited_val != extracted_val:
                        corrections.append({
                            "field": field_name,
                            "extracted": normalize_value(extracted_val),
                            "corrected": normalize_value(edited_val),
                            "correction_type": determine_correction_type(field_name, extracted_val, edited_val)
                        })
                    continue

                # Compare normalized values
                extracted_normalized = normalize_value(extracted_val)
                edited_normalized = normalize_value(edited_val)

                if extracted_normalized != edited_normalized:
                    corrections.append({
                        "field": field_name,
                        "extracted": extracted_normalized,
                        "corrected": edited_normalized,
                        "correction_type": determine_correction_type(field_name, extracted_val, edited_val)
                    })

        # Compare the data structures
        compare_fields(extracted_data, edited_data)

        logger.info(
            "Captured user corrections",
            extra={
                "upload_id": str(upload.id),
                "corrections_count": len(corrections),
                "document_type": upload.document_type.value,
            },
        )

        return corrections


    def finalize_session(self, session_id: UUID) -> Dict[str, Any]:
        """
        Finalize a session and generate summary report.

        Args:
            session_id: UUID of the HistoricalImportSession

        Returns:
            Dictionary with session summary:
            {
                "session_id": UUID,
                "status": str,
                "total_documents": int,
                "successful_imports": int,
                "failed_imports": int,
                "transactions_created": int,
                "properties_created": int,
                "properties_linked": int,
                "uploads": List[Dict],
                "summary": Dict
            }

        Raises:
            ValueError: If session not found
        """
        session = (
            self.db.query(HistoricalImportSession)
            .filter(HistoricalImportSession.id == session_id)
            .first()
        )

        if not session:
            raise ValueError(f"Session not found: {session_id}")

        logger.info(
            "Finalizing session",
            extra={
                "session_id": str(session_id),
                "total_documents": session.total_documents,
            },
        )

        # Update session status
        if session.failed_imports > 0 and session.successful_imports == 0:
            session.status = ImportSessionStatus.FAILED
        else:
            session.status = ImportSessionStatus.COMPLETED

        session.completed_at = datetime.utcnow()
        self.db.commit()

        # Generate summary
        uploads_summary = []
        for upload in session.uploads:
            uploads_summary.append(
                {
                    "upload_id": str(upload.id),
                    "document_type": upload.document_type.value,
                    "tax_year": upload.tax_year,
                    "status": upload.status.value,
                    "confidence": float(upload.extraction_confidence or 0),
                    "requires_review": upload.requires_review,
                    "transactions_created": len(upload.transactions_created),
                    "properties_created": len(upload.properties_created),
                    "properties_linked": len(upload.properties_linked),
                    "errors": upload.errors or [],
                }
            )

        summary = {
            "session_id": str(session_id),
            "status": session.status.value,
            "tax_years": session.tax_years,
            "total_documents": session.total_documents,
            "successful_imports": session.successful_imports,
            "failed_imports": session.failed_imports,
            "transactions_created": session.transactions_created,
            "properties_created": session.properties_created,
            "properties_linked": session.properties_linked,
            "uploads": uploads_summary,
            "created_at": session.created_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        }

        logger.info(
            "Session finalized",
            extra={
                "session_id": str(session_id),
                "status": session.status.value,
                "successful_imports": session.successful_imports,
                "failed_imports": session.failed_imports,
            },
        )

        return summary
    def review_upload(
        self,
        upload_id: UUID,
        approved: bool,
        edited_data: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        reviewed_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Review and approve or reject an upload.

        This method handles the review workflow:
        - If approved=True: Store edited data, finalize import (create transactions, link properties)
        - If approved=False: Cleanup all associated data, allow re-import

        Args:
            upload_id: UUID of the HistoricalImportUpload
            approved: Whether the upload is approved (True) or rejected (False)
            edited_data: Optional user-corrected extraction data
            notes: Optional review notes
            reviewed_by: Optional user ID of reviewer

        Returns:
            Dictionary with review results:
            {
                "upload_id": UUID,
                "status": str,
                "approved": bool,
                "transactions_created": int,
                "properties_created": int,
                "properties_linked": int,
                "message": str
            }

        Raises:
            ValueError: If upload not found or invalid state
        """
        # Get upload record
        upload = (
            self.db.query(HistoricalImportUpload)
            .filter(HistoricalImportUpload.id == upload_id)
            .first()
        )

        if not upload:
            raise ValueError(f"Upload not found: {upload_id}")

        # Validate upload can be reviewed
        if upload.status not in [
            ImportStatus.EXTRACTED,
            ImportStatus.REVIEW_REQUIRED,
            ImportStatus.REJECTED,
        ]:
            raise ValueError(
                f"Upload cannot be reviewed in status: {upload.status}. "
                f"Must be EXTRACTED, REVIEW_REQUIRED, or REJECTED."
            )

        logger.info(
            "Reviewing upload",
            extra={
                "upload_id": str(upload_id),
                "approved": approved,
                "has_edited_data": edited_data is not None,
            },
        )

        # Store review metadata
        upload.reviewed_at = datetime.utcnow()
        upload.reviewed_by = reviewed_by
        upload.approval_notes = notes

        # Store edited data if provided and capture corrections for ML training
        if edited_data is not None:
            upload.edited_data = edited_data
            
            # Capture user corrections for ML training
            if upload.extracted_data:
                corrections = self._capture_user_corrections(
                    upload, upload.extracted_data, edited_data
                )
                
                # Update ImportMetrics with corrections
                if corrections:
                    from app.models.historical_import import ImportMetrics
                    
                    metrics = (
                        self.db.query(ImportMetrics)
                        .filter(ImportMetrics.upload_id == upload.id)
                        .first()
                    )
                    
                    if metrics:
                        metrics.corrections = corrections
                        metrics.fields_corrected = len(corrections)

                        # Update field-level accuracies based on corrections
                        field_accuracies = dict(metrics.field_accuracies or {})
                        for correction in corrections:
                            field_name = correction["field"]
                            # Mark corrected fields as inaccurate (0.0)
                            if field_name in field_accuracies:
                                field_accuracies[field_name] = 0.0
                        metrics.field_accuracies = field_accuracies

                        self.db.add(metrics)
                        
                        logger.info(
                            "Updated ImportMetrics with user corrections",
                            extra={
                                "upload_id": str(upload.id),
                                "fields_corrected": len(corrections),
                            },
                        )

        if approved:
            # Approval workflow: finalize import
            result = self._finalize_upload(upload)
            upload.status = ImportStatus.APPROVED
            self.db.commit()

            # Update session metrics if part of a session
            if upload.session_id:
                self._update_session_metrics(upload.session_id)

            logger.info(
                "Upload approved and finalized",
                extra={
                    "upload_id": str(upload_id),
                    "transactions_created": result["transactions_created"],
                    "properties_created": result["properties_created"],
                },
            )

            return {
                "upload_id": upload_id,
                "status": ImportStatus.APPROVED.value,
                "approved": True,
                "transactions_created": result["transactions_created"],
                "properties_created": result["properties_created"],
                "properties_linked": result["properties_linked"],
                "message": "Upload approved and finalized successfully",
            }
        else:
            # Rejection workflow: cleanup
            result = self._reject_upload(upload)
            upload.status = ImportStatus.REJECTED
            self.db.commit()

            # Update session metrics if part of a session
            if upload.session_id:
                self._update_session_metrics(upload.session_id)

            logger.info(
                "Upload rejected and cleaned up",
                extra={
                    "upload_id": str(upload_id),
                    "transactions_deleted": result["transactions_deleted"],
                    "properties_unlinked": result["properties_unlinked"],
                },
            )

            return {
                "upload_id": upload_id,
                "status": ImportStatus.REJECTED.value,
                "approved": False,
                "transactions_created": 0,
                "properties_created": 0,
                "properties_linked": 0,
                "message": "Upload rejected and cleaned up successfully",
            }


    def _process_e1_form(
        self, upload: HistoricalImportUpload, ocr_text: Optional[str]
    ) -> Dict[str, Any]:
        """Process E1 form document."""
        if not ocr_text:
            raise ValueError("OCR text is required for E1 form processing")

        result = self.e1_import.import_from_ocr_text(
            text=ocr_text, user_id=upload.user_id, document_id=upload.document_id
        )

        return {
            "confidence": result.get("confidence", 0.0),
            "extracted_data": result.get("e1_data", {}),
            "transactions_created": [t["id"] for t in result.get("transactions", [])],
            "properties_created": [],
            "properties_linked": [],
            "requires_review": result.get("confidence", 0.0) < float(self.CONFIDENCE_THRESHOLD_E1),
        }

    def _process_bescheid(
        self, upload: HistoricalImportUpload, ocr_text: Optional[str]
    ) -> Dict[str, Any]:
        """Process Bescheid document."""
        if not ocr_text:
            raise ValueError("OCR text is required for Bescheid processing")

        result = self.bescheid_import.import_from_ocr_text(
            text=ocr_text, user_id=upload.user_id, document_id=upload.document_id
        )

        # Extract property IDs from linking suggestions
        properties_linked = []
        for suggestion in result.get("property_linking_suggestions", []):
            if suggestion.get("matched_property_id"):
                try:
                    prop_id = UUID(suggestion["matched_property_id"])
                    properties_linked.append(prop_id)
                except (ValueError, TypeError):
                    pass

        return {
            "confidence": result.get("confidence", 0.0),
            "extracted_data": result.get("bescheid_data", {}),
            "transactions_created": [t["id"] for t in result.get("transactions", [])],
            "properties_created": [],
            "properties_linked": properties_linked,
            "requires_review": result.get("confidence", 0.0)
            < float(self.CONFIDENCE_THRESHOLD_BESCHEID),
        }

    def _process_kaufvertrag(
        self, upload: HistoricalImportUpload, ocr_text: Optional[str]
    ) -> Dict[str, Any]:
        """Process Kaufvertrag document."""
        if not ocr_text:
            raise ValueError("OCR text is required for Kaufvertrag processing")

        result = self.kaufvertrag_import.import_from_ocr_text(
            text=ocr_text, user_id=upload.user_id, document_id=upload.document_id
        )

        properties_created = []
        properties_linked = []

        if result.get("property_created"):
            properties_created.append(result["property_id"])
        else:
            properties_linked.append(result["property_id"])

        return {
            "confidence": result.get("confidence", 0.0),
            "extracted_data": result.get("extracted_data", {}),
            "transactions_created": result.get("transactions_created", []),
            "properties_created": properties_created,
            "properties_linked": properties_linked,
            "requires_review": result.get("confidence", 0.0)
            < float(self.CONFIDENCE_THRESHOLD_KAUFVERTRAG),
        }

    def _process_saldenliste(
        self, upload: HistoricalImportUpload, file_path: Optional[str]
    ) -> Dict[str, Any]:
        """Process Saldenliste document."""
        if not file_path:
            raise ValueError("File path is required for Saldenliste processing")

        result = self.saldenliste_import.import_saldenliste(
            file_path=file_path,
            user_id=upload.user_id,
            tax_year=upload.tax_year,
            upload_id=upload.id,
        )

        # Check if review is required due to unmapped accounts
        requires_review = (
            result.get("confidence", 0.0) < float(self.CONFIDENCE_THRESHOLD_SALDENLISTE)
            or result.get("accounts_unmapped", 0) > 0
        )

        return {
            "confidence": result.get("confidence", 0.0),
            "extracted_data": {
                "accounts_imported": result.get("accounts_imported", 0),
                "accounts_unmapped": result.get("accounts_unmapped", 0),
                "unmapped_accounts": result.get("unmapped_accounts", []),
            },
            "transactions_created": result.get("transactions_created", []),
            "properties_created": [],
            "properties_linked": [],
            "requires_review": requires_review,
        }

    def _update_upload_success(
        self, upload: HistoricalImportUpload, result: Dict[str, Any]
    ) -> None:
        """Update upload record with successful processing results."""
        upload.status = (
            ImportStatus.REVIEW_REQUIRED
            if result.get("requires_review", False)
            else ImportStatus.EXTRACTED
        )
        upload.extraction_confidence = Decimal(str(result.get("confidence", 0.0)))
        upload.extracted_data = result.get("extracted_data", {})
        upload.transactions_created = result.get("transactions_created", [])
        upload.properties_created = result.get("properties_created", [])
        upload.properties_linked = result.get("properties_linked", [])
        upload.requires_review = result.get("requires_review", False)

        self.db.commit()

    def _update_upload_error(self, upload: HistoricalImportUpload, error_msg: str) -> None:
        """Update upload record with error information."""
        upload.status = ImportStatus.FAILED
        upload.requires_review = True

        errors = upload.errors or []
        errors.append(
            {
                "type": "processing_error",
                "message": error_msg,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        upload.errors = errors

        self.db.commit()

    def _finalize_upload(self, upload: HistoricalImportUpload) -> Dict[str, Any]:
        """
        Finalize an approved upload by creating transactions and linking properties.

        Uses edited_data if available, otherwise uses extracted_data.
        Marks created transactions as reviewed and locked.

        This method:
        1. Uses edited_data if available, otherwise uses extracted_data
        2. If edited_data is provided, deletes existing transactions and re-creates them
        3. Creates actual transaction records in the database
        4. Links properties to transactions based on property linking suggestions
        5. Marks transactions as reviewed and locked to prevent automatic modifications
        6. Updates user profile with tax information (tax number, family status, etc.)

        Args:
            upload: HistoricalImportUpload to finalize

        Returns:
            Dictionary with finalization results:
            {
                "transactions_created": int,
                "properties_created": int,
                "properties_linked": int
            }
        """
        from app.models.transaction import Transaction
        from app.models.user import User
        from app.core.encryption import get_encryption

        # Use edited data if available, otherwise use extracted data
        data_to_import = upload.edited_data if upload.edited_data else upload.extracted_data

        if not data_to_import:
            raise ValueError("No data available to finalize (neither edited_data nor extracted_data)")

        using_edited_data = upload.edited_data is not None

        logger.info(
            "Finalizing upload",
            extra={
                "upload_id": str(upload.id),
                "document_type": upload.document_type.value,
                "using_edited_data": using_edited_data,
            },
        )

        # If edited data was provided, delete existing transactions and re-create
        if using_edited_data and upload.transactions_created:
            logger.info(
                "Deleting existing transactions for re-import with edited data",
                extra={
                    "upload_id": str(upload.id),
                    "transactions_to_delete": len(upload.transactions_created),
                },
            )
            deleted_count = (
                self.db.query(Transaction)
                .filter(Transaction.id.in_(upload.transactions_created))
                .delete(synchronize_session=False)
            )
            self.db.commit()
            logger.info(
                "Deleted existing transactions",
                extra={"upload_id": str(upload.id), "count": deleted_count},
            )
            # Clear the transaction list
            upload.transactions_created = []

        # Re-import or finalize based on document type
        transactions_created = []
        properties_created = []
        properties_linked = []

        if upload.document_type == HistoricalDocumentType.E1_FORM:
            result = self._finalize_e1_form(upload, data_to_import)
            transactions_created = result["transactions_created"]
            properties_linked = result["properties_linked"]
        elif upload.document_type == HistoricalDocumentType.BESCHEID:
            result = self._finalize_bescheid(upload, data_to_import)
            transactions_created = result["transactions_created"]
            properties_linked = result["properties_linked"]
        elif upload.document_type == HistoricalDocumentType.KAUFVERTRAG:
            result = self._finalize_kaufvertrag(upload, data_to_import)
            transactions_created = result["transactions_created"]
            properties_created = result["properties_created"]
            properties_linked = result["properties_linked"]
        elif upload.document_type == HistoricalDocumentType.SALDENLISTE:
            result = self._finalize_saldenliste(upload, data_to_import)
            transactions_created = result["transactions_created"]
        else:
            raise ValueError(f"Unsupported document type: {upload.document_type}")

        # Mark all created transactions as reviewed and locked
        if transactions_created:
            self.db.query(Transaction).filter(
                Transaction.id.in_(transactions_created)
            ).update(
                {"reviewed": True, "locked": True},
                synchronize_session=False,
            )
            self.db.commit()

        # Update upload record with final transaction/property IDs
        upload.transactions_created = transactions_created
        upload.properties_created = properties_created
        upload.properties_linked = properties_linked
        self.db.commit()

        logger.info(
            "Upload finalized",
            extra={
                "upload_id": str(upload.id),
                "transactions_created": len(transactions_created),
                "properties_created": len(properties_created),
                "properties_linked": len(properties_linked),
            },
        )

        return {
            "transactions_created": len(transactions_created),
            "properties_created": len(properties_created),
            "properties_linked": len(properties_linked),
        }

    def _reject_upload(self, upload: HistoricalImportUpload) -> Dict[str, Any]:
        """
        Reject an upload and cleanup all associated data.

        Deletes:
        - All transactions created during import
        - Property links (not the properties themselves)
        - Depreciation schedules (for Kaufvertrag)

        Args:
            upload: HistoricalImportUpload to reject

        Returns:
            Dictionary with cleanup results:
            {
                "transactions_deleted": int,
                "properties_unlinked": int,
                "depreciation_schedules_deleted": int
            }
        """
        from app.models.transaction import Transaction
        from app.models.property import PropertyDepreciation

        logger.info(
            "Rejecting upload and cleaning up",
            extra={
                "upload_id": str(upload.id),
                "document_type": upload.document_type.value,
                "transactions_to_delete": len(upload.transactions_created),
            },
        )

        transactions_deleted = 0
        properties_unlinked = 0
        depreciation_schedules_deleted = 0

        # Delete transactions
        if upload.transactions_created:
            deleted_count = (
                self.db.query(Transaction)
                .filter(Transaction.id.in_(upload.transactions_created))
                .delete(synchronize_session=False)
            )
            transactions_deleted = deleted_count
            logger.info(
                "Deleted transactions",
                extra={
                    "upload_id": str(upload.id),
                    "count": deleted_count,
                },
            )

        # For Kaufvertrag, delete depreciation schedules
        if upload.document_type == HistoricalDocumentType.KAUFVERTRAG and upload.properties_created:
            for property_id in upload.properties_created:
                deleted_count = (
                    self.db.query(PropertyDepreciation)
                    .filter(PropertyDepreciation.property_id == property_id)
                    .delete(synchronize_session=False)
                )
                depreciation_schedules_deleted += deleted_count

        # Clear upload's transaction and property references
        upload.transactions_created = []
        upload.properties_created = []
        upload.properties_linked = []

        self.db.commit()

        logger.info(
            "Upload rejected and cleaned up",
            extra={
                "upload_id": str(upload.id),
                "transactions_deleted": transactions_deleted,
                "depreciation_schedules_deleted": depreciation_schedules_deleted,
            },
        )

        return {
            "transactions_deleted": transactions_deleted,
            "properties_unlinked": properties_unlinked,
            "depreciation_schedules_deleted": depreciation_schedules_deleted,
        }

    def _update_session_metrics(self, session_id: UUID) -> None:
        """Update session metrics based on current uploads."""
        session = (
            self.db.query(HistoricalImportSession)
            .filter(HistoricalImportSession.id == session_id)
            .first()
        )

        if not session:
            return

        # Count uploads by status
        total_documents = len(session.uploads)
        successful_imports = sum(
            1
            for upload in session.uploads
            if upload.status
            in [ImportStatus.EXTRACTED, ImportStatus.APPROVED, ImportStatus.REVIEW_REQUIRED]
        )
        failed_imports = sum(
            1 for upload in session.uploads if upload.status == ImportStatus.FAILED
        )

        # Sum transactions and properties
        transactions_created = sum(
            len(upload.transactions_created) for upload in session.uploads
        )
        properties_created = sum(len(upload.properties_created) for upload in session.uploads)
        properties_linked = sum(len(upload.properties_linked) for upload in session.uploads)

        # Update session
        session.total_documents = total_documents
        session.successful_imports = successful_imports
        session.failed_imports = failed_imports
        session.transactions_created = transactions_created
        session.properties_created = properties_created
        session.properties_linked = properties_linked

        self.db.commit()

    def _log_import_metrics(
        self,
        upload: HistoricalImportUpload,
        result: Dict[str, Any],
        extraction_time_ms: int,
    ) -> None:
        """
        Log import metrics for quality tracking and ML training.

        Creates an ImportMetrics record with:
        - Extraction confidence score
        - Number of fields extracted vs total expected
        - Processing time in milliseconds
        - Field-level accuracy scores (if available)
        - Error information

        Args:
            upload: HistoricalImportUpload record
            result: Processing result dictionary from import service
            extraction_time_ms: Processing time in milliseconds
        """
        from app.models.historical_import import ImportMetrics
        from decimal import Decimal

        # Calculate fields extracted and total
        extracted_data = result.get("extracted_data", {})
        fields_extracted = 0
        fields_total = 0
        field_accuracies = {}

        # Count fields based on document type
        if upload.document_type == HistoricalDocumentType.E1_FORM:
            # E1 form has KZ values
            all_kz = extracted_data.get("all_kz_values", {})
            fields_extracted = len([v for v in all_kz.values() if v is not None and v != 0])
            # Expected fields for E1 (common KZ codes)
            expected_kz = ["kz_245", "kz_210", "kz_220", "kz_350", "kz_370", "kz_390", "kz_260", "kz_261", "kz_263", "kz_450"]
            fields_total = len(expected_kz)
            
            # Field-level accuracy (all extracted fields assumed accurate initially)
            for kz_code in all_kz.keys():
                field_accuracies[kz_code] = 1.0

        elif upload.document_type == HistoricalDocumentType.BESCHEID:
            # Bescheid has income fields and property addresses
            if extracted_data.get("employment_income"):
                fields_extracted += 1
            if extracted_data.get("rental_income"):
                fields_extracted += 1
            if extracted_data.get("property_addresses"):
                fields_extracted += len(extracted_data["property_addresses"])
            
            fields_total = 5  # employment_income, rental_income, tax_year, steuernummer, property_addresses
            
            # Field-level accuracy
            if extracted_data.get("employment_income"):
                field_accuracies["employment_income"] = 1.0
            if extracted_data.get("rental_income"):
                field_accuracies["rental_income"] = 1.0

        elif upload.document_type == HistoricalDocumentType.KAUFVERTRAG:
            # Kaufvertrag has property details and costs
            if extracted_data.get("purchase_price"):
                fields_extracted += 1
            if extracted_data.get("building_value"):
                fields_extracted += 1
            if extracted_data.get("land_value"):
                fields_extracted += 1
            if extracted_data.get("purchase_date"):
                fields_extracted += 1
            if extracted_data.get("address"):
                fields_extracted += 1
            if extracted_data.get("grunderwerbsteuer"):
                fields_extracted += 1
            if extracted_data.get("notary_fees"):
                fields_extracted += 1
            if extracted_data.get("registry_fees"):
                fields_extracted += 1
            
            fields_total = 8
            
            # Field-level accuracy
            for field in ["purchase_price", "building_value", "land_value", "purchase_date", "address", "grunderwerbsteuer", "notary_fees", "registry_fees"]:
                if extracted_data.get(field):
                    field_accuracies[field] = 1.0

        elif upload.document_type == HistoricalDocumentType.SALDENLISTE:
            # Saldenliste has account balances
            accounts = extracted_data.get("accounts", [])
            fields_extracted = extracted_data.get("accounts_imported", len(accounts))
            fields_total = fields_extracted + extracted_data.get("accounts_unmapped", 0)
            
            # Field-level accuracy based on mapping success
            if fields_total > 0:
                field_accuracies["account_mapping"] = fields_extracted / fields_total

        # Create ImportMetrics record
        metrics = ImportMetrics(
            upload_id=upload.id,
            document_type=upload.document_type,
            extraction_confidence=Decimal(str(result.get("confidence", 0.0))),
            fields_extracted=fields_extracted,
            fields_total=fields_total,
            extraction_time_ms=extraction_time_ms,
            field_accuracies=field_accuracies,
            fields_corrected=0,  # Will be updated when user makes corrections
            corrections=[],  # Will be populated during review
        )

        self.db.add(metrics)
        self.db.commit()

        logger.info(
            "Import metrics logged",
            extra={
                "upload_id": str(upload.id),
                "document_type": upload.document_type.value,
                "confidence": float(metrics.extraction_confidence),
                "fields_extracted": fields_extracted,
                "fields_total": fields_total,
                "extraction_time_ms": extraction_time_ms,
            },
        )

    def _finalize_e1_form(
        self, upload: HistoricalImportUpload, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Finalize E1 form import by creating transactions and updating user profile.

        Args:
            upload: HistoricalImportUpload record
            data: Extracted or edited E1 form data

        Returns:
            Dictionary with transaction and property IDs
        """
        from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
        from app.models.user import User
        from app.core.encryption import get_encryption
        from datetime import date
        from decimal import Decimal

        tax_year = data.get("tax_year", date.today().year - 1)
        ref_date = date(tax_year, 12, 31)
        
        transactions_created = []
        properties_linked = []

        # Helper function to create transaction
        def create_txn(
            txn_type: TransactionType,
            amount: Decimal,
            description: str,
            income_category=None,
            expense_category=None,
            is_deductible=False,
        ):
            txn = Transaction(
                user_id=upload.user_id,
                type=txn_type,
                amount=amount,
                transaction_date=ref_date,
                description=description,
                income_category=income_category,
                expense_category=expense_category,
                document_id=upload.document_id,
                import_source="e1_import",
                is_deductible=is_deductible,
                classification_confidence=Decimal("0.95"),
                needs_review=False,
            )
            self.db.add(txn)
            self.db.flush()
            return txn.id

        # Create transactions from KZ values
        all_kz = data.get("all_kz_values", {})

        # Employment income (KZ 245)
        if "kz_245" in all_kz and all_kz["kz_245"] > 0:
            txn_id = create_txn(
                TransactionType.INCOME,
                Decimal(str(all_kz["kz_245"])),
                f"Einkünfte aus nichtselbständiger Arbeit {tax_year} (KZ 245)",
                income_category=IncomeCategory.EMPLOYMENT,
            )
            transactions_created.append(txn_id)

        # Self-employment income (KZ 210)
        if "kz_210" in all_kz and all_kz["kz_210"] != 0:
            amount = abs(Decimal(str(all_kz["kz_210"])))
            txn_type = TransactionType.INCOME if all_kz["kz_210"] > 0 else TransactionType.EXPENSE
            txn_id = create_txn(
                txn_type,
                amount,
                f"Einkünfte aus selbständiger Arbeit {tax_year} (KZ 210)",
                income_category=IncomeCategory.SELF_EMPLOYMENT if all_kz["kz_210"] > 0 else None,
                expense_category=ExpenseCategory.OTHER if all_kz["kz_210"] < 0 else None,
                is_deductible=all_kz["kz_210"] < 0,
            )
            transactions_created.append(txn_id)

        # Business income (KZ 220)
        if "kz_220" in all_kz and all_kz["kz_220"] != 0:
            amount = abs(Decimal(str(all_kz["kz_220"])))
            txn_type = TransactionType.INCOME if all_kz["kz_220"] > 0 else TransactionType.EXPENSE
            txn_id = create_txn(
                txn_type,
                amount,
                f"Einkünfte aus Gewerbebetrieb {tax_year} (KZ 220)",
                income_category=IncomeCategory.BUSINESS if all_kz["kz_220"] > 0 else None,
                expense_category=ExpenseCategory.OTHER if all_kz["kz_220"] < 0 else None,
                is_deductible=all_kz["kz_220"] < 0,
            )
            transactions_created.append(txn_id)

        # Rental income (KZ 350)
        rental_txn_id = None
        if "kz_350" in all_kz and all_kz["kz_350"] != 0:
            amount = abs(Decimal(str(all_kz["kz_350"])))
            txn_type = TransactionType.INCOME if all_kz["kz_350"] > 0 else TransactionType.EXPENSE
            rental_txn_id = create_txn(
                txn_type,
                amount,
                f"Einkünfte aus Vermietung und Verpachtung {tax_year} (KZ 350)",
                income_category=IncomeCategory.RENTAL if all_kz["kz_350"] > 0 else None,
                expense_category=ExpenseCategory.MAINTENANCE if all_kz["kz_350"] < 0 else None,
                is_deductible=all_kz["kz_350"] < 0,
            )
            transactions_created.append(rental_txn_id)

        # Capital income (KZ 370)
        if "kz_370" in all_kz and all_kz["kz_370"] > 0:
            txn_id = create_txn(
                TransactionType.INCOME,
                Decimal(str(all_kz["kz_370"])),
                f"Einkünfte aus Kapitalvermögen {tax_year} (KZ 370)",
                income_category=IncomeCategory.CAPITAL_GAINS,
            )
            transactions_created.append(txn_id)

        # Other income (KZ 390)
        if "kz_390" in all_kz and all_kz["kz_390"] > 0:
            txn_id = create_txn(
                TransactionType.INCOME,
                Decimal(str(all_kz["kz_390"])),
                f"Sonstige Einkünfte {tax_year} (KZ 390)",
                income_category=IncomeCategory.OTHER_INCOME,
            )
            transactions_created.append(txn_id)

        # Werbungskosten (KZ 260)
        if "kz_260" in all_kz and all_kz["kz_260"] > 0:
            txn_id = create_txn(
                TransactionType.EXPENSE,
                Decimal(str(all_kz["kz_260"])),
                f"Werbungskosten {tax_year} (KZ 260)",
                expense_category=ExpenseCategory.OTHER,
                is_deductible=True,
            )
            transactions_created.append(txn_id)

        # Pendlerpauschale (KZ 261)
        if "kz_261" in all_kz and all_kz["kz_261"] > 0:
            txn_id = create_txn(
                TransactionType.EXPENSE,
                Decimal(str(all_kz["kz_261"])),
                f"Pendlerpauschale {tax_year} (KZ 261)",
                expense_category=ExpenseCategory.COMMUTING,
                is_deductible=True,
            )
            transactions_created.append(txn_id)

        # Telearbeitspauschale (KZ 263)
        if "kz_263" in all_kz and all_kz["kz_263"] > 0:
            txn_id = create_txn(
                TransactionType.EXPENSE,
                Decimal(str(all_kz["kz_263"])),
                f"Telearbeitspauschale {tax_year} (KZ 263)",
                expense_category=ExpenseCategory.HOME_OFFICE,
                is_deductible=True,
            )
            transactions_created.append(txn_id)

        # Sonderausgaben (KZ 450)
        if "kz_450" in all_kz and all_kz["kz_450"] > 0:
            txn_id = create_txn(
                TransactionType.EXPENSE,
                Decimal(str(all_kz["kz_450"])),
                f"Sonderausgaben {tax_year} (KZ 450)",
                expense_category=ExpenseCategory.OTHER,
                is_deductible=True,
            )
            transactions_created.append(txn_id)

        self.db.commit()

        # Update user profile with tax information
        user = self.db.query(User).filter(User.id == upload.user_id).first()
        if user:
            encryption = get_encryption()
            
            # Update tax number if provided and not already set
            if data.get("steuernummer") and not user.tax_number:
                user.tax_number = encryption.encrypt_field(data["steuernummer"])
            
            # Update family info if provided
            if data.get("family_status"):
                family_info = user.family_info or {}
                if "num_children" in data:
                    family_info["num_children"] = data["num_children"]
                if "is_single_parent" in data:
                    family_info["is_single_parent"] = data["is_single_parent"]
                user.family_info = family_info
            
            self.db.commit()

        # Link properties if rental income exists and suggestions are provided
        if rental_txn_id and data.get("property_linking_suggestions"):
            for suggestion in data["property_linking_suggestions"]:
                if suggestion.get("action") == "auto_link" and suggestion.get("matched_property_id"):
                    try:
                        from uuid import UUID
                        property_id = UUID(suggestion["matched_property_id"])
                        
                        # Update transaction with property_id
                        self.db.query(Transaction).filter(
                            Transaction.id == rental_txn_id
                        ).update({"property_id": property_id})
                        self.db.commit()
                        
                        properties_linked.append(property_id)
                        logger.info(
                            "Linked rental transaction to property",
                            extra={
                                "transaction_id": rental_txn_id,
                                "property_id": str(property_id),
                            },
                        )
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            "Failed to link property",
                            extra={
                                "transaction_id": rental_txn_id,
                                "error": str(e),
                            },
                        )

        return {
            "transactions_created": transactions_created,
            "properties_created": [],
            "properties_linked": properties_linked,
        }

    def _finalize_bescheid(
        self, upload: HistoricalImportUpload, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Finalize Bescheid import by creating transactions and linking properties.

        Args:
            upload: HistoricalImportUpload record
            data: Extracted or edited Bescheid data

        Returns:
            Dictionary with transaction and property IDs
        """
        from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
        from datetime import date
        from decimal import Decimal

        tax_year = data.get("tax_year", date.today().year - 1)
        ref_date = date(tax_year, 12, 31)
        
        transactions_created = []
        properties_linked = []

        # Helper function to create transaction
        def create_txn(
            txn_type: TransactionType,
            amount: Decimal,
            description: str,
            income_category=None,
            expense_category=None,
        ):
            txn = Transaction(
                user_id=upload.user_id,
                type=txn_type,
                amount=amount,
                transaction_date=ref_date,
                description=description,
                income_category=income_category,
                expense_category=expense_category,
                document_id=upload.document_id,
                import_source="bescheid_import",
                classification_confidence=Decimal("0.95"),
                needs_review=False,
            )
            self.db.add(txn)
            self.db.flush()
            return txn.id

        # Create transactions from Bescheid data
        if data.get("employment_income") and data["employment_income"] > 0:
            txn_id = create_txn(
                TransactionType.INCOME,
                Decimal(str(data["employment_income"])),
                f"Einkünfte aus nichtselbständiger Arbeit {tax_year} (Bescheid)",
                income_category=IncomeCategory.EMPLOYMENT,
            )
            transactions_created.append(txn_id)

        if data.get("rental_income") and data["rental_income"] != 0:
            amount = abs(Decimal(str(data["rental_income"])))
            txn_type = TransactionType.INCOME if data["rental_income"] > 0 else TransactionType.EXPENSE
            txn_id = create_txn(
                txn_type,
                amount,
                f"Einkünfte aus Vermietung und Verpachtung {tax_year} (Bescheid)",
                income_category=IncomeCategory.RENTAL if data["rental_income"] > 0 else None,
                expense_category=ExpenseCategory.MAINTENANCE if data["rental_income"] < 0 else None,
            )
            transactions_created.append(txn_id)

        self.db.commit()

        # Link properties based on suggestions
        if data.get("property_linking_suggestions"):
            for suggestion in data["property_linking_suggestions"]:
                if suggestion.get("action") == "auto_link" and suggestion.get("matched_property_id"):
                    try:
                        from uuid import UUID
                        property_id = UUID(suggestion["matched_property_id"])
                        properties_linked.append(property_id)
                    except (ValueError, TypeError):
                        pass

        return {
            "transactions_created": transactions_created,
            "properties_created": [],
            "properties_linked": properties_linked,
        }

    def _finalize_kaufvertrag(
        self, upload: HistoricalImportUpload, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Finalize Kaufvertrag import by creating/updating property and transactions.

        Args:
            upload: HistoricalImportUpload record
            data: Extracted or edited Kaufvertrag data

        Returns:
            Dictionary with transaction and property IDs
        """
        from app.models.transaction import Transaction, TransactionType, ExpenseCategory
        from app.models.property import Property
        from datetime import date
        from decimal import Decimal
        from uuid import UUID

        transactions_created = []
        properties_created = []
        properties_linked = []

        # Check if property was already created
        property_id = None
        if data.get("property_id"):
            try:
                property_id = UUID(data["property_id"])
                properties_linked.append(property_id)
            except (ValueError, TypeError):
                pass

        if not property_id and data.get("property_created"):
            # Property needs to be created - this should have been done during initial processing
            # For finalization, we just record the property_id
            if data.get("property_id"):
                try:
                    property_id = UUID(data["property_id"])
                    properties_created.append(property_id)
                except (ValueError, TypeError):
                    pass

        # Create purchase cost transactions
        purchase_date = date.fromisoformat(data["purchase_date"]) if isinstance(data.get("purchase_date"), str) else data.get("purchase_date")
        
        if data.get("grunderwerbsteuer") and data["grunderwerbsteuer"] > 0:
            txn = Transaction(
                user_id=upload.user_id,
                type=TransactionType.EXPENSE,
                amount=Decimal(str(data["grunderwerbsteuer"])),
                transaction_date=purchase_date,
                description=f"Grunderwerbsteuer",
                expense_category=ExpenseCategory.PROPERTY_TAX,
                document_id=upload.document_id,
                import_source="kaufvertrag_import",
                property_id=property_id,
                classification_confidence=Decimal("0.95"),
                needs_review=False,
            )
            self.db.add(txn)
            self.db.flush()
            transactions_created.append(txn.id)

        if data.get("notary_fees") and data["notary_fees"] > 0:
            txn = Transaction(
                user_id=upload.user_id,
                type=TransactionType.EXPENSE,
                amount=Decimal(str(data["notary_fees"])),
                transaction_date=purchase_date,
                description=f"Notarkosten",
                expense_category=ExpenseCategory.PROFESSIONAL_SERVICES,
                document_id=upload.document_id,
                import_source="kaufvertrag_import",
                property_id=property_id,
                classification_confidence=Decimal("0.95"),
                needs_review=False,
            )
            self.db.add(txn)
            self.db.flush()
            transactions_created.append(txn.id)

        if data.get("registry_fees") and data["registry_fees"] > 0:
            txn = Transaction(
                user_id=upload.user_id,
                type=TransactionType.EXPENSE,
                amount=Decimal(str(data["registry_fees"])),
                transaction_date=purchase_date,
                description=f"Eintragungsgebühr",
                expense_category=ExpenseCategory.PROFESSIONAL_SERVICES,
                document_id=upload.document_id,
                import_source="kaufvertrag_import",
                property_id=property_id,
                classification_confidence=Decimal("0.95"),
                needs_review=False,
            )
            self.db.add(txn)
            self.db.flush()
            transactions_created.append(txn.id)

        self.db.commit()

        return {
            "transactions_created": transactions_created,
            "properties_created": properties_created,
            "properties_linked": properties_linked,
        }

    def _finalize_saldenliste(
        self, upload: HistoricalImportUpload, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Finalize Saldenliste import by creating opening balance transactions.

        Args:
            upload: HistoricalImportUpload record
            data: Extracted or edited Saldenliste data

        Returns:
            Dictionary with transaction IDs
        """
        from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
        from datetime import date
        from decimal import Decimal

        tax_year = data.get("tax_year", date.today().year - 1)
        ref_date = date(tax_year, 1, 1)  # Opening balance at start of year
        
        transactions_created = []

        # Create opening balance transactions for each account
        for account in data.get("accounts", []):
            if account.get("balance") and account["balance"] != 0:
                amount = abs(Decimal(str(account["balance"])))
                txn_type = TransactionType.INCOME if account["balance"] > 0 else TransactionType.EXPENSE
                
                txn = Transaction(
                    user_id=upload.user_id,
                    type=txn_type,
                    amount=amount,
                    transaction_date=ref_date,
                    description=f"Eröffnungsbilanz {tax_year}: {account.get('account_name', account.get('account_number'))}",
                    income_category=IncomeCategory.OTHER_INCOME if account["balance"] > 0 else None,
                    expense_category=ExpenseCategory.OTHER if account["balance"] < 0 else None,
                    document_id=upload.document_id,
                    import_source="saldenliste_import",
                    classification_confidence=Decimal("0.90"),
                    needs_review=False,
                )
                self.db.add(txn)
                self.db.flush()
                transactions_created.append(txn.id)

        self.db.commit()

        return {
            "transactions_created": transactions_created,
            "properties_created": [],
            "properties_linked": [],
        }
