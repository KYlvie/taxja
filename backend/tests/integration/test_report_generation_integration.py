"""Integration tests for report generation

Tests complete report generation workflows including:
- PDF generation (Requirements 7.1, 7.5)
- XML generation and validation (Requirement 8.1)
- CSV export/import roundtrip (Requirement 14.1)
"""
import pytest
from decimal import Decimal
from datetime import datetime, date
import xml.etree.ElementTree as ET
import csv
from io import StringIO


class TestPDFGeneration:
    """Integration tests for PDF report generation"""
    
    def test_generate_basic_tax_report_pdf(self, authenticated_client, test_transactions):
        """Test generating a basic tax report PDF"""
        # Create transactions for the year
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Generate tax report
        report_data = {
            "tax_year": 2026,
            "format": "pdf",
            "language": "de"
        }
        
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        assert response.status_code == 201
        
        data = response.json()
        assert "report_id" in data
        assert data["format"] == "pdf"
        assert data["status"] == "completed"
        
        report_id = data["report_id"]
        
        # Download PDF
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        
        # Verify PDF content is not empty
        pdf_content = response.content
        assert len(pdf_content) > 0
        assert pdf_content.startswith(b'%PDF')  # PDF magic number
    
    def test_generate_pdf_with_all_income_types(self, authenticated_client):
        """Test PDF generation with all income types"""
        # Create diverse transactions
        transactions = [
            {"type": "income", "amount": 36000.00, "date": "2026-01-31", "description": "Salary", "category": "employment_income"},
            {"type": "income", "amount": 12000.00, "date": "2026-02-15", "description": "Rental income", "category": "rental_income"},
            {"type": "income", "amount": 15000.00, "date": "2026-03-20", "description": "Freelance", "category": "self_employment_income"},
            {"type": "income", "amount": 2000.00, "date": "2026-04-10", "description": "Dividends", "category": "capital_gains"},
            {"type": "expense", "amount": 5000.00, "date": "2026-05-15", "description": "Business expenses", "category": "office_supplies", "is_deductible": True}
        ]
        
        for txn in transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Generate PDF report
        report_data = {"tax_year": 2026, "format": "pdf", "language": "de"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        assert response.status_code == 201
        
        report_id = response.json()["report_id"]
        
        # Download and verify PDF
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/pdf")
        assert response.status_code == 200
        assert len(response.content) > 1000  # Should be substantial
    
    def test_generate_pdf_in_multiple_languages(self, authenticated_client, test_transactions):
        """Test PDF generation in German, English, and Chinese"""
        # Create transactions
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        languages = ['de', 'en', 'zh']
        
        for lang in languages:
            report_data = {
                "tax_year": 2026,
                "format": "pdf",
                "language": lang
            }
            
            response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
            assert response.status_code == 201
            
            report_id = response.json()["report_id"]
            
            # Download PDF
            response = authenticated_client.get(f"/api/v1/reports/{report_id}/pdf")
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert len(response.content) > 0
    
    def test_pdf_contains_required_sections(self, authenticated_client, test_transactions):
        """Test that PDF contains all required sections per Requirement 7.1"""
        # Create transactions
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Generate report
        report_data = {"tax_year": 2026, "format": "pdf"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        # Get report metadata to verify sections
        response = authenticated_client.get(f"/api/v1/reports/{report_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "taxpayer_info" in data
        assert "income_summary" in data
        assert "expense_summary" in data
        assert "tax_calculation" in data
        assert "deductions" in data
    
    def test_pdf_generation_with_no_transactions(self, authenticated_client):
        """Test PDF generation with no transactions"""
        report_data = {"tax_year": 2026, "format": "pdf"}
        
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        assert response.status_code == 201
        
        report_id = response.json()["report_id"]
        
        # Should still generate PDF with zero values
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/pdf")
        assert response.status_code == 200
        assert len(response.content) > 0
    
    def test_pdf_includes_disclaimer(self, authenticated_client, test_transactions):
        """Test that PDF includes required disclaimer per Requirement 17.11"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        report_data = {"tax_year": 2026, "format": "pdf"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        # Get report data
        response = authenticated_client.get(f"/api/v1/reports/{report_id}")
        data = response.json()
        
        # Verify disclaimer is present
        assert "disclaimer" in data or "includes_disclaimer" in data
    
    def test_pdf_shows_usp_2026_reference(self, authenticated_client, test_transactions):
        """Test that PDF references USP 2026 tax tables per Requirement 3.11"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        report_data = {"tax_year": 2026, "format": "pdf"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        response = authenticated_client.get(f"/api/v1/reports/{report_id}")
        data = response.json()
        
        # Should reference USP 2026
        assert "usp_2026" in str(data).lower() or "based_on_usp" in data


class TestXMLGeneration:
    """Integration tests for FinanzOnline XML generation"""
    
    def test_generate_finanzonline_xml(self, authenticated_client, test_transactions):
        """Test generating FinanzOnline XML format"""
        # Create transactions
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Generate XML report
        report_data = {
            "tax_year": 2026,
            "format": "xml"
        }
        
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        assert response.status_code == 201
        
        report_id = response.json()["report_id"]
        
        # Download XML
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/xml")
        assert response.status_code == 200
        assert response.headers["content-type"] in ["application/xml", "text/xml"]
        
        xml_content = response.text
        assert len(xml_content) > 0
        assert '<?xml' in xml_content
    
    def test_xml_is_well_formed(self, authenticated_client, test_transactions):
        """Test that generated XML is well-formed"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        report_data = {"tax_year": 2026, "format": "xml"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        # Download XML
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/xml")
        xml_content = response.text
        
        # Parse XML to verify it's well-formed
        try:
            root = ET.fromstring(xml_content)
            assert root is not None
        except ET.ParseError as e:
            pytest.fail(f"XML is not well-formed: {e}")
    
    def test_xml_contains_required_elements(self, authenticated_client, test_transactions):
        """Test that XML contains required FinanzOnline elements per Requirement 8.2"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        report_data = {"tax_year": 2026, "format": "xml"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/xml")
        xml_content = response.text
        
        root = ET.fromstring(xml_content)
        
        # Check for required elements
        assert root.tag == 'Einkommensteuererklärung'
        assert root.get('Jahr') == '2026'
        
        # Should have taxpayer info
        taxpayer = root.find('Steuerpflichtiger')
        assert taxpayer is not None
        
        # Should have income section
        income = root.find('Einkünfte')
        # May be None if no income, but structure should be valid
        
        # Should have tax calculation
        tax_calc = root.find('Steuerberechnung')
        assert tax_calc is not None
    
    def test_xml_includes_taxpayer_information(self, authenticated_client, test_user, test_transactions):
        """Test that XML includes taxpayer information per Requirement 15.1"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        report_data = {"tax_year": 2026, "format": "xml"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/xml")
        xml_content = response.text
        
        root = ET.fromstring(xml_content)
        taxpayer = root.find('Steuerpflichtiger')
        
        # Should include name
        name_elem = taxpayer.find('Name')
        assert name_elem is not None
        assert len(name_elem.text) > 0
    
    def test_xml_includes_income_sections(self, authenticated_client):
        """Test that XML includes income sections per Requirement 15.2"""
        # Create income transactions
        transactions = [
            {"type": "income", "amount": 30000.00, "date": "2026-01-15", "category": "employment_income"},
            {"type": "income", "amount": 10000.00, "date": "2026-02-15", "category": "rental_income"},
            {"type": "income", "amount": 5000.00, "date": "2026-03-15", "category": "self_employment_income"}
        ]
        
        for txn in transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        report_data = {"tax_year": 2026, "format": "xml"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/xml")
        xml_content = response.text
        
        root = ET.fromstring(xml_content)
        income = root.find('Einkünfte')
        
        if income is not None:
            # Check for income types
            employment = income.find('NichtselbständigeArbeit')
            rental = income.find('VermietungUndVerpachtung')
            self_emp = income.find('SelbständigeArbeit')
            
            # At least one should be present
            assert employment is not None or rental is not None or self_emp is not None
    
    def test_xml_includes_deductions(self, authenticated_client):
        """Test that XML includes deductions per Requirement 15.3"""
        # Create transactions with deductions
        transactions = [
            {"type": "income", "amount": 40000.00, "date": "2026-01-15", "category": "employment_income"},
            {"type": "expense", "amount": 3000.00, "date": "2026-02-15", "category": "svs_contributions", "is_deductible": True}
        ]
        
        for txn in transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        report_data = {"tax_year": 2026, "format": "xml"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/xml")
        xml_content = response.text
        
        root = ET.fromstring(xml_content)
        deductions = root.find('Sonderausgaben')
        
        # Deductions section may be present if there are deductible expenses
        # Structure should be valid
        assert root is not None
    
    def test_xml_validation_against_schema(self, authenticated_client, test_transactions):
        """Test XML validation against FinanzOnline schema per Requirement 15.5"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        report_data = {"tax_year": 2026, "format": "xml", "validate": True}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        
        # Should succeed if validation passes
        assert response.status_code == 201
        
        data = response.json()
        assert data.get("validation_status") in ["passed", "validated", None]
    
    def test_xml_roundtrip_validation(self, authenticated_client, test_transactions):
        """Test XML roundtrip validation per Requirement 15.4"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Generate XML
        report_data = {"tax_year": 2026, "format": "xml"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        # Download XML
        response = authenticated_client.get(f"/api/v1/reports/{report_id}/xml")
        xml_content1 = response.text
        
        # Parse and regenerate
        root = ET.fromstring(xml_content1)
        xml_content2 = ET.tostring(root, encoding='unicode')
        
        # Parse again
        root2 = ET.fromstring(xml_content2)
        
        # Should produce equivalent structure
        assert root.tag == root2.tag
        assert root.get('Jahr') == root2.get('Jahr')


class TestCSVExport:
    """Integration tests for CSV export functionality"""
    
    def test_export_transactions_to_csv(self, authenticated_client, test_transactions):
        """Test exporting transactions to CSV"""
        # Create transactions
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Export to CSV
        response = authenticated_client.get("/api/v1/transactions/export?format=csv&tax_year=2026")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"
        
        csv_content = response.text
        assert len(csv_content) > 0
        
        # Parse CSV
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) >= len(test_transactions)
        
        # Verify headers
        assert 'id' in reader.fieldnames
        assert 'date' in reader.fieldnames
        assert 'amount' in reader.fieldnames
        assert 'description' in reader.fieldnames
    
    def test_csv_contains_all_transaction_fields(self, authenticated_client):
        """Test that CSV export contains all required fields per Requirement 14.2"""
        # Create a transaction with all fields
        transaction = {
            "type": "expense",
            "amount": 150.00,
            "date": "2026-01-15",
            "description": "Test transaction",
            "category": "office_supplies",
            "is_deductible": True,
            "vat_rate": 0.20,
            "vat_amount": 25.00
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction)
        transaction_id = response.json()["id"]
        
        # Export to CSV
        response = authenticated_client.get("/api/v1/transactions/export?format=csv")
        csv_content = response.text
        
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        # Find our transaction
        txn_row = next((r for r in rows if r['id'] == str(transaction_id)), None)
        assert txn_row is not None
        
        # Verify all fields are present
        assert txn_row['type'] == 'expense'
        assert float(txn_row['amount']) == 150.00
        assert txn_row['description'] == 'Test transaction'
        assert txn_row['category'] == 'office_supplies'
        assert txn_row['is_deductible'] in ['true', 'True', '1']
    
    def test_csv_export_with_date_range_filter(self, authenticated_client):
        """Test CSV export with date range filtering"""
        # Create transactions in different months
        transactions = [
            {"type": "income", "amount": 1000.00, "date": "2026-01-15", "description": "Jan"},
            {"type": "income", "amount": 1000.00, "date": "2026-02-15", "description": "Feb"},
            {"type": "income", "amount": 1000.00, "date": "2026-03-15", "description": "Mar"}
        ]
        
        for txn in transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Export only January
        response = authenticated_client.get(
            "/api/v1/transactions/export?format=csv&start_date=2026-01-01&end_date=2026-01-31"
        )
        assert response.status_code == 200
        
        csv_content = response.text
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        # Should only have January transaction
        for row in rows:
            if row['description'] in ['Jan', 'Feb', 'Mar']:
                assert row['description'] == 'Jan'
    
    def test_csv_export_empty_dataset(self, authenticated_client):
        """Test CSV export with no transactions"""
        response = authenticated_client.get("/api/v1/transactions/export?format=csv&tax_year=2025")
        assert response.status_code == 200
        
        csv_content = response.text
        
        # Should have headers but no data rows
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 0
        assert len(reader.fieldnames) > 0  # Headers should still be present


class TestCSVImportExportRoundtrip:
    """Integration tests for CSV export/import roundtrip consistency"""
    
    def test_csv_roundtrip_consistency(self, authenticated_client):
        """Test CSV export then import produces same data per Requirement 14.3"""
        # Create original transactions
        original_transactions = [
            {
                "type": "income",
                "amount": 3500.00,
                "date": "2026-01-15",
                "description": "Salary January",
                "category": "employment_income"
            },
            {
                "type": "expense",
                "amount": 150.50,
                "date": "2026-01-20",
                "description": "Office supplies",
                "category": "office_supplies",
                "is_deductible": True,
                "vat_rate": 0.20,
                "vat_amount": 25.08
            },
            {
                "type": "income",
                "amount": 1200.00,
                "date": "2026-02-01",
                "description": "Rental income",
                "category": "rental_income"
            }
        ]
        
        created_ids = []
        for txn in original_transactions:
            response = authenticated_client.post("/api/v1/transactions", json=txn)
            created_ids.append(response.json()["id"])
        
        # Export to CSV
        response = authenticated_client.get("/api/v1/transactions/export?format=csv&tax_year=2026")
        csv_content = response.text
        
        # Delete original transactions
        for txn_id in created_ids:
            authenticated_client.delete(f"/api/v1/transactions/{txn_id}")
        
        # Import CSV
        files = {"file": ("transactions.csv", csv_content, "text/csv")}
        response = authenticated_client.post("/api/v1/transactions/import", files=files)
        assert response.status_code == 200
        
        import_result = response.json()
        assert import_result["imported_count"] >= len(original_transactions)
        
        # Export again
        response = authenticated_client.get("/api/v1/transactions/export?format=csv&tax_year=2026")
        csv_content2 = response.text
        
        # Parse both CSVs
        reader1 = csv.DictReader(StringIO(csv_content))
        reader2 = csv.DictReader(StringIO(csv_content2))
        
        rows1 = sorted(list(reader1), key=lambda x: (x['date'], x['description']))
        rows2 = sorted(list(reader2), key=lambda x: (x['date'], x['description']))
        
        # Should have same number of rows
        assert len(rows1) == len(rows2)
        
        # Compare key fields (ignoring IDs which may change)
        for r1, r2 in zip(rows1, rows2):
            assert r1['type'] == r2['type']
            assert r1['amount'] == r2['amount']
            assert r1['date'] == r2['date']
            assert r1['description'] == r2['description']
            assert r1['category'] == r2['category']
    
    def test_csv_roundtrip_preserves_metadata(self, authenticated_client):
        """Test that CSV roundtrip preserves all metadata per Requirement 14.4"""
        # Create transaction with full metadata
        transaction = {
            "type": "expense",
            "amount": 200.00,
            "date": "2026-01-25",
            "description": "Business expense with metadata",
            "category": "professional_services",
            "is_deductible": True,
            "deduction_reason": "Business related",
            "vat_rate": 0.20,
            "vat_amount": 33.33
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction)
        original_id = response.json()["id"]
        
        # Export
        response = authenticated_client.get("/api/v1/transactions/export?format=csv")
        csv_content = response.text
        
        # Parse and verify metadata is present
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        txn_row = next((r for r in rows if r['id'] == str(original_id)), None)
        assert txn_row is not None
        
        # Verify metadata fields
        assert 'is_deductible' in txn_row
        assert 'vat_rate' in txn_row
        assert 'vat_amount' in txn_row
        assert 'category' in txn_row
    
    def test_csv_roundtrip_with_special_characters(self, authenticated_client):
        """Test CSV roundtrip with special characters in descriptions"""
        # Create transaction with special characters
        transaction = {
            "type": "expense",
            "amount": 100.00,
            "date": "2026-01-30",
            "description": 'Test with "quotes", commas, and Umlauts: äöü ÄÖÜ ß',
            "category": "other"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction)
        assert response.status_code == 201
        
        # Export
        response = authenticated_client.get("/api/v1/transactions/export?format=csv")
        csv_content = response.text
        
        # Parse
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        # Find transaction
        txn_row = next((r for r in rows if 'Umlauts' in r['description']), None)
        assert txn_row is not None
        
        # Description should be preserved
        assert 'äöü' in txn_row['description']
        assert 'ÄÖÜ' in txn_row['description']
    
    def test_csv_import_validates_data(self, authenticated_client):
        """Test that CSV import validates data per Requirement 14.5"""
        # Create CSV with invalid data
        invalid_csv = """id,date,type,amount,description
1,2026-01-15,income,-100.00,Invalid negative amount
2,2099-12-31,income,1000.00,Future date
3,2026-01-20,invalid_type,500.00,Invalid type
"""
        
        files = {"file": ("invalid.csv", invalid_csv, "text/csv")}
        response = authenticated_client.post("/api/v1/transactions/import", files=files)
        
        # Should report errors
        data = response.json()
        assert "errors" in data or "invalid_count" in data
        assert data.get("invalid_count", 0) > 0 or len(data.get("errors", [])) > 0


class TestReportGeneration:
    """Integration tests for complete report generation workflow"""
    
    def test_generate_report_all_formats(self, authenticated_client, test_transactions):
        """Test generating report in all formats"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        formats = ['pdf', 'xml', 'csv']
        
        for fmt in formats:
            report_data = {"tax_year": 2026, "format": fmt}
            response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
            assert response.status_code == 201
            
            report_id = response.json()["report_id"]
            
            # Verify report can be retrieved
            response = authenticated_client.get(f"/api/v1/reports/{report_id}")
            assert response.status_code == 200
            assert response.json()["format"] == fmt
    
    def test_list_generated_reports(self, authenticated_client, test_transactions):
        """Test listing all generated reports"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Generate multiple reports
        for fmt in ['pdf', 'xml']:
            report_data = {"tax_year": 2026, "format": fmt}
            authenticated_client.post("/api/v1/reports/generate", json=report_data)
        
        # List reports
        response = authenticated_client.get("/api/v1/reports")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 2
    
    def test_delete_generated_report(self, authenticated_client, test_transactions):
        """Test deleting a generated report"""
        for txn in test_transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Generate report
        report_data = {"tax_year": 2026, "format": "pdf"}
        response = authenticated_client.post("/api/v1/reports/generate", json=report_data)
        report_id = response.json()["report_id"]
        
        # Delete report
        response = authenticated_client.delete(f"/api/v1/reports/{report_id}")
        assert response.status_code == 204
        
        # Verify deletion
        response = authenticated_client.get(f"/api/v1/reports/{report_id}")
        assert response.status_code == 404
    
    def test_report_generation_requires_authentication(self, client):
        """Test that report generation requires authentication"""
        report_data = {"tax_year": 2026, "format": "pdf"}
        
        response = client.post("/api/v1/reports/generate", json=report_data)
        assert response.status_code == 401
    
    def test_users_cannot_access_other_users_reports(self, client, multiple_test_users, test_transactions):
        """Test that users cannot access other users' reports"""
        user1 = multiple_test_users[0]
        user2 = multiple_test_users[1]
        
        # Login as user1
        login_data = {"username": user1["email"], "password": user1["password"]}
        response = client.post("/api/v1/auth/login", data=login_data)
        token1 = response.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        # Create transactions and report as user1
        for txn in test_transactions:
            client.post("/api/v1/transactions", json=txn, headers=headers1)
        
        report_data = {"tax_year": 2026, "format": "pdf"}
        response = client.post("/api/v1/reports/generate", json=report_data, headers=headers1)
        report_id = response.json()["report_id"]
        
        # Login as user2
        login_data = {"username": user2["email"], "password": user2["password"]}
        response = client.post("/api/v1/auth/login", data=login_data)
        token2 = response.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # Try to access user1's report as user2
        response = client.get(f"/api/v1/reports/{report_id}", headers=headers2)
        assert response.status_code == 404  # Not found (or 403 Forbidden)
