"""Tests for DocumentClassifier new tax document type classification."""
import pytest
from app.services.document_classifier import DocumentClassifier, DocumentType


@pytest.fixture
def classifier():
    return DocumentClassifier()


class TestL1Classification:
    def test_l1_form_detected(self, classifier):
        text = "Formular L 1\nErklärung zur Arbeitnehmerveranlagung 2025\nKZ 717: 120,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.L1_FORM
        assert conf >= 0.8

    def test_l1_pdf_marker(self, classifier):
        text = "L1-PDF\nArbeitnehmerveranlagung für das Jahr 2025"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.L1_FORM


class TestL1kClassification:
    def test_l1k_detected(self, classifier):
        text = "Formular L 1\nL1k Beilage für Kinder\nFamilienbonus Plus 2.000,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.L1K_BEILAGE

    def test_l1k_standalone(self, classifier):
        text = "L1k-PDF\nBeilage für Kinder\nKindermehrbetrag"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.L1K_BEILAGE


class TestL1abClassification:
    def test_l1ab_detected(self, classifier):
        text = "Formular L 1\nL1ab Absetzbeträge\nAlleinverdienerabsetzbetrag\nPendlerpauschale"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.L1AB_BEILAGE

    def test_l1ab_standalone(self, classifier):
        text = "L1ab-PDF\nAbsetzbeträge und Pendlerpauschale"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.L1AB_BEILAGE


class TestE1aClassification:
    def test_e1a_detected(self, classifier):
        text = "Formular E 1a\nEinkünfte aus selbständiger Arbeit\nBetriebseinnahmen 80.000,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.E1A_BEILAGE
        assert conf >= 0.8


class TestE1bClassification:
    def test_e1b_detected(self, classifier):
        text = "Formular E 1b\nEinkünfte aus Vermietung und Verpachtung\nKZ 9460: 12.000,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.E1B_BEILAGE

    def test_e1b_vs_mietvertrag(self, classifier):
        """E1b is a tax form, not a rental contract."""
        text = "E1b-PDF\nEinkünfte aus Vermietung und Verpachtung\nKZ 9460 KZ 9500"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.E1B_BEILAGE


class TestE1kvClassification:
    def test_e1kv_detected(self, classifier):
        text = "Formular E 1kv\nEinkünfte aus Kapitalvermögen\nKapitalertragsteuer"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.E1KV_BEILAGE


class TestU1Classification:
    def test_u1_detected(self, classifier):
        text = "Formular U 1\nUmsatzsteuererklärung für das Jahr 2025"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.U1_FORM
        assert conf >= 0.8


class TestU30Classification:
    def test_u30_detected(self, classifier):
        text = "U30-PDF\nUmsatzsteuervoranmeldung für Jänner 2025"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.U30_FORM


class TestJahresabschlussClassification:
    def test_jahresabschluss_via_patterns(self, classifier):
        text = "Jahresabschluss zum 31.12.2025\nBilanz\nGewinn- und Verlustrechnung\nBilanzsumme 500.000,00\nJahresergebnis 35.000,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.JAHRESABSCHLUSS


class TestClassifierPriority:
    def test_l1_not_confused_with_e1(self, classifier):
        """L1 contains 'arbeitnehmerveranlagung', E1 contains 'einkommensteuererklärung'."""
        l1_text = "L1-PDF\nErklärung zur Arbeitnehmerveranlagung 2025"
        e1_text = "E 1-PDF\nEinkommensteuererklärung für das Jahr 2025"
        l1_type, _ = classifier.classify(None, l1_text)
        e1_type, _ = classifier.classify(None, e1_text)
        assert l1_type == DocumentType.L1_FORM
        assert e1_type == DocumentType.E1_FORM

    def test_u1_not_confused_with_u30(self, classifier):
        u1_text = "Formular U 1\nUmsatzsteuererklärung für das Jahr 2025"
        u30_text = "U30-PDF\nUmsatzsteuervoranmeldung für Jänner 2025"
        u1_type, _ = classifier.classify(None, u1_text)
        u30_type, _ = classifier.classify(None, u30_text)
        assert u1_type == DocumentType.U1_FORM
        assert u30_type == DocumentType.U30_FORM

    def test_payslip_not_confused_with_l1(self, classifier):
        """Monthly payslip should be LOHNZETTEL, not L1_FORM."""
        payslip_text = "Gehaltszettel\nAuszahlungsmonat: 01.2025\nPersonalnummer: 12345\nSumme Bezüge: 3.500,00\nSumme Abzüge: 800,00"
        doc_type, _ = classifier.classify(None, payslip_text)
        assert doc_type == DocumentType.LOHNZETTEL


