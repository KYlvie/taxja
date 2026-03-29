from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.document import DocumentType
from app.models.property import Property
from app.models.recurring_transaction import (
    RecurringTransaction,
    RecurringTransactionType,
)
from app.models.transaction import IncomeCategory, Transaction, TransactionType
from app.models.user import UserType
from tests.fixtures.models import (
    create_test_document,
    create_test_property,
    create_test_user,
)


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def _first_day_of_current_month() -> date:
    today = date.today()
    return today.replace(day=1)


def _make_landlord_document(
    db: Session,
    *,
    user,
    monthly_rent: float,
    address: str,
    matched_property_id: str | None,
    file_name: str = "mietvertrag.pdf",
) -> object:
    start_date = _first_day_of_current_month().isoformat()
    return create_test_document(
        db,
        user=user,
        document_type=DocumentType.RENTAL_CONTRACT,
        file_name=file_name,
        raw_text=(
            f"Mietvertrag Vermieter {user.name} "
            f"Mieter Mag. Stefan Berger Mietobjekt {address}"
        ),
        ocr_result={
            "monthly_rent": monthly_rent,
            "property_address": address,
            "tenant_name": "Mag. Stefan Berger",
            "landlord_name": user.name,
            "start_date": start_date,
            "import_suggestion": {
                "type": "create_recurring_income",
                "status": "pending",
                "data": {
                    "monthly_rent": monthly_rent,
                    "start_date": start_date,
                    "end_date": None,
                    "address": address,
                    "tenant_name": "Mag. Stefan Berger",
                    "landlord_name": user.name,
                    "matched_property_id": matched_property_id,
                    "matched_property_address": address if matched_property_id else None,
                    "no_property_match": matched_property_id is None,
                    "is_partial_match": False,
                    "address_mismatch_warning": False,
                    "user_contract_role": "landlord",
                    "user_contract_role_source": "ocr_party_name_match",
                    "role_gate_mode": "legacy",
                    "role_gate_would_block": False,
                },
            },
        },
        confidence_score=Decimal("0.95"),
    )


def test_confirm_recurring_creates_landlord_income_recurring_and_first_income_transaction(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="landlord-recurring@example.com",
        name="DI Maria Steiner",
        user_type=UserType.LANDLORD,
    )
    property_obj = create_test_property(
        db,
        user=user,
        street="Praterstrasse 40/12",
        city="Wien",
        postal_code="1020",
    )
    document = _make_landlord_document(
        db,
        user=user,
        monthly_rent=1035.00,
        address=property_obj.address,
        matched_property_id=str(property_obj.id),
        file_name="VL_01_Mietvertrag_Praterstrasse.pdf",
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-recurring",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recurring_created"] is True
    assert payload["property_id"] == str(property_obj.id)
    assert payload["monthly_rent"] == 1035.0

    recurring = (
        db.query(RecurringTransaction)
        .filter(RecurringTransaction.source_document_id == document.id)
        .one()
    )
    assert recurring.recurring_type == RecurringTransactionType.RENTAL_INCOME
    assert recurring.property_id == property_obj.id
    assert recurring.amount == Decimal("1035.00")
    assert recurring.transaction_type == "income"
    assert recurring.category == "rental_income"

    generated = (
        db.query(Transaction)
        .filter(Transaction.source_recurring_id == recurring.id)
        .all()
    )
    assert len(generated) == 1
    assert generated[0].type == TransactionType.INCOME
    assert generated[0].income_category == IncomeCategory.RENTAL
    assert generated[0].amount == Decimal("1035.00")
    assert generated[0].property_id == property_obj.id
    assert generated[0].is_system_generated is True

    db.refresh(document)
    assert document.ocr_result["import_suggestion"]["status"] == "confirmed"
    assert document.ocr_result["import_suggestion"]["recurring_id"] == recurring.id


def test_confirm_recurring_auto_creates_property_when_none_matched(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="landlord-autocreate@example.com",
        name="DI Maria Steiner",
        user_type=UserType.LANDLORD,
    )
    address = "Praterstrasse 40/12, 1020 Wien"
    document = _make_landlord_document(
        db,
        user=user,
        monthly_rent=1035.00,
        address=address,
        matched_property_id=None,
        file_name="VL_01_Mietvertrag_Autocreate.pdf",
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-recurring",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recurring_created"] is True
    assert payload["property_auto_created"] is True

    created_property = db.query(Property).filter(Property.user_id == user.id).one()
    assert created_property.address == address
    assert created_property.mietvertrag_document_id == document.id
    assert created_property.purchase_price == Decimal("0.01")

    recurring = (
        db.query(RecurringTransaction)
        .filter(RecurringTransaction.source_document_id == document.id)
        .one()
    )
    assert str(recurring.property_id) == payload["property_id"]
    assert recurring.property_id == created_property.id


