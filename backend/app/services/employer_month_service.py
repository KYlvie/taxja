"""Employer-light month management service."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.document import Document, DocumentType
from app.models.employer_annual_archive import (
    EmployerAnnualArchive,
    EmployerAnnualArchiveDocument,
    EmployerAnnualArchiveStatus,
)
from app.models.employer_month import EmployerMonth, EmployerMonthDocument, EmployerMonthStatus
from app.models.user import User, UserType


def _parse_year_month(year_month: str) -> tuple[int, int]:
    """Validate and split a YYYY-MM string."""
    try:
        year_str, month_str = year_month.split("-", 1)
        year = int(year_str)
        month = int(month_str)
    except (TypeError, ValueError) as exc:
        raise ValueError("year_month must be in YYYY-MM format") from exc

    if year < 2000 or year > 2100 or month < 1 or month > 12:
        raise ValueError("year_month must be in YYYY-MM format")

    return year, month


def _next_month_deadline(year_month: str) -> date:
    """Payroll-related monthly obligations are due by the 15th of the next month."""
    year, month = _parse_year_month(year_month)
    if month == 12:
        return date(year + 1, 1, 15)
    return date(year, month + 1, 15)


def _coerce_decimal(value) -> Optional[Decimal]:
    """Convert floats/strings from OCR output into a Decimal when possible."""
    if value in (None, "", False):
        return None
    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value).replace(",", "."))
    except Exception:
        return None


def _extract_year_month_from_value(value) -> Optional[str]:
    """Parse a YYYY-MM month key from common OCR date formats."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return f"{value.year:04d}-{value.month:02d}"
    if isinstance(value, date):
        return f"{value.year:04d}-{value.month:02d}"

    text = str(value).strip()
    if not text:
        return None

    if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", text):
        return text

    if re.match(r"^\d{4}-(0[1-9]|1[0-2])-\d{1,2}$", text):
        parsed = datetime.strptime(text, "%Y-%m-%d")
        return f"{parsed.year:04d}-{parsed.month:02d}"

    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return f"{parsed.year:04d}-{parsed.month:02d}"
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return f"{parsed.year:04d}-{parsed.month:02d}"
    except ValueError:
        return None


def _extract_summary_from_document(document: Document) -> dict:
    """Pull lightweight month summary fields from OCR output when available."""
    ocr_result = document.ocr_result or {}
    if not isinstance(ocr_result, dict):
        return {}

    summary = {
        "employee_count": ocr_result.get("employee_count"),
        "gross_wages": _coerce_decimal(ocr_result.get("gross_income")),
        "net_paid": _coerce_decimal(ocr_result.get("net_income")),
        "employer_social_cost": _coerce_decimal(ocr_result.get("employer_social_cost")),
        "lohnsteuer": _coerce_decimal(ocr_result.get("withheld_tax")),
        "db_amount": _coerce_decimal(ocr_result.get("db_amount")),
        "dz_amount": _coerce_decimal(ocr_result.get("dz_amount")),
        "kommunalsteuer": _coerce_decimal(ocr_result.get("kommunalsteuer")),
        "special_payments": _coerce_decimal(ocr_result.get("special_payments")),
    }
    return {key: value for key, value in summary.items() if value is not None}


def _extract_year_month_from_document(document: Document) -> str:
    """Infer the payroll month from OCR output, then fall back to upload date."""
    ocr_result = document.ocr_result or {}
    if isinstance(ocr_result, dict):
        candidate_fields = (
            "year_month",
            "payroll_month",
            "salary_month",
            "pay_date",
            "date",
            "period_start",
            "service_date",
        )
        for field in candidate_fields:
            year_month = _extract_year_month_from_value(ocr_result.get(field))
            if year_month:
                return year_month

    uploaded_at = document.processed_at or document.uploaded_at or datetime.utcnow()
    return f"{uploaded_at.year:04d}-{uploaded_at.month:02d}"


def _extract_tax_year(value) -> Optional[int]:
    """Parse a tax year from OCR output if it looks trustworthy."""
    if value is None or value == "":
        return None

    if isinstance(value, int):
        return value if 2000 <= value <= 2100 else None

    if isinstance(value, Decimal):
        year = int(value)
        return year if 2000 <= year <= 2100 else None

    text = str(value).strip()
    if not text:
        return None

    match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    if not match:
        return None

    year = int(match.group(1))
    return year if 2000 <= year <= 2100 else None


