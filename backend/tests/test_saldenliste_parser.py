"""
Unit tests for SaldenlisteParser service.
Tests CSV parsing, Excel parsing, format detection, and account normalization.
"""
import csv
import tempfile
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.services.saldenliste_parser import (
    AccountBalance,
    SaldenlisteData,
    SaldenlisteFormat,
    SaldenlisteParser,
)


@pytest.fixture
def parser():
    """Create a SaldenlisteParser instance."""
    return SaldenlisteParser()


@pytest.fixture
def sample_csv_file():
    """Create a temporary CSV file with sample data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Konto", "Bezeichnung", "Saldo"])
        writer.writerow(["1000", "Kassa", "5000.00"])
        writer.writerow(["2000", "Bank", "15000.50"])
        writer.writerow(["4000", "Umsatzerlöse", "-20000.00"])
        writer.writerow(["7000", "Wareneinsatz", "3000.00"])
        return f.name
    

@pytest.fixture
def sample_csv_file_debit_credit():
    """Create a temporary CSV file with debit/credit columns."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Kontonummer", "Kontobezeichnung", "Soll", "Haben"])
        writer.writerow(["1000", "Kassa", "5000.00", "0.00"])
        writer.writerow(["2000", "Bank", "15000.50", "0.00"])
        writer.writerow(["4000", "Umsatzerlöse", "0.00", "20000.00"])
        writer.writerow(["7000", "Wareneinsatz", "3000.00", "0.00"])
        return f.name