def test_confirm_recurring_reuses_existing_landlord_recurring_for_same_property(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="landlord-dedup@example.com",
        name="DI Maria Steiner",
        user_type=UserType.LANDLORD,
    )
    property_obj = create_test_property(
        db,
        user=user,
        street="Praterstrasse 40/12",
        city="Wien",
        postal_code="1020",
    )

    first_document = _make_landlord_document(
        db,
        user=user,
        monthly_rent=1035.00,
        address=property_obj.address,
        matched_property_id=str(property_obj.id),
        file_name="VL_01_Mietvertrag_Praterstrasse.pdf",
    )
    second_document = _make_landlord_document(
        db,
        user=user,
        monthly_rent=1035.00,
        address=property_obj.address,
        matched_property_id=str(property_obj.id),
        file_name="VL_01_Mietvertrag_Praterstrasse_Duplikat.pdf",
    )

    first_response = client.post(
        f"/api/v1/documents/{first_document.id}/confirm-recurring",
        headers=_auth_headers(user.email),
    )
    assert first_response.status_code == 200
    first_recurring_id = first_response.json()["recurring_id"]

    second_response = client.post(
        f"/api/v1/documents/{second_document.id}/confirm-recurring",
        headers=_auth_headers(user.email),
    )
    assert second_response.status_code == 200
    assert second_response.json()["recurring_id"] == first_recurring_id

    recurrings = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.user_id == user.id,
            RecurringTransaction.property_id == property_obj.id,
            RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
        )
        .all()
    )
    assert len(recurrings) == 1

    generated = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            Transaction.source_recurring_id == first_recurring_id,
            Transaction.type == TransactionType.INCOME,
        )
        .all()
    )
    assert len(generated) == 1

    db.refresh(second_document)
    assert second_document.ocr_result["import_suggestion"]["status"] == "confirmed"
    assert second_document.ocr_result["import_suggestion"]["recurring_id"] == first_recurring_id


def test_confirm_recurring_is_idempotent_after_first_confirmation(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="landlord-idempotent@example.com",
        name="DI Maria Steiner",
        user_type=UserType.LANDLORD,
    )
    property_obj = create_test_property(
        db,
        user=user,
        street="Praterstrasse 40/12",
        city="Wien",
        postal_code="1020",
    )
    document = _make_landlord_document(
        db,
        user=user,
        monthly_rent=1035.00,
        address=property_obj.address,
        matched_property_id=str(property_obj.id),
        file_name="VL_01_Mietvertrag_Idempotent.pdf",
    )

    first_response = client.post(
        f"/api/v1/documents/{document.id}/confirm-recurring",
        headers=_auth_headers(user.email),
    )
    assert first_response.status_code == 200
    recurring_id = first_response.json()["recurring_id"]

    second_response = client.post(
        f"/api/v1/documents/{document.id}/confirm-recurring",
        headers=_auth_headers(user.email),
    )
    assert second_response.status_code == 200
    assert second_response.json()["already_confirmed"] is True
    assert second_response.json()["recurring_id"] == recurring_id


def test_confirm_recurring_blocks_when_contract_role_resolves_to_tenant_in_strict_mode(
    client: TestClient,
    db: Session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "CONTRACT_ROLE_MODE", "strict")

    user = create_test_user(
        db,
        email="landlord-role-block@example.com",
        name="DI Maria Steiner",
        user_type=UserType.LANDLORD,
    )
    property_obj = create_test_property(
        db,
        user=user,
        street="Praterstrasse 40/12",
        city="Wien",
        postal_code="1020",
    )
    start_date = _first_day_of_current_month().isoformat()
    document = create_test_document(
        db,
        user=user,
        document_type=DocumentType.RENTAL_CONTRACT,
        file_name="VL_01_Mietvertrag_Falschrolle.pdf",
        raw_text=(
            "Mietvertrag Mieter DI Maria Steiner "
            "Vermieter Ing. Thomas Gruber "
            f"Mietobjekt {property_obj.address}"
        ),
        ocr_result={
            "monthly_rent": 1035.00,
            "property_address": property_obj.address,
            "tenant_name": "DI Maria Steiner",
            "landlord_name": "Ing. Thomas Gruber",
            "start_date": start_date,
            "import_suggestion": {
                "type": "create_recurring_income",
                "status": "pending",
                "data": {
                    "monthly_rent": 1035.00,
                    "start_date": start_date,
                    "end_date": None,
                    "address": property_obj.address,
                    "tenant_name": "DI Maria Steiner",
                    "landlord_name": "Ing. Thomas Gruber",
                    "matched_property_id": str(property_obj.id),
                    "matched_property_address": property_obj.address,
                    "no_property_match": False,
                    "is_partial_match": False,
                    "address_mismatch_warning": False,
                },
            },
        },
        confidence_score=Decimal("0.95"),
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/confirm-recurring",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 400
    assert "tenant" in response.json()["detail"]

    recurring_count = (
        db.query(RecurringTransaction)
        .filter(RecurringTransaction.user_id == user.id)
        .count()
    )
    assert recurring_count == 0
