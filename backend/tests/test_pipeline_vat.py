"""Tests for U1/U30 VAT pipeline: routing → extraction → suggestion."""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator, PipelineResult,
)
from app.models.document import DocumentType as DBDocumentType
from tests._pipeline_test_helpers import FakeDocument


class TestVatPipelineRouting:
    def test_ocr_engine_has_tax_form_route(self):
        from app.services.ocr_engine import OCREngine
        assert hasattr(OCREngine(), '_route_to_tax_form_extractor')

    def test_u1_extractor_importable(self):
        from app.services.vat_form_extractor import VatFormExtractor
        ext = VatFormExtractor()
        text = "Jahr: 2025\n20% Umsatz 80.000,00\nVorsteuer 15.000,00\nZahllast 5.000,00"
        result = ext.extract(text)
        assert result.form_type == "u1"

    def test_u30_extractor_importable(self):
        from app.services.vat_form_extractor import VatFormExtractor
        ext = VatFormExtractor()
        text = "Zeitraum: Jänner 2025\nKZ 022: 25.000,00\nKZ 060: 4.000,00"
        result = ext.extract_u30(text)
        assert result.form_type == "u30"


class TestVatPipelineSuggestion:
    def test_u1_in_tax_form_types(self):
        assert DBDocumentType.U1_FORM in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.U1_FORM] == "import_u1"

    def test_u30_in_tax_form_types(self):
        assert DBDocumentType.U30_FORM in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES
        assert DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP[DBDocumentType.U30_FORM] == "import_u30"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_u1_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=8, ocr_result={
            "extracted_data": {"tax_year": 2025, "umsatz_20": 80000.0, "zahllast": 5000.0},
            "confidence_score": 0.88,
        })
        result = PipelineResult(document_id=8)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.U1_FORM, result)
        assert suggestion["type"] == "import_u1"

    @patch("sqlalchemy.orm.attributes.flag_modified", lambda *a, **kw: None)
    def test_build_u30_suggestion(self):
        orch = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orch.db = MagicMock()
        doc = FakeDocument(id=9, ocr_result={
            "extracted_data": {"tax_year": 2025, "period": "Q1 2025", "umsatz_20": 25000.0},
            "confidence_score": 0.85,
        })
        result = PipelineResult(document_id=9)
        suggestion = orch._build_tax_form_suggestion(doc, DBDocumentType.U30_FORM, result)
        assert suggestion["type"] == "import_u30"
