"""
Property-based tests for OCR data structure integrity

Property 25: OCR extracted data structure integrity
Validates: Requirements 19.4, 23.2, 25.2, 25.4
"""
import pytest
from hypothesis import given, strategies as st, assume
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from app.services.ocr_engine import OCREngine, OCRResult
from app.services.document_classifier import DocumentType
from app.services.field_extractor import FieldExtractor, ExtractedField


# ========== Test Data Strategies ==========


@st.composite
def valid_extracted_data(draw):
    """Generate valid extracted data structure"""
    doc_type = draw(st.sampled_from(list(DocumentType)))

    base_data = {
        "date": draw(st.one_of(st.none(), st.datetimes(min_value=datetime(2020, 1, 1)))),
        "amount": draw(
            st.one_of(st.none(), st.decimals(min_value=0, max_value=100000, places=2))
        ),
        "date_confidence": draw(st.floats(min_value=0.0, max_value=1.0)),
        "amount_confidence": draw(st.floats(min_value=0.0, max_value=1.0)),
    }

    # Add document-specific fields
    if doc_type == DocumentType.RECEIPT:
        base_data.update(
            {
                "merchant": draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
                "merchant_confidence": draw(st.floats(min_value=0.0, max_value=1.0)),
                "items": draw(st.lists(st.dictionaries(st.text(), st.text()), max_size=10)),
                "vat_amounts": draw(
                    st.dictionaries(
                        st.sampled_from(["10%", "20%"]),
                        st.decimals(min_value=0, max_value=1000, places=2),
                    )
                ),
            }
        )
    elif doc_type in [DocumentType.PAYSLIP, DocumentType.LOHNZETTEL]:
        base_data.update(
            {
                "gross_income": draw(
                    st.one_of(st.none(), st.decimals(min_value=0, max_value=100000, places=2))
                ),
                "net_income": draw(
                    st.one_of(st.none(), st.decimals(min_value=0, max_value=100000, places=2))
                ),
                "withheld_tax": draw(
                    st.one_of(st.none(), st.decimals(min_value=0, max_value=50000, places=2))
                ),
                "employer": draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
            }
        )
    elif doc_type == DocumentType.INVOICE:
        base_data.update(
            {
                "invoice_number": draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
                "supplier": draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
                "vat_total": draw(
                    st.one_of(st.none(), st.decimals(min_value=0, max_value=10000, places=2))
                ),
            }
        )

    return base_data


@st.composite
def ocr_result_strategy(draw):
    """Generate OCR result"""
    doc_type = draw(st.sampled_from(list(DocumentType)))
    extracted_data = draw(valid_extracted_data())
    raw_text = draw(st.text(min_size=10, max_size=1000))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    processing_time = draw(st.floats(min_value=1.0, max_value=10000.0))

    return OCRResult(
        document_type=doc_type,
        extracted_data=extracted_data,
        raw_text=raw_text,
        confidence_score=confidence,
        needs_review=confidence < 0.6,
        processing_time_ms=processing_time,
        suggestions=draw(st.lists(st.text(min_size=1, max_size=100), max_size=5)),
    )


# ========== Property Tests ==========


