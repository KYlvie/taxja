from unittest.mock import MagicMock

from app.services.document_classifier import DocumentType
from app.services.ocr_engine import OCREngine, OCRResult


def _make_expected_result() -> OCRResult:
    return OCRResult(
        document_type=DocumentType.RECEIPT,
        extracted_data={"receipt_count": 4, "_receipt_count": 4},
        raw_text="vision-json",
        confidence_score=0.86,
        needs_review=True,
        processing_time_ms=12.0,
        suggestions=["Detected 4 receipts across 2 PDF page(s)."],
    )


def test_text_layer_pdf_receipt_uses_vlm_multi_receipt_path():
    engine = OCREngine()
    pdf_bytes = b"%PDF-1.4 fake text layer pdf"
    suspicious_text = """
    Rechnung
    SUMME 68,32 EUR
    Rechnung
    SUMME 64,72 EUR
    """
    expected = _make_expected_result()

    engine._extract_text_from_pdf = MagicMock(return_value=suspicious_text)
    engine.classifier.classify = MagicMock(return_value=(DocumentType.RECEIPT, 0.91))
    engine._try_vlm_pdf_multi_receipt_ocr = MagicMock(return_value=expected)
    engine._try_llm_extraction = MagicMock(return_value=None)

    result = engine.process_document(pdf_bytes)

    assert result is expected
    engine._try_vlm_pdf_multi_receipt_ocr.assert_called_once()
    assert engine._try_vlm_pdf_multi_receipt_ocr.call_args.args[:2] == (
        pdf_bytes,
        DocumentType.RECEIPT,
    )
    engine._try_llm_extraction.assert_not_called()


def test_scanned_pdf_receipt_uses_vlm_multi_receipt_path_before_llm():
    engine = OCREngine()
    pdf_bytes = b"%PDF-1.4 fake scanned pdf"
    partial_text = "Tankstelle\nSUMME 65,46 EUR"
    suspicious_text = """
    --- PAGE 1 ---
    Rechnung
    SUMME 65,46 EUR

    Rechnung
    SUMME 64,72 EUR
    """
    expected = _make_expected_result()

    ocr_pages = [partial_text, suspicious_text]

    engine._extract_text_from_pdf = MagicMock(return_value="")
    engine._ocr_all_pdf_pages = MagicMock(side_effect=lambda *_args, **_kwargs: ocr_pages.pop(0))
    engine.classifier.classify = MagicMock(return_value=(DocumentType.RECEIPT, 0.87))
    engine._try_vlm_pdf_multi_receipt_ocr = MagicMock(return_value=expected)
    engine._try_llm_extraction = MagicMock(return_value=None)

    result = engine.process_document(pdf_bytes)

    assert result is expected
    engine._ocr_all_pdf_pages.assert_any_call(pdf_bytes, max_pages=2)
    engine._ocr_all_pdf_pages.assert_any_call(pdf_bytes, max_pages=5)
    engine._try_vlm_pdf_multi_receipt_ocr.assert_called_once()
    assert engine._try_vlm_pdf_multi_receipt_ocr.call_args.args[:2] == (
        pdf_bytes,
        DocumentType.RECEIPT,
    )
    engine._try_llm_extraction.assert_not_called()


def test_multi_receipt_pdf_heuristic_triggers_for_multiple_totals():
    engine = OCREngine()
    raw_text = """
    Rechnung
    SUMME 68,32 EUR

    Rechnung
    SUMME 64,72 EUR
    """

    assert engine._should_try_vlm_multi_receipt_pdf(raw_text, DocumentType.RECEIPT) is True
    assert engine._should_try_vlm_multi_receipt_pdf(raw_text, DocumentType.INVOICE) is True
    assert engine._should_try_vlm_multi_receipt_pdf(raw_text, DocumentType.KAUFVERTRAG) is False
