"""Tests for Grundsteuer pipeline: routing → extraction → suggestion."""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestGrundsteuerPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_extractor_importable(self):
        from app.services.grundsteuer_extractor import GrundsteuerExtractor
        ext = GrundsteuerExtractor()
        text = "Grundsteuerbescheid\nVorschreibung: 2025\nGrundsteuer 450,00"
        result = ext.extract(text)
        assert result.grundsteuer_betrag == Decimal("450.00")


class TestGrundsteuerPipelineSuggestion:
    def test_in_tax_form_types(self):
        assert DBDocumentType.PROPERTY_TAX in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.PROPERTY_TAX] == "import_grundsteuer"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=12, ocr_result={
            "extracted_data": {"tax_year": 2025, "grundsteuer_betrag": 450.0},
            "confidence_score": 0.9,
        })
        result = PipelineResult(document_id=12)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.PROPERTY_TAX, result)
        assert suggestion["type"] == "import_grundsteuer"
