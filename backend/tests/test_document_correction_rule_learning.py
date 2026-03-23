from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.document import DocumentType
from app.models.user import UserType
from app.models.user_classification_rule import UserClassificationRule
from app.models.user_deductibility_rule import UserDeductibilityRule
from app.services.user_classification_service import UserClassificationService
from app.services.user_deductibility_service import UserDeductibilityService
from tests.fixtures.models import create_test_document, create_test_user


GERMAN_A_UMLAUT = "\u00e4"
GERMAN_O_UMLAUT = "\u00d6"
GERMAN_U_UMLAUT = "\u00dc"


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_document_correction_learns_rules_for_additional_receipt_items(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="multi-receipt-learning@example.com",
        user_type=UserType.MIXED,
        business_type="gewerbe",
        business_industry="beherbergung",
    )
    user.email_verified = True
    db.commit()
    db.refresh(user)

    primary_receipt = {
        "merchant": "Eni Service-Station",
        "amount": 68.32,
        "_transaction_type": "expense",
        "line_items": [
            {
                "description": "Diesel",
                "amount": 68.32,
                "quantity": 1,
                "category": "fuel",
                "is_deductible": True,
                "deduction_reason": "Existing confirmed fuel purchase.",
            }
        ],
    }
    secondary_receipt = {
        "merchant": "Tankautomat Leissenaach",
        "amount": 10.91,
        "_transaction_type": "expense",
        "line_items": [
            {
                "description": f"S{GERMAN_A_UMLAUT}ule 1",
                "amount": 9.85,
                "quantity": 4.925,
                "category": "other",
                "is_deductible": False,
                "deduction_reason": "Initial OCR guess.",
            }
        ],
    }
    corrected_secondary = {
        **secondary_receipt,
        "line_items": [
            {
                "description": f"S{GERMAN_A_UMLAUT}ule 1",
                "amount": 9.85,
                "quantity": 4.925,
                "category": "fuel",
                "is_deductible": True,
                "deduction_reason": "Vehicle fuel used for lodging business procurement.",
            }
        ],
        "items": [
            {
                "description": f"S{GERMAN_A_UMLAUT}ule 1",
                "amount": 9.85,
                "quantity": 4.925,
                "category": "fuel",
                "is_deductible": True,
                "deduction_reason": "Vehicle fuel used for lodging business procurement.",
            }
        ],
    }

    document = create_test_document(
        db,
        user,
        document_type=DocumentType.RECEIPT,
        file_name="multi-receipt-learning.pdf",
        file_size=2048,
        mime_type="application/pdf",
        ocr_result={
            **primary_receipt,
            "multiple_receipts": [primary_receipt, secondary_receipt],
            "_additional_receipts": [secondary_receipt],
            "receipt_count": 2,
            "_receipt_count": 2,
        },
        raw_text="Eni plus tankautomat receipt set",
        confidence_score=0.72,
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/correct",
        headers=_auth_headers(user.email),
        json={
            "corrected_data": {
                "multiple_receipts": [primary_receipt, corrected_secondary],
                "_additional_receipts": [corrected_secondary],
                "receipt_count": 2,
                "_receipt_count": 2,
            }
        },
    )

    assert response.status_code == 200

    class_rules_response = client.get(
        "/api/v1/classification-rules/",
        headers=_auth_headers(user.email),
    )
    assert class_rules_response.status_code == 200
    classification_rules = class_rules_response.json()
    assert any(
        rule["original_description"] == "Tankautomat Leissenaach"
        and rule["txn_type"] == "expense"
        and rule["category"] == "fuel"
        for rule in classification_rules
    )

    deductibility_rules_response = client.get(
        "/api/v1/classification-rules/deductibility",
        headers=_auth_headers(user.email),
    )
    assert deductibility_rules_response.status_code == 200
    deductibility_rules = deductibility_rules_response.json()
    assert any(
        rule["original_description"] == f"Tankautomat Leissenaach S{GERMAN_A_UMLAUT}ule 1"
        and rule["expense_category"] == "fuel"
        and rule["is_deductible"] is True
        for rule in deductibility_rules
    )


