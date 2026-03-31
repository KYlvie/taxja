"""OCR Engine — Vision-first document processing via llama-4-scout.

Sends PDF/image directly to vision model for classification + extraction
in a single API call. No Tesseract, no text extraction, no VLM layer.
"""
import base64
import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List

import fitz  # PyMuPDF for PDF→image conversion

logger = logging.getLogger(__name__)


# Keep DocumentType for backward compatibility with pipeline
from app.services.document_classifier import DocumentType


@dataclass
class OCRResult:
    """Result of document processing"""
    document_type: DocumentType
    extracted_data: Dict[str, Any]
    raw_text: str
    confidence_score: float
    needs_review: bool
    processing_time_ms: float
    suggestions: List[str]
    provider_used: Optional[str] = None
    classification_source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["document_type"] = self.document_type.value
        return result


@dataclass
class BatchOCRResult:
    """Result of batch processing"""
    results: List[OCRResult]
    total_processing_time_ms: float
    successful: int
    failed: int


# Vision prompt for llama-4-scout — one call does everything
VISION_SYSTEM = (
    "Du bist ein Experte für österreichische Steuer- und Finanzdokumente. "
    "Analysiere das Dokument-Bild und extrahiere alle relevanten Felder. "
    "ZAHLENFORMAT: Europäisch! '10.800,00' = 10800.00. "
    "Antworte NUR als JSON."
)

VISION_PROMPT = """\
Analysiere dieses Dokument und extrahiere:

{
  "document_type": "invoice|asset_purchase|svs_vorschreibung|versicherungspolizze|grundsteuerbescheid|lohnzettel|einkommensteuerbescheid|mietvertrag|mietvorschreibung|betriebskostenabrechnung|loan_contract|zinsbescheinigung|spendenbestaetigung|kirchenbeitrag|bank_statement|fahrtenbuch|homeoffice_nachweis|receipt|other",
  "confidence": 0.0-1.0,
  "creates": ["transaction", "asset", "recurring", "loan", "property", "archive_only"],
  "raw_text": "Vollständiger Text des Dokuments (so genau wie möglich abtippen)",
  "expense_or_income": "income|expense|archive_only",
  "amount": Hauptbetrag als Zahl oder null,
  "amount_brutto": Bruttobetrag oder null,
  "amount_netto": Nettobetrag oder null,
  "vat_amount": USt-Betrag oder null,
  "vat_rate": USt-Satz in Prozent oder null,
  "date": "YYYY-MM-DD",
  "description": "Kurzbeschreibung",
  "issuer": "Aussteller/Absender oder null",
  "recipient": "Empfänger oder null",
  "property_address": "Immobilienadresse oder null",
  "asset_type": "pkw|e_auto|lkw|fiskal_lkw|maschine|it_hardware|null",
  "is_deductible": true/false/null,
  "deduction_category": "Betriebsausgabe|Werbungskosten|Sonderausgaben|null",
  "tax_form": "E1a|E1b|E1|null",
  "svs_quarter": "Q1|Q2|Q3|Q4|null",
  "quarterly_amount": Quartalsbeitrag oder null,
  "insurance_subtype": "berufshaftpflicht|gebaeudeversicherung|kfz|other|null",
  "lender_name": "Bank/Kreditgeber oder null",
  "annual_interest": Jahreszinsen oder null
}"""


