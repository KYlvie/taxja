from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from app.core.security import create_access_token
from app.models.asset_policy_snapshot import AssetPolicySnapshot
from app.models.document import DocumentType
from app.models.property import Property
from app.models.transaction import ExpenseCategory, Transaction, TransactionType
from app.models.transaction_line_item import LineItemPostingType
from app.models.user import UserType
from app.tasks.ocr_tasks import create_asset_from_suggestion
from tests.fixtures.models import create_test_document, create_test_transaction, create_test_user


def test_create_asset_from_suggestion_applies_confirmation_overrides(db):
    user = create_test_user(
        db,
        email="asset-confirm@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.INVOICE,
        file_name="laptop.pdf",
        ocr_result={
            "amount": 1499.00,
            "net_amount": 1249.17,
            "vat_amount": 249.83,
            "merchant": "Dell GmbH",
            "date": "2026-03-10",
            "line_items": [{"description": "Latitude 9450 Laptop"}],
            "import_suggestion": {"type": "create_asset", "status": "pending"},
        },
        raw_text="Dell GmbH Rechnung Latitude 9450 Laptop Computer",
        confidence_score=Decimal("0.91"),
    )

    result = create_asset_from_suggestion(
        db,
        document,
        {
            "asset_type": "computer",
            "sub_category": "computer",
            "name": "Dell Latitude 9450",
            "purchase_date": "2026-03-10",
            "purchase_price": 1499.00,
            "supplier": "Dell GmbH",
            "business_use_percentage": 100,
            "useful_life_years": 3,
            "decision": "create_asset_suggestion",
            "policy_confidence": 0.91,
            "policy_rule_ids": ["VAT-001"],
        },
        {
            "put_into_use_date": "2026-03-20",
            "business_use_percentage": 80,
            "depreciation_method": "degressive",
        },
        trigger_source="user",
    )

    asset = db.query(Property).filter(Property.id == UUID(result["asset_id"])).one()
    snapshot = (
        db.query(AssetPolicySnapshot)
        .filter(AssetPolicySnapshot.property_id == asset.id)
        .one()
    )
    acquisition_transaction = (
        db.query(Transaction)
        .filter(Transaction.document_id == document.id)
        .one()
    )
    db.refresh(document)

    assert asset.put_into_use_date == date(2026, 3, 20)
    assert asset.business_use_percentage == Decimal("80.00")
    assert asset.depreciation_method == "degressive"
    assert asset.degressive_afa_rate == Decimal("0.3000")
    assert asset.comparison_basis == "net"
    assert asset.comparison_amount == Decimal("1249.17")
    assert asset.income_tax_depreciable_base == Decimal("1249.17")
    assert snapshot.effective_anchor_date == date(2026, 3, 20)
    assert snapshot.snapshot_payload["selected_depreciation_method"] == "degressive"
    assert acquisition_transaction.type == TransactionType.ASSET_ACQUISITION
    assert acquisition_transaction.amount == Decimal("1499.00")
    assert acquisition_transaction.expense_category is None
    assert acquisition_transaction.is_deductible is False
    assert len(acquisition_transaction.line_items) == 2
    business_line, private_line = sorted(
        acquisition_transaction.line_items,
        key=lambda line: line.sort_order,
    )
    assert business_line.posting_type == LineItemPostingType.ASSET_ACQUISITION
    assert business_line.category == ExpenseCategory.EQUIPMENT.value
    assert business_line.amount == Decimal("999.34")
    assert business_line.vat_amount == Decimal("199.86")
    assert business_line.vat_recoverable_amount == Decimal("199.86")
    assert private_line.posting_type == LineItemPostingType.PRIVATE_USE
    assert private_line.category == ExpenseCategory.EQUIPMENT.value
    assert private_line.amount == Decimal("299.80")
    assert private_line.vat_amount == Decimal("49.97")
    assert private_line.vat_recoverable_amount == Decimal("0.00")
    assert document.ocr_result.get("import_suggestion") is None
    assert document.ocr_result["asset_outcome"]["status"] == "confirmed"
    assert document.ocr_result["asset_outcome"]["asset_id"] == result["asset_id"]