@pytest.fixture
def sample_excel_file():
    """Create a temporary Excel file with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        
        # Write headers
        sheet.append(["Konto", "Bezeichnung", "Saldo"])
        
        # Write data
        sheet.append([1000, "Kassa", 5000.00])
        sheet.append([2000, "Bank", 15000.50])
        sheet.append([4000, "Umsatzerlöse", -20000.00])
        sheet.append([7000, "Wareneinsatz", 3000.00])
        
        workbook.save(f.name)
        workbook.close()
        return f.name


class TestSaldenlisteParser:
    """Test suite for SaldenlisteParser."""

    def test_parse_csv_basic(self, parser, sample_csv_file):
        """Test basic CSV parsing with balance column."""
        result = parser.parse_csv(sample_csv_file, tax_year=2023)
        
        assert isinstance(result, SaldenlisteData)
        assert result.tax_year == 2023
        assert len(result.accounts) == 4
        assert result.confidence > 0.0
        
        # Check first account
        account = result.accounts[0]
        assert account.account_number == "1000"
        assert account.account_name == "Kassa"
        assert account.balance == Decimal("5000.00")
        assert account.kontenklasse == 1
        
        # Cleanup
        Path(sample_csv_file).unlink()

    def test_parse_csv_debit_credit(self, parser, sample_csv_file_debit_credit):
        """Test CSV parsing with debit/credit columns."""
        result = parser.parse_csv(sample_csv_file_debit_credit, tax_year=2023)
        
        assert len(result.accounts) == 4
        
        # Check account with debit balance
        kassa = next(acc for acc in result.accounts if acc.account_number == "1000")
        assert kassa.debit_balance == Decimal("5000.00")
        assert kassa.credit_balance == Decimal("0.00")
        assert kassa.balance == Decimal("5000.00")
        
        # Check account with credit balance
        revenue = next(acc for acc in result.accounts if acc.account_number == "4000")
        assert revenue.debit_balance == Decimal("0.00")
        assert revenue.credit_balance == Decimal("20000.00")
        assert revenue.balance == Decimal("-20000.00")
        
        # Cleanup
        Path(sample_csv_file_debit_credit).unlink()

    def test_parse_excel_basic(self, parser, sample_excel_file):
        """Test basic Excel parsing."""
        result = parser.parse_excel(sample_excel_file, tax_year=2023)
        
        assert isinstance(result, SaldenlisteData)
        assert result.tax_year == 2023
        assert len(result.accounts) == 4
        assert result.confidence > 0.0
        
        # Check first account
        account = result.accounts[0]
        assert account.account_number == "1000"
        assert account.account_name == "Kassa"
        assert account.balance == Decimal("5000.00")
        assert account.kontenklasse == 1
        
        # Cleanup
        Path(sample_excel_file).unlink()

    def test_normalize_account_number(self, parser):
        """Test account number normalization."""
        assert parser.normalize_account_number("1000") == "1000"
        assert parser.normalize_account_number("100") == "0100"
        assert parser.normalize_account_number("1") == "0001"
        assert parser.normalize_account_number("10-00") == "1000"
        assert parser.normalize_account_number("1.000") == "1000"
        assert parser.normalize_account_number("  1000  ") == "1000"

    def test_extract_kontenklasse(self, parser):
        """Test Kontenklasse extraction from account number."""
        assert parser.extract_kontenklasse("1000") == 1
        assert parser.extract_kontenklasse("2000") == 2
        assert parser.extract_kontenklasse("4000") == 4
        assert parser.extract_kontenklasse("7000") == 7
        assert parser.extract_kontenklasse("100") == 0  # Normalized to 0100
        assert parser.extract_kontenklasse("abc") is None

    def test_detect_format_csv(self, parser, sample_csv_file):
        """Test format detection for CSV files."""
        format_detected = parser.detect_format(sample_csv_file)
        assert format_detected in [SaldenlisteFormat.CUSTOM, SaldenlisteFormat.BMD]
        
        # Cleanup
        Path(sample_csv_file).unlink()

    def test_detect_format_excel(self, parser, sample_excel_file):
        """Test format detection for Excel files."""
        format_detected = parser.detect_format(sample_excel_file)
        assert format_detected in [SaldenlisteFormat.CUSTOM, SaldenlisteFormat.BMD]
        
        # Cleanup
        Path(sample_excel_file).unlink()

    def test_parse_csv_missing_file(self, parser):
        """Test parsing non-existent file raises error."""
        with pytest.raises(ValueError, match="File not found"):
            parser.parse_csv("/nonexistent/file.csv", tax_year=2023)

    def test_parse_csv_invalid_headers(self, parser):
        """Test parsing CSV with invalid headers raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["InvalidColumn1", "InvalidColumn2"])
            writer.writerow(["value1", "value2"])
            temp_file = f.name
        
        with pytest.raises(ValueError, match="Required columns not found"):
            parser.parse_csv(temp_file, tax_year=2023)
        
        # Cleanup
        Path(temp_file).unlink()

    def test_parse_decimal_various_formats(self, parser):
        """Test decimal parsing with various number formats."""
        assert parser._parse_decimal("1000") == Decimal("1000")
        assert parser._parse_decimal("1000.50") == Decimal("1000.50")
        assert parser._parse_decimal("1.000,50") == Decimal("1000.50")  # German format
        assert parser._parse_decimal("1,000.50") == Decimal("1000.50")  # US format
        assert parser._parse_decimal("€ 1.000,50") == Decimal("1000.50")
        assert parser._parse_decimal("1000.50 EUR") == Decimal("1000.50")
        assert parser._parse_decimal("-1000.50") == Decimal("-1000.50")
        assert parser._parse_decimal("") == Decimal("0")
        assert parser._parse_decimal(None) == Decimal("0")
        assert parser._parse_decimal(1000.50) == Decimal("1000.50")

    def test_calculate_confidence(self, parser):
        """Test confidence calculation."""
        # High confidence: all fields valid
        accounts = [
            AccountBalance(
                account_number="1000",
                account_name="Kassa",
                balance=Decimal("5000"),
                kontenklasse=1,
            ),
            AccountBalance(
                account_number="2000",
                account_name="Bank",
                balance=Decimal("10000"),
                kontenklasse=2,
            ),
        ]
        confidence = parser._calculate_confidence(accounts)
        assert confidence > 0.8
        
        # Low confidence: missing data
        accounts_low = [
            AccountBalance(
                account_number="1",
                account_name="",
                balance=Decimal("0"),
                kontenklasse=None,
            ),
        ]
        confidence_low = parser._calculate_confidence(accounts_low)
        assert confidence_low < 0.5
        
        # Zero confidence: empty list
        assert parser._calculate_confidence([]) == 0.0

    def test_parse_csv_with_german_number_format(self, parser):
        """Test parsing CSV with German number format (comma as decimal separator)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Konto", "Bezeichnung", "Saldo"])
            writer.writerow(["1000", "Kassa", "5.000,00"])
            writer.writerow(["2000", "Bank", "15.000,50"])
            temp_file = f.name
        
        result = parser.parse_csv(temp_file, tax_year=2023)
        
        assert len(result.accounts) == 2
        assert result.accounts[0].balance == Decimal("5000.00")
        assert result.accounts[1].balance == Decimal("15000.50")
        
        # Cleanup
        Path(temp_file).unlink()

    def test_account_balance_dataclass(self):
        """Test AccountBalance dataclass creation."""
        account = AccountBalance(
            account_number="1000",
            account_name="Kassa",
            balance=Decimal("5000"),
            kontenklasse=1,
        )
        
        assert account.account_number == "1000"
        assert account.account_name == "Kassa"
        assert account.balance == Decimal("5000")
        assert account.kontenklasse == 1
        assert account.debit_balance is None
        assert account.credit_balance is None

    def test_saldenliste_data_dataclass(self):
        """Test SaldenlisteData dataclass creation."""
        data = SaldenlisteData(
            tax_year=2023,
            company_name="Test Company",
            accounts=[],
            confidence=0.95,
            format_detected=SaldenlisteFormat.BMD,
        )
        
        assert data.tax_year == 2023
        assert data.company_name == "Test Company"
        assert data.accounts == []
        assert data.confidence == 0.95
        assert data.format_detected == SaldenlisteFormat.BMD
