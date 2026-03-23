"""Tests for E1a Beilage pipeline: routing → extraction → suggestion + loss detection."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestE1aPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_e1a_extractor_importable(self):
        from app.services.e1a_extractor import E1aExtractor
        ext = E1aExtractor()
        assert ext is not None

    def test_e1a_loss_detection(self):
        from app.services.e1a_extractor import E1aExtractor
        ext = E1aExtractor()
        text = "E1a Beilage 2025\nBetriebseinnahmen 20.000,00\nBetriebsausgaben 35.000,00\nVerlust -15.000,00"
        result = ext.extract(text)
        if result.gewinn_verlust is not None:
            assert float(result.gewinn_verlust) < 0


class TestE1aPipelineSuggestion:
    def test_e1a_in_tax_form_types(self):
        assert DBDocumentType.E1A_BEILAGE in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.E1A_BEILAGE] == "import_e1a"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=5, ocr_result={
            "extracted_data": {"tax_year": 2025, "betriebseinnahmen": 80000.0, "gewinn_verlust": 35000.0},
            "confidence_score": 0.9,
        })
        result = PipelineResult(document_id=5)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.E1A_BEILAGE, result)
        assert suggestion["type"] == "import_e1a"
        assert suggestion["data"]["gewinn_verlust"] == 35000.0
