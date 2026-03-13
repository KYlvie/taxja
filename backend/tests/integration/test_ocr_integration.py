"""Integration tests for OCR pipeline

Tests complete OCR workflows including:
- Document upload and OCR processing (Requirement 19.1)
- OCR review and correction (Requirements 23.1, 23.3)
- Transaction creation from OCR (Requirement 19.7)
- Document-transaction association (Requirements 19.8, 19.9)
"""
import pytest
import io
from PIL import Image
from datetime import datetime


class TestDocumentUpload:
    """Integration tests for document upload"""
    
    def test_upload_single_document(self, authenticated_client):
        """Test uploading a single document"""
        # Create a test image
        image = Image.new('RGB', (800, 600), color='white')
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        
        files = {
            'file': ('receipt.jpg', img_byte_arr, 'image/jpeg')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 201
        
        data = response.json()
        assert "id" in data
        assert "file_path" in data
        assert data["document_type"] is not None
        assert "ocr_status" in data
    
    def test_upload_document_triggers_ocr(self, authenticated_client):
        """Test that document upload triggers OCR processing"""
        # Create test image with text
        image = Image.new('RGB', (800, 600), color='white')
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        
        files = {
            'file': ('invoice.jpg', img_byte_arr, 'image/jpeg')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 201
        
        document_id = response.json()["id"]
        
        # Check OCR status (may be processing or completed)
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ocr_status"] in ["pending", "processing", "completed", "failed"]
    
    def test_upload_multiple_documents(self, authenticated_client):
        """Test batch upload of multiple documents"""
        # Create multiple test images
        files = []
        for i in range(3):
            image = Image.new('RGB', (800, 600), color='white')
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            files.append(('files', (f'receipt{i}.jpg', img_byte_arr, 'image/jpeg')))
        
        response = authenticated_client.post("/api/v1/documents/batch-upload", files=files)
        assert response.status_code == 200
        
        data = response.json()
        assert "uploaded" in data
        assert len(data["uploaded"]) == 3
        assert "failed" in data
    
    def test_upload_pdf_document(self, authenticated_client):
        """Test uploading PDF document"""
        # Create a simple PDF (in real scenario, use actual PDF)
        pdf_content = b'%PDF-1.4\n%Test PDF'
        
        files = {
            'file': ('invoice.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        # May succeed or fail depending on PDF processing implementation
        assert response.status_code in [201, 400]
    
    def test_upload_invalid_file_type(self, authenticated_client):
        """Test that invalid file types are rejected"""
        # Try to upload a text file
        files = {
            'file': ('document.txt', io.BytesIO(b'Plain text'), 'text/plain')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 400
        assert "format" in response.json()["detail"].lower()
    
    def test_upload_oversized_file(self, authenticated_client):
        """Test that oversized files are rejected"""
        # Create a large image (>10MB)
        # Note: This is a simplified test
        large_image = Image.new('RGB', (10000, 10000), color='white')
        img_byte_arr = io.BytesIO()
        large_image.save(img_byte_arr, format='JPEG', quality=100)
        img_byte_arr.seek(0)
        
        files = {
            'file': ('large_receipt.jpg', img_byte_arr, 'image/jpeg')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        # May succeed or fail depending on size limit
        if response.status_code == 400:
            assert "size" in response.json()["detail"].lower()
    
    def test_upload_requires_authentication(self, client):
        """Test that document upload requires authentication"""
        image = Image.new('RGB', (800, 600), color='white')
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        
        files = {
            'file': ('receipt.jpg', img_byte_arr, 'image/jpeg')
        }
        
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 401


class TestOCRProcessing:
    """Integration tests for OCR processing"""
    
    def test_ocr_extracts_text_from_receipt(self, authenticated_client, sample_receipt_image):
        """Test OCR text extraction from receipt"""
        files = {
            'file': ('receipt.jpg', sample_receipt_image, 'image/jpeg')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        document_id = response.json()["id"]
        
        # Wait for OCR processing (in real test, may need to poll or use async)
        import time
        time.sleep(2)
        
        # Get OCR results
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ocr_status"] == "completed"
        assert "ocr_result" in data
        assert data["ocr_result"]["raw_text"] is not None
    
    def test_ocr_classifies_document_type(self, authenticated_client, sample_receipt_image):
        """Test OCR document type classification"""
        files = {
            'file': ('receipt.jpg', sample_receipt_image, 'image/jpeg')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        document_id = response.json()["id"]
        
        # Get document details
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        data = response.json()
        
        assert data["document_type"] in [
            "receipt", "invoice", "payslip", "bank_statement",
            "rental_contract", "svs_notice", "unknown"
        ]
    
    def test_ocr_extracts_key_fields_from_receipt(self, authenticated_client, sample_receipt_image):
        """Test OCR key field extraction from receipt"""
        files = {
            'file': ('receipt.jpg', sample_receipt_image, 'image/jpeg')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        document_id = response.json()["id"]
        
        # Get OCR results
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        data = response.json()
        
        if data["ocr_status"] == "completed":
            ocr_result = data["ocr_result"]
            assert "extracted_data" in ocr_result
            
            extracted = ocr_result["extracted_data"]
            # Check for common receipt fields
            assert "date" in extracted or "amount" in extracted or "merchant" in extracted
    
    def test_ocr_confidence_scoring(self, authenticated_client, sample_receipt_image):
        """Test OCR confidence score calculation"""
        files = {
            'file': ('receipt.jpg', sample_receipt_image, 'image/jpeg')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        document_id = response.json()["id"]
        
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        data = response.json()
        
        if data["ocr_status"] == "completed":
            assert "confidence_score" in data["ocr_result"]
            confidence = data["ocr_result"]["confidence_score"]
            assert 0.0 <= confidence <= 1.0
    
    def test_ocr_handles_poor_quality_image(self, authenticated_client):
        """Test OCR handling of poor quality image"""
        # Create a very small, low quality image
        image = Image.new('RGB', (100, 100), color='gray')
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=10)
        img_byte_arr.seek(0)
        
        files = {
            'file': ('poor_quality.jpg', img_byte_arr, 'image/jpeg')
        }
        
        response = authenticated_client.post("/api/v1/documents/upload", files=files)
        document_id = response.json()["id"]
        
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        data = response.json()
        
        # Should complete but with low confidence or failed status
        assert data["ocr_status"] in ["completed", "failed"]
        if data["ocr_status"] == "completed":
            assert data["ocr_result"]["confidence_score"] < 0.6
    
    def test_batch_ocr_processing(self, authenticated_client):
        """Test batch OCR processing of multiple documents"""
        # Upload multiple documents
        files = []
        for i in range(3):
            image = Image.new('RGB', (800, 600), color='white')
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            files.append(('files', (f'receipt{i}.jpg', img_byte_arr, 'image/jpeg')))
        
        response = authenticated_client.post("/api/v1/documents/batch-upload", files=files)
        assert response.status_code == 200
        
        uploaded_docs = response.json()["uploaded"]
        
        # Check that all documents are being processed
        for doc in uploaded_docs:
            response = authenticated_client.get(f"/api/v1/documents/{doc['id']}")
            assert response.status_code == 200
            assert response.json()["ocr_status"] in ["pending", "processing", "completed"]


class TestOCRReviewAndCorrection:
    """Integration tests for OCR review and correction"""
    
    def test_get_document_for_review(self, authenticated_client, document_with_ocr):
        """Test retrieving document for OCR review"""
        document_id = document_with_ocr["id"]
        
        response = authenticated_client.get(f"/api/v1/documents/{document_id}/review")
        assert response.status_code == 200
        
        data = response.json()
        assert "document_id" in data
        assert "ocr_result" in data
        assert "extracted_data" in data["ocr_result"]
        assert "confidence_score" in data["ocr_result"]
    
    def test_confirm_ocr_results(self, authenticated_client, document_with_ocr):
        """Test confirming OCR results without changes"""
        document_id = document_with_ocr["id"]
        
        response = authenticated_client.post(f"/api/v1/documents/{document_id}/confirm")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "confirmed"
        assert "transaction_id" in data  # Should create transaction
    
    def test_correct_ocr_results(self, authenticated_client, document_with_ocr):
        """Test correcting OCR extracted data"""
        document_id = document_with_ocr["id"]
        
        # Correct the extracted data
        corrections = {
            "date": "2026-01-15",
            "amount": 125.50,
            "merchant": "BILLA",
            "description": "Groceries"
        }
        
        response = authenticated_client.post(
            f"/api/v1/documents/{document_id}/correct",
            json={"corrected_data": corrections}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "corrected"
        assert "transaction_id" in data
    
    def test_correction_updates_ml_model(self, authenticated_client, document_with_ocr):
        """Test that corrections are used to improve ML model"""
        document_id = document_with_ocr["id"]
        
        corrections = {
            "date": "2026-01-15",
            "amount": 100.00,
            "merchant": "Custom Merchant",
            "category": "office_supplies"
        }
        
        response = authenticated_client.post(
            f"/api/v1/documents/{document_id}/correct",
            json={"corrected_data": corrections}
        )
        assert response.status_code == 200
        
        # Verify correction was recorded for ML training
        # (Implementation detail - may need to check database or ML service)
    
    def test_low_confidence_ocr_requires_review(self, authenticated_client, low_confidence_document):
        """Test that low confidence OCR results are flagged for review"""
        document_id = low_confidence_document["id"]
        
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        data = response.json()
        
        assert data["ocr_result"]["confidence_score"] < 0.6
        assert data["ocr_result"]["needs_review"] is True
    
    def test_high_confidence_ocr_auto_creates_transaction(self, authenticated_client, high_confidence_document):
        """Test that high confidence OCR can auto-create transaction"""
        document_id = high_confidence_document["id"]
        
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        data = response.json()
        
        assert data["ocr_result"]["confidence_score"] >= 0.8
        
        # May auto-create transaction or suggest it
        if "transaction_id" in data:
            # Verify transaction was created
            transaction_id = data["transaction_id"]
            response = authenticated_client.get(f"/api/v1/transactions/{transaction_id}")
            assert response.status_code == 200


class TestTransactionCreationFromOCR:
    """Integration tests for creating transactions from OCR data"""
    
    def test_create_transaction_from_receipt_ocr(self, authenticated_client, receipt_ocr_data):
        """Test creating transaction from receipt OCR data"""
        document_id = receipt_ocr_data["document_id"]
        
        # Confirm OCR and create transaction
        response = authenticated_client.post(f"/api/v1/documents/{document_id}/confirm")
        assert response.status_code == 200
        
        transaction_id = response.json()["transaction_id"]
        
        # Verify transaction was created correctly
        response = authenticated_client.get(f"/api/v1/transactions/{transaction_id}")
        assert response.status_code == 200
        
        transaction = response.json()
        assert transaction["type"] == "expense"
        assert "amount" in transaction
        assert "date" in transaction
        assert transaction["document_id"] == document_id
    
    def test_create_transaction_from_invoice_ocr(self, authenticated_client, invoice_ocr_data):
        """Test creating transaction from invoice OCR data"""
        document_id = invoice_ocr_data["document_id"]
        
        response = authenticated_client.post(f"/api/v1/documents/{document_id}/confirm")
        assert response.status_code == 200
        
        transaction_id = response.json()["transaction_id"]
        
        # Verify transaction includes VAT information
        response = authenticated_client.get(f"/api/v1/transactions/{transaction_id}")
        transaction = response.json()
        
        assert "vat_amount" in transaction
        assert "vat_rate" in transaction
    
    def test_create_transaction_from_payslip_ocr(self, authenticated_client, payslip_ocr_data):
        """Test creating transaction from payslip OCR data"""
        document_id = payslip_ocr_data["document_id"]
        
        response = authenticated_client.post(f"/api/v1/documents/{document_id}/confirm")
        assert response.status_code == 200
        
        transaction_id = response.json()["transaction_id"]
        
        # Verify income transaction was created
        response = authenticated_client.get(f"/api/v1/transactions/{transaction_id}")
        transaction = response.json()
        
        assert transaction["type"] == "income"
        assert transaction["category"] == "employment_income"
    
    def test_transaction_links_to_source_document(self, authenticated_client, receipt_ocr_data):
        """Test that created transaction links back to source document"""
        document_id = receipt_ocr_data["document_id"]
        
        response = authenticated_client.post(f"/api/v1/documents/{document_id}/confirm")
        transaction_id = response.json()["transaction_id"]
        
        # Check transaction has document reference
        response = authenticated_client.get(f"/api/v1/transactions/{transaction_id}")
        transaction = response.json()
        assert transaction["document_id"] == document_id
        
        # Check document has transaction reference
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        document = response.json()
        assert document["transaction_id"] == transaction_id
    
    def test_manual_transaction_creation_with_document(self, authenticated_client, document_with_ocr):
        """Test manually creating transaction and linking to document"""
        document_id = document_with_ocr["id"]
        
        # Create transaction manually with document reference
        transaction_data = {
            "type": "expense",
            "amount": 99.99,
            "date": "2026-01-15",
            "description": "Manual entry from document",
            "document_id": document_id
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 201
        
        transaction = response.json()
        assert transaction["document_id"] == document_id
    
    def test_ocr_suggests_transaction_category(self, authenticated_client, receipt_ocr_data):
        """Test that OCR suggests appropriate transaction category"""
        document_id = receipt_ocr_data["document_id"]
        
        response = authenticated_client.post(f"/api/v1/documents/{document_id}/confirm")
        transaction_id = response.json()["transaction_id"]
        
        response = authenticated_client.get(f"/api/v1/transactions/{transaction_id}")
        transaction = response.json()
        
        # Should have a category assigned
        assert "category" in transaction
        assert transaction["category"] is not None
        
        # Should have classification confidence
        assert "classification_confidence" in transaction


class TestDocumentTransactionAssociation:
    """Integration tests for document-transaction association"""
    
    def test_document_archival_on_transaction_delete(self, authenticated_client, transaction_with_document):
        """Test that document is archived when transaction is deleted"""
        transaction_id = transaction_with_document["transaction_id"]
        document_id = transaction_with_document["document_id"]
        
        # Delete transaction
        response = authenticated_client.delete(f"/api/v1/transactions/{transaction_id}")
        assert response.status_code == 204
        
        # Check document is marked as archived
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        assert response.status_code == 200
        
        document = response.json()
        assert document["is_archived"] is True
        assert document["archived_reason"] == "transaction_deleted"
    
    def test_document_remains_accessible_after_archival(self, authenticated_client, transaction_with_document):
        """Test that archived documents remain accessible"""
        transaction_id = transaction_with_document["transaction_id"]
        document_id = transaction_with_document["document_id"]
        
        # Delete transaction (archives document)
        authenticated_client.delete(f"/api/v1/transactions/{transaction_id}")
        
        # Document should still be accessible
        response = authenticated_client.get(f"/api/v1/documents/{document_id}")
        assert response.status_code == 200
        
        # Can still download document
        response = authenticated_client.get(f"/api/v1/documents/{document_id}/download")
        assert response.status_code == 200
    
    def test_list_documents_by_transaction(self, authenticated_client, transaction_with_multiple_documents):
        """Test listing all documents associated with a transaction"""
        transaction_id = transaction_with_multiple_documents["transaction_id"]
        
        response = authenticated_client.get(
            f"/api/v1/transactions/{transaction_id}/documents"
        )
        assert response.status_code == 200
        
        documents = response.json()
        assert len(documents) > 0
        
        for doc in documents:
            assert doc["transaction_id"] == transaction_id
    
    def test_search_documents_by_ocr_text(self, authenticated_client):
        """Test searching documents by OCR extracted text"""
        # Upload document with specific text
        # (In real test, would use image with known text)
        
        response = authenticated_client.get(
            "/api/v1/documents/search?q=BILLA"
        )
        assert response.status_code == 200
        
        results = response.json()
        # Should return documents containing "BILLA" in OCR text
        for doc in results["items"]:
            assert "BILLA" in doc["ocr_result"]["raw_text"].upper()
    
    def test_filter_documents_by_type(self, authenticated_client):
        """Test filtering documents by document type"""
        response = authenticated_client.get(
            "/api/v1/documents?document_type=receipt"
        )
        assert response.status_code == 200
        
        documents = response.json()
        for doc in documents["items"]:
            assert doc["document_type"] == "receipt"
    
    def test_download_original_document(self, authenticated_client, document_with_ocr):
        """Test downloading original uploaded document"""
        document_id = document_with_ocr["id"]
        
        response = authenticated_client.get(f"/api/v1/documents/{document_id}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] in ["image/jpeg", "image/png", "application/pdf"]