def test_document_correction_dedupes_multi_item_receipt_rule_learning(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="multi-item-dedupe@example.com",
        user_type=UserType.MIXED,
        business_type="gewerbe",
        business_industry="beherbergung",
    )
    user.email_verified = True
    db.commit()
    db.refresh(user)

    item_one = "VARTA ABA71 BLUE DYN EFB"
    item_two = f"K{GERMAN_U_UMLAUT}HLERFROSTSCHUTZ MC30 1,5l."
    parent_description = (
        f"Purchase of {item_one} battery and "
        f"K{GERMAN_U_UMLAUT}HLERFROSTSCHUTZ MC30 1.5l."
    )
    parent_rule_description = f"{GERMAN_O_UMLAUT}AMTC: {parent_description}"

    initial_receipt = {
        "merchant": f"{GERMAN_O_UMLAUT}AMTC",
        "description": parent_description,
        "_transaction_type": "expense",
        "line_items": [
            {
                "description": item_one,
                "amount": 222,
                "quantity": 1,
                "category": "vehicle",
                "is_deductible": True,
                "deduction_reason": "Initial guess.",
            },
            {
                "description": item_two,
                "amount": 15.9,
                "quantity": 1,
                "category": "vehicle",
                "is_deductible": True,
                "deduction_reason": "Initial guess.",
            },
        ],
        "items": [
            {
                "description": item_one,
                "amount": 222,
                "quantity": 1,
                "category": "vehicle",
                "is_deductible": True,
                "deduction_reason": "Initial guess.",
            },
            {
                "description": item_two,
                "amount": 15.9,
                "quantity": 1,
                "category": "vehicle",
                "is_deductible": True,
                "deduction_reason": "Initial guess.",
            },
        ],
    }
    corrected_receipt = {
        **initial_receipt,
        "line_items": [
            {
                "description": item_one,
                "amount": 222,
                "quantity": 1,
                "category": "other",
                "is_deductible": False,
                "deduction_reason": "Battery purchase is not deductible.",
            },
            {
                "description": item_two,
                "amount": 15.9,
                "quantity": 1,
                "category": "other",
                "is_deductible": False,
                "deduction_reason": "Battery purchase is not deductible.",
            },
        ],
        "items": [
            {
                "description": item_one,
                "amount": 222,
                "quantity": 1,
                "category": "other",
                "is_deductible": False,
                "deduction_reason": "Battery purchase is not deductible.",
            },
            {
                "description": item_two,
                "amount": 15.9,
                "quantity": 1,
                "category": "other",
                "is_deductible": False,
                "deduction_reason": "Battery purchase is not deductible.",
            },
        ],
        "tax_analysis": {"reviewed": True},
    }

    document = create_test_document(
        db,
        user,
        document_type=DocumentType.RECEIPT,
        file_name="oamtc-multi-item.pdf",
        file_size=2048,
        mime_type="application/pdf",
        ocr_result=initial_receipt,
        raw_text="OAMTC invoice",
        confidence_score=0.72,
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/correct",
        headers=_auth_headers(user.email),
        json={"corrected_data": corrected_receipt},
    )

    assert response.status_code == 200

    classification_rules = (
        db.query(UserClassificationRule)
        .filter(UserClassificationRule.user_id == user.id)
        .order_by(UserClassificationRule.id.asc())
        .all()
    )
    deductibility_rules = (
        db.query(UserDeductibilityRule)
        .filter(UserDeductibilityRule.user_id == user.id)
        .order_by(UserDeductibilityRule.id.asc())
        .all()
    )

    assert len(classification_rules) == 2
    assert len(deductibility_rules) == 2
    assert classification_rules[0].original_description == parent_rule_description
    assert classification_rules[0].hit_count == 1
    assert deductibility_rules[0].original_description == parent_rule_description
    assert deductibility_rules[0].hit_count == 1


def test_document_correction_persists_transaction_type_override(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="transaction-type-override@example.com",
        user_type=UserType.MIXED,
        business_type="gewerbe",
        business_industry="it",
    )
    user.email_verified = True
    db.commit()
    db.refresh(user)

    document = create_test_document(
        db,
        user,
        document_type=DocumentType.INVOICE,
        file_name="income-switch.pdf",
        file_size=1024,
        mime_type="application/pdf",
        ocr_result={
            "merchant": "ACME Studio",
            "_transaction_type": "expense",
            "line_items": [
                {
                    "description": "Consulting invoice",
                    "amount": 299,
                    "quantity": 1,
                    "category": "professional_services",
                    "is_deductible": True,
                }
            ],
        },
        raw_text="Consulting invoice",
        confidence_score=0.82,
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/correct",
        headers=_auth_headers(user.email),
        json={
            "corrected_data": {
                "_transaction_type": "income",
                "document_transaction_direction": "income",
            }
        },
    )

    assert response.status_code == 200
    assert "_transaction_type" in response.json()["updated_fields"]

    db.refresh(document)
    assert document.ocr_result["_transaction_type"] == "income"
    assert document.ocr_result["document_transaction_direction"] == "income"


