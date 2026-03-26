"""Integration tests for the current document upload and OCR review contracts."""

from datetime import datetime, timedelta
from decimal import Decimal
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw

from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.document import Document, DocumentType
from app.models.plan import BillingCycle, Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User


class InMemoryStorageService:
    """Simple storage stub for upload/download integration tests."""

    def __init__(self):
        self.files = {}

    def upload_file(self, file_bytes: bytes, file_path: str, content_type=None) -> bool:
        self.files[file_path] = file_bytes
        return True

    def download_file(self, file_path: str):
        return self.files.get(file_path)

    def delete_file(self, file_path: str) -> bool:
        self.files.pop(file_path, None)
        return True


def _make_image_bytes(label: str, *, color: str = "white") -> io.BytesIO:
    image = Image.new("RGB", (800, 600), color=color)
    draw = ImageDraw.Draw(image)
    draw.text((40, 40), label, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def _seed_ocr_access(db, user: User, *, credits: int = 5) -> None:
    """Provision OCR feature access using the current credit contracts."""
    now = datetime.utcnow()

    pro_plan = Plan(
        plan_type=PlanType.PRO,
        name="Pro",
        monthly_price=Decimal("9.90"),
        yearly_price=Decimal("99.00"),
        features={"ocr_scanning": True},
        quotas={"ocr_scans": -1},
        monthly_credits=credits,
        overage_price_per_credit=Decimal("0.0500"),
    )
    db.add(pro_plan)
    db.flush()

    subscription = Subscription(
        user_id=user.id,
        plan_id=pro_plan.id,
        status=SubscriptionStatus.ACTIVE,
        billing_cycle=BillingCycle.MONTHLY,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db.add(subscription)
    db.flush()

    user.subscription_id = subscription.id
    db.add(
        CreditCostConfig(
            operation="ocr_scan",
            credit_cost=1,
            description="OCR scan",
            pricing_version=1,
            is_active=True,
        )
    )
    db.add(
        CreditBalance(
            user_id=user.id,
            plan_balance=credits,
            topup_balance=0,
            overage_enabled=False,
            overage_credits_used=0,
            has_unpaid_overage=False,
            unpaid_overage_periods=0,
        )
    )
    db.commit()


@pytest.fixture
def ocr_enabled_user(db, test_user):
    user = db.query(User).filter(User.email == test_user["email"]).first()
    _seed_ocr_access(db, user)
    db.refresh(user)
    return user


@pytest.fixture
def ocr_authenticated_client(client, test_user, ocr_enabled_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {token}",
    }
    return client


@pytest.fixture
def processed_receipt_document(db, ocr_enabled_user):
    document = Document(
        user_id=ocr_enabled_user.id,
        document_type=DocumentType.RECEIPT,
        file_path="/test/receipt.jpg",
        file_name="receipt.jpg",
        file_size=2048,
        mime_type="image/jpeg",
        raw_text="BILLA Supermarkt\nDatum: 15.01.2026\nSumme: 8.50 EUR",
        confidence_score=Decimal("0.82"),
        processed_at=datetime.utcnow(),
        ocr_result={
            "raw_text": "BILLA Supermarkt\nDatum: 15.01.2026\nSumme: 8.50 EUR",
            "extracted_data": {
                "date": "2026-01-15",
                "amount": 8.50,
                "merchant": "BILLA",
                "date_confidence": 0.91,
                "amount_confidence": 0.88,
                "merchant_confidence": 0.86,
            },
        },
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


class TestDocumentUploadCurrentContracts:
    """Current upload behavior: feature-gated, credit-backed, storage-backed."""

    def test_upload_single_document_deducts_credit_and_returns_metadata(
        self,
        ocr_authenticated_client,
        ocr_enabled_user,
        db,
    ):
        storage = InMemoryStorageService()
        files = {
            "file": ("receipt.jpg", _make_image_bytes("Receipt #1"), "image/jpeg")
        }

        with patch(
            "app.api.v1.endpoints.documents.get_storage_service",
            return_value=storage,
        ), patch(
            "app.api.v1.endpoints.documents._schedule_ocr_processing"
        ) as mock_schedule:
            response = ocr_authenticated_client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["file_name"] == "receipt.jpg"
        assert data["mime_type"] == "image/jpeg"
        assert data["document_type"] == "other"
        assert data["deduplicated"] is False
        assert response.headers["X-Credits-Remaining"] == "4"

        document = db.query(Document).filter(Document.id == data["id"]).first()
        assert document is not None
        assert document.user_id == ocr_enabled_user.id
        assert storage.download_file(document.file_path) is not None
        mock_schedule.assert_called_once()

        balance = (
            db.query(CreditBalance)
            .filter(CreditBalance.user_id == ocr_enabled_user.id)
            .first()
        )
        assert balance.plan_balance == 4

    def test_batch_upload_stops_after_credits_are_exhausted(
        self,
        ocr_authenticated_client,
        ocr_enabled_user,
        db,
    ):
        balance = (
            db.query(CreditBalance)
            .filter(CreditBalance.user_id == ocr_enabled_user.id)
            .first()
        )
        balance.plan_balance = 1
        db.commit()

        storage = InMemoryStorageService()
        files = [
            ("files", ("receipt-1.jpg", _make_image_bytes("Receipt A", color="white"), "image/jpeg")),
            ("files", ("receipt-2.jpg", _make_image_bytes("Receipt B", color="lightgray"), "image/jpeg")),
        ]

        with patch(
            "app.api.v1.endpoints.documents.get_storage_service",
            return_value=storage,
        ), patch("app.api.v1.endpoints.documents._schedule_ocr_processing"):
            response = ocr_authenticated_client.post("/api/v1/documents/batch-upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["total_uploaded"] == 1
        assert len(data["successful"]) == 1
        assert len(data["failed"]) == 1
        assert "Insufficient credits" in data["failed"][0]["error"]

        db.refresh(balance)
        assert balance.plan_balance == 0

    def test_upload_invalid_file_type_is_rejected(self, ocr_authenticated_client):
        files = {
            "file": ("document.txt", io.BytesIO(b"plain text"), "text/plain")
        }

        response = ocr_authenticated_client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 400
        assert "Invalid file format" in response.json()["detail"]

    def test_upload_requires_authentication(self, client):
        files = {
            "file": ("receipt.jpg", _make_image_bytes("Unauthenticated"), "image/jpeg")
        }
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code in (401, 403)


class TestOCRReviewAndCorrectionCurrentContracts:
    """Current OCR review flow for processed documents."""

    def test_review_ocr_results_returns_field_confidences(
        self,
        ocr_authenticated_client,
        processed_receipt_document,
    ):
        response = ocr_authenticated_client.get(
            f"/api/v1/documents/{processed_receipt_document.id}/review"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == processed_receipt_document.id
        assert data["document_type"] == "receipt"
        assert data["overall_confidence"] == 0.82
        field_names = {field["field_name"] for field in data["extracted_fields"]}
        assert {"date", "amount", "merchant"} <= field_names

    def test_review_ocr_results_recovers_tax_fields_for_bescheid_documents(
        self,
        ocr_authenticated_client,
        ocr_enabled_user,
        db,
    ):
        raw_text = """
        REPUBLIK OESTERREICH
        DI Maria Steiner
        FA: Finanzamt Oesterreich
        St.Nr. 09-123/4567
        Steuerberechnung fuer 2023
        EINKOMMENSTEUERBESCHEID 2023
        Einkuenfte aus selbstaendiger Arbeit (KZ 320) EUR 42.850,00
        Einkommen EUR 42.200,00
        Festgesetzte Einkommensteuer EUR 8.957,50
        Abgabennachforderung EUR 957,50
        """.strip()

        document = Document(
            user_id=ocr_enabled_user.id,
            document_type=DocumentType.EINKOMMENSTEUERBESCHEID,
            file_name="A23_Einkommensteuerbescheid_2023_4S.pdf",
            file_path="documents/A23_Einkommensteuerbescheid_2023_4S.pdf",
            file_size=2048,
            mime_type="application/pdf",
            confidence_score=0.95,
            processed_at=datetime.utcnow(),
            raw_text=raw_text,
            ocr_result={
                "date": "2024-09-15",
                "amount": 957.5,
                "merchant": "Finanzamt Österreich",
                "description": "Einkommensteuerbescheid für das Jahr 2023",
                "tax_id": "09-123/4567",
                "commercial_document_semantics": "invoice",
                "document_transaction_direction": "expense",
                "document_transaction_direction_source": "issuer",
                "is_reversal": False,
            },
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        response = ocr_authenticated_client.get(
            f"/api/v1/documents/{document.id}/review"
        )

        assert response.status_code == 200
        data = response.json()
        field_names = {field["field_name"] for field in data["extracted_fields"]}
        assert "tax_year" in field_names
        assert "taxpayer_name" in field_names
        assert "festgesetzte_einkommensteuer" in field_names
        assert "abgabennachforderung" in field_names
        assert "merchant" not in field_names
        assert "amount" not in field_names

    def test_confirm_ocr_results_marks_document_confirmed(
        self,
        ocr_authenticated_client,
        processed_receipt_document,
        ocr_enabled_user,
        db,
    ):
        with patch(
            "app.services.ocr_transaction_service.OCRTransactionService.create_transaction_suggestion",
            return_value=None,
        ):
            response = ocr_authenticated_client.post(
                f"/api/v1/documents/{processed_receipt_document.id}/confirm",
                json={"confirmed": True, "notes": "Looks correct"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == processed_receipt_document.id
        assert "confirmed successfully" in data["message"]
        assert data["can_create_transaction"] is True

        db.refresh(processed_receipt_document)
        assert processed_receipt_document.ocr_result["confirmed"] is True
        assert processed_receipt_document.ocr_result["confirmed_by"] == ocr_enabled_user.id
        assert processed_receipt_document.ocr_result["confirmation_notes"] == "Looks correct"

    def test_correct_ocr_results_updates_data_and_confidence(
        self,
        ocr_authenticated_client,
        processed_receipt_document,
        db,
    ):
        response = ocr_authenticated_client.post(
            f"/api/v1/documents/{processed_receipt_document.id}/correct",
            json={
                "corrected_data": {
                    "merchant": "BILLA Plus",
                    "amount": 9.10,
                },
                "notes": "Corrected merchant spelling",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert set(data["updated_fields"]) == {"merchant", "amount"}
        assert data["previous_confidence"] == 0.82
        assert data["new_confidence"] == 1.0
        assert data["correction_recorded"] is True

        db.refresh(processed_receipt_document)
        extracted = processed_receipt_document.ocr_result["extracted_data"]
        assert extracted["merchant"] == "BILLA Plus"
        assert extracted["amount"] == 9.10
        assert processed_receipt_document.confidence_score == Decimal("1.00")

    def test_confirm_ocr_results_consumes_multi_stored_transaction_suggestions(
        self,
        ocr_authenticated_client,
        processed_receipt_document,
        db,
    ):
        processed_receipt_document.ocr_result = {
            **processed_receipt_document.ocr_result,
            "tax_analysis": {
                "items": [
                    {
                        "amount": "5.50",
                        "date": "2026-01-15",
                        "description": "BILLA groceries",
                        "category": "other",
                        "needs_review": True,
                        "reviewed": False,
                        "status": "pending-review",
                    },
                    {
                        "amount": "3.00",
                        "date": "2026-01-15",
                        "description": "BILLA bakery",
                        "category": "other",
                        "needs_review": True,
                        "reviewed": False,
                        "status": "manual-review-required",
                    },
                ]
            },
        }
        db.add(processed_receipt_document)
        db.commit()
        db.refresh(processed_receipt_document)

        creation_results = [
            MagicMock(
                transaction=MagicMock(id=501),
                created=True,
                duplicate_of_id=None,
                duplicate_confidence=None,
            ),
            MagicMock(
                transaction=MagicMock(id=502),
                created=False,
                duplicate_of_id=502,
                duplicate_confidence=0.91,
            ),
        ]

        with patch(
            "app.services.ocr_transaction_service.OCRTransactionService.create_transaction_from_suggestion_with_result",
            side_effect=creation_results,
        ) as mock_create, patch(
            "app.services.ocr_transaction_service.OCRTransactionService.create_transaction_suggestion",
            side_effect=AssertionError("legacy suggestion regeneration should not run"),
        ):
            response = ocr_authenticated_client.post(
                f"/api/v1/documents/{processed_receipt_document.id}/confirm",
                json={"confirmed": True},
            )

        assert response.status_code == 200
        assert mock_create.call_count == 2
        data = response.json()
        assert "2 transactions were finalized" in data["message"]
        assert data["can_create_transaction"] is False

        db.refresh(processed_receipt_document)
        items = processed_receipt_document.ocr_result["tax_analysis"]["items"]
        assert items[0]["transaction_id"] == 501
        assert items[0]["status"] == "confirmed"
        assert items[0]["needs_review"] is False
        assert items[0]["reviewed"] is True
        assert items[1]["transaction_id"] == 502
        assert items[1]["status"] == "confirmed"
        assert items[1]["is_duplicate"] is True
        assert items[1]["duplicate_of_id"] == 502
        assert items[1]["needs_review"] is False
        assert items[1]["reviewed"] is True

    def test_correct_ocr_results_marks_multi_transaction_suggestions_stale(
        self,
        ocr_authenticated_client,
        processed_receipt_document,
        db,
    ):
        processed_receipt_document.ocr_result = {
            **processed_receipt_document.ocr_result,
            "transaction_suggestion": {
                "amount": "8.50",
                "date": "2026-01-15",
                "description": "BILLA groceries",
                "status": "pending-review",
            },
            "tax_analysis": {
                "items": [
                    {
                        "amount": "5.50",
                        "date": "2026-01-15",
                        "description": "BILLA groceries",
                        "status": "pending-review",
                    },
                    {
                        "amount": "3.00",
                        "date": "2026-01-15",
                        "description": "BILLA bakery",
                        "status": "manual-review-required",
                    },
                ]
            },
        }
        db.add(processed_receipt_document)
        db.commit()
        db.refresh(processed_receipt_document)

        with patch(
            "app.tasks.ocr_tasks.refresh_contract_role_sensitive_suggestions",
            return_value=None,
        ):
            response = ocr_authenticated_client.post(
                f"/api/v1/documents/{processed_receipt_document.id}/correct",
                json={
                    "corrected_data": {
                        "merchant": "BILLA Plus",
                    },
                    "notes": "refresh stale transaction suggestions",
                },
            )

        assert response.status_code == 200

        db.refresh(processed_receipt_document)
        items = processed_receipt_document.ocr_result["tax_analysis"]["items"]
        assert items[0]["_stale"] is True
        assert items[1]["_stale"] is True
