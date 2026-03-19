"""Recognition-stage decisioning for Austrian asset tax handling."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from app.schemas.asset_recognition import (
    AssetCandidate,
    AssetReasonCode,
    AssetRecognitionDecision,
    AssetRecognitionInput,
    AssetRecognitionResult,
    AssetReviewReason,
    AssetTaxFlags,
    ComparisonBasis,
    DepreciationMethod,
    DuplicateAssessment,
    DuplicateMatchType,
    DuplicateStatus,
    VatRecoverableStatus,
)
from app.services.asset_tax_policy_service import AssetTaxPolicyService
from app.services.document_classifier import DocumentClassifier


class AssetRecognitionService:
    """Classify OCR uploads into asset-tax decision states."""

    AUTO_CREATE_CONFIDENCE_THRESHOLD = Decimal("0.95")
    SUGGESTION_CONFIDENCE_THRESHOLD = Decimal("0.65")
    GWG_THRESHOLD_2022 = Decimal("800.00")
    GWG_THRESHOLD_2023 = Decimal("1000.00")

    def __init__(
        self,
        classifier: DocumentClassifier | None = None,
        tax_policy_service: AssetTaxPolicyService | None = None,
    ):
        self.classifier = classifier or DocumentClassifier()
        self.tax_policy_service = tax_policy_service or AssetTaxPolicyService()

    def recognize(self, data: AssetRecognitionInput) -> AssetRecognitionResult:
        duplicate = self._detect_duplicate(data)
        if duplicate.duplicate_status == DuplicateStatus.HIGH_CONFIDENCE:
            return self._duplicate_result(data, duplicate, suspected=False)
        if duplicate.duplicate_status == DuplicateStatus.SUSPECTED:
            return self._duplicate_result(data, duplicate, suspected=True)

        normalized_text = self._normalized_text(data.raw_text, data.extracted_line_items)
        if self._looks_like_inventory_or_resale(normalized_text):
            return self._expense_result(data, AssetReasonCode.INVENTORY_OR_RESALE_DETECTED)
        if self._looks_like_repair_or_maintenance(normalized_text):
            return self._expense_result(data, AssetReasonCode.REPAIR_OR_MAINTENANCE_DETECTED)
        if self._looks_like_service_or_subscription(normalized_text):
            return self._expense_result(data, AssetReasonCode.SERVICE_OR_SUBSCRIPTION_DETECTED)

        candidate = self._build_candidate(data, normalized_text)
        if not candidate.asset_subtype:
            return self._expense_result(data, AssetReasonCode.EXPENSE_DEFAULT_LOW_RISK)

        reason_codes: list[AssetReasonCode] = [
            AssetReasonCode.DURABLE_EQUIPMENT_DETECTED,
            AssetReasonCode.LIKELY_LONG_LIVED_ACQUISITION,
            AssetReasonCode.USEFUL_LIFE_GT_1Y,
        ]
        policy_evaluation = self.tax_policy_service.evaluate(data, candidate)
        reason_codes.extend(policy_evaluation.reason_codes)
        review_reasons = list(policy_evaluation.review_reasons)
        missing_fields = list(policy_evaluation.missing_fields)
        tax_flags = policy_evaluation.tax_flags

        if not tax_flags.depreciable:
            review_reasons.append(AssetReviewReason.NON_DEPRECIABLE_OR_UNCLEAR)
            return self._manual_review_result(
                data,
                candidate,
                reason_codes,
                review_reasons,
                missing_fields,
                tax_flags.comparison_basis,
                tax_flags.comparison_amount,
                tax_flags.policy_anchor_date or self.tax_policy_service.resolve_policy_anchor_date(data),
            )

        confidence = self._compute_confidence(data, candidate, review_reasons)
        decision = self._select_decision(
            data=data,
            candidate=candidate,
            confidence=confidence,
            gwg_eligible=tax_flags.gwg_eligible,
            missing_fields=missing_fields,
            review_reasons=review_reasons,
        )

        return AssetRecognitionResult(
            decision=decision,
            asset_candidate=candidate,
            tax_flags=tax_flags,
            reason_codes=reason_codes,
            review_reasons=review_reasons,
            missing_fields=missing_fields,
            requires_user_confirmation=decision != AssetRecognitionDecision.CREATE_ASSET_AUTO,
            policy_confidence=confidence,
            policy_rule_ids=policy_evaluation.rule_ids,
            duplicate=duplicate,
        )

    def _normalized_text(self, raw_text: str, line_items: Iterable[Any]) -> str:
        parts = [raw_text or ""]
        for item in line_items or []:
            if isinstance(item, dict):
                parts.extend(str(v) for v in item.values() if v is not None)
            else:
                parts.append(str(item))
        return "\n".join(parts).lower()

    def _detect_duplicate(self, data: AssetRecognitionInput) -> DuplicateAssessment:
        if data.file_hash:
            for candidate in data.duplicate_document_candidates:
                if candidate.file_hash and candidate.file_hash == data.file_hash:
                    return DuplicateAssessment(
                        duplicate_status=DuplicateStatus.HIGH_CONFIDENCE,
                        duplicate_match_type=DuplicateMatchType.SAME_DOCUMENT,
                        matched_asset_id=candidate.matched_asset_id,
                        matched_document_id=candidate.matched_document_id,
                        duplicate_reason_codes=[AssetReasonCode.EXACT_FILE_HASH_DUPLICATE],
                    )

        comparable_amount = data.extracted_amount
        for candidate in [*data.duplicate_document_candidates, *data.duplicate_asset_candidates]:
            same_vendor = self._safe_equal(candidate.vendor_name, data.extracted_vendor)
            same_invoice = self._safe_equal(candidate.invoice_number, data.extracted_invoice_number)
            same_amount = bool(candidate.amount_gross is not None and comparable_amount == candidate.amount_gross)
            same_date = bool(candidate.document_date is not None and candidate.document_date == data.extracted_date)
            if same_vendor and same_amount and (same_invoice or same_date):
                return DuplicateAssessment(
                    duplicate_status=DuplicateStatus.SUSPECTED,
                    duplicate_match_type=DuplicateMatchType.SAME_INVOICE if same_invoice else DuplicateMatchType.SIMILAR_ASSET,
                    matched_asset_id=candidate.matched_asset_id,
                    matched_document_id=candidate.matched_document_id,
                    duplicate_reason_codes=[AssetReasonCode.DUPLICATE_INVOICE_SIGNATURE],
                )
        return DuplicateAssessment()

    def _safe_equal(self, left: str | None, right: str | None) -> bool:
        if not left or not right:
            return False
        return left.strip().lower() == right.strip().lower()

    def _looks_like_service_or_subscription(self, text: str) -> bool:
        keywords = [
            "beratung", "consulting", "service fee", "servicepauschale", "training",
            "schulung", "support", "wartungsvertrag", "subscription", "monthly",
            "monatlich", "jährlich", "jaehrlich", "cloud", "hosting", "saas",
            "miete", "rental fee", "leasingrate", "lizenzverlängerung", "lizenzverlaengerung",
            "implementation service", "implementierung",
        ]
        return any(keyword in text for keyword in keywords)

    def _looks_like_repair_or_maintenance(self, text: str) -> bool:
        keywords = [
            "reparatur", "maintenance", "wartung", "servicearbeiten", "instanthaltung",
            "instandhaltung", "ersatzteil", "repair", "kundendienst",
        ]
        return any(keyword in text for keyword in keywords)

    def _looks_like_inventory_or_resale(self, text: str) -> bool:
        keywords = [
            "wareneingang", "weiterverkauf", "resale", "resell", "lagerware",
            "inventory", "verkaufsware", "handelsware",
        ]
        return any(keyword in text for keyword in keywords)

    def _build_candidate(self, data: AssetRecognitionInput, text: str) -> AssetCandidate:
        subtype = self._detect_asset_subtype(text)
        asset_type = self._map_asset_type(subtype)
        vehicle_category = (
            subtype
            if subtype in {"pkw", "electric_pkw", "truck_van", "fiscal_truck", "motorcycle", "special_vehicle"}
            else None
        )
        is_used_asset = data.is_used_asset if data.is_used_asset is not None else ("gebraucht" in text or "used" in text)
        return AssetCandidate(
            asset_type=asset_type,
            asset_subtype=subtype,
            asset_name=self._suggest_asset_name(data),
            vendor_name=data.extracted_vendor,
            vehicle_category=vehicle_category,
            is_used_asset=is_used_asset if subtype else None,
        )

    def _detect_asset_subtype(self, text: str) -> str | None:
        if any(keyword in text for keyword in ["motorrad", "motorcycle", "roller"]):
            return "motorcycle"
        if any(keyword in text for keyword in ["klein-lkw", "kastenwagen", "pritschenwagen", "kleinbus", "fiskal-lkw", "fiskallkw"]):
            return "fiscal_truck"
        if any(keyword in text for keyword in ["lkw", "truck", "lieferwagen", "transporter"]):
            return "truck_van"
        if any(keyword in text for keyword in ["e-auto", "elektrofahrzeug", "elektroauto", "0g co2", "ladekabel"]):
            return "electric_pkw"

        classifier_type = self.classifier.detect_asset_type(text)
        mapping = {
            "vehicle": "pkw",
            "electric_vehicle": "electric_pkw",
            "computer": "computer",
            "phone": "phone",
            "office_furniture": "office_furniture",
            "machinery": "machinery",
            "software": "perpetual_license",
            "tools": "tools",
        }
        subtype = mapping.get(classifier_type)
        if subtype:
            return subtype

        if any(keyword in text for keyword in ["drucker", "scanner", "copier"]):
            return "printer_scanner"
        if any(keyword in text for keyword in ["monitor", "display", "projektor", "kamera", "webcam"]):
            return "monitor_av"
        if any(keyword in text for keyword in ["router", "switch", "nas", "server"]):
            return "server_network"
        return None

    def _map_asset_type(self, subtype: str | None) -> str | None:
        if subtype is None:
            return None
        mapping = {
            "pkw": "vehicle",
            "electric_pkw": "electric_vehicle",
            "truck_van": "machinery",
            "fiscal_truck": "machinery",
            "motorcycle": "vehicle",
            "special_vehicle": "vehicle",
            "computer": "computer",
            "phone": "phone",
            "printer_scanner": "other_equipment",
            "monitor_av": "other_equipment",
            "server_network": "other_equipment",
            "office_furniture": "office_furniture",
            "machinery": "machinery",
            "tools": "tools",
            "perpetual_license": "software",
            "retail_equipment": "other_equipment",
            "restaurant_equipment": "other_equipment",
            "medical_beauty_equipment": "other_equipment",
            "leasehold_improvement": "other_equipment",
            "renewable_energy": "other_equipment",
            "bike_mobility": "other_equipment",
            "other_equipment": "other_equipment",
        }
        return mapping.get(subtype, "other_equipment")

    def _suggest_asset_name(self, data: AssetRecognitionInput) -> str | None:
        for item in data.extracted_line_items or []:
            if isinstance(item, dict):
                name = item.get("description") or item.get("name")
                if name:
                    return str(name)
            elif item:
                return str(item)
        return data.extracted_vendor or None

    def _resolve_comparison_basis(
        self,
        data: AssetRecognitionInput,
        reason_codes: list[AssetReasonCode],
        review_reasons: list[AssetReviewReason],
    ) -> ComparisonBasis:
        if data.vat_status == "regelbesteuert":
            reason_codes.append(AssetReasonCode.COMPARISON_BASIS_NET)
            return ComparisonBasis.NET
        if data.vat_status == "kleinunternehmer":
            reason_codes.append(AssetReasonCode.COMPARISON_BASIS_GROSS)
            return ComparisonBasis.GROSS
        review_reasons.append(AssetReviewReason.VAT_STATUS_UNKNOWN)
        reason_codes.append(AssetReasonCode.COMPARISON_BASIS_GROSS)
        return ComparisonBasis.GROSS

    def _resolve_policy_anchor_date(self, data: AssetRecognitionInput) -> date:
        return (
            data.put_into_use_date
            or data.payment_date
            or data.extracted_date
            or data.upload_timestamp.date()
        )

    def _resolve_comparison_amount(
        self,
        data: AssetRecognitionInput,
        basis: ComparisonBasis,
    ) -> Decimal:
        if basis == ComparisonBasis.NET:
            if data.extracted_net_amount is not None:
                return data.extracted_net_amount
            if data.extracted_vat_amount is not None:
                return data.extracted_amount - data.extracted_vat_amount
        return data.extracted_amount

    def _is_depreciable(self, subtype: str | None) -> bool:
        return subtype is not None

    def _suggest_useful_life_years(
        self,
        subtype: str | None,
        data: AssetRecognitionInput,
    ) -> Decimal | None:
        if subtype is None:
            return None
        if subtype in {"pkw", "electric_pkw"}:
            if data.is_used_asset and data.prior_owner_usage_years is not None:
                remaining = Decimal("8") - data.prior_owner_usage_years
                return remaining if remaining > Decimal("3") else Decimal("3")
            return Decimal("8")
        defaults = {
            "truck_van": Decimal("5"),
            "fiscal_truck": Decimal("5"),
            "motorcycle": Decimal("5"),
            "computer": Decimal("3"),
            "phone": Decimal("3"),
            "printer_scanner": Decimal("5"),
            "monitor_av": Decimal("5"),
            "server_network": Decimal("5"),
            "office_furniture": Decimal("10"),
            "machinery": Decimal("10"),
            "tools": Decimal("5"),
            "perpetual_license": Decimal("3"),
            "other_equipment": Decimal("5"),
        }
        return defaults.get(subtype, Decimal("5"))

    def _resolve_depreciation_methods(
        self,
        subtype: str,
        data: AssetRecognitionInput,
        reason_codes: list[AssetReasonCode],
    ) -> tuple[list[DepreciationMethod], DepreciationMethod]:
        methods = [DepreciationMethod.LINEAR]
        suggested = DepreciationMethod.LINEAR
        anchor = self._resolve_policy_anchor_date(data)
        is_used = data.is_used_asset or False

        if subtype == "pkw":
            reason_codes.append(AssetReasonCode.PKW_DETECTED)
            reason_codes.append(AssetReasonCode.DEGRESSIVE_BLOCKED_PKW)
            return methods, suggested
        if subtype == "electric_pkw":
            reason_codes.append(AssetReasonCode.ELECTRIC_VEHICLE_DETECTED)
        if is_used:
            reason_codes.append(AssetReasonCode.USED_ASSET_DETECTED)
            reason_codes.append(AssetReasonCode.DEGRESSIVE_BLOCKED_USED_ASSET)
            return methods, suggested
        if anchor >= date(2020, 7, 1):
            methods.append(DepreciationMethod.DEGRESSIVE)
            reason_codes.append(AssetReasonCode.DEGRESSIVE_ALLOWED)
        return methods, suggested

    def _resolve_vat_recoverable_status(
        self,
        subtype: str,
        data: AssetRecognitionInput,
    ) -> VatRecoverableStatus:
        if data.vat_status != "regelbesteuert":
            return VatRecoverableStatus.LIKELY_NO
        if subtype == "pkw":
            return VatRecoverableStatus.LIKELY_NO
        if subtype == "electric_pkw":
            return VatRecoverableStatus.PARTIAL
        return VatRecoverableStatus.LIKELY_YES

    def _resolve_ifb(
        self,
        subtype: str,
        data: AssetRecognitionInput,
        useful_life_years: Decimal | None,
        gwg_eligible: bool,
        reason_codes: list[AssetReasonCode],
        review_reasons: list[AssetReviewReason],
    ) -> tuple[bool, Decimal | None]:
        if useful_life_years is None or useful_life_years < Decimal("4"):
            reason_codes.append(AssetReasonCode.IFB_BLOCKED_SHORT_USEFUL_LIFE)
            return False, None
        if gwg_eligible:
            reason_codes.append(AssetReasonCode.IFB_BLOCKED_GWG)
            return False, None
        if data.is_used_asset:
            reason_codes.append(AssetReasonCode.IFB_BLOCKED_USED_ASSET)
            return False, None
        if subtype == "pkw":
            reason_codes.append(AssetReasonCode.IFB_BLOCKED_ORDINARY_PKW)
            return False, None
        if subtype == "perpetual_license":
            reason_codes.append(AssetReasonCode.IFB_BLOCKED_NONQUALIFYING_INTANGIBLE)
            return False, None

        anchor = self._resolve_policy_anchor_date(data)
        is_eco = subtype == "electric_pkw"
        if date(2023, 1, 1) <= anchor <= date(2025, 10, 31):
            rate = Decimal("0.15") if is_eco else Decimal("0.10")
        elif date(2025, 11, 1) <= anchor <= date(2026, 12, 31):
            rate = Decimal("0.22") if is_eco else Decimal("0.20")
        elif anchor >= date(2027, 1, 1):
            review_reasons.append(AssetReviewReason.IFB_FUTURE_WINDOW_UNKNOWN)
            return True, None
        else:
            rate = None

        reason_codes.append(
            AssetReasonCode.IFB_CANDIDATE_ECO if is_eco else AssetReasonCode.IFB_CANDIDATE_STANDARD
        )
        return True, rate

    def _resolve_gwg_threshold(self, anchor: date) -> Decimal:
        return self.GWG_THRESHOLD_2022 if anchor <= date(2022, 12, 31) else self.GWG_THRESHOLD_2023

    def _compute_confidence(
        self,
        data: AssetRecognitionInput,
        candidate: AssetCandidate,
        review_reasons: list[AssetReviewReason],
    ) -> Decimal:
        base = Decimal(str(data.ocr_confidence if data.ocr_confidence is not None else "0.85"))
        if not candidate.asset_subtype:
            base -= Decimal("0.30")
        if review_reasons:
            base -= Decimal("0.10") * Decimal(len(review_reasons))
        if data.document_type in {"purchase_contract", "kaufvertrag"} and candidate.asset_subtype:
            base += Decimal("0.10")
        return max(Decimal("0.00"), min(Decimal("1.00"), base.quantize(Decimal("0.01"))))

    def _select_decision(
        self,
        *,
        data: AssetRecognitionInput,
        candidate: AssetCandidate,
        confidence: Decimal,
        gwg_eligible: bool,
        missing_fields: list[str],
        review_reasons: list[AssetReviewReason],
    ) -> AssetRecognitionDecision:
        if AssetReviewReason.THRESHOLD_BOUNDARY_AMBIGUOUS in review_reasons:
            return AssetRecognitionDecision.MANUAL_REVIEW
        if AssetReviewReason.USED_VEHICLE_HISTORY_MISSING in review_reasons:
            return AssetRecognitionDecision.MANUAL_REVIEW
        if confidence < self.SUGGESTION_CONFIDENCE_THRESHOLD:
            if AssetReviewReason.CONFIDENCE_BELOW_THRESHOLD not in review_reasons:
                review_reasons.append(AssetReviewReason.CONFIDENCE_BELOW_THRESHOLD)
            return AssetRecognitionDecision.MANUAL_REVIEW
        if gwg_eligible:
            return AssetRecognitionDecision.GWG_SUGGESTION
        if (
            confidence >= self.AUTO_CREATE_CONFIDENCE_THRESHOLD
            and data.document_type in {"purchase_contract", "kaufvertrag"}
            and not missing_fields
            and not review_reasons
            and candidate.asset_subtype is not None
        ):
            return AssetRecognitionDecision.CREATE_ASSET_AUTO
        return AssetRecognitionDecision.CREATE_ASSET_SUGGESTION

    def _expense_result(
        self,
        data: AssetRecognitionInput,
        reason_code: AssetReasonCode,
        review_reason: AssetReviewReason | None = None,
    ) -> AssetRecognitionResult:
        review_reasons = [review_reason] if review_reason else []
        return AssetRecognitionResult(
            decision=AssetRecognitionDecision.EXPENSE_ONLY,
            asset_candidate=AssetCandidate(
                asset_name=self._suggest_asset_name(data),
                vendor_name=data.extracted_vendor,
            ),
            tax_flags=AssetTaxFlags(
                depreciable=False,
                gwg_eligible=False,
                gwg_default_selected=False,
                gwg_election_required=False,
                comparison_basis=ComparisonBasis.GROSS,
                comparison_amount=data.extracted_amount,
                vat_recoverable_status=VatRecoverableStatus.UNCLEAR,
                ifb_candidate=False,
                ifb_rate=None,
                half_year_rule_applicable=False,
                allowed_depreciation_methods=[],
                suggested_depreciation_method=None,
                suggested_useful_life_years=None,
                policy_anchor_date=self._resolve_policy_anchor_date(data),
            ),
            reason_codes=[reason_code],
            review_reasons=review_reasons,
            missing_fields=[],
            requires_user_confirmation=False,
            policy_confidence=Decimal("0.98"),
            policy_rule_ids=[],
            duplicate=DuplicateAssessment(),
        )

    def _manual_review_result(
        self,
        data: AssetRecognitionInput,
        candidate: AssetCandidate,
        reason_codes: list[AssetReasonCode],
        review_reasons: list[AssetReviewReason],
        missing_fields: list[str],
        comparison_basis: ComparisonBasis,
        comparison_amount: Decimal,
        policy_anchor_date: date,
    ) -> AssetRecognitionResult:
        return AssetRecognitionResult(
            decision=AssetRecognitionDecision.MANUAL_REVIEW,
            asset_candidate=candidate,
            tax_flags=AssetTaxFlags(
                depreciable=False,
                gwg_eligible=False,
                gwg_default_selected=False,
                gwg_election_required=False,
                comparison_basis=comparison_basis,
                comparison_amount=comparison_amount,
                vat_recoverable_status=VatRecoverableStatus.UNCLEAR,
                ifb_candidate=False,
                ifb_rate=None,
                half_year_rule_applicable=False,
                allowed_depreciation_methods=[DepreciationMethod.LINEAR],
                suggested_depreciation_method=DepreciationMethod.LINEAR,
                suggested_useful_life_years=None,
                policy_anchor_date=policy_anchor_date,
            ),
            reason_codes=reason_codes,
            review_reasons=review_reasons,
            missing_fields=missing_fields,
            requires_user_confirmation=True,
            policy_confidence=Decimal("0.50"),
            policy_rule_ids=[],
            duplicate=DuplicateAssessment(),
        )

    def _duplicate_result(
        self,
        data: AssetRecognitionInput,
        duplicate: DuplicateAssessment,
        *,
        suspected: bool,
    ) -> AssetRecognitionResult:
        review_reasons = [AssetReviewReason.DUPLICATE_SUSPECTED] if suspected else []
        return AssetRecognitionResult(
            decision=AssetRecognitionDecision.DUPLICATE_WARNING,
            asset_candidate=AssetCandidate(
                asset_name=self._suggest_asset_name(data),
                vendor_name=data.extracted_vendor,
            ),
            tax_flags=AssetTaxFlags(
                depreciable=False,
                gwg_eligible=False,
                gwg_default_selected=False,
                gwg_election_required=False,
                comparison_basis=ComparisonBasis.GROSS,
                comparison_amount=data.extracted_amount,
                vat_recoverable_status=VatRecoverableStatus.UNCLEAR,
                ifb_candidate=False,
                ifb_rate=None,
                half_year_rule_applicable=False,
                allowed_depreciation_methods=[],
                suggested_depreciation_method=None,
                suggested_useful_life_years=None,
                policy_anchor_date=self._resolve_policy_anchor_date(data),
            ),
            reason_codes=duplicate.duplicate_reason_codes,
            review_reasons=review_reasons,
            missing_fields=[],
            requires_user_confirmation=True,
            policy_confidence=Decimal("0.99") if not suspected else Decimal("0.80"),
            policy_rule_ids=[],
            duplicate=duplicate,
        )
