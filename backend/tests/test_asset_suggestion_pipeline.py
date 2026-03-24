from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from app.models.asset_event import AssetEvent, AssetEventType
from app.models.asset_policy_snapshot import AssetPolicySnapshot
from app.models.document import DocumentType
from app.services.document_pipeline_orchestrator import (
    ClassificationResult,
    ConfidenceLevel,
    PipelineResult,
    PipelineStage,
)
from app.tasks.ocr_tasks import (
    _build_asset_suggestion,
    _build_kaufvertrag_suggestion,
    create_asset_from_suggestion,
)
from app.models.user import Gewinnermittlungsart, UserType, VatStatus
from tests.fixtures.models import create_test_document, create_test_user


def test_build_asset_suggestion_for_invoice_persists_recognition(db):
    user = create_test_user(
        db,
        email="asset-suggestion@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.INVOICE,
        file_name="laptop-rechnung.pdf",
        file_hash="hash-laptop-001",
        mime_type="application/pdf",
        ocr_result={
            "amount": 1499.00,
            "vat_amount": 249.83,
            "merchant": "Dell GmbH",
            "date": "2026-03-12",
            "line_items": [{"description": "Latitude 9450 Laptop"}],
        },
        raw_text="Dell GmbH Rechnung Latitude 9450 Laptop Computer",
        confidence_score=Decimal("0.91"),
    )

    result = SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.91"))

    suggestion_payload = _build_asset_suggestion(db, document, result)
    db.refresh(document)

    suggestion = suggestion_payload["import_suggestion"]
    assert suggestion is not None
    assert suggestion["type"] == "create_asset"
    assert suggestion["data"]["asset_type"] == "computer"
    assert suggestion["data"]["decision"] == "create_asset_suggestion"
    assert "gwg_eligible" in suggestion["data"]
    assert "gwg_default_selected" in suggestion["data"]
    assert "gwg_election_required" in suggestion["data"]
    assert "requires_user_confirmation" in suggestion["data"]
    assert suggestion["data"]["policy_rule_ids"]
    assert suggestion["data"]["ifb_rate_source"] == "not_applicable"
    assert document.ocr_result["asset_recognition"]["decision"] == "create_asset_suggestion"
    assert document.ocr_result["asset_outcome"]["status"] == "pending_confirmation"
    assert document.ocr_result["asset_outcome"]["source"] == "quality_gate"


def test_asset_suggestion_audit_uses_persisted_tax_profile_inputs_without_vat_number(db):
    user = create_test_user(
        db,
        email="asset-audit-profile@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number=None,
        vat_status=VatStatus.KLEINUNTERNEHMER,
        gewinnermittlungsart=Gewinnermittlungsart.PAUSCHAL,
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.INVOICE,
        file_name="camera-invoice.pdf",
        file_hash="hash-camera-001",
        mime_type="application/pdf",
        ocr_result={
            "amount": 2499.00,
            "vat_amount": 0.0,
            "merchant": "Foto Handel GmbH",
            "date": "2026-03-11",
            "line_items": [{"description": "Sony Alpha Camera"}],
        },
        raw_text="Foto Handel GmbH Rechnung Sony Alpha Camera",
        confidence_score=Decimal("0.95"),
    )

    result = SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.95"))

    _build_asset_suggestion(db, document, result)
    db.refresh(document)

    recognition = document.ocr_result["asset_recognition"]
    audit = recognition["decision_audit"]
    quality_gate = document.ocr_result["asset_quality_gate"]

    assert audit["source_document_id"] == document.id
    assert audit["profile_inputs_used"]["vat_status"] == VatStatus.KLEINUNTERNEHMER.value
    assert (
        audit["profile_inputs_used"]["gewinnermittlungsart"]
        == Gewinnermittlungsart.PAUSCHAL.value
    )
    assert quality_gate["missing_fields"] == []


def test_vehicle_purchase_contract_skips_property_suggestion_and_builds_asset(db):
    user = create_test_user(
        db,
        email="vehicle-contract@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="vw-golf-kaufvertrag.pdf",
        file_hash="hash-vw-golf-001",
        mime_type="application/pdf",
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
            "Kaufvertrag fur ein gebrauchtes Kraftfahrzeug "
            "Marke / Modell Volkswagen Golf 1.6 TDI Comfortline "
            "Fahrzeugart PKW Erstzulassung 15.04.2018 "
            "FIN / Fahrgestellnummer WVWZZZAUZJW123456 "
            "Kaufpreis EUR 13.800,00"
        ),
        confidence_score=Decimal("0.89"),
    )

    result = SimpleNamespace(raw_text=document.raw_text, confidence_score=Decimal("0.89"))

    property_suggestion = _build_kaufvertrag_suggestion(db, document, result)
    db.refresh(document)
    assert property_suggestion["import_suggestion"] is None

    asset_payload = _build_asset_suggestion(db, document, result)
    db.refresh(document)
    suggestion = asset_payload["import_suggestion"] or asset_payload["auto_create_payload"]

    assert suggestion is not None
    assert suggestion["type"] == "create_asset"
    assert suggestion["data"]["asset_type"] == "vehicle"
    assert suggestion["data"]["decision"] in {
        "create_asset_suggestion",
        "create_asset_auto",
    }
    assert document.ocr_result["purchase_contract_kind"] == "asset"
    if asset_payload["import_suggestion"] is not None:
        assert document.ocr_result["import_suggestion"]["type"] == "create_asset"
    else:
        assert document.ocr_result.get("import_suggestion") is None


