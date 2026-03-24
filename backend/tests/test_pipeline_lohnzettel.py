"""Tests for L16 Lohnzettel pipeline: OCR routing → extraction → validation → suggestion."""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator,
    PipelineResult,
    ValidationResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestL16PipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_l16_extractor_extracts_kz(self):
        from app.services.l16_extractor import L16Extractor
        result = L16Extractor().extract("Lohnzettel Kalenderjahr: 2025\nKZ 245: 42.500,00\nKZ 260: 8.750,00")
        assert result.kz_245 == Decimal("42500.00")
        assert result.tax_year == 2025


class TestL16PipelineValidation:
    def test_validate_with_key_fields(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        result = PipelineResult(document_id=1)
        validation = orch._stage_validate(DBDocumentType.LOHNZETTEL, {"tax_year": 2025, "kz_245": 42500.0}, result)
        assert isinstance(validation, ValidationResult)

    def test_validate_empty_data_fails(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        result = PipelineResult(document_id=1)
        validation = orch._stage_validate(DBDocumentType.LOHNZETTEL, {}, result)
        assert not validation.is_valid


class TestL16PipelineSuggestion:
    def test_type_map(self):
        assert DBDocumentType.LOHNZETTEL in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.LOHNZETTEL] == "import_lohnzettel"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=1, ocr_result={
            "extracted_data": {"tax_year": 2025, "kz_245": 42500.0, "kz_260": 8750.0},
            "confidence_score": 0.92,
        })
        result = PipelineResult(document_id=1)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.LOHNZETTEL, result)
        assert suggestion is not None
        assert suggestion["type"] == "import_lohnzettel"
        assert suggestion["status"] == "pending"
        assert suggestion["data"]["kz_245"] == 42500.0
