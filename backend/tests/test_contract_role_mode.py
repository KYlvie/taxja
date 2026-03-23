from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.models.document import DocumentType
from app.models.user import UserType
from app.tasks.ocr_tasks import (
    _build_asset_suggestion,
    _build_kaufvertrag_suggestion,
    _build_mietvertrag_suggestion,
    create_asset_from_suggestion,
    create_property_from_suggestion,
    create_recurring_from_suggestion,
    refresh_contract_role_sensitive_suggestions,
)
from tests.fixtures.models import create_test_document, create_test_user


def test_rental_contract_shadow_mode_keeps_suggestion_with_role_gate_metadata(db, monkeypatch):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "shadow")
    user = create_test_user(
        db,
        email="tenant-shadow@example.com",
        name="Fenghong Zhang",
        user_type=UserType.EMPLOYEE,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.RENTAL_CONTRACT,
        file_name="mietvertrag.pdf",
        ocr_result={
            "monthly_rent": 1200.0,
            "property_address": "Argentinierstrasse 21, 1234 Wien",
            "tenant_name": "Fenghong Zhang",
            "landlord_name": "OOHK Properties GmbH",
            "start_date": "2026-03-01",
        },
        raw_text="Mietvertrag Vermieter OOHK Properties GmbH Mieter Fenghong Zhang",
        confidence_score=Decimal("0.87"),
    )

    payload = _build_mietvertrag_suggestion(
        db,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.87")),
    )
    db.refresh(document)

    suggestion = payload["import_suggestion"]
    assert suggestion is not None
    assert suggestion["type"] == "create_recurring_income"
    assert suggestion["data"]["user_contract_role"] == "tenant"
    assert suggestion["data"]["role_gate_would_block"] is True
    assert document.ocr_result["contract_role_resolution"]["mode"] == "shadow"


def test_rental_contract_strict_mode_blocks_tenant_recurring_suggestion(db, monkeypatch):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "strict")
    user = create_test_user(
        db,
        email="tenant-strict@example.com",
        name="Fenghong Zhang",
        user_type=UserType.EMPLOYEE,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.RENTAL_CONTRACT,
        file_name="mietvertrag-strict.pdf",
        ocr_result={
            "monthly_rent": 980.0,
            "property_address": "Argentinierstrasse 21, 1234 Wien",
            "tenant_name": "Fenghong Zhang",
            "landlord_name": "OOHK Properties GmbH",
            "start_date": "2026-03-01",
        },
        raw_text="Mietvertrag Vermieter OOHK Properties GmbH Mieter Fenghong Zhang",
        confidence_score=Decimal("0.85"),
    )

    payload = _build_mietvertrag_suggestion(
        db,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.85")),
    )
    db.refresh(document)

    assert payload["import_suggestion"] is None
    assert document.ocr_result["user_contract_role"] == "tenant"
    assert document.ocr_result["contract_role_resolution"]["strict_would_block"] is True
    assert document.ocr_result.get("import_suggestion") is None


def test_property_purchase_strict_mode_blocks_seller_side_property_suggestion(db, monkeypatch):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "strict")
    user = create_test_user(
        db,
        email="seller-property@example.com",
        name="Markus Steiner",
        user_type=UserType.LANDLORD,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="haus-kaufvertrag.pdf",
        ocr_result={
            "purchase_contract_kind": "property",
            "purchase_price": 385000.0,
            "property_address": "Argentinierstrasse 21, 1234 Wien",
            "purchase_date": "2026-03-15",
            "buyer_name": "OOHK Properties GmbH",
            "seller_name": "Markus Steiner",
        },
        raw_text="Kaufvertrag Liegenschaft Verkäufer Markus Steiner Käufer OOHK Properties GmbH",
        confidence_score=Decimal("0.9"),
    )

    payload = _build_kaufvertrag_suggestion(
        db,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.9")),
    )
    db.refresh(document)

    assert payload["purchase_contract_kind"] == "property"
    assert payload["import_suggestion"] is None
    assert document.ocr_result["user_contract_role"] == "seller"
    assert document.ocr_result.get("import_suggestion") is None