def test_create_asset_from_suggestion_requires_used_pkw_history(db):
    user = create_test_user(
        db,
        email="used-pkw@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="used-car.pdf",
        ocr_result={
            "amount": 18000.00,
            "net_amount": 15000.00,
            "vat_amount": 3000.00,
            "supplier": "Autohaus Wien",
            "date": "2026-03-12",
            "import_suggestion": {"type": "create_asset", "status": "pending"},
        },
        raw_text="Kaufvertrag gebrauchte PKW Fahrgestellnummer",
        confidence_score=Decimal("0.88"),
    )

    with pytest.raises(ValueError, match="prior_owner_usage_years_or_first_registration_date"):
        create_asset_from_suggestion(
            db,
            document,
            {
                "asset_type": "vehicle",
                "sub_category": "pkw",
                "name": "Used PKW",
                "purchase_date": "2026-03-12",
                "purchase_price": 18000.00,
                "supplier": "Autohaus Wien",
                "business_use_percentage": 100,
                "decision": "create_asset_suggestion",
            },
            {
                "put_into_use_date": "2026-03-20",
                "is_used_asset": True,
            },
            trigger_source="user",
        )


def test_create_asset_from_suggestion_persists_gwg_election(db):
    user = create_test_user(
        db,
        email="gwg-asset@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.INVOICE,
        file_name="printer.pdf",
        ocr_result={
            "amount": 900.00,
            "net_amount": 750.00,
            "vat_amount": 150.00,
            "merchant": "Printer GmbH",
            "date": "2026-03-01",
            "line_items": [{"description": "Office printer"}],
            "import_suggestion": {"type": "create_asset", "status": "pending"},
        },
        raw_text="Rechnung Office Printer Drucker",
        confidence_score=Decimal("0.90"),
    )

    result = create_asset_from_suggestion(
        db,
        document,
        {
            "asset_type": "other_equipment",
            "sub_category": "printer_scanner",
            "name": "Office Printer",
            "purchase_date": "2026-03-01",
            "purchase_price": 900.00,
            "supplier": "Printer GmbH",
            "business_use_percentage": 100,
            "decision": "gwg_suggestion",
            "policy_confidence": 0.90,
        },
        {
            "put_into_use_date": "2026-03-05",
            "gwg_elected": True,
        },
        trigger_source="user",
    )

    asset = db.query(Property).filter(Property.id == UUID(result["asset_id"])).one()

    assert asset.gwg_eligible is True
    assert asset.gwg_elected is True
    assert asset.useful_life_years == 1
    assert asset.depreciation_rate == Decimal("1.0000")
    assert asset.recognition_decision == "gwg_suggestion"


def test_create_asset_from_suggestion_creates_linked_acquisition_transaction(db):
    user = create_test_user(
        db,
        email="vehicle-asset@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="vw-golf.pdf",
        ocr_result={
            "amount": 13800.00,
            "merchant": "Autohaus Wien",
            "supplier": "Autohaus Wien",
            "date": "2026-03-18",
            "import_suggestion": {"type": "create_asset", "status": "pending"},
        },
        raw_text="Kaufvertrag fur ein gebrauchtes Kraftfahrzeug Volkswagen Golf PKW",
        confidence_score=Decimal("0.96"),
    )

    result = create_asset_from_suggestion(
        db,
        document,
        {
            "asset_type": "vehicle",
            "sub_category": "pkw",
            "name": "Volkswagen Golf 1.6 TDI Comfortline",
            "purchase_date": "2026-03-18",
            "purchase_price": 13800.00,
            "supplier": "Autohaus Wien",
            "business_use_percentage": 100,
            "decision": "create_asset_suggestion",
            "policy_confidence": 0.96,
            "policy_rule_ids": ["ASSET-VEHICLE-001"],
        },
        {
            "put_into_use_date": "2026-03-18",
            "is_used_asset": True,
            "first_registration_date": "2018-04-15",
        },
        trigger_source="user",
    )

    asset = db.query(Property).filter(Property.id == UUID(result["asset_id"])).one()
    acquisition_transaction = (
        db.query(Transaction)
        .filter(Transaction.document_id == document.id)
        .one()
    )
    db.refresh(document)

    assert result["transaction_id"] == acquisition_transaction.id
    assert result["transaction_created"] is True
    assert document.transaction_id == acquisition_transaction.id
    assert acquisition_transaction.property_id == asset.id
    assert acquisition_transaction.type == TransactionType.ASSET_ACQUISITION
    assert acquisition_transaction.amount == Decimal("13800.00")
    assert acquisition_transaction.transaction_date == date(2026, 3, 18)
    assert acquisition_transaction.expense_category is None
    assert acquisition_transaction.is_deductible is False
    assert acquisition_transaction.import_source == "asset_import"
    assert acquisition_transaction.is_system_generated is True
    assert "depreciation (AfA)" in (acquisition_transaction.deduction_reason or "")
    assert len(acquisition_transaction.line_items) == 1
    line_item = acquisition_transaction.line_items[0]
    assert line_item.posting_type == LineItemPostingType.ASSET_ACQUISITION
    assert line_item.category == ExpenseCategory.VEHICLE.value
    assert line_item.amount == Decimal("13800.00")
    assert line_item.vat_recoverable_amount == Decimal("0.00")
    assert document.ocr_result.get("import_suggestion") is None
    assert document.ocr_result["asset_outcome"]["status"] == "confirmed"


