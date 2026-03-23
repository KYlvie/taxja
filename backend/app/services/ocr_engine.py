"""Main OCR processing engine"""
import logging
import re
import pytesseract
import cv2
import numpy as np
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

from app.core.ocr_config import OCRConfig
from app.services.image_preprocessor import ImagePreprocessor
from app.services.document_classifier import DocumentClassifier, DocumentType
from app.services.field_extractor import FieldExtractor
from app.services.merchant_database import MerchantDatabase
from app.services.llm_extractor import get_llm_extractor

logger = logging.getLogger(__name__)


def _parse_amount(value: Any) -> Optional[float]:
    """Parse OCR amount values from float/int/string into a normalized float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    cleaned = cleaned.replace("EUR", "").replace("€", "").replace(" ", "")

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")

    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if not cleaned or cleaned == "-":
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def _amounts_match(left: Any, right: Any, tolerance_ratio: float = 0.01) -> bool:
    """Compare amounts with a small relative tolerance for OCR noise."""
    left_value = _parse_amount(left)
    right_value = _parse_amount(right)

    if left_value is None or right_value is None:
        return False
    if left_value == 0 and right_value == 0:
        return True

    denominator = max(abs(left_value), abs(right_value), 1.0)
    return abs(left_value - right_value) / denominator <= tolerance_ratio


def _normalize_merchant(value: str) -> str:
    cleaned = re.sub(r"\bFILIALE\b\s*\d*", "", value.upper())
    cleaned = re.sub(r"[^A-Z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _merchants_match(left: Any, right: Any) -> bool:
    """Fuzzy-ish merchant comparison for OCR cross-validation."""
    if not left or not right:
        return False

    left_normalized = _normalize_merchant(str(left))
    right_normalized = _normalize_merchant(str(right))

    if not left_normalized or not right_normalized:
        return False

    return (
        left_normalized == right_normalized
        or left_normalized in right_normalized
        or right_normalized in left_normalized
    )


@dataclass
class OCRResult:
    """Result of OCR processing"""

    document_type: DocumentType
    extracted_data: Dict[str, Any]
    raw_text: str
    confidence_score: float
    needs_review: bool
    processing_time_ms: float
    suggestions: List[str]
    provider_used: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result["document_type"] = self.document_type.value
        return result


@dataclass
class BatchOCRResult:
    """Result of batch OCR processing"""

    results: List[OCRResult]
    grouped_results: Dict[str, List[OCRResult]]
    suggestions: List[str]
    total_processing_time_ms: float
    success_count: int
    failure_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "results": [r.to_dict() for r in self.results],
            "grouped_results": {
                k: [r.to_dict() for r in v] for k, v in self.grouped_results.items()
            },
            "suggestions": self.suggestions,
            "total_processing_time_ms": self.total_processing_time_ms,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }


class OCREngine:
    """Main OCR processing engine"""

    def __init__(self):
        self.config = OCRConfig()
        self.preprocessor = ImagePreprocessor()
        self.classifier = DocumentClassifier()
        self.extractor = FieldExtractor()
        self.merchant_db = MerchantDatabase()
        self.llm_extractor = get_llm_extractor()
        self._vision_provider_preference: Optional[str] = None

        # Set Tesseract command path
        pytesseract.pytesseract.tesseract_cmd = self.config.get_tesseract_cmd()

    def process_document(
        self,
        image_bytes: bytes,
        mime_type: str = None,
        vision_provider_preference: Optional[str] = None,
        reprocess_mode: Optional[str] = None,
        document_type_hint: Optional[Any] = None,
    ) -> OCRResult:
        """
        Process a single document image or PDF

        Args:
            image_bytes: Image/PDF file as bytes
            mime_type: Optional MIME type hint (e.g. image/jpeg, image/png)
            vision_provider_preference: Optional OCR vision provider override

        Returns:
            OCRResult with extracted data
        """
        start_time = datetime.now()
        previous_preference = self._vision_provider_preference
        self._vision_provider_preference = vision_provider_preference

        try:
            normalized_hint = self._normalize_document_type_hint(document_type_hint)

            if reprocess_mode == "claude_direct":
                return self._process_document_via_claude_direct(
                    image_bytes,
                    mime_type=mime_type,
                    start_time=start_time,
                    document_type_hint=normalized_hint,
                )

            # Check if PDF and try direct text extraction first (much faster)
            if image_bytes[:5] == b"%PDF-":
                pdf_text = self._extract_text_from_pdf(image_bytes)
                if pdf_text and len(pdf_text.strip()) > 20:
                    # PDF has a text layer — skip Tesseract entirely
                    return self._process_from_raw_text(
                        pdf_text.strip(),
                        image_bytes,
                        start_time,
                        document_type_hint=normalized_hint,
                    )

            # 1. Load and preprocess image (falls back to Tesseract OCR)
            # For multi-page scanned PDFs, use fast-path for contracts
            if image_bytes[:5] == b"%PDF-":
                # Quick OCR: first 2 pages only for classification (~8s vs ~23s)
                raw_text = self._ocr_all_pdf_pages(image_bytes, max_pages=2)

                # VLM fallback: if Tesseract returned nothing (not installed,
                # crashed, or image-only PDF it cannot read), render the first
                # page to PNG and try the VLM vision path instead.
                if not raw_text.strip():
                    logger.warning(
                        "Tesseract returned empty text for PDF, attempting VLM fallback"
                    )
                    vlm_result = self._try_vlm_ocr_for_pdf(
                        image_bytes, start_time
                    )
                    if vlm_result is not None:
                        return vlm_result

                # Classify from partial text
                doc_type, classification_confidence = self.classifier.classify(
                    None, raw_text
                )

                # Contracts: VLM reads images directly, skip full Tesseract OCR
                if doc_type in (
                    DocumentType.KAUFVERTRAG, DocumentType.MIETVERTRAG,
                    DocumentType.RENTAL_CONTRACT,
                ):
                    extraction_type = (
                        DocumentType.MIETVERTRAG
                        if doc_type == DocumentType.RENTAL_CONTRACT
                        else doc_type
                    )
                    return self._route_to_contract_extractor(
                        extraction_type, raw_text, image_bytes, start_time
                    )
                if doc_type == DocumentType.LOAN_CONTRACT:
                    return self._route_to_kreditvertrag_extractor(
                        raw_text, start_time
                    )

                # Non-contract: OCR all pages for full text extraction
                if raw_text.strip():
                    raw_text = self._ocr_all_pdf_pages(image_bytes, max_pages=5)
            else:
                # For images: try VLM (AI vision) first, then Tesseract as fallback
                vlm_result = self._try_vlm_ocr(
                    image_bytes, mime_type or "image/jpeg", start_time
                )
                if vlm_result is not None:
                    return vlm_result

                # VLM unavailable — fall back to Tesseract
                image = self._load_image(image_bytes)
                processed_image = self.preprocessor.preprocess(image)
                raw_text = self._extract_text(processed_image)

            return self._process_from_raw_text(
                raw_text,
                image_bytes,
                start_time,
                document_type_hint=normalized_hint,
            )

        except Exception as e:
            # Return error result
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return OCRResult(
                document_type=DocumentType.UNKNOWN,
                extracted_data={},
                raw_text="",
                confidence_score=0.0,
                needs_review=True,
                processing_time_ms=processing_time,
                suggestions=[f"OCR processing failed: {str(e)}"],
            )
        finally:
            self._vision_provider_preference = previous_preference

    def _normalize_document_type_hint(
        self,
        document_type_hint: Optional[Any],
    ) -> Optional[DocumentType]:
        if document_type_hint is None:
            return None

        if isinstance(document_type_hint, DocumentType):
            return document_type_hint

        raw_value = getattr(document_type_hint, "value", document_type_hint)
        raw_name = getattr(document_type_hint, "name", None)

        candidates = []
        if raw_value is not None:
            candidates.append(str(raw_value))
        if raw_name:
            candidates.append(str(raw_name))

        for candidate in candidates:
            try:
                return DocumentType(candidate)
            except Exception:
                pass
            try:
                return DocumentType[candidate]
            except Exception:
                pass

        fallback_map = {
            "purchase_contract": DocumentType.KAUFVERTRAG,
            "rental_contract": DocumentType.RENTAL_CONTRACT,
            "loan_contract": DocumentType.LOAN_CONTRACT,
            "receipt": DocumentType.RECEIPT,
            "invoice": DocumentType.INVOICE,
            "other": None,
        }
        for candidate in candidates:
            normalized = candidate.strip().lower()
            if normalized in fallback_map:
                return fallback_map[normalized]

        return None

    def _process_document_via_claude_direct(
        self,
        image_bytes: bytes,
        *,
        mime_type: Optional[str],
        start_time: datetime,
        document_type_hint: Optional[DocumentType],
    ) -> OCRResult:
        raw_text = self._extract_text_with_claude_direct(
            image_bytes,
            mime_type=mime_type,
            document_type_hint=document_type_hint,
        )

        if not raw_text.strip():
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return OCRResult(
                document_type=document_type_hint or DocumentType.UNKNOWN,
                extracted_data={},
                raw_text="",
                confidence_score=0.0,
                needs_review=True,
                processing_time_ms=processing_time,
                suggestions=["Claude direct reprocessing returned no readable text."],
                provider_used="anthropic",
            )

        return self._process_from_raw_text(
            raw_text,
            image_bytes,
            start_time,
            document_type_hint=document_type_hint,
            classification_confidence_hint=0.99 if document_type_hint else None,
            provider_used="anthropic",
        )

    def _process_from_raw_text(
        self,
        raw_text: str,
        image_bytes: bytes,
        start_time: datetime,
        *,
        document_type_hint: Optional[DocumentType] = None,
        classification_confidence_hint: Optional[float] = None,
        provider_used: Optional[str] = None,
    ) -> OCRResult:
        raw_text = raw_text.strip()
        if document_type_hint is not None:
            doc_type = document_type_hint
            classification_confidence = classification_confidence_hint or 0.99
        else:
            doc_type, classification_confidence = self.classifier.classify(None, raw_text)

        if doc_type in (DocumentType.KAUFVERTRAG, DocumentType.MIETVERTRAG, DocumentType.RENTAL_CONTRACT):
            extraction_type = DocumentType.MIETVERTRAG if doc_type == DocumentType.RENTAL_CONTRACT else doc_type
            result = self._route_to_contract_extractor(extraction_type, raw_text, image_bytes, start_time)
            if provider_used and not result.provider_used:
                result.provider_used = provider_used
            return result
        if doc_type == DocumentType.LOAN_CONTRACT:
            result = self._route_to_kreditvertrag_extractor(raw_text, start_time)
            if provider_used and not result.provider_used:
                result.provider_used = provider_used
            return result
        if doc_type == DocumentType.EINKOMMENSTEUERBESCHEID:
            result = self._route_to_bescheid_extractor(raw_text, start_time)
            if provider_used and not result.provider_used:
                result.provider_used = provider_used
            return result
        if doc_type == DocumentType.E1_FORM:
            result = self._route_to_e1_extractor(raw_text, start_time)
            if provider_used and not result.provider_used:
                result.provider_used = provider_used
            return result
        if doc_type in self.TAX_FORM_EXTRACTOR_TYPES:
            result = self._route_to_tax_form_extractor(doc_type, raw_text, start_time)
            if provider_used and not result.provider_used:
                result.provider_used = provider_used
            return result

        if image_bytes[:5] == b"%PDF-" and self._should_try_vlm_multi_receipt_pdf(raw_text, doc_type):
            vlm_multi_result = self._try_vlm_pdf_multi_receipt_ocr(
                image_bytes, doc_type, start_time
            )
            if vlm_multi_result is not None:
                if provider_used and not vlm_multi_result.provider_used:
                    vlm_multi_result.provider_used = provider_used
                return vlm_multi_result

        llm_result = self._try_llm_extraction(raw_text, doc_type, start_time)
        if llm_result is not None:
            if provider_used and not llm_result.provider_used:
                llm_result.provider_used = provider_used
            return llm_result

        multi_results = self.extractor.extract_multi_receipt_fields(raw_text, doc_type)
        if len(multi_results) > 1:
            extracted_data = self._build_multi_receipt_payload(multi_results)
            logger.info("Detected %d receipts in document", len(multi_results))
        else:
            extracted_data = self._normalize_receipt_payload(multi_results[0])

        overall_confidence = self._calculate_confidence(
            extracted_data, classification_confidence
        )

        if overall_confidence < 0.9 and self.llm_extractor.is_available:
            logger.info(
                "Regex confidence %.2f is low, retrying with LLM",
                overall_confidence,
            )
            llm_retry = self._try_llm_extraction(raw_text, doc_type, start_time)
            if llm_retry is not None:
                if provider_used and not llm_retry.provider_used:
                    llm_retry.provider_used = provider_used
                return llm_retry

        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        return OCRResult(
            document_type=doc_type,
            extracted_data=extracted_data,
            raw_text=raw_text,
            confidence_score=overall_confidence,
            needs_review=overall_confidence < self.config.CONFIDENCE_THRESHOLD,
            processing_time_ms=processing_time,
            suggestions=self._generate_suggestions(None, extracted_data, overall_confidence),
            provider_used=provider_used,
        )

    @staticmethod
    def _compare_extracted_fields(
        vlm_data: Dict[str, Any], tess_data: Dict[str, Any]
    ) -> tuple[int, list[str], int]:
        """Compare overlapping OCR fields for cross-validation."""
        comparable_fields = {"amount", "date", "merchant", "invoice_number"}
        overlap = comparable_fields.intersection(vlm_data.keys()).intersection(tess_data.keys())

        matches = 0
        mismatches: list[str] = []

        for field in overlap:
            if field == "amount":
                same = _amounts_match(vlm_data.get(field), tess_data.get(field))
            elif field == "merchant":
                same = _merchants_match(vlm_data.get(field), tess_data.get(field))
            else:
                same = (
                    str(vlm_data.get(field)).strip().lower()
                    == str(tess_data.get(field)).strip().lower()
                )

            if same:
                matches += 1
            else:
                mismatches.append(field)

        return matches, mismatches, len(overlap)

    def _tesseract_llm_extract(
        self, image_bytes: bytes, captured_at: datetime, doc_type: DocumentType
    ) -> Optional[OCRResult]:
        """Compatibility hook for OCR cross-validation fallback extraction."""
        _ = (image_bytes, captured_at, doc_type)
        return None

    def _cross_validate_image(
        self, vlm_result: OCRResult, image_bytes: bytes, captured_at: datetime
    ) -> OCRResult:
        """Cross-validate VLM OCR with a Tesseract+LLM fallback when confidence is moderate."""
        if vlm_result.confidence_score >= 0.85:
            return vlm_result

        tess_result = self._tesseract_llm_extract(
            image_bytes, captured_at, vlm_result.document_type
        )
        if tess_result is None:
            return vlm_result

        matches, mismatches, compared = self._compare_extracted_fields(
            vlm_result.extracted_data, tess_result.extracted_data
        )
        if compared == 0:
            return vlm_result

        merged_data = dict(vlm_result.extracted_data)
        for key, value in tess_result.extracted_data.items():
            if key not in merged_data and value is not None:
                merged_data[key] = value

        match_ratio = matches / compared
        critical_mismatch = any(field in {"amount", "date"} for field in mismatches)

        if match_ratio >= 0.5:
            boost = 0.15 if not critical_mismatch else 0.08
            confidence = min(1.0, vlm_result.confidence_score + boost)
            suggestions = [
                *vlm_result.suggestions,
                f"Cross-validated against fallback OCR ({matches}/{compared} key fields matched).",
            ]
            needs_review = False
        else:
            penalty = 0.20 if critical_mismatch else 0.10
            confidence = max(0.0, vlm_result.confidence_score - penalty)
            suggestions = [
                *vlm_result.suggestions,
                f"Fallback OCR disagree on {len(mismatches)} key field(s): {', '.join(mismatches)}.",
            ]
            needs_review = True

        return OCRResult(
            document_type=vlm_result.document_type,
            extracted_data=merged_data,
            raw_text=vlm_result.raw_text,
            confidence_score=confidence,
            needs_review=needs_review,
            processing_time_ms=vlm_result.processing_time_ms,
            suggestions=suggestions,
        )

    def process_batch(self, image_bytes_list: List[bytes]) -> BatchOCRResult:
        """
        Process multiple documents in batch

        Args:
            image_bytes_list: List of image files as bytes

        Returns:
            BatchOCRResult with all results
        """
        start_time = datetime.now()

        results = []
        success_count = 0
        failure_count = 0

        # Process each document
        for image_bytes in image_bytes_list:
            result = self.process_document(image_bytes)
            results.append(result)

            if result.confidence_score > 0:
                success_count += 1
            else:
                failure_count += 1

        # Group results by document type and date
        grouped_results = self._group_results(results)

        # Generate batch suggestions
        suggestions = self._generate_batch_suggestions(grouped_results)

        # Calculate total processing time
        total_time = (datetime.now() - start_time).total_seconds() * 1000

        return BatchOCRResult(
            results=results,
            grouped_results=grouped_results,
            suggestions=suggestions,
            total_processing_time_ms=total_time,
            success_count=success_count,
            failure_count=failure_count,
        )

    @staticmethod
    def _normalize_receipt_payload(receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize receipt payloads so downstream code sees stable keys."""
        cleaned = {k: v for k, v in receipt.items() if v is not None}
        cleaned.pop("raw_text", None)
        cleaned.pop("document_type", None)
        if "line_items" not in cleaned and isinstance(cleaned.get("items"), list):
            cleaned["line_items"] = cleaned["items"]
        OCREngine._ensure_vat_amounts(cleaned)
        return cleaned

    @staticmethod
    def _ensure_vat_amounts(data: Dict[str, Any]) -> None:
        """Ensure ``vat_amounts`` dict exists when VAT info is available.

        Converts ``vat_summary`` (VLM format) or single ``vat_rate``/``vat_amount``
        (LLM format) into the ``vat_amounts`` dict that the frontend expects.
        """
        if data.get("vat_amounts"):
            return

        vat_amounts: Dict[str, float] = {}

        # Path 1: VLM returns vat_summary [{rate, net_amount, vat_amount, ...}]
        vat_summary = data.get("vat_summary")
        if isinstance(vat_summary, list):
            for entry in vat_summary:
                if not isinstance(entry, dict):
                    continue
                rate = entry.get("rate")
                amount = entry.get("vat_amount")
                if rate is not None and amount is not None:
                    try:
                        rate_key = str(rate).rstrip("%") + "%"
                        vat_amounts[rate_key] = float(amount)
                    except (ValueError, TypeError):
                        continue

        # Path 2: LLM returns single vat_rate + vat_amount
        if not vat_amounts:
            vat_rate = data.get("vat_rate")
            vat_amount = data.get("vat_amount")
            if vat_rate is not None and vat_amount is not None:
                try:
                    rate_val = float(vat_rate)
                    # Normalize: 0.20 → "20%", 20 → "20%"
                    if rate_val < 1:
                        rate_val = rate_val * 100
                    rate_key = f"{rate_val:g}%"
                    vat_amounts[rate_key] = float(vat_amount)
                except (ValueError, TypeError):
                    pass

        if vat_amounts:
            data["vat_amounts"] = vat_amounts

    def _build_multi_receipt_payload(self, receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Pack multi-receipt OCR into a backward-compatible structure."""
        normalized = [
            self._normalize_receipt_payload(receipt)
            for receipt in receipts
            if isinstance(receipt, dict)
        ]
        if not normalized:
            return {}

        total_amount = 0.0
        for receipt in normalized:
            try:
                if receipt.get("amount") is not None:
                    total_amount += float(receipt["amount"])
            except (ValueError, TypeError):
                continue

        primary = dict(normalized[0])
        additional = normalized[1:]
        receipt_count = len(normalized)

        payload = {
            **primary,
            "_additional_receipts": additional,
            "_receipt_count": receipt_count,
            "multiple_receipts": normalized,
            "receipt_count": receipt_count,
            "total_amount": round(total_amount, 2),
        }

        if "line_items" not in payload and isinstance(primary.get("items"), list):
            payload["line_items"] = primary["items"]

        return payload

    def _should_try_vlm_multi_receipt_pdf(
        self,
        raw_text: str,
        doc_type: DocumentType,
    ) -> bool:
        """Decide whether a PDF should try multi-image VLM receipt extraction."""
        if doc_type not in (DocumentType.RECEIPT, DocumentType.INVOICE):
            return False

        page_markers = len(re.findall(r"--- PAGE \d+ ---", raw_text))
        header_hits = len(re.findall(
            r"(?:Rechnung|Invoice|Receipt|Beleg|Quittung|Kassenbon|Kassabon|BON\s*NR)\s*(?:\||:|\b|#|\d)",
            raw_text,
            re.IGNORECASE,
        ))
        total_hits = len(re.findall(
            r"^.*(?:SUMME|TOTAL|GESAMT|ZAHLBETRAG|RECHNUNGSBETRAG|ENDBETRAG|ZU ZAHLEN)[:\s]*[\d.,]+\s*(?:EUR|€)?",
            raw_text,
            re.IGNORECASE | re.MULTILINE,
        ))

        return page_markers >= 1 or header_hits >= 2 or total_hits >= 2

    def _try_vlm_ocr_for_pdf(
        self, pdf_bytes: bytes, start_time: datetime
    ) -> Optional[OCRResult]:
        """Render first PDF page to image and try VLM OCR as fallback when Tesseract fails."""
        try:
            import fitz

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if len(doc) == 0:
                doc.close()
                return None

            page = doc[0]
            mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI for good VLM quality
            pix = page.get_pixmap(matrix=mat)
            png_bytes = pix.tobytes("png")
            doc.close()

            return self._try_vlm_ocr(png_bytes, "image/png", start_time)
        except Exception as e:
            logger.warning("VLM PDF fallback failed: %s", e)
            return None

    def _try_vlm_pdf_multi_receipt_ocr(
        self,
        pdf_bytes: bytes,
        doc_type: DocumentType,
        start_time: datetime,
    ) -> Optional[OCRResult]:
        """Use multi-image vision OCR for PDF receipts/invoices that likely contain many receipts."""
        if doc_type not in (DocumentType.RECEIPT, DocumentType.INVOICE):
            return None

        from app.services.llm_service import get_llm_service
        import fitz

        llm = get_llm_service()
        if not llm.is_available:
            return None

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            num_pages = min(len(doc), 5)
            images: list[tuple[bytes, str]] = []

            for i in range(num_pages):
                page = doc[i]
                mat = fitz.Matrix(150 / 72, 150 / 72)
                pix = page.get_pixmap(matrix=mat)
                images.append((pix.tobytes("png"), "image/png"))
            doc.close()

            if not images:
                return None

            response = llm.generate_vision_multi(
                system_prompt=(
                    "OCR expert. You are reading pages from a PDF that may contain many separate "
                    "receipts, invoices, fuel slips, parking tickets, or payment slips on each page. "
                    "Extract EVERY distinct receipt visible across ALL pages. "
                    "Return a JSON array with one object per receipt. "
                    "Each object must contain: raw_text (first 120 chars), document_type "
                    "(receipt/invoice/unknown), date (YYYY-MM-DD if possible), amount (receipt total), "
                    "merchant, description, vat_amount, vat_rate, invoice_number, payment_method, tax_id, "
                    "line_items [{name,quantity,unit_price,total_price,vat_rate,vat_indicator}], "
                    "vat_summary [{rate,net_amount,vat_amount,indicator}]. "
                    "Do not stop after the most prominent receipt. JSON only."
                ),
                user_prompt=(
                    f"This PDF has {len(images)} page(s). "
                    "Some pages may contain multiple small receipts arranged side-by-side or overlapping. "
                    "Extract all receipts you can see across all pages and return them as a JSON array."
                ),
                images=images,
                temperature=0.0,
                max_tokens=4000,
                provider_preference=self._vision_provider_preference,
            )

            data = self._parse_vlm_json(response)
            if not isinstance(data, list):
                return None

            normalized = [
                self._normalize_receipt_payload(receipt)
                for receipt in data
                if isinstance(receipt, dict) and (
                    receipt.get("amount") is not None
                    or receipt.get("merchant")
                    or receipt.get("description")
                )
            ]
            if len(normalized) <= 1:
                return None

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(
                "PDF multi-receipt VLM extraction detected %d receipts across %d page(s)",
                len(normalized),
                len(images),
            )
            return OCRResult(
                document_type=doc_type,
                extracted_data=self._build_multi_receipt_payload(normalized),
                raw_text=response,
                confidence_score=0.86,
                needs_review=True,
                processing_time_ms=processing_time,
                suggestions=[
                    f"Detected {len(normalized)} receipts across {len(images)} PDF page(s)."
                ],
            )
        except Exception as e:
            logger.warning("PDF multi-receipt VLM extraction failed: %s", e)
            return None

    def _extract_text_with_claude_direct(
        self,
        image_bytes: bytes,
        *,
        mime_type: Optional[str],
        document_type_hint: Optional[DocumentType],
        max_pdf_pages: int = 8,
    ) -> str:
        """Use Claude vision as a strict OCR transcription pass for manual retry."""
        from app.services.llm_service import get_llm_service

        llm = get_llm_service()
        if not getattr(llm, "anthropic_client", None):
            raise RuntimeError("Anthropic Claude is not configured for direct retry")

        hint_text = ""
        if document_type_hint is not None:
            hint_text = (
                f"The expected document type is '{document_type_hint.value}'. "
                "Use that as a strong hint while transcribing labels and form fields."
            )

        system_prompt = (
            "You are a meticulous OCR transcription system for tax and business documents. "
            "Read every visible word, number, code, KZ field, table cell, tax ID, date, and amount. "
            "Do not summarize. Do not explain. Return plain text only."
        )

        if image_bytes[:5] == b"%PDF-":
            images = self._render_pdf_pages_for_vision(image_bytes, max_pages=max_pdf_pages)
            if not images:
                return ""
            return llm.generate_vision_multi_strict_provider(
                provider_name="anthropic",
                system_prompt=system_prompt,
                user_prompt=(
                    f"{hint_text} Transcribe the attached PDF exactly. "
                    "Prefix each page with '--- PAGE N ---'. "
                    "Preserve the reading order as much as possible. Plain text only."
                ).strip(),
                images=images,
                temperature=0.0,
                max_tokens=4000,
            ).strip()

        return llm.generate_vision_strict_provider(
            provider_name="anthropic",
            system_prompt=system_prompt,
            user_prompt=(
                f"{hint_text} Transcribe this document image exactly as plain text. "
                "Preserve labels, amounts, names, and form field values. Plain text only."
            ).strip(),
            image_bytes=image_bytes,
            mime_type=mime_type or "image/jpeg",
            temperature=0.0,
            max_tokens=3000,
        ).strip()

    def _try_vlm_ocr(
        self, image_bytes: bytes, mime_type: str, start_time: datetime
    ) -> Optional[OCRResult]:
        """
        Use a Vision-Language Model to OCR an image directly.
        Sends the image as base64 to the VL model and gets back structured data.
        Returns OCRResult or None if VLM unavailable/failed.

        Two-pass approach for multi-receipt images:
          Pass 1: Extract data normally.
          Pass 2: If pass 1 returned a single receipt, ask VLM how many separate
                  receipts are visible. If >1, re-extract each one individually.
        """
        from app.services.llm_service import get_llm_service
        import json

        llm = get_llm_service()
        if not llm.is_available:
            return None

        # Compact prompt to save tokens — VL models have limited context (4096).
        # The image itself consumes most of the budget.
        system_prompt = (
            "OCR expert. Extract data from this document image as JSON.\n"
            "IMPORTANT: First count how many SEPARATE receipts/invoices/tickets are "
            "visible in the image. They may be side-by-side, stacked, or overlapping.\n"
            "If MULTIPLE receipts are visible, you MUST return a JSON array with one "
            "object per receipt. If only one receipt, return a single JSON object.\n"
            "Fields (null if missing): raw_text (first 200 chars), document_type (invoice/receipt/"
            "mietvertrag/kaufvertrag/unknown), date (YYYY-MM-DD), amount (total), merchant, "
            "description (brief summary of purchased items), vat_amount, vat_rate, "
            "invoice_number, payment_method, tax_id, "
            "line_items [{name,quantity,unit_price,total_price,vat_rate,vat_indicator}], "
            "vat_summary [{rate,net_amount,vat_amount,indicator}], "
            "property_address, monthly_rent, purchase_price.\n"
            "CRITICAL: Read ALL line items from the receipt. For each item include at minimum "
            "the name and total_price. If the receipt has many items, still list them all.\n"
            "JSON only, no markdown."
        )

        try:
            logger.info("Attempting VLM OCR for image (%s, %d bytes)", mime_type, len(image_bytes))
            response = llm.generate_vision(
                system_prompt=system_prompt,
                user_prompt=(
                    "Look carefully at this image. Are there multiple separate receipts, "
                    "invoices, or tickets visible? If yes, extract EACH one as a separate "
                    "JSON object in an array. If only one, return a single JSON object."
                ),
                image_bytes=image_bytes,
                mime_type=mime_type,
                temperature=0.1,
                max_tokens=4000,
                provider_preference=self._vision_provider_preference,
            )

            # Parse JSON response
            data = self._parse_vlm_json(response)
            if not data:
                logger.warning("VLM OCR returned unparseable response")
                return None

            # Handle multi-receipt response (VLM returns array)
            if isinstance(data, list):
                if len(data) == 0:
                    logger.warning("VLM OCR returned empty array")
                    return None
                if len(data) == 1:
                    data = data[0]
                else:
                    # Multiple receipts in one image — build a combined result
                    logger.info("VLM detected %d receipts in single image", len(data))
                    processing_time = (datetime.now() - start_time).total_seconds() * 1000
                    return OCRResult(
                        document_type=DocumentType.RECEIPT,
                        extracted_data=self._build_multi_receipt_payload(data),
                        raw_text=response,
                        confidence_score=0.85,
                        needs_review=True,
                        processing_time_ms=processing_time,
                        suggestions=[
                            f"Detected {len(data)} receipts in one image. "
                            "Please upload each receipt separately for best results."
                        ],
                    )

            raw_text = data.pop("raw_text", response) or response
            doc_type_str = data.pop("document_type", "unknown") or "unknown"

            # Map to DocumentType
            type_map = {
                "invoice": DocumentType.INVOICE,
                "receipt": DocumentType.RECEIPT,
                "mietvertrag": DocumentType.MIETVERTRAG,
                "kaufvertrag": DocumentType.KAUFVERTRAG,
                "e1_form": DocumentType.E1_FORM,
                "einkommensteuerbescheid": DocumentType.EINKOMMENSTEUERBESCHEID,
                "bank_statement": DocumentType.UNKNOWN,
            }
            doc_type = type_map.get(doc_type_str.lower(), DocumentType.UNKNOWN)

            extracted_data = self._normalize_receipt_payload(data)

            # --- Pass 2: multi-receipt detection ---
            # VLMs often focus on the most prominent receipt and miss others.
            # If the first pass returned a single receipt/invoice, ask the VLM
            # specifically whether there are additional receipts in the image.
            if doc_type in (DocumentType.RECEIPT, DocumentType.INVOICE):
                multi_result = self._vlm_multi_receipt_check(
                    llm, image_bytes, mime_type, extracted_data, start_time
                )
                if multi_result is not None:
                    return multi_result

            field_count = len(extracted_data)
            confidence = min(0.95, 0.6 + field_count * 0.05)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                "VLM OCR succeeded: type=%s, %d fields, confidence %.2f",
                doc_type.value, field_count, confidence,
            )

            return OCRResult(
                document_type=doc_type,
                extracted_data=extracted_data,
                raw_text=str(raw_text),
                confidence_score=confidence,
                needs_review=confidence < self.config.CONFIDENCE_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=["AI vision model used for OCR."],
            )
        except Exception as e:
            logger.warning("VLM OCR failed: %s", e)
            return None

    def _vlm_multi_receipt_check(
        self, llm, image_bytes: bytes, mime_type: str,
        first_receipt: Dict[str, Any], start_time: datetime,
    ) -> Optional[OCRResult]:
        """
        Pass 2: Ask VLM if there are additional receipts beyond the one already extracted.

        Returns an OCRResult with multi-receipt payload if additional receipts found,
        or None if only one receipt is present.
        """
        first_merchant = first_receipt.get("merchant") or "unknown"
        try:
            count_prompt = (
                f"I already extracted one receipt from merchant '{first_merchant}'. "
                "Are there OTHER separate receipts, invoices, or tickets visible in this "
                "image? Answer with a JSON object: "
                '{"additional_count": <number>, "merchants": ["name1", "name2"]}. '
                "If there are no other receipts, return {\"additional_count\": 0}."
            )
            count_response = llm.generate_vision(
                system_prompt="You are an image analysis assistant. Answer precisely in JSON.",
                user_prompt=count_prompt,
                image_bytes=image_bytes,
                mime_type=mime_type,
                temperature=0.1,
                max_tokens=300,
                provider_preference=self._vision_provider_preference,
            )
            count_data = self._parse_vlm_json(count_response)
            additional_count = 0
            if isinstance(count_data, dict):
                additional_count = int(count_data.get("additional_count", 0))

            if additional_count <= 0:
                return None

            logger.info(
                "VLM pass-2 detected %d additional receipt(s) besides '%s'",
                additional_count, first_merchant,
            )

            # Extract each additional receipt individually
            additional_merchants = []
            if isinstance(count_data, dict) and isinstance(count_data.get("merchants"), list):
                additional_merchants = count_data["merchants"]

            all_receipts = [first_receipt]
            for i, merchant_hint in enumerate(additional_merchants):
                try:
                    extra = self._vlm_extract_single_receipt(
                        llm, image_bytes, mime_type, merchant_hint, first_merchant
                    )
                    if extra:
                        all_receipts.append(extra)
                except Exception as e:
                    logger.warning("Failed to extract additional receipt %d: %s", i + 1, e)

            # If we didn't get merchant hints or extraction failed, try a bulk re-extract
            if len(all_receipts) == 1 and additional_count > 0:
                bulk = self._vlm_extract_all_receipts(
                    llm, image_bytes, mime_type, additional_count + 1
                )
                if bulk and len(bulk) > 1:
                    all_receipts = bulk

            if len(all_receipts) <= 1:
                return None

            logger.info(
                "Multi-receipt extraction complete: %d receipts total", len(all_receipts)
            )
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return OCRResult(
                document_type=DocumentType.RECEIPT,
                extracted_data=self._build_multi_receipt_payload(all_receipts),
                raw_text="",
                confidence_score=0.80,
                needs_review=True,
                processing_time_ms=processing_time,
                suggestions=[
                    f"Detected {len(all_receipts)} receipts in one image. "
                    "Each receipt will create a separate transaction."
                ],
            )
        except Exception as e:
            logger.warning("Multi-receipt check failed: %s", e)
            return None

    def _vlm_extract_single_receipt(
        self, llm, image_bytes: bytes, mime_type: str,
        target_merchant: str, exclude_merchant: str,
    ) -> Optional[Dict[str, Any]]:
        """Extract a single specific receipt from a multi-receipt image."""
        prompt = (
            f"This image contains multiple receipts. Extract ONLY the receipt from "
            f"'{target_merchant}' (NOT from '{exclude_merchant}'). "
            "Return a single JSON object with fields: date, amount, merchant, description, "
            "vat_amount, vat_rate, payment_method, "
            "line_items [{name,quantity,unit_price,total_price}]. "
            "JSON only, no markdown."
        )
        response = llm.generate_vision(
            system_prompt="OCR expert. Extract data from the specified receipt only.",
            user_prompt=prompt,
            image_bytes=image_bytes,
            mime_type=mime_type,
            temperature=0.1,
            max_tokens=2000,
            provider_preference=self._vision_provider_preference,
        )
        data = self._parse_vlm_json(response)
        if isinstance(data, dict):
            return self._normalize_receipt_payload(data)
        if isinstance(data, list) and data:
            return self._normalize_receipt_payload(data[0])
        return None

    def _vlm_extract_all_receipts(
        self, llm, image_bytes: bytes, mime_type: str, expected_count: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """Bulk re-extract all receipts from a multi-receipt image."""
        prompt = (
            f"This image contains {expected_count} separate receipts/invoices. "
            "Extract ALL of them. Return a JSON array with one object per receipt. "
            "Each object: date, amount, merchant, description, vat_amount, vat_rate, "
            "payment_method, line_items [{name,quantity,unit_price,total_price}]. "
            "JSON only, no markdown."
        )
        response = llm.generate_vision(
            system_prompt="OCR expert. Extract ALL separate receipts from this image.",
            user_prompt=prompt,
            image_bytes=image_bytes,
            mime_type=mime_type,
            temperature=0.1,
            max_tokens=4000,
            provider_preference=self._vision_provider_preference,
        )
        data = self._parse_vlm_json(response)
        if isinstance(data, list) and len(data) > 1:
            return [self._normalize_receipt_payload(r) for r in data if isinstance(r, dict)]
        return None

    @staticmethod
    def _parse_vlm_json(response: str) -> Optional[Any]:
        """Parse JSON from VLM response, handling markdown code blocks and nested structures."""
        import re, json

        if not response:
            return None
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)

        # Try parsing the whole text first (handles nested arrays/objects)
        try:
            data = json.loads(text)
            if isinstance(data, (dict, list)):
                return data
        except Exception:
            pass

        # Try finding a JSON array first [ ... ]
        arr_start = text.find("[")
        obj_start = text.find("{")
        if arr_start != -1 and (obj_start == -1 or arr_start < obj_start):
            # Try to parse as array
            depth = 0
            in_string = False
            escape = False
            for i in range(arr_start, len(text)):
                c = text[i]
                if escape:
                    escape = False
                    continue
                if c == "\\":
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        try:
                            data = json.loads(text[arr_start : i + 1])
                            if isinstance(data, list):
                                return data
                        except Exception:
                            pass
                        break

        # Find the outermost { ... } using brace counting (supports deep nesting)
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start : i + 1])
                        if isinstance(data, dict):
                            return data
                    except Exception:
                        pass
                    break
        return None

    def _try_llm_extraction(
        self, raw_text: str, doc_type: DocumentType, start_time: datetime
    ) -> Optional[OCRResult]:
        """
        Try to extract fields using LLM. Returns OCRResult or None if LLM unavailable/failed.
        """
        if not self.llm_extractor.is_available:
            return None

        try:
            logger.info("Attempting LLM extraction for %s", doc_type.value)
            llm_data = self.llm_extractor.extract(
                raw_text,
                doc_type,
                provider_preference=self._vision_provider_preference,
            )
            if not llm_data:
                return None

            # Remove null values
            extracted_data = {k: v for k, v in llm_data.items() if v is not None}

            if not extracted_data:
                return None

            # Ensure vat_amounts is populated from vat_rate/vat_amount
            self._ensure_vat_amounts(extracted_data)

            # Estimate confidence based on how many fields were extracted
            field_count = len(extracted_data)
            confidence = min(0.95, 0.6 + field_count * 0.05)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                "LLM extraction succeeded: %d fields, confidence %.2f",
                field_count, confidence,
            )

            return OCRResult(
                document_type=doc_type,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=confidence,
                needs_review=confidence < self.config.CONFIDENCE_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=["AI-powered extraction used for this document."],
            )
        except Exception as e:
            logger.warning("LLM extraction failed, falling back to regex: %s", e)
            return None

    # VLM confidence threshold: below this, fall back to vision model
    _VLM_FALLBACK_THRESHOLD = 0.70

    _VLM_CONTRACT_KAUFVERTRAG_PROMPT = (
        "You are an Austrian tax document extraction expert.\n"
        "This is a Kaufvertrag (purchase contract). Extract ALL of these fields as JSON.\n"
        "Use null for fields you cannot find. Dates in YYYY-MM-DD. Amounts as plain numbers.\n"
        "{\n"
        '  "property_address": "full street address with unit/TOP, postal code and city",\n'
        '  "street": "street name and house number (e.g. Hauptstraße 12)",\n'
        '  "unit_number": "apartment/unit number, e.g. TOP 1, Top 3, Stiege 2/Top 5, or null",\n'
        '  "city": "city name",\n'
        '  "postal_code": "4-digit PLZ",\n'
        '  "purchase_price": total price as number,\n'
        '  "purchase_date": "YYYY-MM-DD signing date",\n'
        '  "building_value": building value as number,\n'
        '  "land_value": land value as number,\n'
        '  "grunderwerbsteuer": property transfer tax as number,\n'
        '  "notary_fees": notary fees as number,\n'
        '  "registry_fees": land registry fee as number,\n'
        '  "buyer_name": "buyer full name",\n'
        '  "seller_name": "seller full name",\n'
        '  "construction_year": year as integer\n'
        "}\n"
        "CRITICAL: property_address must be a real street address, NOT cadastral numbers.\n"
        "Look for TOP/Wohnungstop/Stiege unit numbers — include them in unit_number.\n"
        "JSON only, no markdown."
    )

    _VLM_CONTRACT_MIETVERTRAG_PROMPT = (
        "You are an Austrian tax document extraction expert.\n"
        "This is a Mietvertrag (rental contract). Extract ALL of these fields as JSON.\n"
        "Use null for fields you cannot find. Dates in YYYY-MM-DD. Amounts as plain numbers.\n"
        "{\n"
        '  "property_address": "full street address with unit/TOP, postal code and city",\n'
        '  "street": "street name and house number (e.g. Hauptstraße 12)",\n'
        '  "unit_number": "apartment/unit number, e.g. TOP 1, Top 3, Stiege 2/Top 5, or null",\n'
        '  "city": "city name",\n'
        '  "postal_code": "4-digit PLZ",\n'
        '  "monthly_rent": net monthly rent as number,\n'
        '  "start_date": "YYYY-MM-DD lease start",\n'
        '  "end_date": "YYYY-MM-DD lease end or null if unbefristet",\n'
        '  "betriebskosten": monthly operating costs as number,\n'
        '  "heating_costs": monthly heating costs as number,\n'
        '  "deposit_amount": security deposit as number,\n'
        '  "utilities_included": true/false,\n'
        '  "tenant_name": "tenant full name",\n'
        '  "landlord_name": "landlord full name",\n'
        '  "contract_type": "Befristet or Unbefristet"\n'
        "}\n"
        "CRITICAL: Read the FULL document across all pages. "
        "Look for Kaution/deposit amount, Betriebskosten, and contract end date carefully.\n"
        "Look for TOP/Wohnungstop/Stiege unit numbers — include them in unit_number.\n"
        "JSON only, no markdown."
    )

    def _vlm_contract_fallback(
        self, image_bytes: bytes, contract_type: str, extracted_data: dict,
    ) -> dict:
        """
        Use VLM (gpt-4o vision) to extract contract fields directly from the document image.
        Called when Tesseract+LLM confidence is below threshold.

        For PDFs: renders all pages (up to 5) as images and sends them ALL in a single
        VLM request using multi-image support. This gives the model full context across
        all pages while using only one API call.
        """
        from app.services.llm_service import get_llm_service

        llm = get_llm_service()
        if not llm.is_available:
            logger.warning("VLM contract fallback: LLM service unavailable")
            return extracted_data

        # Determine prompt based on contract type
        if contract_type == "kaufvertrag":
            system_prompt = self._VLM_CONTRACT_KAUFVERTRAG_PROMPT
        else:
            system_prompt = self._VLM_CONTRACT_MIETVERTRAG_PROMPT

        try:
            if image_bytes[:5] == b"%PDF-":
                import fitz

                doc = fitz.open(stream=image_bytes, filetype="pdf")
                num_pages = min(len(doc), 5)

                # Render all pages as images
                images: list[tuple[bytes, str]] = []
                for i in range(num_pages):
                    page = doc[i]
                    mat = fitz.Matrix(100 / 72, 100 / 72)  # 100 DPI (contracts have large text)
                    pix = page.get_pixmap(matrix=mat)
                    images.append((pix.tobytes("png"), "image/png"))
                doc.close()

                if not images:
                    return extracted_data

                logger.info(
                    "VLM contract fallback: sending %d pages in single request", len(images),
                )

                # Single multi-image VLM call — all pages at once
                response = llm.generate_vision_multi(
                    system_prompt=system_prompt,
                    user_prompt=(
                        f"This contract has {len(images)} pages. "
                        "All pages are shown above. Extract ALL fields by reading across all pages. "
                        "Key info like deposit (Kaution), end date, and operating costs (Betriebskosten) "
                        "may appear on later pages. Return a single JSON object."
                    ),
                    images=images,
                    temperature=0.0,
                    max_tokens=2000,
                    provider_preference=self._vision_provider_preference,
                )
                vlm_data = self._parse_llm_contract_response(response) or {}

            else:
                # Single image — send directly
                logger.info(
                    "VLM contract fallback: sending image (%d bytes)", len(image_bytes),
                )
                response = llm.generate_vision(
                    system_prompt=system_prompt,
                    user_prompt="Extract all contract fields from this document image. Return JSON only.",
                    image_bytes=image_bytes,
                    mime_type="image/jpeg",
                    temperature=0.0,
                    max_tokens=2000,
                    provider_preference=self._vision_provider_preference,
                )
                vlm_data = self._parse_llm_contract_response(response) or {}

            if not vlm_data:
                logger.warning("VLM contract fallback: no data extracted")
                extracted_data["_vlm_fallback"] = "no_data"
                return extracted_data

            # Merge VLM results into existing data
            field_conf = extracted_data.get("field_confidence", {})
            vlm_filled = []
            vlm_corrected = []

            for key, vlm_val in vlm_data.items():
                if vlm_val is None:
                    continue
                current_val = extracted_data.get(key)
                current_conf = field_conf.get(key, 0.0)

                if current_val is None:
                    # Fill missing field from VLM
                    extracted_data[key] = vlm_val
                    field_conf[key] = 0.90  # VLM vision confidence
                    vlm_filled.append(key)
                elif current_conf < 0.90 and str(vlm_val) != str(current_val):
                    # VLM is authoritative — any disagreement below 0.90 → use VLM
                    extracted_data[key] = vlm_val
                    field_conf[key] = 0.90
                    vlm_corrected.append(key)
                # Only keep existing if confidence >= 0.90 AND values agree

            extracted_data["field_confidence"] = field_conf
            extracted_data["_vlm_fallback"] = {
                "filled": vlm_filled,
                "corrected": vlm_corrected,
            }

            # Rebuild property_address from best available components
            # VLM often corrects street/city/postal_code but property_address
            # still holds the old regex value (e.g. OCR typo "Trenneberg" vs correct "Thenneberg")
            best_street = extracted_data.get("street") or ""
            best_unit = extracted_data.get("unit_number") or ""
            best_postal = extracted_data.get("postal_code") or ""
            best_city = extracted_data.get("city") or ""
            if best_street:
                addr_parts = [best_street]
                if best_unit:
                    addr_parts[0] = f"{best_street}/{best_unit}"
                if best_postal or best_city:
                    addr_parts.append(f"{best_postal} {best_city}".strip())
                new_addr = ", ".join(addr_parts)
                old_addr = extracted_data.get("property_address", "")
                if new_addr != old_addr:
                    extracted_data["property_address"] = new_addr
                    field_conf["property_address"] = 0.85
                    logger.info(
                        "Rebuilt property_address: '%s' → '%s'", old_addr, new_addr,
                    )

            logger.info(
                "VLM contract fallback done: filled %s, corrected %s",
                vlm_filled, vlm_corrected,
            )
            return extracted_data

        except Exception as e:
            logger.warning("VLM contract fallback failed: %s", e)
            extracted_data["_vlm_fallback"] = f"error: {e}"
            return extracted_data

    def _route_to_contract_extractor(
        self, doc_type: DocumentType, raw_text: str, image_bytes: bytes, start_time: datetime
    ) -> OCRResult:
        """
        Route Kaufvertrag and Mietvertrag documents to specialized extractors.

        Pipeline (adaptive):
          - Regex extracts what it can from OCR text
          - If many fields missing (≥3): skip LLM text, go straight to VLM vision (faster)
          - If few fields missing: LLM text supplement only (cheaper, usually sufficient)
          - If LLM text leaves gaps: VLM vision fallback
        """
        try:
            contract_type = "kaufvertrag" if doc_type == DocumentType.KAUFVERTRAG else "mietvertrag"

            if doc_type == DocumentType.KAUFVERTRAG:
                from app.services.purchase_contract_intelligence import (
                    PurchaseContractKind,
                    detect_purchase_contract_kind,
                    extract_asset_purchase_contract_fields,
                )

                contract_kind = detect_purchase_contract_kind(
                    raw_text,
                    classifier=self.classifier,
                )
                if contract_kind == PurchaseContractKind.ASSET:
                    extracted_data = extract_asset_purchase_contract_fields(
                        raw_text,
                        classifier=self.classifier,
                    )
                    conf = float(extracted_data.get("confidence") or 0.0)
                    processing_time = (datetime.now() - start_time).total_seconds() * 1000
                    return OCRResult(
                        document_type=doc_type,
                        extracted_data=extracted_data,
                        raw_text=raw_text,
                        confidence_score=conf,
                        needs_review=conf < self.TAX_FORM_LLM_FALLBACK_THRESHOLD,
                        processing_time_ms=processing_time,
                        suggestions=self._generate_contract_suggestions(conf),
                    )

                from app.services.kaufvertrag_ocr_service import KaufvertragOCRService

                service = KaufvertragOCRService()
                result = service.process_kaufvertrag_from_text(raw_text)
                extracted_data = service.extractor.to_dict(result.kaufvertrag_data)
                extracted_data["purchase_contract_kind"] = PurchaseContractKind.PROPERTY.value
            else:
                from app.services.mietvertrag_ocr_service import MietvertragOCRService

                service = MietvertragOCRService()
                result = service.process_mietvertrag_from_text(raw_text)
                extracted_data = service.extractor.to_dict(result.mietvertrag_data)

            # Count missing required fields after regex
            required = (
                self._KAUFVERTRAG_REQUIRED if contract_type == "kaufvertrag"
                else self._MIETVERTRAG_REQUIRED
            )
            missing_after_regex = [f for f in required if not extracted_data.get(f)]

            if len(missing_after_regex) >= 3:
                # Many fields missing → OCR text is too garbled for LLM text extraction
                # Skip LLM supplement, go straight to VLM vision (reads actual images)
                logger.info(
                    "Contract %s: %d required fields missing after regex %s — "
                    "skipping LLM text, going straight to VLM vision",
                    contract_type, len(missing_after_regex), missing_after_regex,
                )
                extracted_data["_llm_supplement"] = "skipped_for_vlm"
                extracted_data = self._vlm_contract_fallback(
                    image_bytes, contract_type, extracted_data,
                )
            else:
                # Few fields missing → LLM text supplement is likely sufficient
                extracted_data = self._llm_supplement_contract(
                    extracted_data, raw_text, contract_type
                )

                # Check if VLM fallback is still needed
                conf = self._contract_confidence(extracted_data, contract_type)
                logger.info(
                    "Contract extraction after regex+LLM: conf=%.2f, threshold=%.2f, will_vlm=%s",
                    conf, self._VLM_FALLBACK_THRESHOLD, conf < self._VLM_FALLBACK_THRESHOLD,
                )

                if conf < self._VLM_FALLBACK_THRESHOLD:
                    logger.info(
                        "Contract confidence %.2f < %.2f threshold, triggering VLM vision fallback",
                        conf, self._VLM_FALLBACK_THRESHOLD,
                    )
                    extracted_data = self._vlm_contract_fallback(
                        image_bytes, contract_type, extracted_data,
                    )

            # Final confidence calculation
            conf = self._contract_confidence(extracted_data, contract_type)

            # If confidence still < 0.9 after regex+LLM+VLM, try full LLM extraction
            if conf < self.TAX_FORM_LLM_FALLBACK_THRESHOLD:
                logger.info(
                    "Contract %s final confidence %.2f < 0.9, attempting LLM tax form fallback",
                    contract_type, conf,
                )
                llm_result = self._try_llm_tax_form_extraction(
                    raw_text, doc_type, extracted_data, conf, start_time,
                )
                if llm_result is not None:
                    return llm_result

            # Sync confidence into extracted_data so DB value matches
            extracted_data["confidence"] = conf
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return OCRResult(
                document_type=doc_type,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=conf,
                needs_review=conf < self.TAX_FORM_LLM_FALLBACK_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=self._generate_contract_suggestions(conf),
            )

        except Exception as e:
            # On total failure, try LLM as last resort
            llm_result = self._try_llm_tax_form_extraction(
                raw_text, doc_type, {}, 0.0, start_time,
            )
            if llm_result is not None:
                return llm_result
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return OCRResult(
                document_type=doc_type,
                extracted_data={},
                raw_text=raw_text,
                confidence_score=0.0,
                needs_review=True,
                processing_time_ms=processing_time,
                suggestions=[f"Contract extraction failed: {str(e)}"],
            )

    def _route_to_kreditvertrag_extractor(
        self,
        raw_text: str,
        start_time: datetime,
    ) -> OCRResult:
        """Route loan contracts to the dedicated Kreditvertrag extractor."""
        try:
            from app.services.kreditvertrag_extractor import KreditvertragExtractor

            extractor = KreditvertragExtractor()
            data = extractor.extract(raw_text)
            extracted_data = extractor.to_dict(data)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return OCRResult(
                document_type=DocumentType.LOAN_CONTRACT,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=data.confidence,
                needs_review=data.confidence < self.TAX_FORM_LLM_FALLBACK_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=self._generate_loan_document_suggestions(data.confidence),
            )
        except Exception as e:
            logger.error("Kreditvertrag extraction failed: %s", e)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return OCRResult(
                document_type=DocumentType.LOAN_CONTRACT,
                extracted_data={},
                raw_text=raw_text,
                confidence_score=0.0,
                needs_review=True,
                processing_time_ms=processing_time,
                suggestions=[f"Kreditvertrag extraction failed: {str(e)}"],
            )

    # Tax form types that use the generic _route_to_tax_form_extractor
    TAX_FORM_EXTRACTOR_TYPES = {
        DocumentType.LOHNZETTEL,
        DocumentType.L1_FORM,
        DocumentType.L1K_BEILAGE,
        DocumentType.L1AB_BEILAGE,
        DocumentType.E1A_BEILAGE,
        DocumentType.E1B_BEILAGE,
        DocumentType.E1KV_BEILAGE,
        DocumentType.U1_FORM,
        DocumentType.U30_FORM,
        DocumentType.JAHRESABSCHLUSS,
        DocumentType.SVS_NOTICE,
        DocumentType.PROPERTY_TAX,
        DocumentType.BANK_STATEMENT,
    }

    # Confidence threshold for LLM fallback on tax forms — tax data must be accurate
    TAX_FORM_LLM_FALLBACK_THRESHOLD = 0.9

    def _route_to_tax_form_extractor(
        self, doc_type: DocumentType, raw_text: str, start_time: datetime
    ) -> OCRResult:
        """
        Generic router for all tax form extractors (L16, L1, E1a, E1b, etc.).

        Each extractor follows the same interface: extract(text) -> XxxData with .confidence
        and to_dict(data) -> dict.

        If regex extraction confidence < 0.9, attempts LLM fallback for higher accuracy.
        """
        extractor_map = {
            DocumentType.LOHNZETTEL: ("app.services.l16_extractor", "L16Extractor"),
            DocumentType.L1_FORM: ("app.services.l1_form_extractor", "L1FormExtractor"),
            DocumentType.L1K_BEILAGE: ("app.services.l1k_extractor", "L1kExtractor"),
            DocumentType.L1AB_BEILAGE: ("app.services.l1ab_extractor", "L1abExtractor"),
            DocumentType.E1A_BEILAGE: ("app.services.e1a_extractor", "E1aExtractor"),
            DocumentType.E1B_BEILAGE: ("app.services.e1b_extractor", "E1bExtractor"),
            DocumentType.E1KV_BEILAGE: ("app.services.e1kv_extractor", "E1kvExtractor"),
            DocumentType.U1_FORM: ("app.services.vat_form_extractor", "VatFormExtractor"),
            DocumentType.U30_FORM: ("app.services.vat_form_extractor", "VatFormExtractor"),
            DocumentType.JAHRESABSCHLUSS: (
                "app.services.jahresabschluss_extractor", "JahresabschlussExtractor"
            ),
            DocumentType.SVS_NOTICE: ("app.services.svs_extractor", "SvsExtractor"),
            DocumentType.PROPERTY_TAX: (
                "app.services.grundsteuer_extractor", "GrundsteuerExtractor"
            ),
            DocumentType.BANK_STATEMENT: (
                "app.services.kontoauszug_extractor", "KontoauszugExtractor"
            ),
        }

        try:
            import importlib

            module_path, class_name = extractor_map[doc_type]
            module = importlib.import_module(module_path)
            extractor_cls = getattr(module, class_name)
            extractor = extractor_cls()

            # U30 uses extract_u30 method
            if doc_type == DocumentType.U30_FORM and hasattr(extractor, "extract_u30"):
                data = extractor.extract_u30(raw_text)
            else:
                data = extractor.extract(raw_text)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            extracted_data = extractor.to_dict(data)

            # If regex confidence < 0.9, try LLM fallback for better accuracy
            if data.confidence < self.TAX_FORM_LLM_FALLBACK_THRESHOLD:
                logger.info(
                    "Tax form %s regex confidence %.2f < %.2f, attempting LLM fallback",
                    doc_type.value, data.confidence, self.TAX_FORM_LLM_FALLBACK_THRESHOLD,
                )
                llm_result = self._try_llm_tax_form_extraction(
                    raw_text, doc_type, extracted_data, data.confidence, start_time
                )
                if llm_result is not None:
                    return llm_result
                logger.info(
                    "LLM fallback unavailable/failed for %s, using regex result (%.2f)",
                    doc_type.value, data.confidence,
                )

            return OCRResult(
                document_type=doc_type,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=data.confidence,
                needs_review=data.confidence < self.TAX_FORM_LLM_FALLBACK_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=self._generate_tax_document_suggestions(data.confidence),
            )

        except Exception as e:
            logger.error(f"Tax form extraction failed for {doc_type.value}: {e}")
            # On total failure, try LLM as last resort
            llm_result = self._try_llm_tax_form_extraction(
                raw_text, doc_type, {}, 0.0, start_time
            )
            if llm_result is not None:
                return llm_result
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return OCRResult(
                document_type=doc_type,
                extracted_data={},
                raw_text=raw_text,
                confidence_score=0.0,
                needs_review=True,
                processing_time_ms=processing_time,
                suggestions=[f"{doc_type.value} extraction failed: {str(e)}"],
            )

    def _try_llm_tax_form_extraction(
        self,
        raw_text: str,
        doc_type: DocumentType,
        regex_data: dict,
        regex_confidence: float,
        start_time: datetime,
    ) -> Optional[OCRResult]:
        """
        LLM fallback for tax form extraction when regex confidence < 0.9.

        Sends the raw text + document type hint to the LLM and asks it to extract
        structured KZ fields. Merges LLM result with regex result, preferring LLM
        values for fields that regex missed (None/0).
        """
        if not self.llm_extractor.is_available:
            return None

        try:
            logger.info(
                "LLM fallback for tax form %s (regex confidence %.2f)",
                doc_type.value, regex_confidence,
            )

            # Build a targeted prompt for the specific tax form type
            llm_data = self.llm_extractor.extract(
                raw_text,
                doc_type,
                provider_preference=self._vision_provider_preference,
            )
            if not llm_data or not isinstance(llm_data, dict):
                return None

            # Merge: LLM fills in gaps from regex, regex values kept if both present
            merged = dict(regex_data)
            llm_filled = 0
            for k, v in llm_data.items():
                if v is None:
                    continue
                existing = merged.get(k)
                if existing is None or existing == 0 or existing == "":
                    merged[k] = v
                    llm_filled += 1

            if llm_filled == 0:
                logger.info("LLM did not fill any new fields for %s", doc_type.value)
                return None

            # Recalculate confidence: boost based on how many fields LLM filled
            total_fields = len([v for v in merged.values() if v is not None and v != 0])
            new_confidence = min(0.95, regex_confidence + llm_filled * 0.05)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                "LLM fallback for %s: filled %d fields, confidence %.2f → %.2f",
                doc_type.value, llm_filled, regex_confidence, new_confidence,
            )

            merged["_extraction_method"] = "regex+llm"

            return OCRResult(
                document_type=doc_type,
                extracted_data=merged,
                raw_text=raw_text,
                confidence_score=new_confidence,
                needs_review=new_confidence < self.TAX_FORM_LLM_FALLBACK_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=[
                    f"AI-assisted extraction used (regex confidence was {regex_confidence:.0%})."
                ],
            )
        except Exception as e:
            logger.warning("LLM tax form fallback failed for %s: %s", doc_type.value, e)
            return None

    def _route_to_bescheid_extractor(
        self, raw_text: str, start_time: datetime
    ) -> OCRResult:
        """
        Route Einkommensteuerbescheid to specialized extractor.
        Falls back to LLM if confidence < 0.9.
        """
        try:
            from app.services.bescheid_extractor import BescheidExtractor

            extractor = BescheidExtractor()
            data = extractor.extract(raw_text)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            extracted_data = extractor.to_dict(data)

            # LLM fallback if confidence < 0.9
            if data.confidence < self.TAX_FORM_LLM_FALLBACK_THRESHOLD:
                logger.info(
                    "Bescheid regex confidence %.2f < 0.9, attempting LLM fallback",
                    data.confidence,
                )
                llm_result = self._try_llm_tax_form_extraction(
                    raw_text, DocumentType.EINKOMMENSTEUERBESCHEID,
                    extracted_data, data.confidence, start_time,
                )
                if llm_result is not None:
                    return llm_result

            return OCRResult(
                document_type=DocumentType.EINKOMMENSTEUERBESCHEID,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=data.confidence,
                needs_review=data.confidence < self.TAX_FORM_LLM_FALLBACK_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=self._generate_tax_document_suggestions(data.confidence),
            )

        except Exception as e:
            # On total failure, try LLM as last resort
            llm_result = self._try_llm_tax_form_extraction(
                raw_text, DocumentType.EINKOMMENSTEUERBESCHEID, {}, 0.0, start_time,
            )
            if llm_result is not None:
                return llm_result
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return OCRResult(
                document_type=DocumentType.EINKOMMENSTEUERBESCHEID,
                extracted_data={},
                raw_text=raw_text,
                confidence_score=0.0,
                needs_review=True,
                processing_time_ms=processing_time,
                suggestions=[f"Bescheid extraction failed: {str(e)}"],
            )

    def _route_to_e1_extractor(
        self, raw_text: str, start_time: datetime
    ) -> OCRResult:
        """
        Route E1 tax declaration form to specialized extractor.

        Strategy: Regex extractor first (fast, reliable, 900+ lines of
        Austrian-tax-specific logic). LLM is only used as a lightweight
        validation layer when regex confidence is below threshold.
        AI = orchestration layer, not data extraction.
        """
        from app.services.e1_form_extractor import E1FormExtractor

        try:
            extractor = E1FormExtractor()
            data = extractor.extract(raw_text)
            extracted_data = extractor.to_dict(data)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # If regex confidence is high enough, return directly
            if data.confidence >= self.TAX_FORM_LLM_FALLBACK_THRESHOLD:
                logger.info(
                    "E1 regex extraction succeeded: confidence %.2f", data.confidence
                )
                return OCRResult(
                    document_type=DocumentType.E1_FORM,
                    extracted_data=extracted_data,
                    raw_text=raw_text,
                    confidence_score=data.confidence,
                    needs_review=False,
                    processing_time_ms=processing_time,
                    suggestions=[],
                )

            # Low confidence — try LLM to validate/supplement key fields
            llm_supplement = self._try_llm_e1_validation(
                raw_text, extracted_data, data.confidence
            )
            if llm_supplement:
                extracted_data.update(llm_supplement)
                # Bump confidence slightly since LLM confirmed/added fields
                boosted = min(0.95, data.confidence + 0.15)
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                logger.info(
                    "E1 LLM validation supplemented %d fields, confidence %.2f -> %.2f",
                    len(llm_supplement), data.confidence, boosted,
                )
                if boosted >= self.TAX_FORM_LLM_FALLBACK_THRESHOLD:
                    return OCRResult(
                        document_type=DocumentType.E1_FORM,
                        extracted_data=extracted_data,
                        raw_text=raw_text,
                        confidence_score=boosted,
                        needs_review=False,
                        processing_time_ms=processing_time,
                        suggestions=["AI validation used to supplement extraction."],
                    )
                # Boosted but still < 0.9 — fall through to full LLM extraction

            # Still below threshold — try full LLM tax form extraction
            logger.info(
                "E1 confidence still < 0.9 after validation, attempting full LLM fallback",
            )
            llm_result = self._try_llm_tax_form_extraction(
                raw_text, DocumentType.E1_FORM, extracted_data,
                data.confidence, start_time,
            )
            if llm_result is not None:
                return llm_result

            # LLM unavailable or didn't help — return regex result as-is
            return OCRResult(
                document_type=DocumentType.E1_FORM,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=data.confidence,
                needs_review=data.confidence < self.TAX_FORM_LLM_FALLBACK_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=self._generate_tax_document_suggestions(data.confidence),
            )

        except Exception as e:
            # On total failure, try LLM as last resort
            llm_result = self._try_llm_tax_form_extraction(
                raw_text, DocumentType.E1_FORM, {}, 0.0, start_time,
            )
            if llm_result is not None:
                return llm_result
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return OCRResult(
                document_type=DocumentType.E1_FORM,
                extracted_data={},
                raw_text=raw_text,
                confidence_score=0.0,
                needs_review=True,
                processing_time_ms=processing_time,
                suggestions=[f"E1 form extraction failed: {str(e)}"],
            )


    def _try_llm_e1_validation(
        self, raw_text: str, extracted_data: dict, regex_confidence: float
    ) -> Optional[Dict[str, Any]]:
        """
        LLM as validation/supplement layer for E1 forms.

        Only called when regex confidence is low. Sends a compact summary of
        what regex already found plus a focused text excerpt, asking the LLM
        to fill in missing fields. Returns a dict of supplemental fields to
        merge, or None if LLM unavailable/unhelpful.

        AI = orchestration layer. Regex does the heavy lifting.
        """
        from app.services.llm_service import get_llm_service

        llm = get_llm_service()
        if not llm.is_available:
            return None

        # Identify which key fields regex missed
        key_fields = {
            "tax_year": "Steuerjahr",
            "taxpayer_name": "Name des Steuerpflichtigen",
            "steuernummer": "Steuernummer",
            "kz_245": "KZ 245 (Einkünfte aus nichtselbständiger Arbeit)",
            "kz_260": "KZ 260 (Lohnsteuer)",
            "kz_350": "KZ 350 (Einkünfte aus Vermietung)",
        }
        missing = {k: desc for k, desc in key_fields.items() if not extracted_data.get(k)}

        if not missing:
            # Nothing to supplement
            return None

        # Send a compact excerpt (first 6000 chars) — just enough for LLM
        # to find the missing fields without blowing the context window
        excerpt = raw_text[:6000]

        missing_list = ", ".join(f"{k} ({desc})" for k, desc in missing.items())
        system_prompt = (
            "You are validating an Austrian E1 tax form extraction. "
            "The regex extractor missed some fields. "
            "Find ONLY the missing fields from the text. Reply with JSON only.\n"
            "Austrian number format: 1.234,56 → output as 1234.56\n"
            "Return ONLY a flat JSON object with the missing field keys and values."
        )
        user_prompt = (
            f"Missing fields: {missing_list}\n\n"
            f"Document text (excerpt):\n{excerpt}"
        )

        try:
            logger.info(
                "LLM E1 validation: %d missing fields, %d chars excerpt",
                len(missing), len(excerpt),
            )
            response = llm.generate_simple(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=500,
                provider_preference=self._vision_provider_preference,
            )

            data = self._parse_vlm_json(response)
            if not data or not isinstance(data, dict):
                return None

            # Only return fields that were actually missing
            supplement = {k: v for k, v in data.items() if k in missing and v is not None}
            if supplement:
                logger.info("LLM supplemented %d fields: %s", len(supplement), list(supplement))
            return supplement or None

        except Exception as e:
            logger.warning("LLM E1 validation failed: %s", e)
            return None

    def _generate_tax_document_suggestions(self, confidence: float) -> List[str]:
        """
        Generate suggestions for tax document processing

        Args:
            confidence: Overall confidence score

        Returns:
            List of suggestions
        """
        suggestions = []

        if confidence < 0.5:
            suggestions.append(
                "Low confidence in tax document extraction. Please review all fields carefully."
            )
        elif confidence < 0.7:
            suggestions.append("Medium confidence. Please verify critical tax fields.")

        suggestions.append("Tax document detected. Review extracted data before using for calculations.")

        return suggestions

    def _generate_contract_suggestions(self, confidence: float) -> List[str]:
        """
        Generate suggestions for contract document processing

        Args:
            confidence: Overall confidence score

        Returns:
            List of suggestions
        """
        suggestions = []

        if confidence < 0.5:
            suggestions.append(
                "Low confidence in contract extraction. Please review all fields carefully."
            )
        elif confidence < 0.7:
            suggestions.append("Medium confidence. Please verify critical fields like dates and amounts.")

        suggestions.append("Contract documents detected. Review extracted property details before saving.")

        return suggestions

    def _generate_loan_document_suggestions(self, confidence: float) -> List[str]:
        """Generate suggestions for loan contract extraction."""
        suggestions = []

        if confidence < 0.5:
            suggestions.append(
                "Low confidence in loan contract extraction. Please review all financial terms carefully."
            )
        elif confidence < 0.7:
            suggestions.append(
                "Medium confidence. Please verify loan amount, interest rate, and repayment dates."
            )

        suggestions.append(
            "Loan contract detected. Review lender, borrower, and repayment terms before confirming."
        )
        return suggestions

    # ---- LLM supplement for contracts ----

    # Required fields per contract type — if ALL present with high confidence, skip LLM
    _KAUFVERTRAG_REQUIRED = [
        "property_address", "purchase_price", "purchase_date",
        "building_value", "land_value", "grunderwerbsteuer",
        "notary_fees", "registry_fees", "construction_year",
        "buyer_name", "seller_name",
    ]
    _MIETVERTRAG_REQUIRED = [
        "property_address", "monthly_rent", "start_date", "end_date",
        "tenant_name", "landlord_name", "deposit_amount",
        "betriebskosten",
    ]

    _CONTRACT_SUPPLEMENT_PROMPT = """You are an Austrian tax document extraction assistant.
You are given OCR text from a {contract_type_de} and a set of fields already extracted by regex.
Your job:
1. For each field marked null/missing, extract the correct value from the text.
2. For each field already extracted, verify it is correct. If you find a discrepancy, return the corrected value.
3. Return ONLY a JSON object with the fields. Use null for fields you cannot find.

IMPORTANT RULES:
- Dates must be in YYYY-MM-DD format
- Amounts must be plain numbers (no currency symbols, no thousand separators)
- For purchase_date: this is the contract signing date, NOT dates referencing other documents
- For construction_year: look for Baujahr, Errichtungsjahr, erbaut, or similar
- For notary_fees: look for Notarkosten, Vertragserrichtungskosten, Honorar
- For registry_fees: look for Eintragungsgebühr, Grundbuchgebühr
- For deposit_amount: look for Kaution, Sicherheitsleistung
- For betriebskosten: look for Betriebskosten, BK, Nebenkosten

CRITICAL ADDRESS RULES:
- property_address MUST be a real street address (e.g. "Angeligasse 86, 1100 Wien"), NOT a cadastral/land registry number
- GST-NR like "816/129" or "GST-Fläche 615" are cadastral parcel numbers — NEVER use these as property_address
- Look for GST-ADRESSE entries in the Grundbuch section — these contain actual street names
- Look for addresses after "Bauf. (20)" entries — these are building addresses
- Combine street + postal code + city from the Grundbuch or contract text
- If the buyer or seller address in the contract matches the property district, that may be the property address
- The Katastralgemeinde name and Bezirksgericht help identify the district/city

Return ONLY valid JSON, no markdown, no explanation."""

    _KAUFVERTRAG_FIELDS_PROMPT = """Extract/verify these fields from the Kaufvertrag:
{{
  "property_address": "full STREET address with postal code and city (e.g. 'Angeligasse 86, 1100 Wien'). NEVER use cadastral numbers like '816/129' or 'GST-Fläche'. Look for GST-ADRESSE or Bauf.(20) entries in the Grundbuch section for the actual street name.",
  "street": "street name and house number (e.g. 'Angeligasse 86')",
  "city": "city name",
  "postal_code": "PLZ (4-digit Austrian postal code)",
  "purchase_price": total purchase price as number,
  "purchase_date": "YYYY-MM-DD contract signing date",
  "building_value": building value as number (Gebäudewert),
  "land_value": land value as number (Grundwert),
  "grunderwerbsteuer": property transfer tax as number (3.5% of price),
  "notary_fees": notary fees as number,
  "registry_fees": land registry fee as number (Eintragungsgebühr, 1.1% of price),
  "buyer_name": "buyer full name",
  "seller_name": "seller full name",
  "construction_year": year as integer,
  "property_type": "Wohnung/Haus/Grundstück",
  "notary_name": "notary full name",
  "notary_location": "notary city"
}}

Already extracted by regex (verify these):
{existing_json}

OCR text:
{raw_text}"""

    _MIETVERTRAG_FIELDS_PROMPT = """Extract/verify these fields from the Mietvertrag:
{{
  "property_address": "full address",
  "street": "street name and number",
  "city": "city name",
  "postal_code": "PLZ",
  "monthly_rent": net monthly rent as number (Hauptmietzins),
  "start_date": "YYYY-MM-DD lease start date",
  "end_date": "YYYY-MM-DD lease end date or null if unbefristet",
  "betriebskosten": monthly operating costs as number,
  "heating_costs": monthly heating costs as number,
  "deposit_amount": security deposit as number (Kaution),
  "tenant_name": "tenant full name (Mieter)",
  "landlord_name": "landlord full name (Vermieter)",
  "contract_type": "Befristet/Unbefristet"
}}

Already extracted by regex (verify these):
{existing_json}

OCR text:
{raw_text}"""

    def _llm_supplement_contract(
        self, extracted_data: dict, raw_text: str, contract_type: str,
    ) -> dict:
        """
        Use LLM to fill missing fields and validate existing ones.

        Skip LLM if all required fields are present and average field confidence >= 0.90.
        """
        required = (
            self._KAUFVERTRAG_REQUIRED if contract_type == "kaufvertrag"
            else self._MIETVERTRAG_REQUIRED
        )

        # Check if all required fields are present (non-null)
        field_conf = extracted_data.get("field_confidence", {})
        missing = [f for f in required if not extracted_data.get(f)]

        # Detect cadastral numbers mistakenly used as property_address
        # GST-NR patterns: "816/129", "GST-Fläche 615", pure numbers with slashes
        import re as _re
        current_addr = extracted_data.get("property_address") or ""
        if current_addr and _re.match(
            r"^[\d/]+\s*(?:GST|Fläche|Flache|EZ|KG|BG)|\d{2,}/\d{1,}",
            current_addr, _re.IGNORECASE,
        ):
            logger.info(
                "Cadastral number detected as property_address: '%s' — lowering confidence",
                current_addr,
            )
            field_conf["property_address"] = 0.30  # Force LLM to correct

        avg_conf = (
            sum(field_conf.values()) / len(field_conf) if field_conf else 0.0
        )

        if not missing and avg_conf >= 0.90:
            logger.info(
                "Contract LLM supplement skipped: all %d required fields present, "
                "avg confidence %.2f",
                len(required), avg_conf,
            )
            extracted_data["_llm_supplement"] = "skipped"
            return extracted_data

        logger.info(
            "Contract LLM supplement: %d missing fields %s, avg confidence %.2f",
            len(missing), missing, avg_conf,
        )

        try:
            from app.services.llm_service import LLMService
            import json as _json

            llm = LLMService()

            # Build existing fields JSON (only non-null, non-meta fields)
            skip_keys = {"field_confidence", "confidence", "_llm_supplement"}
            existing = {
                k: v for k, v in extracted_data.items()
                if k not in skip_keys and v is not None
            }
            existing_json = _json.dumps(existing, ensure_ascii=False, indent=2)

            # Truncate raw_text to ~6000 chars to stay within token limits
            text_for_llm = raw_text[:6000] if len(raw_text) > 6000 else raw_text

            contract_type_de = "Kaufvertrag" if contract_type == "kaufvertrag" else "Mietvertrag"
            system_prompt = self._CONTRACT_SUPPLEMENT_PROMPT.format(
                contract_type_de=contract_type_de
            )

            if contract_type == "kaufvertrag":
                user_prompt = self._KAUFVERTRAG_FIELDS_PROMPT.format(
                    existing_json=existing_json, raw_text=text_for_llm,
                )
            else:
                user_prompt = self._MIETVERTRAG_FIELDS_PROMPT.format(
                    existing_json=existing_json, raw_text=text_for_llm,
                )

            response = llm.generate_simple(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=2000,
                provider_preference=self._vision_provider_preference,
            )

            # Parse LLM response
            llm_data = self._parse_llm_contract_response(response)
            if not llm_data:
                logger.warning("Contract LLM supplement: failed to parse response")
                extracted_data["_llm_supplement"] = "parse_failed"
                return extracted_data

            # Fields that must stay as strings
            _str_fields = {
                "postal_code", "street", "city", "property_address",
                "tenant_name", "landlord_name", "buyer_name", "seller_name",
                "notary_name", "notary_location", "contract_type", "unit_number",
                "start_date", "end_date", "purchase_date",
            }

            # Merge: LLM fills missing fields, corrects low-confidence fields
            filled = []
            corrected = []
            for key, llm_val in llm_data.items():
                if llm_val is None:
                    continue
                # Ensure string fields stay as strings (e.g. postal_code: 2571.0 → "2571")
                if key in _str_fields and not isinstance(llm_val, str):
                    llm_val = str(llm_val)
                    if llm_val.endswith(".0"):
                        llm_val = llm_val[:-2]

                current_val = extracted_data.get(key)
                current_conf = field_conf.get(key, 0.0)

                if current_val is None:
                    # Fill missing field
                    extracted_data[key] = llm_val
                    field_conf[key] = 0.80  # LLM-sourced confidence
                    filled.append(key)
                elif current_conf < 0.70 and str(llm_val) != str(current_val):
                    # Low-confidence field disagrees with LLM → use LLM
                    extracted_data[key] = llm_val
                    field_conf[key] = 0.80
                    corrected.append(key)
                # High-confidence regex field agrees or LLM agrees → keep regex

            extracted_data["field_confidence"] = field_conf
            extracted_data["_llm_supplement"] = {
                "filled": filled,
                "corrected": corrected,
                "missing_before": missing,
            }

            logger.info(
                "Contract LLM supplement done: filled %s, corrected %s",
                filled, corrected,
            )
            return extracted_data

        except Exception as e:
            logger.warning("Contract LLM supplement failed: %s", e)
            extracted_data["_llm_supplement"] = f"error: {e}"
            return extracted_data

    @staticmethod
    def _parse_llm_contract_response(response: str) -> Optional[dict]:
        """Parse LLM JSON response for contract fields."""
        import json as _json

        text = response.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        # Find JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None

        # Fields that must stay as strings even if they look numeric
        _STRING_FIELDS = {
            "postal_code", "street", "city", "property_address",
            "tenant_name", "landlord_name", "buyer_name", "seller_name",
            "notary_name", "notary_location", "contract_type", "unit_number",
            "start_date", "end_date", "purchase_date",
        }

        try:
            data = _json.loads(text[start:end + 1])
            # Normalize numeric strings to float (skip string-only fields)
            for key in list(data.keys()):
                if key in _STRING_FIELDS:
                    # Ensure string fields stay as strings
                    if data[key] is not None and not isinstance(data[key], str):
                        data[key] = str(data[key])
                        # Strip trailing .0 from int-like floats (e.g. 2571.0 → "2571")
                        if isinstance(data[key], str) and data[key].endswith(".0"):
                            data[key] = data[key][:-2]
                    continue
                val = data[key]
                if isinstance(val, str):
                    # Try to parse as number if it looks numeric
                    cleaned = val.replace(",", ".").replace(" ", "")
                    try:
                        data[key] = float(cleaned)
                    except ValueError:
                        pass
            return data
        except _json.JSONDecodeError:
            return None

    @staticmethod
    def _contract_confidence(extracted_data: dict, contract_type: str) -> float:
        """Recalculate confidence after LLM supplement based on field completeness."""
        if contract_type == "kaufvertrag":
            critical = ["property_address", "purchase_price", "purchase_date"]
            important = [
                "building_value", "land_value", "grunderwerbsteuer",
                "buyer_name", "seller_name", "construction_year",
            ]
        else:
            critical = ["property_address", "monthly_rent", "start_date"]
            important = [
                "tenant_name", "landlord_name", "betriebskosten",
                "deposit_amount", "end_date",
            ]

        field_conf = extracted_data.get("field_confidence", {})

        # Critical fields: each missing one costs 0.20
        critical_score = 1.0
        for f in critical:
            if not extracted_data.get(f):
                critical_score -= 0.20

        # Important fields: each missing one costs 0.05
        important_present = sum(1 for f in important if extracted_data.get(f))
        important_missing = len(important) - important_present
        important_penalty = important_missing * 0.05

        # Average field confidence
        avg_conf = (
            sum(field_conf.values()) / len(field_conf) if field_conf else 0.5
        )

        score = (critical_score * 0.5) + (avg_conf * 0.3) - important_penalty + (important_present * 0.02)
        return round(min(1.0, max(0.0, score)), 2)


    def _load_image(self, image_bytes: bytes) -> np.ndarray:
        """Load image from bytes, with PDF support via PyMuPDF"""
        # Check if the bytes are a PDF (starts with %PDF)
        if image_bytes[:5] == b"%PDF-":
            return self._load_pdf_as_image(image_bytes)

        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            # Last resort: try treating as PDF even without magic bytes
            try:
                return self._load_pdf_as_image(image_bytes)
            except Exception:
                raise ValueError("Failed to decode image")

        return image

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text directly from PDF using PyMuPDF (no OCR needed if text layer exists).

        Also extracts AcroForm widget values (filled-in form fields) which are common
        in Austrian tax forms (E1, L1, etc.) where the text layer only contains labels
        but the actual data lives in interactive form fields.
        """
        try:
            import fitz

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            # Detect if this is a tax form (E1/L1/etc.) — they can be 10+ pages
            first_page_text = doc[0].get_text() if len(doc) > 0 else ""
            is_tax_form = any(
                kw in first_page_text
                for kw in [
                    "Einkommensteuererklärung",
                    "E 1,",
                    "E 1-PDF",
                    "E 1-EDV",
                    "Arbeitnehmerveranlagung",
                    "L 1,",
                    "Steuerberechnung",
                ]
            )
            max_pages = min(len(doc), 20 if is_tax_form else 5)

            text_parts = []
            form_field_parts = []

            for i in range(max_pages):
                page = doc[i]
                page_text = page.get_text()
                if page_text:
                    text_parts.append(f"--- PAGE {i + 1} ---\n{page_text}")

                # Extract AcroForm widget values (filled-in form fields)
                try:
                    for widget in page.widgets():
                        field_name = widget.field_name or ""
                        field_value = widget.field_value
                        if field_value and str(field_value).strip():
                            form_field_parts.append(f"{field_name}: {field_value}")
                except Exception:
                    pass  # page.widgets() may fail on non-form pages

            doc.close()

            combined = "\n".join(text_parts)

            # Append form field data so regex extractors can find KZ values
            if form_field_parts:
                logger.info(
                    "Extracted %d form field values from PDF", len(form_field_parts)
                )
                combined += "\n\n--- FORM FIELDS ---\n"
                combined += "\n".join(form_field_parts)

            return combined
        except Exception as e:
            logger.warning("PDF text extraction failed: %s", e)
            return ""

    def _load_pdf_as_image(self, pdf_bytes: bytes) -> np.ndarray:
        """Convert first page of PDF to OpenCV image using PyMuPDF"""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if len(doc) == 0:
                raise ValueError("PDF has no pages")

            # Render first page at 300 DPI for better OCR quality
            page = doc[0]
            mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat)

            # Convert to numpy array
            img_bytes = pix.tobytes("png")
            doc.close()

            nparr = np.frombuffer(img_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                raise ValueError("Failed to convert PDF page to image")

            return image
        except ImportError:
            raise ValueError(
                "PyMuPDF (fitz) is required for PDF processing. "
                "Install with: pip install PyMuPDF"
            )
        except Exception as e:
            raise ValueError(f"Failed to process PDF: {str(e)}")

    def _render_pdf_pages_for_vision(
        self,
        pdf_bytes: bytes,
        *,
        max_pages: int = 8,
        dpi: int = 200,
    ) -> list[tuple[bytes, str]]:
        """Render PDF pages to PNG bytes for direct vision transcription."""
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            num_pages = min(len(doc), max_pages)
            images: list[tuple[bytes, str]] = []
            matrix = fitz.Matrix(dpi / 72, dpi / 72)
            for index in range(num_pages):
                page = doc[index]
                pix = page.get_pixmap(matrix=matrix)
                images.append((pix.tobytes("png"), "image/png"))
            return images
        finally:
            doc.close()

    def _ocr_all_pdf_pages(self, pdf_bytes: bytes, max_pages: int = 5) -> str:
        """
        OCR all pages of a scanned PDF for better text extraction.

        Renders each page at 150 DPI (good balance: readable + fast).
        Concatenates text from all pages.
        """
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        num_pages = min(len(doc), max_pages)
        all_text = []

        logger.info("OCR scanning %d pages of scanned PDF at 150 DPI", num_pages)

        for i in range(num_pages):
            page = doc[i]
            mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI (was 300 — 4x faster)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")

            nparr = np.frombuffer(img_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                continue

            # Preprocess for better OCR
            processed = self.preprocessor.preprocess(image)
            try:
                page_text = pytesseract.image_to_string(
                    processed, config=self.config.TESSERACT_CONFIG
                )
                if page_text and page_text.strip():
                    all_text.append(f"--- PAGE {i + 1} ---\n{page_text.strip()}")
            except Exception as e:
                logger.error("Tesseract failed on page %d: %s", i + 1, e)

        doc.close()

        combined = "\n\n".join(all_text)
        if not combined:
            logger.error(
                "Tesseract extracted no text from %d PDF pages — all pages failed",
                num_pages,
            )
        else:
            logger.info(
                "Multi-page OCR complete: %d pages, %d chars extracted",
                num_pages, len(combined),
            )
        return combined

    def _extract_text(self, image: np.ndarray) -> str:
        """
        Extract text from image using Tesseract.
        Tries PSM 6 (uniform block) first, falls back to PSM 4 (sparse text)
        if result is too short — helps with parking receipts and small tickets.

        Args:
            image: Preprocessed image

        Returns:
            Extracted text
        """
        try:
            text = pytesseract.image_to_string(image, config=self.config.TESSERACT_CONFIG)
            text = text.strip()

            # If very little text extracted, retry with sparse text mode (PSM 4)
            # This helps with parking receipts, tickets, and non-standard layouts
            if len(text) < 30:
                sparse_config = self.config.TESSERACT_CONFIG.replace("--psm 6", "--psm 4")
                text2 = pytesseract.image_to_string(image, config=sparse_config).strip()
                if len(text2) > len(text):
                    logger.info("PSM 4 (sparse text) yielded better result: %d vs %d chars", len(text2), len(text))
                    text = text2

            return text
        except Exception as e:
            raise ValueError(f"Tesseract OCR failed: {str(e)}")

    def _calculate_confidence(
        self, extracted_data: Dict[str, Any], classification_confidence: float
    ) -> float:
        """
        Calculate overall confidence score

        Args:
            extracted_data: Extracted fields
            classification_confidence: Document classification confidence

        Returns:
            Overall confidence score (0.0 to 1.0)
        """
        # Start with classification confidence
        confidence = classification_confidence

        # Check field extraction confidence
        field_confidences = []
        for key, value in extracted_data.items():
            if key.endswith("_confidence"):
                field_confidences.append(value)

        if field_confidences:
            avg_field_confidence = sum(field_confidences) / len(field_confidences)
            # Weighted average: 40% classification, 60% field extraction
            confidence = 0.4 * classification_confidence + 0.6 * avg_field_confidence

        # Penalize if critical fields are missing
        critical_fields = ["date", "amount"]
        missing_critical = sum(
            1 for field in critical_fields if not extracted_data.get(field)
        )
        if missing_critical > 0:
            confidence *= 0.7  # Reduce confidence by 30%

        return min(confidence, 1.0)

    def _generate_suggestions(
        self, image: Optional[np.ndarray], extracted_data: Dict[str, Any], confidence: float
    ) -> List[str]:
        """
        Generate suggestions for improving OCR results

        Args:
            image: Original image (may be None for multi-page PDFs)
            extracted_data: Extracted data
            confidence: Overall confidence score

        Returns:
            List of suggestions
        """
        suggestions = []

        # Low confidence warning
        if confidence < 0.6:
            if image is not None:
                suggestions.append(
                    "OCR confidence is low. Consider retaking the photo with better lighting and focus."
                )
            else:
                suggestions.append(
                    "OCR confidence is low. Please verify the extracted fields manually."
                )

        # Image quality suggestions (only for photos, not PDFs)
        if image is not None:
            quality_suggestions = self.preprocessor.suggest_improvements(image)
            suggestions.extend(quality_suggestions)

        # Missing field warnings
        if not extracted_data.get("date"):
            suggestions.append("Date could not be extracted. Please verify manually.")

        if not extracted_data.get("amount"):
            suggestions.append("Amount could not be extracted. Please verify manually.")

        # Document-specific suggestions
        if not extracted_data.get("merchant") and not extracted_data.get("supplier"):
            suggestions.append(
                "Merchant/supplier name could not be identified. Please enter manually."
            )

        return suggestions

    def _group_results(self, results: List[OCRResult]) -> Dict[str, List[OCRResult]]:
        """
        Group results by document type and month

        Args:
            results: List of OCR results

        Returns:
            Dictionary of grouped results
        """
        grouped = {}

        for result in results:
            # Extract date from result
            date = result.extracted_data.get("date")
            if date and isinstance(date, datetime):
                month_key = date.strftime("%Y-%m")
            else:
                month_key = "unknown"

            # Create group key
            group_key = f"{result.document_type.value}_{month_key}"

            if group_key not in grouped:
                grouped[group_key] = []

            grouped[group_key].append(result)

        return grouped

    def _generate_batch_suggestions(
        self, grouped_results: Dict[str, List[OCRResult]]
    ) -> List[str]:
        """
        Generate suggestions for batch processing

        Args:
            grouped_results: Grouped OCR results

        Returns:
            List of suggestions
        """
        suggestions = []

        # Analyze groups
        for group_key, group_results in grouped_results.items():
            doc_type, month = group_key.split("_", 1)

            if doc_type == "receipt" and len(group_results) > 5:
                suggestions.append(
                    f"Found {len(group_results)} receipts in {month}. "
                    "Consider creating a summary transaction for this month."
                )

            # Check for low confidence results
            low_confidence_count = sum(
                1 for r in group_results if r.confidence_score < 0.6
            )
            if low_confidence_count > 0:
                suggestions.append(
                    f"{low_confidence_count} documents in {group_key} need manual review."
                )

        return suggestions

    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats"""
        return self.config.SUPPORTED_FORMATS

    def validate_file_size(self, file_size_bytes: int) -> bool:
        """
        Validate file size

        Args:
            file_size_bytes: File size in bytes

        Returns:
            True if valid, False otherwise
        """
        max_size_bytes = self.config.MAX_FILE_SIZE_MB * 1024 * 1024
        return file_size_bytes <= max_size_bytes

    def get_processing_stats(self, result: OCRResult) -> Dict[str, Any]:
        """
        Get processing statistics

        Args:
            result: OCR result

        Returns:
            Dictionary of statistics
        """
        return {
            "document_type": result.document_type.value,
            "confidence_score": result.confidence_score,
            "needs_review": result.needs_review,
            "processing_time_ms": result.processing_time_ms,
            "fields_extracted": len(result.extracted_data),
            "text_length": len(result.raw_text),
        }
