"""OCR processing tasks"""
import re
from celery import Task, group
from celery.exceptions import Retry as CeleryRetry
from typing import List, Dict, Any
from types import SimpleNamespace
from datetime import datetime, date
from decimal import Decimal
import logging

from app.celery_app import celery_app
from app.services.ocr_engine import OCREngine
from app.services.credit_service import CreditService

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
        """Handle task failure — refund credits if applicable"""
        logger.error(f"OCR task {task_id} failed: {exc}")
        logger.error(f"Traceback: {einfo}")

        # Refund credits for failed OCR processing
        document_id = args[0] if args else kwargs.get("document_id")
        if document_id is not None:
            try:
                from app.db.base import SessionLocal
                from app.models.document import Document

                db = SessionLocal()
                try:
                    document = db.query(Document).filter(Document.id == document_id).first()
                    if document:
                        credit_service = CreditService(db, redis_client=None)
                        credit_service.refund_credits(
                            user_id=document.user_id,
                            operation="ocr_scan",
                            reason="ocr_processing_failed",
                            context_type="document",
                            context_id=document_id,
                            refund_key=f"refund:ocr:{document_id}",
                        )
                        db.commit()
                        logger.info(f"Refunded OCR credits for failed document {document_id}")
                except Exception as refund_err:
                    db.rollback()
                    logger.error(
                        f"Failed to refund credits for document {document_id}: {refund_err}"
                    )
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Could not refund credits for document {document_id}: {e}")


def _parse_ocr_date(value):
    """Parse common OCR date formats into date objects."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def _to_decimal(value):
    """Best-effort Decimal conversion for OCR values."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _resolve_result_confidence(document, result):
    """
    Resolve OCR/classification confidence across legacy OCRResult and PipelineResult.

    Older callers pass an OCRResult with ``confidence_score`` while the newer
    orchestrator path passes a PipelineResult with ``classification.confidence``.
    Prefer the persisted document score, then gracefully fall back to whatever
    the in-memory result object exposes.
    """
    document_confidence = _to_decimal(getattr(document, "confidence_score", None))
    if document_confidence is not None:
        return document_confidence

    legacy_confidence = _to_decimal(getattr(result, "confidence_score", None))
    if legacy_confidence is not None:
        return legacy_confidence

    classification = getattr(result, "classification", None)
    classification_confidence = _to_decimal(
        getattr(classification, "confidence", None) if classification else None
    )
    if classification_confidence is not None:
        return classification_confidence

    extracted_confidence = None
    if isinstance(getattr(result, "extracted_data", None), dict):
        extracted_confidence = _to_decimal(result.extracted_data.get("confidence"))
    if extracted_confidence is not None:
        return extracted_confidence

    return Decimal("0")


def _extract_invoice_number(ocr_data: dict) -> str | None:
    for key in ("invoice_number", "invoice_no", "rechnung_nr", "receipt_number", "beleg_nr"):
        value = ocr_data.get(key)
        if value:
            return str(value)
    return None


def _serialize_asset_recognition_result(recognition_result) -> dict:
    """Convert recognition result into JSON-safe dict for ocr_result."""
    if recognition_result is None:
        return {}
    if hasattr(recognition_result, "model_dump"):
        return _make_json_safe(recognition_result.model_dump(mode="json"))
    return _make_json_safe(recognition_result)


def _build_duplicate_document_candidates(db, document) -> list:
    """Collect likely duplicate OCR documents for the same user."""
    from app.models.document import Document
    from app.schemas.asset_recognition import DuplicateCandidate

    candidates = []
    existing_documents = (
        db.query(Document)
        .filter(
            Document.user_id == document.user_id,
            Document.id != document.id,
            Document.ocr_result.isnot(None),
        )
        .order_by(Document.uploaded_at.desc())
        .limit(25)
        .all()
    )

    for existing in existing_documents:
        ocr_data = existing.ocr_result if isinstance(existing.ocr_result, dict) else {}
        candidates.append(
            DuplicateCandidate(
                matched_document_id=existing.id,
                file_hash=existing.file_hash,
                vendor_name=ocr_data.get("merchant") or ocr_data.get("supplier"),
                invoice_number=_extract_invoice_number(ocr_data),
                amount_gross=_to_decimal(ocr_data.get("amount") or ocr_data.get("purchase_price")),
                amount_net=_to_decimal(ocr_data.get("net_amount")),
                document_date=_parse_ocr_date(
                    ocr_data.get("purchase_date") or ocr_data.get("date")
                ),
            )
        )
    return candidates


def _build_duplicate_asset_candidates(db, document) -> list:
    """Collect existing non-real-estate assets for duplicate detection."""
    from sqlalchemy import text

    from app.schemas.asset_recognition import DuplicateCandidate

    candidates = []
    query = text(
        """
        select
            id,
            supplier,
            purchase_price,
            purchase_date,
            asset_type,
            name
        from properties
        where user_id = :user_id
          and asset_type != 'real_estate'
        order by created_at desc
        limit 25
        """
    )
    asset_rows = db.execute(query, {"user_id": document.user_id}).mappings().all()

    for asset in asset_rows:
        candidates.append(
            DuplicateCandidate(
                matched_asset_id=str(asset["id"]),
                vendor_name=asset["supplier"],
                amount_gross=_to_decimal(asset["purchase_price"]),
                document_date=asset["purchase_date"],
                invoice_number=None,
                file_hash=None,
            )
        )
    return candidates


def _get_user_and_tax_profile_context(db, user_id: int):
    """Load the user together with persisted tax-profile source-of-truth."""
    from app.services.contract_role_service import load_sensitive_user_context
    from app.services.tax_profile_service import TaxProfileService

    user = load_sensitive_user_context(db, user_id)
    if not user:
        return None, None
    return user, TaxProfileService().get_asset_tax_profile_context(user)


def _profile_inputs_used_payload(profile_context) -> dict[str, str | None]:
    return {
        "vat_status": getattr(profile_context.vat_status, "value", profile_context.vat_status),
        "gewinnermittlungsart": getattr(
            profile_context.gewinnermittlungsart,
            "value",
            profile_context.gewinnermittlungsart,
        ),
    }


def _build_asset_decision_audit(recognition_input, recognition_result, profile_context, policy_outcome):
    """Build the minimum asset decision audit payload."""
    from app.schemas.asset_recognition import (
        AssetDecisionAudit,
        AssetProfileInputsUsed,
    )

    return AssetDecisionAudit(
        recognition_decision=recognition_result.decision,
        policy_outcome=policy_outcome,
        policy_confidence=recognition_result.policy_confidence,
        reason_codes=recognition_result.reason_codes,
        review_reasons=recognition_result.review_reasons,
        missing_fields=list(
            dict.fromkeys(
                list(recognition_result.missing_fields)
                + list(profile_context.completeness.missing_fields)
            )
        ),
        duplicate_status=recognition_result.duplicate.duplicate_status,
        source_document_id=recognition_input.source_document_id,
        profile_inputs_used=AssetProfileInputsUsed(
            vat_status=profile_context.vat_status,
            gewinnermittlungsart=profile_context.gewinnermittlungsart,
        ),
    )


def _build_asset_outcome_payload(
    *,
    status,
    decision,
    source,
    asset_id=None,
    quality_gate_decision=None,
):
    """Build the persisted asset outcome contract for OCR result state."""
    from app.schemas.asset_recognition import AssetOutcome

    return AssetOutcome(
        status=status,
        decision=decision,
        asset_id=asset_id,
        source=source,
        quality_gate_decision=quality_gate_decision,
    ).model_dump(mode="json")


def _clear_asset_import_suggestion(ocr_result: dict) -> None:
    suggestion = ocr_result.get("import_suggestion")
    if isinstance(suggestion, dict) and suggestion.get("type") == "create_asset":
        ocr_result.pop("import_suggestion", None)


def _clear_import_suggestion_types(ocr_result: dict, suggestion_types: set[str]) -> None:
    suggestion = ocr_result.get("import_suggestion")
    if isinstance(suggestion, dict) and suggestion.get("type") in suggestion_types:
        ocr_result.pop("import_suggestion", None)


PURCHASE_CONTRACT_EXTRACTED_FIELDS = {
    "property_address",
    "street",
    "city",
    "postal_code",
    "purchase_price",
    "purchase_date",
    "building_value",
    "land_value",
    "grunderwerbsteuer",
    "notary_fees",
    "registry_fees",
    "buyer_name",
    "seller_name",
    "notary_name",
    "notary_location",
    "construction_year",
    "property_type",
}


def _apply_contract_role_resolution(updated_ocr: dict, resolution) -> None:
    if resolution is None:
        return
    updated_ocr["user_contract_role"] = resolution.candidate
    updated_ocr["user_contract_role_source"] = resolution.source
    updated_ocr["user_contract_role_confidence"] = round(float(resolution.confidence), 4)
    updated_ocr["contract_role_resolution"] = resolution.to_payload()


def _annotate_contract_role_gate(target: dict | None, resolution) -> None:
    if not isinstance(target, dict) or resolution is None:
        return

    target["user_contract_role"] = resolution.candidate
    target["user_contract_role_source"] = resolution.source
    target["user_contract_role_confidence"] = round(float(resolution.confidence), 4)
    target["role_evidence"] = list(resolution.evidence)
    target["role_gate_mode"] = resolution.mode
    target["role_gate_would_block"] = resolution.strict_would_block
    target["role_gate_reason"] = resolution.evidence[0] if resolution.evidence else None


def _apply_transaction_direction_resolution(updated_ocr: dict, resolution) -> None:
    if resolution is None:
        return
    updated_ocr["document_transaction_direction"] = resolution.candidate
    updated_ocr["document_transaction_direction_source"] = resolution.source
    updated_ocr["document_transaction_direction_confidence"] = round(
        float(resolution.confidence),
        4,
    )
    updated_ocr["transaction_direction_resolution"] = resolution.to_payload()
    updated_ocr["commercial_document_semantics"] = resolution.semantics
    updated_ocr["is_reversal"] = bool(resolution.is_reversal)


def _annotate_transaction_direction_gate(target: dict | None, resolution) -> None:
    if not isinstance(target, dict) or resolution is None:
        return

    target["document_transaction_direction"] = resolution.candidate
    target["document_transaction_direction_source"] = resolution.source
    target["document_transaction_direction_confidence"] = round(
        float(resolution.confidence),
        4,
    )
    target["direction_evidence"] = list(resolution.evidence)
    target["commercial_document_semantics"] = resolution.semantics
    target["is_reversal"] = bool(resolution.is_reversal)
    target["direction_gate_mode"] = resolution.mode
    target["direction_gate_would_block"] = resolution.strict_would_block
    target["direction_gate_reason"] = resolution.evidence[0] if resolution.evidence else None


def _resolve_contract_role_for_document(
    db,
    document,
    ocr_data: dict | None = None,
    *,
    purchase_contract_kind: str | None = None,
    raw_text: str | None = None,
):
    from app.models.document import DocumentType as DBDocumentType
    from app.services.contract_role_service import ContractRoleService

    user, _ = _get_user_and_tax_profile_context(db, document.user_id)
    if not user:
        return None

    role_input = ocr_data if isinstance(ocr_data, dict) else (document.ocr_result or {})
    service = ContractRoleService(language=getattr(user, "language", None))

    if document.document_type == DBDocumentType.RENTAL_CONTRACT:
        return service.resolve_rental_contract_role(user, role_input, raw_text=raw_text or document.raw_text)

    if document.document_type == DBDocumentType.PURCHASE_CONTRACT:
        return service.resolve_purchase_contract_role(
            user,
            role_input,
            contract_kind=purchase_contract_kind or role_input.get("purchase_contract_kind"),
            raw_text=raw_text or document.raw_text,
        )

    if document.document_type == DBDocumentType.LOAN_CONTRACT:
        return service.resolve_loan_contract_role(user, role_input, raw_text=raw_text or document.raw_text)

    if document.document_type == DBDocumentType.VERSICHERUNGSBESTAETIGUNG:
        return service.resolve_insurance_role(user, role_input, raw_text=raw_text or document.raw_text)

    return None


def _resolve_transaction_direction_for_document(
    db,
    document,
    ocr_data: dict | None = None,
    *,
    raw_text: str | None = None,
):
    from app.models.document import DocumentType as DBDocumentType
    from app.services.contract_role_service import ContractRoleService

    if getattr(document, "document_type", None) not in {
        DBDocumentType.INVOICE,
        DBDocumentType.RECEIPT,
        DBDocumentType.BANK_STATEMENT,
    }:
        return None

    user, _ = _get_user_and_tax_profile_context(db, document.user_id)
    if not user:
        return None

    direction_input = ocr_data if isinstance(ocr_data, dict) else (document.ocr_result or {})
    service = ContractRoleService(language=getattr(user, "language", None))
    return service.resolve_transaction_direction(
        user,
        document.document_type,
        direction_input,
        raw_text=raw_text or document.raw_text,
    )


def _persist_transaction_suggestions_on_document(document, suggestions: list[dict]) -> None:
    updated_ocr = document.ocr_result.copy() if isinstance(document.ocr_result, dict) else {}
    if suggestions:
        updated_ocr["transaction_suggestion"] = suggestions[0]
        updated_ocr["tax_analysis"] = {
            "items": [
                {
                    "description": suggestion.get("description", ""),
                    "amount": suggestion.get("amount"),
                    "category": suggestion.get("category"),
                    "is_deductible": suggestion.get("is_deductible", False),
                    "deduction_reason": suggestion.get("deduction_reason", ""),
                    "confidence": suggestion.get("confidence", 0),
                    "transaction_type": suggestion.get("transaction_type", "expense"),
                    "commercial_document_semantics": suggestion.get(
                        "commercial_document_semantics",
                        updated_ocr.get("commercial_document_semantics"),
                    ),
                    "is_reversal": suggestion.get("is_reversal", updated_ocr.get("is_reversal")),
                }
                for suggestion in suggestions
            ],
            "is_split": len(suggestions) > 1,
            "commercial_document_semantics": suggestions[0].get(
                "commercial_document_semantics",
                updated_ocr.get("commercial_document_semantics"),
            ),
            "is_reversal": suggestions[0].get("is_reversal", updated_ocr.get("is_reversal")),
        }
    else:
        updated_ocr.pop("transaction_suggestion", None)
        updated_ocr.pop("tax_analysis", None)

    document.ocr_result = _make_json_safe(updated_ocr)


def _clear_transaction_artifact_keys(ocr_payload: dict) -> dict:
    for key in (
        "transaction_suggestion",
        "tax_analysis",
        "matched_existing",
        "document_transaction_direction",
        "document_transaction_direction_source",
        "document_transaction_direction_confidence",
        "transaction_direction_resolution",
        "commercial_document_semantics",
        "is_reversal",
    ):
        ocr_payload.pop(key, None)
    return ocr_payload


def _clear_transaction_artifacts_on_document(document) -> None:
    """Remove transaction-oriented OCR artifacts when a document moves to another flow."""
    updated_ocr = document.ocr_result.copy() if isinstance(document.ocr_result, dict) else {}
    updated_ocr = _clear_transaction_artifact_keys(updated_ocr)
    document.ocr_result = _make_json_safe(updated_ocr)


def _update_direction_metadata_only(db, document, result) -> dict:
    from sqlalchemy.orm.attributes import flag_modified

    updated_ocr = document.ocr_result.copy() if isinstance(document.ocr_result, dict) else {}
    resolution = _resolve_transaction_direction_for_document(
        db,
        document,
        updated_ocr,
        raw_text=getattr(result, "raw_text", None) or document.raw_text,
    )
    _apply_transaction_direction_resolution(updated_ocr, resolution)
    document.ocr_result = _make_json_safe(updated_ocr)
    flag_modified(document, "ocr_result")
    db.flush()
    return {
        "transaction_direction_resolution": resolution.to_payload() if resolution else None,
        "commercial_document_semantics": updated_ocr.get("commercial_document_semantics"),
        "is_reversal": updated_ocr.get("is_reversal"),
    }


def _refresh_direction_sensitive_suggestions(db, document, result) -> dict:
    from app.models.document import DocumentType as DBDocumentType
    from app.services.ocr_transaction_service import OCRTransactionService
    from sqlalchemy.orm.attributes import flag_modified

    if document.document_type == DBDocumentType.BANK_STATEMENT:
        return _update_direction_metadata_only(db, document, result)

    suggestions = OCRTransactionService(db).create_split_suggestions(document.id, document.user_id)
    _persist_transaction_suggestions_on_document(document, suggestions)
    flag_modified(document, "ocr_result")
    db.flush()
    return {
        "transaction_suggestions": suggestions,
        "transaction_suggestion": suggestions[0] if suggestions else None,
    }


def _get_corrected_field_names(ocr_result: dict | None) -> set[str]:
    if not isinstance(ocr_result, dict):
        return set()

    corrected_fields: set[str] = set()
    history = ocr_result.get("correction_history")
    if not isinstance(history, list):
        return corrected_fields

    for entry in history:
        if not isinstance(entry, dict):
            continue
        fields = entry.get("corrected_fields")
        if isinstance(fields, list):
            corrected_fields.update(
                str(field_name) for field_name in fields if isinstance(field_name, str)
            )

    return corrected_fields


