"""Tests for Kontoauszug (bank statement) extractor."""
import pytest
from decimal import Decimal
from app.services.kontoauszug_extractor import KontoauszugExtractor, KontoauszugData


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
