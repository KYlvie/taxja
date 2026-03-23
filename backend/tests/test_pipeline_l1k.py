"""Tests for L1k Beilage pipeline: routing → extraction → suggestion."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestL1kPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_l1k_extractor_works(self):
        from app.services.l1k_extractor import L1kExtractor
        ext = L1kExtractor()
        text = "Veranlagung: 2025\nFamilienbonus Plus 2.000,00"
        result = ext.extract(text)
        assert result.tax_year == 2025


class TestL1kPipelineSuggestion:
    def test_l1k_in_tax_form_types(self):
        assert DBDocumentType.L1K_BEILAGE in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.L1K_BEILAGE] == "import_l1k"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=3, ocr_result={
            "extracted_data": {"tax_year": 2025, "familienbonus_total": 2000.0},
            "confidence_score": 0.88,
        })
        result = PipelineResult(document_id=3)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.L1K_BEILAGE, result)
        assert suggestion["type"] == "import_l1k"
