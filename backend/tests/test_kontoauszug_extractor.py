"""Tests for Kontoauszug (bank statement) extractor."""
from decimal import Decimal

import pytest

from app.services.kontoauszug_extractor import KontoauszugExtractor, KontoauszugData

MONTH_GROUPED_STATEMENT_TEXT = (
    "--- PAGE 1 ---\n"
    "13 Kontoausgaenge:\n"
    "\u2212\u200a\u20ac 1.008,24\n"
    "Dieser Ausdruck gilt nicht als Kontoauszug.\n"
    "Dipl.-Ing. Ylvie Khoo BSc\n"
    "AT60 2011 1837 4498 0900\n"
    "Dezember 2024\n"
    "3 Kontoausgaenge: \u2212\u200a\u20ac 137,04\n"
    "19. Dez.\n"
    "T-Mobile Austria GmbH\n"
    "Ratenplan 9001004040 vom 22.05.2023\n"
    "\u2212\u200a\u20ac 2,03\n"
    "16. Dez.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta Mobil Rechnung 908162761224\n"
    "\u2212\u200a\u20ac 72,78\n"
    "16. Dez.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta offener Saldo per 18.12.202\n"
    "\u2212\u200a\u20ac 62,23\n"
    "November 2024\n"
    "2 Kontoausgaenge: \u2212\u200a\u20ac 137,04\n"
    "18. Nov.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta offener Saldo per 20.11.202\n"
    "\u2212\u200a\u20ac 64,26\n"
    "18. Nov.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta Mobil Rechnung 910246231124\n"
    "\u2212\u200a\u20ac 72,78\n"
    "Oktober 2024\n"
    "2 Kontoausgaenge: \u2212\u200a\u20ac 137,04\n"
    "14. Okt.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta offener Saldo per 16.10.202\n"
    "\u2212\u200a\u20ac 64,26\n"
    "14. Okt.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta Mobil Rechnung 911454891024\n"
    "\u2212\u200a\u20ac 72,78\n"
    "September 2024\n"
    "2 Kontoausgaenge: \u2212\u200a\u20ac 139,92\n"
    "16. Sep.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta offener Saldo per 18.09.202\n"
    "\u2212\u200a\u20ac 67,14\n"
    "16. Sep.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta Mobil Rechnung 911381710924\n"
    "\u2212\u200a\u20ac 72,78\n"
    "August 2024\n"
    "2 Kontoausgaenge: \u2212\u200a\u20ac 261,23\n"
    "16. Aug.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta offener Saldo per 21.08.202\n"
    "\u2212\u200a\u20ac 69,26\n"
    "16. Aug.\n"
    "T-Mobile Austria GmbH\n"
    "Magenta Mobil Rechnung 908018510824\n"
    "\u2212\u200a\u20ac 191,97\n"
    "Juli 2024\n"
    "1 Kontoausgang: \u2212\u200a\u20ac 162,97\n"
    "10. Juli\n"
    "T-Mobile Austria GmbH\n"
    "1.21848297\n"
    "\u2212\u200a\u20ac 162,97\n"
    "Juni 2024\n"
    "1 Kontoausgang: \u2212\u200a\u20ac 33,00\n"
    "26. Juni\n"
    "T-Mobile Austria GmbH\n"
    "043750601038\n"
    "\u2212\u200a\u20ac 33,00"
)


@pytest.fixture
def extractor():
    return KontoauszugExtractor()


class TestKontoauszugBasic:
    def test_empty_text(self, extractor):
        assert extractor.extract("").confidence == 0.0

    def test_extract_returns_data(self, extractor):
        result = extractor.extract("Erste Bank Kontoauszug AT12 1234 5678 9012 3456")
        assert isinstance(result, KontoauszugData)


class TestKontoauszugBankDetection:
    def test_erste_bank(self, extractor):
        text = "Erste Bank und Sparkassen\nKontoauszug\nAT12 1234 5678 9012 3456"
        result = extractor.extract(text)
        assert result.bank_name == "Erste Bank"

    def test_raiffeisen(self, extractor):
        text = "Raiffeisen Landesbank\nKontoauszug\nAT12 1234 5678 9012 3456"
        result = extractor.extract(text)
        assert result.bank_name == "Raiffeisen"

    def test_bawag(self, extractor):
        text = "BAWAG P.S.K.\nKontoauszug\nAT12 1234 5678 9012 3456"
        result = extractor.extract(text)
        assert result.bank_name == "BAWAG P.S.K."


