"""
Unit Tests for CSV Import

Tests various Austrian bank CSV formats and duplicate detection.
"""

import pytest
from decimal import Decimal
from datetime import datetime

from app.services.csv_parser import CSVParser, BankFormat
from app.services.bank_import_service import BankImportService, ImportFormat


class TestCSVParser:
    """Test CSV parser with various bank formats"""
    
    def test_parse_raiffeisen_format(self):
        """Test parsing Raiffeisen bank CSV format"""
        
        csv_content = """Buchungsdatum;Betrag;Buchungstext;Referenz
31.12.2026;-123,45;BILLA DANKT 1234;REF123
15.12.2026;2500,00;Gehalt Dezember;SAL456
01.12.2026;-45,90;HOFER 5678;REF789"""
        
        parser = CSVParser(bank_format=BankFormat.RAIFFEISEN)
        transactions = parser.parse(csv_content)
        
        assert len(transactions) == 3
        
        # Check first transaction
        assert transactions[0]["date"] == datetime(2026, 12, 31)
        assert transactions[0]["amount"] == Decimal("-123.45")
        assert "BILLA" in transactions[0]["description"]
        assert transactions[0]["reference"] == "REF123"
        
        # Check second transaction
        assert transactions[1]["date"] == datetime(2026, 12, 15)
        assert transactions[1]["amount"] == Decimal("2500.00")
        assert "Gehalt" in transactions[1]["description"]
    
    def test_parse_erste_bank_format(self):
        """Test parsing Erste Bank CSV format"""
        
        csv_content = """Valutadatum;Betrag;Verwendungszweck;Belegnummer
31.12.2026;-50,00;SPAR DANKT;BEL001
20.12.2026;1500,00;Miete Jänner 2027;BEL002"""
        
        parser = CSVParser(bank_format=BankFormat.ERSTE_BANK)
        transactions = parser.parse(csv_content)
        
        assert len(transactions) == 2
        assert transactions[0]["amount"] == Decimal("-50.00")
        assert transactions[1]["amount"] == Decimal("1500.00")
    
    def test_parse_sparkasse_format(self):
        """Test parsing Sparkasse CSV format"""
        
        csv_content = """Buchungstag;Betrag;Verwendungszweck
31.12.2026;-100,00;OBI Baumarkt
15.12.2026;3000,00;Lohn Dezember"""
        
        parser = CSVParser(bank_format=BankFormat.SPARKASSE)
        transactions = parser.parse(csv_content)
        
        assert len(transactions) == 2
        assert "OBI" in transactions[0]["description"]
    
    def test_parse_bank_austria_format(self):
        """Test parsing Bank Austria CSV format"""
        
        csv_content = """Buchungsdatum;Betrag;Buchungstext;Referenznummer
31/12/2026;-75,50;MERKUR;REF999
01/12/2026;2000,00;Gehalt;REF888"""
        
        parser = CSVParser(bank_format=BankFormat.BANK_AUSTRIA)
        transactions = parser.parse(csv_content)
        
        assert len(transactions) == 2
        assert transactions[0]["date"] == datetime(2026, 12, 31)
    
    def test_auto_detect_bank_format(self):
        """Test automatic bank format detection"""
        
        # Erste Bank format with Valutadatum
        csv_content = """Valutadatum;Betrag;Verwendungszweck
31.12.2026;-50,00;Test"""
        
        parser = CSVParser()  # No format specified
        transactions = parser.parse(csv_content)
        
        assert parser.bank_format == BankFormat.ERSTE_BANK
        assert len(transactions) == 1
    
    def test_parse_different_date_formats(self):
        """Test parsing various date formats"""
        
        test_cases = [
            ("31.12.2026", datetime(2026, 12, 31)),
            ("31/12/2026", datetime(2026, 12, 31)),
            ("2026-12-31", datetime(2026, 12, 31)),
            ("31-12-2026", datetime(2026, 12, 31)),
            ("31.12.26", datetime(2026, 12, 31)),
        ]
        
        parser = CSVParser()
        
        for date_str, expected_date in test_cases:
            parsed_date = parser._parse_date(date_str)
            assert parsed_date == expected_date, f"Failed to parse {date_str}"
    
    def test_parse_austrian_decimal_format(self):
        """Test parsing Austrian decimal format (comma as decimal separator)"""
        
        test_cases = [
            ("123,45", Decimal("123.45")),
            ("1.234,56", Decimal("1234.56")),
            ("10.000,00", Decimal("10000.00")),
            ("-50,99", Decimal("-50.99")),
            ("€ 100,00", Decimal("100.00")),
            ("EUR 250,50", Decimal("250.50")),
        ]
        
        parser = CSVParser()
        
        for amount_str, expected_amount in test_cases:
            parsed_amount = parser._parse_amount(amount_str)
            assert parsed_amount == expected_amount, f"Failed to parse {amount_str}"
    
    def test_parse_international_decimal_format(self):
        """Test parsing international decimal format (dot as decimal separator)"""
        
        test_cases = [
            ("123.45", Decimal("123.45")),
            ("1,234.56", Decimal("1234.56")),
            ("10,000.00", Decimal("10000.00")),
        ]
        
        parser = CSVParser()
        
        for amount_str, expected_amount in test_cases:
            parsed_amount = parser._parse_amount(amount_str)
            assert parsed_amount == expected_amount, f"Failed to parse {amount_str}"
    
    def test_parse_with_comma_delimiter(self):
        """Test parsing CSV with comma delimiter"""
        
        csv_content = """Date,Amount,Description
31.12.2026,-123.45,BILLA
15.12.2026,2500.00,Salary"""
        
        parser = CSVParser()
        transactions = parser.parse(csv_content)
        
        assert len(transactions) == 2
    
    def test_parse_with_tab_delimiter(self):
        """Test parsing CSV with tab delimiter"""
        
        csv_content = """Date\tAmount\tDescription
31.12.2026\t-123,45\tBILLA
15.12.2026\t2500,00\tSalary"""
        
        parser = CSVParser()
        transactions = parser.parse(csv_content)
        
        assert len(transactions) == 2
    
    def test_validate_csv_success(self):
        """Test CSV validation with valid file"""
        
        csv_content = """Datum;Betrag;Text
31.12.2026;-100,00;BILLA
15.12.2026;2500,00;Gehalt"""
        
        parser = CSVParser()
        validation = parser.validate_csv(csv_content)
        
        assert validation["valid"] is True
        assert validation["transaction_count"] == 2
        assert validation["date_range"]["start"] == datetime(2026, 12, 15)
        assert validation["date_range"]["end"] == datetime(2026, 12, 31)
    
    def test_validate_csv_failure(self):
        """Test CSV validation with invalid file"""
        
        csv_content = """Invalid CSV content without proper structure"""
        
        parser = CSVParser()
        validation = parser.validate_csv(csv_content)
        
        assert validation["valid"] is False
        assert "error" in validation
    
    def test_skip_invalid_rows(self):
        """Test that parser skips invalid rows but continues parsing"""
        
        csv_content = """Datum;Betrag;Text
31.12.2026;-100,00;BILLA
invalid;row;here
15.12.2026;2500,00;Gehalt
another;invalid;row
01.12.2026;-50,00;SPAR"""
        
        parser = CSVParser()
        transactions = parser.parse(csv_content)
        
        # Should parse 3 valid transactions and skip 2 invalid rows
        assert len(transactions) == 3


