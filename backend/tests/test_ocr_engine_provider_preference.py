from datetime import datetime
from unittest.mock import MagicMock

from app.services.document_classifier import DocumentType
from app.services.ocr_engine import OCREngine, OCRResult


def test_vlm_ocr_passes_provider_preference_to_llm(monkeypatch):
    engine = OCREngine()
    engine._vision_provider_preference = "anthropic"
    engine._vlm_multi_receipt_check = MagicMock(return_value=None)

    fake_llm = MagicMock()
    fake_llm.is_available = True
    fake_llm.generate_vision.return_value = """
    {
      "document_type": "receipt",
      "amount": 64.72,
      "merchant": "Test Tankstelle",
      "description": "Fuel",
      "line_items": [{"name": "Diesel", "total_price": 64.72}]
    }
    """

    monkeypatch.setattr(
        "app.services.llm_service.get_llm_service",
        lambda: fake_llm,
    )

    result = engine._try_vlm_ocr(
        image_bytes=b"fake-image",
        mime_type="image/png",
        start_time=datetime.utcnow(),
    )

    assert result is not None
    assert result.document_type == DocumentType.RECEIPT
    assert fake_llm.generate_vision.call_args.kwargs["provider_preference"] == "anthropic"


def test_tax_form_llm_fallback_passes_provider_preference_to_extractor():
    engine = OCREngine()
    engine._vision_provider_preference = "anthropic"

    fake_extractor = MagicMock()
    fake_extractor.is_available = True
    fake_extractor.extract.return_value = {"kz_029": 13684.40, "tax_year": 2019}
    engine.llm_extractor = fake_extractor

    result = engine._try_llm_tax_form_extraction(
        raw_text="U1 Umsatzsteuer 2019",
        doc_type=DocumentType.U1_FORM,
        regex_data={"tax_year": 2019},
        regex_confidence=0.25,
        start_time=datetime.utcnow(),
    )

    assert result is not None
    assert result.document_type == DocumentType.U1_FORM
    assert fake_extractor.extract.call_args.kwargs["provider_preference"] == "anthropic"


def test_claude_direct_retry_skips_standard_pdf_ocr(monkeypatch):
    engine = OCREngine()

    monkeypatch.setattr(
        engine,
        "_extract_text_from_pdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pdf text layer should not be used")),
    )
    monkeypatch.setattr(
        engine,
        "_ocr_all_pdf_pages",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("tesseract pdf OCR should not be used")),
    )
    monkeypatch.setattr(
        engine,
        "_extract_text_with_claude_direct",
        lambda *_args, **_kwargs: "U 1 Umsatzsteuererklaerung 2019 KZ 095 2988,40",
    )
    monkeypatch.setattr(
        engine,
        "_route_to_tax_form_extractor",
        lambda doc_type, raw_text, start_time: OCRResult(
            document_type=doc_type,
            extracted_data={"kz_095": 2988.40},
            raw_text=raw_text,
            confidence_score=0.94,
            needs_review=False,
            processing_time_ms=1.0,
            suggestions=[],
        ),
    )

    result = engine.process_document(
        b"%PDF-1.7 fake pdf bytes",
        mime_type="application/pdf",
        vision_provider_preference="anthropic",
        reprocess_mode="claude_direct",
        document_type_hint=DocumentType.U1_FORM,
    )

    assert result.document_type == DocumentType.U1_FORM
    assert result.provider_used == "anthropic"
    assert result.raw_text.startswith("U 1 Umsatzsteuer")
