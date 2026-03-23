from datetime import date, datetime
from decimal import Decimal

from app.schemas.asset_recognition import (
    AssetCandidate,
    AssetRecognitionInput,
    AssetReviewReason,
    Gewinnermittlungsart,
    VatStatus,
)
from app.services.asset_tax_policy_service import AssetTaxPolicyService


def make_input(**overrides) -> AssetRecognitionInput:
    payload = {
        "extracted_amount": Decimal("1499.00"),
        "extracted_net_amount": Decimal("1249.17"),
        "extracted_vat_amount": Decimal("249.83"),
        "extracted_date": date(2026, 3, 10),
        "extracted_vendor": "Example Supplier GmbH",
        "extracted_invoice_number": "INV-200",
        "extracted_line_items": [{"description": "Laptop"}],
        "document_language": "de",
        "raw_text": "Rechnung Laptop Computer",
        "document_type": "invoice",
        "ocr_confidence": Decimal("0.92"),
        "vat_status": VatStatus.REGELBESTEUERT,
        "gewinnermittlungsart": Gewinnermittlungsart.EA_RECHNUNG,
        "business_type": "freiberufler",
        "source_document_id": 55,
        "upload_timestamp": datetime(2026, 3, 18, 10, 0, 0),
    }
    payload.update(overrides)
    return AssetRecognitionInput(**payload)


def make_candidate(**overrides) -> AssetCandidate:
    payload = {
        "asset_type": "computer",
        "asset_subtype": "computer",
        "asset_name": "Laptop",
        "vendor_name": "Example Supplier GmbH",
        "is_used_asset": False,
    }
    payload.update(overrides)
    return AssetCandidate(**payload)


def test_policy_service_applies_2026_ifb_window_and_degressive():
    service = AssetTaxPolicyService()

    evaluation = service.evaluate(
        make_input(
            raw_text="Rechnung CNC Maschine Produktionsanlage",
            extracted_line_items=[{"description": "CNC Maschine"}],
        ),
        make_candidate(
            asset_type="machinery",
            asset_subtype="machinery",
            asset_name="CNC Maschine",
        ),
    )

    assert evaluation.tax_flags.ifb_candidate is True
    assert evaluation.tax_flags.ifb_rate == Decimal("0.20")
    assert evaluation.tax_flags.ifb_rate_source == "statutory_window"
    assert evaluation.tax_flags.allowed_depreciation_methods == ["linear", "degressive"]
    assert evaluation.tax_flags.degressive_max_rate == Decimal("0.30")
    assert "IFB-003" in evaluation.rule_ids
    assert "DEP-METH-002" in evaluation.rule_ids


def test_policy_service_marks_future_ifb_window_as_review():
    service = AssetTaxPolicyService()

    evaluation = service.evaluate(
        make_input(
            extracted_date=date(2027, 1, 15),
            upload_timestamp=datetime(2027, 1, 16, 10, 0, 0),
            put_into_use_date=date(2027, 1, 20),
            raw_text="Rechnung Produktionsmaschine",
        ),
        make_candidate(
            asset_type="machinery",
            asset_subtype="machinery",
            asset_name="Produktionsmaschine",
        ),
    )

    assert evaluation.tax_flags.ifb_candidate is True
    assert evaluation.tax_flags.ifb_rate is None
    assert evaluation.tax_flags.ifb_rate_source == "fallback_default"
    assert AssetReviewReason.IFB_FUTURE_WINDOW_UNKNOWN in evaluation.review_reasons
    assert "IFB-004" in evaluation.rule_ids


def test_policy_service_applies_pkw_cost_cap_and_vat_block():
    service = AssetTaxPolicyService()

    evaluation = service.evaluate(
        make_input(
            extracted_amount=Decimal("60000.00"),
            extracted_net_amount=Decimal("50000.00"),
            extracted_vat_amount=Decimal("10000.00"),
            raw_text="Kaufvertrag PKW Fahrgestellnummer",
            put_into_use_date=date(2026, 4, 1),
        ),
        make_candidate(
            asset_type="vehicle",
            asset_subtype="pkw",
            asset_name="Business Car",
            is_used_asset=False,
        ),
    )

    assert evaluation.tax_flags.income_tax_cost_cap == Decimal("40000.00")
    assert evaluation.tax_flags.income_tax_depreciable_base == Decimal("40000.00")
    assert evaluation.tax_flags.vat_recoverable_status == "likely_no"
    assert evaluation.tax_flags.allowed_depreciation_methods == ["linear"]
    assert evaluation.tax_flags.suggested_useful_life_years == Decimal("8")
    assert "VEH-001" in evaluation.rule_ids
    assert "VEH-002" in evaluation.rule_ids


def test_policy_service_treats_fiscal_truck_as_non_pkw_vehicle():
    service = AssetTaxPolicyService()

    evaluation = service.evaluate(
        make_input(
            extracted_amount=Decimal("22000.00"),
            extracted_net_amount=Decimal("18333.33"),
            extracted_vat_amount=Decimal("3666.67"),
            raw_text="Rechnung Fiskal-LKW Kastenwagen",
            put_into_use_date=date(2026, 2, 1),
        ),
        make_candidate(
            asset_type="machinery",
            asset_subtype="fiscal_truck",
            asset_name="Kastenwagen",
            is_used_asset=False,
        ),
    )

    assert evaluation.tax_flags.vat_recoverable_status == "likely_yes"
    assert evaluation.tax_flags.income_tax_cost_cap is None
    assert evaluation.tax_flags.suggested_useful_life_years == Decimal("5")
    assert "VEH-004" in evaluation.rule_ids


def test_policy_service_marks_vat_boundary_ambiguity_for_manual_review():
    service = AssetTaxPolicyService()

    evaluation = service.evaluate(
        make_input(
            vat_status=VatStatus.UNKNOWN,
            extracted_amount=Decimal("1100.00"),
            extracted_net_amount=Decimal("916.67"),
            extracted_vat_amount=Decimal("183.33"),
            extracted_date=date(2026, 6, 1),
        ),
        make_candidate(),
    )

    assert AssetReviewReason.VAT_STATUS_UNKNOWN in evaluation.review_reasons
    assert AssetReviewReason.THRESHOLD_BOUNDARY_AMBIGUOUS in evaluation.review_reasons
    assert "MR-003" in evaluation.rule_ids