class TestBankImportService:
    """Test bank import service with duplicate detection"""
    
    def test_import_csv_transactions(self):
        """Test importing transactions from CSV"""
        
        csv_content = """Datum;Betrag;Text
31.12.2026;-100,00;BILLA DANKT
15.12.2026;2500,00;Gehalt Dezember"""
        
        # Mock user object
        class MockUser:
            id = 1
            user_type = "employee"
        
        service = BankImportService()
        result = service.import_transactions(
            file_content=csv_content,
            import_format=ImportFormat.CSV,
            user=MockUser(),
            tax_year=2026,
            auto_classify=True,
            skip_duplicates=True,
        )
        
        assert result.total_count == 2
        assert result.imported_count == 2
        assert result.duplicate_count == 0
        assert result.error_count == 0
    
    def test_duplicate_detection(self):
        """Test duplicate transaction detection during import"""
        
        csv_content = """Datum;Betrag;Text
31.12.2026;-100,00;BILLA DANKT
31.12.2026;-100,00;BILLA DANKT
15.12.2026;2500,00;Gehalt"""
        
        class MockUser:
            id = 1
            user_type = "employee"
        
        service = BankImportService()
        result = service.import_transactions(
            file_content=csv_content,
            import_format=ImportFormat.CSV,
            user=MockUser(),
            tax_year=2026,
            auto_classify=True,
            skip_duplicates=True,
        )
        
        # Should detect second BILLA transaction as duplicate
        assert result.total_count == 3
        assert result.imported_count == 2
        assert result.duplicate_count == 1
    
    def test_import_without_duplicate_check(self):
        """Test importing without duplicate detection"""
        
        csv_content = """Datum;Betrag;Text
31.12.2026;-100,00;BILLA
31.12.2026;-100,00;BILLA"""
        
        class MockUser:
            id = 1
            user_type = "employee"
        
        service = BankImportService()
        result = service.import_transactions(
            file_content=csv_content,
            import_format=ImportFormat.CSV,
            user=MockUser(),
            tax_year=2026,
            auto_classify=True,
            skip_duplicates=False,  # Disable duplicate check
        )
        
        # Should import both transactions
        assert result.imported_count == 2
        assert result.duplicate_count == 0
    
    def test_preview_import(self):
        """Test preview import functionality"""
        
        csv_content = """Datum;Betrag;Text
31.12.2026;-100,00;BILLA
31.12.2026;-50,00;SPAR
15.12.2026;2500,00;Gehalt
01.12.2026;1500,00;Miete"""
        
        service = BankImportService()
        preview = service.preview_import(
            file_content=csv_content,
            import_format=ImportFormat.CSV,
        )
        
        assert preview["valid"] is True
        assert preview["total_count"] == 4
        assert preview["income_count"] == 2
        assert preview["expense_count"] == 2
        assert Decimal(preview["total_income"]) == Decimal("4000.00")
        assert Decimal(preview["total_expenses"]) == Decimal("150.00")
        assert len(preview["sample_transactions"]) == 4
    
    def test_import_with_classification(self):
        """Test that imported transactions are auto-classified"""
        
        csv_content = """Datum;Betrag;Text
31.12.2026;-100,00;BILLA DANKT
15.12.2026;2500,00;Gehalt Dezember"""
        
        class MockUser:
            id = 1
            user_type = "employee"
        
        service = BankImportService()
        result = service.import_transactions(
            file_content=csv_content,
            import_format=ImportFormat.CSV,
            user=MockUser(),
            tax_year=2026,
            auto_classify=True,
            skip_duplicates=True,
        )
        
        # Check that transactions have categories assigned
        for transaction in result.transactions:
            if transaction.type.value == "expense":
                assert transaction.expense_category is not None
            else:
                assert transaction.income_category is not None
    
    def test_import_error_handling(self):
        """Test error handling during import"""
        
        # Invalid CSV content
        csv_content = """This is not a valid CSV file"""
        
        class MockUser:
            id = 1
            user_type = "employee"
        
        service = BankImportService()
        result = service.import_transactions(
            file_content=csv_content,
            import_format=ImportFormat.CSV,
            user=MockUser(),
            tax_year=2026,
            auto_classify=True,
            skip_duplicates=True,
        )
        
        assert result.error_count > 0
        assert len(result.errors) > 0


class TestBankFormatDetection:
    """Test automatic bank format detection"""
    
    def test_detect_raiffeisen(self):
        """Test detection of Raiffeisen format"""
        
        csv_content = """Buchungsdatum;Betrag;Buchungstext;Referenz
31.12.2026;-100,00;Test;REF123"""
        
        parser = CSVParser()
        transactions = parser.parse(csv_content)
        
        # Should auto-detect as Raiffeisen or Generic
        assert parser.bank_format in [BankFormat.RAIFFEISEN, BankFormat.GENERIC]
    
    def test_detect_erste_bank(self):
        """Test detection of Erste Bank format"""
        
        csv_content = """Valutadatum;Betrag;Verwendungszweck;Belegnummer
31.12.2026;-100,00;Test;BEL001"""
        
        parser = CSVParser()
        transactions = parser.parse(csv_content)
        
        assert parser.bank_format == BankFormat.ERSTE_BANK
    
    def test_detect_sparkasse(self):
        """Test detection of Sparkasse format"""
        
        csv_content = """Buchungstag;Betrag;Verwendungszweck
31.12.2026;-100,00;Test"""
        
        parser = CSVParser()
        transactions = parser.parse(csv_content)
        
        assert parser.bank_format == BankFormat.SPARKASSE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
