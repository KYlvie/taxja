"""End-to-end integration tests for document type processing flows."""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from app.services.document_pipeline_orchestrator import (
    DocumentPipelineOrchestrator,
    PipelineResult,
    PipelineStage,
    OCR_TO_DB_TYPE_MAP,
)
from app.services.document_classifier import DocumentClassifier, DocumentType as OCRDocumentType
from app.models.document import DocumentType as DBDocumentType


class TestOCRToDBTypeMapping:
    """Verify all new OCR types map to correct DB types."""

    def test_l1_form_mapping(self):
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.L1_FORM] == DBDocumentType.L1_FORM

    def test_l1k_mapping(self):
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.L1K_BEILAGE] == DBDocumentType.L1K_BEILAGE

    def test_l1ab_mapping(self):
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.L1AB_BEILAGE] == DBDocumentType.L1AB_BEILAGE

    def test_e1a_mapping(self):
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.E1A_BEILAGE] == DBDocumentType.E1A_BEILAGE

    def test_e1b_mapping(self):
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.E1B_BEILAGE] == DBDocumentType.E1B_BEILAGE

    def test_e1kv_mapping(self):
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.E1KV_BEILAGE] == DBDocumentType.E1KV_BEILAGE

    def test_u1_mapping(self):
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.U1_FORM] == DBDocumentType.U1_FORM

    def test_u30_mapping(self):
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.U30_FORM] == DBDocumentType.U30_FORM

    def test_jahresabschluss_mapping(self):
        assert OCR_TO_DB_TYPE_MAP[OCRDocumentType.JAHRESABSCHLUSS] == DBDocumentType.JAHRESABSCHLUSS


class TestTaxFormSuggestionTypeMap:
    """Verify all DB types have correct suggestion type strings."""

    def test_all_tax_form_types_have_suggestion_map(self):
        for db_type in DocumentPipelineOrchestrator.TAX_FORM_DB_TYPES:
            assert db_type in DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP, \
                f"{db_type} missing from TAX_FORM_SUGGESTION_TYPE_MAP"

    def test_suggestion_types_start_with_import(self):
        for db_type, stype in DocumentPipelineOrchestrator.TAX_FORM_SUGGESTION_TYPE_MAP.items():
            assert stype.startswith("import_"), f"{stype} doesn't start with import_"


class TestExtractorAvailability:
    """Verify all extractors can be imported and instantiated."""

    def test_l16_extractor(self):
        from app.services.l16_extractor import L16Extractor
        assert L16Extractor() is not None

    def test_l1_form_extractor(self):
        from app.services.l1_form_extractor import L1FormExtractor
        assert L1FormExtractor() is not None

    def test_l1k_extractor(self):
        from app.services.l1k_extractor import L1kExtractor
        assert L1kExtractor() is not None

    def test_l1ab_extractor(self):
        from app.services.l1ab_extractor import L1abExtractor
        assert L1abExtractor() is not None

    def test_e1a_extractor(self):
        from app.services.e1a_extractor import E1aExtractor
        assert E1aExtractor() is not None

    def test_e1b_extractor(self):
        from app.services.e1b_extractor import E1bExtractor
        assert E1bExtractor() is not None

    def test_e1kv_extractor(self):
        from app.services.e1kv_extractor import E1kvExtractor
        assert E1kvExtractor() is not None

    def test_vat_form_extractor(self):
        from app.services.vat_form_extractor import VatFormExtractor
        assert VatFormExtractor() is not None

    def test_jahresabschluss_extractor(self):
        from app.services.jahresabschluss_extractor import JahresabschlussExtractor
        assert JahresabschlussExtractor() is not None

    def test_svs_extractor(self):
        from app.services.svs_extractor import SvsExtractor
        assert SvsExtractor() is not None

    def test_grundsteuer_extractor(self):
        from app.services.grundsteuer_extractor import GrundsteuerExtractor
        assert GrundsteuerExtractor() is not None

    def test_kontoauszug_extractor(self):
        from app.services.kontoauszug_extractor import KontoauszugExtractor
        assert KontoauszugExtractor() is not None


class TestClassifierToExtractorFlow:
    """Test that classifier output feeds correctly into extraction."""

    def test_classify_then_extract_l16(self):
        classifier = DocumentClassifier()
        text = "Lohnzettel Kalenderjahr: 2025\nKZ 245: 42.500,00\nKZ 260: 8.750,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == OCRDocumentType.LOHNZETTEL

        from app.services.l16_extractor import L16Extractor
        result = L16Extractor().extract(text)
        assert result.kz_245 == Decimal("42500.00")

    def test_classify_then_extract_e1a(self):
        classifier = DocumentClassifier()
        text = "Formular E 1a\nEinkünfte aus selbständiger Arbeit\nBetriebseinnahmen 80.000,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == OCRDocumentType.E1A_BEILAGE

        from app.services.e1a_extractor import E1aExtractor
        result = E1aExtractor().extract(text)
        assert result.tax_year is not None or result.betriebseinnahmen is not None

    def test_classify_then_extract_vat(self):
        classifier = DocumentClassifier()
        text = "Formular U 1\nUmsatzsteuererklärung für das Jahr 2025\n20% Umsatz 80.000,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == OCRDocumentType.U1_FORM

        from app.services.vat_form_extractor import VatFormExtractor
        result = VatFormExtractor().extract(text)
        assert result.umsatz_20 == Decimal("80000.00")


class TestLLMFallbackThreshold:
    """Verify the 0.9 confidence threshold for LLM fallback is configured."""

    def test_confidence_threshold_is_09(self):
        from app.core.ocr_config import OCRConfig
        config = OCRConfig()
        assert config.CONFIDENCE_THRESHOLD == 0.9

    def test_tax_form_llm_fallback_threshold(self):
        from app.services.ocr_engine import OCREngine
        engine = OCREngine()
        assert engine.TAX_FORM_LLM_FALLBACK_THRESHOLD == 0.9