def _refresh_purchase_contract_extracted_data(
    document,
    result=None,
) -> dict | None:
    """Re-extract purchase-contract facts while preserving user-corrected fields."""
    from app.services.kaufvertrag_extractor import KaufvertragExtractor

    raw_text = document.raw_text or getattr(result, "raw_text", None) or ""
    if not raw_text.strip():
        return None

    extractor = KaufvertragExtractor()
    refreshed = extractor.to_dict(extractor.extract(raw_text))
    if not isinstance(refreshed, dict):
        return None

    updated_ocr = document.ocr_result.copy() if isinstance(document.ocr_result, dict) else {}
    corrected_fields = _get_corrected_field_names(updated_ocr)

    for field_name in PURCHASE_CONTRACT_EXTRACTED_FIELDS:
        if field_name in corrected_fields:
            continue
        updated_ocr[field_name] = refreshed.get(field_name)

    refreshed_field_confidence = refreshed.get("field_confidence")
    existing_field_confidence = (
        updated_ocr.get("field_confidence")
        if isinstance(updated_ocr.get("field_confidence"), dict)
        else {}
    )
    if isinstance(refreshed_field_confidence, dict):
        merged_field_confidence = dict(existing_field_confidence)
        for field_name, confidence in refreshed_field_confidence.items():
            if field_name in corrected_fields:
                continue
            merged_field_confidence[field_name] = confidence
        updated_ocr["field_confidence"] = merged_field_confidence

    if "confidence" not in corrected_fields and refreshed.get("confidence") is not None:
        updated_ocr["confidence"] = refreshed["confidence"]

    return updated_ocr


def _enforce_contract_role_gate(db, document, expected_role: str, flow_label: str) -> None:
    from app.models.document import DocumentType as DBDocumentType
    from app.services.contract_role_service import get_sensitive_document_mode

    if get_sensitive_document_mode() != "strict":
        return

    if getattr(document, "document_type", None) not in {
        DBDocumentType.RENTAL_CONTRACT,
        DBDocumentType.PURCHASE_CONTRACT,
        DBDocumentType.LOAN_CONTRACT,
        DBDocumentType.VERSICHERUNGSBESTAETIGUNG,
    }:
        return

    resolution = _resolve_contract_role_for_document(
        db,
        document,
        purchase_contract_kind=(document.ocr_result or {}).get("purchase_contract_kind")
        if getattr(document, "document_type", None) == DBDocumentType.PURCHASE_CONTRACT
        else None,
        raw_text=document.raw_text,
    )
    current_role = resolution.candidate if resolution else (document.ocr_result or {}).get(
        "user_contract_role",
        "unknown",
    )
    if current_role != expected_role:
        raise ValueError(
            f"{flow_label} is blocked because this contract currently resolves to "
            f"'{current_role or 'unknown'}' instead of '{expected_role}'."
        )


def _build_asset_normalized_document(
    db,
    document,
    result=None,
    *,
    extracted_overrides: dict | None = None,
):
    """Build the single normalized asset-path input from persisted OCR + profile state."""
    from app.services.document_normalization_service import DocumentNormalizationService

    ocr_data = document.ocr_result or {}
    if not isinstance(ocr_data, dict):
        return None, None

    merged_ocr_data = ocr_data.copy()
    for key, value in (extracted_overrides or {}).items():
        if value is not None:
            merged_ocr_data[key] = value

    amount = _to_decimal(merged_ocr_data.get("purchase_price") or merged_ocr_data.get("amount"))
    if amount is None or amount <= 0:
        return None, None

    user, profile_context = _get_user_and_tax_profile_context(db, document.user_id)
    if not user or not profile_context:
        return None, None

    line_items = merged_ocr_data.get("line_items") or merged_ocr_data.get("items") or []
    default_business_use = _to_decimal(merged_ocr_data.get("business_use_percentage")) or Decimal("100")
    purchase_or_invoice_date = _parse_ocr_date(
        merged_ocr_data.get("purchase_date") or merged_ocr_data.get("date")
    )
    payment_date = _parse_ocr_date(merged_ocr_data.get("payment_date")) or purchase_or_invoice_date

    prior_owner_usage_years = _to_decimal(merged_ocr_data.get("prior_owner_usage_years"))
    first_registration_date = _parse_ocr_date(merged_ocr_data.get("first_registration_date"))
    if (
        prior_owner_usage_years is None
        and first_registration_date is not None
        and purchase_or_invoice_date is not None
        and purchase_or_invoice_date > first_registration_date
    ):
        prior_owner_usage_years = Decimal(str(
            round((purchase_or_invoice_date - first_registration_date).days / 365.25, 2)
        ))

    raw_text = (
        document.raw_text
        or getattr(result, "raw_text", None)
        or " ".join(
            str(merged_ocr_data.get(key) or "")
            for key in (
                "asset_name",
                "asset_type",
                "vehicle_identification_number",
                "license_plate",
                "seller_name",
                "buyer_name",
            )
        ).strip()
    )

    normalized_document = DocumentNormalizationService().normalize_asset_document(
        document=document,
        extracted_data=merged_ocr_data,
        raw_text=raw_text,
        ocr_confidence=(
            _resolve_result_confidence(document, result)
            if result is not None
            else _to_decimal(getattr(document, "confidence_score", None))
        ),
        tax_profile_completeness=profile_context.completeness,
        profile_inputs_used=_profile_inputs_used_payload(profile_context),
        vat_status=profile_context.resolved_vat_status,
        gewinnermittlungsart=profile_context.resolved_gewinnermittlungsart,
        business_type=getattr(user, "business_type", None) or "unknown",
        industry_code=getattr(user, "business_industry", None),
        extracted_amount=amount,
        extracted_net_amount=_to_decimal(merged_ocr_data.get("net_amount")),
        extracted_vat_amount=_to_decimal(merged_ocr_data.get("vat_amount")),
        extracted_date=purchase_or_invoice_date,
        extracted_vendor=merged_ocr_data.get("supplier") or merged_ocr_data.get("merchant"),
        extracted_invoice_number=_extract_invoice_number(merged_ocr_data),
        extracted_line_items=line_items if isinstance(line_items, list) else [],
        default_business_use_percentage=default_business_use,
        duplicate_document_candidates=_build_duplicate_document_candidates(db, document),
        duplicate_asset_candidates=_build_duplicate_asset_candidates(db, document),
        put_into_use_date=_parse_ocr_date(merged_ocr_data.get("put_into_use_date")),
        payment_date=payment_date,
        business_use_percentage=default_business_use,
        is_used_asset=merged_ocr_data.get("is_used_asset"),
        first_registration_date=first_registration_date,
        prior_owner_usage_years=prior_owner_usage_years,
        gwg_elected=merged_ocr_data.get("gwg_elected"),
        depreciation_method=merged_ocr_data.get("depreciation_method"),
        degressive_afa_rate=_to_decimal(merged_ocr_data.get("degressive_afa_rate")),
    )
    return normalized_document, profile_context


def _build_asset_recognition_input(db, document, result):
    """Build recognition input from the normalized asset-path document contract."""
    from app.schemas.asset_recognition import AssetRecognitionInput

    normalized_document, _ = _build_asset_normalized_document(db, document, result)
    if normalized_document is None:
        return None
    return AssetRecognitionInput.from_normalized_document(normalized_document)


def _build_asset_suggestion(db, document, result) -> dict:
    """
    Build asset recognition metadata and, when appropriate, a create_asset suggestion.

    This is additive: the document can still auto-create transactions while also
    surfacing an asset suggestion for later confirmation.
    """
    from sqlalchemy.orm.attributes import flag_modified

    from app.schemas.asset_recognition import (
        AssetOutcomeSource,
        AssetOutcomeStatus,
        AssetRecognitionDecision,
    )
    from app.services.asset_recognition_service import AssetRecognitionService
    from app.services.document_quality_gate_service import (
        DocumentQualityGateService,
        QualityGateDecision,
    )

    from app.schemas.asset_recognition import AssetRecognitionInput

    from app.models.document import DocumentType as DBDocumentType

    updated_ocr = document.ocr_result.copy() if isinstance(document.ocr_result, dict) else {}
    role_resolution = None
    if document.document_type == DBDocumentType.PURCHASE_CONTRACT:
        role_resolution = _resolve_contract_role_for_document(
            db,
            document,
            updated_ocr,
            purchase_contract_kind=updated_ocr.get("purchase_contract_kind") or "asset",
        )
        _apply_contract_role_resolution(updated_ocr, role_resolution)

    normalized_document, profile_context = _build_asset_normalized_document(db, document, result)
    if normalized_document is None or not profile_context:
        updated_ocr.pop("asset_recognition", None)
        updated_ocr.pop("asset_quality_gate", None)
        updated_ocr.pop("asset_outcome", None)
        _clear_asset_import_suggestion(updated_ocr)
        document.ocr_result = _make_json_safe(updated_ocr)
        flag_modified(document, "ocr_result")
        db.flush()
        return {
            "asset_recognition": None,
            "asset_outcome": None,
            "import_suggestion": None,
            "auto_create_payload": None,
        }

    recognition_input = AssetRecognitionInput.from_normalized_document(normalized_document)

    recognition_result = AssetRecognitionService().recognize(recognition_input)
    quality_gate = DocumentQualityGateService().evaluate_asset_decision(
        normalized_document,
        recognition_result,
    )
    decision_audit = _build_asset_decision_audit(
        recognition_input,
        recognition_result,
        profile_context,
        quality_gate.policy_outcome,
    )
    recognition_result = recognition_result.model_copy(
        update={"decision_audit": decision_audit}
    )
    recognition_payload = _serialize_asset_recognition_result(recognition_result)
    updated_ocr["asset_recognition"] = recognition_payload
    updated_ocr["asset_quality_gate"] = _make_json_safe(quality_gate.model_dump(mode="json"))

    suggestion = None
    auto_create_payload = None
    asset_outcome = updated_ocr.get("asset_outcome")
    existing_import_suggestion = updated_ocr.get("import_suggestion")
    if recognition_result.decision in (
        AssetRecognitionDecision.GWG_SUGGESTION,
        AssetRecognitionDecision.CREATE_ASSET_SUGGESTION,
        AssetRecognitionDecision.CREATE_ASSET_AUTO,
    ):
        asset_candidate = recognition_result.asset_candidate
        tax_flags = recognition_result.tax_flags
        purchase_date = (
            recognition_input.extracted_date.isoformat()
            if recognition_input.extracted_date
            else None
        )
        put_into_use_date = (
            recognition_input.put_into_use_date.isoformat()
            if recognition_input.put_into_use_date
            else None
        )
        suggestion = {
            "type": "create_asset",
            "status": "pending",
            "data": {
                "asset_type": asset_candidate.asset_type or "other_equipment",
                "sub_category": asset_candidate.asset_subtype,
                "name": asset_candidate.asset_name or "Unknown Asset",
                "purchase_date": purchase_date,
                "put_into_use_date": put_into_use_date,
                "purchase_price": float(tax_flags.comparison_amount),
                "supplier": asset_candidate.vendor_name,
                "is_used_asset": asset_candidate.is_used_asset,
                "business_use_percentage": float(
                    recognition_input.business_use_percentage
                    or recognition_input.default_business_use_percentage
                    or Decimal("100")
                ),
                "useful_life_years": (
                    int(tax_flags.suggested_useful_life_years)
                    if tax_flags.suggested_useful_life_years is not None
                    else None
                ),
                "comparison_basis": tax_flags.comparison_basis,
                "depreciable": tax_flags.depreciable,
                "gwg_eligible": tax_flags.gwg_eligible,
                "gwg_default_selected": tax_flags.gwg_default_selected,
                "gwg_election_required": tax_flags.gwg_election_required,
                "decision": (
                    recognition_result.decision
                    if recognition_result.decision == AssetRecognitionDecision.GWG_SUGGESTION
                    or quality_gate.decision == QualityGateDecision.AUTO_CREATE
                    else AssetRecognitionDecision.CREATE_ASSET_SUGGESTION
                ),
                "recognition_decision": recognition_result.decision,
                "quality_gate_decision": quality_gate.decision,
                "quality_gate_blocks_side_effects": quality_gate.blocks_side_effects,
                "vat_recoverable_status": tax_flags.vat_recoverable_status,
                "ifb_candidate": tax_flags.ifb_candidate,
                "ifb_rate": (
                    float(tax_flags.ifb_rate) if tax_flags.ifb_rate is not None else None
                ),
                "ifb_rate_source": tax_flags.ifb_rate_source,
                "ifb_exclusion_codes": tax_flags.ifb_exclusion_codes,
                "allowed_depreciation_methods": tax_flags.allowed_depreciation_methods,
                "suggested_depreciation_method": tax_flags.suggested_depreciation_method,
                "degressive_max_rate": (
                    float(tax_flags.degressive_max_rate)
                    if tax_flags.degressive_max_rate is not None
                    else None
                ),
                "reason_codes": recognition_result.reason_codes,
                "review_reasons": recognition_result.review_reasons,
                "missing_fields": quality_gate.missing_fields,
                "requires_user_confirmation": quality_gate.requires_user_confirmation,
                "policy_confidence": float(recognition_result.policy_confidence),
                "policy_rule_ids": recognition_result.policy_rule_ids,
                "policy_anchor_date": (
                    tax_flags.policy_anchor_date.isoformat()
                    if tax_flags.policy_anchor_date
                    else None
                ),
                "gwg_threshold": (
                    float(tax_flags.gwg_threshold) if tax_flags.gwg_threshold is not None else None
                ),
                "useful_life_source": tax_flags.useful_life_source,
                "income_tax_cost_cap": (
                    float(tax_flags.income_tax_cost_cap)
                    if tax_flags.income_tax_cost_cap is not None
                    else None
                ),
                "income_tax_depreciable_base": (
                    float(tax_flags.income_tax_depreciable_base)
                    if tax_flags.income_tax_depreciable_base is not None
                    else None
                ),
                "vat_recoverable_reason_codes": tax_flags.vat_recoverable_reason_codes,
                "duplicate": recognition_result.duplicate.model_dump(mode="json"),
                "tax_profile_completeness": profile_context.completeness.model_dump(mode="json"),
                "decision_audit": decision_audit.model_dump(mode="json"),
            },
            "confidence": float(recognition_result.policy_confidence),
        }
        _annotate_contract_role_gate(suggestion["data"], role_resolution)
        role_gate_blocks = bool(role_resolution and role_resolution.strict_would_block)

        if role_gate_blocks and role_resolution.mode == "strict":
            _clear_asset_import_suggestion(updated_ocr)
            updated_ocr.pop("asset_outcome", None)
            suggestion = None
            auto_create_payload = None
        elif quality_gate.decision == QualityGateDecision.AUTO_CREATE and not (
            role_gate_blocks and role_resolution and role_resolution.mode == "shadow"
        ):
            _clear_asset_import_suggestion(updated_ocr)
            updated_ocr.pop("asset_outcome", None)
            auto_create_payload = suggestion
            suggestion = None
        elif (
            not existing_import_suggestion
            or existing_import_suggestion.get("type") == "create_asset"
        ):
            if role_gate_blocks and role_resolution and role_resolution.mode == "shadow":
                suggestion["data"]["decision"] = AssetRecognitionDecision.CREATE_ASSET_SUGGESTION
                suggestion["data"]["quality_gate_decision"] = QualityGateDecision.SUGGESTION_REQUIRED
                suggestion["data"]["quality_gate_blocks_side_effects"] = True
                suggestion["data"]["requires_user_confirmation"] = True
                suggestion["data"]["role_gate_shadow_downgrade"] = True
            updated_ocr["import_suggestion"] = suggestion
            asset_outcome = _build_asset_outcome_payload(
                status=AssetOutcomeStatus.PENDING_CONFIRMATION,
                decision=(
                    AssetRecognitionDecision.GWG_SUGGESTION
                    if recognition_result.decision == AssetRecognitionDecision.GWG_SUGGESTION
                    else AssetRecognitionDecision.CREATE_ASSET_SUGGESTION
                ),
                source=AssetOutcomeSource.QUALITY_GATE,
                quality_gate_decision=(
                    QualityGateDecision.SUGGESTION_REQUIRED
                    if role_gate_blocks and role_resolution and role_resolution.mode == "shadow"
                    else quality_gate.decision
                ),
            )
            updated_ocr["asset_outcome"] = asset_outcome
        else:
            suggestion = None

    document.ocr_result = _make_json_safe(updated_ocr)
    flag_modified(document, "ocr_result")
    db.flush()

    return {
        "asset_recognition": recognition_payload,
        "asset_outcome": asset_outcome,
        "import_suggestion": suggestion,
        "auto_create_payload": auto_create_payload,
    }


def refresh_contract_role_sensitive_suggestions(db, document) -> dict:
    """Rebuild sensitive-document suggestions and metadata after OCR corrections."""
    from app.models.document import DocumentType as DBDocumentType
    from sqlalchemy.orm.attributes import flag_modified

    result = SimpleNamespace(
        raw_text=document.raw_text,
        confidence_score=_to_decimal(getattr(document, "confidence_score", None)) or Decimal("0"),
    )

    if document.document_type == DBDocumentType.RENTAL_CONTRACT:
        return _build_mietvertrag_suggestion(db, document, result)

    if document.document_type == DBDocumentType.PURCHASE_CONTRACT:
        refreshed_ocr = _refresh_purchase_contract_extracted_data(document, result)
        if refreshed_ocr is not None:
            document.ocr_result = _make_json_safe(refreshed_ocr)
            flag_modified(document, "ocr_result")
            db.flush()
        purchase_result = _build_kaufvertrag_suggestion(db, document, result)
        if purchase_result.get("purchase_contract_kind") == "asset":
            asset_result = _build_asset_suggestion(db, document, result)
            purchase_result.update(asset_result)
        return purchase_result

    if document.document_type == DBDocumentType.LOAN_CONTRACT:
        return _build_kreditvertrag_suggestion(db, document, result)

    if document.document_type == DBDocumentType.VERSICHERUNGSBESTAETIGUNG:
        return _build_versicherung_suggestion(db, document, result)

    if document.document_type in {
        DBDocumentType.INVOICE,
        DBDocumentType.RECEIPT,
        DBDocumentType.BANK_STATEMENT,
    }:
        return _refresh_direction_sensitive_suggestions(db, document, result)

    return {}