def test_create_asset_from_suggestion_materializes_partial_vat_recovery_for_electric_pkw(db):
    user = create_test_user(
        db,
        email="electric-vehicle-asset@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="tesla-model-y.pdf",
        ocr_result={
            "amount": 60000.00,
            "net_amount": 50000.00,
            "vat_amount": 10000.00,
            "merchant": "Tesla Austria GmbH",
            "supplier": "Tesla Austria GmbH",
            "date": "2026-03-18",
            "import_suggestion": {"type": "create_asset", "status": "pending"},
        },
        raw_text="Kaufvertrag Elektroauto Tesla Model Y electric_pkw",
        confidence_score=Decimal("0.95"),
    )

    result = create_asset_from_suggestion(
        db,
        document,
        {
            "asset_type": "vehicle",
            "sub_category": "electric_pkw",
            "name": "Tesla Model Y",
            "purchase_date": "2026-03-18",
            "purchase_price": 60000.00,
            "supplier": "Tesla Austria GmbH",
            "business_use_percentage": 100,
            "decision": "create_asset_suggestion",
            "policy_confidence": 0.95,
            "policy_rule_ids": ["ASSET-VEHICLE-003"],
        },
        {
            "put_into_use_date": "2026-03-18",
        },
        trigger_source="user",
    )

    transaction = db.query(Transaction).filter(Transaction.id == result["transaction_id"]).one()

    assert transaction.type == TransactionType.ASSET_ACQUISITION
    assert len(transaction.line_items) == 1
    line_item = transaction.line_items[0]
    assert line_item.posting_type == LineItemPostingType.ASSET_ACQUISITION
    assert line_item.amount == Decimal("53333.00")
    assert line_item.vat_amount == Decimal("10000.00")
    assert line_item.vat_recoverable_amount == Decimal("6667.00")


def test_create_asset_from_suggestion_reuses_existing_document_transaction(db):
    user = create_test_user(
        db,
        email="reuse-asset-transaction@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
        business_type="freiberufler",
    )
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.PURCHASE_CONTRACT,
        file_name="existing-vehicle-transaction.pdf",
        ocr_result={
            "amount": 13800.00,
            "merchant": "Autohaus Wien",
            "supplier": "Autohaus Wien",
            "date": "2026-03-18",
            "import_suggestion": {"type": "create_asset", "status": "pending"},
        },
        raw_text="Kaufvertrag gebrauchte PKW Volkswagen Golf",
        confidence_score=Decimal("0.95"),
    )
    existing_transaction = create_test_transaction(
        db,
        user=user,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("1.00"),
        transaction_date=date(2026, 3, 1),
        description="Placeholder OCR transaction",
        expense_category=ExpenseCategory.OTHER,
        document_id=document.id,
        is_deductible=True,
    )
    document.transaction_id = existing_transaction.id
    db.add(document)
    db.commit()

    result = create_asset_from_suggestion(
        db,
        document,
        {
            "asset_type": "vehicle",
            "sub_category": "pkw",
            "name": "Volkswagen Golf 1.6 TDI Comfortline",
            "purchase_date": "2026-03-18",
            "purchase_price": 13800.00,
            "supplier": "Autohaus Wien",
            "business_use_percentage": 100,
            "decision": "create_asset_suggestion",
            "policy_confidence": 0.95,
            "policy_rule_ids": ["ASSET-VEHICLE-001"],
        },
        {
            "put_into_use_date": "2026-03-18",
            "is_used_asset": True,
            "first_registration_date": "2018-04-15",
        },
        trigger_source="user",
    )

    db.refresh(document)
    updated_transaction = db.query(Transaction).filter(Transaction.id == existing_transaction.id).one()

    assert result["transaction_id"] == existing_transaction.id
    assert result["transaction_created"] is False
    assert document.transaction_id == existing_transaction.id
    assert (
        db.query(Transaction)
        .filter(Transaction.document_id == document.id)
        .count()
        == 1
    )
    assert updated_transaction.property_id is not None
    assert updated_transaction.type == TransactionType.ASSET_ACQUISITION
    assert updated_transaction.amount == Decimal("13800.00")
    assert updated_transaction.transaction_date == date(2026, 3, 18)
    assert updated_transaction.expense_category is None
    assert updated_transaction.is_deductible is False
    assert updated_transaction.import_source == "asset_import"
    assert len(updated_transaction.line_items) == 1
    assert updated_transaction.line_items[0].posting_type == LineItemPostingType.ASSET_ACQUISITION
    assert updated_transaction.line_items[0].category == ExpenseCategory.VEHICLE.value


