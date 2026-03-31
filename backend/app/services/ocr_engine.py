"""OCR Engine — Two-step AI document processing.

Step 1: llama-4-scout vision → document type + raw_text + basic fields
Step 2: gpt-oss-120b text → type-specific detailed extraction + tax judgment

Fallback chain: Groq → OpenAI → needs_review
"""
import base64
import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List

import fitz  # PyMuPDF for PDF→image

logger = logging.getLogger(__name__)

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
    results: List[OCRResult]
    total_processing_time_ms: float
    successful: int
    failed: int


# Step 1 prompt — lightweight, just classify + transcribe
STEP1_VISION_PROMPT = """\
Analysiere dieses Dokument-Bild. Antworte NUR als JSON:
{
  "document_type": "invoice|asset_purchase|svs_vorschreibung|versicherungspolizze|grundsteuerbescheid|lohnzettel|einkommensteuerbescheid|mietvertrag|mietvorschreibung|betriebskostenabrechnung|loan_contract|zinsbescheinigung|spendenbestaetigung|kirchenbeitrag|bank_statement|fahrtenbuch|receipt|other",
  "confidence": 0.0-1.0,
  "creates": ["transaction", "asset", "recurring", "loan", "property", "archive_only"],
  "amount": Hauptbetrag als Zahl oder null,
  "date": "YYYY-MM-DD oder null",
  "issuer": "Aussteller/Absender",
  "recipient": "Empfaenger",
  "raw_text": "Vollstaendiger Text des Dokuments (alles abtippen was lesbar ist)"
}"""


