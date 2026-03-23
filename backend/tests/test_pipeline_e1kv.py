"""Tests for E1kv Beilage pipeline: routing → extraction → suggestion."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestE1kvPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_e1kv_extractor_importable(self):
        from app.services.e1kv_extractor import E1kvExtractor
        assert E1kvExtractor() is not None


class TestE1kvPipelineSuggestion:
    def test_e1kv_in_tax_form_types(self):
        assert DBDocumentType.E1KV_BEILAGE in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.E1KV_BEILAGE] == "import_e1kv"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=7, ocr_result={
            "extracted_data": {"tax_year": 2025, "total_capital_gains": 5000.0},
            "confidence_score": 0.87,
        })
        result = PipelineResult(document_id=7)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.E1KV_BEILAGE, result)
        assert suggestion["type"] == "import_e1kv"