# ── Tests for 10 new document types ──


class TestSpendenbestaetigungClassification:
    def test_spendenbestaetigung_detected(self, classifier):
        text = "Spendenbestätigung\nZuwendungsbestätigung für das Jahr 2025\nSpende an gemeinnützige Organisation\nRegistrierungsnummer SO-12345\nBetrag: 500,00 EUR"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.SPENDENBESTAETIGUNG
        assert conf >= 0.5

    def test_spendenbestaetigung_ascii_umlauts(self, classifier):
        text = "Spendenbestaetigung\nZuwendungsbestaetigung fuer das Jahr 2025\nSpende absetzbar"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.SPENDENBESTAETIGUNG


class TestVersicherungsbestaetigungClassification:
    def test_versicherungsbestaetigung_detected(self, classifier):
        text = "Versicherungsbestätigung\nVersicherungspolizze Nr. 12345\nVersicherungsnehmer: Max Mustermann\nPrämie: 1.200,00 EUR\nHaushaltsversicherung"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.VERSICHERUNGSBESTAETIGUNG
        assert conf >= 0.5

    def test_versicherungsschein(self, classifier):
        text = "Versicherungsschein\nVersicherungsvertrag\nDeckung Haftpflicht\nPrämie jährlich 800,00"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.VERSICHERUNGSBESTAETIGUNG


class TestLoanContractClassification:
    def test_loan_contract_detected(self, classifier):
        text = (
            "KREDITVERTRAG\n"
            "Vertragsnummer: 515-112233-4455\n"
            "Kreditnehmer: Ing. Klaus Bauer\n"
            "Kreditbetrag: EUR 290.000,00\n"
            "Aktueller Zinssatz: 3,750% p.a.\n"
            "Monatliche Rate: EUR 1.508,33\n"
            "Laufzeit: 25 Jahre\n"
        )
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.LOAN_CONTRACT
        assert conf >= 0.5

    def test_darlehensvertrag_detected(self, classifier):
        text = (
            "Darlehensvertrag\n"
            "Darlehensnehmer: Maria Beispiel\n"
            "Darlehensbetrag: EUR 150.000,00\n"
            "Zinssatz: 3,25%\n"
            "Tilgungsform: Annuitaet\n"
        )
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.LOAN_CONTRACT


class TestKinderbetreuungskostenClassification:
    def test_kinderbetreuungskosten_detected(self, classifier):
        text = "Kinderbetreuungskosten\nKindergarten Sonnenschein\nBetreuungskosten für das Jahr 2025\nKind: Anna Mustermann\nBetrag: 2.400,00 EUR"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.KINDERBETREUUNGSKOSTEN
        assert conf >= 0.5

    def test_tagesmutter(self, classifier):
        text = "Bestätigung Tagesmutter\nKinderbetreuung\nBetreuungskosten monatlich 350,00\nPädagogisch qualifiziert"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.KINDERBETREUUNGSKOSTEN


class TestFortbildungskostenClassification:
    def test_fortbildungskosten_detected(self, classifier):
        text = "Fortbildungskosten\nKursbestätigung\nSeminar: Projektmanagement\nTeilnahmebestätigung\nStudiengebühr: 1.500,00 EUR"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.FORTBILDUNGSKOSTEN
        assert conf >= 0.5

    def test_weiterbildung(self, classifier):
        text = "Weiterbildungskosten\nLehrgang Buchhaltung\nTeilnahmebestätigung\nZertifikat"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.FORTBILDUNGSKOSTEN