def run_ocr_pipeline(document_id: int, db=None) -> Dict[str, Any]:
    """
    Process document through the AI-orchestrated auto pipeline.

    Zero-friction: the orchestrator auto-creates everything (transactions,
    properties, recurring income) for ALL document types. User sees results
    in dashboard, can edit/undo if needed.
    """
    from app.db.base import SessionLocal
    from app.services.document_pipeline_orchestrator import DocumentPipelineOrchestrator
    from app.models.document import Document

    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        orchestrator = DocumentPipelineOrchestrator(db)
        pipeline_result = orchestrator.process_document(document_id)

        if pipeline_result.error:
            logger.error(
                f"Pipeline error for document {document_id}: {pipeline_result.error}"
            )
            # Mark document as processed so frontend stops polling
            try:
                document = db.query(Document).filter(Document.id == document_id).first()
                if document and not document.processed_at:
                    document.processed_at = datetime.utcnow()
                    document.confidence_score = 0.0
                    db.commit()
            except Exception:
                pass

        # Everything is auto-created by the orchestrator already.
        # Just return the result for the frontend to display.
        result_dict = pipeline_result.to_dict()

        # Add convenience fields for frontend
        auto_created = [s for s in pipeline_result.suggestions if s.get("status") == "auto-created"]
        result_dict["auto_created_count"] = len(auto_created)
        result_dict["transaction_created"] = any(s.get("transaction_id") for s in auto_created)

        return result_dict

    except Exception as e:
        db.rollback()
        logger.error(f"Pipeline failed for document {document_id}: {e}")
        # Mark document as processed even on failure
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document and not document.processed_at:
                document.processed_at = datetime.utcnow()
                document.confidence_score = 0.0
                db.commit()
        except Exception:
            pass
        # Refund credits for failed OCR processing
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                credit_svc = CreditService(db, redis_client=None)
                credit_svc.refund_credits(
                    user_id=document.user_id,
                    operation="ocr_scan",
                    reason="ocr_processing_failed",
                    context_type="document",
                    context_id=document_id,
                    refund_key=f"refund:ocr:{document_id}",
                )
                db.commit()
                logger.info(f"Refunded OCR credits for failed document {document_id}")
        except Exception as refund_err:
            logger.warning(f"Credit refund failed for document {document_id}: {refund_err}")
        raise
    finally:
        if own_session:
            db.close()


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
        pipeline_state = {}
        if isinstance(document.ocr_result, dict):
            pipeline_state = document.ocr_result.get("_pipeline") or {}
        vision_provider_preference = pipeline_state.get("ocr_provider_override")
        reprocess_mode = pipeline_state.get("reprocess_mode")
        # When reprocessing or when the document has no meaningful type yet,
        # do NOT lock the document type hint — the previous classification may
        # have been wrong (e.g. SVS classified as INVOICE because only page-1
        # text was available).  Let the VLM/classifier determine the type from
        # the full document content.  Also skip hint for OTHER (upload default).
        from app.models.document import DocumentType as DBDocumentType
        _skip_hint = (
            reprocess_mode
            or document.document_type is None
            or document.document_type == DBDocumentType.OTHER
        )
        doc_type_hint = None if _skip_hint else document.document_type
        result = ocr_engine.process_document(
            image_bytes,
            mime_type=document.mime_type,
            vision_provider_preference=vision_provider_preference,
            reprocess_mode=reprocess_mode,
            document_type_hint=doc_type_hint,
        )

        document.ocr_result = _make_json_safe(result.extracted_data)
        updated_pipeline_state = dict(pipeline_state)
        updated_pipeline_state["current_state"] = "completed"
        if reprocess_mode:
            updated_pipeline_state["last_reprocess_mode"] = reprocess_mode
        if getattr(result, "provider_used", None):
            updated_pipeline_state["last_provider_used"] = result.provider_used
        document.ocr_result["_pipeline"] = updated_pipeline_state
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
            OCRDocumentType.L1_FORM: DBDocumentType.L1_FORM,
            OCRDocumentType.L1K_BEILAGE: DBDocumentType.L1K_BEILAGE,
            OCRDocumentType.L1AB_BEILAGE: DBDocumentType.L1AB_BEILAGE,
            OCRDocumentType.E1A_BEILAGE: DBDocumentType.E1A_BEILAGE,
            OCRDocumentType.E1B_BEILAGE: DBDocumentType.E1B_BEILAGE,
            OCRDocumentType.E1KV_BEILAGE: DBDocumentType.E1KV_BEILAGE,
            OCRDocumentType.U1_FORM: DBDocumentType.U1_FORM,
            OCRDocumentType.U30_FORM: DBDocumentType.U30_FORM,
            OCRDocumentType.JAHRESABSCHLUSS: DBDocumentType.JAHRESABSCHLUSS,
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

        # Filename-based classification boost (also handles umlaut variants)
        fname_lower = (document.file_name or "").lower()
        from app.services.document_classifier import _normalize_umlauts
        fname_norm = _normalize_umlauts(fname_lower)
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
            elif any(kw in fname_lower or kw in fname_norm for kw in [
                "einkommensteuererkl", "einkommensteuererklaerung",
                "e1", "e1b", "e 1b", "l1k", "l 1k",
                "steuererklaerung", "arbeitnehmerveranlagung",
            ]):
                document.document_type = DBDocumentType.E1_FORM
            elif "bescheid" in fname_lower:
                document.document_type = DBDocumentType.EINKOMMENSTEUERBESCHEID

        document.processed_at = datetime.utcnow()
        from app.services.document_year_attribution import (
            materialize_document_temporal_metadata,
        )
        from sqlalchemy.orm.attributes import flag_modified

        materialize_document_temporal_metadata(document, document.ocr_result)
        flag_modified(document, "ocr_result")
        db.commit()

        logger.info(
            f"OCR processing completed for document {document_id} "
            f"(confidence: {result.confidence_score:.2f})"
        )

        # Build import suggestions based on document type
        result_dict = result.to_dict()

        if document.document_type == DBDocumentType.PURCHASE_CONTRACT:
            try:
                _clear_transaction_artifacts_on_document(document)
                kaufvertrag_result = _build_kaufvertrag_suggestion(db, document, result)
                result_dict.update(kaufvertrag_result)
                if kaufvertrag_result.get("purchase_contract_kind") == "asset":
                    result_dict.update(_build_asset_suggestion(db, document, result))
            except Exception as e:
                logger.warning(f"Build Kaufvertrag suggestion failed for document {document_id}: {e}")
                result_dict["import_suggestion"] = None

        elif document.document_type == DBDocumentType.RENTAL_CONTRACT:
            try:
                _clear_transaction_artifacts_on_document(document)
                result_dict.update(_build_mietvertrag_suggestion(db, document, result))
            except Exception as e:
                logger.warning(f"Build Mietvertrag suggestion failed for document {document_id}: {e}")
                result_dict["import_suggestion"] = None

        elif document.document_type == DBDocumentType.LOAN_CONTRACT:
            try:
                _clear_transaction_artifacts_on_document(document)
                result_dict.update(_build_kreditvertrag_suggestion(db, document, result))
                result_dict["transaction_created"] = False
                result_dict["transaction_id"] = None
                result_dict.pop("transaction_suggestion", None)
            except Exception as e:
                logger.warning(f"Build Kreditvertrag suggestion failed for document {document_id}: {e}")
                result_dict["import_suggestion"] = None

        elif document.document_type == DBDocumentType.VERSICHERUNGSBESTAETIGUNG:
            try:
                _clear_transaction_artifacts_on_document(document)
                result_dict.update(_build_versicherung_suggestion(db, document, result))
                result_dict["transaction_created"] = False
                result_dict["transaction_id"] = None
                result_dict.pop("transaction_suggestion", None)
            except Exception as e:
                logger.warning(f"Build Versicherung suggestion failed for document {document_id}: {e}")
                result_dict["import_suggestion"] = None

        elif document.document_type == DBDocumentType.BANK_STATEMENT:
            try:
                _clear_transaction_artifacts_on_document(document)
                result_dict.update(_update_direction_metadata_only(db, document, result))
                result_dict["transaction_created"] = False
                result_dict["transaction_id"] = None
                result_dict.pop("transaction_suggestion", None)
            except Exception as e:
                logger.warning(f"Bank statement direction refresh failed for document {document_id}: {e}")

        elif document.document_type in (DBDocumentType.E1_FORM, DBDocumentType.EINKOMMENSTEUERBESCHEID):
            # Summary / tax declaration documents — extract historical data, no transactions
            try:
                _clear_transaction_artifacts_on_document(document)
                raw_text = document.raw_text or ""
                historical_data = {}
                if document.document_type == DBDocumentType.E1_FORM and raw_text:
                    from app.services.e1_form_extractor import E1FormExtractor
                    ext = E1FormExtractor()
                    e1 = ext.extract(raw_text)
                    historical_data = ext.to_dict(e1)
                    historical_data["_source"] = "e1_form"
                elif document.document_type == DBDocumentType.EINKOMMENSTEUERBESCHEID and raw_text:
                    from app.services.bescheid_extractor import BescheidExtractor
                    ext = BescheidExtractor()
                    bd = ext.extract(raw_text)
                    historical_data = ext.to_dict(bd)
                    historical_data["_source"] = "bescheid"

                if historical_data:
                    import json as _json
                    updated_ocr = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
                    updated_ocr["historical_tax_data"] = historical_data
                    document.ocr_result = updated_ocr
                    db.commit()
                    logger.info(
                        f"Stored historical tax data for {document.document_type.value} "
                        f"document {document_id} (year={historical_data.get('tax_year')})"
                    )
                    result_dict["historical_tax_data"] = historical_data
            except Exception as hist_err:
                logger.warning(f"Historical extraction failed for doc {document_id}: {hist_err}")

        else:
            try:
                from app.services.ocr_transaction_service import OCRTransactionService
                ocr_transaction_service = OCRTransactionService(db)
                suggestions = ocr_transaction_service.create_split_suggestions(
                    document_id, document.user_id
                )
                if suggestions:
                    logger.info(
                        f"Created {len(suggestions)} transaction suggestion(s) for document {document_id}"
                    )
                    created_ids = []
                    duplicate_ids = []
                    for suggestion in suggestions:
                        try:
                            creation_result = ocr_transaction_service.create_transaction_from_suggestion_with_result(
                                suggestion, document.user_id
                            )
                            if creation_result.created:
                                created_ids.append(creation_result.transaction.id)
                                logger.info(
                                    f"Auto-created transaction {creation_result.transaction.id} from document "
                                    f"{document_id} (deductible={suggestion.get('is_deductible')})"
                                )
                            else:
                                duplicate_ids.append(creation_result.transaction.id)
                                logger.info(
                                    f"Skipped duplicate OCR transaction for document {document_id}; "
                                    f"existing transaction {creation_result.transaction.id} reused"
                                )
                        except Exception as e:
                            logger.warning(f"Could not auto-create transaction from document {document_id}: {e}")
                    result_dict["transaction_suggestion"] = suggestions[0]
                    result_dict["transaction_created"] = len(created_ids) > 0
                    result_dict["transaction_id"] = created_ids[0] if created_ids else None
                    if duplicate_ids:
                        result_dict["duplicate_transaction_ids"] = duplicate_ids
                    if len(created_ids) > 1:
                        result_dict["split_transaction_ids"] = created_ids

                    # Detect recurring expense patterns (insurance, subscriptions, etc.)
                    try:
                        recurring_suggestion = _detect_recurring_expense(
                            db, document, suggestions[0]
                        )
                        if recurring_suggestion:
                            result_dict["import_suggestion"] = recurring_suggestion
                    except Exception as rec_err:
                        logger.warning(
                            f"Recurring expense detection failed for doc {document_id}: {rec_err}"
                        )

                    # Persist tax_analysis into document.ocr_result so frontend can display it
                    try:
                        import json as _json
                        updated_ocr = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
                        tax_items = []
                        for s in suggestions:
                            tax_items.append({
                                "description": s.get("description", ""),
                                "amount": s.get("amount"),
                                "category": s.get("category"),
                                "is_deductible": s.get("is_deductible", False),
                                "deduction_reason": s.get("deduction_reason", ""),
                                "confidence": s.get("confidence", 0),
                                "transaction_type": s.get("transaction_type", "expense"),
                            })
                        updated_ocr["tax_analysis"] = {
                            "items": tax_items,
                            "is_split": len(suggestions) > 1,
                            "total_deductible": sum(
                                float(s.get("amount", 0)) for s in suggestions if s.get("is_deductible")
                            ),
                            "total_non_deductible": sum(
                                float(s.get("amount", 0)) for s in suggestions if not s.get("is_deductible")
                            ),
                        }
                        document.ocr_result = updated_ocr
                        db.commit()
                        logger.info(f"Stored tax_analysis for document {document_id}")
                    except Exception as tax_err:
                        logger.warning(f"Could not store tax_analysis for doc {document_id}: {tax_err}")

                try:
                    asset_suggestion = _build_asset_suggestion(db, document, result)
                    result_dict["asset_recognition"] = asset_suggestion.get("asset_recognition")
                    if asset_suggestion.get("asset_outcome"):
                        result_dict["asset_outcome"] = asset_suggestion["asset_outcome"]
                    if (
                        asset_suggestion.get("import_suggestion")
                        and not result_dict.get("import_suggestion")
                    ):
                        result_dict["import_suggestion"] = asset_suggestion["import_suggestion"]
                except Exception as asset_err:
                    logger.warning(
                        f"Asset suggestion detection failed for doc {document_id}: {asset_err}"
                    )
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
        # Refund credits for failed OCR processing
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                credit_svc = CreditService(db, redis_client=None)
                credit_svc.refund_credits(
                    user_id=document.user_id,
                    operation="ocr_scan",
                    reason="ocr_processing_failed",
                    context_type="document",
                    context_id=document_id,
                    refund_key=f"refund:ocr:{document_id}",
                )
                db.commit()
                logger.info(f"Refunded OCR credits for failed document {document_id}")
        except Exception as refund_err:
            logger.warning(f"Credit refund failed for document {document_id}: {refund_err}")
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
        return {"purchase_contract_kind": None, "import_suggestion": None}

    from app.services.purchase_contract_intelligence import (
        PurchaseContractKind,
        detect_purchase_contract_kind,
    )

    contract_kind = detect_purchase_contract_kind(
        document.raw_text or getattr(result, "raw_text", None) or "",
        extracted_data=ocr_data,
    )
    updated_ocr = document.ocr_result.copy() if isinstance(document.ocr_result, dict) else {}
    updated_ocr["purchase_contract_kind"] = contract_kind.value
    if contract_kind != PurchaseContractKind.PROPERTY:
        logger.info(
            f"Kaufvertrag doc {document.id}: detected asset-oriented contract, "
            "skipping property suggestion"
        )
        _clear_import_suggestion_types(updated_ocr, {"create_property", "associate_property"})
        document.ocr_result = updated_ocr
        db.flush()
        return {"purchase_contract_kind": contract_kind.value, "import_suggestion": None}

    role_resolution = _resolve_contract_role_for_document(
        db,
        document,
        updated_ocr,
        purchase_contract_kind=contract_kind.value,
    )
    _apply_contract_role_resolution(updated_ocr, role_resolution)

    purchase_price = ocr_data.get("purchase_price")
    property_address = ocr_data.get("property_address")

    if not purchase_price or not property_address:
        logger.info(
            f"Kaufvertrag doc {document.id}: missing purchase_price or address, "
            f"skipping suggestion"
        )
        _clear_import_suggestion_types(updated_ocr, {"create_property", "associate_property"})
        document.ocr_result = updated_ocr
        db.flush()
        return {"purchase_contract_kind": contract_kind.value, "import_suggestion": None}

    from decimal import Decimal
    from datetime import datetime as dt

    purchase_price_dec = Decimal(str(purchase_price))
    address = str(property_address)
    street = str(ocr_data.get("street") or address)
    city = str(ocr_data.get("city") or "Unbekannt")
    postal_code = str(ocr_data.get("postal_code") or "0000")

    # purchase_date: try OCR field, then 'date' field, fallback to upload date
    pd_raw = ocr_data.get("purchase_date") or ocr_data.get("date")
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
                purchase_date = None  # Don't silently use upload date
        else:
            purchase_date = pd_raw.isoformat() if hasattr(pd_raw, "isoformat") else str(pd_raw)
    else:
        purchase_date = None  # Will be shown as missing in suggestion card

    building_value = (
        float(ocr_data["building_value"])
        if ocr_data.get("building_value")
        else float((purchase_price_dec * Decimal("0.8")).quantize(Decimal("0.01")))
    )
    land_value = float(purchase_price_dec) - building_value

    # Check for upload context with property_id (from PropertyDetailPage navigation)
    upload_context = ocr_data.get("_upload_context", {}) or {}
    context_property_id = upload_context.get("property_id")

    # If upload context has property_id, associate Kaufvertrag to existing property
    existing_property_id = None
    existing_property_address = None
    address_mismatch_warning = False

    if context_property_id:
        try:
            from app.models.property import Property as PropertyModel, PropertyStatus
            context_prop = (
                db.query(PropertyModel)
                .filter(
                    PropertyModel.id == context_property_id,
                    PropertyModel.user_id == document.user_id,
                    PropertyModel.status == PropertyStatus.ACTIVE,
                )
                .first()
            )
            if context_prop:
                existing_property_id = str(context_prop.id)
                existing_property_address = context_prop.address
                # Check if OCR address matches the target property address
                if address and existing_property_address:
                    ocr_addr_norm = address.strip().lower()
                    prop_addr_norm = existing_property_address.strip().lower()
                    if (
                        ocr_addr_norm
                        and prop_addr_norm
                        and ocr_addr_norm not in prop_addr_norm
                        and prop_addr_norm not in ocr_addr_norm
                    ):
                        address_mismatch_warning = True
                        logger.warning(
                            f"Kaufvertrag doc {document.id}: OCR address '{address}' "
                            f"does not match target property address "
                            f"'{existing_property_address}'"
                        )
            else:
                logger.warning(
                    f"Kaufvertrag doc {document.id}: context property_id "
                    f"{context_property_id} not found or not active"
                )
        except Exception as e:
            logger.warning(
                f"Context property lookup failed for Kaufvertrag doc {document.id}: {e}"
            )

    suggestion_type = (
        "associate_property" if existing_property_id else "create_property"
    )

    suggestion = {
        "type": suggestion_type,
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
            "existing_property_id": existing_property_id,
            "existing_property_address": existing_property_address,
            "address_mismatch_warning": address_mismatch_warning,
        },
    }
    _annotate_contract_role_gate(suggestion["data"], role_resolution)

    if role_resolution and role_resolution.strict_would_block and role_resolution.mode == "strict":
        logger.info(
            f"Kaufvertrag doc {document.id}: role '{role_resolution.candidate}' blocks "
            "property suggestion in strict mode"
        )
        _clear_import_suggestion_types(updated_ocr, {"create_property", "associate_property"})
        document.ocr_result = updated_ocr
        db.flush()
        return {"purchase_contract_kind": contract_kind.value, "import_suggestion": None}

    logger.info(
        f"Built property suggestion for Kaufvertrag doc {document.id}: "
        f"address={address}, price={purchase_price}"
    )

    # Save suggestion into document's ocr_result
    updated_ocr["import_suggestion"] = suggestion
    document.ocr_result = updated_ocr
    db.flush()

    return {"purchase_contract_kind": PurchaseContractKind.PROPERTY.value, "import_suggestion": suggestion}


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

    _enforce_contract_role_gate(db, document, expected_role="buyer", flow_label="Property creation")

    # Same-document dedup: if a property was already created from this document, return it
    from app.models.property import Property as _PropModel
    existing_from_doc = (
        db.query(_PropModel)
        .filter(_PropModel.kaufvertrag_document_id == int(document.id))
        .first()
    )
    if existing_from_doc:
        logger.info(
            "Property %s already created from document %s — skipping duplicate creation",
            existing_from_doc.id, document.id,
        )
        # Mark suggestion as confirmed so batch reprocess-all won't re-queue
        import json as _json_kauf
        _ocr = _json_kauf.loads(_json_kauf.dumps(document.ocr_result)) if document.ocr_result else {}
        if _ocr.get("import_suggestion"):
            _ocr["import_suggestion"]["status"] = "confirmed"
            _ocr["import_suggestion"]["property_id"] = str(existing_from_doc.id)
            document.ocr_result = _ocr
            db.commit()
        return {"property_id": str(existing_from_doc.id), "reused": True}

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

    # Check if there are existing rental contracts for this address
    # If no rental contracts → owner_occupied; otherwise → rental/mixed_use
    from app.models.recurring_transaction import (
        RecurringTransaction,
        RecurringTransactionType,
    )
    from app.models.property import Property as PropertyModel, PropertyStatus as PS

    # ── Check for existing placeholder property (auto-created from rental contract) ──
    # If a property exists at the same address with purchase_price<=0.01 (sentinel),
    # update it instead of creating a duplicate.
    # Uses fuzzy matching because OCR may produce slight spelling differences
    # (e.g. "Trenneberg" vs "Thenneberg").
    import re as _re
    from difflib import SequenceMatcher as _SM

    def _house_num(s: str) -> str:
        m = _re.search(r"(\d+\s*[a-zA-Z]?(?:/\d+)?)\s*$", s.strip())
        return m.group(1).strip() if m else ""

    existing_placeholder = None
    if street and street != "Unbekannt":
        candidates = (
            db.query(PropertyModel)
            .filter(
                PropertyModel.user_id == user_id,
                PropertyModel.status == PS.ACTIVE,
                PropertyModel.purchase_price <= Decimal("0.01"),
            )
            .all()
        )
        street_lower = street.lower().strip()
        addr_lower = address.lower().strip() if address else ""
        new_hnum = _house_num(street)
        best_score = 0.0
        best_candidate = None

        for c in candidates:
            c_street = (c.street or "").lower().strip()
            c_addr = (c.address or "").lower().strip()
            if not c_street:
                continue

            # 1) Exact / substring match (original logic)
            if c_street == street_lower or c_street in addr_lower or street_lower in c_addr:
                best_candidate = c
                best_score = 1.0
                break

            c_hnum = _house_num(c_street)

            # 2) Same postal_code + same house number → very strong signal
            if (
                postal_code and postal_code != "0000"
                and c.postal_code == postal_code
                and new_hnum and c_hnum and new_hnum == c_hnum
            ):
                if best_score < 0.95:
                    best_score = 0.95
                    best_candidate = c

            # 3) Same house number + fuzzy street name (OCR typos like Trenneberg/Thenneberg)
            if new_hnum and c_hnum and new_hnum == c_hnum:
                sim = _SM(None, c_street, street_lower).ratio()
                if sim >= 0.70 and sim > best_score:
                    best_score = sim
                    best_candidate = c

        if best_candidate:
            existing_placeholder = best_candidate
            logger.info(
                "Found placeholder property %s (street='%s') matching Kaufvertrag "
                "address '%s' (score=%.2f) — will update instead of creating new",
                best_candidate.id, best_candidate.street, street, best_score,
            )

    if existing_placeholder:
        # Update the placeholder with real Kaufvertrag data
        prop = existing_placeholder
        prop.street = street
        prop.city = city
        prop.postal_code = postal_code
        prop.address = f"{street}, {postal_code} {city}"
        prop.purchase_date = purchase_date
        prop.purchase_price = purchase_price
        if building_value is not None:
            prop.building_value = building_value
        else:
            prop.building_value = purchase_price * Decimal("0.80")
        prop.land_value = prop.purchase_price - prop.building_value
        if construction_year:
            prop.construction_year = construction_year
        if grunderwerbsteuer:
            prop.grunderwerbsteuer = grunderwerbsteuer
        if notary_fees:
            prop.notary_fees = notary_fees
        if registry_fees:
            prop.registry_fees = registry_fees
        # Recalculate depreciation rate based on construction year
        if construction_year and int(construction_year) >= 1915:
            prop.depreciation_rate = Decimal("0.015")
        else:
            prop.depreciation_rate = Decimal("0.02")
        prop.kaufvertrag_document_id = int(document.id)
        db.commit()
        db.refresh(prop)

        logger.info(
            f"Updated placeholder property {prop.id} with Kaufvertrag data from doc {document.id}"
        )

        # Recalculate rental percentage (rental contracts may already be linked)
        try:
            property_service = PropertyService(db)
            property_service.recalculate_rental_percentage(prop.id, user_id)
        except Exception as e:
            logger.warning(f"Failed to recalculate rental percentage after update: {e}")

        # Mark suggestion as confirmed
        import json as _json
        ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
        if ocr_result.get("import_suggestion"):
            ocr_result["import_suggestion"]["status"] = "confirmed"
            ocr_result["import_suggestion"]["property_id"] = str(prop.id)
            document.ocr_result = ocr_result
            db.commit()

        return {
            "property_created": True,
            "property_updated_placeholder": True,
            "property_id": str(prop.id),
            "address": prop.address,
            "purchase_price": float(prop.purchase_price),
        }

    # ── No placeholder found — create new property ──

    # Look for existing properties at similar address that have rental contracts
    existing_rentals = (
        db.query(RecurringTransaction)
        .join(PropertyModel, RecurringTransaction.property_id == PropertyModel.id)
        .filter(
            PropertyModel.user_id == user_id,
            RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
            RecurringTransaction.is_active == True,
        )
        .count()
    )

    # Default to owner_occupied — will be recalculated when rental contract is linked
    initial_type = PropertyType.OWNER_OCCUPIED
    initial_pct = Decimal("0.00")

    # Build PropertyCreate schema for validation
    property_data = PropertyCreate(
        property_type=initial_type,
        rental_percentage=initial_pct,
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

    updated_ocr = document.ocr_result.copy() if document.ocr_result else {}
    role_resolution = _resolve_contract_role_for_document(db, document, updated_ocr)
    _apply_contract_role_resolution(updated_ocr, role_resolution)

    monthly_rent = ocr_data.get("monthly_rent")
    if not monthly_rent:
        _clear_import_suggestion_types(updated_ocr, {"create_recurring_income"})
        document.ocr_result = updated_ocr
        db.flush()
        return {"import_suggestion": None}

    monthly_rent = Decimal(str(monthly_rent))
    address = ocr_data.get("property_address", "")

    # Check for upload context with property_id (from PropertyDetailPage navigation)
    upload_context = ocr_data.get("_upload_context", {}) or {}
    context_property_id = upload_context.get("property_id")

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

    # Try to match property — prefer upload_context.property_id over address matching
    matched_property_id = None
    matched_property_address = None
    address_mismatch_warning = False

    if context_property_id:
        # Direct property association from upload context (PropertyDetailPage navigation)
        try:
            from app.models.property import Property as PropertyModel, PropertyStatus
            context_prop = (
                db.query(PropertyModel)
                .filter(
                    PropertyModel.id == context_property_id,
                    PropertyModel.user_id == document.user_id,
                    PropertyModel.status == PropertyStatus.ACTIVE,
                )
                .first()
            )
            if context_prop:
                matched_property_id = str(context_prop.id)
                matched_property_address = context_prop.address
                # Check if OCR address matches the target property address
                if address and matched_property_address:
                    ocr_addr_norm = address.strip().lower()
                    prop_addr_norm = matched_property_address.strip().lower()
                    if ocr_addr_norm and prop_addr_norm and ocr_addr_norm not in prop_addr_norm and prop_addr_norm not in ocr_addr_norm:
                        address_mismatch_warning = True
                        logger.warning(
                            f"Mietvertrag doc {document.id}: OCR address '{address}' "
                            f"does not match target property address '{matched_property_address}'"
                        )
            else:
                logger.warning(
                    f"Mietvertrag doc {document.id}: context property_id {context_property_id} "
                    f"not found or not active, falling back to address matching"
                )
        except Exception as e:
            logger.warning(f"Context property lookup failed for Mietvertrag doc {document.id}: {e}")

    # Fallback to address matching if no context property_id or lookup failed
    if not matched_property_id and address:
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

    # Detect partial address match (e.g. "Thenneberg 51/3" vs property "Thenneberg 51")
    is_partial_match = False
    if matched_property_id and matched_property_address and address:
        r_norm = address.strip().lower()
        p_norm = matched_property_address.strip().lower().split(",")[0]
        if p_norm and r_norm.startswith(p_norm) and r_norm != p_norm:
            is_partial_match = True

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
            "no_property_match": matched_property_id is None,
            "is_partial_match": is_partial_match,
            "address_mismatch_warning": address_mismatch_warning,
        },
    }
    _annotate_contract_role_gate(suggestion["data"], role_resolution)

    if role_resolution and role_resolution.strict_would_block and role_resolution.mode == "strict":
        logger.info(
            f"Mietvertrag doc {document.id}: role '{role_resolution.candidate}' blocks "
            "recurring income suggestion in strict mode"
        )
        _clear_import_suggestion_types(updated_ocr, {"create_recurring_income"})
        document.ocr_result = updated_ocr
        db.flush()
        return {"import_suggestion": None}

    logger.info(
        f"Built recurring income suggestion for Mietvertrag doc {document.id}: "
        f"rent=€{monthly_rent}, property_match={matched_property_id}"
    )

    # Save suggestion into document's ocr_result
    updated_ocr["import_suggestion"] = suggestion
    document.ocr_result = updated_ocr
    db.flush()

    return {"import_suggestion": suggestion}