def test_build_asset_suggestion_accepts_pipeline_result_without_confidence_score(db):
    user = create_test_user(
        db,
        email="vehicle-pipeline@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="vw-golf-pipeline.pdf",
        file_hash="hash-vw-golf-pipeline-001",
        mime_type="application/pdf",
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
            "Kaufvertrag fur ein gebrauchtes Kraftfahrzeug "
            "Marke / Modell Volkswagen Golf 1.6 TDI Comfortline "
            "Fahrzeugart PKW Erstzulassung 15.04.2018 "
            "FIN / Fahrgestellnummer WVWZZZAUZJW123456 "
            "Kaufpreis EUR 13.800,00"
        ),
        confidence_score=None,
    )

    result = PipelineResult(
        document_id=document.id,
        stage_reached=PipelineStage.SUGGEST,
        classification=ClassificationResult(
            document_type="purchase_contract",
            confidence=0.92,
            method="regex",
        ),
        extracted_data=document.ocr_result,
        raw_text=document.raw_text,
        confidence_level=ConfidenceLevel.HIGH,
        needs_review=False,
    )

    asset_payload = _build_asset_suggestion(db, document, result)
    db.refresh(document)

    suggestion = asset_payload["import_suggestion"] or asset_payload["auto_create_payload"]
    assert suggestion is not None
    assert suggestion["type"] == "create_asset"
    assert suggestion["data"]["asset_type"] == "vehicle"
    assert document.ocr_result["asset_recognition"]["decision"] in {
        "create_asset_suggestion",
        "create_asset_auto",
    }


def test_create_asset_from_suggestion_persists_snapshot_and_events(db):
    user = create_test_user(
        db,
        email="asset-create@example.com",
        user_type=UserType.SELF_EMPLOYED,
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.INVOICE,
        file_name="macbook.pdf",
        ocr_result={
            "import_suggestion": {
                "type": "create_asset",
                "status": "pending",
            }
        },
    )

    result = create_asset_from_suggestion(
        db,
        document,
        {
            "asset_type": "computer",
            "sub_category": "computer",
            "name": "MacBook Pro",
            "purchase_date": "2026-03-10",
            "put_into_use_date": "2026-03-20",
            "purchase_price": 1499.00,
            "supplier": "Apple",
            "business_use_percentage": 90,
            "useful_life_years": 3,
            "comparison_basis": "net",
            "decision": "create_asset_suggestion",
            "reason_codes": ["durable_equipment_detected"],
            "policy_rule_ids": ["VAT-001", "IFB-003"],
        },
        trigger_source="user",
    )

    snapshot = (
        db.query(AssetPolicySnapshot)
        .filter(AssetPolicySnapshot.property_id == UUID(result["asset_id"]))
        .one()
    )
    events = (
        db.query(AssetEvent)
        .filter(AssetEvent.property_id == UUID(result["asset_id"]))
        .order_by(AssetEvent.id.asc())
        .all()
    )

    assert result["asset_type"] == "computer"
    assert snapshot.effective_anchor_date == date(2026, 3, 20)
    assert "VAT-001" in snapshot.rule_ids
    assert "IFB-003" in snapshot.rule_ids
    assert [event.event_type for event in events] == [
        AssetEventType.ACQUIRED,
        AssetEventType.PUT_INTO_USE,
    ]


def test_finalize_keeps_asset_terminal_state_out_of_import_suggestion():
    from unittest.mock import MagicMock

    from app.services.document_pipeline_orchestrator import DocumentPipelineOrchestrator

    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    orchestrator.db = MagicMock()

    document = SimpleNamespace(
        ocr_result={},
        raw_text=None,
        confidence_score=None,
        processed_at=None,
    )

    result = PipelineResult(
        document_id=1,
        stage_reached=PipelineStage.SUGGEST,
        classification=ClassificationResult(
            document_type="invoice",
            confidence=0.91,
            method="regex",
        ),
        extracted_data={"amount": 1499.0},
        raw_text="Dell Laptop",
        confidence_level=ConfidenceLevel.HIGH,
        suggestions=[
            {
                "type": "expense",
                "amount": "1499.00",
                "description": "Dell Laptop",
                "category": "equipment",
                "is_deductible": True,
                "status": "auto-created",
            },
            {
                "type": "create_asset",
                "status": "auto-created",
                "asset_id": "asset-1",
                "data": {"name": "Dell Laptop", "decision": "create_asset_auto"},
            },
        ],
        needs_review=False,
    )

    finalized = orchestrator._finalize(
        result=result,
        document=document,
        start_time=datetime.utcnow(),
    )

    assert finalized is result
    assert "import_suggestion" not in document.ocr_result
    assert document.ocr_result["asset_outcome"]["status"] == "auto_created"
    assert document.ocr_result["asset_outcome"]["asset_id"] == "asset-1"
    assert document.ocr_result["transaction_suggestion"]["description"] == "Dell Laptop"
    assert document.ocr_result["tax_analysis"]["items"][0]["category"] == "equipment"