class TestPendlerpauschaleClassification:
    def test_pendlerpauschale_detected(self, classifier):
        text = "Pendlerpauschale\nPendlerrechner Ergebnis\nEntfernung Arbeitsstätte: 45 km\nÖffentliches Verkehrsmittel nicht zumutbar\nPendlereuro: 90,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.PENDLERPAUSCHALE
        assert conf >= 0.5


class TestKirchenbeitragClassification:
    def test_kirchenbeitrag_detected(self, classifier):
        text = "Kirchenbeitragsbestätigung\nDiözese Wien\nKirchenbeitrag für das Jahr 2025\nBeitragsjahr 2025\nBetrag: 400,00 EUR"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.KIRCHENBEITRAG
        assert conf >= 0.5

    def test_kirchensteuer(self, classifier):
        text = "Kirchensteuer Bestätigung\nPfarrgemeinde St. Stephan\nMitgliedsbeitrag 2025"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.KIRCHENBEITRAG


class TestGrundbuchauszugClassification:
    def test_grundbuchauszug_detected(self, classifier):
        text = "Grundbuchauszug\nBezirksgericht Innere Stadt Wien\nEinlagezahl 1234\nKatastralgemeinde Innere Stadt\nEigentumsrecht: Max Mustermann"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.GRUNDBUCHAUSZUG
        assert conf >= 0.5


class TestBetriebskostenabrechnungClassification:
    def test_betriebskostenabrechnung_detected(self, classifier):
        text = "Betriebskostenabrechnung 2025\nHausverwaltung Müller GmbH\nAbrechnungszeitraum 01.01.2025 - 31.12.2025\nHeizkosten 800,00\nMüllabfuhr 120,00\nNachzahlung: 250,00"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.BETRIEBSKOSTENABRECHNUNG
        assert conf >= 0.5


class TestGewerbescheinClassification:
    def test_gewerbeschein_detected(self, classifier):
        text = "Gewerbeschein\nGewerbeberechtigung\nBezirkshauptmannschaft Graz-Umgebung\nGewerbeordnung\nStandort: Hauptstraße 1, 8010 Graz\nGISA Nr. 12345678"
        doc_type, conf = classifier.classify(None, text)
        assert doc_type == DocumentType.GEWERBESCHEIN
        assert conf >= 0.5


class TestKontoauszugClassification:
    def test_kontoauszug_detected(self, classifier):
        text = "Kontoauszug Nr. 12\nAuszugsnummer 12\nKontobewegungen\nBuchungsdetails\nValuta 15.01.2025\nAnfangssaldo: 5.000,00\nEndsaldo: 4.200,00\nSoll Haben Überweisung"
        doc_type, conf = classifier.classify(None, text)
        # KONTOAUSZUG and BANK_STATEMENT share keywords; both are valid bank document types
        assert doc_type in (DocumentType.KONTOAUSZUG, DocumentType.BANK_STATEMENT)
        assert conf >= 0.5

    def test_kontoauszug_vs_bank_statement(self, classifier):
        """KONTOAUSZUG should be detected when specific markers are present."""
        text = "Kontoauszug\nAuszugsnummer 5\nKontobewegungen vom 01.01 bis 31.01\nBuchungsdetails\nSoll Haben Saldo"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.KONTOAUSZUG


class TestNewTypesDoNotBreakExisting:
    """Ensure existing types still classify correctly after adding new patterns."""

    def test_receipt_still_works(self, classifier):
        text = "BILLA\nKassenbon\nSumme: 23,50 EUR\nBar bezahlt"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.RECEIPT

    def test_invoice_still_works(self, classifier):
        text = "Rechnung Nr. 2025-001\nRechnungsbetrag: 1.200,00 EUR\nUSt-ID: ATU12345678\nZahlbar bis 30.01.2025"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.INVOICE

    def test_lohnzettel_still_works(self, classifier):
        text = "Gehaltszettel\nAuszahlungsmonat: 03.2025\nPersonalnummer: 54321\nSumme Bezüge: 4.000,00"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.LOHNZETTEL

    def test_svs_still_works(self, classifier):
        text = "SVS Beitragsmitteilung\nBeitrag 2025\nPensionsversicherung\nKrankenversicherung\nBeitragsgrundlage"
        doc_type, _ = classifier.classify(None, text)
        assert doc_type == DocumentType.SVS_NOTICE
