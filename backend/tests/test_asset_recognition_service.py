from datetime import date, datetime
from decimal import Decimal

from app.schemas.asset_recognition import (
    AssetRecognitionDecision,
    AssetRecognitionInput,
    AssetReviewReason,
    DuplicateCandidate,
    Gewinnermittlungsart,
    VatStatus,
)
from app.services.asset_recognition_service import AssetRecognitionService


def make_input(**overrides) -> AssetRecognitionInput:
    payload = {
        "extracted_amount": Decimal("1499.00"),
        "extracted_net_amount": Decimal("1249.17"),
        "extracted_vat_amount": Decimal("249.83"),
        "extracted_date": date(2026, 3, 10),
        "extracted_vendor": "Example Supplier GmbH",
        "extracted_invoice_number": "INV-100",
        "extracted_line_items": [{"description": "MacBook Pro 14"}],
        "document_language": "de",
        "raw_text": "Rechnung MacBook Pro 14 Laptop Computer Lieferung",
        "document_type": "invoice",
        "ocr_confidence": Decimal("0.92"),
        "vat_status": VatStatus.REGELBESTEUERT,
        "gewinnermittlungsart": Gewinnermittlungsart.EA_RECHNUNG,
        "business_type": "freiberufler",
        "source_document_id": 12,
        "upload_timestamp": datetime(2026, 3, 18, 10, 0, 0),
    }
    payload.update(overrides)
    return AssetRecognitionInput(**payload)


def test_recognize_service_invoice_as_expense_only():
    service = AssetRecognitionService()

    result = service.recognize(
        make_input(
            raw_text="Wartungsvertrag Cloud Hosting Support monatlich",
            extracted_line_items=[{"description": "Cloud subscription monthly"}],
        )
    )

    assert result.decision == AssetRecognitionDecision.EXPENSE_ONLY
    assert result.requires_user_confirmation is False
    assert result.tax_flags.depreciable is False


def test_recognize_computer_invoice_above_gwg_creates_asset_suggestion():
    service = AssetRecognitionService()

    result = service.recognize(make_input())

    assert result.decision == AssetRecognitionDecision.CREATE_ASSET_SUGGESTION
    assert result.asset_candidate.asset_subtype == "computer"
    assert result.tax_flags.comparison_basis == "net"
    assert result.tax_flags.comparison_amount == Decimal("1249.17")
    assert result.tax_flags.gwg_eligible is False
    assert result.tax_flags.ifb_candidate is False
    assert result.tax_flags.ifb_rate is None
    assert result.tax_flags.ifb_rate_source == "not_applicable"
    assert "put_into_use_date" in result.missing_fields
    assert result.tax_flags.allowed_depreciation_methods == ["linear", "degressive"]
    assert "VAT-001" in result.policy_rule_ids
    assert "IFB-001" in result.policy_rule_ids


def test_recognize_gwg_suggestion_uses_2023_threshold():
    service = AssetRecognitionService()

    result = service.recognize(
        make_input(
            extracted_amount=Decimal("999.00"),
            extracted_net_amount=Decimal("832.50"),
            extracted_vat_amount=Decimal("166.50"),
            raw_text="Rechnung Schreibtisch Bueromoebel",
            extracted_line_items=[{"description": "Schreibtisch"}],
        )
    )

    assert result.decision == AssetRecognitionDecision.GWG_SUGGESTION
    assert result.tax_flags.gwg_eligible is True
    assert result.tax_flags.gwg_election_required is True


def test_recognize_perpetual_license_invoice_as_gwg_asset():
    service = AssetRecognitionService()

    result = service.recognize(
        make_input(
            extracted_amount=Decimal("599.00"),
            extracted_net_amount=Decimal("499.17"),
            extracted_vat_amount=Decimal("99.83"),
            raw_text=(
                "Rechnung JetBrains IntelliJ IDEA Ultimate Perpetual Fallback License "
                "Perpetual license Anlagegut Nutzungsdauer 4 Jahre"
            ),
            extracted_line_items=[
                {"description": "IntelliJ IDEA Ultimate Perpetual Fallback License"}
            ],
        )
    )

    assert result.asset_candidate.asset_subtype == "perpetual_license"
    assert result.decision == AssetRecognitionDecision.GWG_SUGGESTION
    assert result.tax_flags.gwg_eligible is True


