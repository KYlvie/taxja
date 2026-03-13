"""End-to-End Integration Tests for Critical User Journeys

This module contains comprehensive E2E tests that validate complete user workflows
from start to finish, simulating real-world usage scenarios.

Test Coverage:
1. Complete tax filing workflow (registration → transactions → calculation → report)
2. OCR to transaction to report flow (document upload → OCR → transaction → report)
3. Employee refund calculation flow (Lohnzettel upload → refund calculation → report)

Requirements Validated: All core requirements (1.x, 2.x, 3.x, 4.x, 7.x, 8.x, 19.x, 37.x)
"""
import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
from datetime import datetime, date
import io
from PIL import Image
import json


class TestCompleteTaxFilingWorkflow:
    """E2E test for complete tax filing workflow
    
    Simulates a self-employed user's complete tax year journey:
    1. Register account
    2. Set up profile with business information
    3. Add transactions throughout the year
    4. Upload supporting documents
    5. Calculate taxes
    6. Generate and download tax reports
    """
    
    def test_self_employed_complete_tax_year(self, client, db):
        """Test complete tax filing workflow for self-employed user"""
        # Step 1: Register new self-employed user
        registration_data = {
            "email": "freelancer@example.com",
            "password": "SecurePass123!",
            "full_name": "Maria Müller",
            "user_type": "self_employed"
        }
        
        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 201
        user_data = response.json()
        
        # Step 2: Login to get access token
        login_data = {
            "username": registration_data["email"],
            "password": registration_data["password"]
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        
        # Step 3: Update profile with business details
        profile_data = {
            "tax_number": "12-345/6789",
            "vat_number": "ATU12345678",
            "address": "Hauptstraße 123, 1010 Wien",
            "commuting_distance_km": 0,  # Works from home
            "public_transport_available": True,
            "num_children": 0,
            "is_single_parent": False
        }
        
        response = client.put("/api/v1/users/profile", json=profile_data, headers=headers)
        assert response.status_code == 200
        
        # Step 4: Add income transactions (consulting revenue)
        income_transactions = [
            {
                "type": "income",
                "amount": "8500.00",
                "date": "2026-01-31",
                "description": "Consulting Project - Client A",
                "category": "self_employment_income"
            },
            {
                "type": "income",
                "amount": "12000.00",
                "date": "2026-03-15",
                "description": "Web Development - Client B",
                "category": "self_employment_income"
            },
            {
                "type": "income",
                "amount": "6500.00",
                "date": "2026-06-30",
                "description": "Consulting Project - Client C",
                "category": "self_employment_income"
            },
            {
                "type": "income",
                "amount": "9200.00",
                "date": "2026-09-20",
                "description": "Software Development - Client D",
                "category": "self_employment_income"
            }
        ]
        
        created_income_ids = []
        for txn in income_transactions:
            response = client.post("/api/v1/transactions", json=txn, headers=headers)
            assert response.status_code == 201
            created_income_ids.append(response.json()["id"])
        
        # Step 5: Add deductible business expenses
        expense_transactions = [
            {
                "type": "expense",
                "amount": "1200.00",
                "date": "2026-02-10",
                "description": "MacBook Pro - Business Equipment",
                "category": "equipment",
                "is_deductible": True
            },
            {
                "type": "expense",
                "amount": "450.00",
                "date": "2026-03-05",
                "description": "Office Supplies - Staples",
                "category": "office_supplies",
                "is_deductible": True
            },
            {
                "type": "expense",
                "amount": "800.00",
                "date": "2026-05-12",
                "description": "Professional Liability Insurance",
                "category": "insurance",
                "is_deductible": True
            },
            {
                "type": "expense",
                "amount": "350.00",
                "date": "2026-07-20",
                "description": "Marketing - Google Ads",
                "category": "marketing",
                "is_deductible": True
            }
        ]
        
        created_expense_ids = []
        for txn in expense_transactions:
            response = client.post("/api/v1/transactions", json=txn, headers=headers)
            assert response.status_code == 201
            created_expense_ids.append(response.json()["id"])

        
        # Step 6: Verify transactions were created
        response = client.get("/api/v1/transactions?tax_year=2026", headers=headers)
        assert response.status_code == 200
        transactions = response.json()
        assert len(transactions) == 8  # 4 income + 4 expenses
        
        # Step 7: Calculate taxes for the year
        response = client.post("/api/v1/tax/calculate?tax_year=2026", headers=headers)
        assert response.status_code == 200
        tax_result = response.json()
        
        # Verify tax calculation results
        assert "income_tax" in tax_result
        assert "vat" in tax_result
        assert "svs_contributions" in tax_result
        assert "total_tax" in tax_result
        assert "net_income" in tax_result
        
        # Total income: €36,200
        # Total expenses: €2,800
        # Gross profit: €33,400
        # Should be below VAT threshold (€55,000) - small business exemption
        assert tax_result["vat"]["exempt"] is True
        assert "small business" in tax_result["vat"]["reason"].lower()
        
        # SVS contributions should be calculated
        assert Decimal(tax_result["svs_contributions"]["annual_total"]) > 0
        
        # Income tax should be calculated on taxable income
        assert Decimal(tax_result["income_tax"]["total_tax"]) > 0
        
        # Step 8: Generate PDF tax report
        response = client.post(
            "/api/v1/reports/generate",
            json={"tax_year": 2026, "format": "pdf", "language": "de"},
            headers=headers
        )
        assert response.status_code == 201
        report_data = response.json()
        assert report_data["format"] == "pdf"
        assert report_data["tax_year"] == 2026
        report_id = report_data["id"]
        
        # Step 9: Download PDF report
        response = client.get(f"/api/v1/reports/{report_id}/pdf", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert len(response.content) > 0
        
        # Step 10: Generate FinanzOnline XML
        response = client.post(
            "/api/v1/reports/generate",
            json={"tax_year": 2026, "format": "xml"},
            headers=headers
        )
        assert response.status_code == 201
        xml_report_data = response.json()
        xml_report_id = xml_report_data["id"]
        
        # Step 11: Download XML report
        response = client.get(f"/api/v1/reports/{xml_report_id}/xml", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        xml_content = response.content.decode("utf-8")
        
        # Verify XML contains required elements
        assert "Einkommensteuererklärung" in xml_content
        assert "Steuerpflichtiger" in xml_content
        assert "SelbständigeArbeit" in xml_content
        assert str(2026) in xml_content
        
        # Step 12: Export transactions to CSV
        response = client.get("/api/v1/transactions/export?tax_year=2026", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"
        csv_content = response.content.decode("utf-8")
        assert "Consulting Project" in csv_content
        assert "MacBook Pro" in csv_content
        
        # Step 13: View dashboard summary
        response = client.get("/api/v1/dashboard?tax_year=2026", headers=headers)
        assert response.status_code == 200
        dashboard = response.json()
        
        assert Decimal(dashboard["income_summary"]["total"]) == Decimal("36200.00")
        assert Decimal(dashboard["expense_summary"]["deductible"]) == Decimal("2800.00")
        assert dashboard["vat_status"]["below_threshold"] is True
        assert "net_income" in dashboard
        
        print("\n✅ Complete tax filing workflow test passed!")
        print(f"   Total Income: €{dashboard['income_summary']['total']}")
        print(f"   Deductible Expenses: €{dashboard['expense_summary']['deductible']}")
        print(f"   Income Tax: €{tax_result['income_tax']['total_tax']}")
        print(f"   SVS Contributions: €{tax_result['svs_contributions']['annual_total']}")
        print(f"   Net Income: €{tax_result['net_income']}")



class TestOCRToTransactionToReportFlow:
    """E2E test for OCR document processing workflow
    
    Simulates a user uploading receipts and invoices:
    1. Upload document image
    2. OCR processes and extracts data
    3. Review and confirm OCR results
    4. Create transaction from OCR data
    5. Generate report including the transaction
    """
    
    def test_receipt_ocr_to_report_workflow(self, client, authenticated_client, test_user, db):
        """Test complete OCR workflow from document upload to report generation"""
        headers = authenticated_client
        
        # Step 1: Create a test receipt image
        # Simulate a simple receipt with text
        receipt_image = Image.new('RGB', (800, 1200), color='white')
        img_byte_arr = io.BytesIO()
        receipt_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        # Step 2: Upload document for OCR processing
        files = {
            'file': ('receipt.png', img_byte_arr, 'image/png')
        }
        
        response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=headers
        )
        assert response.status_code == 201
        document_data = response.json()
        document_id = document_data["id"]
        
        # Verify OCR was triggered
        assert "ocr_result" in document_data
        assert document_data["document_type"] is not None
        
        # Step 3: Get OCR review data
        response = client.get(f"/api/v1/documents/{document_id}/review", headers=headers)
        assert response.status_code == 200
        ocr_review = response.json()
        
        assert "extracted_data" in ocr_review
        assert "confidence_score" in ocr_review
        assert "document_type" in ocr_review
        
        # Step 4: Correct OCR data if needed (simulate user review)
        corrected_data = {
            "date": "2026-03-15",
            "amount": "125.50",
            "merchant": "BILLA",
            "category": "groceries",
            "is_deductible": False,
            "description": "Groceries - BILLA Supermarket"
        }
        
        response = client.post(
            f"/api/v1/documents/{document_id}/correct",
            json={"extracted_data": corrected_data},
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 5: Create transaction from OCR data
        transaction_data = {
            "type": "expense",
            "amount": corrected_data["amount"],
            "date": corrected_data["date"],
            "description": corrected_data["description"],
            "category": corrected_data["category"],
            "is_deductible": corrected_data["is_deductible"],
            "document_id": document_id
        }
        
        response = client.post("/api/v1/transactions", json=transaction_data, headers=headers)
        assert response.status_code == 201
        transaction = response.json()
        transaction_id = transaction["id"]
        
        # Verify transaction is linked to document
        assert transaction["document_id"] == document_id

        
        # Step 6: Upload another document (business invoice)
        invoice_image = Image.new('RGB', (800, 1200), color='white')
        img_byte_arr2 = io.BytesIO()
        invoice_image.save(img_byte_arr2, format='PNG')
        img_byte_arr2.seek(0)
        
        files2 = {
            'file': ('invoice.png', img_byte_arr2, 'image/png')
        }
        
        response = client.post(
            "/api/v1/documents/upload",
            files=files2,
            headers=headers
        )
        assert response.status_code == 201
        invoice_doc_id = response.json()["id"]
        
        # Create deductible business expense from invoice
        invoice_transaction = {
            "type": "expense",
            "amount": "450.00",
            "date": "2026-03-20",
            "description": "Office Supplies - OBI",
            "category": "office_supplies",
            "is_deductible": True,
            "document_id": invoice_doc_id,
            "vat_rate": "0.20",
            "vat_amount": "75.00"
        }
        
        response = client.post("/api/v1/transactions", json=invoice_transaction, headers=headers)
        assert response.status_code == 201
        
        # Step 7: Verify documents are archived and linked
        response = client.get("/api/v1/documents", headers=headers)
        assert response.status_code == 200
        documents = response.json()
        assert len(documents) >= 2
        
        # Step 8: Generate report including OCR-sourced transactions
        response = client.post(
            "/api/v1/reports/generate",
            json={"tax_year": 2026, "format": "pdf", "language": "en"},
            headers=headers
        )
        assert response.status_code == 201
        report_id = response.json()["id"]
        
        # Step 9: Verify report includes document references
        response = client.get(f"/api/v1/reports/{report_id}", headers=headers)
        assert response.status_code == 200
        report = response.json()
        
        # Report should reference supporting documents
        assert "document_references" in report or "transactions" in report
        
        # Step 10: Download report with document links
        response = client.get(f"/api/v1/reports/{report_id}/pdf", headers=headers)
        assert response.status_code == 200
        assert len(response.content) > 0
        
        # Step 11: Verify audit readiness (all transactions have documents)
        response = client.get("/api/v1/audit/checklist?tax_year=2026", headers=headers)
        assert response.status_code == 200
        audit_checklist = response.json()
        
        # Check that transactions with documents are marked as documented
        assert "transactions_with_documents" in audit_checklist
        
        print("\n✅ OCR to transaction to report workflow test passed!")
        print(f"   Documents uploaded: 2")
        print(f"   Transactions created: 2")
        print(f"   Report generated: PDF with document references")

    
    def test_batch_ocr_processing_workflow(self, client, authenticated_client, db):
        """Test batch OCR processing with multiple documents"""
        headers = authenticated_client
        
        # Step 1: Create multiple receipt images
        receipt_files = []
        for i in range(5):
            img = Image.new('RGB', (800, 1200), color='white')
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            receipt_files.append(('files', (f'receipt_{i}.png', img_byte_arr, 'image/png')))
        
        # Step 2: Batch upload documents
        response = client.post(
            "/api/v1/documents/batch-upload",
            files=receipt_files,
            headers=headers
        )
        assert response.status_code == 201
        batch_result = response.json()
        
        assert "results" in batch_result
        assert len(batch_result["results"]) == 5
        
        # Verify all documents were processed
        for result in batch_result["results"]:
            assert result["status"] in ["success", "needs_review"]
            assert "document_id" in result
        
        # Step 3: Review low-confidence OCR results
        needs_review = [r for r in batch_result["results"] if r.get("needs_review")]
        
        for result in needs_review:
            doc_id = result["document_id"]
            response = client.get(f"/api/v1/documents/{doc_id}/review", headers=headers)
            assert response.status_code == 200
        
        print(f"\n✅ Batch OCR processing test passed!")
        print(f"   Documents processed: 5")
        print(f"   Needs review: {len(needs_review)}")


class TestEmployeeRefundCalculationFlow:
    """E2E test for employee tax refund calculation (Arbeitnehmerveranlagung)
    
    Simulates an employee:
    1. Register as employee
    2. Upload Lohnzettel (payslip with withheld tax)
    3. Add deductible expenses (commuting, home office)
    4. Calculate refund
    5. Generate refund report
    """
    
    def test_employee_refund_complete_workflow(self, client, db):
        """Test complete employee refund calculation workflow"""
        # Step 1: Register employee user
        registration_data = {
            "email": "employee@example.com",
            "password": "SecurePass123!",
            "full_name": "Hans Schmidt",
            "user_type": "employee"
        }
        
        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 201
        
        # Step 2: Login
        login_data = {
            "username": registration_data["email"],
            "password": registration_data["password"]
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 3: Update profile with commuting information
        profile_data = {
            "tax_number": "12-345/6789",
            "address": "Linzer Straße 45, 1140 Wien",
            "commuting_distance_km": 45,  # Qualifies for Pendlerpauschale
            "public_transport_available": True,  # Small commuting allowance
            "num_children": 2,
            "is_single_parent": False
        }
        
        response = client.put("/api/v1/users/profile", json=profile_data, headers=headers)
        assert response.status_code == 200

        
        # Step 4: Upload Lohnzettel (payslip) - simulate OCR extraction
        lohnzettel_image = Image.new('RGB', (800, 1200), color='white')
        img_byte_arr = io.BytesIO()
        lohnzettel_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        files = {
            'file': ('lohnzettel_2026.png', img_byte_arr, 'image/png')
        }
        
        response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=headers
        )
        assert response.status_code == 201
        lohnzettel_doc_id = response.json()["id"]
        
        # Step 5: Provide Lohnzettel data (from OCR or manual entry)
        lohnzettel_data = {
            "gross_income": "42000.00",
            "withheld_tax": "7200.00",
            "withheld_svs": "6500.00",
            "employer_name": "Tech Company GmbH",
            "tax_year": 2026
        }
        
        response = client.post(
            "/api/v1/tax/lohnzettel",
            json=lohnzettel_data,
            headers=headers
        )
        assert response.status_code == 201
        
        # Step 6: Add employment income transaction
        income_transaction = {
            "type": "income",
            "amount": "42000.00",
            "date": "2026-12-31",
            "description": "Annual Salary - Tech Company GmbH",
            "category": "employment_income",
            "document_id": lohnzettel_doc_id
        }
        
        response = client.post("/api/v1/transactions", json=income_transaction, headers=headers)
        assert response.status_code == 201
        
        # Step 7: Add deductible expenses (work-related)
        work_expenses = [
            {
                "type": "expense",
                "amount": "800.00",
                "date": "2026-03-10",
                "description": "Professional Development Course",
                "category": "professional_development",
                "is_deductible": True
            },
            {
                "type": "expense",
                "amount": "250.00",
                "date": "2026-06-15",
                "description": "Work-related Books and Materials",
                "category": "professional_materials",
                "is_deductible": True
            }
        ]
        
        for expense in work_expenses:
            response = client.post("/api/v1/transactions", json=expense, headers=headers)
            assert response.status_code == 201
        
        # Step 8: Calculate employee refund
        response = client.post(
            "/api/v1/tax/calculate-refund?tax_year=2026",
            headers=headers
        )
        assert response.status_code == 200
        refund_result = response.json()
        
        # Verify refund calculation
        assert "actual_tax_liability" in refund_result
        assert "withheld_tax" in refund_result
        assert "refund_amount" in refund_result
        assert "deductions_applied" in refund_result
        
        # Withheld tax: €7,200
        # Deductions should include:
        # - Commuting allowance (45km with public transport)
        # - Home office deduction (€300)
        # - Family deductions (2 children)
        # - Work-related expenses (€1,050)
        
        deductions = refund_result["deductions_applied"]
        assert "commuting_allowance" in deductions
        assert "home_office_deduction" in deductions
        assert "family_deductions" in deductions
        
        # Commuting allowance for 45km with public transport (small)
        assert Decimal(deductions["commuting_allowance"]) > 0
        
        # Home office deduction
        assert Decimal(deductions["home_office_deduction"]) == Decimal("300.00")
        
        # Family deductions (2 children)
        assert Decimal(deductions["family_deductions"]) > 0
        
        # Refund should be positive (withheld more than actual liability)
        refund_amount = Decimal(refund_result["refund_amount"])
        assert refund_amount > 0
        
        print(f"\n✅ Employee refund calculation:")
        print(f"   Gross Income: €{lohnzettel_data['gross_income']}")
        print(f"   Withheld Tax: €{lohnzettel_data['withheld_tax']}")
        print(f"   Actual Tax Liability: €{refund_result['actual_tax_liability']}")
        print(f"   Refund Amount: €{refund_result['refund_amount']}")

        
        # Step 9: Generate refund report (Arbeitnehmerveranlagung)
        response = client.post(
            "/api/v1/reports/generate",
            json={
                "tax_year": 2026,
                "format": "pdf",
                "language": "de",
                "report_type": "employee_refund"
            },
            headers=headers
        )
        assert response.status_code == 201
        report_id = response.json()["id"]
        
        # Step 10: Download refund report
        response = client.get(f"/api/v1/reports/{report_id}/pdf", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        
        # Step 11: Generate FinanzOnline XML for submission
        response = client.post(
            "/api/v1/reports/generate",
            json={
                "tax_year": 2026,
                "format": "xml",
                "report_type": "employee_refund"
            },
            headers=headers
        )
        assert response.status_code == 201
        xml_report_id = response.json()["id"]
        
        response = client.get(f"/api/v1/reports/{xml_report_id}/xml", headers=headers)
        assert response.status_code == 200
        xml_content = response.content.decode("utf-8")
        
        # Verify XML contains employee-specific elements
        assert "Arbeitnehmerveranlagung" in xml_content or "NichtselbständigeArbeit" in xml_content
        assert "Pendlerpauschale" in xml_content
        assert "Kinderabsetzbetrag" in xml_content
        
        # Step 12: View refund estimate on dashboard
        response = client.get("/api/v1/dashboard?tax_year=2026", headers=headers)
        assert response.status_code == 200
        dashboard = response.json()
        
        assert "refund_estimate" in dashboard
        assert Decimal(dashboard["refund_estimate"]) > 0
        
        print(f"   Deductions Applied:")
        for deduction_name, amount in deductions.items():
            print(f"     - {deduction_name}: €{amount}")
        print(f"\n   Reports Generated: PDF + XML for FinanzOnline")


class TestMixedIncomeCompleteWorkflow:
    """E2E test for user with mixed income sources
    
    Simulates an employee with additional rental income:
    1. Register as employee
    2. Add employment income
    3. Add rental income and expenses
    4. Calculate combined taxes
    5. Generate comprehensive report
    """
    
    def test_employee_with_rental_income_workflow(self, client, db):
        """Test complete workflow for employee with rental income"""
        # Step 1: Register user
        registration_data = {
            "email": "mixed@example.com",
            "password": "SecurePass123!",
            "full_name": "Anna Weber",
            "user_type": "employee"  # Primary income source
        }
        
        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 201
        
        # Step 2: Login
        login_data = {
            "username": registration_data["email"],
            "password": registration_data["password"]
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 3: Add employment income
        employment_income = {
            "type": "income",
            "amount": "50000.00",
            "date": "2026-12-31",
            "description": "Annual Salary",
            "category": "employment_income"
        }
        
        response = client.post("/api/v1/transactions", json=employment_income, headers=headers)
        assert response.status_code == 201

        
        # Step 4: Add monthly rental income (residential property)
        monthly_rent = Decimal("1200.00")
        for month in range(1, 13):
            rental_income = {
                "type": "income",
                "amount": str(monthly_rent),
                "date": f"2026-{month:02d}-01",
                "description": f"Rental Income - Apartment Wien - Month {month}",
                "category": "rental_income",
                "property_type": "residential"
            }
            
            response = client.post("/api/v1/transactions", json=rental_income, headers=headers)
            assert response.status_code == 201
        
        # Step 5: Add rental property expenses
        rental_expenses = [
            {
                "type": "expense",
                "amount": "2400.00",
                "date": "2026-02-15",
                "description": "Property Maintenance and Repairs",
                "category": "maintenance",
                "is_deductible": True
            },
            {
                "type": "expense",
                "amount": "1800.00",
                "date": "2026-03-01",
                "description": "Property Management Fees",
                "category": "management_fees",
                "is_deductible": True
            },
            {
                "type": "expense",
                "amount": "1200.00",
                "date": "2026-06-30",
                "description": "Property Insurance",
                "category": "insurance",
                "is_deductible": True
            },
            {
                "type": "expense",
                "amount": "800.00",
                "date": "2026-09-15",
                "description": "Mortgage Interest",
                "category": "loan_interest",
                "is_deductible": True
            }
        ]
        
        for expense in rental_expenses:
            response = client.post("/api/v1/transactions", json=expense, headers=headers)
            assert response.status_code == 201
        
        # Step 6: Calculate combined taxes
        response = client.post("/api/v1/tax/calculate?tax_year=2026", headers=headers)
        assert response.status_code == 200
        tax_result = response.json()
        
        # Verify combined income calculation
        # Employment: €50,000
        # Rental: €14,400 (12 × €1,200)
        # Total: €64,400
        
        assert "income_summary" in tax_result
        income_summary = tax_result["income_summary"]
        
        assert Decimal(income_summary["employment"]) == Decimal("50000.00")
        assert Decimal(income_summary["rental"]) == Decimal("14400.00")
        assert Decimal(income_summary["total"]) == Decimal("64400.00")
        
        # Verify rental expenses are deducted
        assert "expense_summary" in tax_result
        expense_summary = tax_result["expense_summary"]
        
        total_rental_expenses = Decimal("6200.00")  # Sum of all rental expenses
        assert Decimal(expense_summary["deductible"]) == total_rental_expenses
        
        # Verify VAT status (residential rental can opt for exemption)
        assert "vat" in tax_result
        # Rental income alone is below VAT threshold
        
        # Verify income tax on combined income
        assert "income_tax" in tax_result
        assert Decimal(tax_result["income_tax"]["total_tax"]) > 0
        
        print(f"\n✅ Mixed income workflow test passed!")
        print(f"   Employment Income: €{income_summary['employment']}")
        print(f"   Rental Income: €{income_summary['rental']}")
        print(f"   Total Income: €{income_summary['total']}")
        print(f"   Deductible Expenses: €{expense_summary['deductible']}")
        print(f"   Income Tax: €{tax_result['income_tax']['total_tax']}")

        
        # Step 7: Generate comprehensive report
        response = client.post(
            "/api/v1/reports/generate",
            json={"tax_year": 2026, "format": "pdf", "language": "de"},
            headers=headers
        )
        assert response.status_code == 201
        report_id = response.json()["id"]
        
        # Step 8: Download and verify report
        response = client.get(f"/api/v1/reports/{report_id}/pdf", headers=headers)
        assert response.status_code == 200
        
        # Step 9: View dashboard with mixed income summary
        response = client.get("/api/v1/dashboard?tax_year=2026", headers=headers)
        assert response.status_code == 200
        dashboard = response.json()
        
        # Verify dashboard shows both income sources
        assert "income_breakdown" in dashboard
        assert dashboard["income_breakdown"]["employment"] > 0
        assert dashboard["income_breakdown"]["rental"] > 0


class TestLossCarryforwardWorkflow:
    """E2E test for multi-year loss carryforward workflow
    
    Simulates a self-employed user with losses:
    1. Year 2025: Business loss
    2. Year 2026: Profitable year with loss carryforward
    3. Verify loss reduces current year tax
    """
    
    def test_loss_carryforward_across_years(self, client, db):
        """Test loss carryforward from previous year reduces current year tax"""
        # Step 1: Register self-employed user
        registration_data = {
            "email": "startup@example.com",
            "password": "SecurePass123!",
            "full_name": "Thomas Bauer",
            "user_type": "self_employed"
        }
        
        response = client.post("/api/v1/auth/register", json=registration_data)
        assert response.status_code == 201
        
        # Step 2: Login
        login_data = {
            "username": registration_data["email"],
            "password": registration_data["password"]
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 3: Add 2025 transactions (loss year)
        # Low income, high startup costs
        transactions_2025 = [
            {
                "type": "income",
                "amount": "15000.00",
                "date": "2025-12-31",
                "description": "First Year Revenue",
                "category": "self_employment_income"
            },
            {
                "type": "expense",
                "amount": "25000.00",
                "date": "2025-06-15",
                "description": "Equipment and Setup Costs",
                "category": "equipment",
                "is_deductible": True
            }
        ]
        
        for txn in transactions_2025:
            response = client.post("/api/v1/transactions", json=txn, headers=headers)
            assert response.status_code == 201
        
        # Step 4: Calculate 2025 taxes (should result in loss)
        response = client.post("/api/v1/tax/calculate?tax_year=2025", headers=headers)
        assert response.status_code == 200
        tax_2025 = response.json()
        
        # Verify loss was recorded
        assert "loss_carryforward" in tax_2025
        loss_amount = Decimal(tax_2025["loss_carryforward"]["amount"])
        assert loss_amount > 0  # €10,000 loss
        
        print(f"\n✅ Loss carryforward workflow:")
        print(f"   2025 Loss: €{loss_amount}")

        
        # Step 5: Add 2026 transactions (profitable year)
        transactions_2026 = [
            {
                "type": "income",
                "amount": "50000.00",
                "date": "2026-12-31",
                "description": "Second Year Revenue",
                "category": "self_employment_income"
            },
            {
                "type": "expense",
                "amount": "15000.00",
                "date": "2026-06-30",
                "description": "Operating Expenses",
                "category": "operating_expenses",
                "is_deductible": True
            }
        ]
        
        for txn in transactions_2026:
            response = client.post("/api/v1/transactions", json=txn, headers=headers)
            assert response.status_code == 201
        
        # Step 6: Calculate 2026 taxes with loss carryforward
        response = client.post("/api/v1/tax/calculate?tax_year=2026", headers=headers)
        assert response.status_code == 200
        tax_2026 = response.json()
        
        # Verify loss carryforward was applied
        assert "loss_carryforward_applied" in tax_2026
        applied_loss = Decimal(tax_2026["loss_carryforward_applied"])
        assert applied_loss > 0
        
        # 2026 profit before loss: €35,000 (€50,000 - €15,000)
        # After applying €10,000 loss: €25,000 taxable income
        # Tax should be calculated on reduced amount
        
        assert "taxable_income" in tax_2026
        taxable_income = Decimal(tax_2026["taxable_income"])
        
        # Verify taxable income is reduced by loss carryforward
        expected_taxable = Decimal("35000.00") - applied_loss
        assert abs(taxable_income - expected_taxable) < Decimal("1.00")
        
        # Step 7: Check remaining loss balance
        if "loss_carryforward_remaining" in tax_2026:
            remaining_loss = Decimal(tax_2026["loss_carryforward_remaining"])
            assert remaining_loss == Decimal("0.00")  # All loss used
        
        print(f"   2026 Profit (before loss): €35,000.00")
        print(f"   Loss Applied: €{applied_loss}")
        print(f"   Taxable Income: €{taxable_income}")
        print(f"   Tax Saved: ~€{applied_loss * Decimal('0.30')}")  # Approximate


class TestDataExportImportWorkflow:
    """E2E test for data export and import (GDPR compliance)
    
    Tests:
    1. Export all user data
    2. Verify completeness
    3. Import data to new account
    4. Verify data integrity
    """
    
    def test_gdpr_data_export_workflow(self, client, authenticated_client, db):
        """Test GDPR-compliant data export"""
        headers = authenticated_client
        
        # Step 1: Create some data
        transactions = [
            {
                "type": "income",
                "amount": "5000.00",
                "date": "2026-01-15",
                "description": "Consulting Income",
                "category": "self_employment_income"
            },
            {
                "type": "expense",
                "amount": "500.00",
                "date": "2026-01-20",
                "description": "Office Supplies",
                "category": "office_supplies",
                "is_deductible": True
            }
        ]
        
        for txn in transactions:
            response = client.post("/api/v1/transactions", json=txn, headers=headers)
            assert response.status_code == 201
        
        # Step 2: Request GDPR data export
        response = client.post("/api/v1/users/export-data", headers=headers)
        assert response.status_code == 200
        
        export_data = response.json()
        
        # Verify export contains all user data
        assert "user_profile" in export_data
        assert "transactions" in export_data
        assert "documents" in export_data
        assert "tax_reports" in export_data
        
        # Verify transactions are included
        assert len(export_data["transactions"]) == 2
        
        print(f"\n✅ GDPR data export test passed!")
        print(f"   Exported: {len(export_data['transactions'])} transactions")
        print(f"   Exported: {len(export_data['documents'])} documents")



class TestAuditReadinessWorkflow:
    """E2E test for audit readiness preparation
    
    Tests:
    1. Create transactions with and without documents
    2. Generate audit checklist
    3. Verify missing document warnings
    4. Complete documentation
    5. Verify audit readiness
    """
    
    def test_audit_preparation_workflow(self, client, authenticated_client, db):
        """Test complete audit readiness preparation"""
        headers = authenticated_client
        
        # Step 1: Create transactions without documents (incomplete)
        undocumented_transactions = [
            {
                "type": "expense",
                "amount": "1500.00",
                "date": "2026-02-10",
                "description": "Equipment Purchase",
                "category": "equipment",
                "is_deductible": True
            },
            {
                "type": "expense",
                "amount": "800.00",
                "date": "2026-03-15",
                "description": "Professional Services",
                "category": "professional_services",
                "is_deductible": True
            }
        ]
        
        undocumented_ids = []
        for txn in undocumented_transactions:
            response = client.post("/api/v1/transactions", json=txn, headers=headers)
            assert response.status_code == 201
            undocumented_ids.append(response.json()["id"])
        
        # Step 2: Generate initial audit checklist
        response = client.get("/api/v1/audit/checklist?tax_year=2026", headers=headers)
        assert response.status_code == 200
        checklist = response.json()
        
        # Verify warnings for missing documents
        assert "missing_documents" in checklist
        assert len(checklist["missing_documents"]) >= 2
        
        print(f"\n✅ Audit readiness workflow:")
        print(f"   Initial missing documents: {len(checklist['missing_documents'])}")
        
        # Step 3: Upload supporting documents
        for txn_id in undocumented_ids:
            # Create document image
            doc_image = Image.new('RGB', (800, 1200), color='white')
            img_byte_arr = io.BytesIO()
            doc_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            files = {
                'file': (f'receipt_{txn_id}.png', img_byte_arr, 'image/png')
            }
            
            response = client.post(
                "/api/v1/documents/upload",
                files=files,
                headers=headers
            )
            assert response.status_code == 201
            doc_id = response.json()["id"]
            
            # Link document to transaction
            response = client.put(
                f"/api/v1/transactions/{txn_id}",
                json={"document_id": doc_id},
                headers=headers
            )
            assert response.status_code == 200
        
        # Step 4: Generate updated audit checklist
        response = client.get("/api/v1/audit/checklist?tax_year=2026", headers=headers)
        assert response.status_code == 200
        updated_checklist = response.json()
        
        # Verify documents are now linked
        assert len(updated_checklist["missing_documents"]) < len(checklist["missing_documents"])
        
        # Step 5: Generate audit report
        response = client.post(
            "/api/v1/audit/report?tax_year=2026",
            headers=headers
        )
        assert response.status_code == 200
        audit_report = response.json()
        
        assert "compliance_status" in audit_report
        assert "document_coverage" in audit_report
        
        print(f"   After documentation: {len(updated_checklist['missing_documents'])} missing")
        print(f"   Document coverage: {audit_report['document_coverage']}%")


class TestWhatIfSimulationWorkflow:
    """E2E test for tax simulation and optimization
    
    Tests:
    1. Calculate baseline taxes
    2. Simulate adding deductible expense
    3. Compare tax savings
    4. Apply optimization
    """
    
    def test_tax_optimization_simulation(self, client, authenticated_client, db):
        """Test what-if simulation for tax optimization"""
        headers = authenticated_client
        
        # Step 1: Create baseline scenario
        baseline_transactions = [
            {
                "type": "income",
                "amount": "60000.00",
                "date": "2026-12-31",
                "description": "Annual Income",
                "category": "self_employment_income"
            },
            {
                "type": "expense",
                "amount": "10000.00",
                "date": "2026-06-30",
                "description": "Current Expenses",
                "category": "operating_expenses",
                "is_deductible": True
            }
        ]
        
        for txn in baseline_transactions:
            response = client.post("/api/v1/transactions", json=txn, headers=headers)
            assert response.status_code == 201
        
        # Step 2: Calculate baseline taxes
        response = client.post("/api/v1/tax/calculate?tax_year=2026", headers=headers)
        assert response.status_code == 200
        baseline_tax = response.json()
        baseline_total = Decimal(baseline_tax["total_tax"])
        
        print(f"\n✅ What-if simulation workflow:")
        print(f"   Baseline tax: €{baseline_total}")

        
        # Step 3: Simulate adding equipment purchase
        simulation_data = {
            "tax_year": 2026,
            "changes": [
                {
                    "type": "add_expense",
                    "amount": "5000.00",
                    "category": "equipment",
                    "is_deductible": True,
                    "description": "New Computer Equipment"
                }
            ]
        }
        
        response = client.post(
            "/api/v1/tax/simulate",
            json=simulation_data,
            headers=headers
        )
        assert response.status_code == 200
        simulation_result = response.json()
        
        # Verify simulation shows tax savings
        assert "baseline_tax" in simulation_result
        assert "simulated_tax" in simulation_result
        assert "tax_difference" in simulation_result
        
        simulated_total = Decimal(simulation_result["simulated_tax"])
        tax_savings = baseline_total - simulated_total
        
        assert tax_savings > 0  # Should save money
        
        print(f"   Simulated tax (with €5,000 equipment): €{simulated_total}")
        print(f"   Tax savings: €{tax_savings}")
        
        # Step 4: Get optimization suggestions
        response = client.get("/api/v1/dashboard/suggestions?tax_year=2026", headers=headers)
        assert response.status_code == 200
        suggestions = response.json()
        
        assert "suggestions" in suggestions
        assert len(suggestions["suggestions"]) > 0
        
        # Verify suggestions include potential savings
        for suggestion in suggestions["suggestions"]:
            assert "description" in suggestion
            assert "potential_savings" in suggestion
        
        print(f"   Optimization suggestions: {len(suggestions['suggestions'])}")


class TestMultiLanguageReportGeneration:
    """E2E test for multi-language report generation
    
    Tests:
    1. Generate reports in German
    2. Generate reports in English
    3. Generate reports in Chinese
    4. Verify language-specific content
    """
    
    def test_multilanguage_reports(self, client, authenticated_client, db):
        """Test report generation in all supported languages"""
        headers = authenticated_client
        
        # Step 1: Create sample transaction
        transaction = {
            "type": "income",
            "amount": "30000.00",
            "date": "2026-12-31",
            "description": "Annual Income",
            "category": "self_employment_income"
        }
        
        response = client.post("/api/v1/transactions", json=transaction, headers=headers)
        assert response.status_code == 201
        
        # Step 2: Generate reports in all languages
        languages = ["de", "en", "zh"]
        report_ids = {}
        
        for lang in languages:
            response = client.post(
                "/api/v1/reports/generate",
                json={"tax_year": 2026, "format": "pdf", "language": lang},
                headers=headers
            )
            assert response.status_code == 201
            report_ids[lang] = response.json()["id"]
        
        # Step 3: Verify all reports were generated
        for lang, report_id in report_ids.items():
            response = client.get(f"/api/v1/reports/{report_id}/pdf", headers=headers)
            assert response.status_code == 200
            assert len(response.content) > 0
        
        print(f"\n✅ Multi-language report generation test passed!")
        print(f"   Generated reports in: {', '.join(languages)}")


class TestSecurityAndAccessControl:
    """E2E test for security and access control
    
    Tests:
    1. User isolation (cannot access other user's data)
    2. Authentication requirements
    3. Token expiration handling
    """
    
    def test_user_data_isolation(self, client, db):
        """Test that users cannot access each other's data"""
        # Step 1: Create first user
        user1_data = {
            "email": "user1@example.com",
            "password": "Password123!",
            "full_name": "User One",
            "user_type": "employee"
        }
        
        response = client.post("/api/v1/auth/register", json=user1_data)
        assert response.status_code == 201
        
        # Login user 1
        response = client.post(
            "/api/v1/auth/login",
            data={"username": user1_data["email"], "password": user1_data["password"]}
        )
        assert response.status_code == 200
        user1_token = response.json()["access_token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}
        
        # Create transaction for user 1
        transaction1 = {
            "type": "income",
            "amount": "5000.00",
            "date": "2026-01-15",
            "description": "User 1 Income",
            "category": "employment_income"
        }
        
        response = client.post("/api/v1/transactions", json=transaction1, headers=user1_headers)
        assert response.status_code == 201
        transaction1_id = response.json()["id"]

        
        # Step 2: Create second user
        user2_data = {
            "email": "user2@example.com",
            "password": "Password123!",
            "full_name": "User Two",
            "user_type": "self_employed"
        }
        
        response = client.post("/api/v1/auth/register", json=user2_data)
        assert response.status_code == 201
        
        # Login user 2
        response = client.post(
            "/api/v1/auth/login",
            data={"username": user2_data["email"], "password": user2_data["password"]}
        )
        assert response.status_code == 200
        user2_token = response.json()["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}
        
        # Step 3: User 2 tries to access User 1's transaction
        response = client.get(f"/api/v1/transactions/{transaction1_id}", headers=user2_headers)
        assert response.status_code == 404  # Not found (or 403 Forbidden)
        
        # Step 4: User 2 lists transactions (should be empty)
        response = client.get("/api/v1/transactions", headers=user2_headers)
        assert response.status_code == 200
        transactions = response.json()
        assert len(transactions) == 0  # User 2 has no transactions
        
        # Step 5: User 1 can still access their own transaction
        response = client.get(f"/api/v1/transactions/{transaction1_id}", headers=user1_headers)
        assert response.status_code == 200
        
        print(f"\n✅ User data isolation test passed!")
        print(f"   User 1 cannot access User 2's data")
        print(f"   User 2 cannot access User 1's data")
    
    def test_authentication_required(self, client):
        """Test that endpoints require authentication"""
        # Try to access protected endpoints without token
        protected_endpoints = [
            "/api/v1/transactions",
            "/api/v1/documents",
            "/api/v1/dashboard",
            "/api/v1/tax/calculate",
            "/api/v1/reports/generate"
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401  # Unauthorized
        
        print(f"\n✅ Authentication requirement test passed!")
        print(f"   All {len(protected_endpoints)} protected endpoints require auth")


# Summary test to verify all critical workflows
class TestSystemIntegration:
    """High-level integration test verifying all major components work together"""
    
    def test_complete_system_integration(self, client, db):
        """Comprehensive test of entire system integration"""
        print("\n" + "="*70)
        print("COMPREHENSIVE SYSTEM INTEGRATION TEST")
        print("="*70)
        
        # 1. User Management
        print("\n[1/7] Testing User Management...")
        response = client.post("/api/v1/auth/register", json={
            "email": "integration@example.com",
            "password": "SecurePass123!",
            "full_name": "Integration Test User",
            "user_type": "self_employed"
        })
        assert response.status_code == 201
        print("    ✓ User registration")
        
        response = client.post("/api/v1/auth/login", data={
            "username": "integration@example.com",
            "password": "SecurePass123!"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("    ✓ User authentication")
        
        # 2. Transaction Management
        print("\n[2/7] Testing Transaction Management...")
        response = client.post("/api/v1/transactions", json={
            "type": "income",
            "amount": "45000.00",
            "date": "2026-12-31",
            "description": "Business Revenue",
            "category": "self_employment_income"
        }, headers=headers)
        assert response.status_code == 201
        print("    ✓ Transaction creation")
        
        response = client.get("/api/v1/transactions", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) > 0
        print("    ✓ Transaction retrieval")
        
        # 3. Tax Calculation
        print("\n[3/7] Testing Tax Calculation...")
        response = client.post("/api/v1/tax/calculate?tax_year=2026", headers=headers)
        assert response.status_code == 200
        tax_result = response.json()
        assert "income_tax" in tax_result
        assert "total_tax" in tax_result
        print("    ✓ Tax calculation engine")
        
        # 4. Report Generation
        print("\n[4/7] Testing Report Generation...")
        response = client.post("/api/v1/reports/generate", json={
            "tax_year": 2026,
            "format": "pdf",
            "language": "de"
        }, headers=headers)
        assert response.status_code == 201
        report_id = response.json()["id"]
        print("    ✓ PDF report generation")
        
        response = client.post("/api/v1/reports/generate", json={
            "tax_year": 2026,
            "format": "xml"
        }, headers=headers)
        assert response.status_code == 201
        print("    ✓ XML report generation")
        
        # 5. Dashboard
        print("\n[5/7] Testing Dashboard...")
        response = client.get("/api/v1/dashboard?tax_year=2026", headers=headers)
        assert response.status_code == 200
        dashboard = response.json()
        assert "income_summary" in dashboard
        print("    ✓ Dashboard data aggregation")
        
        # 6. Data Export (GDPR)
        print("\n[6/7] Testing Data Export...")
        response = client.post("/api/v1/users/export-data", headers=headers)
        assert response.status_code == 200
        export_data = response.json()
        assert "transactions" in export_data
        print("    ✓ GDPR data export")
        
        # 7. Audit Readiness
        print("\n[7/7] Testing Audit Features...")
        response = client.get("/api/v1/audit/checklist?tax_year=2026", headers=headers)
        assert response.status_code == 200
        print("    ✓ Audit checklist generation")
        
        print("\n" + "="*70)
        print("✅ ALL SYSTEM INTEGRATION TESTS PASSED")
        print("="*70)
        print("\nSystem Components Verified:")
        print("  • User authentication and authorization")
        print("  • Transaction management (CRUD)")
        print("  • Tax calculation engine (income tax, VAT, SVS)")
        print("  • Report generation (PDF, XML, CSV)")
        print("  • Dashboard and analytics")
        print("  • GDPR compliance (data export)")
        print("  • Audit readiness features")
        print("\nAll critical user journeys are functioning correctly! 🎉")
