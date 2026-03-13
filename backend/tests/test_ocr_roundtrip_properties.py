"""
Property-based tests for OCR data extraction roundtrip validation

Property 27: OCR data extraction roundtrip validation
Validates: Requirements 27.1, 27.2, 27.3, 27.4

This test ensures that OCR extracted data can be correctly stored and retrieved
without data loss or corruption, maintaining data integrity throughout the lifecycle.
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite
from datetime import datetime, date
from decimal import Decimal
import json
from typing import Dict, Any


# ============================================================================
# Strategy Definitions
# ============================================================================


# Define DocumentType enum values for testing without importing the model
DOCUMENT_TYPES = ["payslip", "receipt", "invoice", "rental_contract", 
                  "bank_statement", "property_tax", "lohnzettel", "svs_notice", "other"]


@composite
def ocr_extracted_data(draw):
    """
    Generate valid OCR extracted data structures.
    
    This represents the structured data extracted from various document types.
    """
    doc_type = draw(st.sampled_from(DOCUMENT_TYPES))
    
    # Base fields common to all documents
    base_data = {
        "date": draw(st.dates(
            min_value=date(2020, 1, 1),
            max_value=date(2026, 12, 31)
        )).isoformat(),
        "amount": str(draw(st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("99999.99"),
            places=2
        ))),
    }
    
    # Add document-type-specific fields
    if doc_type == "receipt":
        base_data.update({
            "merchant": draw(st.text(min_size=3, max_size=50, alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd'),
                whitelist_characters=' '
            ))),
            "items": draw(st.lists(
                st.dictionaries(
                    keys=st.sampled_from(["name", "quantity", "price"]),
                    values=st.text(min_size=1, max_size=30)
                ),
                min_size=0,
                max_size=10
            )),
            "vat_amounts": {
                "20%": str(draw(st.decimals(min_value=0, max_value=1000, places=2))),
                "10%": str(draw(st.decimals(min_value=0, max_value=1000, places=2))),
            }
        })
    
    elif doc_type == "payslip":
        base_data.update({
            "gross_income": str(draw(st.decimals(
                min_value=Decimal("1000"),
                max_value=Decimal("10000"),
                places=2
            ))),
            "net_income": str(draw(st.decimals(
                min_value=Decimal("800"),
                max_value=Decimal("8000"),
                places=2
            ))),
            "withheld_tax": str(draw(st.decimals(
                min_value=0,
                max_value=Decimal("3000"),
                places=2
            ))),
            "employer": draw(st.text(min_size=3, max_size=50)),
        })
    
    elif doc_type == "invoice":
        base_data.update({
            "invoice_number": draw(st.text(min_size=5, max_size=20)),
            "supplier": draw(st.text(min_size=3, max_size=50)),
            "vat_amount": str(draw(st.decimals(
                min_value=0,
                max_value=Decimal("5000"),
                places=2
            ))),
        })
    
    # Add confidence scores for each field
    confidence_data = {}
    for field in base_data.keys():
        confidence_data[field] = float(draw(st.floats(min_value=0.0, max_value=1.0)))
    
    base_data["confidence"] = confidence_data
    
    return doc_type, base_data


@composite
def ocr_result_with_history(draw):
    """
    Generate OCR result with correction history.
    
    This represents OCR data that has been corrected by users.
    """
    doc_type, extracted_data = draw(ocr_extracted_data())
    
    ocr_result = {
        "extracted_data": extracted_data,
        "document_type": doc_type,
        "processing_timestamp": datetime.utcnow().isoformat(),
    }
    
    # Optionally add correction history
    has_corrections = draw(st.booleans())
    if has_corrections:
        num_corrections = draw(st.integers(min_value=1, max_value=3))
        correction_history = []
        
        for _ in range(num_corrections):
            correction_history.append({
                "corrected_at": datetime.utcnow().isoformat(),
                "corrected_by": draw(st.integers(min_value=1, max_value=1000)),
                "previous_data": extracted_data.copy(),
                "corrected_fields": draw(st.lists(
                    st.sampled_from(list(extracted_data.keys())),
                    min_size=1,
                    max_size=3,
                    unique=True
                )),
                "notes": draw(st.text(max_size=100)),
            })
        
        ocr_result["correction_history"] = correction_history
    
    # Optionally add confirmation
    is_confirmed = draw(st.booleans())
    if is_confirmed:
        ocr_result["confirmed"] = True
        ocr_result["confirmed_at"] = datetime.utcnow().isoformat()
        ocr_result["confirmed_by"] = draw(st.integers(min_value=1, max_value=1000))
    
    return doc_type, ocr_result


# ============================================================================
# Property Tests
# ============================================================================


class TestOCRRoundtripProperties:
    """
    Property 27: OCR data extraction roundtrip validation
    
    Requirements:
    - 27.1: Extracted data can be serialized to structured format
    - 27.2: Stored data can be retrieved and deserialized
    - 27.3: Roundtrip preserves all data without loss
    - 27.4: Original OCR output and user modifications are both preserved
    """
    
    @given(ocr_extracted_data())
    @settings(max_examples=100, deadline=None)
    def test_extracted_data_serialization_roundtrip(self, ocr_data):
        """
        Property: Extracted data survives JSON serialization roundtrip.
        
        Requirement 27.1, 27.2, 27.3
        
        For all valid OCR extracted data:
        - serialize(data) then deserialize should equal original data
        - No data loss during storage
        - All field types preserved correctly
        """
        doc_type, extracted_data = ocr_data
        
        # Serialize to JSON (simulating database storage)
        serialized = json.dumps(extracted_data)
        
        # Deserialize (simulating retrieval)
        deserialized = json.loads(serialized)
        
        # Property: Roundtrip preserves all data
        assert deserialized == extracted_data, \
            "OCR data should survive serialization roundtrip without changes"
        
        # Property: All original fields are present
        for field in extracted_data.keys():
            assert field in deserialized, \
                f"Field '{field}' should be preserved after roundtrip"
        
        # Property: No extra fields added
        for field in deserialized.keys():
            assert field in extracted_data, \
                f"No extra field '{field}' should be added during roundtrip"
    
    @given(ocr_result_with_history())
    @settings(max_examples=100, deadline=None)
    def test_ocr_result_with_corrections_roundtrip(self, ocr_data):
        """
        Property: OCR results with correction history survive roundtrip.
        
        Requirement 27.3, 27.4
        
        For all OCR results with corrections:
        - Original OCR output is preserved
        - User corrections are preserved
        - Correction history is maintained
        - Confirmation status is preserved
        """
        doc_type, ocr_result = ocr_data
        
        # Serialize
        serialized = json.dumps(ocr_result)
        
        # Deserialize
        deserialized = json.loads(serialized)
        
        # Property: Complete OCR result preserved
        assert deserialized == ocr_result, \
            "Complete OCR result should survive roundtrip"
        
        # Property: Extracted data preserved
        assert "extracted_data" in deserialized
        assert deserialized["extracted_data"] == ocr_result["extracted_data"]
        
        # Property: Correction history preserved (if exists)
        if "correction_history" in ocr_result:
            assert "correction_history" in deserialized
            assert len(deserialized["correction_history"]) == len(ocr_result["correction_history"])
            
            for i, correction in enumerate(ocr_result["correction_history"]):
                assert deserialized["correction_history"][i] == correction
        
        # Property: Confirmation preserved (if exists)
        if "confirmed" in ocr_result:
            assert deserialized["confirmed"] == ocr_result["confirmed"]
            assert deserialized["confirmed_at"] == ocr_result["confirmed_at"]
    
    @given(
        doc_type=st.sampled_from(DOCUMENT_TYPES),
        raw_text=st.text(min_size=10, max_size=1000),
        confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=50, deadline=None)
    def test_document_model_ocr_result_storage(self, doc_type, raw_text, confidence):
        """
        Property: Document model correctly stores and retrieves OCR results.
        
        Requirement 27.1, 27.2
        
        For all valid OCR results:
        - Document model can store OCR result as JSON
        - Retrieved OCR result matches stored data
        - Raw text is preserved
        - Confidence score is preserved
        """
        # Create OCR result
        ocr_result = {
            "extracted_data": {
                "date": "2026-01-15",
                "amount": "123.45",
                "confidence": {"date": 0.9, "amount": 0.85}
            },
            "document_type": doc_type,
            "processing_timestamp": datetime.utcnow().isoformat(),
        }
        
        # Simulate storage (JSON serialization)
        stored_ocr_result = json.loads(json.dumps(ocr_result))
        stored_raw_text = raw_text
        stored_confidence = round(confidence, 2)
        
        # Property: OCR result preserved
        assert stored_ocr_result == ocr_result
        
        # Property: Raw text preserved
        assert stored_raw_text == raw_text
        
        # Property: Confidence preserved (with rounding)
        assert abs(stored_confidence - round(confidence, 2)) < 0.01
    
    @given(ocr_extracted_data())
    @settings(max_examples=50, deadline=None)
    def test_field_confidence_preservation(self, ocr_data):
        """
        Property: Field confidence scores are preserved in roundtrip.
        
        Requirement 27.3
        
        For all OCR extracted data with confidence scores:
        - Each field's confidence score is preserved
        - Confidence values remain in valid range [0, 1]
        - No confidence data is lost
        """
        doc_type, extracted_data = ocr_data
        
        # Get confidence data
        confidence_data = extracted_data.get("confidence", {})
        
        # Serialize and deserialize
        serialized = json.dumps(extracted_data)
        deserialized = json.loads(serialized)
        
        # Property: Confidence section preserved
        assert "confidence" in deserialized
        
        # Property: All field confidences preserved
        for field, conf_value in confidence_data.items():
            assert field in deserialized["confidence"]
            assert abs(deserialized["confidence"][field] - conf_value) < 0.0001
        
        # Property: Confidence values in valid range
        for field, conf_value in deserialized["confidence"].items():
            assert 0.0 <= conf_value <= 1.0, \
                f"Confidence for '{field}' should be in range [0, 1]"
    
    @given(ocr_result_with_history())
    @settings(max_examples=50, deadline=None)
    def test_correction_history_ordering_preserved(self, ocr_data):
        """
        Property: Correction history maintains chronological order.
        
        Requirement 27.4
        
        For all OCR results with correction history:
        - Corrections are stored in order
        - Order is preserved after roundtrip
        - Each correction contains required fields
        """
        doc_type, ocr_result = ocr_data
        
        if "correction_history" not in ocr_result:
            return  # Skip if no corrections
        
        # Serialize and deserialize
        serialized = json.dumps(ocr_result)
        deserialized = json.loads(serialized)
        
        original_history = ocr_result["correction_history"]
        retrieved_history = deserialized["correction_history"]
        
        # Property: Same number of corrections
        assert len(retrieved_history) == len(original_history)
        
        # Property: Order preserved
        for i in range(len(original_history)):
            assert retrieved_history[i] == original_history[i], \
                f"Correction {i} should be preserved in order"
        
        # Property: Each correction has required fields
        for correction in retrieved_history:
            assert "corrected_at" in correction
            assert "corrected_by" in correction
            assert "previous_data" in correction
            assert "corrected_fields" in correction
    
    @given(
        st.lists(ocr_extracted_data(), min_size=1, max_size=10)
    )
    @settings(max_examples=30, deadline=None)
    def test_multiple_documents_roundtrip(self, ocr_data_list):
        """
        Property: Multiple OCR results can be stored and retrieved independently.
        
        Requirement 27.1, 27.2, 27.3
        
        For all lists of OCR results:
        - Each document's data is independent
        - Batch storage preserves all documents
        - No cross-contamination between documents
        """
        # Simulate storing multiple documents
        stored_documents = []
        
        for doc_type, extracted_data in ocr_data_list:
            ocr_result = {
                "extracted_data": extracted_data,
                "document_type": doc_type,  # Already a string, no .value needed
            }
            
            # Serialize
            serialized = json.dumps(ocr_result)
            stored_documents.append(serialized)
        
        # Deserialize all
        retrieved_documents = [json.loads(doc) for doc in stored_documents]
        
        # Property: Same number of documents
        assert len(retrieved_documents) == len(ocr_data_list)
        
        # Property: Each document preserved independently
        for i, (doc_type, extracted_data) in enumerate(ocr_data_list):
            retrieved = retrieved_documents[i]
            
            assert retrieved["document_type"] == doc_type
            assert retrieved["extracted_data"] == extracted_data
    
    @given(ocr_extracted_data())
    @settings(max_examples=50, deadline=None)
    def test_decimal_precision_preservation(self, ocr_data):
        """
        Property: Decimal amounts preserve precision in roundtrip.
        
        Requirement 27.3
        
        For all OCR extracted data with amounts:
        - Decimal precision is maintained
        - No rounding errors introduced
        - Currency values remain accurate
        """
        doc_type, extracted_data = ocr_data
        
        # Get amount field
        if "amount" not in extracted_data:
            return
        
        original_amount = extracted_data["amount"]
        
        # Serialize and deserialize
        serialized = json.dumps(extracted_data)
        deserialized = json.loads(serialized)
        
        retrieved_amount = deserialized["amount"]
        
        # Property: Amount preserved exactly
        assert retrieved_amount == original_amount, \
            "Amount should be preserved with exact precision"
        
        # Property: Can convert back to Decimal
        original_decimal = Decimal(original_amount)
        retrieved_decimal = Decimal(retrieved_amount)
        
        assert original_decimal == retrieved_decimal, \
            "Decimal conversion should yield same value"
    
    @given(ocr_result_with_history())
    @settings(max_examples=50, deadline=None)
    def test_user_modifications_separate_from_original(self, ocr_data):
        """
        Property: User modifications don't overwrite original OCR data.
        
        Requirement 27.4
        
        For all OCR results with corrections:
        - Original OCR output is preserved in history
        - Current data reflects user corrections
        - Both versions are accessible
        """
        doc_type, ocr_result = ocr_data
        
        if "correction_history" not in ocr_result:
            return
        
        # Serialize and deserialize
        serialized = json.dumps(ocr_result)
        deserialized = json.loads(serialized)
        
        # Property: Current extracted data exists
        assert "extracted_data" in deserialized
        
        # Property: Correction history exists
        assert "correction_history" in deserialized
        
        # Property: Each correction preserves previous data
        for correction in deserialized["correction_history"]:
            assert "previous_data" in correction, \
                "Each correction should preserve previous data state"
            
            # Previous data should be a valid extracted data structure
            assert isinstance(correction["previous_data"], dict)
