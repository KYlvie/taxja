"""Tests for Kontoauszug pipeline: routing → extraction → suggestion."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestKontoauszugPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_extractor_importable(self):
        from app.services.kontoauszug_extractor import KontoauszugExtractor
        assert KontoauszugExtractor() is not None


class TestKontoauszugPipelineSuggestion:
    def test_in_tax_form_types(self):
        assert DBDocumentType.BANK_STATEMENT in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.BANK_STATEMENT] == "import_bank_statement"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=13, ocr_result={
            "extracted_data": {
                "iban": "AT12 3456 7890 1234 5678",
                "transactions": [{"date": "2025-01-01", "amount": 3500.0, "description": "Gehalt"}],
            },
            "confidence_score": 0.85,
        })
        result = PipelineResult(document_id=13)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.BANK_STATEMENT, result)
        assert suggestion["type"] == "import_bank_statement"
