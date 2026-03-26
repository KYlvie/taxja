from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.document import DocumentType
from app.models.user import UserType
from app.services.ocr_transaction_service import OCRTransactionService
from app.services.transaction_rule_resolver import TransactionRuleResolver
from app.services.user_classification_service import UserClassificationService
from app.services.user_deductibility_service import UserDeductibilityService
from tests.fixtures.models import create_test_document, create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_auto_rule_stays_bank_import_only(db_session: Session):
    user = create_test_user(
        db_session,
        email="auto-scope@example.com",
        user_type=UserType.MIXED,
        business_type="gewerbe",
        business_industry="it",
    )
    user.email_verified = True
    db_session.commit()

    UserClassificationService(db_session).upsert_rule(
        user_id=user.id,
        description="Helvetia Versicherungen AG",
        txn_type="expense",
        category="insurance",
        rule_type="auto",
    )
    db_session.commit()

    resolver = TransactionRuleResolver(db_session)

    ocr_result = resolver.resolve(
        user_id=user.id,
        context="ocr_receipt",
        txn_type="expense",
        canonical_description="Helvetia Versicherungen AG",
    )
    assert ocr_result.resolved_category is None
    assert ocr_result.classification_rule_id is None

    bank_import_result = resolver.resolve(
        user_id=user.id,
        context="bank_import",
        txn_type="expense",
        canonical_description="Helvetia Versicherungen AG",
    )
    assert bank_import_result.resolved_category == "insurance"
    assert bank_import_result.classification_rule_id is not None


def test_multi_item_same_category_rules_resolve_single_category(db_session: Session):
    user = create_test_user(
        db_session,
        email="multi-item-rules@example.com",
        user_type=UserType.MIXED,
        business_type="gewerbe",
        business_industry="it",
    )
    user.email_verified = True
    db_session.commit()

    classification_service = UserClassificationService(db_session)
    classification_service.upsert_rule(
        user_id=user.id,
        description="DI Maria Steiner: Consulting package IT-Beratung",
        txn_type="income",
        category="self_employment",
    )
    classification_service.upsert_rule(
        user_id=user.id,
        description="DI Maria Steiner: Consulting package Workshop",
        txn_type="income",
        category="self_employment",
    )
    db_session.commit()

    resolver = TransactionRuleResolver(db_session)
    result = resolver.resolve(
        user_id=user.id,
        context="ocr_receipt",
        txn_type="income",
        canonical_description="DI Maria Steiner: Consulting package",
        line_items=[
            {"description": "IT-Beratung"},
            {"description": "Workshop"},
        ],
    )

    assert result.resolved_category == "self_employment"
    assert result.classification_rule_id is not None


def test_ocr_receipt_reuses_learned_classification_and_deductibility_rules(
    client: TestClient,
    db: Session,
):
    user = create_test_user(
        db,
        email="ocr-rule-hit@example.com",
        user_type=UserType.MIXED,
        business_type="gewerbe",
        business_industry="beherbergung",
    )
    user.email_verified = True
    db.commit()
    db.refresh(user)

    initial_document = create_test_document(
        db,
        user,
        document_type=DocumentType.RECEIPT,
        file_name="first-receipt.pdf",
        file_size=1024,
        mime_type="application/pdf",
        ocr_result={
            "merchant": "Tankautomat Leissenaach",
            "amount": 10.91,
            "date": "2026-03-25",
            "_transaction_type": "expense",
            "line_items": [
                {
                    "description": "Säule 1",
                    "amount": 9.85,
                    "quantity": 4.925,
                    "category": "other",
                    "is_deductible": False,
                    "deduction_reason": "Initial OCR guess.",
                }
            ],
        },
        raw_text="Tankautomat Leissenaach 15.03.2026 ref 999999 unrelated groceries text",
        confidence_score=0.78,
    )

    correction_response = client.post(
        f"/api/v1/documents/{initial_document.id}/correct",
        headers=_auth_headers(user.email),
        json={
            "corrected_data": {
                "line_items": [
                    {
                        "description": "Säule 1",
                        "amount": 9.85,
                        "quantity": 4.925,
                        "category": "fuel",
                        "is_deductible": True,
                        "deduction_reason": "Vehicle fuel used for lodging business procurement.",
                    }
                ],
                "items": [
                    {
                        "description": "Säule 1",
                        "amount": 9.85,
                        "quantity": 4.925,
                        "category": "fuel",
                        "is_deductible": True,
                        "deduction_reason": "Vehicle fuel used for lodging business procurement.",
                    }
                ],
            }
        },
    )
    assert correction_response.status_code == 200

    follow_up_document = create_test_document(
        db,
        user,
        document_type=DocumentType.RECEIPT,
        file_name="second-receipt.pdf",
        file_size=1024,
        mime_type="application/pdf",
        ocr_result={
            "merchant": "Tankautomat Leissenaach",
            "amount": 10.91,
            "date": "2026-04-02",
            "_transaction_type": "expense",
            "line_items": [
                {
                    "description": "Säule 1",
                    "amount": 9.85,
                    "quantity": 4.925,
                    "category": "other",
                    "is_deductible": False,
                    "deduction_reason": "OCR uncertain.",
                }
            ],
        },
        raw_text="Tankautomat Leissenaach 02.04.2026 ref 888888 account info and extra OCR noise",
        confidence_score=0.76,
    )

    suggestion = OCRTransactionService(db).create_transaction_suggestion(
        follow_up_document.id,
        user.id,
    )

    assert suggestion is not None
    assert suggestion["category"] == "fuel"
    assert suggestion["is_deductible"] is True
    assert suggestion["classification_method"] == "user_rule"
    assert suggestion["classification_rule_id"] is not None
    assert suggestion["deductibility_rule_id"] is not None
    assert "classification:strict" in suggestion["applied_rule_sources"]
    assert "deductibility:user_rule" in suggestion["applied_rule_sources"]


def test_frozen_soft_rule_does_not_override_ocr_receipt(db_session: Session):
    user = create_test_user(
        db_session,
        email="frozen-soft-rule@example.com",
        user_type=UserType.MIXED,
        business_type="gewerbe",
        business_industry="it",
    )
    user.email_verified = True
    db_session.commit()

    classification_service = UserClassificationService(db_session)
    rule = classification_service.upsert_rule(
        user_id=user.id,
        description="Amazon Druckerpatrone",
        txn_type="expense",
        category="office_supplies",
        rule_type="soft",
    )
    rule.frozen = True
    db_session.commit()

    document = create_test_document(
        db_session,
        user,
        document_type=DocumentType.RECEIPT,
        file_name="amazon-receipt.pdf",
        file_size=1024,
        mime_type="application/pdf",
        ocr_result={
            "merchant": "Amazon",
            "description": "Druckerpatrone",
            "amount": 22.50,
            "date": "2026-03-15",
        },
        raw_text="Amazon Druckerpatrone 12345",
        confidence_score=0.6,
    )

    suggestion = OCRTransactionService(db_session).create_transaction_suggestion(
        document.id,
        user.id,
    )

    assert suggestion is not None
    assert suggestion["classification_rule_id"] is None
    assert suggestion["classification_method"] != "user_rule_soft"
