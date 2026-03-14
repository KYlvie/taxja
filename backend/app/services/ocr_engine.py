"""Main OCR processing engine"""
import logging
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

        # Set Tesseract command path
        pytesseract.pytesseract.tesseract_cmd = self.config.get_tesseract_cmd()

    def process_document(self, image_bytes: bytes, mime_type: str = None) -> OCRResult:
        """
        Process a single document image or PDF

        Args:
            image_bytes: Image/PDF file as bytes
            mime_type: Optional MIME type hint (e.g. image/jpeg, image/png)

        Returns:
            OCRResult with extracted data
        """
        start_time = datetime.now()

        try:
            # Check if PDF and try direct text extraction first (much faster)
            if image_bytes[:5] == b"%PDF-":
                pdf_text = self._extract_text_from_pdf(image_bytes)
                if pdf_text and len(pdf_text.strip()) > 20:
                    # PDF has a text layer — skip Tesseract entirely
                    raw_text = pdf_text.strip()

                    # Classify document type
                    doc_type, classification_confidence = self.classifier.classify(
                        None, raw_text
                    )

                    # For specialized document types, use regex extractors FIRST
                    # (much faster and more reliable than LLM on CPU)
                    if doc_type in (DocumentType.KAUFVERTRAG, DocumentType.MIETVERTRAG, DocumentType.RENTAL_CONTRACT):
                        extraction_type = DocumentType.MIETVERTRAG if doc_type == DocumentType.RENTAL_CONTRACT else doc_type
                        return self._route_to_contract_extractor(
                            extraction_type, raw_text, image_bytes, start_time
                        )
                    elif doc_type == DocumentType.EINKOMMENSTEUERBESCHEID:
                        return self._route_to_bescheid_extractor(
                            raw_text, start_time
                        )
                    elif doc_type == DocumentType.E1_FORM:
                        return self._route_to_e1_extractor(
                            raw_text, start_time
                        )

                    # For generic documents (invoices, receipts, etc.), try LLM
                    llm_result = self._try_llm_extraction(
                        raw_text, doc_type, start_time
                    )
                    if llm_result is not None:
                        return llm_result

                    # Extract fields using regex
                    extracted_data = self.extractor.extract_fields(raw_text, doc_type)

                    # Calculate confidence
                    overall_confidence = self._calculate_confidence(
                        extracted_data, classification_confidence
                    )

                    # If regex gave low confidence, retry with LLM as fallback
                    if overall_confidence < 0.5 and self.llm_extractor.is_available:
                        logger.info(
                            "Regex confidence %.2f is low, retrying with LLM",
                            overall_confidence,
                        )
                        llm_retry = self._try_llm_extraction(
                            raw_text, doc_type, start_time
                        )
                        if llm_retry is not None:
                            return llm_retry

                    needs_review = overall_confidence < self.config.CONFIDENCE_THRESHOLD
                    processing_time = (datetime.now() - start_time).total_seconds() * 1000

                    return OCRResult(
                        document_type=doc_type,
                        extracted_data=extracted_data,
                        raw_text=raw_text,
                        confidence_score=overall_confidence,
                        needs_review=needs_review,
                        processing_time_ms=processing_time,
                        suggestions=[],
                    )

            # 1. Load and preprocess image (falls back to Tesseract OCR)
            # For multi-page scanned PDFs, OCR all pages
            if image_bytes[:5] == b"%PDF-":
                raw_text = self._ocr_all_pdf_pages(image_bytes)
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

            # 3. Classify document type
            doc_type, classification_confidence = self.classifier.classify(
                None, raw_text
            )

            # Route to specialized regex extractors FIRST for known types
            # (much faster and more reliable than LLM on CPU)
            if doc_type in (DocumentType.KAUFVERTRAG, DocumentType.MIETVERTRAG, DocumentType.RENTAL_CONTRACT):
                extraction_type = DocumentType.MIETVERTRAG if doc_type == DocumentType.RENTAL_CONTRACT else doc_type
                return self._route_to_contract_extractor(
                    extraction_type, raw_text, image_bytes, start_time
                )
            elif doc_type == DocumentType.EINKOMMENSTEUERBESCHEID:
                return self._route_to_bescheid_extractor(
                    raw_text, start_time
                )
            elif doc_type == DocumentType.E1_FORM:
                return self._route_to_e1_extractor(
                    raw_text, start_time
                )

            # For generic documents, try LLM extraction
            llm_result = self._try_llm_extraction(
                raw_text, doc_type, start_time
            )
            if llm_result is not None:
                return llm_result

            # 4. Extract fields based on document type
            extracted_data = self.extractor.extract_fields(raw_text, doc_type)

            # 5. Calculate overall confidence score
            overall_confidence = self._calculate_confidence(
                extracted_data, classification_confidence
            )

            # If regex gave low confidence, retry with LLM as fallback
            if overall_confidence < 0.5 and self.llm_extractor.is_available:
                logger.info(
                    "Regex confidence %.2f is low, retrying with LLM",
                    overall_confidence,
                )
                llm_retry = self._try_llm_extraction(
                    raw_text, doc_type, start_time
                )
                if llm_retry is not None:
                    return llm_retry

            # 6. Generate suggestions
            suggestions = self._generate_suggestions(
                None, extracted_data, overall_confidence
            )

            # 7. Determine if review is needed
            needs_review = overall_confidence < self.config.CONFIDENCE_THRESHOLD

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return OCRResult(
                document_type=doc_type,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=overall_confidence,
                needs_review=needs_review,
                processing_time_ms=processing_time,
                suggestions=suggestions,
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
    def _try_vlm_ocr(
        self, image_bytes: bytes, mime_type: str, start_time: datetime
    ) -> Optional[OCRResult]:
        """
        Use a Vision-Language Model to OCR an image directly.
        Sends the image as base64 to the VL model and gets back structured data.
        Returns OCRResult or None if VLM unavailable/failed.
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
            "IMPORTANT: If the image contains MULTIPLE receipts/invoices, return a JSON array "
            "with one object per receipt. If only one receipt, return a single JSON object.\n"
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
                user_prompt="Extract all data from this document. If multiple receipts are visible, extract each one separately.",
                image_bytes=image_bytes,
                mime_type=mime_type,
                temperature=0.1,
                max_tokens=3500,
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
                    # Store all receipts in extracted_data for downstream processing
                    logger.info("VLM detected %d receipts in single image", len(data))
                    all_receipts = []
                    total_amount = 0
                    for i, receipt in enumerate(data):
                        cleaned = {k: v for k, v in receipt.items() if v is not None}
                        cleaned.pop("raw_text", None)
                        cleaned.pop("document_type", None)
                        if "amount" in cleaned:
                            try:
                                total_amount += float(cleaned["amount"])
                            except (ValueError, TypeError):
                                pass
                        all_receipts.append(cleaned)

                    processing_time = (datetime.now() - start_time).total_seconds() * 1000
                    return OCRResult(
                        document_type=DocumentType.RECEIPT,
                        extracted_data={
                            "multiple_receipts": all_receipts,
                            "receipt_count": len(all_receipts),
                            "total_amount": round(total_amount, 2),
                        },
                        raw_text=response,
                        confidence_score=0.85,
                        needs_review=True,
                        processing_time_ms=processing_time,
                        suggestions=[
                            f"Detected {len(all_receipts)} receipts in one image. "
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

            # Remove null values
            extracted_data = {k: v for k, v in data.items() if v is not None}

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
            llm_data = self.llm_extractor.extract(raw_text, doc_type)
            if not llm_data:
                return None

            # Remove null values
            extracted_data = {k: v for k, v in llm_data.items() if v is not None}

            if not extracted_data:
                return None

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

    def _route_to_contract_extractor(
        self, doc_type: DocumentType, raw_text: str, image_bytes: bytes, start_time: datetime
    ) -> OCRResult:
        """
        Route Kaufvertrag and Mietvertrag documents to specialized extractors

        Args:
            doc_type: Detected document type (KAUFVERTRAG or MIETVERTRAG)
            raw_text: Extracted text from OCR
            image_bytes: Original document bytes
            start_time: Processing start time

        Returns:
            OCRResult with specialized extraction data
        """
        try:
            if doc_type == DocumentType.KAUFVERTRAG:
                from app.services.kaufvertrag_ocr_service import KaufvertragOCRService

                service = KaufvertragOCRService()
                result = service.process_kaufvertrag_from_text(raw_text)

                processing_time = (datetime.now() - start_time).total_seconds() * 1000

                # Use the extractor's to_dict method
                extracted_data = service.extractor.to_dict(result.kaufvertrag_data)

                return OCRResult(
                    document_type=doc_type,
                    extracted_data=extracted_data,
                    raw_text=raw_text,
                    confidence_score=result.overall_confidence,
                    needs_review=result.overall_confidence < self.config.CONFIDENCE_THRESHOLD,
                    processing_time_ms=processing_time,
                    suggestions=self._generate_contract_suggestions(result.overall_confidence),
                )

            elif doc_type == DocumentType.MIETVERTRAG:
                from app.services.mietvertrag_ocr_service import MietvertragOCRService

                service = MietvertragOCRService()
                result = service.process_mietvertrag_from_text(raw_text)

                processing_time = (datetime.now() - start_time).total_seconds() * 1000

                # Use the extractor's to_dict method
                extracted_data = service.extractor.to_dict(result.mietvertrag_data)

                return OCRResult(
                    document_type=doc_type,
                    extracted_data=extracted_data,
                    raw_text=raw_text,
                    confidence_score=result.overall_confidence,
                    needs_review=result.overall_confidence < self.config.CONFIDENCE_THRESHOLD,
                    processing_time_ms=processing_time,
                    suggestions=self._generate_contract_suggestions(result.overall_confidence),
                )

            else:
                raise ValueError(f"Unsupported contract type: {doc_type}")

        except Exception as e:
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

    def _route_to_bescheid_extractor(
        self, raw_text: str, start_time: datetime
    ) -> OCRResult:
        """
        Route Einkommensteuerbescheid to specialized extractor

        Args:
            raw_text: Extracted text from OCR
            start_time: Processing start time

        Returns:
            OCRResult with specialized extraction data
        """
        try:
            from app.services.bescheid_extractor import BescheidExtractor

            extractor = BescheidExtractor()
            data = extractor.extract(raw_text)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            extracted_data = extractor.to_dict(data)

            return OCRResult(
                document_type=DocumentType.EINKOMMENSTEUERBESCHEID,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=data.confidence,
                needs_review=data.confidence < self.config.CONFIDENCE_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=self._generate_tax_document_suggestions(data.confidence),
            )

        except Exception as e:
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
            if data.confidence >= self.config.CONFIDENCE_THRESHOLD:
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
                return OCRResult(
                    document_type=DocumentType.E1_FORM,
                    extracted_data=extracted_data,
                    raw_text=raw_text,
                    confidence_score=boosted,
                    needs_review=boosted < self.config.CONFIDENCE_THRESHOLD,
                    processing_time_ms=processing_time,
                    suggestions=["AI validation used to supplement extraction."],
                )

            # LLM unavailable or didn't help — return regex result as-is
            return OCRResult(
                document_type=DocumentType.E1_FORM,
                extracted_data=extracted_data,
                raw_text=raw_text,
                confidence_score=data.confidence,
                needs_review=data.confidence < self.config.CONFIDENCE_THRESHOLD,
                processing_time_ms=processing_time,
                suggestions=self._generate_tax_document_suggestions(data.confidence),
            )

        except Exception as e:
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
                    text_parts.append(page_text)

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

    def _ocr_all_pdf_pages(self, pdf_bytes: bytes, max_pages: int = 5) -> str:
        """
        OCR all pages of a scanned PDF for better text extraction.

        Renders each page at 300 DPI, preprocesses, and runs Tesseract.
        Concatenates text from all pages.

        Args:
            pdf_bytes: Raw PDF bytes
            max_pages: Maximum number of pages to OCR (default 5)

        Returns:
            Combined OCR text from all pages
        """
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        num_pages = min(len(doc), max_pages)
        all_text = []

        logger.info("OCR scanning %d pages of scanned PDF at 300 DPI", num_pages)

        for i in range(num_pages):
            page = doc[i]
            mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
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
                    all_text.append(page_text.strip())
            except Exception as e:
                logger.warning("Tesseract failed on page %d: %s", i + 1, e)

        doc.close()

        combined = "\n\n".join(all_text)
        logger.info(
            "Multi-page OCR complete: %d pages, %d chars extracted",
            num_pages, len(combined),
        )
        return combined

    def _extract_text(self, image: np.ndarray) -> str:
        """
        Extract text from image using Tesseract

        Args:
            image: Preprocessed image

        Returns:
            Extracted text
        """
        try:
            text = pytesseract.image_to_string(image, config=self.config.TESSERACT_CONFIG)
            return text.strip()
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