def _build_kreditvertrag_suggestion(db, document, result) -> dict:
    """
    Build a loan creation suggestion from Kreditvertrag OCR data.
    Does NOT create any records — only stores suggestion data for user confirmation.
    Returns dict with suggestion keys to merge into ocr_result.
    """
    from decimal import Decimal
    from datetime import datetime as dt
    from app.models.liability import LiabilitySourceType
    from app.models.property_loan import PropertyLoan

    updated_ocr = document.ocr_result.copy() if isinstance(document.ocr_result, dict) else {}
    updated_ocr = _clear_transaction_artifact_keys(updated_ocr)
    role_resolution = _resolve_contract_role_for_document(
        db,
        document,
        updated_ocr,
        raw_text=getattr(result, "raw_text", None) or document.raw_text,
    )
    _apply_contract_role_resolution(updated_ocr, role_resolution)

    existing_loan = (
        db.query(PropertyLoan)
        .filter(PropertyLoan.loan_contract_document_id == document.id)
        .first()
    )
    if existing_loan:
        logger.info(
            f"Kreditvertrag doc {document.id}: PropertyLoan {existing_loan.id} already exists, "
            f"returning existing suggestion as confirmed"
        )
        suggestion = {
            "type": "create_loan",
            "status": "confirmed",
            "data": {
                "loan_amount": float(existing_loan.loan_amount) if existing_loan.loan_amount else None,
                "interest_rate": float(existing_loan.interest_rate) if existing_loan.interest_rate else None,
                "monthly_payment": float(existing_loan.monthly_payment) if existing_loan.monthly_payment else None,
                "lender_name": existing_loan.lender_name,
                "start_date": existing_loan.start_date.isoformat() if existing_loan.start_date else None,
                "end_date": existing_loan.end_date.isoformat() if existing_loan.end_date else None,
                "matched_property_id": str(existing_loan.property_id) if existing_loan.property_id else None,
            },
            "loan_id": existing_loan.id,
        }
        _annotate_contract_role_gate(suggestion["data"], role_resolution)
        updated_ocr["import_suggestion"] = suggestion
        document.ocr_result = updated_ocr
        db.commit()
        return {"import_suggestion": suggestion}

    ocr_data = updated_ocr
    if not isinstance(ocr_data, dict):
        return {"import_suggestion": None}

    loan_amount = ocr_data.get("loan_amount")
    interest_rate = ocr_data.get("interest_rate")
    monthly_payment = ocr_data.get("monthly_payment")
    lender_name = ocr_data.get("lender_name")

    missing_fields = []
    if not loan_amount:
        missing_fields.append("loan_amount")
    if not interest_rate:
        missing_fields.append("interest_rate")

    sd_raw = ocr_data.get("start_date")
    start_date = None
    if sd_raw:
        if isinstance(sd_raw, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
                try:
                    start_date = dt.strptime(sd_raw, fmt).date()
                    break
                except ValueError:
                    continue
        else:
            start_date = sd_raw
    if not start_date:
        start_date = document.uploaded_at.date()

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

    property_address = ocr_data.get("property_address")
    upload_context = ocr_data.get("_upload_context", {}) or {}
    context_property_id = upload_context.get("property_id")

    matched_property_id, matched_property_address, address_mismatch_warning = _match_property_for_loan_contract(
        db,
        document,
        context_property_id=context_property_id,
        property_address=property_address,
    )

    if matched_property_id:
        updated_ocr["matched_property_id"] = matched_property_id
        updated_ocr["matched_property_address"] = matched_property_address

    # Missing critical fields should keep the suggestion visible, but make the
    # follow-up explicit so callers can render the correct "needs input" state.
    status = "needs_input" if missing_fields else "pending"
    suggestion_type = "create_loan" if matched_property_id else "create_loan_repayment"
    suggestion_data = {
        "loan_amount": float(Decimal(str(loan_amount))) if loan_amount else None,
        "interest_rate": float(Decimal(str(interest_rate))) if interest_rate else None,
        "monthly_payment": float(Decimal(str(monthly_payment))) if monthly_payment else None,
        "annual_interest_amount": (
            float(Decimal(str(ocr_data.get("annual_interest_amount"))))
            if ocr_data.get("annual_interest_amount")
            else None
        ),
        "certificate_year": ocr_data.get("certificate_year"),
        "lender_name": lender_name,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "matched_property_id": matched_property_id,
        "matched_property_address": matched_property_address,
        "property_address": property_address,
        "no_property_match": matched_property_id is None,
        "address_mismatch_warning": address_mismatch_warning,
    }
    if missing_fields:
        suggestion_data["missing_fields"] = missing_fields

    suggestion = {
        "type": suggestion_type,
        "status": status,
        "data": suggestion_data,
    }
    _annotate_contract_role_gate(suggestion["data"], role_resolution)

    if role_resolution and role_resolution.strict_would_block and role_resolution.mode == "strict":
        updated_ocr.pop("import_suggestion", None)
        document.ocr_result = updated_ocr
        db.commit()
        return {"import_suggestion": None}

    document_confidence = _to_decimal(getattr(result, "confidence_score", None)) or _to_decimal(
        getattr(document, "confidence_score", None)
    ) or Decimal("0")
    can_auto_create = (
        suggestion_type == "create_loan"
        and not missing_fields
        and bool(matched_property_id)
        and not address_mismatch_warning
        and document_confidence >= Decimal("0.90")
    )

    if can_auto_create:
        create_result = create_loan_from_suggestion(
            db,
            document,
            suggestion_data,
            liability_source_type=LiabilitySourceType.DOCUMENT_AUTO_CREATED,
        )
        refreshed_ocr = document.ocr_result if isinstance(document.ocr_result, dict) else {}
        auto_created_suggestion = refreshed_ocr.get("import_suggestion")
        if isinstance(auto_created_suggestion, dict):
            auto_created_suggestion["status"] = "confirmed"
            auto_created_suggestion["auto_created"] = True
            if isinstance(auto_created_suggestion.get("data"), dict):
                auto_created_suggestion["data"]["auto_created"] = True
                auto_created_suggestion["data"]["quality_gate_decision"] = "auto_create"
            document.ocr_result = refreshed_ocr
            db.commit()

        logger.info(
            f"Auto-created property-linked loan from Kreditvertrag doc {document.id} "
            f"(confidence={document_confidence}, property={matched_property_id})"
        )
        return {
            "import_suggestion": auto_created_suggestion,
            "loan_auto_created": True,
            **create_result,
        }

    logger.info(
        f"Built loan suggestion for Kreditvertrag doc {document.id}: "
        f"amount={loan_amount}, rate={interest_rate}, status={status}"
    )

    updated_ocr["import_suggestion"] = suggestion
    document.ocr_result = updated_ocr
    db.commit()

    return {"import_suggestion": suggestion}


def _match_property_for_loan_contract(
    db,
    document,
    *,
    context_property_id=None,
    property_address=None,
):
    """Resolve a property for a loan contract via upload context or OCR address."""
    matched_property_id = None
    matched_property_address = None
    address_mismatch_warning = False
    address = str(property_address or "").strip()

    if context_property_id:
        try:
            from app.models.property import Property as PropertyModel, PropertyStatus

            context_prop = (
                db.query(PropertyModel)
                .filter(
                    PropertyModel.id == context_property_id,
                    PropertyModel.user_id == document.user_id,
                    PropertyModel.status == PropertyStatus.ACTIVE,
                )
                .first()
            )
            if context_prop:
                matched_property_id = str(context_prop.id)
                matched_property_address = context_prop.address
                if address and matched_property_address:
                    ocr_addr_norm = address.lower()
                    prop_addr_norm = matched_property_address.strip().lower()
                    if (
                        ocr_addr_norm
                        and prop_addr_norm
                        and ocr_addr_norm not in prop_addr_norm
                        and prop_addr_norm not in ocr_addr_norm
                    ):
                        address_mismatch_warning = True
                        logger.warning(
                            f"Kreditvertrag doc {document.id}: OCR address '{address}' "
                            f"does not match target property address '{matched_property_address}'"
                        )
            else:
                logger.warning(
                    f"Kreditvertrag doc {document.id}: context property_id "
                    f"{context_property_id} not found or not active, falling back to address matching"
                )
        except Exception as e:
            logger.warning(
                f"Context property lookup failed for Kreditvertrag doc {document.id}: {e}"
            )

    if not matched_property_id and address:
        try:
            from app.models.property import Property as PropertyModel, PropertyStatus
            from app.services.address_matcher import AddressMatcher

            matcher = AddressMatcher(db)
            matches = matcher.match_address(address, document.user_id)
            if matches and matches[0].confidence > 0.3:
                matched_property_id = str(matches[0].property.id)
                matched_property_address = matches[0].property.address
            else:
                user_props = (
                    db.query(PropertyModel)
                    .filter(
                        PropertyModel.user_id == document.user_id,
                        PropertyModel.status == PropertyStatus.ACTIVE,
                    )
                    .all()
                )
                addr_lower = address.lower()
                for prop in user_props:
                    street = (prop.street or "").lower()
                    if street and street in addr_lower:
                        matched_property_id = str(prop.id)
                        matched_property_address = prop.address
                        break
        except Exception as e:
            logger.warning(f"Address matching failed for Kreditvertrag doc {document.id}: {e}")

    return matched_property_id, matched_property_address, address_mismatch_warning


def _resolve_standalone_liability_type(document):
    from app.models.user import UserType

    user_type = getattr(getattr(document, "user", None), "user_type", None)
    if user_type in {UserType.SELF_EMPLOYED, UserType.LANDLORD, UserType.MIXED, UserType.GMBH}:
        return "business_loan"
    return "other_liability"


def _merge_asset_confirmation_overrides(suggestion_data: dict, confirmation_overrides: dict | None) -> dict:
    """Merge allowed user confirmation overrides into suggestion data."""
    merged = dict(suggestion_data or {})
    if not confirmation_overrides:
        return merged

    allowed_fields = {
        "put_into_use_date",
        "business_use_percentage",
        "is_used_asset",
        "first_registration_date",
        "prior_owner_usage_years",
        "gwg_elected",
        "depreciation_method",
        "degressive_afa_rate",
        "useful_life_years",
    }

    for key in allowed_fields:
        if key in confirmation_overrides and confirmation_overrides[key] is not None:
            merged[key] = confirmation_overrides[key]

    return merged


def _build_asset_confirmation_input(db, document, suggestion_data: dict):
    """Rebuild recognition input solely from the normalized asset-path contract."""
    from app.schemas.asset_recognition import AssetRecognitionInput

    normalized_document, _ = _build_asset_normalized_document(
        db,
        document,
        extracted_overrides=suggestion_data,
    )
    if normalized_document is None:
        raise ValueError("Asset suggestion is missing a valid amount")
    return AssetRecognitionInput.from_normalized_document(normalized_document)


def _map_asset_transaction_category(asset_type: str | None, sub_category: str | None):
    """Map asset types to expense categories for linked acquisition records."""
    from app.models.transaction import ExpenseCategory

    normalized_asset_type = (asset_type or "").lower()
    normalized_sub_category = (sub_category or "").lower()

    if normalized_asset_type == "vehicle" or normalized_sub_category in {
        "pkw",
        "electric_pkw",
        "truck_van",
        "fiscal_truck",
        "motorcycle",
        "special_vehicle",
    }:
        return ExpenseCategory.VEHICLE

    if normalized_asset_type == "phone":
        return ExpenseCategory.TELECOM

    if normalized_asset_type == "software" or normalized_sub_category in {
        "perpetual_license",
    }:
        return ExpenseCategory.SOFTWARE

    return ExpenseCategory.EQUIPMENT


def _build_asset_acquisition_description(asset, supplier: str | None) -> str:
    """Build a stable description for the asset acquisition transaction."""
    asset_name = (getattr(asset, "name", None) or "").strip()
    supplier_name = (supplier or getattr(asset, "supplier", None) or "").strip()

    if asset_name and supplier_name and supplier_name.lower() not in asset_name.lower():
        return f"{asset_name} - {supplier_name}"[:500]
    if asset_name:
        return asset_name[:500]
    if supplier_name:
        return f"Asset acquisition - {supplier_name}"[:500]
    return f"Asset acquisition - {asset.id}"[:500]


def _build_asset_acquisition_reason(asset) -> str:
    """Explain why acquisition is tracked separately from the tax deduction path."""
    if getattr(asset, "gwg_elected", False):
        return "GWG election recorded on the asset; tax deduction is handled via the asset schedule."
    return "Capitalized asset acquisition; tax deduction is handled via depreciation (AfA), not as an immediate expense."


def _resolve_asset_vat_recoverable_ratio(
    asset,
    suggestion_data: dict,
    policy_evaluation=None,
) -> Decimal:
    """Resolve recoverable VAT ratio for canonical asset acquisition postings."""
    ratio = _to_decimal((suggestion_data or {}).get("vat_recoverable_ratio"))
    if ratio is None and policy_evaluation is not None:
        ratio = _to_decimal(
            getattr(getattr(policy_evaluation, "tax_flags", None), "vat_recoverable_ratio", None)
        )

    if ratio is None:
        status = getattr(asset, "vat_recoverable_status", None)
        status = getattr(status, "value", status)
        if status == "likely_yes":
            ratio = Decimal("1.0000")
        else:
            ratio = Decimal("0.0000")

    if ratio < Decimal("0"):
        ratio = Decimal("0.0000")
    if ratio > Decimal("1"):
        ratio = Decimal("1.0000")
    return ratio.quantize(Decimal("0.0001"))


def _build_asset_acquisition_line_items(
    asset,
    category,
    description: str,
    suggestion_data: dict,
    *,
    vat_amount: Decimal | None,
    vat_rate: Decimal | None,
    policy_evaluation=None,
) -> list[dict]:
    """Materialize canonical business/private/VAT posting lines for assets."""
    from app.models.transaction_line_item import (
        LineItemAllocationSource,
        LineItemPostingType,
    )
    from app.services.posting_line_utils import quantize_money

    gross_amount = quantize_money(getattr(asset, "purchase_price", None))
    business_pct = (
        _to_decimal(getattr(asset, "business_use_percentage", None))
        or _to_decimal((suggestion_data or {}).get("business_use_percentage"))
        or Decimal("100.00")
    )
    business_pct = min(max(business_pct, Decimal("0.00")), Decimal("100.00"))
    business_ratio = (business_pct / Decimal("100")).quantize(Decimal("0.0001"))

    business_cash = (gross_amount * business_ratio).quantize(Decimal("0.01"))
    private_cash = (gross_amount - business_cash).quantize(Decimal("0.01"))

    total_vat = quantize_money(vat_amount)
    business_vat = (total_vat * business_ratio).quantize(Decimal("0.01"))
    private_vat = (total_vat - business_vat).quantize(Decimal("0.01"))

    recoverable_ratio = _resolve_asset_vat_recoverable_ratio(
        asset,
        suggestion_data,
        policy_evaluation=policy_evaluation,
    )
    recoverable_vat = (business_vat * recoverable_ratio).quantize(Decimal("0.01"))
    if recoverable_vat > business_cash:
        recoverable_vat = business_cash

    business_amount = (business_cash - recoverable_vat).quantize(Decimal("0.01"))
    category_token = getattr(category, "value", category)

    line_items = []
    if business_cash > Decimal("0.00"):
        line_items.append(
            {
                "description": description,
                "amount": business_amount,
                "quantity": 1,
                "posting_type": LineItemPostingType.ASSET_ACQUISITION,
                "allocation_source": (
                    LineItemAllocationSource.VAT_POLICY
                    if recoverable_vat > Decimal("0.00")
                    else (
                        LineItemAllocationSource.MIXED_USE_RULE
                        if private_cash > Decimal("0.00")
                        else LineItemAllocationSource.MANUAL
                    )
                ),
                "category": category_token,
                "is_deductible": False,
                "vat_rate": vat_rate,
                "vat_amount": business_vat if total_vat > Decimal("0.00") else None,
                "vat_recoverable_amount": recoverable_vat,
                "sort_order": 0,
            }
        )

    if private_cash > Decimal("0.00"):
        line_items.append(
            {
                "description": f"{description} (private use)",
                "amount": private_cash,
                "quantity": 1,
                "posting_type": LineItemPostingType.PRIVATE_USE,
                "allocation_source": LineItemAllocationSource.MIXED_USE_RULE,
                "category": category_token,
                "is_deductible": False,
                "vat_rate": vat_rate,
                "vat_amount": private_vat if total_vat > Decimal("0.00") else None,
                "vat_recoverable_amount": Decimal("0.00"),
                "sort_order": 1,
            }
        )

    return line_items


def _ensure_asset_acquisition_transaction(
    db,
    document,
    asset,
    suggestion_data: dict,
    *,
    policy_evaluation=None,
):
    """
    Ensure the confirmed asset has exactly one linked acquisition transaction.

    The purchase transaction itself remains non-deductible because the tax
    effect is handled by GWG/AfA logic on the asset lifecycle.
    """
    from app.models.transaction import Transaction, TransactionType
    from app.services.posting_line_utils import (
        normalize_line_item_payloads,
        replace_transaction_line_items,
    )

    ocr_data = document.ocr_result if isinstance(document.ocr_result, dict) else {}
    supplier = (
        suggestion_data.get("supplier")
        or ocr_data.get("supplier")
        or ocr_data.get("merchant")
    )
    category = _map_asset_transaction_category(
        getattr(asset, "asset_type", None),
        getattr(asset, "sub_category", None),
    )
    description = _build_asset_acquisition_description(asset, supplier)
    deduction_reason = _build_asset_acquisition_reason(asset)
    confidence = (
        _to_decimal(suggestion_data.get("policy_confidence"))
        or _to_decimal(getattr(document, "confidence_score", None))
        or Decimal("0.95")
    )
    vat_amount = _to_decimal(ocr_data.get("vat_amount"))
    net_amount = _to_decimal(ocr_data.get("net_amount"))
    vat_rate = None
    if vat_amount is not None and net_amount and net_amount > 0:
        try:
            vat_rate = (vat_amount / net_amount).quantize(Decimal("0.0001"))
        except Exception:
            vat_rate = None

    existing_transaction = None
    if getattr(document, "transaction_id", None):
        existing_transaction = (
            db.query(Transaction)
            .filter(
                Transaction.id == document.transaction_id,
                Transaction.user_id == document.user_id,
            )
            .first()
        )

    if existing_transaction is None:
        existing_transaction = (
            db.query(Transaction)
            .filter(
                Transaction.document_id == document.id,
                Transaction.user_id == document.user_id,
            )
            .order_by(Transaction.created_at.asc())
            .first()
        )

    normalized_line_items = normalize_line_item_payloads(
        transaction_type=TransactionType.ASSET_ACQUISITION,
        transaction_amount=asset.purchase_price,
        description=description,
        expense_category=category,
        is_deductible=False,
        deduction_reason=deduction_reason,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        line_items=_build_asset_acquisition_line_items(
            asset,
            category,
            description,
            suggestion_data,
            vat_amount=vat_amount,
            vat_rate=vat_rate,
            policy_evaluation=policy_evaluation,
        ),
    )

    if existing_transaction:
        existing_transaction.property_id = asset.id
        existing_transaction.type = TransactionType.ASSET_ACQUISITION
        existing_transaction.income_category = None
        existing_transaction.expense_category = None
        existing_transaction.amount = asset.purchase_price
        existing_transaction.transaction_date = asset.purchase_date
        existing_transaction.description = description
        existing_transaction.is_deductible = False
        existing_transaction.deduction_reason = deduction_reason
        existing_transaction.vat_amount = vat_amount
        existing_transaction.vat_rate = vat_rate
        existing_transaction.document_id = document.id
        existing_transaction.is_system_generated = True
        existing_transaction.import_source = "asset_import"
        existing_transaction.classification_confidence = confidence
        existing_transaction.classification_method = "rule"
        existing_transaction.needs_review = False
        replace_transaction_line_items(db, existing_transaction, normalized_line_items)
        existing_transaction.is_deductible = False
        existing_transaction.deduction_reason = deduction_reason
        document.transaction_id = existing_transaction.id
        return existing_transaction, False

    transaction = Transaction(
        user_id=document.user_id,
        property_id=asset.id,
        type=TransactionType.ASSET_ACQUISITION,
        amount=asset.purchase_price,
        transaction_date=asset.purchase_date,
        description=description,
        expense_category=None,
        is_deductible=False,
        deduction_reason=deduction_reason,
        vat_amount=vat_amount,
        vat_rate=vat_rate,
        document_id=document.id,
        classification_confidence=confidence,
        classification_method="rule",
        needs_review=False,
        is_system_generated=True,
        import_source="asset_import",
    )
    db.add(transaction)
    db.flush()
    replace_transaction_line_items(db, transaction, normalized_line_items)
    transaction.is_deductible = False
    transaction.deduction_reason = deduction_reason
    document.transaction_id = transaction.id
    return transaction, True


def create_asset_from_suggestion(
    db,
    document,
    suggestion_data: dict,
    confirmation_overrides: dict | None = None,
    *,
    trigger_source: str = "user",
) -> dict:
    """
    Create a non-real-estate asset from a confirmed OCR suggestion.

    Also writes the initial policy snapshot and lifecycle events so the asset
    tax engine has a stable audit trail from day one.
    """
    from datetime import date as date_type

    from sqlalchemy.orm.attributes import flag_modified

    from app.models.asset_event import AssetEvent, AssetEventTriggerSource, AssetEventType
    from app.models.asset_policy_snapshot import AssetPolicySnapshot
    from app.schemas.asset_recognition import (
        AssetCandidate,
        AssetOutcomeSource,
        AssetOutcomeStatus,
        AssetRecognitionDecision,
        AssetReviewReason,
        DepreciationMethod,
        UsefulLifeSource,
    )
    from app.schemas.property import AssetCreate
    from app.services.asset_tax_policy_service import AssetTaxPolicyService
    from app.services.property_service import PropertyService
    from app.services.tax_profile_service import TaxProfileService

    _enforce_contract_role_gate(db, document, expected_role="buyer", flow_label="Asset creation")

    data = _merge_asset_confirmation_overrides(suggestion_data or {}, confirmation_overrides)
    user, _ = _get_user_and_tax_profile_context(db, document.user_id)
    if not user:
        raise ValueError(f"User with id {document.user_id} not found")
    TaxProfileService().require_complete_asset_profile(user)
    recognition_input = _build_asset_confirmation_input(db, document, data)

    candidate_subtype = data.get("sub_category")
    asset_candidate = AssetCandidate(
        asset_type=data.get("asset_type", "other_equipment"),
        asset_subtype=candidate_subtype,
        asset_name=data.get("name", "Unknown Asset"),
        vendor_name=data.get("supplier"),
        vehicle_category=(
            candidate_subtype
            if candidate_subtype in {"pkw", "electric_pkw", "truck_van", "fiscal_truck", "motorcycle", "special_vehicle"}
            else None
        ),
        is_used_asset=recognition_input.is_used_asset,
    )

    policy_evaluation = AssetTaxPolicyService().evaluate(recognition_input, asset_candidate)
    blocking_review_reasons = {
        AssetReviewReason.NON_DEPRECIABLE_OR_UNCLEAR.value,
        AssetReviewReason.THRESHOLD_BOUNDARY_AMBIGUOUS.value,
        AssetReviewReason.USED_VEHICLE_HISTORY_MISSING.value,
    }
    missing_fields = list(policy_evaluation.missing_fields)
    # put_into_use_date is deferrable — asset can be created first, user fills it later
    deferrable_fields = {"put_into_use_date"}
    blocking_missing = [f for f in missing_fields if f not in deferrable_fields]
    if blocking_missing:
        raise ValueError(
            f"Missing required asset confirmation fields: {', '.join(blocking_missing)}"
        )
    active_blockers = [reason for reason in policy_evaluation.review_reasons if reason in blocking_review_reasons]
    if active_blockers:
        raise ValueError(
            f"Asset suggestion still requires review: {', '.join(active_blockers)}"
        )

    purchase_date = _parse_ocr_date(data.get("purchase_date")) or date_type.today()
    put_into_use_date = recognition_input.put_into_use_date or purchase_date
    policy_anchor_date = policy_evaluation.tax_flags.policy_anchor_date or put_into_use_date or purchase_date

    if data.get("useful_life_years") is not None:
        useful_life_years = int(data.get("useful_life_years"))
        useful_life_source = UsefulLifeSource.USER_OVERRIDE
    elif policy_evaluation.tax_flags.suggested_useful_life_years is not None:
        useful_life_years = int(policy_evaluation.tax_flags.suggested_useful_life_years)
        useful_life_source = policy_evaluation.tax_flags.useful_life_source
    else:
        useful_life_years = None
        useful_life_source = policy_evaluation.tax_flags.useful_life_source

    allowed_methods = {
        getattr(method, "value", method) for method in policy_evaluation.tax_flags.allowed_depreciation_methods
    }
    selected_method = getattr(
        data.get("depreciation_method") or policy_evaluation.tax_flags.suggested_depreciation_method,
        "value",
        data.get("depreciation_method") or policy_evaluation.tax_flags.suggested_depreciation_method or DepreciationMethod.LINEAR,
    )
    if selected_method not in allowed_methods:
        raise ValueError(
            f"Depreciation method '{selected_method}' is not allowed for this asset. "
            f"Allowed: {sorted(allowed_methods)}"
        )

    degressive_rate = None
    if selected_method == DepreciationMethod.DEGRESSIVE.value:
        degressive_rate = (
            _to_decimal(data.get("degressive_afa_rate"))
            or policy_evaluation.tax_flags.degressive_max_rate
        )
        if degressive_rate is None:
            raise ValueError("degressive_afa_rate is required when depreciation_method is 'degressive'")
        max_rate = policy_evaluation.tax_flags.degressive_max_rate
        if max_rate is not None and degressive_rate > max_rate:
            raise ValueError(
                f"degressive_afa_rate cannot exceed {max_rate} for this asset"
            )

    gwg_elected = (
        bool(data.get("gwg_elected"))
        if data.get("gwg_elected") is not None
        else bool(policy_evaluation.tax_flags.gwg_default_selected)
    )
    if gwg_elected and not policy_evaluation.tax_flags.gwg_eligible:
        raise ValueError("GWG can only be elected when the asset is GWG-eligible")

    asset_data = AssetCreate(
        asset_type=data.get("asset_type", "other_equipment"),
        sub_category=data.get("sub_category"),
        name=data.get("name", "Unknown Asset"),
        purchase_date=purchase_date,
        purchase_price=Decimal(str(data.get("purchase_price", 0))),
        supplier=data.get("supplier"),
        business_use_percentage=recognition_input.business_use_percentage or Decimal("100"),
        useful_life_years=useful_life_years,
        document_id=document.id,
        acquisition_kind="used_asset" if recognition_input.is_used_asset else data.get("acquisition_kind", "purchase"),
        put_into_use_date=put_into_use_date,
        is_used_asset=bool(recognition_input.is_used_asset),
        first_registration_date=recognition_input.first_registration_date,
        prior_owner_usage_years=recognition_input.prior_owner_usage_years,
        comparison_basis=policy_evaluation.tax_flags.comparison_basis,
        comparison_amount=policy_evaluation.tax_flags.comparison_amount,
        gwg_eligible=policy_evaluation.tax_flags.gwg_eligible,
        gwg_elected=gwg_elected,
        depreciation_method=selected_method,
        degressive_afa_rate=degressive_rate,
        useful_life_source=useful_life_source,
        income_tax_cost_cap=policy_evaluation.tax_flags.income_tax_cost_cap,
        income_tax_depreciable_base=policy_evaluation.tax_flags.income_tax_depreciable_base,
        vat_recoverable_status=policy_evaluation.tax_flags.vat_recoverable_status,
        ifb_candidate=policy_evaluation.tax_flags.ifb_candidate,
        ifb_rate=policy_evaluation.tax_flags.ifb_rate,
        ifb_rate_source=policy_evaluation.tax_flags.ifb_rate_source,
        recognition_decision=(
            AssetRecognitionDecision.GWG_SUGGESTION
            if gwg_elected
            else data.get("decision", AssetRecognitionDecision.CREATE_ASSET_SUGGESTION)
        ),
        policy_confidence=_to_decimal(data.get("policy_confidence")),
    )

    service = PropertyService(db)
    asset = service.create_asset(document.user_id, asset_data)

    snapshot = AssetPolicySnapshot(
        user_id=document.user_id,
        property_id=asset.id,
        effective_anchor_date=policy_anchor_date,
        snapshot_payload=_make_json_safe({
            "decision": getattr(asset_data.recognition_decision, "value", asset_data.recognition_decision),
            "comparison_basis": getattr(asset_data.comparison_basis, "value", asset_data.comparison_basis),
            "comparison_amount": float(policy_evaluation.tax_flags.comparison_amount),
            "vat_recoverable_status": getattr(asset_data.vat_recoverable_status, "value", asset_data.vat_recoverable_status),
            "ifb_candidate": policy_evaluation.tax_flags.ifb_candidate,
            "ifb_rate": float(policy_evaluation.tax_flags.ifb_rate) if policy_evaluation.tax_flags.ifb_rate is not None else None,
            "ifb_rate_source": getattr(asset_data.ifb_rate_source, "value", asset_data.ifb_rate_source),
            "ifb_exclusion_codes": [getattr(code, "value", code) for code in policy_evaluation.tax_flags.ifb_exclusion_codes],
            "allowed_depreciation_methods": [getattr(method, "value", method) for method in policy_evaluation.tax_flags.allowed_depreciation_methods],
            "selected_depreciation_method": selected_method,
            "degressive_max_rate": (
                float(policy_evaluation.tax_flags.degressive_max_rate)
                if policy_evaluation.tax_flags.degressive_max_rate is not None
                else None
            ),
            "degressive_afa_rate": float(degressive_rate) if degressive_rate is not None else None,
            "gwg_threshold": float(policy_evaluation.tax_flags.gwg_threshold) if policy_evaluation.tax_flags.gwg_threshold is not None else None,
            "gwg_eligible": policy_evaluation.tax_flags.gwg_eligible,
            "gwg_elected": gwg_elected,
            "useful_life_years": useful_life_years,
            "useful_life_source": getattr(useful_life_source, "value", useful_life_source),
            "income_tax_cost_cap": (
                float(policy_evaluation.tax_flags.income_tax_cost_cap)
                if policy_evaluation.tax_flags.income_tax_cost_cap is not None
                else None
            ),
            "income_tax_depreciable_base": (
                float(policy_evaluation.tax_flags.income_tax_depreciable_base)
                if policy_evaluation.tax_flags.income_tax_depreciable_base is not None
                else None
            ),
            "vat_recoverable_reason_codes": [
                getattr(code, "value", code) for code in policy_evaluation.tax_flags.vat_recoverable_reason_codes
            ],
            "reason_codes": [getattr(code, "value", code) for code in policy_evaluation.reason_codes],
            "review_reasons": [getattr(reason, "value", reason) for reason in policy_evaluation.review_reasons],
            "missing_fields": policy_evaluation.missing_fields,
            "policy_confidence": data.get("policy_confidence"),
            "source_document_id": document.id,
            "user_confirmation_overrides": confirmation_overrides or {},
            "decision_audit": data.get("decision_audit"),
        }),
        rule_ids=list(dict.fromkeys((data.get("policy_rule_ids", []) or []) + (policy_evaluation.rule_ids or []))),
    )
    db.add(snapshot)

    source = AssetEventTriggerSource.USER
    if trigger_source == "system":
        source = AssetEventTriggerSource.SYSTEM
    elif trigger_source == "import":
        source = AssetEventTriggerSource.IMPORT
    elif trigger_source == "policy_recompute":
        source = AssetEventTriggerSource.POLICY_RECOMPUTE

    db.add(
        AssetEvent(
            user_id=document.user_id,
            property_id=asset.id,
            event_type=AssetEventType.ACQUIRED,
            trigger_source=source,
            event_date=purchase_date,
            payload={
                "source_document_id": document.id,
                "purchase_price": float(asset_data.purchase_price),
                "asset_type": asset_data.asset_type,
                "sub_category": asset_data.sub_category,
                "comparison_amount": float(policy_evaluation.tax_flags.comparison_amount),
                "business_use_percentage": float(asset_data.business_use_percentage),
            },
        )
    )
    if put_into_use_date:
        db.add(
            AssetEvent(
                user_id=document.user_id,
                property_id=asset.id,
                event_type=AssetEventType.PUT_INTO_USE,
                trigger_source=source,
                event_date=put_into_use_date,
                payload={"put_into_use_date": put_into_use_date.isoformat()},
            )
        )

    acquisition_transaction, transaction_created = _ensure_asset_acquisition_transaction(
        db,
        document,
        asset,
        data,
        policy_evaluation=policy_evaluation,
    )

    import json as _json

    ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
    _clear_asset_import_suggestion(ocr_result)
    outcome_decision = (
        data.get("recognition_decision")
        or data.get("decision")
        or (
            AssetRecognitionDecision.CREATE_ASSET_AUTO
            if trigger_source == "system"
            else AssetRecognitionDecision.CREATE_ASSET_SUGGESTION
        )
    )
    ocr_result["asset_outcome"] = _build_asset_outcome_payload(
        status=(
            AssetOutcomeStatus.AUTO_CREATED
            if trigger_source == "system"
            else AssetOutcomeStatus.CONFIRMED
        ),
        decision=outcome_decision,
        source=(
            AssetOutcomeSource.QUALITY_GATE
            if trigger_source == "system"
            else AssetOutcomeSource.USER_CONFIRMATION
        ),
        asset_id=str(asset.id),
        quality_gate_decision=data.get("quality_gate_decision"),
    )
    document.ocr_result = _make_json_safe(ocr_result)
    flag_modified(document, "ocr_result")

    db.commit()
    service._invalidate_metrics_cache(asset.id)
    service._invalidate_portfolio_cache(document.user_id)

    return {
        "asset_id": str(asset.id),
        "asset_type": asset_data.asset_type,
        "name": asset_data.name,
        "purchase_price": float(asset_data.purchase_price),
        "useful_life_years": asset.useful_life_years,
        "depreciation_rate": float(asset.depreciation_rate),
        "depreciation_method": asset.depreciation_method,
        "gwg_elected": asset.gwg_elected,
        "policy_snapshot_id": snapshot.id,
        "transaction_id": acquisition_transaction.id,
        "transaction_created": transaction_created,
    }


def create_loan_from_suggestion(
    db,
    document,
    suggestion_data: dict,
    *,
    liability_source_type=None,
) -> dict:
    """
    Create PropertyLoan + RecurringTransaction(loan_interest) from a confirmed Kreditvertrag suggestion.
    Called by the confirm-loan API endpoint after user approves.

    Steps:
    1. Create PropertyLoan record with loan_contract_document_id = document.id
    2. Create RecurringTransaction (type=loan_interest), amount = monthly interest
    3. Generate historical due transactions
    4. Mark suggestion as confirmed

    Args:
        db: Database session
        document: Document ORM instance
        suggestion_data: The suggestion["data"] dict from ocr_result.import_suggestion

    Returns:
        Dict with created record IDs and summary info
    """
    from app.models.liability import LiabilitySourceType
    from app.models.property_loan import PropertyLoan
    from app.services.loan_service import LoanService
    from app.services.recurring_transaction_service import RecurringTransactionService
    from decimal import Decimal
    from datetime import datetime as dt, date as date_cls

    _enforce_contract_role_gate(
        db,
        document,
        expected_role="borrower",
        flow_label="Loan creation",
    )

    data = suggestion_data

    # --- Extract and validate required fields ---
    loan_amount_raw = data.get("loan_amount")
    interest_rate_raw = data.get("interest_rate")

    if not loan_amount_raw or not interest_rate_raw:
        raise ValueError(
            "Missing required fields: loan_amount and interest_rate are required"
        )

    loan_amount = Decimal(str(loan_amount_raw))
    # OCR stores interest_rate as percentage (e.g. 3.5 for 3.5%)
    # PropertyLoan stores as decimal (e.g. 0.035)
    interest_rate_pct = Decimal(str(interest_rate_raw))
    interest_rate_decimal = interest_rate_pct / Decimal("100")

    monthly_payment_raw = data.get("monthly_payment")
    monthly_payment = Decimal(str(monthly_payment_raw)) if monthly_payment_raw else None

    lender_name = data.get("lender_name", "Unknown Lender")

    # Parse start_date
    sd_raw = data.get("start_date")
    start_date = None
    if sd_raw and isinstance(sd_raw, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                start_date = dt.strptime(sd_raw, fmt).date()
                break
            except ValueError:
                continue
    if not start_date:
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

    # Resolve property_id — retry OCR-address/property-context matching before
    # falling back to the standalone repayment path.
    property_id = data.get("matched_property_id")
    if not property_id:
        ocr_result = document.ocr_result if isinstance(document.ocr_result, dict) else {}
        upload_context = (ocr_result.get("_upload_context") or {}) if isinstance(ocr_result, dict) else {}
        property_id, matched_property_address, address_mismatch_warning = _match_property_for_loan_contract(
            db,
            document,
            context_property_id=upload_context.get("property_id"),
            property_address=data.get("property_address") or ocr_result.get("property_address"),
        )
        if property_id:
            data = {
                **data,
                "matched_property_id": property_id,
                "matched_property_address": matched_property_address,
                "address_mismatch_warning": address_mismatch_warning,
            }
        else:
            return confirm_unlinked_loan_contract(db, document, data)

    # Verify property exists and belongs to user
    from app.models.property import Property as PropertyModel, PropertyStatus

    prop = (
        db.query(PropertyModel)
        .filter(
            PropertyModel.id == property_id,
            PropertyModel.user_id == document.user_id,
            PropertyModel.status == PropertyStatus.ACTIVE,
        )
        .first()
    )
    if not prop:
        raise ValueError(f"Property {property_id} not found or not active")

    # Calculate monthly interest if not provided
    if not monthly_payment or monthly_payment <= 0:
        monthly_payment = (loan_amount * interest_rate_decimal / Decimal("12")).quantize(
            Decimal("0.01")
        )

    # Monthly interest amount for the recurring transaction
    monthly_interest = (loan_amount * interest_rate_decimal / Decimal("12")).quantize(
        Decimal("0.01")
    )

    # --- Create PropertyLoan ---
    loan = PropertyLoan(
        property_id=property_id,
        user_id=document.user_id,
        loan_amount=loan_amount,
        interest_rate=interest_rate_decimal,
        start_date=start_date,
        end_date=end_date,
        monthly_payment=monthly_payment,
        lender_name=lender_name,
        loan_contract_document_id=document.id,
    )
    db.add(loan)
    db.flush()  # Get loan.id without committing
    from app.services.liability_service import LiabilityService
    liability = LiabilityService(db).ensure_property_loan_liability(
        loan,
        source_document_id=document.id,
        source_type=liability_source_type or LiabilitySourceType.DOCUMENT_CONFIRMED,
    )

    loan_service = LoanService(db)
    installments = loan_service.generate_installment_plan(
        loan.id,
        document.user_id,
        replace_existing_estimates=True,
        commit_changes=False,
    )

    # --- Create RecurringTransaction (loan_interest) ---
    service = RecurringTransactionService(db)
    recurring = service.create_loan_interest_recurring(
        user_id=document.user_id,
        loan_id=loan.id,
        liability_id=liability.id,
        monthly_interest=monthly_interest,
        start_date=start_date,
        end_date=end_date,
        day_of_month=start_date.day,
    )

    # Link recurring to source document
    recurring.source_document_id = document.id
    db.flush()

    # --- Generate historical due transactions ---
    generated = []
    try:
        generated = service.generate_due_transactions(
            target_date=date_cls.today(), user_id=document.user_id
        )
        logger.info(
            f"Generated {len(generated)} transactions from loan recurring {recurring.id}"
        )
    except Exception as e:
        logger.warning(
            f"Failed to generate due transactions for loan recurring {recurring.id}: {e}"
        )

    # --- Mark suggestion as confirmed ---
    import json as _json

    ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
    if ocr_result.get("import_suggestion"):
        ocr_result["import_suggestion"]["status"] = "confirmed"
        ocr_result["import_suggestion"]["loan_id"] = loan.id
        ocr_result["import_suggestion"]["recurring_id"] = recurring.id
        document.ocr_result = ocr_result
    db.commit()

    logger.info(
        f"Created PropertyLoan {loan.id} and recurring {recurring.id} from "
        f"Kreditvertrag doc {document.id} (amount=€{loan_amount}, "
        f"rate={interest_rate_pct}%, monthly_interest=€{monthly_interest})"
    )

    return {
        "loan_id": loan.id,
        "recurring_id": recurring.id,
        "property_id": property_id,
        "loan_amount": float(loan_amount),
        "interest_rate": float(interest_rate_pct),
        "monthly_interest": float(monthly_interest),
        "monthly_payment": float(monthly_payment),
        "installment_count": len(installments),
        "generated_count": len(generated),
    }


def _build_versicherung_suggestion(db, document, result) -> dict:
    """
    Build an insurance recurring expense suggestion from Versicherungsbestätigung OCR data.
    Does NOT create any records — only stores suggestion data for user confirmation.
    Returns dict with suggestion keys to merge into ocr_result.
    """
    from decimal import Decimal
    from datetime import datetime as dt

    updated_ocr = document.ocr_result.copy() if isinstance(document.ocr_result, dict) else {}
    updated_ocr = _clear_transaction_artifact_keys(updated_ocr)
    role_resolution = _resolve_contract_role_for_document(
        db,
        document,
        updated_ocr,
        raw_text=getattr(result, "raw_text", None) or document.raw_text,
    )
    _apply_contract_role_resolution(updated_ocr, role_resolution)

    ocr_data = updated_ocr
    if not isinstance(ocr_data, dict):
        return {"import_suggestion": None}

    # Extract premium amount - the key OCR field
    praemie = ocr_data.get("praemie") or ocr_data.get("premium") or ocr_data.get("amount")
    if not praemie:
        updated_ocr.pop("import_suggestion", None)
        document.ocr_result = updated_ocr
        db.commit()
        return {"import_suggestion": None}

    try:
        praemie_decimal = Decimal(str(praemie))
        if praemie_decimal <= 0:
            updated_ocr.pop("import_suggestion", None)
            document.ocr_result = updated_ocr
            db.commit()
            return {"import_suggestion": None}
    except Exception:
        updated_ocr.pop("import_suggestion", None)
        document.ocr_result = updated_ocr
        db.commit()
        return {"import_suggestion": None}

    # Extract frequency — try explicit field, then infer from text
    freq_raw = (
        ocr_data.get("zahlungsfrequenz")
        or ocr_data.get("payment_frequency")
        or ocr_data.get("zahlungsweise")
        or ocr_data.get("frequency")
        or ""
    )
    freq_map = {
        "monatlich": "monthly", "monthly": "monthly",
        "quartalsweise": "quarterly", "quarterly": "quarterly",
        "vierteljährlich": "quarterly", "vierteljaehrlich": "quarterly",
        "halbjährlich": "semi_annual", "halbjaehrlich": "semi_annual",
        "semi_annual": "semi_annual", "semi-annual": "semi_annual",
        "jährlich": "annually", "annually": "annually",
        "jaehrlich": "annually",
    }
    frequency = freq_map.get(str(freq_raw).lower().strip(), "")

    # Infer from raw_text / description / file_name if not explicitly set
    if not frequency:
        _freq_text = str(ocr_data.get("raw_text") or "")[:2000].lower()
        _freq_text += " " + str(getattr(document, 'raw_text', '') or "")[:2000].lower()
        _freq_text += " " + str(ocr_data.get("description") or "").lower()
        if any(m in _freq_text for m in ("monatlich", "monats", "sepa-lastschrift", "pro monat", "_sepa_", "sepa abbuchung")):
            frequency = "monthly"
        elif any(m in _freq_text for m in ("vierteljährlich", "vierteljaehrlich", "quartalsweise", "quartal")):
            frequency = "quarterly"
        elif any(m in _freq_text for m in ("halbjährlich", "halbjaehrlich", "halbjahres")):
            frequency = "semi_annual"
        else:
            frequency = "annually"  # Default for insurance

    # Extract insurance type — try OCR fields first, then infer from file name
    insurance_type = (
        ocr_data.get("versicherungsart")
        or ocr_data.get("insurance_type")
        or ""
    )
    if not insurance_type or insurance_type == "unknown":
        # Infer from extracted document content ONLY (never from file name)
        _desc = str(ocr_data.get("description", "")).lower()
        _raw = str(ocr_data.get("raw_text", ""))[:3000].lower()
        # Also check document.raw_text (stored separately from ocr_result)
        _doc_raw = str(getattr(document, 'raw_text', '') or "")[:3000].lower()
        _merchant = str(ocr_data.get("merchant") or ocr_data.get("issuer") or "").lower()
        _content = _desc + " " + _raw + " " + _doc_raw + " " + _merchant
        # Order matters! More specific keywords first
        _type_infer = [
            ("kfz", "KFZ-Versicherung"),
            ("vollkasko", "KFZ-Versicherung"),
            ("kraftfahrzeug", "KFZ-Versicherung"),
            ("fahrzeugversicherung", "KFZ-Versicherung"),
            ("berufshaftpflicht", "Berufshaftpflicht"),
            ("rechtsschutz", "Rechtsschutzversicherung"),
            ("gebaeudeversicherung", "Gebäudeversicherung"),
            ("gebäudeversicherung", "Gebäudeversicherung"),
            ("haushaltsversicherung", "Haushaltsversicherung"),
            ("hausratversicherung", "Haushaltsversicherung"),
            ("private krankenversicherung", "Private Krankenversicherung"),
            ("zusatzversicherung", "Private Krankenversicherung"),
            ("sonderklasse", "Private Krankenversicherung"),
            ("unfallversicherung", "Unfallversicherung"),
            ("lebensversicherung", "Lebensversicherung"),
            ("haftpflicht", "Haftpflicht"),  # Last — generic
        ]
        for keyword, label in _type_infer:
            if keyword in _content:
                insurance_type = label
                break
    if not insurance_type:
        insurance_type = "unknown"

    def _clean_ocr_name(val):
        """Remove OCR page markers and clean up names."""
        if not val or not isinstance(val, str):
            return None
        # Remove page markers: "--- PAGE 1 ---", "PAGE 1 ---", "--- PAGE 1", etc.
        cleaned = re.sub(r'-{0,3}\s*PAGE\s*\d+\s*-{0,3}', '', val, flags=re.IGNORECASE).strip()
        # Remove leading/trailing newlines and whitespace
        cleaned = re.sub(r'^[\s\n]+|[\s\n]+$', '', cleaned)
        # Replace internal newlines with space
        cleaned = re.sub(r'\s*\n\s*', ' ', cleaned)
        if not cleaned or cleaned in ("Unbekannt", "Unknown"):
            return None
        return cleaned

    _raw_insurer = (
        _clean_ocr_name(ocr_data.get("versicherer"))
        or _clean_ocr_name(ocr_data.get("insurer_name"))
        or _clean_ocr_name(ocr_data.get("company_name"))
        or _clean_ocr_name(ocr_data.get("issuer"))
        or _clean_ocr_name(ocr_data.get("merchant"))
    )
    insurer_name = _raw_insurer
    if not insurer_name:
        # Try to extract from document content (never file name)
        _raw = str(ocr_data.get("raw_text", ""))[:2000] + " " + str(getattr(document, 'raw_text', '') or "")[:2000]
        _known_insurers = {
            "UNIQA": "UNIQA Insurance Group AG",
            "Wiener Städtische": "Wiener Städtische",
            "Wiener Staedtische": "Wiener Städtische",
            "Generali": "Generali Versicherung AG",
            "Allianz": "Allianz Elementar",
            "Zürich": "Zürich Versicherungs-AG",
            "Zuerich": "Zürich Versicherungs-AG",
            "GRAWE": "GRAWE (Grazer Wechselseitige)",
            "Grazer Wechselseitige": "GRAWE (Grazer Wechselseitige)",
            "Helvetia": "Helvetia Versicherungen AG",
            "Donau": "Donau Versicherung AG",
        }
        for keyword, full_name in _known_insurers.items():
            if keyword.lower() in _raw.lower():
                insurer_name = full_name
                break
    if not insurer_name:
        insurer_name = "Unbekannt"
    upload_context = ocr_data.get("_upload_context", {}) or {}
    linked_property_id = (
        upload_context.get("property_id")
        or ocr_data.get("linked_property_id")
        or ocr_data.get("matched_property_id")
    )
    linked_asset_id = upload_context.get("asset_id") or ocr_data.get("linked_asset_id")

    # Parse start_date
    sd_raw = ocr_data.get("start_date") or ocr_data.get("vertragsbeginn")
    start_date = None
    if sd_raw:
        if isinstance(sd_raw, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
                try:
                    start_date = dt.strptime(sd_raw, fmt).date()
                    break
                except ValueError:
                    continue
        else:
            start_date = sd_raw
    if not start_date:
        start_date = document.uploaded_at.date()

    # Parse end_date
    ed_raw = ocr_data.get("end_date") or ocr_data.get("vertragsende")
    end_date = None
    if ed_raw:
        if isinstance(ed_raw, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
                try:
                    end_date = dt.strptime(ed_raw, fmt).date()
                    break
                except ValueError:
                    continue

    # Insurance subtype and deductibility based on type
    insurance_subtype = ocr_data.get("insurance_subtype", "").strip().lower()
    if not insurance_subtype:
        # Infer from versicherungsart or insurance_type
        _type_lower = (insurance_type or "").lower()
        _subtype_map = {
            "haftpflicht": "berufshaftpflicht",
            "berufshaftpflicht": "berufshaftpflicht",
            "betriebsunterbrechung": "betriebsunterbrechung",
            "rechtsschutz": "rechtsschutz",
            "kfz": "kfz", "auto": "kfz", "fahrzeug": "kfz",
            "gebäude": "gebaeudeversicherung", "gebaeudeversicherung": "gebaeudeversicherung",
            "haushalt": "haushaltsversicherung", "haushaltsversicherung": "haushaltsversicherung",
            "kranken": "private_krankenversicherung",
            "unfall": "unfallversicherung",
            "leben": "lebensversicherung",
        }
        for keyword, subtype in _subtype_map.items():
            if keyword in _type_lower:
                insurance_subtype = subtype
                break
        if not insurance_subtype:
            insurance_subtype = "other"

    # Set deductibility based on subtype
    _DEDUCTIBILITY_MAP = {
        "berufshaftpflicht": (True, "Betriebsausgabe — E1a KZ 9230"),
        "betriebsunterbrechung": (True, "Betriebsausgabe — E1a KZ 9230"),
        "rechtsschutz": (True, "Nur gewerblicher Anteil absetzbar — E1a KZ 9230"),
        "kfz": (True, "Nur gewerblicher KFZ-Anteil absetzbar — E1a KZ 9230"),
        "gebaeudeversicherung": (True, "Werbungskosten Vermietung — E1b"),
        "haushaltsversicherung": (True, "Nur Home-Office-Anteil absetzbar — E1a KZ 9230"),
        "private_krankenversicherung": (True, "Sonderausgaben — E1 KZ 455"),
        "unfallversicherung": (True, "Sonderausgaben — E1 KZ 455"),
        "lebensversicherung": (True, "Sonderausgaben — E1 KZ 455"),
        "other": (False, "Bitte prüfen Sie die steuerliche Absetzbarkeit"),
    }
    is_deductible, deduction_reason = _DEDUCTIBILITY_MAP.get(insurance_subtype, (False, ""))

    suggestion = {
        "type": "create_insurance_recurring",
        "status": "pending",
        "data": {
            "praemie": float(praemie_decimal),
            "frequency": frequency,
            "insurance_type": insurance_type,
            "insurance_subtype": insurance_subtype,
            "insurer_name": insurer_name,
            "is_deductible": is_deductible,
            "deduction_reason": deduction_reason,
            "linked_property_id": linked_property_id,
            "linked_asset_id": linked_asset_id,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    }
    _annotate_contract_role_gate(suggestion["data"], role_resolution)

    if role_resolution and role_resolution.strict_would_block and role_resolution.mode == "strict":
        updated_ocr.pop("import_suggestion", None)
        document.ocr_result = updated_ocr
        db.commit()
        return {"import_suggestion": None}

    logger.info(
        f"Built insurance recurring suggestion for Versicherung doc {document.id}: "
        f"praemie=€{praemie_decimal}, frequency={frequency}, type={insurance_type}"
    )

    # Write key insurance fields to top-level ocr_result so frontend can display them
    updated_ocr["insurer_name"] = insurer_name
    updated_ocr["insurance_type"] = insurance_type
    updated_ocr["insurance_subtype"] = insurance_subtype
    updated_ocr["praemie"] = float(praemie_decimal)
    updated_ocr["zahlungsfrequenz"] = frequency
    updated_ocr["is_deductible"] = is_deductible
    updated_ocr["deduction_reason"] = deduction_reason
    if ocr_data.get("polizze") or ocr_data.get("versicherungsnummer"):
        updated_ocr["polizze"] = ocr_data.get("polizze") or ocr_data.get("versicherungsnummer") or ""

    # Save suggestion into document's ocr_result
    updated_ocr["import_suggestion"] = suggestion
    document.ocr_result = updated_ocr
    db.commit()

    return {"import_suggestion": suggestion}


def create_insurance_recurring_from_suggestion(db, document, suggestion_data: dict) -> dict:
    """
    Create RecurringTransaction(insurance_premium) from a confirmed Versicherung suggestion.
    Called by the confirm-insurance-recurring API endpoint after user approves.
    """
    from app.models.recurring_transaction import (
        RecurringTransaction,
        RecurringTransactionType,
        RecurrenceFrequency,
    )
    from sqlalchemy import cast, String
    from decimal import Decimal
    from datetime import datetime as dt, date as date_cls
    import json as _json
    import re

    _enforce_contract_role_gate(
        db,
        document,
        expected_role="policy_holder",
        flow_label="Insurance recurring creation",
    )

    data = suggestion_data

    praemie_raw = data.get("praemie")
    if not praemie_raw:
        raise ValueError("Missing required field: praemie")

    praemie = Decimal(str(praemie_raw))
    if praemie <= 0:
        raise ValueError("Premium amount must be positive")

    # Map frequency
    freq_str = data.get("frequency", "annually")
    freq_map = {
        "monthly": RecurrenceFrequency.MONTHLY,
        "quarterly": RecurrenceFrequency.QUARTERLY,
        "annually": RecurrenceFrequency.ANNUALLY,
    }
    frequency = freq_map.get(freq_str, RecurrenceFrequency.ANNUALLY)

    insurance_type = data.get("insurance_type", "unknown")
    insurer_name = data.get("insurer_name", "Unknown Insurer")
    linked_property_id = data.get("linked_property_id")
    linked_asset_id = data.get("linked_asset_id")

    # Parse start_date
    sd_raw = data.get("start_date")
    start_date = None
    if sd_raw and isinstance(sd_raw, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                start_date = dt.strptime(sd_raw, fmt).date()
                break
            except ValueError:
                continue
    if not start_date:
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

    description = f"Insurance premium - {insurer_name}"
    if insurance_type and insurance_type != "unknown":
        description = f"Insurance premium ({insurance_type}) - {insurer_name}"

    def _normalize_token(value: str | None) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    duplicate_query = db.query(RecurringTransaction).filter(
        RecurringTransaction.user_id == document.user_id,
        RecurringTransaction.recurring_type == RecurringTransactionType.INSURANCE_PREMIUM,
        RecurringTransaction.is_active == True,
        RecurringTransaction.amount == praemie,
        RecurringTransaction.frequency == frequency,
    )
    if linked_property_id:
        duplicate_query = duplicate_query.filter(
            cast(RecurringTransaction.property_id, String) == str(linked_property_id)
        )

    insurer_norm = _normalize_token(insurer_name)
    insurance_norm = _normalize_token(insurance_type)
    duplicate_recurring = None
    for candidate in duplicate_query.all():
        if candidate.start_date and abs((candidate.start_date - start_date).days) > 45:
            continue
        haystack = _normalize_token(" ".join(filter(None, [candidate.description, candidate.notes])))
        if insurer_norm and insurer_norm not in haystack:
            continue
        if insurance_norm and insurance_norm != "unknown" and insurance_norm not in haystack:
            continue
        duplicate_recurring = candidate
        break

    if duplicate_recurring:
        ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
        if ocr_result.get("import_suggestion"):
            ocr_result["import_suggestion"]["status"] = "confirmed"
            ocr_result["import_suggestion"]["recurring_id"] = duplicate_recurring.id
            ocr_result["import_suggestion"]["duplicate_of_recurring_id"] = duplicate_recurring.id
            document.ocr_result = ocr_result
        db.commit()
        return {
            "recurring_id": duplicate_recurring.id,
            "praemie": float(praemie),
            "frequency": freq_str,
            "insurance_type": insurance_type,
            "generated_count": 0,
            "duplicate_reused": True,
        }

    recurring = RecurringTransaction(
        user_id=document.user_id,
        recurring_type=RecurringTransactionType.INSURANCE_PREMIUM,
        description=description,
        amount=praemie,
        transaction_type="expense",
        category="insurance",
        frequency=frequency,
        start_date=start_date,
        end_date=end_date,
        day_of_month=start_date.day,
        is_active=True,
        next_generation_date=start_date,
        source_document_id=document.id,
        property_id=linked_property_id,
        notes="; ".join(
            filter(
                None,
                [
                    f"insurance_type={insurance_type}" if insurance_type else None,
                    f"insurer_name={insurer_name}" if insurer_name else None,
                    f"linked_asset_id={linked_asset_id}" if linked_asset_id else None,
                ],
            )
        ) or None,
    )
    db.add(recurring)
    db.flush()

    # Generate historical due transactions
    from app.services.recurring_transaction_service import RecurringTransactionService

    service = RecurringTransactionService(db)
    generated = []
    try:
        generated = service.generate_due_transactions(
            target_date=date_cls.today(), user_id=document.user_id
        )
    except Exception as e:
        logger.warning(
            f"Failed to generate due transactions for insurance recurring {recurring.id}: {e}"
        )

    # Mark suggestion as confirmed
    ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
    if ocr_result.get("import_suggestion"):
        ocr_result["import_suggestion"]["status"] = "confirmed"
        ocr_result["import_suggestion"]["recurring_id"] = recurring.id
        document.ocr_result = ocr_result
    db.commit()

    logger.info(
        f"Created insurance recurring {recurring.id} from Versicherung doc {document.id} "
        f"(praemie=€{praemie}, frequency={freq_str})"
    )

    return {
        "recurring_id": recurring.id,
        "praemie": float(praemie),
        "frequency": freq_str,
        "insurance_type": insurance_type,
        "generated_count": len(generated),
    }


def confirm_unlinked_loan_contract(db, document, suggestion_data: dict) -> dict:
    """
    Confirm a loan contract that is not linked to a taxable property yet.

    If a property can now be matched, promote into the property-loan flow.
    Otherwise create a standalone liability and, when the monthly payment is
    available, a recurring liability repayment plan.
    """
    import json as _json
    from datetime import datetime as dt
    from decimal import Decimal

    from app.models.liability import LiabilitySourceType, LiabilityType
    from app.services.liability_service import LiabilityService

    _enforce_contract_role_gate(
        db,
        document,
        expected_role="borrower",
        flow_label="Loan contract confirmation",
    )

    data = suggestion_data
    property_id = data.get("matched_property_id")

    if not property_id:
        ocr_result = document.ocr_result if isinstance(document.ocr_result, dict) else {}
        upload_context = (ocr_result.get("_upload_context") or {}) if isinstance(ocr_result, dict) else {}
        property_id, matched_property_address, address_mismatch_warning = _match_property_for_loan_contract(
            db,
            document,
            context_property_id=upload_context.get("property_id"),
            property_address=data.get("property_address") or ocr_result.get("property_address"),
        )
        if property_id:
            data = {
                **data,
                "matched_property_id": property_id,
                "matched_property_address": matched_property_address,
                "address_mismatch_warning": address_mismatch_warning,
            }

    if property_id:
        logger.info(
            f"Kreditvertrag doc {document.id}: promoting unlinked loan confirmation "
            f"to property-linked loan via property {property_id}"
        )
        return create_loan_from_suggestion(db, document, data)

    loan_amount_raw = data.get("loan_amount")
    interest_rate_raw = data.get("interest_rate")
    monthly_payment_raw = data.get("monthly_payment")
    lender_name = data.get("lender_name") or "Unknown Lender"

    if not loan_amount_raw or not interest_rate_raw:
        raise ValueError("Missing required fields: loan_amount and interest_rate are required")

    loan_amount = Decimal(str(loan_amount_raw))
    interest_rate_pct = Decimal(str(interest_rate_raw))
    monthly_payment = Decimal(str(monthly_payment_raw)) if monthly_payment_raw else None

    sd_raw = data.get("start_date")
    start_date = None
    if sd_raw and isinstance(sd_raw, str):
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
    if ed_raw and isinstance(ed_raw, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                end_date = dt.strptime(ed_raw, fmt).date()
                break
            except ValueError:
                continue

    liability_type_value = _resolve_standalone_liability_type(document)
    liability_type = LiabilityType(liability_type_value)
    liability_service = LiabilityService(db)
    liability = liability_service.create_liability(
        document.user_id,
        liability_type=liability_type,
        source_type=LiabilitySourceType.DOCUMENT_CONFIRMED,
        display_name=f"{lender_name} loan",
        currency="EUR",
        lender_name=lender_name,
        principal_amount=loan_amount,
        outstanding_balance=loan_amount,
        interest_rate=interest_rate_pct,
        start_date=start_date,
        end_date=end_date,
        monthly_payment=monthly_payment,
        tax_relevant=False,
        tax_relevance_reason=None,
        report_category=None,
        linked_property_id=None,
        linked_loan_id=None,
        source_document_id=document.id,
        notes="Created from confirmed standalone loan contract",
        create_recurring_plan=bool(monthly_payment and monthly_payment > 0),
        recurring_day_of_month=start_date.day,
    )

    ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
    suggestion = ocr_result.get("import_suggestion")
    recurring_id = None
    if liability.recurring_transactions:
        recurring_id = liability.recurring_transactions[0].id

    if suggestion:
        suggestion["status"] = "confirmed"
        suggestion["liability_id"] = liability.id
        suggestion["created_recurring"] = bool(recurring_id)
        suggestion["created_transaction"] = True
        suggestion.pop("acknowledged_only", None)
        suggestion_data_payload = suggestion.get("data")
        if isinstance(suggestion_data_payload, dict):
            suggestion_data_payload["created_liability_id"] = liability.id
            suggestion_data_payload["no_property_match"] = True
            suggestion_data_payload["source_type"] = "document_confirmed"
        if recurring_id:
            suggestion["recurring_id"] = recurring_id
        document.ocr_result = ocr_result
        db.commit()

    logger.info(
        f"Confirmed standalone loan contract for doc {document.id} and created liability {liability.id}"
    )

    return {
        "liability_id": liability.id,
        "recurring_id": recurring_id,
        "property_id": None,
        "generated_count": 0,
        "acknowledged_only": False,
        "created_recurring": bool(recurring_id),
        "created_transaction": True,
    }


def create_standalone_loan_repayment(db, document, suggestion_data: dict) -> dict:
    """
    Legacy compatibility wrapper for the former standalone loan repayment flow.

    The product now confirms unlinked loan contracts without creating an
    expense-style recurring. If a property match becomes available, the helper
    still promotes the contract into the property-loan interest flow.
    """
    return confirm_unlinked_loan_contract(db, document, suggestion_data)


def _detect_recurring_expense(db, document, suggestion: dict) -> dict | None:
    """
    Detect if an invoice/receipt represents a recurring expense pattern.

    Checks OCR text and extracted data for keywords indicating periodic payments
    (insurance, subscriptions, monthly fees, maintenance contracts, etc.).
    Returns an import_suggestion dict or None.
    """
    import json as _json

    ocr_data = document.ocr_result or {}
    if not isinstance(ocr_data, dict):
        return None

    description = suggestion.get("description", "")
    amount = suggestion.get("amount")
    if not amount or float(amount) <= 0:
        return None

    raw_text = (document.raw_text or "").lower()
    desc_lower = description.lower()
    combined = f"{desc_lower} {raw_text}"

    # Keywords that indicate recurring payments (German + English)
    RECURRING_KEYWORDS = {
        # Insurance
        "versicherung", "insurance", "polizze", "prämie", "premium",
        "haftpflicht", "haushaltsversicherung", "gebäudeversicherung",
        "rechtsschutz", "kfz-versicherung", "lebensversicherung",
        # Subscriptions / memberships
        "abonnement", "abo", "subscription", "mitgliedschaft", "membership",
        "monatsbeitrag", "jahresbeitrag", "beitrag",
        # Recurring services
        "wartungsvertrag", "servicevertrag", "maintenance",
        "hausverwaltung", "property management",
        "reinigung", "cleaning", "gartenpflege",
        # Utilities / telecom
        "internet", "telefon", "mobilfunk", "strom", "gas", "fernwärme",
        # Loan / leasing
        "leasingrate", "kreditrate", "darlehen", "tilgung",
        # Periodic indicators
        "monatlich", "monthly", "vierteljährlich", "quarterly",
        "jährlich", "annually", "halbjährlich",
        "pro monat", "per month", "je monat",
        "pro quartal", "pro jahr",
    }

    # Frequency detection from text
    FREQ_PATTERNS = {
        "monthly": ["monatlich", "monthly", "pro monat", "per month", "je monat", "mtl"],
        "quarterly": [
            "vierteljährlich", "quarterly", "pro quartal", "quartalsweise",
        ],
        "annually": [
            "jährlich", "annually", "pro jahr", "per year", "jahresprämie",
        ],
    }

    matched_keywords = [kw for kw in RECURRING_KEYWORDS if kw in combined]
    if not matched_keywords:
        return None

    # Determine frequency
    detected_freq = "monthly"  # default
    for freq, patterns in FREQ_PATTERNS.items():
        if any(p in combined for p in patterns):
            detected_freq = freq
            break

    # Try to extract contract period from OCR data
    start_raw = ocr_data.get("start_date") or ocr_data.get("contract_start")
    end_raw = ocr_data.get("end_date") or ocr_data.get("contract_end") or ocr_data.get("valid_until")

    from datetime import datetime as dt

    def _parse_date(raw):
        if not raw or not isinstance(raw, str):
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
            try:
                return dt.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

    start = _parse_date(start_raw)
    end = _parse_date(end_raw)

    if not start:
        txn_date = suggestion.get("transaction_date")
        start = _parse_date(txn_date) or document.uploaded_at.date()

    category = suggestion.get("category", "other")
    txn_type = suggestion.get("transaction_type", "expense")

    suggestion_data = {
        "type": "create_recurring_expense",
        "status": "pending",
        "data": {
            "description": description,
            "amount": float(amount),
            "transaction_type": txn_type,
            "category": category,
            "frequency": detected_freq,
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "detected_keywords": matched_keywords[:5],
            "day_of_month": start.day if start else 1,
        },
    }

    logger.info(
        f"Detected recurring expense pattern for doc {document.id}: "
        f"desc='{description[:50]}', amount=€{amount}, freq={detected_freq}, "
        f"keywords={matched_keywords[:3]}"
    )

    # Save into document's ocr_result
    updated_ocr = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
    updated_ocr["import_suggestion"] = suggestion_data
    document.ocr_result = updated_ocr
    db.commit()

    return suggestion_data


def create_recurring_from_suggestion(db, document, suggestion_data: dict) -> dict:
    """
    Create recurring rental income from a confirmed suggestion.
    Called by the confirmation API endpoint after user approves.
    """
    from app.services.recurring_transaction_service import RecurringTransactionService
    from decimal import Decimal
    from datetime import datetime as dt

    _enforce_contract_role_gate(
        db,
        document,
        expected_role="landlord",
        flow_label="Recurring income creation",
    )

    # Same-document dedup: if a recurring was already created from this document, return it
    from app.models.recurring_transaction import RecurringTransaction as _RT
    existing_from_doc = (
        db.query(_RT)
        .filter(_RT.source_document_id == int(document.id))
        .first()
    )
    if existing_from_doc:
        logger.info(
            "Recurring %s already created from document %s — skipping duplicate creation",
            existing_from_doc.id, document.id,
        )
        # Mark suggestion as confirmed so batch reprocess-all won't re-queue
        import json as _json_miet
        _ocr = _json_miet.loads(_json_miet.dumps(document.ocr_result)) if document.ocr_result else {}
        if _ocr.get("import_suggestion"):
            _ocr["import_suggestion"]["status"] = "confirmed"
            _ocr["import_suggestion"]["recurring_id"] = existing_from_doc.id
            document.ocr_result = _ocr
            db.commit()
        return {"recurring_id": existing_from_doc.id, "reused": True}

    data = suggestion_data
    monthly_rent = Decimal(str(data["monthly_rent"]))
    property_id = data.get("matched_property_id")

    # Retry address matching if no property was matched at upload time
    # (property may have been created after the Mietvertrag was uploaded)
    if not property_id:
        address = data.get("address", "")
        if address:
            try:
                from app.services.address_matcher import AddressMatcher
                matcher = AddressMatcher(db)
                matches = matcher.match_address(address, document.user_id)
                if matches and matches[0].confidence > 0.3:
                    property_id = str(matches[0].property.id)
                    logger.info(
                        f"Retry match found property {property_id} for address '{address}'"
                    )
                else:
                    # Fallback: street name matching
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
                            property_id = str(p.id)
                            logger.info(
                                f"Retry street match found property {property_id} for '{address}'"
                            )
                            break
            except Exception as e:
                logger.warning(f"Retry address matching failed: {e}")

    if not property_id:
        # Auto-create a minimal property from the rental contract address
        # User can later upload Kaufvertrag to fill in purchase details
        address = data.get("address", "")
        logger.info(
            f"No matching property for rental contract (doc {document.id}), "
            f"auto-creating from address: '{address}'"
        )
        try:
            from app.models.property import (
                Property as PropertyModel,
                PropertyType,
                PropertyStatus,
            )
            from decimal import Decimal as D

            # Parse address into components (best-effort)
            street = address or "Unbekannt"
            city = "Unbekannt"
            postal_code = "0000"
            # Try to split "Street, PostalCode City" pattern
            if "," in address:
                parts = address.split(",", 1)
                street = parts[0].strip()
                rest = parts[1].strip()
                # Try to extract postal code and city from rest
                rest_parts = rest.split(None, 1)
                if rest_parts and rest_parts[0].isdigit():
                    postal_code = rest_parts[0]
                    city = rest_parts[1] if len(rest_parts) > 1 else "Unbekannt"
                else:
                    city = rest

            new_prop = PropertyModel(
                user_id=document.user_id,
                property_type=PropertyType.OWNER_OCCUPIED,  # Will be recalculated
                rental_percentage=D("0.00"),
                address=address or street,
                street=street,
                city=city,
                postal_code=postal_code,
                purchase_date=dt.now().date(),  # Placeholder — user should correct
                purchase_price=D("0.01"),  # Placeholder (DB CHECK requires > 0)
                building_value=D("0.01"),  # Placeholder (DB CHECK requires > 0)
                land_value=D("0.00"),
                depreciation_rate=D("0.015"),  # Default 1.5% for rental
                status=PropertyStatus.ACTIVE,
                mietvertrag_document_id=int(document.id),
            )
            db.add(new_prop)
            db.flush()
            property_id = str(new_prop.id)
            logger.info(
                f"Auto-created property {property_id} from rental contract address '{address}'"
            )
        except Exception as e:
            logger.error(f"Failed to auto-create property from rental contract: {e}")
            raise ValueError(
                "No matching property found and auto-creation failed. "
                "Please create the property first."
            )

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

    # Link recurring back to source document for edit-sync
    recurring.source_document_id = document.id
    db.flush()

    # Detect partial address match → set unit_percentage hint
    # e.g. property="Thenneberg 51" vs rental="Thenneberg 51/3" → partial match
    rental_address = data.get("address", "")
    prop_address = prop.address if prop else ""
    is_partial_match = False
    if prop and rental_address and prop_address:
        # Rental address contains property address as prefix but has extra unit info
        r_norm = rental_address.strip().lower()
        p_norm = prop_address.strip().lower()
        p_street = (prop.street or "").strip().lower()
        if p_street and r_norm.startswith(p_street) and r_norm != p_street:
            is_partial_match = True
        elif p_norm and r_norm.startswith(p_norm.split(",")[0]) and r_norm != p_norm:
            is_partial_match = True

    # Default unit_percentage: 100% if exact match, None if partial (user must set)
    if not is_partial_match:
        recurring.unit_percentage = Decimal("100.00")
    # else: leave as None — frontend will prompt user to set it

    # If end_date is in the past, mark as inactive but still let recalculate run first
    # so the property type reflects the rental relationship before expiry kicks in
    from datetime import date as date_cls
    contract_expired = end_date and end_date < date_cls.today()

    # Recalculate property rental_percentage from all active contracts
    from app.services.property_service import PropertyService as PS
    ps = PS(db)
    try:
        ps.recalculate_rental_percentage(prop.id, document.user_id)
    except Exception as e:
        logger.warning(f"Failed to recalculate rental percentage for property {property_id}: {e}")

    # Generate individual transactions BEFORE deactivating expired contracts.
    # For expired contracts, generate up to end_date; for active ones, up to today.
    # generate_due_transactions only processes is_active=True, so this must run first.
    gen_target = end_date if contract_expired else date_cls.today()
    try:
        generated = service.generate_due_transactions(
            target_date=gen_target, user_id=document.user_id
        )
        logger.info(
            f"Generated {len(generated)} transactions from recurring {recurring.id} "
            f"(start={start_date}, target={gen_target})"
        )
    except Exception as e:
        logger.warning(f"Failed to generate transactions from recurring {recurring.id}: {e}")

    # Now handle expired contracts: deactivate and recalculate again
    # This ensures the property was briefly marked as rental (for history/AfA),
    # then reverts to owner_occupied since the contract is no longer active
    if contract_expired:
        recurring.is_active = False
        db.commit()
        logger.info(
            f"Contract expired (end_date={end_date}), deactivated recurring {recurring.id}"
        )
        try:
            ps.recalculate_rental_percentage(prop.id, document.user_id)
        except Exception as e:
            logger.warning(f"Failed to recalculate after expiry for property {property_id}: {e}")

    logger.info(
        f"Created recurring rental income {recurring.id} from confirmed suggestion "
        f"for doc {document.id} (rent=€{monthly_rent}, property={property_id}, "
        f"partial_match={is_partial_match}, expired={contract_expired})"
    )

    # Mark suggestion as confirmed (deep copy to trigger SQLAlchemy change detection)
    import json as _json
    ocr_result = _json.loads(_json.dumps(document.ocr_result)) if document.ocr_result else {}
    if ocr_result.get("import_suggestion"):
        ocr_result["import_suggestion"]["status"] = "confirmed"
        ocr_result["import_suggestion"]["recurring_id"] = recurring.id
        document.ocr_result = ocr_result
        db.commit()

    # Track whether property was auto-created (for frontend messaging)
    property_auto_created = prop and prop.purchase_price is not None and prop.purchase_price <= Decimal("0.01")

    return {
        "recurring_created": True,
        "recurring_id": recurring.id,
        "property_id": property_id,
        "monthly_rent": float(monthly_rent),
        "is_partial_match": is_partial_match,
        "unit_percentage": float(recurring.unit_percentage) if recurring.unit_percentage else None,
        "contract_expired": bool(contract_expired),
        "property_auto_created": property_auto_created,
        "property_address": prop.address if prop else None,
    }


@celery_app.task(
    base=OCRTask,
    bind=True,
    soft_time_limit=300,
    time_limit=360,
    autoretry_for=(IOError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def process_document_ocr(self, document_id: int) -> Dict[str, Any]:
    """
    Process single document OCR in background.
    Uses the AI-orchestrated pipeline for classification, validation, and suggestions.
    Falls back to run_ocr_sync if the pipeline is unavailable.

    Transient errors (IOError, ConnectionError, TimeoutError) are re-raised so
    Celery's autoretry mechanism can handle them with exponential backoff.
    Non-transient pipeline failures fall back to the legacy sync path.
    """
    try:
        return run_ocr_pipeline(document_id)
    except (IOError, ConnectionError, TimeoutError):
        # Let Celery autoretry handle transient errors
        raise
    except Exception as e:
        logger.warning(
            f"Pipeline failed for document {document_id}, falling back to legacy: {e}"
        )
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
        
    except CeleryRetry:
        raise
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

