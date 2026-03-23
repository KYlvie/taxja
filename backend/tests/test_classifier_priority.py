"""Tests for document classifier priority and disambiguation."""
import pytest
from app.services.document_classifier import DocumentClassifier, DocumentType


@pytest.fixture
def classifier():
    return DocumentClassifier()


class TestL1VsE1:
    """L1 = Arbeitnehmerveranlagung, E1 = Einkommensteuererklärung."""

    def test_l1_with_arbeitnehmerveranlagung(self, classifier):
        text = "L1-PDF\nErklärung zur Arbeitnehmerveranlagung 2025"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.L1_FORM

    def test_e1_with_einkommensteuererklaerung(self, classifier):
        text = "E 1-PDF\nEinkommensteuererklärung für das Jahr 2025"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.E1_FORM

    def test_l1_form_marker(self, classifier):
        text = "Formular L 1\nArbeitnehmerveranlagung\nKZ 717: 120,00"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.L1_FORM

    def test_e1_form_marker(self, classifier):
        text = "Formular E 1\nEinkommensteuererklärung\nEinkünfte aus Gewerbebetrieb"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.E1_FORM

    def test_l1_not_e1_with_werbungskosten(self, classifier):
        text = "L1 Arbeitnehmerveranlagung 2025\nWerbungskosten KZ 717: 500,00"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.L1_FORM


class TestE1bVsMietvertrag:
    """E1b = tax form supplement, Mietvertrag = actual rental contract."""

    def test_e1b_with_kz_codes(self, classifier):
        text = "Formular E 1b\nEinkünfte aus Vermietung und Verpachtung\nKZ 9460: 12.000,00"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.E1B_BEILAGE

    def test_mietvertrag_with_contract_language(self, classifier):
        text = "Mietvertrag\nzwischen Vermieter und Mieter\nMonatliche Miete: 800,00 EUR\nMietbeginn: 01.01.2025"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type in (DocumentType.MIETVERTRAG, DocumentType.RENTAL_CONTRACT)


class TestU1VsU30:
    """U1 = annual VAT return, U30 = advance VAT return."""

    def test_u1_annual(self, classifier):
        text = "Formular U 1\nUmsatzsteuererklärung für das Jahr 2025"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.U1_FORM

    def test_u30_advance(self, classifier):
        text = "U30-PDF\nUmsatzsteuervoranmeldung für Jänner 2025"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.U30_FORM

    def test_u1_with_jahresumsatzsteuer(self, classifier):
        text = "Jahresumsatzsteuer 2025\nUmsatzsteuererklärung"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.U1_FORM

    def test_u30_with_uva(self, classifier):
        text = "UVA Voranmeldung\nUmsatzsteuervoranmeldung Q1 2025"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.U30_FORM


class TestPayslipVsL16:
    """Monthly payslip = LOHNZETTEL, L16 annual = also LOHNZETTEL (same type)."""

    def test_monthly_payslip(self, classifier):
        text = "Gehaltszettel\nAuszahlungsmonat: 01.2025\nPersonalnummer: 12345\nSumme Bezüge: 3.500,00"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.LOHNZETTEL

    def test_annual_l16(self, classifier):
        text = "Lohnzettel (L16)\nKalenderjahr: 2025\nKZ 245: 42.500,00\nKZ 260: 8.750,00"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.LOHNZETTEL


class TestSubformPriority:
    """L1k/L1ab should take priority over L1 when specific markers present."""

    def test_l1k_over_l1(self, classifier):
        text = "L1k Beilage für Kinder\nFamilienbonus Plus\nKindermehrbetrag"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.L1K_BEILAGE

    def test_l1ab_over_l1(self, classifier):
        text = "L1ab Absetzbeträge\nAlleinverdienerabsetzbetrag\nPendlerpauschale"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.L1AB_BEILAGE

    def test_e1a_over_e1(self, classifier):
        text = "Formular E 1a\nEinkünfte aus selbständiger Arbeit\nBetriebseinnahmen"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.E1A_BEILAGE

    def test_e1b_over_e1(self, classifier):
        text = "Formular E 1b\nVermietung und Verpachtung\nKZ 9460"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.E1B_BEILAGE

    def test_e1kv_over_e1(self, classifier):
        text = "Formular E 1kv\nKapitalvermögen\nKapitalertragsteuer"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.E1KV_BEILAGE
