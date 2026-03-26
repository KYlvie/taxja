from datetime import datetime
from decimal import Decimal

from app.models.document import Document, DocumentType
from app.models.transaction import ExpenseCategory, TransactionType
from app.models.user import User, UserType
from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator,
    ValidationResult,
)
from app.services.ocr_transaction_service import OCRTransactionService


def _make_user(db, email: str = "normalization-int@example.com") -> User:
    user = User(
        email=email,
        password_hash="hashed",
        name="Normalization Integration User",
        user_type=UserType.SELF_EMPLOYED,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_document(
    db,
    user_id: int,
    *,
    file_name: str,
    document_type: DocumentType = DocumentType.INVOICE,
    raw_text: str | None = None,
    ocr_result=None,
) -> Document:
    document = Document(
        user_id=user_id,
        document_type=document_type,
        file_path=f"users/{user_id}/documents/{file_name}",
        file_name=file_name,
        file_hash=None,
        file_size=1024,
        mime_type="application/pdf",
        raw_text=raw_text,
        ocr_result=ocr_result,
        uploaded_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_reverse_charge_invoice_sample_normalizes_and_creates_transaction_without_domestic_vat(
    db,
):
    user = _make_user(db, email="reverse-charge-int@example.com")
    document = _make_document(
        db,
        user.id,
        file_name="notion-reverse-charge.pdf",
        document_type=DocumentType.INVOICE,
    )

    orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
    validation = ValidationResult(is_valid=True)
    extracted = {
        "amount": "96,00",
        "date": "02.01.2024",
        "merchant": "Notion Labs Inc.",
        "description": "Notion Plus Plan - Annual (Jan-Dec 2024)",
        "invoice_text": (
            "Reverse Charge - Steuerschuldnerschaft des Leistungsempfängers"
        ),
    }

    orchestrator._autofix_amount(extracted, validation)
    orchestrator._autofix_date(extracted, validation)
    orchestrator._validate_invoice(extracted, validation)
    extracted.update(validation.corrected_fields)

    assert validation.error_count == 0
    assert extracted["amount"] == 96.0
    assert extracted["date"] == "2024-01-02"
    assert "vat_rate" not in validation.corrected_fields
    assert "vat_amount" not in validation.corrected_fields
    assert any(
        "reverse-charge indicators detected" in issue.issue
        for issue in validation.issues
    )

    service = OCRTransactionService(db)
    result = service.create_transaction_from_suggestion_with_result(
        {
            "document_id": document.id,
            "amount": extracted["amount"],
            "date": extracted["date"],
            "description": extracted["description"],
            "transaction_type": TransactionType.EXPENSE.value,
            "category": ExpenseCategory.SOFTWARE.value,
            "confidence": 0.95,
            "needs_review": False,
            "reviewed": True,
            "is_deductible": True,
        },
        user.id,
    )

    assert result.created is True
    transaction = result.transaction
    assert transaction.amount == Decimal("96.00")
    assert transaction.transaction_date.isoformat() == "2024-01-02"
    assert transaction.vat_rate is None
    assert transaction.vat_amount is None
    assert transaction.reviewed is True
    assert transaction.needs_review is False


def test_receipt_sample_normalizes_explicit_line_items_end_to_end(db):
    user = _make_user(db, email="line-items-explicit@example.com")
    document = _make_document(
        db,
        user.id,
        file_name="office-supplies.pdf",
        document_type=DocumentType.RECEIPT,
    )

    service = OCRTransactionService(db)
    result = service.create_transaction_from_suggestion_with_result(
        {
            "document_id": document.id,
            "amount": "18,00",
            "date": "19. Dez. 2024",
            "description": "Office supplies",
            "transaction_type": TransactionType.EXPENSE.value,
            "category": ExpenseCategory.OFFICE_SUPPLIES.value,
            "confidence": 0.91,
            "needs_review": False,
            "reviewed": True,
            "line_items": [
                {
                    "description": "Printer paper",
                    "total_price": "18,00",
                    "quantity": "2 Stück",
                    "vat_rate": "20 %",
                    "is_deductible": "ja",
                    "currency": "EUR",
                }
            ],
        },
        user.id,
    )

    transaction = result.transaction
    assert transaction.amount == Decimal("18.00")
    assert transaction.transaction_date.isoformat() == "2024-12-19"
    assert len(transaction.line_items) == 1
    line_item = transaction.line_items[0]
    assert line_item.description == "Printer paper"
    assert line_item.amount == Decimal("9.00")
    assert line_item.quantity == 2
    assert line_item.vat_rate == Decimal("0.2000")
    assert line_item.is_deductible is True


def test_invoice_sample_normalizes_document_backed_line_items_when_syncing_from_ocr_result(
    db,
):
    user = _make_user(db, email="line-items-document@example.com")
    document = _make_document(
        db,
        user.id,
        file_name="consulting-invoice.pdf",
        document_type=DocumentType.INVOICE,
        ocr_result={
            "tax_analysis": {
                "items": [
                    {
                        "description": "Systemanalyse + Sicherheitsaudit",
                        "total_price": "9.500,00",
                        "quantity": "1,0",
                        "vat_rate": "20 %",
                        "is_deductible": "ja",
                        "currency": "EUR",
                    },
                    {
                        "description": "Penetration Test Report",
                        "total": "3.500,00",
                        "quantity": "1",
                        "status": "bezahlt",
                        "currency": "EUR",
                    },
                ]
            }
        },
    )

    service = OCRTransactionService(db)
    result = service.create_transaction_from_suggestion_with_result(
        {
            "document_id": document.id,
            "amount": "13.000,00",
            "date": "30.06.2024",
            "description": "Invoice from DI Maria Steiner",
            "transaction_type": TransactionType.INCOME.value,
            "category": "self_employment",
            "confidence": 0.94,
            "needs_review": False,
            "reviewed": True,
        },
        user.id,
    )

    transaction = result.transaction
    assert transaction.amount == Decimal("13000.00")
    assert transaction.transaction_date.isoformat() == "2024-06-30"
    assert len(transaction.line_items) == 2

    first_item = transaction.line_items[0]
    second_item = transaction.line_items[1]

    assert first_item.amount == Decimal("9500.00")
    assert first_item.quantity == 1
    assert first_item.vat_rate == Decimal("0.2000")
    assert first_item.is_deductible is False
    assert second_item.amount == Decimal("3500.00")
    assert second_item.quantity == 1
