"""Data reconciliation service for detecting and resolving conflicts between imported documents"""
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.historical_import import (
    HistoricalImportUpload,
    ImportConflict,
    HistoricalDocumentType,
)


class DataReconciliationService:
    """Detect and reconcile conflicts between imported documents."""

    def __init__(self, db: Session):
        self.db = db
        # Threshold for detecting conflicts (1% difference)
        self.conflict_threshold = Decimal("0.01")

    def detect_conflicts(self, session_id: str) -> List[ImportConflict]:
        """
        Detect conflicts between documents in a session.

        Compares overlapping data fields from documents in the same tax year
        and flags conflicts when values differ by more than the threshold.

        Args:
            session_id: UUID of the import session

        Returns:
            List of detected ImportConflict records
        """
        conflicts = []

        # Get all uploads in the session
        uploads = (
            self.db.query(HistoricalImportUpload)
            .filter(HistoricalImportUpload.session_id == session_id)
            .all()
        )

        # Group uploads by tax year for comparison
        uploads_by_year: Dict[int, List[HistoricalImportUpload]] = {}
        for upload in uploads:
            if upload.tax_year not in uploads_by_year:
                uploads_by_year[upload.tax_year] = []
            uploads_by_year[upload.tax_year].append(upload)

        # Compare documents within each tax year
        for tax_year, year_uploads in uploads_by_year.items():
            # Compare E1 forms with Bescheid documents
            e1_uploads = [
                u for u in year_uploads if u.document_type == HistoricalDocumentType.E1_FORM
            ]
            bescheid_uploads = [
                u
                for u in year_uploads
                if u.document_type == HistoricalDocumentType.BESCHEID
            ]

            for e1_upload in e1_uploads:
                for bescheid_upload in bescheid_uploads:
                    detected = self._compare_e1_bescheid(
                        e1_upload, bescheid_upload, session_id
                    )
                    conflicts.extend(detected)

        return conflicts

    def _compare_e1_bescheid(
        self,
        e1_upload: HistoricalImportUpload,
        bescheid_upload: HistoricalImportUpload,
        session_id: str,
    ) -> List[ImportConflict]:
        """
        Compare E1 form data with Bescheid data for conflicts.

        Checks overlapping fields like employment income (KZ 245 vs employment_income),
        rental income (KZ 350 vs rental_income), etc.

        Args:
            e1_upload: E1 form upload
            bescheid_upload: Bescheid upload
            session_id: Session ID for conflict records

        Returns:
            List of detected conflicts
        """
        conflicts = []

        if not e1_upload.extracted_data or not bescheid_upload.extracted_data:
            return conflicts

        e1_data = e1_upload.extracted_data
        bescheid_data = bescheid_upload.extracted_data

        # Define field mappings between E1 and Bescheid
        field_mappings = [
            ("kz_245", "employment_income", "Employment Income"),
            ("kz_350", "rental_income", "Rental Income"),
            ("kz_730", "special_expenses", "Special Expenses"),
        ]

        for e1_field, bescheid_field, field_label in field_mappings:
            e1_value = e1_data.get(e1_field)
            bescheid_value = bescheid_data.get(bescheid_field)

            if e1_value is not None and bescheid_value is not None:
                conflict = self._check_amount_conflict(
                    e1_upload.id,
                    bescheid_upload.id,
                    session_id,
                    field_label,
                    e1_value,
                    bescheid_value,
                    e1_upload.extraction_confidence or 0,
                    bescheid_upload.extraction_confidence or 0,
                )
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _check_amount_conflict(
        self,
        upload_id_1: str,
        upload_id_2: str,
        session_id: str,
        field_name: str,
        value_1: Any,
        value_2: Any,
        confidence_1: float,
        confidence_2: float,
    ) -> Optional[ImportConflict]:
        """
        Check if two amounts conflict (differ by more than threshold).

        Args:
            upload_id_1: First upload ID
            upload_id_2: Second upload ID
            session_id: Session ID
            field_name: Name of the field being compared
            value_1: Value from first document
            value_2: Value from second document
            confidence_1: Extraction confidence for first document
            confidence_2: Extraction confidence for second document

        Returns:
            ImportConflict if conflict detected, None otherwise
        """
        try:
            amount_1 = Decimal(str(value_1))
            amount_2 = Decimal(str(value_2))
        except (ValueError, TypeError):
            # Cannot compare non-numeric values
            return None

        # Calculate percentage difference
        if amount_1 == 0 and amount_2 == 0:
            return None

        max_amount = max(abs(amount_1), abs(amount_2))
        if max_amount == 0:
            return None

        difference = abs(amount_1 - amount_2)
        percentage_diff = difference / max_amount

        # Check if difference exceeds threshold (1%)
        if percentage_diff > self.conflict_threshold:
            # Check if conflict already exists
            existing = (
                self.db.query(ImportConflict)
                .filter(
                    and_(
                        ImportConflict.session_id == session_id,
                        ImportConflict.upload_id_1 == upload_id_1,
                        ImportConflict.upload_id_2 == upload_id_2,
                        ImportConflict.field_name == field_name,
                    )
                )
                .first()
            )

            if existing:
                return None

            # Create new conflict record
            conflict = ImportConflict(
                session_id=session_id,
                upload_id_1=upload_id_1,
                upload_id_2=upload_id_2,
                conflict_type="conflicting_amount",
                field_name=field_name,
                value_1=str(amount_1),
                value_2=str(amount_2),
                resolution=self._suggest_resolution_internal(
                    amount_1, amount_2, confidence_1, confidence_2
                ),
            )

            self.db.add(conflict)
            self.db.commit()
            self.db.refresh(conflict)

            return conflict

        return None

    def reconcile_income_amounts(
        self, e1_amount: Decimal, bescheid_amount: Decimal, category: str
    ) -> Dict[str, Any]:
        """
        Reconcile conflicting income amounts from E1 and Bescheid.

        Args:
            e1_amount: Amount from E1 form
            bescheid_amount: Amount from Bescheid
            category: Income category (e.g., "employment", "rental")

        Returns:
            Dictionary with reconciliation result:
            - recommended_amount: The amount to use
            - source: Which document to trust ("e1" or "bescheid")
            - difference: Absolute difference between amounts
            - percentage_diff: Percentage difference
            - requires_review: Whether manual review is needed
        """
        difference = abs(e1_amount - bescheid_amount)
        max_amount = max(abs(e1_amount), abs(bescheid_amount))

        if max_amount == 0:
            return {
                "recommended_amount": Decimal("0"),
                "source": "both",
                "difference": Decimal("0"),
                "percentage_diff": Decimal("0"),
                "requires_review": False,
            }

        percentage_diff = difference / max_amount

        # Bescheid is generally more authoritative (official tax assessment)
        # Use Bescheid amount unless difference is very small
        if percentage_diff <= self.conflict_threshold:
            # Difference is within threshold, use Bescheid
            return {
                "recommended_amount": bescheid_amount,
                "source": "bescheid",
                "difference": difference,
                "percentage_diff": percentage_diff,
                "requires_review": False,
            }
        else:
            # Significant difference, require manual review
            # But suggest Bescheid as it's the official assessment
            return {
                "recommended_amount": bescheid_amount,
                "source": "bescheid",
                "difference": difference,
                "percentage_diff": percentage_diff,
                "requires_review": True,
            }

    def suggest_resolution(self, conflict: ImportConflict) -> str:
        """
        Suggest automatic resolution strategy for a conflict.

        Resolution strategies:
        - "keep_first": Use value from first document (higher confidence)
        - "keep_second": Use value from second document (higher confidence)
        - "manual_merge": Requires manual review (similar confidence)
        - "ignore": Difference is negligible

        Args:
            conflict: ImportConflict record

        Returns:
            Suggested resolution strategy
        """
        # Get the uploads to check confidence scores
        upload_1 = (
            self.db.query(HistoricalImportUpload)
            .filter(HistoricalImportUpload.id == conflict.upload_id_1)
            .first()
        )
        upload_2 = (
            self.db.query(HistoricalImportUpload)
            .filter(HistoricalImportUpload.id == conflict.upload_id_2)
            .first()
        )

        if not upload_1 or not upload_2:
            return "manual_merge"

        confidence_1 = float(upload_1.extraction_confidence or 0)
        confidence_2 = float(upload_2.extraction_confidence or 0)

        # Bescheid is generally more authoritative
        if upload_2.document_type == HistoricalDocumentType.BESCHEID:
            return "keep_second"
        elif upload_1.document_type == HistoricalDocumentType.BESCHEID:
            return "keep_first"

        # Use confidence scores
        confidence_diff = abs(confidence_1 - confidence_2)

        if confidence_diff < 0.1:
            # Similar confidence, require manual review
            return "manual_merge"
        elif confidence_1 > confidence_2:
            return "keep_first"
        else:
            return "keep_second"

    def _suggest_resolution_internal(
        self, amount_1: Decimal, amount_2: Decimal, confidence_1: float, confidence_2: float
    ) -> str:
        """
        Internal method to suggest resolution based on amounts and confidence.

        Args:
            amount_1: First amount
            amount_2: Second amount
            confidence_1: Confidence for first amount
            confidence_2: Confidence for second amount

        Returns:
            Suggested resolution strategy
        """
        confidence_diff = abs(confidence_1 - confidence_2)

        if confidence_diff < 0.1:
            return "manual_merge"
        elif confidence_1 > confidence_2:
            return "keep_first"
        else:
            return "keep_second"