class OCREngine:
    """Vision-first document processor using llama-4-scout."""

    def __init__(self, config=None):
        self._config = config

    def process_document(
        self,
        image_bytes: bytes,
        mime_type: str = None,
        vision_provider_preference: Optional[str] = None,
        reprocess_mode: Optional[str] = None,
        document_type_hint: Optional[Any] = None,
        user_identity: Optional[str] = None,
    ) -> OCRResult:
        """Process document by sending image directly to vision AI.

        No OCR, no text extraction — vision model sees the document image
        and returns classification + extracted fields in one call.
        """
        start_time = datetime.now()

        try:
            # Convert PDF/image to PNG for vision model
            img_b64 = self._to_base64_image(image_bytes, mime_type)

            # Build user context string
            context = ""
            if user_identity:
                context = f"\n\nBENUTZER-KONTEXT:\n{user_identity}"

            # Call vision model
            result = self._call_vision_model(img_b64, context)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            if not result:
                return self._empty_result(processing_time)

            # Map AI document_type to DocumentType enum
            doc_type = self._map_document_type(result.get("document_type", "other"))
            confidence = float(result.get("confidence", 0.8))

            # Build extracted_data from vision result
            extracted_data = {}
            for key in ["amount", "amount_brutto", "amount_netto", "vat_amount",
                        "vat_rate", "date", "description", "issuer", "recipient",
                        "property_address", "asset_type", "svs_quarter",
                        "quarterly_amount", "insurance_subtype", "lender_name",
                        "annual_interest"]:
                if result.get(key) is not None:
                    extracted_data[key] = result[key]

            # Store full AI result for downstream pipeline
            extracted_data["_ai_first"] = {
                "document_type": result.get("document_type", "other"),
                "confidence": confidence,
                "creates": result.get("creates", ["transaction"]),
                "document_subtype": result.get("insurance_subtype") or result.get("asset_type"),
                "role_detection": {
                    "landlord_name": None,
                    "tenant_name": None,
                    "user_is": None,
                },
                "amounts": {
                    "total_amount": result.get("amount_brutto") or result.get("amount"),
                    "annual_amount": result.get("amount_netto") or result.get("annual_interest"),
                    "monthly_amount": None,
                    "settlement_amount": None,
                    "new_amount": None,
                },
                "key_fields": {
                    k: result.get(k) for k in [
                        "date", "issuer", "recipient", "property_address",
                        "asset_type", "svs_quarter", "quarterly_amount",
                        "insurance_subtype", "lender_name", "description",
                    ] if result.get(k) is not None
                },
                "tax_treatment": {
                    "is_deductible": result.get("is_deductible"),
                    "deduction_category": result.get("deduction_category"),
                    "tax_form": result.get("tax_form"),
                    "expense_or_income": result.get("expense_or_income"),
                },
            }

            # Use raw_text from vision model's transcription
            raw_text = result.get("raw_text", "")

            return OCRResult(
                document_type=doc_type,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=confidence,
                needs_review=confidence < 0.7,
                processing_time_ms=processing_time,
                suggestions=[],
                provider_used="llama-4-scout-vision",
                classification_source="vision_ai",
            )

        except Exception as e:
            logger.error("Vision processing failed: %s", e)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return self._empty_result(processing_time)

    def _to_base64_image(self, file_bytes: bytes, mime_type: str = None) -> str:
        """Convert PDF or image to base64 PNG for vision model."""
        is_pdf = file_bytes[:5] == b"%PDF-"

        if is_pdf:
            # PDF → render first page as PNG
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            doc.close()
        else:
            # Already an image
            img_bytes = file_bytes

        return base64.b64encode(img_bytes).decode()

    def _call_vision_model(self, img_b64: str, context: str = "") -> Optional[Dict]:
        """Call llama-4-scout vision model via Groq."""
        from dotenv import load_dotenv
        load_dotenv()

        groq_keys = [k for k in [
            os.getenv("GROQ_API_KEY"),
            os.getenv("GROQ_API_KEY_2"),
        ] if k]

        prompt = VISION_PROMPT + context

        for key in groq_keys:
            try:
                from groq import Groq
                client = Groq(api_key=key, timeout=90.0)
                resp = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{VISION_SYSTEM}\n\n{prompt}"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ]
                    }],
                    max_tokens=2048,
                    temperature=0,
                )
                content = resp.choices[0].message.content
                if content:
                    return self._parse_json(content)
            except Exception as e:
                logger.warning("Vision call failed: %s", e)
                continue

        return None

    def _parse_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from model response."""
        if not text:
            return None
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _map_document_type(self, ai_type: str) -> DocumentType:
        """Map AI document type string to DocumentType enum."""
        mapping = {
            "invoice": DocumentType.INVOICE,
            "asset_purchase": DocumentType.INVOICE,
            "receipt": DocumentType.RECEIPT,
            "svs_vorschreibung": DocumentType.SVS_NOTICE,
            "svs_nachbemessung": DocumentType.SVS_NOTICE,
            "versicherungspolizze": DocumentType.VERSICHERUNGSBESTAETIGUNG,
            "grundsteuerbescheid": DocumentType.INVOICE,
            "lohnzettel": DocumentType.LOHNZETTEL,
            "einkommensteuerbescheid": DocumentType.EINKOMMENSTEUERBESCHEID,
            "mietvertrag": DocumentType.RENTAL_CONTRACT,
            "mietvorschreibung": DocumentType.INVOICE,
            "betriebskostenabrechnung": DocumentType.INVOICE,
            "loan_contract": DocumentType.LOAN_CONTRACT,
            "zinsbescheinigung": DocumentType.LOAN_CONTRACT,
            "kaufvertrag": DocumentType.INVOICE,  # NOT PURCHASE_CONTRACT — let AI handle via creates
            "spendenbestaetigung": DocumentType.SPENDENBESTAETIGUNG,
            "kirchenbeitrag": DocumentType.KIRCHENBEITRAG,
            "bank_statement": DocumentType.BANK_STATEMENT,
            "fahrtenbuch": DocumentType.OTHER,
            "homeoffice_nachweis": DocumentType.OTHER,
            "e1_form": DocumentType.E1_FORM,
        }
        return mapping.get(ai_type, DocumentType.OTHER)

    def _empty_result(self, processing_time: float) -> OCRResult:
        return OCRResult(
            document_type=DocumentType.OTHER,
            extracted_data={},
            raw_text="",
            confidence_score=0.0,
            needs_review=True,
            processing_time_ms=processing_time,
            suggestions=[],
            provider_used="llama-4-scout-vision",
            classification_source="vision_ai_failed",
        )

    # Batch processing
    def process_batch(self, documents: List[bytes], **kwargs) -> BatchOCRResult:
        start = datetime.now()
        results = []
        ok = 0; fail = 0
        for doc_bytes in documents:
            r = self.process_document(doc_bytes, **kwargs)
            results.append(r)
            if r.confidence_score > 0:
                ok += 1
            else:
                fail += 1
        return BatchOCRResult(
            results=results,
            total_processing_time_ms=(datetime.now() - start).total_seconds() * 1000,
            successful=ok,
            failed=fail,
        )