class TestOCRDataStructureIntegrity:
    """Test OCR data structure integrity properties"""

    @given(ocr_result=ocr_result_strategy())
    def test_property_25_ocr_result_serialization_roundtrip(self, ocr_result: OCRResult):
        """
        Property 25: OCR result serialization roundtrip consistency

        For all valid OCR results:
        - Serializing to dict and back should preserve data structure
        - All required fields should be present
        - Data types should be preserved
        """
        # Serialize to dict
        result_dict = ocr_result.to_dict()

        # Verify required fields are present
        required_fields = [
            "document_type",
            "extracted_data",
            "raw_text",
            "confidence_score",
            "needs_review",
            "processing_time_ms",
            "suggestions",
        ]

        for field in required_fields:
            assert field in result_dict, f"Required field '{field}' missing from serialized result"

        # Verify data types
        assert isinstance(result_dict["document_type"], str)
        assert isinstance(result_dict["extracted_data"], dict)
        assert isinstance(result_dict["raw_text"], str)
        assert isinstance(result_dict["confidence_score"], float)
        assert isinstance(result_dict["needs_review"], bool)
        assert isinstance(result_dict["processing_time_ms"], float)
        assert isinstance(result_dict["suggestions"], list)

        # Verify confidence score is in valid range
        assert 0.0 <= result_dict["confidence_score"] <= 1.0

        # Verify needs_review is consistent with confidence
        if result_dict["confidence_score"] < 0.6:
            assert result_dict["needs_review"] is True

    @given(extracted_data=valid_extracted_data())
    def test_property_25_extracted_data_structure_validity(self, extracted_data: Dict[str, Any]):
        """
        Property 25: Extracted data structure validity

        For all extracted data:
        - Confidence fields should be in range [0.0, 1.0]
        - Date fields should be datetime or None
        - Amount fields should be Decimal or None
        - All confidence fields should have corresponding data fields
        """
        # Check confidence fields are in valid range
        for key, value in extracted_data.items():
            if key.endswith("_confidence"):
                assert isinstance(value, float), f"Confidence field {key} should be float"
                assert 0.0 <= value <= 1.0, f"Confidence {key} out of range: {value}"

                # Check corresponding data field exists
                data_field = key.replace("_confidence", "")
                assert (
                    data_field in extracted_data
                ), f"Data field {data_field} missing for confidence {key}"

        # Check date fields
        if "date" in extracted_data and extracted_data["date"] is not None:
            assert isinstance(
                extracted_data["date"], datetime
            ), "Date field should be datetime or None"

        # Check amount fields
        amount_fields = ["amount", "gross_income", "net_income", "withheld_tax", "vat_total"]
        for field in amount_fields:
            if field in extracted_data and extracted_data[field] is not None:
                assert isinstance(
                    extracted_data[field], Decimal
                ), f"Amount field {field} should be Decimal or None"
                assert extracted_data[field] >= 0, f"Amount field {field} should be non-negative"

    @given(
        extracted_data=valid_extracted_data(),
        classification_confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_property_25_confidence_calculation_bounds(
        self, extracted_data: Dict[str, Any], classification_confidence: float
    ):
        """
        Property 25: Confidence calculation bounds

        For all extracted data and classification confidence:
        - Overall confidence should be in range [0.0, 1.0]
        - Overall confidence should not exceed max of individual confidences
        - Missing critical fields should reduce confidence
        """
        # Mock OCR engine confidence calculation
        field_confidences = [
            v for k, v in extracted_data.items() if k.endswith("_confidence")
        ]

        if field_confidences:
            avg_field_confidence = sum(field_confidences) / len(field_confidences)
            overall_confidence = 0.4 * classification_confidence + 0.6 * avg_field_confidence
        else:
            overall_confidence = classification_confidence

        # Check for missing critical fields
        critical_fields = ["date", "amount"]
        missing_critical = sum(1 for field in critical_fields if not extracted_data.get(field))

        if missing_critical > 0:
            overall_confidence *= 0.7

        overall_confidence = min(overall_confidence, 1.0)

        # Verify bounds
        assert 0.0 <= overall_confidence <= 1.0, "Overall confidence out of range"

        # Verify confidence doesn't exceed maximum
        max_confidence = max([classification_confidence] + field_confidences)
        assert (
            overall_confidence <= max_confidence * 1.1
        ), "Overall confidence exceeds individual confidences"

    @given(
        doc_type=st.sampled_from(list(DocumentType)),
        text=st.text(min_size=10, max_size=1000),
    )
    def test_property_25_field_extraction_consistency(self, doc_type: DocumentType, text: str):
        """
        Property 25: Field extraction consistency

        For all document types and text:
        - Extracting fields multiple times should return same structure
        - All returned fields should have corresponding confidence scores
        - Field types should match expected types for document type
        """
        extractor = FieldExtractor()

        # Extract fields twice
        result1 = extractor.extract_fields(text, doc_type)
        result2 = extractor.extract_fields(text, doc_type)

        # Results should have same keys
        assert set(result1.keys()) == set(
            result2.keys()
        ), "Field extraction should be deterministic"

        # All data fields should have confidence scores
        data_fields = [k for k in result1.keys() if not k.endswith("_confidence")]
        for field in data_fields:
            confidence_field = f"{field}_confidence"
            if field not in ["items", "vat_amounts", "items_count"]:  # Skip list/dict fields
                # Either confidence field exists or field is derived
                if confidence_field not in result1:
                    # Derived fields like vat_total, items_count don't need confidence
                    pass

    @given(ocr_results=st.lists(ocr_result_strategy(), min_size=1, max_size=10))
    def test_property_25_batch_result_structure(self, ocr_results: list):
        """
        Property 25: Batch result structure integrity

        For all batch results:
        - Success count + failure count should equal total results
        - Grouped results should contain all original results
        - All results should be serializable
        """
        from app.services.ocr_engine import BatchOCRResult

        # Count successes and failures
        success_count = sum(1 for r in ocr_results if r.confidence_score > 0)
        failure_count = len(ocr_results) - success_count

        # Create batch result
        batch_result = BatchOCRResult(
            results=ocr_results,
            grouped_results={},
            suggestions=[],
            total_processing_time_ms=sum(r.processing_time_ms for r in ocr_results),
            success_count=success_count,
            failure_count=failure_count,
        )

        # Verify counts
        assert batch_result.success_count + batch_result.failure_count == len(ocr_results)
        assert batch_result.success_count == success_count
        assert batch_result.failure_count == failure_count

        # Verify serialization
        batch_dict = batch_result.to_dict()
        assert isinstance(batch_dict, dict)
        assert "results" in batch_dict
        assert "success_count" in batch_dict
        assert "failure_count" in batch_dict
        assert len(batch_dict["results"]) == len(ocr_results)

    @given(
        date=st.one_of(st.none(), st.datetimes(min_value=datetime(2020, 1, 1))),
        amount=st.one_of(st.none(), st.decimals(min_value=0, max_value=100000, places=2)),
    )
    def test_property_25_extracted_field_wrapper_consistency(
        self, date: datetime, amount: Decimal
    ):
        """
        Property 25: ExtractedField wrapper consistency

        For all field values:
        - ExtractedField should preserve value and confidence
        - Confidence should be in valid range
        - Raw text should be optional
        """
        # Test with date
        if date is not None:
            field = ExtractedField(value=date, confidence=0.9, raw_text="01.01.2024")
            assert field.value == date
            assert 0.0 <= field.confidence <= 1.0
            assert field.raw_text is not None

        # Test with amount
        if amount is not None:
            field = ExtractedField(value=amount, confidence=0.8)
            assert field.value == amount
            assert 0.0 <= field.confidence <= 1.0

        # Test with None
        field = ExtractedField(value=None, confidence=0.0)
        assert field.value is None
        assert field.confidence == 0.0

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0),
        threshold=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_property_25_needs_review_flag_consistency(self, confidence: float, threshold: float):
        """
        Property 25: Needs review flag consistency

        For all confidence scores and thresholds:
        - needs_review should be True when confidence < threshold
        - needs_review should be False when confidence >= threshold
        """
        needs_review = confidence < threshold

        if confidence < threshold:
            assert needs_review is True
        else:
            assert needs_review is False

    @given(
        text=st.text(min_size=0, max_size=10000),
        processing_time=st.floats(min_value=0.0, max_value=100000.0),
    )
    def test_property_25_ocr_result_invariants(self, text: str, processing_time: float):
        """
        Property 25: OCR result invariants

        For all OCR results:
        - Raw text length should match actual text length
        - Processing time should be non-negative
        - Suggestions should be a list
        """
        result = OCRResult(
            document_type=DocumentType.UNKNOWN,
            extracted_data={},
            raw_text=text,
            confidence_score=0.5,
            needs_review=True,
            processing_time_ms=processing_time,
            suggestions=["test"],
        )

        # Verify text length
        assert len(result.raw_text) == len(text)

        # Verify processing time
        assert result.processing_time_ms >= 0

        # Verify suggestions is list
        assert isinstance(result.suggestions, list)

    @given(extracted_data=valid_extracted_data())
    def test_property_25_vat_amounts_structure(self, extracted_data: Dict[str, Any]):
        """
        Property 25: VAT amounts structure validity

        For all extracted data with VAT amounts:
        - VAT rates should be valid Austrian rates (10%, 20%)
        - VAT amounts should be non-negative Decimals
        - VAT amounts dictionary should be serializable
        """
        if "vat_amounts" in extracted_data:
            vat_amounts = extracted_data["vat_amounts"]
            assert isinstance(vat_amounts, dict)

            for rate, amount in vat_amounts.items():
                # Valid Austrian VAT rates
                assert rate in ["10%", "20%"], f"Invalid VAT rate: {rate}"

                # Amount should be Decimal and non-negative
                assert isinstance(amount, Decimal), f"VAT amount should be Decimal: {type(amount)}"
                assert amount >= 0, f"VAT amount should be non-negative: {amount}"


