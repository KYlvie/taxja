"""Tests for E1b Beilage pipeline: routing → extraction → suggestion."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestE1bPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_e1b_extractor_importable(self):
        from app.services.e1b_extractor import E1bExtractor
        assert E1bExtractor() is not None


class TestE1bPipelineSuggestion:
    def test_e1b_in_tax_form_types(self):
        assert DBDocumentType.E1B_BEILAGE in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.E1B_BEILAGE] == "import_e1b"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=6, ocr_result={
            "extracted_data": {"tax_year": 2025, "total_income": 12000.0},
            "confidence_score": 0.85,
        })
        result = PipelineResult(document_id=6)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.E1B_BEILAGE, result)
        assert suggestion["type"] == "import_e1b"