def test_asset_purchase_strict_mode_blocks_seller_side_asset_suggestion(db, monkeypatch):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "strict")
    user = create_test_user(
        db,
        email="seller-asset@example.com",
        name="Markus Steiner",
        user_type=UserType.SELF_EMPLOYED,
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="car-sale.pdf",
        ocr_result={
            "purchase_contract_kind": "asset",
            "asset_type": "vehicle",
            "asset_name": "Volkswagen Golf 1.6 TDI Comfortline",
            "purchase_price": 13800.0,
            "purchase_date": "2026-03-18",
            "first_registration_date": "2018-04-15",
            "vehicle_identification_number": "WVWZZZAUZJW123456",
            "seller_name": "Markus Steiner",
            "buyer_name": "Fenghong Zhang",
            "is_used_asset": True,
        },
        raw_text=(
            "Kaufvertrag Kraftfahrzeug Verkäufer Markus Steiner Käufer Fenghong Zhang "
            "Fahrzeugart PKW Fahrgestellnummer WVWZZZAUZJW123456 Kaufpreis EUR 13.800,00"
        ),
        confidence_score=Decimal("0.89"),
    )

    payload = _build_asset_suggestion(
        db,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.89")),
    )
    db.refresh(document)

    assert payload["import_suggestion"] is None
    assert payload["auto_create_payload"] is None
    assert document.ocr_result["user_contract_role"] == "seller"
    assert document.ocr_result["contract_role_resolution"]["strict_would_block"] is True


def test_asset_purchase_shadow_mode_persists_role_resolution_even_without_asset_suggestion(
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "shadow")
    user = create_test_user(
        db,
        email="buyer-incomplete-asset@example.com",
        name="ZH TECH SOLUTIONS E.U.",
        user_type=UserType.SELF_EMPLOYED,
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="incomplete-vehicle-contract.pdf",
        ocr_result={
            "purchase_contract_kind": "asset",
            "asset_type": "vehicle",
            "buyer_name": "ZH TECH SOLUTIONS E.U.",
            "seller_name": "AUTOHAUS DONAUCITY GMBH",
            "import_suggestion": {
                "type": "create_asset",
                "status": "pending",
                "data": {"name": "stale asset suggestion"},
            },
        },
        raw_text=(
            "Kaufvertrag Kraftfahrzeug Kaeufer ZH TECH SOLUTIONS E.U. "
            "Verkaeufer AUTOHAUS DONAUCITY GMBH"
        ),
        confidence_score=Decimal("0.84"),
    )

    payload = _build_asset_suggestion(
        db,
        document,
        SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.84")),
    )
    db.refresh(document)

    assert payload["asset_recognition"] is None
    assert payload["import_suggestion"] is None
    assert payload["auto_create_payload"] is None
    assert document.ocr_result["user_contract_role"] == "buyer"
    assert document.ocr_result["user_contract_role_source"] == "party_name_match"
    assert document.ocr_result["contract_role_resolution"]["strict_would_block"] is False
    assert document.ocr_result.get("import_suggestion") is None


