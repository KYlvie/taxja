from datetime import datetime, timedelta
from types import SimpleNamespace

from app.models.document import DocumentType
from app.schemas.document import DocumentDetail


def _make_document_stub(**overrides):
    now = datetime.utcnow()
    base = {
        "id": 1,
        "user_id": 1,
        "document_type": DocumentType.RECEIPT,
        "file_name": "receipt.png",
        "file_size": 1024,
        "mime_type": "image/png",
        "file_path": "users/1/documents/receipt.png",
        "ocr_result": None,
        "raw_text": None,
        "confidence_score": 0.8,
        "transaction_id": None,
        "uploaded_at": now,
        "processed_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_document_detail_marks_recent_finalizing_document_as_processing():
    started_at = (datetime.utcnow() - timedelta(minutes=2)).isoformat()
    document = _make_document_stub(
        ocr_result={
            "_pipeline": {
                "current_state": "finalizing",
                "phase_checkpoints": [
                    {
                        "checkpoint": "finalization",
                        "status": "started",
                        "started_at": started_at,
                        "completed_at": None,
                    }
                ],
            }
        }
    )

    detail = DocumentDetail.from_orm(document)

    assert detail.ocr_status == "processing"


def test_document_detail_marks_stale_finalizing_document_as_failed():
    started_at = (datetime.utcnow() - timedelta(minutes=6)).isoformat()
    document = _make_document_stub(
        ocr_result={
            "_pipeline": {
                "current_state": "finalizing",
                "phase_checkpoints": [
                    {
                        "checkpoint": "finalization",
                        "status": "started",
                        "started_at": started_at,
                        "completed_at": None,
                    }
                ],
            }
        }
    )

    detail = DocumentDetail.from_orm(document)

    assert detail.ocr_status == "failed"


def test_document_detail_marks_processed_document_as_completed():
    document = _make_document_stub(
        processed_at=datetime.utcnow(),
        ocr_result={"_pipeline": {"current_state": "completed"}},
    )

    detail = DocumentDetail.from_orm(document)

    assert detail.ocr_status == "completed"


def test_document_detail_does_not_mark_confirmed_import_outcome_as_needing_review():
    document = _make_document_stub(
        processed_at=datetime.utcnow(),
        confidence_score=0.95,
        ocr_result={
            "confirmed": False,
            "import_suggestion": {"status": "confirmed"},
        },
    )

    detail = DocumentDetail.from_orm(document)

    assert detail.needs_review is False


def test_document_detail_keeps_medium_confidence_transaction_pending_review():
    document = _make_document_stub(
        processed_at=datetime.utcnow(),
        confidence_score=0.8,
        transaction_id=123,
        ocr_result={"confirmed": False},
    )

    detail = DocumentDetail.from_orm(document)

    assert detail.needs_review is True


def test_document_detail_treats_high_confidence_linked_transaction_as_final_outcome():
    document = _make_document_stub(
        processed_at=datetime.utcnow(),
        confidence_score=0.95,
        transaction_id=456,
        ocr_result={"confirmed": False},
    )

    detail = DocumentDetail.from_orm(document)

    assert detail.needs_review is False
