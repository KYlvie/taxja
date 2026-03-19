"""Schemas and enums for asset tax recognition decisions."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import Gewinnermittlungsart, VatStatus

if TYPE_CHECKING:
    from app.services.document_normalization_service import NormalizedDocument


class AssetRecognitionDecision(str, Enum):
    EXPENSE_ONLY = "expense_only"
    GWG_SUGGESTION = "gwg_suggestion"
    CREATE_ASSET_SUGGESTION = "create_asset_suggestion"
    CREATE_ASSET_AUTO = "create_asset_auto"
    DUPLICATE_WARNING = "duplicate_warning"
    MANUAL_REVIEW = "manual_review"


class PolicyOutcome(str, Enum):
    EXPENSE_ONLY = "expense_only"
    DUPLICATE_WARNING = "duplicate_warning"
    MANUAL_REVIEW = "manual_review"
    SUGGESTION_REQUIRED = "suggestion_required"
    AUTO_CREATE = "auto_create"


class ComparisonBasis(str, Enum):
    NET = "net"
    GROSS = "gross"


class VatRecoverableStatus(str, Enum):
    LIKELY_YES = "likely_yes"
    LIKELY_NO = "likely_no"
    PARTIAL = "partial"
    UNCLEAR = "unclear"


class DepreciationMethod(str, Enum):
    LINEAR = "linear"
    DEGRESSIVE = "degressive"


class UsefulLifeSource(str, Enum):
    LAW = "law"
    TAX_PRACTICE = "tax_practice"
    SYSTEM_DEFAULT = "system_default"
    USER_OVERRIDE = "user_override"


class IfbRateSource(str, Enum):
    STATUTORY_WINDOW = "statutory_window"
    FALLBACK_DEFAULT = "fallback_default"
    NOT_APPLICABLE = "not_applicable"


class DuplicateStatus(str, Enum):
    NONE = "none"
    SUSPECTED = "suspected"
    HIGH_CONFIDENCE = "high_confidence"


class DuplicateMatchType(str, Enum):
    SAME_DOCUMENT = "same_document"
    SAME_INVOICE = "same_invoice"
    SIMILAR_ASSET = "similar_asset"


class AssetReasonCode(str, Enum):
    COMPARISON_BASIS_NET = "comparison_basis_net"
    COMPARISON_BASIS_GROSS = "comparison_basis_gross"
    DURABLE_EQUIPMENT_DETECTED = "durable_equipment_detected"
    LIKELY_LONG_LIVED_ACQUISITION = "likely_long_lived_acquisition"
    USEFUL_LIFE_GT_1Y = "useful_life_gt_1y"
    AMOUNT_WITHIN_GWG_THRESHOLD = "amount_within_gwg_threshold"
    AMOUNT_ABOVE_GWG_THRESHOLD = "amount_above_gwg_threshold"
    SERVICE_OR_SUBSCRIPTION_DETECTED = "service_or_subscription_detected"
    REPAIR_OR_MAINTENANCE_DETECTED = "repair_or_maintenance_detected"
    INVENTORY_OR_RESALE_DETECTED = "inventory_or_resale_detected"
    EXPENSE_DEFAULT_LOW_RISK = "expense_default_low_risk"
    PKW_DETECTED = "pkw_detected"
    ELECTRIC_VEHICLE_DETECTED = "electric_vehicle_detected"
    USED_ASSET_DETECTED = "used_asset_detected"
    DEGRESSIVE_ALLOWED = "degressive_allowed"
    DEGRESSIVE_BLOCKED_USED_ASSET = "degressive_blocked_used_asset"
    DEGRESSIVE_BLOCKED_PKW = "degressive_blocked_pkw"
    IFB_CANDIDATE_STANDARD = "ifb_candidate_standard"
    IFB_CANDIDATE_ECO = "ifb_candidate_eco"
    IFB_BLOCKED_GWG = "ifb_blocked_gwg"
    IFB_BLOCKED_USED_ASSET = "ifb_blocked_used_asset"
    IFB_BLOCKED_SHORT_USEFUL_LIFE = "ifb_blocked_short_useful_life"
    IFB_BLOCKED_ORDINARY_PKW = "ifb_blocked_ordinary_pkw"
    IFB_BLOCKED_NONQUALIFYING_INTANGIBLE = "ifb_blocked_nonqualifying_intangible"
    EXACT_FILE_HASH_DUPLICATE = "exact_file_hash_duplicate"
    DUPLICATE_INVOICE_SIGNATURE = "duplicate_invoice_signature"


class AssetReviewReason(str, Enum):
    VAT_STATUS_UNKNOWN = "vat_status_unknown"
    PUT_INTO_USE_DATE_MISSING = "put_into_use_date_missing"
    USED_VEHICLE_HISTORY_MISSING = "used_vehicle_history_missing"
    SUBTYPE_AMBIGUOUS = "subtype_ambiguous"
    CONFIDENCE_BELOW_THRESHOLD = "confidence_below_threshold"
    DUPLICATE_SUSPECTED = "duplicate_suspected"
    IFB_FUTURE_WINDOW_UNKNOWN = "ifb_future_window_unknown"
    NON_DEPRECIABLE_OR_UNCLEAR = "non_depreciable_or_unclear"
    THRESHOLD_BOUNDARY_AMBIGUOUS = "threshold_boundary_ambiguous"


class DuplicateCandidate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    matched_document_id: int | None = None
    matched_asset_id: str | int | None = None
    file_hash: str | None = None
    vendor_name: str | None = None
    invoice_number: str | None = None
    amount_gross: Decimal | None = None
    amount_net: Decimal | None = None
    document_date: date | None = None


class AssetRecognitionInput(BaseModel):
    """Input contract for recognition-stage decisioning."""

    model_config = ConfigDict(use_enum_values=True)

    extracted_amount: Decimal
    extracted_net_amount: Decimal | None = None
    extracted_vat_amount: Decimal | None = None
    extracted_date: date | None = None
    extracted_vendor: str | None = None
    extracted_invoice_number: str | None = None
    extracted_line_items: list[Any] = Field(default_factory=list)
    document_language: str | None = None
    raw_text: str
    document_type: str
    ocr_confidence: Decimal | None = None

    vat_status: VatStatus = VatStatus.UNKNOWN
    gewinnermittlungsart: Gewinnermittlungsart = Gewinnermittlungsart.UNKNOWN
    business_type: str = "unknown"
    industry_code: str | None = None
    default_business_use_percentage: Decimal | None = None

    source_document_id: int
    upload_timestamp: datetime
    file_hash: str | None = None
    mime_type: str | None = None
    page_count: int | None = None

    duplicate_document_candidates: list[DuplicateCandidate] = Field(default_factory=list)
    duplicate_asset_candidates: list[DuplicateCandidate] = Field(default_factory=list)
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

    @classmethod
    def from_normalized_document(
        cls,
        normalized_document: "NormalizedDocument",
    ) -> "AssetRecognitionInput":
        return cls(
            extracted_amount=normalized_document.extracted_amount,
            extracted_net_amount=normalized_document.extracted_net_amount,
            extracted_vat_amount=normalized_document.extracted_vat_amount,
            extracted_date=normalized_document.extracted_date,
            extracted_vendor=normalized_document.extracted_vendor,
            extracted_invoice_number=normalized_document.extracted_invoice_number,
            extracted_line_items=normalized_document.extracted_line_items,
            document_language=normalized_document.document_language,
            raw_text=normalized_document.raw_text,
            document_type=normalized_document.document_type,
            ocr_confidence=normalized_document.ocr_confidence,
            vat_status=normalized_document.vat_status,
            gewinnermittlungsart=normalized_document.gewinnermittlungsart,
            business_type=normalized_document.business_type,
            industry_code=normalized_document.industry_code,
            default_business_use_percentage=normalized_document.default_business_use_percentage,
            source_document_id=normalized_document.source_document_id,
            upload_timestamp=normalized_document.upload_timestamp,
            file_hash=normalized_document.file_hash,
            mime_type=normalized_document.mime_type,
            page_count=normalized_document.page_count,
            duplicate_document_candidates=normalized_document.duplicate_document_candidates,
            duplicate_asset_candidates=normalized_document.duplicate_asset_candidates,
            related_transactions=normalized_document.related_transactions,
            put_into_use_date=normalized_document.put_into_use_date,
            payment_date=normalized_document.payment_date,
            business_use_percentage=normalized_document.business_use_percentage,
            is_used_asset=normalized_document.is_used_asset,
            first_registration_date=normalized_document.first_registration_date,
            prior_owner_usage_years=normalized_document.prior_owner_usage_years,
            gwg_elected=normalized_document.gwg_elected,
            depreciation_method=normalized_document.depreciation_method,
            degressive_afa_rate=normalized_document.degressive_afa_rate,
        )


class AssetCandidate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    asset_type: str | None = None
    asset_subtype: str | None = None
    asset_name: str | None = None
    vendor_name: str | None = None
    vehicle_category: str | None = None
    is_used_asset: bool | None = None


class AssetTaxFlags(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    depreciable: bool
    gwg_eligible: bool
    gwg_default_selected: bool
    gwg_election_required: bool
    comparison_basis: ComparisonBasis
    comparison_amount: Decimal
    vat_recoverable_status: VatRecoverableStatus
    ifb_candidate: bool
    ifb_rate: Decimal | None = None
    half_year_rule_applicable: bool
    allowed_depreciation_methods: list[DepreciationMethod] = Field(default_factory=list)
    suggested_depreciation_method: DepreciationMethod | None = None
    suggested_useful_life_years: Decimal | None = None
    policy_anchor_date: date | None = None
    gwg_threshold: Decimal | None = None
    degressive_max_rate: Decimal | None = None
    useful_life_source: UsefulLifeSource | None = None
    income_tax_cost_cap: Decimal | None = None
    income_tax_depreciable_base: Decimal | None = None
    vat_recoverable_reason_codes: list[AssetReasonCode] = Field(default_factory=list)
    ifb_rate_source: IfbRateSource | None = None
    ifb_exclusion_codes: list[AssetReasonCode] = Field(default_factory=list)


class DuplicateAssessment(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    duplicate_status: DuplicateStatus = DuplicateStatus.NONE
    duplicate_match_type: DuplicateMatchType | None = None
    matched_asset_id: str | int | None = None
    matched_document_id: int | None = None
    duplicate_reason_codes: list[AssetReasonCode] = Field(default_factory=list)


class AssetTaxPolicyEvaluation(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    tax_flags: AssetTaxFlags
    reason_codes: list[AssetReasonCode] = Field(default_factory=list)
    review_reasons: list[AssetReviewReason] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)


class AssetProfileInputsUsed(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    vat_status: VatStatus | None = None
    gewinnermittlungsart: Gewinnermittlungsart | None = None


class AssetDecisionAudit(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    recognition_decision: AssetRecognitionDecision
    policy_outcome: PolicyOutcome | None = None
    policy_confidence: Decimal | None = None
    reason_codes: list[AssetReasonCode] = Field(default_factory=list)
    review_reasons: list[AssetReviewReason] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    duplicate_status: DuplicateStatus | None = None
    source_document_id: str | int | None = None
    profile_inputs_used: AssetProfileInputsUsed


class AssetOutcomeStatus(str, Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    AUTO_CREATED = "auto_created"
    FAILED = "failed"


class AssetOutcomeSource(str, Enum):
    QUALITY_GATE = "quality_gate"
    USER_CONFIRMATION = "user_confirmation"
    SYSTEM_FALLBACK = "system_fallback"
    LEGACY_COMPAT = "legacy_compat"


class AssetOutcome(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    contract_version: str = "v1"
    type: str = "create_asset"
    status: AssetOutcomeStatus
    decision: AssetRecognitionDecision
    asset_id: str | int | None = None
    source: AssetOutcomeSource
    quality_gate_decision: PolicyOutcome | str | None = None


class AssetRecognitionResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    decision: AssetRecognitionDecision
    asset_candidate: AssetCandidate
    tax_flags: AssetTaxFlags
    reason_codes: list[AssetReasonCode] = Field(default_factory=list)
    review_reasons: list[AssetReviewReason] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    requires_user_confirmation: bool
    policy_confidence: Decimal
    policy_rule_ids: list[str] = Field(default_factory=list)
    duplicate: DuplicateAssessment = Field(default_factory=DuplicateAssessment)
    decision_audit: AssetDecisionAudit | None = None


class AssetSuggestionConfirmationRequest(BaseModel):
    """Minimal user-confirmed facts for asset suggestion finalization."""

    model_config = ConfigDict(use_enum_values=True)

    put_into_use_date: date | None = None
    business_use_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    is_used_asset: bool | None = None
    first_registration_date: date | None = None
    prior_owner_usage_years: Decimal | None = Field(default=None, ge=0, le=Decimal("50.00"))
    gwg_elected: bool | None = None
    depreciation_method: DepreciationMethod | None = None
    degressive_afa_rate: Decimal | None = Field(default=None, gt=0, le=Decimal("0.3000"))
    useful_life_years: int | None = Field(default=None, ge=1, le=50)
