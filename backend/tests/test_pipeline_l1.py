"""Tests for L1 Form pipeline: routing → extraction → suggestion."""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestL1PipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_l1_extractor_works(self):
        from app.services.l1_form_extractor import L1FormExtractor
        ext = L1FormExtractor()
        text = "Arbeitnehmerveranlagung 2025\nKZ 717: 120,00\nKZ 724: 300,00"
        result = ext.extract(text)
        assert result.tax_year == 2025
        assert result.kz_717 == Decimal("120.00")


class TestL1PipelineSuggestion:
    def test_l1_in_tax_form_types(self):
        assert DBDocumentType.L1_FORM in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.L1_FORM] == "import_l1"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=2, ocr_result={
            "extracted_data": {"tax_year": 2025, "kz_717": 120.0},
            "confidence_score": 0.85,
        })
        result = PipelineResult(document_id=2)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.L1_FORM, result)
        assert suggestion is not None
        assert suggestion["type"] == "import_l1"
