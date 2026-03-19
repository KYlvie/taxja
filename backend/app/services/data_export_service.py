"""Data export service for GDPR data portability (Article 20).

Exports all user data into an AES-256 encrypted ZIP package, uploads it to
MinIO, and returns a 48-hour pre-signed download URL.
"""
import csv
import io
import json
import logging
import tempfile
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Optional

import pyzipper
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.classification_correction import ClassificationCorrection
from app.models.document import Document
from app.models.loss_carryforward import LossCarryforward
from app.models.property import Property
from app.models.property_loan import PropertyLoan
from app.models.tax_report import TaxReport
from app.models.transaction import Transaction
from app.models.user import User
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

# 48 hours in seconds
EXPORT_URL_EXPIRY_SECONDS = 48 * 60 * 60

# MinIO bucket path prefix for data exports
EXPORT_BUCKET_PREFIX = "data-exports"


# Data dictionary descriptions for exported JSON fields
DATA_DICTIONARY = {
    "user": {
        "id": "Unique user identifier (integer)",
        "email": "User email address (string)",
        "name": "User display name (string)",
        "user_type": "User type: employee, self_employed, landlord, mixed, gmbh (string)",
        "tax_number": "Austrian tax number / Steuernummer (string, encrypted at rest)",
        "vat_number": "VAT identification number / UID (string, encrypted at rest)",
        "address": "User address (string, encrypted at rest)",
        "language": "Preferred language: de, en, zh (string)",
        "family_info": "Family information JSON (object)",
        "commuting_info": "Commuting information JSON (object)",
        "home_office_eligible": "Home office eligibility flag (boolean)",
        "created_at": "Account creation timestamp (ISO 8601)",
    },
    "transactions": {
        "id": "Unique transaction identifier (integer)",
        "type": "Transaction type: income or expense (string)",
        "amount": "Transaction amount in EUR (decimal)",
        "transaction_date": "Date of the transaction (ISO 8601 date)",
        "description": "Transaction description (string)",
        "income_category": "Income category if type=income (string, nullable)",
        "expense_category": "Expense category if type=expense (string, nullable)",
        "is_deductible": "Whether the expense is tax-deductible (boolean)",
        "deduction_reason": "Reason for deductibility (string, nullable)",
        "vat_rate": "Applied VAT rate as decimal, e.g. 0.20 for 20% (decimal, nullable)",
        "vat_amount": "VAT amount in EUR (decimal, nullable)",
        "classification_confidence": "ML classification confidence 0.0-1.0 (decimal, nullable)",
        "import_source": "How the transaction was created: csv, psd2, manual, ocr (string, nullable)",
        "created_at": "Record creation timestamp (ISO 8601)",
    },
    "tax_reports": {
        "id": "Unique tax report identifier (integer)",
        "tax_year": "Tax year the report covers (integer)",
        "income_summary": "Breakdown of income by category (JSON object)",
        "expense_summary": "Breakdown of expenses by category (JSON object)",
        "tax_calculation": "Detailed tax calculation with brackets (JSON object)",
        "deductions": "Applied deductions breakdown (JSON object)",
        "net_income": "Net income after all taxes and deductions in EUR (decimal)",
        "generated_at": "Report generation timestamp (ISO 8601)",
    },
    "classification_corrections": {
        "id": "Unique correction identifier (integer)",
        "transaction_id": "Related transaction identifier (integer)",
        "original_category": "Category before correction (string)",
        "original_confidence": "ML confidence before correction (string, nullable)",
        "correct_category": "User-corrected category (string)",
        "created_at": "Correction timestamp (ISO 8601)",
    },
    "loss_carryforwards": {
        "id": "Unique loss carryforward identifier (integer)",
        "loss_year": "Year the loss occurred (integer)",
        "loss_amount": "Original loss amount in EUR (decimal)",
        "used_amount": "Amount already offset in subsequent years in EUR (decimal)",
        "remaining_amount": "Remaining loss available for future offset in EUR (decimal)",
        "created_at": "Record creation timestamp (ISO 8601)",
    },
    "properties": {
        "id": "Unique property identifier (UUID)",
        "property_type": "Property type: rental, owner_occupied, mixed_use (string)",
        "address": "Property address (string, decrypted for export)",
        "street": "Street name (string, decrypted for export)",
        "city": "City name (string, decrypted for export)",
        "postal_code": "Postal code (string)",
        "purchase_date": "Property purchase date (ISO 8601 date)",
        "purchase_price": "Purchase price in EUR (decimal)",
        "building_value": "Building value portion in EUR (decimal)",
        "land_value": "Land value portion in EUR (decimal, nullable)",
        "construction_year": "Year of construction (integer, nullable)",
        "depreciation_rate": "Annual depreciation rate as decimal (decimal)",
        "status": "Property status: active, sold, archived (string)",
        "created_at": "Record creation timestamp (ISO 8601)",
    },
    "property_loans": {
        "id": "Unique loan identifier (integer)",
        "property_id": "Related property identifier (UUID)",
        "loan_amount": "Original loan amount in EUR (decimal)",
        "interest_rate": "Annual interest rate as decimal (decimal)",
        "start_date": "Loan start date (ISO 8601 date)",
        "end_date": "Loan end date (ISO 8601 date, nullable)",
        "monthly_payment": "Monthly payment amount in EUR (decimal)",
        "lender_name": "Name of the lending institution (string)",
        "loan_type": "Loan type: fixed_rate, variable_rate, annuity (string, nullable)",
        "created_at": "Record creation timestamp (ISO 8601)",
    },
}


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for types not handled by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class DataExportService:
    """Service for exporting user data as an AES-256 encrypted ZIP package."""

    @staticmethod
    def export_user_data(
        user_id: int,
        encryption_password: str,
        db: Session,
    ) -> str:
        """Export all user data into an encrypted ZIP and return a pre-signed URL.

        Steps:
        1. Query all user data (transactions, documents, tax reports, etc.)
        2. Export transactions as CSV
        3. Export structured data as JSON with data dictionary descriptions
        4. Include document files in original format
        5. Package everything into an AES-256 encrypted ZIP via pyzipper
        6. Upload to MinIO data-exports/ bucket
        7. Return a 48-hour pre-signed download URL

        Args:
            user_id: The user whose data to export.
            encryption_password: Password for AES-256 ZIP encryption.
            db: SQLAlchemy database session.

        Returns:
            Pre-signed download URL valid for 48 hours.

        Raises:
            ValueError: If user is not found.
            RuntimeError: If upload to MinIO fails.
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        logger.info("Starting data export for user %s", user_id)

        storage = StorageService()

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=True) as tmp:
            tmp_path = tmp.name

        # Build the encrypted ZIP in memory then write to temp file
        with pyzipper.AESZipFile(
            tmp_path,
            "w",
            compression=pyzipper.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES,
        ) as zf:
            zf.setpassword(encryption_password.encode("utf-8"))

            # --- User info JSON ---
            user_data = _build_user_info(user)
            zf.writestr(
                "user_info.json",
                json.dumps(
                    {"data_dictionary": DATA_DICTIONARY["user"], "data": user_data},
                    default=_json_serializer,
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            # --- Transactions CSV ---
            transactions = (
                db.query(Transaction)
                .filter(Transaction.user_id == user_id)
                .order_by(Transaction.transaction_date)
                .all()
            )
            csv_bytes = _build_transactions_csv(transactions)
            zf.writestr("transactions.csv", csv_bytes)

            # --- Tax reports JSON ---
            tax_reports = (
                db.query(TaxReport)
                .filter(TaxReport.user_id == user_id)
                .order_by(TaxReport.tax_year)
                .all()
            )
            reports_data = [_serialize_tax_report(r) for r in tax_reports]
            zf.writestr(
                "tax_reports.json",
                json.dumps(
                    {
                        "data_dictionary": DATA_DICTIONARY["tax_reports"],
                        "data": reports_data,
                    },
                    default=_json_serializer,
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            # --- Classification corrections JSON ---
            corrections = (
                db.query(ClassificationCorrection)
                .filter(ClassificationCorrection.user_id == user_id)
                .order_by(ClassificationCorrection.created_at)
                .all()
            )
            corrections_data = [_serialize_correction(c) for c in corrections]
            zf.writestr(
                "classification_corrections.json",
                json.dumps(
                    {
                        "data_dictionary": DATA_DICTIONARY["classification_corrections"],
                        "data": corrections_data,
                    },
                    default=_json_serializer,
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            # --- Loss carryforwards JSON ---
            loss_cfs = (
                db.query(LossCarryforward)
                .filter(LossCarryforward.user_id == user_id)
                .order_by(LossCarryforward.loss_year)
                .all()
            )
            loss_data = [_serialize_loss_carryforward(lc) for lc in loss_cfs]
            zf.writestr(
                "loss_carryforwards.json",
                json.dumps(
                    {
                        "data_dictionary": DATA_DICTIONARY["loss_carryforwards"],
                        "data": loss_data,
                    },
                    default=_json_serializer,
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            # --- Properties JSON ---
            properties = (
                db.query(Property)
                .filter(Property.user_id == user_id)
                .all()
            )
            props_data = [_serialize_property(p) for p in properties]
            zf.writestr(
                "properties.json",
                json.dumps(
                    {
                        "data_dictionary": DATA_DICTIONARY["properties"],
                        "data": props_data,
                    },
                    default=_json_serializer,
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            # --- Property loans JSON ---
            loans = (
                db.query(PropertyLoan)
                .filter(PropertyLoan.user_id == user_id)
                .order_by(PropertyLoan.start_date)
                .all()
            )
            loans_data = [_serialize_property_loan(loan) for loan in loans]
            zf.writestr(
                "property_loans.json",
                json.dumps(
                    {
                        "data_dictionary": DATA_DICTIONARY["property_loans"],
                        "data": loans_data,
                    },
                    default=_json_serializer,
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            # --- Document files (original format) ---
            documents = (
                db.query(Document)
                .filter(Document.user_id == user_id)
                .all()
            )
            for doc in documents:
                if not doc.file_path:
                    continue
                try:
                    file_bytes = storage.download_file(doc.file_path)
                    if file_bytes:
                        safe_name = doc.file_name or f"document_{doc.id}"
                        zf.writestr(f"documents/{safe_name}", file_bytes)
                except Exception:
                    logger.warning(
                        "Could not download document %s for export", doc.id
                    )

        # Read the finished ZIP file
        with open(tmp_path, "rb") as f:
            zip_bytes = f.read()

        # Clean up temp file
        import os

        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        # Upload to MinIO
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        minio_key = f"{EXPORT_BUCKET_PREFIX}/user_{user_id}_{timestamp}.zip"

        success = storage.upload_file(
            zip_bytes, minio_key, content_type="application/zip"
        )
        if not success:
            raise RuntimeError("Failed to upload data export to storage")

        # Generate 48h pre-signed download URL
        download_url = storage.get_file_url(minio_key, expiration=EXPORT_URL_EXPIRY_SECONDS)
        if not download_url:
            raise RuntimeError("Failed to generate download URL for data export")

        logger.info(
            "Data export completed for user %s: %s (%d bytes)",
            user_id,
            minio_key,
            len(zip_bytes),
        )

        return download_url


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _build_user_info(user: User) -> dict:
    """Serialize user profile data for export."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "user_type": user.user_type.value if user.user_type else None,
        "tax_number": user.tax_number,
        "vat_number": user.vat_number,
        "address": user.address,
        "language": user.language,
        "family_info": user.family_info,
        "commuting_info": user.commuting_info,
        "home_office_eligible": user.home_office_eligible,
        "created_at": user.created_at,
    }


