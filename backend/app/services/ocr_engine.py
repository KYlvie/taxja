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
from difflib import SequenceMatcher
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


# Step 1 prompt — PERCEPTION ONLY: classify + extract numbers + transcribe
# No business judgment (direction, creates, is_asset) — that's Step 2 + Step 3
STEP1_VISION_PROMPT = """\
Analysiere dieses Dokument-Bild. Antworte NUR als JSON.

AUFGABE: Nur LESEN und ABTIPPEN. Keine steuerliche Bewertung!

WICHTIG: Pruefe ob das Bild MEHRERE separate Dokumente/Kassenbons enthaelt.

{
  "receipt_count": Anzahl separater Rechnungen/Kassenbons im Bild (1 wenn nur ein Dokument),
  "document_type": "invoice|asset_purchase|svs_vorschreibung|versicherungspolizze|grundsteuerbescheid|lohnzettel|einkommensteuerbescheid|mietvertrag|mietvorschreibung|betriebskostenabrechnung|loan_contract|zinsbescheinigung|spendenbestaetigung|kirchenbeitrag|bank_statement|fahrtenbuch|receipt|other",
  "confidence": 0.0-1.0,
  "gross_amount": Rechnungsbetrag brutto (der grosse Endbetrag) als Zahl oder null,
  "vat_amount": USt-Betrag als Zahl oder null,
  "date": "YYYY-MM-DD oder null",
  "issuer": "Aussteller/Absender (wer hat das Dokument erstellt)",
  "recipient": "Empfaenger/Kunde (an wen ist es gerichtet)",
  "raw_text": "Vollstaendiger Text des Dokuments (ALLES abtippen was lesbar ist, JEDE Zeile, NICHTS auslassen oder abkuerzen)"
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

            receipt_count = int(step1.get("receipt_count", 1) or 1)
            raw_text = step1.get("raw_text", "")
            doc_type_str = step1.get("document_type", "other")

            # ── Multi-receipt: use OpenAI gpt-4o for structured extraction ──
            if receipt_count > 1:
                logger.info("Step 1 detected %d receipts — calling OpenAI gpt-4o", receipt_count)
                multi_result = self._vision_multi_receipt(img_b64, receipt_count, user_identity=user_identity)
                if multi_result:
                    return multi_result

            # Step 1 = perception only: gross_amount, vat_amount, issuer, recipient
            # NO creates, NO direction — those come from Step 2 + Step 3

            # Step 2: Detailed extraction + business judgment via gpt-oss-120b
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

            # Merge Step 1 (perception) + Step 2 (judgment) into _ai_first
            # Amounts: prefer Step 2 gross_amount, fallback to Step 1 gross_amount
            amounts = {
                "total_amount": step2.get("gross_amount") or step2.get("amount_brutto")
                               or step2.get("gesamtbetrag") or step2.get("amount")
                               or step1.get("gross_amount") or step1.get("amount")
                               or step2.get("brutto_jahresgehalt") or step2.get("settlement_amount"),
                "annual_amount": step2.get("praemie_jaehrlich")
                                or step2.get("annual_tax") or step2.get("annual_interest_paid")
                                or step2.get("annual_amount"),
                "monthly_amount": step2.get("gesamtmiete") or step2.get("monthly_amount"),
                "settlement_amount": step2.get("settlement_amount"),
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

            # Direction: Step 2 judgment only (Step 1 no longer provides this)
            tax_treatment = {
                "is_deductible": step2.get("is_deductible"),
                "deduction_category": step2.get("deduction_category"),
                "tax_form": step2.get("tax_form"),
                "expense_or_income": step2.get("expense_or_income"),
            }

            ai_first = {
                "document_type": doc_type_str,
                "confidence": float(step1.get("confidence", 0.8)),
                # creates: NO LONGER from Step 1. Pipeline Step 3 rules engine decides.
                "creates": [],
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
            # Promote top-level fields for backward compat + pipeline access
            for k in ["date", "description", "issuer", "recipient",
                       "vat_amount", "vat_rate"]:
                val = step2.get(k) or step1.get(k)
                if val is not None:
                    extracted_data[k] = val
            # gross_amount from Step 1 perception (most reliable)
            ga = step1.get("gross_amount") or step2.get("gross_amount") or step1.get("amount")
            if ga is not None:
                extracted_data["amount"] = ga
                extracted_data["gross_amount"] = ga
            va = step1.get("vat_amount") or step2.get("vat_amount")
            if va is not None:
                extracted_data["vat_amount"] = va

            # ── Line items from Step 2 AI (preferred over regex) ──
            ai_line_items = self._normalize_line_items(step2.get("line_items"))
            expected_line_item_names = [li["name"] for li in ai_line_items]
            if ai_line_items:
                if self._has_meaningful_line_item_prices(ai_line_items):
                    extracted_data["line_items"] = ai_line_items
                    logger.info("Step 2 AI returned %d usable line items", len(ai_line_items))
                else:
                    logger.info(
                        "Step 2 AI returned %d line items but no meaningful prices; trying fallback recovery",
                        len(ai_line_items),
                    )

            # ── Fallback: Multi-receipt detection + regex line item extraction ──
            doc_type = self._map_document_type(doc_type_str)
            if (
                not self._has_meaningful_line_item_prices(extracted_data.get("line_items"))
                and raw_text
                and doc_type in (DocumentType.RECEIPT, DocumentType.INVOICE)
            ):
                try:
                    from app.services.field_extractor import FieldExtractor
                    fe = FieldExtractor()

                    # Multi-receipt splitting
                    multi_results = fe.extract_multi_receipt_fields(raw_text, doc_type)
                    if len(multi_results) > 1:
                        logger.info("Detected %d receipts in document", len(multi_results))
                        primary = multi_results[0]
                        extracted_data["_receipt_count"] = len(multi_results)
                        extracted_data["_additional_receipts"] = multi_results[1:]
                        # Use primary receipt amount if AI didn't find one
                        if not extracted_data.get("amount") and primary.get("amount"):
                            extracted_data["amount"] = float(primary["amount"])
                            extracted_data["gross_amount"] = float(primary["amount"])
                        # Promote primary merchant/issuer if missing
                        if not extracted_data.get("issuer") and primary.get("merchant"):
                            extracted_data["issuer"] = primary["merchant"]

                    # Line item extraction (always, even for single receipts)
                    line_items = fe.extract_line_items(raw_text)
                    if line_items:
                        # Convert Decimal to float for JSON serialization
                        regex_line_items = [
                            {"name": li["name"], "price": float(li["price"])}
                            for li in line_items
                            if li.get("name") and not self._is_receipt_summary_line(str(li["name"]))
                        ]
                        if self._has_meaningful_line_item_prices(regex_line_items):
                            extracted_data["line_items"] = regex_line_items
                            logger.info("Extracted %d line items from raw_text", len(line_items))
                        # If amount is still missing, sum line items
                        if not extracted_data.get("amount") and self._has_meaningful_line_item_prices(regex_line_items):
                            total = sum(float(li["price"]) for li in line_items)
                            if total > 0:
                                extracted_data["amount"] = total
                                extracted_data["gross_amount"] = total

                    # VAT extraction
                    vat_amounts = fe.extract_vat_amounts(raw_text)
                    if vat_amounts:
                        extracted_data["vat_breakdown"] = {
                            rate: float(amt) for rate, amt in vat_amounts.items()
                        }
                        if not extracted_data.get("vat_amount"):
                            extracted_data["vat_amount"] = sum(
                                float(v) for v in vat_amounts.values()
                            )
                except Exception as e:
                    logger.warning("Multi-receipt/line-item extraction failed: %s", e)

            if (
                doc_type in (DocumentType.RECEIPT, DocumentType.INVOICE)
                and not self._has_meaningful_line_item_prices(extracted_data.get("line_items"))
            ):
                recovered_line_items = self._extract_receipt_line_items_from_image(
                    image_bytes,
                    expected_names=expected_line_item_names,
                )
                if recovered_line_items:
                    extracted_data["line_items"] = recovered_line_items
                    logger.info(
                        "Recovered %d receipt line items from image OCR fallback",
                        len(recovered_line_items),
                    )

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

    # ── Multi-receipt: OpenAI gpt-4o structured extraction ──────────

    def _vision_multi_receipt(self, img_b64: str, receipt_count: int,
                               user_identity: Optional[str] = None) -> Optional[OCRResult]:
        """Use OpenAI gpt-4o for multi-receipt: returns structured data per receipt."""
        from dotenv import load_dotenv
        load_dotenv()

        user_context = ""
        if user_identity:
            user_context = f"\nBENUTZER-KONTEXT:\n{user_identity}\n"

        prompt = (
            f"Dieses Bild enthält mehrere Kassenbons. Analysiere JEDEN einzeln.\n"
            f"{user_context}\n"
            "Antworte als JSON: {\"receipts\": [{\"issuer\": \"Name\", \"date\": \"YYYY-MM-DD\", "
            "\"gross_amount\": 10.0, \"expense_or_income\": \"expense\", "
            "\"is_deductible\": false, \"deduction_category\": \"nicht_absetzbar\", "
            "\"items\": [{\"name\": \"Artikel\", \"price\": 1.0, \"is_deductible\": false}]}]}\n\n"
            "REGELN:\n"
            "- JEDER Kassenbon = eigener Eintrag\n"
            "- JEDEN Artikel mit Name und Preis\n"
            "- gross_amount = Summe/Endbetrag\n"
            "- is_deductible anhand BENUTZER-KONTEXT bewerten\n"
            "- Lebensmittel = nicht absetzbar fuer IT/Buero\n"
            "- NICHT wiederholen, NICHTS auslassen"
        )

        parsed = None

        # Primary: OpenAI gpt-4o (stable for multi-receipt)
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import openai
                client = openai.OpenAI(api_key=openai_key)
                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ]
                    }],
                    max_tokens=8192,
                    temperature=0,
                )
                content = resp.choices[0].message.content
                if content:
                    parsed = self._parse_json(content)
                    if parsed and parsed.get("receipts"):
                        logger.info("Multi-receipt OpenAI gpt-4o: %d receipts", len(parsed["receipts"]))
            except Exception as e:
                logger.warning("Multi-receipt OpenAI failed: %s", e)

        # Fallback: Groq
        if not parsed or not parsed.get("receipts"):
            groq_keys = [k for k in [os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY_2")] if k]
            for key in groq_keys:
                try:
                    from groq import Groq
                    client = Groq(api_key=key, timeout=120.0)
                    resp = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                            ]
                        }],
                        max_tokens=8192,
                        temperature=0,
                    )
                    content = resp.choices[0].message.content
                    if content:
                        parsed = self._parse_json(content)
                        if parsed and parsed.get("receipts"):
                            break
                except Exception as e:
                    logger.warning("Multi-receipt Groq fallback failed: %s", e)
                    continue

        if not parsed or not parsed.get("receipts"):
            return None

        receipts = parsed["receipts"]
        logger.info("Multi-receipt: %d receipts extracted", len(receipts))

        # Build OCRResult
        primary = receipts[0]
        additional = []
        for r in receipts[1:]:
            additional.append({
                "amount": r.get("gross_amount"),
                "merchant": r.get("issuer"),
                "date": r.get("date"),
                "expense_or_income": r.get("expense_or_income", "expense"),
                "is_deductible": r.get("is_deductible"),
                "deduction_category": r.get("deduction_category"),
                "line_items": [
                    {"name": li.get("name", ""), "price": float(li["price"]) if li.get("price") is not None else 0.0,
                     "is_deductible": li.get("is_deductible")}
                    for li in r.get("items", [])
                ],
            })

        doc_type = self._map_document_type("receipt")
        ai_first = {
            "document_type": "receipt",
            "confidence": 0.95,
            "creates": [],
            "amounts": {"total_amount": primary.get("gross_amount")},
            "key_fields": {"date": primary.get("date"), "issuer": primary.get("issuer")},
            "tax_treatment": {
                "expense_or_income": primary.get("expense_or_income", "expense"),
                "is_deductible": primary.get("is_deductible"),
                "deduction_category": primary.get("deduction_category"),
            },
        }

        extracted_data = {
            "_ai_first": ai_first,
            "amount": primary.get("gross_amount"),
            "gross_amount": primary.get("gross_amount"),
            "date": primary.get("date"),
            "issuer": primary.get("issuer"),
            "merchant": primary.get("issuer"),
            "_receipt_count": len(receipts),
            "_additional_receipts": additional,
            "line_items": [
                {"name": li.get("name", ""), "price": float(li["price"]) if li.get("price") is not None else 0.0,
                 "is_deductible": li.get("is_deductible")}
                for li in primary.get("items", [])
            ],
        }

        pt = (datetime.now() - datetime.now()).total_seconds() * 1000
        return OCRResult(
            document_type=doc_type,
            extracted_data=extracted_data,
            raw_text="",
            confidence_score=0.95,
            needs_review=False,
            processing_time_ms=0,
            suggestions=[],
            provider_used="gpt-4o+multi-receipt",
            classification_source="vision_ai_multi_receipt",
        )

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
        # Strip markdown code fences
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            json_str = m.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Fix raw newlines inside JSON string values
                json_str2 = json_str.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                try:
                    return json.loads(json_str2)
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def _parse_float_amount(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return None

        cleaned = value.strip().replace("EUR", "").replace("eur", "").replace("€", "")
        cleaned = cleaned.replace(" ", "")
        if not cleaned:
            return None

        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")

        cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
        if not cleaned or cleaned == "-":
            return None

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _normalize_line_items(self, items: Any) -> List[Dict[str, Any]]:
        if not isinstance(items, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or item.get("description") or "").strip()
            if not name:
                continue

            price = self._parse_float_amount(item.get("price"))
            if price is None:
                price = self._parse_float_amount(item.get("total_price"))
            if price is None:
                price = 0.0

            normalized_item: Dict[str, Any] = {"name": name, "price": price}
            if item.get("is_deductible") is not None:
                normalized_item["is_deductible"] = item.get("is_deductible")
            normalized.append(normalized_item)

        return normalized

    @staticmethod
    def _has_meaningful_line_item_prices(line_items: Any) -> bool:
        if not isinstance(line_items, list):
            return False

        for item in line_items:
            if not isinstance(item, dict):
                continue
            try:
                price = float(item.get("price") or 0.0)
            except (TypeError, ValueError):
                continue
            if abs(price) >= 0.009:
                return True
        return False

    @staticmethod
    def _normalize_receipt_text(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    @classmethod
    def _normalize_ocr_amount_token(cls, token: str) -> str:
        cleaned = token.strip().replace(" ", "")
        if not cleaned:
            return ""

        cleaned = "".join(
            {
                "O": "0", "o": "0", "Q": "0", "D": "0",
                "I": "1", "l": "1", "|": "1",
                "S": "5", "s": "5",
                "B": "8", "&": "8",
            }.get(char, char)
            for char in cleaned
        )

        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")

        cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
        if cleaned.count(".") > 1:
            head, tail = cleaned.rsplit(".", 1)
            cleaned = head.replace(".", "") + "." + tail
        return cleaned

    @classmethod
    def _extract_amount_from_ocr_line(cls, line: str) -> Optional[float]:
        stripped = line.strip()
        match = re.search(
            r"(-?[0-9OoQDIlSsB&]+(?:\s*[.,]\s*[0-9OoQDIlSsB&]{2}))\s*$",
            stripped,
        )
        if not match:
            match = re.search(r"(-?[0-9OoQDIlSsB&][0-9OoQDIlSsB&.,]*)\s*$", stripped)
        if not match:
            return None

        normalized = cls._normalize_ocr_amount_token(match.group(1))
        if not re.fullmatch(r"-?\d+(?:\.\d{2})?", normalized):
            return None

        try:
            return float(normalized)
        except ValueError:
            return None

    @classmethod
    def _cleanup_receipt_line_name(cls, line: str) -> str:
        cleaned = re.sub(
            r"(-?[0-9OoQDIlSsB&]+(?:\s*[.,]\s*[0-9OoQDIlSsB&]{2}))\s*$",
            "",
            line,
        )
        cleaned = re.sub(r"(-?[0-9OoQDIlSsB&][0-9OoQDIlSsB&.,]*)\s*$", "", cleaned)
        cleaned = cleaned.strip(" -:\t")
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def _is_receipt_summary_line(name: str) -> bool:
        lowered = name.lower()
        blocked = (
            "summe", "gesamt", "betrag", "total", "mwst", "ust", "tax",
            "kassen", "beleg", "filiale", "qr", "danke", "zahlung", "cash",
            "mastercard", "visa", "debit", "kredit", "change", "rabatt",
        )
        return any(word in lowered for word in blocked)

    def _score_receipt_name_match(self, candidate_name: str, expected_name: str) -> float:
        candidate_norm = self._normalize_receipt_text(candidate_name)
        expected_norm = self._normalize_receipt_text(expected_name)
        if not candidate_norm or not expected_norm:
            return 0.0
        if candidate_norm in expected_norm or expected_norm in candidate_norm:
            return 0.99
        return SequenceMatcher(None, candidate_norm, expected_norm).ratio()

    def _extract_line_items_from_receipt_ocr_text(
        self,
        ocr_text: str,
        expected_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not ocr_text:
            return []

        expected_names = [str(name).strip() for name in (expected_names or []) if str(name).strip()]
        candidates: List[Dict[str, Any]] = []

        for raw_line in ocr_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            amount = self._extract_amount_from_ocr_line(line)
            if amount is None:
                continue
            name = self._cleanup_receipt_line_name(line)
            if not name or self._is_receipt_summary_line(name):
                continue
            candidates.append({"name": name, "price": amount})

        if not candidates:
            return []

        if not expected_names:
            return candidates

        matched: List[Dict[str, Any]] = []
        used_candidate_indexes = set()
        for expected_name in expected_names:
            best_index = None
            best_score = 0.0
            for index, candidate in enumerate(candidates):
                if index in used_candidate_indexes:
                    continue
                score = self._score_receipt_name_match(candidate["name"], expected_name)
                if score > best_score:
                    best_score = score
                    best_index = index
            if best_index is not None and best_score >= 0.45:
                used_candidate_indexes.add(best_index)
                matched.append({"name": expected_name, "price": candidates[best_index]["price"]})

        return matched if matched else candidates

    def _decode_image_for_receipt_fallback(self, file_bytes: bytes):
        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.warning("Receipt OCR fallback unavailable: cv2/numpy not installed")
            return None

        is_pdf = file_bytes[:5] == b"%PDF-"
        if is_pdf:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=250)
            img_bytes = pix.tobytes("png")
            doc.close()
        else:
            img_bytes = file_bytes

        nparr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def _extract_receipt_line_items_from_image(
        self,
        file_bytes: bytes,
        expected_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        image = self._decode_image_for_receipt_fallback(file_bytes)
        if image is None:
            return []

        try:
            import cv2
            import pytesseract
            from app.core.ocr_config import OCRConfig
        except ImportError:
            logger.warning("Receipt OCR fallback unavailable: pytesseract/cv2 missing")
            return []

        pytesseract.pytesseract.tesseract_cmd = OCRConfig.get_tesseract_cmd()

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enlarged = cv2.resize(gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        thresholded = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        variants = [
            (thresholded, "--oem 3 --psm 4 -l deu+eng"),
            (thresholded, "--oem 3 --psm 6 -l deu+eng"),
            (enlarged, "--oem 3 --psm 4 -l deu+eng"),
        ]

        best: List[Dict[str, Any]] = []
        for variant_image, config in variants:
            try:
                ocr_text = pytesseract.image_to_string(variant_image, config=config)
            except Exception as exc:
                logger.warning("Receipt OCR fallback failed with config %s: %s", config, exc)
                continue

            recovered = self._extract_line_items_from_receipt_ocr_text(
                ocr_text,
                expected_names=expected_names,
            )
            if len(recovered) > len(best):
                best = recovered
            if self._has_meaningful_line_item_prices(recovered) and (
                not expected_names or len(recovered) >= len(expected_names)
            ):
                return recovered

        return best

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
