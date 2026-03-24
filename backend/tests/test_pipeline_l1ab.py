"""Tests for L1ab Beilage pipeline: routing → extraction → suggestion."""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestL1abPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_l1ab_extractor_works(self):
        from app.services.l1ab_extractor import L1abExtractor
        ext = L1abExtractor()
        text = "Veranlagung: 2025\nPendlerpauschale 696,00"
        result = ext.extract(text)
        assert result.pendlerpauschale_betrag == Decimal("696.00")


class TestL1abPipelineSuggestion:
    def test_l1ab_in_tax_form_types(self):
        assert DBDocumentType.L1AB_BEILAGE in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.L1AB_BEILAGE] == "import_l1ab"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=4, ocr_result={
            "extracted_data": {"tax_year": 2025, "pendlerpauschale_betrag": 696.0},
            "confidence_score": 0.82,
        })
        result = PipelineResult(document_id=4)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.L1AB_BEILAGE, result)
        assert suggestion["type"] == "import_l1ab"