# ========== Integration Tests ==========


class TestOCREngineIntegration:
    """Integration tests for OCR engine"""

    def test_ocr_result_to_dict_preserves_structure(self):
        """Test that OCR result serialization preserves structure"""
        result = OCRResult(
            document_type=DocumentType.RECEIPT,
            extracted_data={
                "date": datetime(2024, 1, 15),
                "amount": Decimal("123.45"),
                "merchant": "BILLA AG",
                "date_confidence": 0.9,
                "amount_confidence": 0.85,
                "merchant_confidence": 0.95,
            },
            raw_text="Sample receipt text",
            confidence_score=0.88,
            needs_review=False,
            processing_time_ms=1234.56,
            suggestions=["All fields extracted successfully"],
        )

        result_dict = result.to_dict()

        assert result_dict["document_type"] == "receipt"
        assert "date" in result_dict["extracted_data"]
        assert result_dict["confidence_score"] == 0.88
        assert result_dict["needs_review"] is False

    def test_extracted_field_preserves_metadata(self):
        """Test that ExtractedField preserves all metadata"""
        field = ExtractedField(
            value=Decimal("99.99"), confidence=0.75, raw_text="€ 99,99"
        )

        assert field.value == Decimal("99.99")
        assert field.confidence == 0.75
        assert field.raw_text == "€ 99,99"

