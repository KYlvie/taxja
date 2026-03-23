"""Tests for SVS pipeline: routing → extraction → suggestion."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestSvsPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_svs_extractor_importable(self):
        from app.services.svs_extractor import SvsExtractor
        assert SvsExtractor() is not None


class TestSvsPipelineSuggestion:
    def test_svs_in_tax_form_types(self):
        assert DBDocumentType.SVS_NOTICE in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.SVS_NOTICE] == "import_svs"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=11, ocr_result={
            "extracted_data": {"tax_year": 2025, "total_contribution": 7200.0},
            "confidence_score": 0.88,
        })
        result = PipelineResult(document_id=11)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.SVS_NOTICE, result)
        assert suggestion["type"] == "import_svs"