def _extract_tax_year_from_document(document: Document) -> Optional[int]:
    """Infer the historical payroll year from structured OCR output."""
    ocr_result = document.ocr_result or {}
    if not isinstance(ocr_result, dict):
        return None

    candidate_fields = (
        "tax_year",
        "calendar_year",
        "year",
        "assessment_year",
        "lohnzettel_year",
    )
    for field in candidate_fields:
        year = _extract_tax_year(ocr_result.get(field))
        if year is not None:
            return year

    return None


def _extract_annual_summary_from_document(document: Document) -> dict:
    """Pull annual payroll summary fields from OCR output when available."""
    ocr_result = document.ocr_result or {}
    if not isinstance(ocr_result, dict):
        return {}

    summary = {
        "employer_name": ocr_result.get("employer_name") or ocr_result.get("employer"),
        "gross_income": _coerce_decimal(ocr_result.get("gross_income") or ocr_result.get("kz_210")),
        "withheld_tax": _coerce_decimal(ocr_result.get("withheld_tax") or ocr_result.get("kz_260")),
    }
    return {key: value for key, value in summary.items() if value is not None}


class EmployerMonthService:
    """CRUD and summary logic for employer-light monthly states."""

    def __init__(self, db: Session):
        self.db = db

    def get_month(self, user_id: int, year_month: str) -> Optional[EmployerMonth]:
        _parse_year_month(year_month)
        return (
            self.db.query(EmployerMonth)
            .options(joinedload(EmployerMonth.document_links).joinedload(EmployerMonthDocument.document))
            .filter(EmployerMonth.user_id == user_id, EmployerMonth.year_month == year_month)
            .first()
        )

    def list_months(self, user_id: int, year: int) -> list[EmployerMonth]:
        prefix = f"{year}-"
        return (
            self.db.query(EmployerMonth)
            .options(joinedload(EmployerMonth.document_links).joinedload(EmployerMonthDocument.document))
            .filter(EmployerMonth.user_id == user_id, EmployerMonth.year_month.like(f"{prefix}%"))
            .order_by(EmployerMonth.year_month.asc())
            .all()
        )

    def get_month_by_document(self, user_id: int, document_id: int) -> Optional[EmployerMonth]:
        return (
            self.db.query(EmployerMonth)
            .join(EmployerMonth.document_links)
            .options(joinedload(EmployerMonth.document_links).joinedload(EmployerMonthDocument.document))
            .filter(
                EmployerMonth.user_id == user_id,
                EmployerMonthDocument.document_id == document_id,
            )
            .first()
        )

    def get_or_create_month(self, user_id: int, year_month: str) -> EmployerMonth:
        _parse_year_month(year_month)
        month = self.get_month(user_id, year_month)
        if month:
            return month

        month = EmployerMonth(user_id=user_id, year_month=year_month, status=EmployerMonthStatus.UNKNOWN)
        self.db.add(month)
        self.db.flush()
        return month

    def mark_payroll_detected(
        self,
        user_id: int,
        year_month: str,
        *,
        document_id: Optional[int] = None,
        source_type: str = "manual_summary",
        payroll_signal: Optional[str] = None,
        confidence: Optional[Decimal] = None,
        summary: Optional[dict] = None,
    ) -> EmployerMonth:
        month = self.get_or_create_month(user_id, year_month)
        month.status = EmployerMonthStatus.PAYROLL_DETECTED
        month.source_type = source_type
        month.payroll_signal = payroll_signal
        month.confidence = confidence
        month.last_signal_at = datetime.utcnow()
        month.confirmed_at = datetime.utcnow()

        if summary:
            self.apply_summary(month, summary)

        if document_id is not None:
            self.link_document(month, document_id)

        self.db.flush()
        return month

    def mark_missing_confirmation(
        self,
        user_id: int,
        year_month: str,
        *,
        payroll_signal: Optional[str] = None,
        document_id: Optional[int] = None,
        source_type: str = "ai_signal",
        confidence: Optional[Decimal] = None,
        summary: Optional[dict] = None,
    ) -> EmployerMonth:
        month = self.get_or_create_month(user_id, year_month)
        if month.status != EmployerMonthStatus.PAYROLL_DETECTED:
            month.status = EmployerMonthStatus.MISSING_CONFIRMATION
        month.source_type = source_type
        month.payroll_signal = payroll_signal
        month.confidence = confidence
        month.last_signal_at = datetime.utcnow()

        if summary:
            self.apply_summary(month, summary)

        if document_id is not None:
            self.link_document(month, document_id)

        self.db.flush()
        return month

    def confirm_no_payroll(self, user_id: int, year_month: str, note: Optional[str] = None) -> EmployerMonth:
        month = self.get_or_create_month(user_id, year_month)
        month.status = EmployerMonthStatus.NO_PAYROLL_CONFIRMED
        month.confirmed_at = datetime.utcnow()
        month.notes = note or month.notes
        self.db.flush()
        return month

    def update_summary(self, user_id: int, year_month: str, summary: dict) -> EmployerMonth:
        month = self.get_or_create_month(user_id, year_month)
        self.apply_summary(month, summary)
        self.db.flush()
        return month

    def apply_summary(self, month: EmployerMonth, summary: dict) -> None:
        editable_fields = [
            "employee_count",
            "gross_wages",
            "net_paid",
            "employer_social_cost",
            "lohnsteuer",
            "db_amount",
            "dz_amount",
            "kommunalsteuer",
            "special_payments",
            "notes",
        ]
        for field in editable_fields:
            if field in summary:
                setattr(month, field, summary[field])

    def link_document(self, month: EmployerMonth, document_id: int, relation_type: str = "supporting") -> None:
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == month.user_id)
            .first()
        )
        if document is None:
            raise ValueError("Document not found")

        exists = next((link for link in month.document_links if link.document_id == document_id), None)
        if exists:
            exists.relation_type = relation_type
            return

        month.document_links.append(
            EmployerMonthDocument(document_id=document_id, relation_type=relation_type)
        )

    def detect_from_document(self, user: User, document_id: int) -> tuple[bool, Optional[EmployerMonth], Optional[str]]:
        """Inspect a document and create/update an employer month when it looks payroll-related."""
        if (user.employer_mode or "none") == "none":
            return False, None, "employer_mode_disabled"

        if user.user_type not in {UserType.SELF_EMPLOYED, UserType.MIXED}:
            return False, None, "user_type_not_supported"

        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user.id)
            .first()
        )
        if document is None:
            raise ValueError("Document not found")

        document_type = (
            document.document_type.value
            if hasattr(document.document_type, "value")
            else str(document.document_type)
        )
        if document_type != "payslip":
            return False, None, "not_monthly_payroll_document"

        year_month = _extract_year_month_from_document(document)
        confidence = _coerce_decimal(document.confidence_score)
        summary = _extract_summary_from_document(document)

        month = self.get_month(user.id, year_month)
        if month and month.status == EmployerMonthStatus.PAYROLL_DETECTED:
            month.source_type = "document_detected"
            month.payroll_signal = document_type
            month.confidence = confidence
            month.last_signal_at = datetime.utcnow()
            if summary:
                self.apply_summary(month, summary)
            self.link_document(month, document.id)
            self.db.flush()
            return False, month, "already_confirmed"

        month = self.mark_missing_confirmation(
            user.id,
            year_month,
            payroll_signal=document_type,
            document_id=document.id,
            source_type="document_detected",
            confidence=confidence,
            summary=summary,
        )
        return True, month, None

    def get_annual_archive(self, user_id: int, tax_year: int) -> Optional[EmployerAnnualArchive]:
        return (
            self.db.query(EmployerAnnualArchive)
            .options(
                joinedload(EmployerAnnualArchive.document_links).joinedload(
                    EmployerAnnualArchiveDocument.document
                )
            )
            .filter(EmployerAnnualArchive.user_id == user_id, EmployerAnnualArchive.tax_year == tax_year)
            .first()
        )

    def list_annual_archives(self, user_id: int) -> list[EmployerAnnualArchive]:
        return (
            self.db.query(EmployerAnnualArchive)
            .options(
                joinedload(EmployerAnnualArchive.document_links).joinedload(
                    EmployerAnnualArchiveDocument.document
                )
            )
            .filter(EmployerAnnualArchive.user_id == user_id)
            .order_by(EmployerAnnualArchive.tax_year.desc())
            .all()
        )

    def get_annual_archive_by_document(
        self,
        user_id: int,
        document_id: int,
    ) -> Optional[EmployerAnnualArchive]:
        return (
            self.db.query(EmployerAnnualArchive)
            .join(EmployerAnnualArchive.document_links)
            .options(
                joinedload(EmployerAnnualArchive.document_links).joinedload(
                    EmployerAnnualArchiveDocument.document
                )
            )
            .filter(
                EmployerAnnualArchive.user_id == user_id,
                EmployerAnnualArchiveDocument.document_id == document_id,
            )
            .first()
        )

    def get_or_create_annual_archive(self, user_id: int, tax_year: int) -> EmployerAnnualArchive:
        archive = self.get_annual_archive(user_id, tax_year)
        if archive:
            return archive

        archive = EmployerAnnualArchive(
            user_id=user_id,
            tax_year=tax_year,
            status=EmployerAnnualArchiveStatus.PENDING_CONFIRMATION,
        )
        self.db.add(archive)
        self.db.flush()
        return archive

    def apply_annual_summary(self, archive: EmployerAnnualArchive, summary: dict) -> None:
        editable_fields = ["employer_name", "gross_income", "withheld_tax", "notes"]
        for field in editable_fields:
            if field in summary:
                setattr(archive, field, summary[field])

    def link_annual_document(
        self,
        archive: EmployerAnnualArchive,
        document_id: int,
        relation_type: str = "supporting",
    ) -> None:
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == archive.user_id)
            .first()
        )
        if document is None:
            raise ValueError("Document not found")

        exists = next((link for link in archive.document_links if link.document_id == document_id), None)
        if exists:
            exists.relation_type = relation_type
            return

        archive.document_links.append(
            EmployerAnnualArchiveDocument(document_id=document_id, relation_type=relation_type)
        )

    def mark_annual_archive_pending(
        self,
        user_id: int,
        tax_year: int,
        *,
        document_id: Optional[int] = None,
        archive_signal: Optional[str] = None,
        source_type: str = "document_detected",
        confidence: Optional[Decimal] = None,
        summary: Optional[dict] = None,
    ) -> EmployerAnnualArchive:
        archive = self.get_or_create_annual_archive(user_id, tax_year)
        if archive.status != EmployerAnnualArchiveStatus.ARCHIVED:
            archive.status = EmployerAnnualArchiveStatus.PENDING_CONFIRMATION
        archive.source_type = source_type
        archive.archive_signal = archive_signal
        archive.confidence = confidence
        archive.last_signal_at = datetime.utcnow()

        if summary:
            self.apply_annual_summary(archive, summary)

        if document_id is not None:
            self.link_annual_document(archive, document_id)

        self.db.flush()
        return archive

    def confirm_annual_archive(
        self,
        user_id: int,
        tax_year: int,
        *,
        document_id: Optional[int] = None,
        archive_signal: Optional[str] = None,
        source_type: str = "manual_archive",
        confidence: Optional[Decimal] = None,
        summary: Optional[dict] = None,
    ) -> EmployerAnnualArchive:
        archive = self.get_or_create_annual_archive(user_id, tax_year)
        archive.status = EmployerAnnualArchiveStatus.ARCHIVED
        archive.source_type = source_type
        archive.archive_signal = archive_signal
        archive.confidence = confidence
        archive.last_signal_at = datetime.utcnow()
        archive.confirmed_at = datetime.utcnow()

        if summary:
            self.apply_annual_summary(archive, summary)

        if document_id is not None:
            self.link_annual_document(archive, document_id)

        self.db.flush()
        return archive

    def detect_annual_archive_from_document(
        self,
        user: User,
        document_id: int,
    ) -> tuple[bool, Optional[EmployerAnnualArchive], Optional[str]]:
        """Inspect a document and create/update a historical annual payroll archive when relevant."""
        if (user.employer_mode or "none") == "none":
            return False, None, "employer_mode_disabled"

        if user.user_type not in {UserType.SELF_EMPLOYED, UserType.MIXED}:
            return False, None, "user_type_not_supported"

        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user.id)
            .first()
        )
        if document is None:
            raise ValueError("Document not found")

        if document.document_type != DocumentType.LOHNZETTEL:
            return False, None, "not_historical_payroll_archive_document"

        tax_year = _extract_tax_year_from_document(document)
        if tax_year is None:
            return False, None, "tax_year_not_found"

        current_year = datetime.utcnow().year
        if tax_year >= current_year:
            return False, None, "current_year_not_archivable"

        confidence = _coerce_decimal(document.confidence_score)
        summary = _extract_annual_summary_from_document(document)
        archive = self.get_annual_archive(user.id, tax_year)
        if archive and archive.status == EmployerAnnualArchiveStatus.ARCHIVED:
            archive.source_type = "document_detected"
            archive.archive_signal = document.document_type.value
            archive.confidence = confidence
            archive.last_signal_at = datetime.utcnow()
            if summary:
                self.apply_annual_summary(archive, summary)
            self.link_annual_document(archive, document.id)
            self.db.flush()
            return False, archive, "already_archived"

        archive = self.mark_annual_archive_pending(
            user.id,
            tax_year,
            document_id=document.id,
            archive_signal=document.document_type.value,
            source_type="document_detected",
            confidence=confidence,
            summary=summary,
        )
        return True, archive, None

    def get_document_review_context(self, user: User, document_id: int) -> dict:
        """Return the non-mutating employer review context for a document detail page."""
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user.id)
            .first()
        )
        if document is None:
            raise ValueError("Document not found")

        document_type = (
            document.document_type.value
            if hasattr(document.document_type, "value")
            else str(document.document_type)
        )
        response = {
            "supported": False,
            "reason": None,
            "document_id": document.id,
            "document_type": document_type,
            "candidate_year_month": None,
            "candidate_tax_year": None,
            "month": None,
            "annual_archive": None,
        }

        if (user.employer_mode or "none") == "none":
            response["reason"] = "employer_mode_disabled"
            return response

        if user.user_type not in {UserType.SELF_EMPLOYED, UserType.MIXED}:
            response["reason"] = "user_type_not_supported"
            return response

        if document.document_type == DocumentType.PAYSLIP:
            candidate_year_month = _extract_year_month_from_document(document)
            month = self.get_month_by_document(user.id, document.id)
            if month is None:
                month = self.get_month(user.id, candidate_year_month)

            response.update(
                {
                    "supported": True,
                    "candidate_year_month": candidate_year_month,
                    "month": month,
                }
            )
            return response

        if document.document_type == DocumentType.LOHNZETTEL:
            candidate_tax_year = _extract_tax_year_from_document(document)
            archive = self.get_annual_archive_by_document(user.id, document.id)

            if archive is None and candidate_tax_year is not None:
                archive = self.get_annual_archive(user.id, candidate_tax_year)

            current_year = datetime.utcnow().year
            if candidate_tax_year is not None and candidate_tax_year >= current_year and archive is None:
                response["reason"] = "current_year_not_archivable"
                response["candidate_tax_year"] = candidate_tax_year
                return response

            if archive is None and candidate_tax_year is None:
                response["reason"] = "tax_year_not_found"
                return response

            response.update(
                {
                    "supported": True,
                    "candidate_tax_year": candidate_tax_year or (archive.tax_year if archive is not None else None),
                    "annual_archive": archive,
                }
            )
            return response

        response["reason"] = "not_payroll_review_document"
        return response

    def get_overview(self, user_id: int, year: int, employer_mode: str) -> dict:
        months = self.list_months(user_id, year)
        status_counts = {
            EmployerMonthStatus.PAYROLL_DETECTED: 0,
            EmployerMonthStatus.MISSING_CONFIRMATION: 0,
            EmployerMonthStatus.NO_PAYROLL_CONFIRMED: 0,
            EmployerMonthStatus.UNKNOWN: 0,
            EmployerMonthStatus.ARCHIVED_YEAR_ONLY: 0,
        }

        upcoming_deadlines: list[tuple[date, str]] = []
        today = date.today()
        for month in months:
            status_counts[month.status] = status_counts.get(month.status, 0) + 1
            if month.status in (
                EmployerMonthStatus.PAYROLL_DETECTED,
                EmployerMonthStatus.MISSING_CONFIRMATION,
            ):
                deadline = _next_month_deadline(month.year_month)
                if deadline >= today:
                    upcoming_deadlines.append((deadline, f"Employer month {month.year_month}"))

        upcoming_deadlines.sort(key=lambda item: item[0])
        next_deadline = upcoming_deadlines[0] if upcoming_deadlines else None

        return {
            "year": year,
            "employer_mode": employer_mode or "none",
            "total_months": len(months),
            "payroll_months": status_counts[EmployerMonthStatus.PAYROLL_DETECTED],
            "missing_confirmation_months": status_counts[EmployerMonthStatus.MISSING_CONFIRMATION],
            "no_payroll_months": status_counts[EmployerMonthStatus.NO_PAYROLL_CONFIRMED],
            "unknown_months": status_counts[EmployerMonthStatus.UNKNOWN],
            "next_deadline": next_deadline[0] if next_deadline else None,
            "next_deadline_label": next_deadline[1] if next_deadline else None,
        }