class OCREngine:
    """Two-step document processor: vision classification → text extraction."""

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
        """Process document: Step 1 (vision) → Step 2 (text extraction)."""
        start_time = datetime.now()

        try:
            # Step 1: Vision classification + raw_text
            img_b64 = self._to_base64_image(image_bytes, mime_type)
            step1 = self._step1_vision(img_b64)

            if not step1 or not step1.get("document_type"):
                # Vision failed entirely → needs_review
                pt = (datetime.now() - start_time).total_seconds() * 1000
                return self._empty_result(pt)

            raw_text = step1.get("raw_text", "")
            doc_type_str = step1.get("document_type", "other")
            creates = self._normalize_creates(step1.get("creates", []))

            # Fix direction: if issuer matches user name → income
            direction = step1.get("expense_or_income", "expense")
            issuer = (step1.get("issuer") or "").lower()
            if user_identity and direction != "income" and issuer:
                for line in (user_identity or "").split("\n"):
                    if line.startswith("Name:") or line.startswith("Firma:"):
                        name = line.split(":", 1)[-1].strip().lower()
                        if any(p in issuer for p in name.split() if len(p) > 2):
                            direction = "income"
                            break

            # Step 2: Detailed extraction via gpt-oss-120b
            step2 = {}
            if raw_text and len(raw_text.strip()) > 20:
                from app.services.ai_first_classifier import AIFirstClassifier
                classifier = AIFirstClassifier()

                # Build user context for Step 2
                user_ctx = None
                if user_identity:
                    user_ctx = {"name": "", "role_hints": []}
                    for line in user_identity.split("\n"):
                        if line.startswith("Name:"):
                            user_ctx["name"] = line.split(":", 1)[-1].strip()
                        elif line.startswith("UID:"):
                            user_ctx["vat_number"] = line.split(":", 1)[-1].strip()
                        elif line.startswith("Steuernummer:"):
                            user_ctx["tax_number"] = line.split(":", 1)[-1].strip()
                        elif line.startswith("Typ:") or line.startswith("USt:"):
                            user_ctx["role_hints"].append(line.split(":", 1)[-1].strip())

                step2 = classifier.extract_fields(
                    raw_text, doc_type_str,
                    user_context=user_ctx,
                )

            # Merge Step 1 + Step 2 into _ai_first
            amounts = {
                "total_amount": step2.get("amount_brutto") or step1.get("amount"),
                "annual_amount": step2.get("amount_netto") or step2.get("praemie_jaehrlich")
                                or step2.get("annual_interest_paid") or step2.get("annual_tax"),
                "monthly_amount": step2.get("gesamtmiete") or step2.get("monthly_amount"),
                "settlement_amount": step2.get("settlement_amount"),
                "new_amount": None,
            }

            key_fields = {}
            for k in ["date", "issuer", "recipient", "property_address", "asset_type",
                       "svs_quarter", "quarterly_amount", "insurance_subtype",
                       "lender_name", "description", "invoice_number", "employer_name",
                       "brutto_jahresgehalt", "lohnsteuer", "tax_year", "beitragsjahr",
                       "is_asset_purchase", "is_gwg", "useful_life_years",
                       "business_use_percentage", "deductible_percentage",
                       "purchase_date", "supplier"]:
                val = step2.get(k) or step1.get(k)
                if val is not None:
                    key_fields[k] = val

            tax_treatment = {
                "is_deductible": step2.get("is_deductible"),
                "deduction_category": step2.get("deduction_category"),
                "tax_form": step2.get("tax_form"),
                "expense_or_income": step2.get("expense_or_income") or direction,
            }

            ai_first = {
                "document_type": doc_type_str,
                "confidence": float(step1.get("confidence", 0.8)),
                "creates": creates,
                "document_subtype": step2.get("insurance_subtype") or step2.get("asset_type")
                                   or step2.get("settlement_type") or step2.get("loan_type"),
                "role_detection": {
                    "landlord_name": step2.get("landlord_name"),
                    "tenant_name": step2.get("tenant_name"),
                    "user_is": step2.get("user_is"),
                },
                "amounts": amounts,
                "key_fields": key_fields,
                "tax_treatment": tax_treatment,
            }

            extracted_data = {"_ai_first": ai_first}
            # Promote top-level fields for backward compat
            for k in ["amount", "date", "description", "issuer", "recipient",
                       "vat_amount", "vat_rate"]:
                val = step2.get(k) or step1.get(k)
                if val is not None:
                    extracted_data[k] = val

            doc_type = self._map_document_type(doc_type_str)
            confidence = float(step1.get("confidence", 0.8))
            pt = (datetime.now() - start_time).total_seconds() * 1000

            return OCRResult(
                document_type=doc_type,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=confidence,
                needs_review=confidence < 0.7,
                processing_time_ms=pt,
                suggestions=[],
                provider_used="llama-4-scout+gpt-oss-120b",
                classification_source="vision_ai_two_step",
            )

        except Exception as e:
            logger.error("Document processing failed: %s", e, exc_info=True)
            pt = (datetime.now() - start_time).total_seconds() * 1000
            return self._empty_result(pt)

    # ── Step 1: Vision ──────────────────────────────────────────────

    def _step1_vision(self, img_b64: str) -> Optional[Dict]:
        """Call llama-4-scout vision for classification + raw_text."""
        from dotenv import load_dotenv
        load_dotenv()

        groq_keys = [k for k in [os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY_2")] if k]

        for key in groq_keys:
            try:
                from groq import Groq
                client = Groq(api_key=key, timeout=90.0)
                resp = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": STEP1_VISION_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ]
                    }],
                    max_tokens=2048,
                    temperature=0,
                )
                content = resp.choices[0].message.content
                if content:
                    result = self._parse_json(content)
                    if result:
                        return result
            except Exception as e:
                logger.warning("Vision step1 failed with Groq: %s", e)
                continue

        # Fallback: OpenAI gpt-4o-mini with vision
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import openai
                client = openai.OpenAI(api_key=openai_key)
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": STEP1_VISION_PROMPT},
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
                logger.warning("Vision step1 OpenAI fallback failed: %s", e)

        return None

    # ── Helpers ──────────────────────────────────────────────────────

    def _to_base64_image(self, file_bytes: bytes, mime_type: str = None) -> str:
        is_pdf = file_bytes[:5] == b"%PDF-"
        if is_pdf:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            doc.close()
        else:
            img_bytes = file_bytes
        return base64.b64encode(img_bytes).decode()

    def _parse_json(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _normalize_creates(creates):
        if not creates:
            return ["transaction"]
        if isinstance(creates, str):
            creates = [creates]
        normalized = []
        for c in creates:
            if c in ("expense", "income"):
                if "transaction" not in normalized:
                    normalized.append("transaction")
            else:
                normalized.append(c)
        return normalized or ["transaction"]

    def _map_document_type(self, ai_type: str) -> DocumentType:
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
            "kaufvertrag": DocumentType.INVOICE,
            "spendenbestaetigung": DocumentType.SPENDENBESTAETIGUNG,
            "kirchenbeitrag": DocumentType.KIRCHENBEITRAG,
            "bank_statement": DocumentType.BANK_STATEMENT,
            "fahrtenbuch": DocumentType.UNKNOWN,
            "homeoffice_nachweis": DocumentType.UNKNOWN,
            "e1_form": DocumentType.E1_FORM,
        }
        return mapping.get(ai_type, DocumentType.UNKNOWN)

    def _empty_result(self, processing_time: float) -> OCRResult:
        return OCRResult(
            document_type=DocumentType.UNKNOWN,
            extracted_data={},
            raw_text="",
            confidence_score=0.0,
            needs_review=True,
            processing_time_ms=processing_time,
            suggestions=[],
            provider_used="failed",
            classification_source="needs_manual_review",
        )

    def process_batch(self, documents: List[bytes], **kwargs) -> BatchOCRResult:
        start = datetime.now()
        results = []
        ok = 0; fail = 0
        for doc_bytes in documents:
            r = self.process_document(doc_bytes, **kwargs)
            results.append(r)
            if r.confidence_score > 0: ok += 1
            else: fail += 1
        return BatchOCRResult(
            results=results,
            total_processing_time_ms=(datetime.now() - start).total_seconds() * 1000,
            successful=ok, failed=fail,
        )
