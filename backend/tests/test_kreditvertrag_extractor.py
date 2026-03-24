from datetime import datetime

from app.models.document import DocumentType as DBDocumentType
from app.services.document_classifier import DocumentType as OCRDocumentType
from app.services.document_pipeline_orchestrator import OCR_TO_DB_TYPE_MAP
from app.services.kreditvertrag_extractor import KreditvertragExtractor
from app.services.ocr_engine import OCREngine


B14_STYLE_TEXT = """
KREDITVERTRAG
Vertragsnummer: 515-112233-4455
1. Vertragsparteien
Kreditgeberin:
Erste Bank der oesterreichischen Sparkassen AG
Am Belvedere 1, 1100 Wien
FN 33209m, HG Wien
Kreditnehmer:
Ing. Klaus Bauer
geb. am 01.05.1983
Wiedner Hauptstrasse 63/2/14, 1040 Wien
2. Kreditbetrag und Verwendungszweck
Kreditbetrag:
EUR 290.000,00
Verwendungszweck:
Ankauf Eigentumswohnung
Argentinierstrasse 21/Top 12, 1040 Wien
Auszahlungstag:
01.05.2024
3. Laufzeit
Vertragsbeginn:
01.05.2024
Vertragsende:
30.04.2049
Laufzeit:
25 Jahre (300 Monate)
Erste Rate:
01.06.2024
4. Zinssatz und Konditionen
Aktueller Zinssatz:
3,750% p.a.
5. Rueckzahlung
Tilgungsform:
Annuitaet
Monatliche Rate:
EUR 1.508,33
"""


def test_kreditvertrag_extractor_extracts_happy_path_fields():
    extractor = KreditvertragExtractor()

    data = extractor.extract(B14_STYLE_TEXT)
    payload = extractor.to_dict(data)

    assert payload["contract_number"] == "515-112233-4455"
    assert payload["lender_name"] == "Erste Bank der oesterreichischen Sparkassen AG"
    assert payload["borrower_name"] == "Ing. Klaus Bauer"
    assert payload["kreditnehmer"] == "Ing. Klaus Bauer"
    assert payload["loan_amount"] == 290000.0
    assert payload["interest_rate"] == 3.75
    assert payload["monthly_payment"] == 1508.33
    assert payload["start_date"] == "2024-05-01"
    assert payload["end_date"] == "2049-04-30"
    assert payload["first_rate_date"] == "2024-06-01"
    assert payload["term_years"] == 25
    assert payload["term_months"] == 300
    assert payload["property_address"] == "Argentinierstrasse 21/Top 12, 1040 Wien"
    assert payload["confidence"] >= 0.9


def test_ocr_engine_normalizes_db_loan_hint():
    engine = OCREngine()

    normalized = engine._normalize_document_type_hint(DBDocumentType.LOAN_CONTRACT)

    assert normalized == OCRDocumentType.LOAN_CONTRACT
    assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.LOAN_CONTRACT] == DBDocumentType.LOAN_CONTRACT


def test_ocr_engine_routes_loan_hint_to_kreditvertrag_extractor():
    engine = OCREngine()

    result = engine._process_from_raw_text(
        B14_STYLE_TEXT,
        b"%PDF-1.4\n",
        start_time=datetime.now(),
        document_type_hint=OCRDocumentType.LOAN_CONTRACT,
        classification_confidence_hint=0.99,
    )

    assert result.document_type == OCRDocumentType.LOAN_CONTRACT
    assert result.extracted_data["loan_amount"] == 290000.0
    assert result.extracted_data["interest_rate"] == 3.75
    assert result.extracted_data["monthly_payment"] == 1508.33
    assert result.extracted_data["lender_name"] == "Erste Bank der oesterreichischen Sparkassen AG"