class TestKontoauszugIBAN:
    def test_extract_iban(self, extractor):
        text = "Kontoauszug\nIBAN: AT12 1234 5678 9012 3456\nErste Bank"
        result = extractor.extract(text)
        assert result.iban == "AT121234567890123456"


class TestKontoauszugBalances:
    def test_opening_balance(self, extractor):
        text = "Erste Bank Kontoauszug\nAT12 1234 5678 9012 3456\nAnfangssaldo                     5.000,00"
        result = extractor.extract(text)
        assert result.opening_balance == Decimal("5000.00")

    def test_closing_balance(self, extractor):
        text = "Erste Bank Kontoauszug\nAT12 1234 5678 9012 3456\nEndsaldo                         4.200,00"
        result = extractor.extract(text)
        assert result.closing_balance == Decimal("4200.00")


class TestKontoauszugTransactions:
    def test_extract_transactions(self, extractor):
        text = (
            "Erste Bank Kontoauszug\nAT12 1234 5678 9012 3456\n"
            "01.01.2025 BILLA Einkauf -45,50\n"
            "02.01.2025 Gehalt Firma GmbH 3.500,00\n"
            "03.01.2025 Miete Wohnung -850,00"
        )
        result = extractor.extract(text)
        assert len(result.transactions) >= 2

    def test_transaction_type_credit(self, extractor):
        text = "Erste Bank\nAT12 1234 5678 9012 3456\n02.01.2025 Gehalt 3.500,00"
        result = extractor.extract(text)
        credits = [t for t in result.transactions if t.transaction_type == "credit"]
        assert len(credits) >= 1

    def test_transaction_type_debit(self, extractor):
        text = "Erste Bank\nAT12 1234 5678 9012 3456\n01.01.2025 BILLA Einkauf -45,50"
        result = extractor.extract(text)
        debits = [t for t in result.transactions if t.transaction_type == "debit"]
        assert len(debits) >= 1

    def test_transaction_limit(self, extractor):
        """Extractor should cap at 500 transactions."""
        lines = [f"{i:02d}.01.2025 Transaction {i} -10,00" for i in range(1, 32)]
        text = "Erste Bank\nAT12 1234 5678 9012 3456\n" + "\n".join(lines)
        result = extractor.extract(text)
        assert len(result.transactions) <= 500

    def test_extracts_month_grouped_bank_statement_entries(self, extractor):
        result = extractor.extract(MONTH_GROUPED_STATEMENT_TEXT)

        assert result.iban == "AT602011183744980900"
        assert len(result.transactions) == 13
        assert result.transactions[0].date == "19.12.2024"
        assert result.transactions[0].amount == Decimal("-2.03")
        assert result.transactions[0].counterparty == "T-Mobile Austria GmbH"
        assert result.transactions[0].reference == "Ratenplan 9001004040 vom 22.05.2023"
        assert all(transaction.transaction_type == "debit" for transaction in result.transactions)


class TestKontoauszugConfidence:
    def test_high_confidence(self, extractor):
        text = (
            "Erste Bank Kontoauszug\nAT12 1234 5678 9012 3456\n"
            "Zeitraum: 01.01.2025 - 31.01.2025\n"
            "Anfangssaldo 5.000,00\n"
            "01.01.2025 BILLA -45,50\n"
            "02.01.2025 Gehalt 3.500,00\n"
            "03.01.2025 Miete -850,00\n"
            "04.01.2025 Amazon -29,99\n"
            "05.01.2025 Strom -65,00\n"
            "Endsaldo 7.509,51"
        )
        result = extractor.extract(text)
        assert result.confidence >= 0.6


class TestKontoauszugToDict:
    def test_to_dict_transactions(self, extractor):
        text = "Erste Bank\nAT12 1234 5678 9012 3456\n01.01.2025 BILLA -45,50"
        data = extractor.extract(text)
        result = extractor.to_dict(data)
        assert "transactions" in result
        assert isinstance(result["transactions"], list)
