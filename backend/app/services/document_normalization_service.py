"""Phase-1 normalization contracts for document business decisions."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import Gewinnermittlungsart, VatStatus
from app.schemas.asset_recognition import DepreciationMethod
from app.schemas.user import TaxProfileCompleteness


class NormalizedDocument(BaseModel):
    """Single normalized business-decision input for the asset path."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    document_id: int
    source_document_id: int = 0
    document_type: str
    document_language: str | None = None
    raw_text: str = ""
    ocr_confidence: Decimal | None = None
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    extracted_amount: Decimal = Decimal("0")
    extracted_net_amount: Decimal | None = None
    extracted_vat_amount: Decimal | None = None
    extracted_date: date | None = None
    extracted_vendor: str | None = None
    extracted_invoice_number: str | None = None
    extracted_line_items: list[Any] = Field(default_factory=list)
    upload_timestamp: datetime
    mime_type: str | None = None
    file_hash: str | None = None
    page_count: int | None = None
    tax_profile_completeness: TaxProfileCompleteness
    vat_status: VatStatus = VatStatus.UNKNOWN
    gewinnermittlungsart: Gewinnermittlungsart = Gewinnermittlungsart.UNKNOWN
    profile_inputs_used: dict[str, str | None] = Field(default_factory=dict)
    business_type: str = "unknown"
    industry_code: str | None = None
    default_business_use_percentage: Decimal | None = None
    duplicate_document_candidates: list[Any] = Field(default_factory=list)
    duplicate_asset_candidates: list[Any] = Field(default_factory=list)
    related_transactions: list[dict[str, Any]] = Field(default_factory=list)
    put_into_use_date: date | None = None
    payment_date: date | None = None
    business_use_percentage: Decimal | None = None
    is_used_asset: bool | None = None
    first_registration_date: date | None = None
    prior_owner_usage_years: Decimal | None = None
    gwg_elected: bool | None = None
    depreciation_method: DepreciationMethod | None = None
    degressive_afa_rate: Decimal | None = None


class DocumentNormalizationService:
    """Normalize pipeline/document state into a single contract."""

    def normalize_asset_document(
        self,
        *,
        document,
        extracted_data: dict[str, Any],
        raw_text: str,
        ocr_confidence: Decimal | None,
        tax_profile_completeness: TaxProfileCompleteness,
        profile_inputs_used: dict[str, str | None],
        vat_status: VatStatus,
        gewinnermittlungsart: Gewinnermittlungsart,
        business_type: str,
        industry_code: str | None,
        extracted_amount: Decimal,
        extracted_net_amount: Decimal | None = None,
        extracted_vat_amount: Decimal | None = None,
        extracted_date: date | None = None,
        extracted_vendor: str | None = None,
        extracted_invoice_number: str | None = None,
        extracted_line_items: list[Any] | None = None,
        default_business_use_percentage: Decimal | None = None,
        page_count: int | None = None,
        duplicate_document_candidates: list[Any] | None = None,
        duplicate_asset_candidates: list[Any] | None = None,
        related_transactions: list[dict[str, Any]] | None = None,
        put_into_use_date: date | None = None,
        payment_date: date | None = None,
        business_use_percentage: Decimal | None = None,
        is_used_asset: bool | None = None,
        first_registration_date: date | None = None,
        prior_owner_usage_years: Decimal | None = None,
        gwg_elected: bool | None = None,
        depreciation_method: DepreciationMethod | None = None,
        degressive_afa_rate: Decimal | None = None,
    ) -> NormalizedDocument:
        return NormalizedDocument(
            document_id=document.id,
            source_document_id=document.id,
            document_type=(
                document.document_type.value
                if hasattr(document.document_type, "value")
                else str(document.document_type)
            ),
            document_language=getattr(document, "language", None),
            raw_text=raw_text or "",
            ocr_confidence=ocr_confidence,
            extracted_data=extracted_data or {},
            extracted_amount=extracted_amount,
            extracted_net_amount=extracted_net_amount,
            extracted_vat_amount=extracted_vat_amount,
            extracted_date=extracted_date,
            extracted_vendor=extracted_vendor,
            extracted_invoice_number=extracted_invoice_number,
            extracted_line_items=extracted_line_items or [],
            upload_timestamp=document.uploaded_at,
            mime_type=getattr(document, "mime_type", None),
            file_hash=getattr(document, "file_hash", None),
            page_count=getattr(document, "page_count", page_count),
            tax_profile_completeness=tax_profile_completeness,
            vat_status=vat_status,
            gewinnermittlungsart=gewinnermittlungsart,
            profile_inputs_used=profile_inputs_used,
            business_type=business_type or "unknown",
            industry_code=industry_code,
            default_business_use_percentage=default_business_use_percentage,
            duplicate_document_candidates=duplicate_document_candidates or [],
            duplicate_asset_candidates=duplicate_asset_candidates or [],
            related_transactions=related_transactions or [],
            put_into_use_date=put_into_use_date,
            payment_date=payment_date,
            business_use_percentage=business_use_percentage,
            is_used_asset=is_used_asset,
            first_registration_date=first_registration_date,
            prior_owner_usage_years=prior_owner_usage_years,
            gwg_elected=gwg_elected,
            depreciation_method=depreciation_method,
            degressive_afa_rate=degressive_afa_rate,
        )