def test_confirm_asset_endpoint_accepts_confirmation_payload(client, db):
    user = create_test_user(
        db,
        email="confirm-endpoint@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_number="ATU12345678",
        business_type="freiberufler",
    )
    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.INVOICE,
        file_name="macbook.pdf",
        ocr_result={
            "amount": 1499.00,
            "net_amount": 1249.17,
            "vat_amount": 249.83,
            "merchant": "Apple",
            "date": "2026-03-10",
            "line_items": [{"description": "MacBook Pro 14"}],
            "import_suggestion": {
                "type": "create_asset",
                "status": "pending",
                "data": {
                    "asset_type": "computer",
                    "sub_category": "computer",
                    "name": "MacBook Pro",
                    "purchase_date": "2026-03-10",
                    "purchase_price": 1499.00,
                    "supplier": "Apple",
                    "business_use_percentage": 100,
                    "useful_life_years": 3,
                    "decision": "create_asset_suggestion",
                    "policy_confidence": 0.93,
                },
            },
        },
        raw_text="Apple Rechnung MacBook Pro 14 Laptop Computer",
        confidence_score=Decimal("0.93"),
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-asset",
        json={
            "put_into_use_date": "2026-03-20",
            "business_use_percentage": 75,
            "depreciation_method": "degressive",
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset_type"] == "computer"
    assert payload["transaction_id"] is not None
    asset = db.query(Property).filter(Property.id == UUID(payload["asset_id"])).one()
    transaction = db.query(Transaction).filter(Transaction.id == payload["transaction_id"]).one()
    assert asset.put_into_use_date == date(2026, 3, 20)
    assert asset.business_use_percentage == Decimal("75.00")
    assert asset.depreciation_method == "degressive"
    assert transaction.property_id == asset.id
    assert transaction.document_id == document.id
    assert transaction.type == TransactionType.ASSET_ACQUISITION
    assert transaction.is_deductible is False
    assert transaction.expense_category is None
    assert len(transaction.line_items) == 2
    assert transaction.line_items[0].posting_type == LineItemPostingType.ASSET_ACQUISITION
    assert transaction.line_items[0].category == ExpenseCategory.EQUIPMENT.value
    assert transaction.line_items[1].posting_type == LineItemPostingType.PRIVATE_USE

    detail_response = client.get(
        f"/api/v1/properties/{payload['asset_id']}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["asset_type"] == "computer"
    assert detail_payload["put_into_use_date"] == "2026-03-20"
    assert detail_payload["business_use_percentage"] == "75.00"
    assert detail_payload["comparison_basis"] == "net"
    assert detail_payload["comparison_amount"] == "1249.17"
    assert detail_payload["depreciation_method"] == "degressive"
    assert detail_payload["degressive_afa_rate"] == "0.3000"
    assert detail_payload["vat_recoverable_status"] == "likely_yes"
    assert detail_payload["ifb_candidate"] is False
    assert detail_payload["ifb_rate"] is None
    assert detail_payload["recognition_decision"] == "create_asset_suggestion"