def _build_transactions_csv(transactions: list) -> bytes:
    """Build a CSV file from a list of Transaction model instances."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "id",
        "type",
        "amount",
        "transaction_date",
        "description",
        "income_category",
        "expense_category",
        "is_deductible",
        "deduction_reason",
        "vat_rate",
        "vat_amount",
        "classification_confidence",
        "import_source",
        "created_at",
    ])

    for t in transactions:
        writer.writerow([
            t.id,
            t.type.value if t.type else "",
            float(t.amount) if t.amount is not None else "",
            t.transaction_date.isoformat() if t.transaction_date else "",
            t.description or "",
            t.income_category.value if t.income_category else "",
            t.expense_category.value if t.expense_category else "",
            t.is_deductible,
            t.deduction_reason or "",
            float(t.vat_rate) if t.vat_rate is not None else "",
            float(t.vat_amount) if t.vat_amount is not None else "",
            float(t.classification_confidence) if t.classification_confidence is not None else "",
            t.import_source or "",
            t.created_at.isoformat() if t.created_at else "",
        ])

    return output.getvalue().encode("utf-8")


def _serialize_tax_report(report: TaxReport) -> dict:
    """Serialize a TaxReport model instance."""
    return {
        "id": report.id,
        "tax_year": report.tax_year,
        "income_summary": report.income_summary,
        "expense_summary": report.expense_summary,
        "tax_calculation": report.tax_calculation,
        "deductions": report.deductions,
        "net_income": report.net_income,
        "generated_at": report.generated_at,
    }


def _serialize_correction(correction: ClassificationCorrection) -> dict:
    """Serialize a ClassificationCorrection model instance."""
    return {
        "id": correction.id,
        "transaction_id": correction.transaction_id,
        "original_category": correction.original_category,
        "original_confidence": correction.original_confidence,
        "correct_category": correction.correct_category,
        "created_at": correction.created_at,
    }


def _serialize_loss_carryforward(lc: LossCarryforward) -> dict:
    """Serialize a LossCarryforward model instance."""
    return {
        "id": lc.id,
        "loss_year": lc.loss_year,
        "loss_amount": lc.loss_amount,
        "used_amount": lc.used_amount,
        "remaining_amount": lc.remaining_amount,
        "created_at": lc.created_at,
    }


def _serialize_property(prop: Property) -> dict:
    """Serialize a Property model instance (decrypts address fields)."""
    return {
        "id": str(prop.id),
        "property_type": prop.property_type.value if prop.property_type else None,
        "address": prop.address,  # hybrid_property decrypts
        "street": prop.street,
        "city": prop.city,
        "postal_code": prop.postal_code,
        "purchase_date": prop.purchase_date,
        "purchase_price": prop.purchase_price,
        "building_value": prop.building_value,
        "land_value": prop.land_value,
        "construction_year": prop.construction_year,
        "depreciation_rate": prop.depreciation_rate,
        "status": prop.status.value if prop.status else None,
        "created_at": prop.created_at,
    }


def _serialize_property_loan(loan: PropertyLoan) -> dict:
    """Serialize a PropertyLoan model instance."""
    return {
        "id": loan.id,
        "property_id": str(loan.property_id),
        "loan_amount": loan.loan_amount,
        "interest_rate": loan.interest_rate,
        "start_date": loan.start_date,
        "end_date": loan.end_date,
        "monthly_payment": loan.monthly_payment,
        "lender_name": loan.lender_name,
        "loan_type": loan.loan_type,
        "created_at": loan.created_at,
    }