def test_document_correction_learns_two_income_rules_for_two_line_items(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="income-two-items@example.com",
        user_type=UserType.MIXED,
        business_type="gewerbe",
        business_industry="it",
    )
    user.email_verified = True
    db.commit()
    db.refresh(user)

    parent_description = "Consulting package March 2024"
    item_one = "IT-Beratung Softwarearchitektur (Jan-Mar 2024 120 Std.)"
    item_two = "Workshop Anforderungsanalyse (2 Tage)"

    document = create_test_document(
        db,
        user,
        document_type=DocumentType.INVOICE,
        file_name="income-multi-item.pdf",
        file_size=1024,
        mime_type="application/pdf",
        ocr_result={
            "merchant": "DI Maria Steiner",
            "description": parent_description,
            "_transaction_type": "expense",
            "line_items": [
                {
                    "description": item_one,
                    "amount": 10200,
                    "quantity": 1,
                    "category": "professional_services",
                    "is_deductible": True,
                },
                {
                    "description": item_two,
                    "amount": 2000,
                    "quantity": 1,
                    "category": "professional_services",
                    "is_deductible": True,
                },
            ],
        },
        raw_text="consulting invoice",
        confidence_score=0.9,
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/correct",
        headers=_auth_headers(user.email),
        json={
            "corrected_data": {
                "_transaction_type": "income",
                "document_transaction_direction": "income",
                "line_items": [
                    {
                        "description": item_one,
                        "amount": 10200,
                        "quantity": 1,
                        "category": "self_employment",
                        "is_deductible": False,
                    },
                    {
                        "description": item_two,
                        "amount": 2000,
                        "quantity": 1,
                        "category": "self_employment",
                        "is_deductible": False,
                    },
                ],
                "items": [
                    {
                        "description": item_one,
                        "amount": 10200,
                        "quantity": 1,
                        "category": "self_employment",
                        "is_deductible": False,
                    },
                    {
                        "description": item_two,
                        "amount": 2000,
                        "quantity": 1,
                        "category": "self_employment",
                        "is_deductible": False,
                    },
                ],
            }
        },
    )

    assert response.status_code == 200

    classification_rules = (
        db.query(UserClassificationRule)
        .filter(UserClassificationRule.user_id == user.id)
        .order_by(UserClassificationRule.id.asc())
        .all()
    )

    assert len(classification_rules) == 2
    assert all(rule.txn_type == "income" for rule in classification_rules)
    assert all(rule.category == "self_employment" for rule in classification_rules)
    assert not any(
        rule.original_description == f"DI Maria Steiner: {parent_description}"
        for rule in classification_rules
    )


def test_document_correction_replaces_expense_rules_when_switching_to_income(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="expense-to-income-rules@example.com",
        user_type=UserType.MIXED,
        business_type="gewerbe",
        business_industry="it",
    )
    user.email_verified = True
    db.commit()
    db.refresh(user)

    parent_description = "ACME Studio: Consulting invoice"
    classification_service = UserClassificationService(db)
    deductibility_service = UserDeductibilityService(db)
    classification_service.upsert_rule(
        user_id=user.id,
        description=parent_description,
        txn_type="expense",
        category="professional_services",
    )
    deductibility_service.upsert_rule(
        user_id=user.id,
        description=parent_description,
        expense_category="professional_services",
        is_deductible=True,
        reason="Old expense rule.",
    )
    db.commit()

    document = create_test_document(
        db,
        user,
        document_type=DocumentType.INVOICE,
        file_name="expense-to-income.pdf",
        file_size=1024,
        mime_type="application/pdf",
        ocr_result={
            "merchant": "ACME Studio",
            "description": "Consulting invoice",
            "_transaction_type": "expense",
            "line_items": [
                {
                    "description": "Consulting invoice",
                    "amount": 299,
                    "quantity": 1,
                    "category": "professional_services",
                    "is_deductible": True,
                }
            ],
        },
        raw_text="Consulting invoice",
        confidence_score=0.82,
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/correct",
        headers=_auth_headers(user.email),
        json={
            "corrected_data": {
                "_transaction_type": "income",
                "document_transaction_direction": "income",
                "line_items": [
                    {
                        "description": "Consulting invoice",
                        "amount": 299,
                        "quantity": 1,
                        "category": "self_employment",
                        "is_deductible": False,
                    }
                ],
                "items": [
                    {
                        "description": "Consulting invoice",
                        "amount": 299,
                        "quantity": 1,
                        "category": "self_employment",
                        "is_deductible": False,
                    }
                ],
            }
        },
    )

    assert response.status_code == 200

    classification_rules = (
        db.query(UserClassificationRule)
        .filter(UserClassificationRule.user_id == user.id)
        .order_by(UserClassificationRule.id.asc())
        .all()
    )
    deductibility_rules = (
        db.query(UserDeductibilityRule)
        .filter(UserDeductibilityRule.user_id == user.id)
        .order_by(UserDeductibilityRule.id.asc())
        .all()
    )

    assert len(classification_rules) == 1
    assert classification_rules[0].txn_type == "income"
    assert classification_rules[0].category == "self_employment"
    assert len(deductibility_rules) == 0