def test_purchase_contract_refresh_reextracts_stale_party_fields(db, monkeypatch):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "shadow")
    user = create_test_user(
        db,
        email="buyer-refresh@example.com",
        name="ZH TECH SOLUTIONS E.U.",
        user_type=UserType.SELF_EMPLOYED,
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="vehicle-contract-refresh.pdf",
        ocr_result={
            "purchase_contract_kind": "asset",
            "purchase_price": None,
            "buyer_name": "AUTOHAUS DONAUCITY GMBH, Wien ZH TECH SOLUTIONS E.U.",
            "seller_name": "kaufer",
        },
        raw_text=(
            "Kaufvertrag Kraftfahrzeug\n"
            "Verkaufer kaufer\n"
            "AUTOHAUS DONAUCITY GMBH, Wien ZH TECH SOLUTIONS E.U.\n"
            "brutto\n"
            "EUR 35.000,00\n"
        ),
        confidence_score=Decimal("0.81"),
    )

    payload = refresh_contract_role_sensitive_suggestions(db, document)
    db.refresh(document)

    assert payload["purchase_contract_kind"] == "asset"
    assert document.ocr_result["purchase_price"] == 35000.0
    assert document.ocr_result["buyer_name"] == "ZH TECH SOLUTIONS E.U."
    assert document.ocr_result["seller_name"] == "AUTOHAUS DONAUCITY GMBH"
    assert document.ocr_result["user_contract_role"] == "buyer"
    assert document.ocr_result["user_contract_role_source"] == "party_name_match"
    assert document.ocr_result["contract_role_resolution"]["strict_would_block"] is False


def test_purchase_contract_refresh_preserves_user_corrected_fields(db, monkeypatch):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "shadow")
    user = create_test_user(
        db,
        email="buyer-refresh-corrected@example.com",
        name="ZH TECH SOLUTIONS E.U.",
        user_type=UserType.SELF_EMPLOYED,
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="vehicle-contract-corrected.pdf",
        ocr_result={
            "purchase_contract_kind": "asset",
            "purchase_price": 32100.0,
            "buyer_name": "ZH TECH SOLUTIONS E.U.",
            "seller_name": "kaufer",
            "correction_history": [
                {
                    "corrected_at": "2026-03-20T10:00:00",
                    "corrected_by": user.id,
                    "previous_values": {"purchase_price": None},
                    "corrected_fields": ["purchase_price"],
                    "notes": "manual correction",
                }
            ],
        },
        raw_text=(
            "Kaufvertrag Kraftfahrzeug\n"
            "Verkaufer kaufer\n"
            "AUTOHAUS DONAUCITY GMBH, Wien ZH TECH SOLUTIONS E.U.\n"
            "brutto\n"
            "EUR 35.000,00\n"
        ),
        confidence_score=Decimal("0.81"),
    )

    refresh_contract_role_sensitive_suggestions(db, document)
    db.refresh(document)

    assert document.ocr_result["purchase_price"] == 32100.0
    assert document.ocr_result["buyer_name"] == "ZH TECH SOLUTIONS E.U."
    assert document.ocr_result["seller_name"] == "AUTOHAUS DONAUCITY GMBH"


@pytest.mark.parametrize(
    ("document_type", "role_value", "function", "suggestion_data", "expected_role_label"),
    [
        (
            DocumentType.RENTAL_CONTRACT,
            "tenant",
            create_recurring_from_suggestion,
            {"monthly_rent": 1200.0},
            "landlord",
        ),
        (
            DocumentType.PURCHASE_CONTRACT,
            "seller",
            create_property_from_suggestion,
            {},
            "buyer",
        ),
        (
            DocumentType.PURCHASE_CONTRACT,
            "seller",
            create_asset_from_suggestion,
            {},
            "buyer",
        ),
    ],
)
def test_strict_mode_confirmation_gate_rejects_wrong_contract_side(
    db,
    monkeypatch,
    document_type,
    role_value,
    function,
    suggestion_data,
    expected_role_label,
):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "strict")
    user = create_test_user(
        db,
        email=f"{role_value}-{document_type.value}@example.com",
        name="Blocked User",
        user_type=UserType.SELF_EMPLOYED,
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=document_type,
        file_name="blocked-contract.pdf",
        ocr_result={
            "user_contract_role": role_value,
            "purchase_contract_kind": "asset" if function is create_asset_from_suggestion else "property",
        },
    )

    with pytest.raises(ValueError, match=expected_role_label):
        function(db, document, suggestion_data)
