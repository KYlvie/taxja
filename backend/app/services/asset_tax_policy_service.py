"""Centralized Austrian asset tax policy evaluation."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.schemas.asset_recognition import (
    AssetCandidate,
    AssetReasonCode,
    AssetRecognitionInput,
    AssetReviewReason,
    AssetTaxFlags,
    AssetTaxPolicyEvaluation,
    ComparisonBasis,
    DepreciationMethod,
    IfbRateSource,
    UsefulLifeSource,
    VatRecoverableStatus,
)


class AssetTaxPolicyService:
    """Apply frozen Austrian tax rules to an asset candidate."""

    DEGRESSIVE_MAX_RATE = Decimal("0.30")
    GWG_THRESHOLD_2022 = Decimal("800.00")
    GWG_THRESHOLD_2023 = Decimal("1000.00")
    INCOME_TAX_COST_CAP_PKW = Decimal("40000.00")

    # E-Auto Vorsteuer thresholds (BMF)
    EAUTO_VST_FULL_THRESHOLD = Decimal("40000.00")   # 100% VSt deduction up to €40k brutto AK
    EAUTO_VST_ZERO_THRESHOLD = Decimal("80000.00")   # 0% VSt above €80k brutto AK
    # Between €40k-€80k: abziehbare_vst = gesamte_vst × (40000 / brutto_ak)

    def evaluate(
        self,
        data: AssetRecognitionInput,
        candidate: AssetCandidate,
    ) -> AssetTaxPolicyEvaluation:
        reason_codes: list[AssetReasonCode] = []
        review_reasons: list[AssetReviewReason] = []
        missing_fields: list[str] = []
        rule_ids: list[str] = []

        comparison_basis = self._resolve_comparison_basis(
            data=data,
            reason_codes=reason_codes,
            review_reasons=review_reasons,
            rule_ids=rule_ids,
        )
        policy_anchor_date = self.resolve_policy_anchor_date(data)
        comparison_amount = self._resolve_comparison_amount(
            data=data,
            basis=comparison_basis,
        )

        depreciable = bool(candidate.asset_subtype)
        useful_life_years, useful_life_source = self._resolve_useful_life(
            data=data,
            candidate=candidate,
            review_reasons=review_reasons,
            missing_fields=missing_fields,
            rule_ids=rule_ids,
        )

        if data.put_into_use_date is None:
            missing_fields.append("put_into_use_date")
            review_reasons.append(AssetReviewReason.PUT_INTO_USE_DATE_MISSING)
            rule_ids.append("HJ-002")

        half_year_rule_applicable = bool(
            data.put_into_use_date and data.put_into_use_date.month >= 7
        )
        if data.put_into_use_date:
            rule_ids.append("HJ-001")

        gwg_threshold = self._resolve_gwg_threshold(policy_anchor_date, rule_ids)
        gwg_eligible = bool(
            depreciable
            and useful_life_years is not None
            and useful_life_years > Decimal("1")
            and comparison_amount <= gwg_threshold
        )
        if depreciable:
            rule_ids.append("GWG-001")
        if gwg_eligible:
            reason_codes.append(AssetReasonCode.AMOUNT_WITHIN_GWG_THRESHOLD)
            rule_ids.append("GWG-004")
        else:
            reason_codes.append(AssetReasonCode.AMOUNT_ABOVE_GWG_THRESHOLD)

        self._apply_boundary_review_if_needed(
            data=data,
            gwg_threshold=gwg_threshold,
            review_reasons=review_reasons,
            rule_ids=rule_ids,
        )

        allowed_methods, suggested_method, degressive_max_rate = self._resolve_depreciation_methods(
            data=data,
            candidate=candidate,
            reason_codes=reason_codes,
            rule_ids=rule_ids,
        )
        (
            income_tax_cost_cap,
            income_tax_depreciable_base,
        ) = self._resolve_income_tax_cap(
            candidate=candidate,
            comparison_amount=comparison_amount,
            reason_codes=reason_codes,
            rule_ids=rule_ids,
        )
        (
            vat_recoverable_status,
            vat_reason_codes,
            vat_recoverable_ratio,
        ) = self._resolve_vat_recoverable_status(
            data=data,
            candidate=candidate,
            comparison_amount=comparison_amount,
            reason_codes=reason_codes,
            rule_ids=rule_ids,
        )
        (
            ifb_candidate,
            ifb_rate,
            ifb_rate_source,
            ifb_exclusion_codes,
        ) = self._resolve_ifb(
            data=data,
            candidate=candidate,
            depreciable=depreciable,
            useful_life_years=useful_life_years,
            gwg_eligible=gwg_eligible,
            reason_codes=reason_codes,
            review_reasons=review_reasons,
            rule_ids=rule_ids,
        )

        tax_flags = AssetTaxFlags(
            depreciable=depreciable,
            gwg_eligible=gwg_eligible,
            gwg_default_selected=gwg_eligible,
            gwg_election_required=gwg_eligible,
            comparison_basis=comparison_basis,
            comparison_amount=comparison_amount,
            vat_recoverable_status=vat_recoverable_status,
            ifb_candidate=ifb_candidate,
            ifb_rate=ifb_rate,
            half_year_rule_applicable=half_year_rule_applicable,
            allowed_depreciation_methods=allowed_methods,
            suggested_depreciation_method=suggested_method,
            suggested_useful_life_years=useful_life_years,
            policy_anchor_date=policy_anchor_date,
            gwg_threshold=gwg_threshold,
            degressive_max_rate=degressive_max_rate,
            useful_life_source=useful_life_source,
            income_tax_cost_cap=income_tax_cost_cap,
            income_tax_depreciable_base=income_tax_depreciable_base,
            vat_recoverable_ratio=vat_recoverable_ratio,
            vat_recoverable_reason_codes=vat_reason_codes,
            ifb_rate_source=ifb_rate_source,
            ifb_exclusion_codes=ifb_exclusion_codes,
        )

        return AssetTaxPolicyEvaluation(
            tax_flags=tax_flags,
            reason_codes=reason_codes,
            review_reasons=review_reasons,
            missing_fields=missing_fields,
            rule_ids=self._unique(rule_ids),
        )

    def resolve_policy_anchor_date(self, data: AssetRecognitionInput) -> date:
        return (
            data.put_into_use_date
            or data.payment_date
            or data.extracted_date
            or data.upload_timestamp.date()
        )

    def _resolve_comparison_basis(
        self,
        *,
        data: AssetRecognitionInput,
        reason_codes: list[AssetReasonCode],
        review_reasons: list[AssetReviewReason],
        rule_ids: list[str],
    ) -> ComparisonBasis:
        rule_ids.append("VAT-001")
        if data.vat_status == "regelbesteuert":
            reason_codes.append(AssetReasonCode.COMPARISON_BASIS_NET)
            return ComparisonBasis.NET
        if data.vat_status == "kleinunternehmer":
            reason_codes.append(AssetReasonCode.COMPARISON_BASIS_GROSS)
            return ComparisonBasis.GROSS
        reason_codes.append(AssetReasonCode.COMPARISON_BASIS_GROSS)
        review_reasons.append(AssetReviewReason.VAT_STATUS_UNKNOWN)
        return ComparisonBasis.GROSS

    def _resolve_comparison_amount(
        self,
        *,
        data: AssetRecognitionInput,
        basis: ComparisonBasis,
    ) -> Decimal:
        if basis == ComparisonBasis.NET:
            if data.extracted_net_amount is not None:
                return data.extracted_net_amount
            if data.extracted_vat_amount is not None:
                return data.extracted_amount - data.extracted_vat_amount
        return data.extracted_amount

    def _resolve_gwg_threshold(
        self,
        anchor: date,
        rule_ids: list[str],
    ) -> Decimal:
        if anchor <= date(2022, 12, 31):
            rule_ids.append("GWG-002")
            return self.GWG_THRESHOLD_2022
        rule_ids.append("GWG-003")
        return self.GWG_THRESHOLD_2023

    def _resolve_useful_life(
        self,
        *,
        data: AssetRecognitionInput,
        candidate: AssetCandidate,
        review_reasons: list[AssetReviewReason],
        missing_fields: list[str],
        rule_ids: list[str],
    ) -> tuple[Decimal | None, UsefulLifeSource | None]:
        subtype = candidate.asset_subtype
        is_used = bool(candidate.is_used_asset)
        prior_usage_years = data.prior_owner_usage_years

        if subtype is None:
            return None, None

        if subtype == "pkw":
            rule_ids.append("LIFE-001")
            if is_used:
                rule_ids.append("VEH-005")
                if prior_usage_years is None and data.first_registration_date is None:
                    review_reasons.append(AssetReviewReason.USED_VEHICLE_HISTORY_MISSING)
                    missing_fields.append("prior_owner_usage_years_or_first_registration_date")
                    return Decimal("8"), UsefulLifeSource.LAW
                if prior_usage_years is not None:
                    remaining = Decimal("8") - prior_usage_years
                    return (remaining if remaining > Decimal("3") else Decimal("3")), UsefulLifeSource.TAX_PRACTICE
            return Decimal("8"), UsefulLifeSource.LAW

        if subtype == "electric_pkw":
            rule_ids.append("LIFE-002")
            if is_used and prior_usage_years is not None:
                remaining = Decimal("8") - prior_usage_years
                return (remaining if remaining > Decimal("3") else Decimal("3")), UsefulLifeSource.TAX_PRACTICE
            return Decimal("8"), UsefulLifeSource.LAW

        if subtype in {"truck_van", "fiscal_truck"}:
            rule_ids.append("LIFE-003")
            return Decimal("5"), UsefulLifeSource.TAX_PRACTICE

        if subtype in {"computer", "phone", "perpetual_license"}:
            rule_ids.append("LIFE-004")
            return Decimal("3"), UsefulLifeSource.SYSTEM_DEFAULT

        if subtype in {"office_furniture", "machinery"}:
            rule_ids.append("LIFE-005")
            return Decimal("10"), UsefulLifeSource.SYSTEM_DEFAULT

        defaults = {
            "motorcycle": Decimal("5"),
            "printer_scanner": Decimal("5"),
            "monitor_av": Decimal("5"),
            "server_network": Decimal("5"),
            "tools": Decimal("5"),
            "retail_equipment": Decimal("5"),
            "restaurant_equipment": Decimal("10"),
            "medical_beauty_equipment": Decimal("10"),
            "leasehold_improvement": Decimal("10"),
            "renewable_energy": Decimal("10"),
            "bike_mobility": Decimal("5"),
            "other_equipment": Decimal("5"),
        }
        return defaults.get(subtype, Decimal("5")), UsefulLifeSource.SYSTEM_DEFAULT

    def _resolve_depreciation_methods(
        self,
        *,
        data: AssetRecognitionInput,
        candidate: AssetCandidate,
        reason_codes: list[AssetReasonCode],
        rule_ids: list[str],
    ) -> tuple[list[DepreciationMethod], DepreciationMethod, Decimal | None]:
        methods = [DepreciationMethod.LINEAR]
        suggested = DepreciationMethod.LINEAR
        degressive_max_rate: Decimal | None = None
        anchor = self.resolve_policy_anchor_date(data)
        subtype = candidate.asset_subtype
        is_used = bool(candidate.is_used_asset)

        rule_ids.append("DEP-METH-001")

        if subtype == "pkw":
            reason_codes.append(AssetReasonCode.PKW_DETECTED)
            reason_codes.append(AssetReasonCode.DEGRESSIVE_BLOCKED_PKW)
            return methods, suggested, degressive_max_rate

        if subtype == "electric_pkw":
            reason_codes.append(AssetReasonCode.ELECTRIC_VEHICLE_DETECTED)
            rule_ids.append("DEP-METH-003")

        if is_used:
            reason_codes.append(AssetReasonCode.USED_ASSET_DETECTED)
            reason_codes.append(AssetReasonCode.DEGRESSIVE_BLOCKED_USED_ASSET)
            rule_ids.append("DEP-METH-002")
            return methods, suggested, degressive_max_rate

        if anchor >= date(2020, 7, 1):
            methods.append(DepreciationMethod.DEGRESSIVE)
            degressive_max_rate = self.DEGRESSIVE_MAX_RATE
            reason_codes.append(AssetReasonCode.DEGRESSIVE_ALLOWED)
            rule_ids.append("DEP-METH-002")

        return methods, suggested, degressive_max_rate

    def _resolve_income_tax_cap(
        self,
        *,
        candidate: AssetCandidate,
        comparison_amount: Decimal,
        reason_codes: list[AssetReasonCode],
        rule_ids: list[str],
    ) -> tuple[Decimal | None, Decimal]:
        subtype = candidate.asset_subtype
        if subtype in {"pkw", "electric_pkw"}:
            rule_ids.extend(["VEH-001", "VEH-002"] if subtype == "pkw" else ["VEH-002", "VEH-003"])
            if subtype == "pkw":
                reason_codes.append(AssetReasonCode.PKW_DETECTED)
            else:
                reason_codes.append(AssetReasonCode.ELECTRIC_VEHICLE_DETECTED)
            return self.INCOME_TAX_COST_CAP_PKW, min(comparison_amount, self.INCOME_TAX_COST_CAP_PKW)
        if subtype == "fiscal_truck":
            rule_ids.append("VEH-004")
        return None, comparison_amount

    def _resolve_vat_recoverable_status(
        self,
        *,
        data: AssetRecognitionInput,
        candidate: AssetCandidate,
        comparison_amount: Decimal,
        reason_codes: list[AssetReasonCode],
        rule_ids: list[str],
    ) -> tuple[VatRecoverableStatus, list[AssetReasonCode], Decimal | None]:
        """Resolve VAT recoverability status and ratio.

        Returns:
            (status, reason_codes, vat_recoverable_ratio)
            ratio is None for non-vehicle assets, 0 for PKW, 1 for fiscal_truck,
            and a calculated value for electric_pkw based on BMF Staffelung.
        """
        subtype = candidate.asset_subtype
        reason_list: list[AssetReasonCode] = []

        if data.vat_status != "regelbesteuert":
            return VatRecoverableStatus.LIKELY_NO, reason_list, None

        if subtype == "pkw":
            rule_ids.append("VEH-001")
            if AssetReasonCode.PKW_DETECTED not in reason_codes:
                reason_codes.append(AssetReasonCode.PKW_DETECTED)
            reason_list.append(AssetReasonCode.PKW_DETECTED)
            return VatRecoverableStatus.LIKELY_NO, reason_list, Decimal("0.00")

        if subtype == "electric_pkw":
            rule_ids.append("VEH-003")
            if AssetReasonCode.ELECTRIC_VEHICLE_DETECTED not in reason_codes:
                reason_codes.append(AssetReasonCode.ELECTRIC_VEHICLE_DETECTED)
            reason_list.append(AssetReasonCode.ELECTRIC_VEHICLE_DETECTED)

            # E-Auto VSt Staffelung (BMF):
            #   ≤ €40,000 brutto AK → 100% Vorsteuerabzug
            #   €40,000 – €80,000   → abziehbare_vst = gesamte_vst × (40000 / brutto_ak)
            #   > €80,000            → 0% Vorsteuerabzug
            # Use extracted_amount (gross) as brutto AK for the formula.
            brutto_ak = data.extracted_amount
            ratio = self._calculate_eauto_vst_ratio(brutto_ak)
            if ratio >= Decimal("1"):
                status = VatRecoverableStatus.LIKELY_YES
            elif ratio <= Decimal("0"):
                status = VatRecoverableStatus.LIKELY_NO
            else:
                status = VatRecoverableStatus.PARTIAL
            return status, reason_list, ratio.quantize(Decimal("0.0001"))

        if subtype == "fiscal_truck":
            rule_ids.append("VEH-004")
            return VatRecoverableStatus.LIKELY_YES, reason_list, Decimal("1.00")

        return VatRecoverableStatus.LIKELY_YES, reason_list, None

    def _calculate_eauto_vst_ratio(self, brutto_ak: Decimal) -> Decimal:
        """Calculate E-Auto Vorsteuer deduction ratio per BMF Staffelung.

        Formula: abziehbare_vst = gesamte_vst × (40000 / brutto_ak)
        - ≤ €40,000: ratio = 1.0 (full deduction)
        - €40,000 – €80,000: ratio = 40000 / brutto_ak
        - > €80,000: ratio = 0.0 (no deduction)
        """
        if brutto_ak <= self.EAUTO_VST_FULL_THRESHOLD:
            return Decimal("1.0000")
        if brutto_ak > self.EAUTO_VST_ZERO_THRESHOLD:
            return Decimal("0.0000")
        return (self.EAUTO_VST_FULL_THRESHOLD / brutto_ak).quantize(Decimal("0.0001"))

    def _resolve_ifb(
        self,
        *,
        data: AssetRecognitionInput,
        candidate: AssetCandidate,
        depreciable: bool,
        useful_life_years: Decimal | None,
        gwg_eligible: bool,
        reason_codes: list[AssetReasonCode],
        review_reasons: list[AssetReviewReason],
        rule_ids: list[str],
    ) -> tuple[bool, Decimal | None, IfbRateSource, list[AssetReasonCode]]:
        subtype = candidate.asset_subtype
        is_used = bool(candidate.is_used_asset)
        exclusions: list[AssetReasonCode] = []
        rule_ids.append("IFB-001")

        if not depreciable or useful_life_years is None or useful_life_years < Decimal("4"):
            exclusions.append(AssetReasonCode.IFB_BLOCKED_SHORT_USEFUL_LIFE)
            return False, None, IfbRateSource.NOT_APPLICABLE, exclusions

        if gwg_eligible:
            exclusions.append(AssetReasonCode.IFB_BLOCKED_GWG)
            return False, None, IfbRateSource.NOT_APPLICABLE, exclusions

        if is_used:
            exclusions.append(AssetReasonCode.IFB_BLOCKED_USED_ASSET)
            return False, None, IfbRateSource.NOT_APPLICABLE, exclusions

        if subtype == "pkw":
            exclusions.append(AssetReasonCode.IFB_BLOCKED_ORDINARY_PKW)
            return False, None, IfbRateSource.NOT_APPLICABLE, exclusions

        if subtype == "perpetual_license" and not self._qualifies_special_intangible_ifb(data):
            rule_ids.append("SW-003")
            exclusions.append(AssetReasonCode.IFB_BLOCKED_NONQUALIFYING_INTANGIBLE)
            return False, None, IfbRateSource.NOT_APPLICABLE, exclusions

        anchor = self.resolve_policy_anchor_date(data)
        is_eco = subtype in {"electric_pkw", "renewable_energy"}
        if anchor < date(2023, 1, 1):
            return False, None, IfbRateSource.NOT_APPLICABLE, exclusions
        if date(2023, 1, 1) <= anchor <= date(2025, 10, 31):
            rule_ids.append("IFB-002")
            rate = Decimal("0.15") if is_eco else Decimal("0.10")
            reason_codes.append(
                AssetReasonCode.IFB_CANDIDATE_ECO if is_eco else AssetReasonCode.IFB_CANDIDATE_STANDARD
            )
            return True, rate, IfbRateSource.STATUTORY_WINDOW, exclusions
        if date(2025, 11, 1) <= anchor <= date(2026, 12, 31):
            rule_ids.append("IFB-003")
            rate = Decimal("0.22") if is_eco else Decimal("0.20")
            reason_codes.append(
                AssetReasonCode.IFB_CANDIDATE_ECO if is_eco else AssetReasonCode.IFB_CANDIDATE_STANDARD
            )
            return True, rate, IfbRateSource.STATUTORY_WINDOW, exclusions

        rule_ids.append("IFB-004")
        review_reasons.append(AssetReviewReason.IFB_FUTURE_WINDOW_UNKNOWN)
        return True, None, IfbRateSource.FALLBACK_DEFAULT, exclusions

    def _apply_boundary_review_if_needed(
        self,
        *,
        data: AssetRecognitionInput,
        gwg_threshold: Decimal,
        review_reasons: list[AssetReviewReason],
        rule_ids: list[str],
    ) -> None:
        if data.vat_status != "unknown" or data.extracted_net_amount is None:
            return
        gross_is_gwg = data.extracted_amount <= gwg_threshold
        net_is_gwg = data.extracted_net_amount <= gwg_threshold
        if gross_is_gwg != net_is_gwg:
            review_reasons.append(AssetReviewReason.THRESHOLD_BOUNDARY_AMBIGUOUS)
            rule_ids.append("MR-003")

    def _qualifies_special_intangible_ifb(self, data: AssetRecognitionInput) -> bool:
        text = " ".join(
            [
                data.raw_text or "",
                " ".join(str(item) for item in data.extracted_line_items or []),
            ]
        ).lower()
        qualifying_markers = [
            "erp",
            "crm",
            "digital",
            "digitalisierung",
            "automation",
            "health",
            "gesund",
            "life science",
            "medizin",
            "eco",
            "klima",
        ]
        return any(marker in text for marker in qualifying_markers)

    def _unique(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                unique_values.append(value)
        return unique_values

