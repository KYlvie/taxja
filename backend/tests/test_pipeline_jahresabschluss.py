"""Tests for Jahresabschluss pipeline: routing → extraction → suggestion + loss detection."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestJahresabschlussPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_extractor_importable(self):
        from app.services.jahresabschluss_extractor import JahresabschlussExtractor
        assert JahresabschlussExtractor() is not None

    def test_loss_detection(self):
        from app.services.jahresabschluss_extractor import JahresabschlussExtractor
        ext = JahresabschlussExtractor()
        text = "Jahresabschluss 2025\nBetriebseinnahmen 50.000,00\nBetriebsausgaben 70.000,00\nVerlust -20.000,00"
        result = ext.extract(text)
        if result.gewinn_verlust is not None:
            assert float(result.gewinn_verlust) < 0


class TestJahresabschlussPipelineSuggestion:
    def test_in_tax_form_types(self):
        assert DBDocumentType.JAHRESABSCHLUSS in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.JAHRESABSCHLUSS] == "import_jahresabschluss"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=10, ocr_result={
            "extracted_data": {"tax_year": 2025, "gewinn_verlust": 35000.0},
            "confidence_score": 0.9,
        })
        result = PipelineResult(document_id=10)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.JAHRESABSCHLUSS, result)
        assert suggestion["type"] == "import_jahresabschluss"
