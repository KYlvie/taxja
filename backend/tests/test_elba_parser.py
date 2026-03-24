"""Tests for ELBA bank format parsing in CSVParser.

Covers format detection, column mapping, amount parsing (positive/negative),
date parsing, and distinguishing ELBA from other Austrian bank formats.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app.services.csv_parser import BankFormat, CSVParser


# ---------------------------------------------------------------------------
# Sample CSV data
# ---------------------------------------------------------------------------

ELBA_CSV_KONTONUMMER_VALUTA = """\
Kontonummer;Valuta;Buchungsdatum;Betrag;Auftraggeber/Empfaenger;Zahlungsreferenz;Buchungstext
AT123456789;03.01.2026;03.01.2026;-45,90;Wiener Stadtwerke;REF-001;Lastschrift
AT123456789;05.01.2026;05.01.2026;2500,00;Arbeitgeber GmbH;REF-002;Gehalt
"""

ELBA_CSV_ZAHLUNGSREFERENZ = """\
Buchungsdatum;Betrag;Auftraggeber/Empfaenger;Zahlungsreferenz;Buchungstext
10.02.2026;-120,50;Amazon EU;ZR-99001;Kartenzahlung
15.02.2026;3.500,00;Finanzamt Wien;ZR-99002;Steuererstattung
"""

RAIFFEISEN_CSV = """\
Buchungsdatum;Betrag;Buchungstext;Referenz;Raiffeisen
01.03.2026;-50,00;Einkauf;R-001;Raiffeisen Konto
"""

ERSTE_BANK_CSV = """\
Valutadatum;Betrag;Buchungstext;Belegnummer
01.03.2026;-30,00;Einkauf;BN-001
"""

SPARKASSE_CSV = """\
Buchungstag;Betrag;Verwendungszweck;Referenz
01.03.2026;-25,00;Einkauf;S-001
"""

BANK_AUSTRIA_CSV = """\
Buchungsdatum;Betrag;Buchungstext;Referenznummer
01.03.2026;-15,00;Einkauf;BA-001
"""

GENERIC_CSV = """\
date;amount;description
2026-03-01;-10.00;Misc purchase
"""


# ---------------------------------------------------------------------------
# 1. ELBA format detection
# ---------------------------------------------------------------------------

class TestELBAFormatDetection:
    """_detect_bank_format must identify ELBA from header patterns."""

    def test_detect_elba_by_kontonummer_and_valuta(self):
        parser = CSVParser()
        headers = ["Kontonummer", "Valuta", "Buchungsdatum", "Betrag"]
        result = parser._detect_bank_format(headers)
        assert result == BankFormat.ELBA

    def test_detect_elba_by_zahlungsreferenz(self):
        parser = CSVParser()
        headers = ["Buchungsdatum", "Betrag", "Zahlungsreferenz"]
        result = parser._detect_bank_format(headers)
        assert result == BankFormat.ELBA

    def test_detect_elba_case_insensitive(self):
        parser = CSVParser()
        headers = ["kontonummer", "valuta", "buchungsdatum", "betrag"]
        result = parser._detect_bank_format(headers)
        assert result == BankFormat.ELBA

    def test_kontonummer_alone_not_elba(self):
        """Kontonummer without Valuta should not trigger ELBA detection."""
        parser = CSVParser()
        headers = ["Kontonummer", "Buchungsdatum", "Betrag"]
        result = parser._detect_bank_format(headers)
        # Should fall through to GENERIC since no other bank matches
        assert result != BankFormat.ELBA


# ---------------------------------------------------------------------------
# 2. ELBA CSV parsing with correct column mapping
# ---------------------------------------------------------------------------

class TestELBAParsing:
    """Full parse of ELBA-formatted CSV content."""

    def test_parse_elba_kontonummer_valuta_format(self):
        parser = CSVParser()
        transactions = parser.parse(ELBA_CSV_KONTONUMMER_VALUTA)

        assert len(transactions) == 2
        assert parser.bank_format == BankFormat.ELBA

        # First transaction: expense
        tx0 = transactions[0]
        assert tx0["amount"] == Decimal("-45.90")
        assert tx0["date"] == datetime(2026, 1, 3)

        # Second transaction: income
        tx1 = transactions[1]
        assert tx1["amount"] == Decimal("2500.00")
        assert tx1["date"] == datetime(2026, 1, 5)

    def test_parse_elba_zahlungsreferenz_format(self):
        parser = CSVParser()
        transactions = parser.parse(ELBA_CSV_ZAHLUNGSREFERENZ)

        assert len(transactions) == 2
        assert parser.bank_format == BankFormat.ELBA

    def test_elba_description_extracted(self):
        parser = CSVParser()
        transactions = parser.parse(ELBA_CSV_KONTONUMMER_VALUTA)
        # Description should come from Auftraggeber/Empfaenger
        assert "Wiener Stadtwerke" in transactions[0]["description"]

    def test_elba_reference_extracted(self):
        parser = CSVParser()
        transactions = parser.parse(ELBA_CSV_KONTONUMMER_VALUTA)
        assert transactions[0]["reference"] == "REF-001"


# ---------------------------------------------------------------------------
# 3. Amount parsing (positive / negative, Austrian format)
# ---------------------------------------------------------------------------

class TestAmountParsing:
    """CSVParser._parse_amount handles Austrian decimal conventions."""

    def test_negative_comma_decimal(self):
        parser = CSVParser()
        assert parser._parse_amount("-45,90") == Decimal("-45.90")

    def test_positive_comma_decimal(self):
        parser = CSVParser()
        assert parser._parse_amount("2500,00") == Decimal("2500.00")

    def test_thousands_dot_comma_decimal(self):
        """Austrian format: 3.500,00 == 3500.00"""
        parser = CSVParser()
        assert parser._parse_amount("3.500,00") == Decimal("3500.00")

    def test_euro_symbol_stripped(self):
        parser = CSVParser()
        assert parser._parse_amount("€ 100,50") == Decimal("100.50")

    def test_eur_text_stripped(self):
        parser = CSVParser()
        assert parser._parse_amount("EUR 100,50") == Decimal("100.50")

    def test_invalid_amount_returns_none(self):
        parser = CSVParser()
        assert parser._parse_amount("abc") is None


# ---------------------------------------------------------------------------
# 4. Date parsing from ELBA format
# ---------------------------------------------------------------------------

class TestDateParsing:
    """CSVParser._parse_date handles German/Austrian date formats."""

    def test_dd_mm_yyyy_dot(self):
        parser = CSVParser()
        assert parser._parse_date("03.01.2026") == datetime(2026, 1, 3)

    def test_dd_mm_yyyy_slash(self):
        parser = CSVParser()
        assert parser._parse_date("03/01/2026") == datetime(2026, 1, 3)

    def test_iso_format(self):
        parser = CSVParser()
        assert parser._parse_date("2026-01-03") == datetime(2026, 1, 3)

    def test_short_year(self):
        parser = CSVParser()
        assert parser._parse_date("03.01.26") == datetime(2026, 1, 3)

    def test_invalid_date_returns_none(self):
        parser = CSVParser()
        assert parser._parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# 5. Distinguish ELBA from other bank formats
# ---------------------------------------------------------------------------

class TestFormatDistinction:
    """Ensure ELBA detection does not false-positive on other banks."""

    def test_raiffeisen_detected_correctly(self):
        parser = CSVParser()
        parser.parse(RAIFFEISEN_CSV)
        assert parser.bank_format == BankFormat.RAIFFEISEN

    def test_erste_bank_detected_correctly(self):
        parser = CSVParser()
        parser.parse(ERSTE_BANK_CSV)
        assert parser.bank_format == BankFormat.ERSTE_BANK

    def test_sparkasse_detected_correctly(self):
        parser = CSVParser()
        parser.parse(SPARKASSE_CSV)
        assert parser.bank_format == BankFormat.SPARKASSE

    def test_bank_austria_detected_correctly(self):
        parser = CSVParser()
        parser.parse(BANK_AUSTRIA_CSV)
        assert parser.bank_format == BankFormat.BANK_AUSTRIA

    def test_generic_detected_correctly(self):
        parser = CSVParser()
        parser.parse(GENERIC_CSV)
        assert parser.bank_format == BankFormat.GENERIC

    def test_explicit_elba_format_skips_detection(self):
        """When bank_format is set explicitly, auto-detection is skipped."""
        parser = CSVParser(bank_format=BankFormat.ELBA)
        transactions = parser.parse(ELBA_CSV_KONTONUMMER_VALUTA)
        assert parser.bank_format == BankFormat.ELBA
        assert len(transactions) == 2