def test_recognize_phone_invoice_as_gwg_asset():
    service = AssetRecognitionService()

    result = service.recognize(
        make_input(
            extracted_amount=Decimal("999.00"),
            extracted_net_amount=Decimal("832.50"),
            extracted_vat_amount=Decimal("166.50"),
            raw_text="Rechnung Apple iPhone 15 Pro 256GB Smartphone Handy",
            extracted_line_items=[{"description": "Apple iPhone 15 Pro 256GB"}],
        )
    )

    assert result.asset_candidate.asset_subtype == "phone"
    assert result.decision == AssetRecognitionDecision.GWG_SUGGESTION
    assert result.tax_flags.gwg_eligible is True


def test_recognize_2022_anchor_uses_old_gwg_threshold():
    service = AssetRecognitionService()

    result = service.recognize(
        make_input(
            extracted_amount=Decimal("900.00"),
            extracted_net_amount=Decimal("750.00"),
            extracted_vat_amount=Decimal("150.00"),
            extracted_date=date(2022, 6, 15),
            raw_text="Rechnung Laptop Computer",
            extracted_line_items=[{"description": "Laptop"}],
        )
    )

    assert result.tax_flags.comparison_amount == Decimal("750.00")
    assert result.tax_flags.gwg_eligible is True

    result_klein = service.recognize(
        make_input(
            extracted_amount=Decimal("900.00"),
            extracted_net_amount=Decimal("750.00"),
            extracted_vat_amount=Decimal("150.00"),
            extracted_date=date(2022, 6, 15),
            vat_status=VatStatus.KLEINUNTERNEHMER,
            raw_text="Rechnung Laptop Computer",
            extracted_line_items=[{"description": "Laptop"}],
        )
    )

    assert result_klein.tax_flags.comparison_basis == "gross"
    assert result_klein.tax_flags.gwg_eligible is False
    assert result_klein.decision == AssetRecognitionDecision.CREATE_ASSET_SUGGESTION


def test_duplicate_hash_returns_duplicate_warning():
    service = AssetRecognitionService()

    result = service.recognize(
        make_input(
            file_hash="abc123",
            duplicate_document_candidates=[
                DuplicateCandidate(
                    matched_document_id=22,
                    file_hash="abc123",
                )
            ],
        )
    )

    assert result.decision == AssetRecognitionDecision.DUPLICATE_WARNING
    assert result.duplicate.duplicate_status == "high_confidence"
    assert result.duplicate.matched_document_id == 22


def test_similar_existing_asset_does_not_block_repeat_asset_purchase():
    service = AssetRecognitionService()

    result = service.recognize(
        make_input(
            extracted_amount=Decimal("999.00"),
            extracted_net_amount=Decimal("832.50"),
            extracted_vat_amount=Decimal("166.50"),
            raw_text="Rechnung Apple iPhone 15 Pro 256GB Smartphone Handy",
            extracted_line_items=[{"description": "Apple iPhone 15 Pro 256GB"}],
            duplicate_asset_candidates=[
                DuplicateCandidate(
                    matched_asset_id="asset-1",
                    vendor_name="Example Supplier GmbH",
                    amount_gross=Decimal("999.00"),
                    document_date=date(2026, 3, 10),
                )
            ],
        )
    )

    assert result.decision == AssetRecognitionDecision.GWG_SUGGESTION
    assert result.duplicate.duplicate_status == "none"


def test_used_pkw_blocks_degressive_and_ifb():
    service = AssetRecognitionService()

    result = service.recognize(
        make_input(
            raw_text="Kaufvertrag gebrauchte PKW Fahrgestellnummer Kennzeichen Erstzulassung",
            document_type="purchase_contract",
            put_into_use_date=date(2026, 3, 20),
            is_used_asset=True,
            prior_owner_usage_years=Decimal("3"),
            extracted_amount=Decimal("18000.00"),
            extracted_net_amount=Decimal("15000.00"),
            extracted_vat_amount=Decimal("3000.00"),
        )
    )

    assert result.asset_candidate.asset_subtype == "pkw"
    assert result.tax_flags.allowed_depreciation_methods == ["linear"]
    assert result.tax_flags.ifb_candidate is False
    assert result.tax_flags.suggested_useful_life_years == Decimal("5")


def test_unknown_vat_near_gwg_boundary_requires_manual_review():
    service = AssetRecognitionService()

    result = service.recognize(
        make_input(
            vat_status=VatStatus.UNKNOWN,
            extracted_amount=Decimal("1100.00"),
            extracted_net_amount=Decimal("916.67"),
            extracted_vat_amount=Decimal("183.33"),
            raw_text="Rechnung Laptop Computer",
            extracted_line_items=[{"description": "Laptop"}],
        )
    )

    assert result.decision == AssetRecognitionDecision.MANUAL_REVIEW
    assert AssetReviewReason.THRESHOLD_BOUNDARY_AMBIGUOUS in result.review_reasons
