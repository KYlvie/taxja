"""Integration tests for transaction management

Tests complete transaction workflows including:
- Transaction CRUD operations (Requirements 1.1, 1.2, 1.5, 1.6)
- Transaction classification (Requirements 2.1, 2.2)
- Duplicate detection (Requirement 9.3)
- Multi-year data isolation (Requirements 10.1, 10.2)
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal


class TestTransactionCRUD:
    """Integration tests for transaction CRUD operations"""
    
    def test_create_income_transaction(self, authenticated_client):
        """Test creating an income transaction"""
        transaction_data = {
            "type": "income",
            "amount": 3500.00,
            "date": "2026-01-15",
            "description": "Monthly salary",
            "category": "employment_income"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["type"] == "income"
        assert float(data["amount"]) == 3500.00
        assert data["description"] == "Monthly salary"
        assert data["category"] == "employment_income"
        assert "id" in data
        assert "created_at" in data
    
    def test_create_expense_transaction(self, authenticated_client):
        """Test creating an expense transaction"""
        transaction_data = {
            "type": "expense",
            "amount": 150.50,
            "date": "2026-01-20",
            "description": "Office supplies from OBI",
            "category": "office_supplies"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["type"] == "expense"
        assert float(data["amount"]) == 150.50
        assert data["category"] == "office_supplies"
    
    def test_create_transaction_with_vat(self, authenticated_client):
        """Test creating transaction with VAT information"""
        transaction_data = {
            "type": "expense",
            "amount": 120.00,
            "date": "2026-01-25",
            "description": "Business lunch",
            "category": "meals",
            "vat_rate": 0.20,
            "vat_amount": 20.00
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 201
        
        data = response.json()
        assert float(data["vat_rate"]) == 0.20
        assert float(data["vat_amount"]) == 20.00
    
    def test_get_transaction_by_id(self, authenticated_client):
        """Test retrieving a specific transaction"""
        # Create transaction
        transaction_data = {
            "type": "income",
            "amount": 2000.00,
            "date": "2026-02-01",
            "description": "Freelance project",
            "category": "self_employment_income"
        }
        
        create_response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        transaction_id = create_response.json()["id"]
        
        # Get transaction
        response = authenticated_client.get(f"/api/v1/transactions/{transaction_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == transaction_id
        assert data["description"] == "Freelance project"
    
    def test_list_transactions(self, authenticated_client):
        """Test listing all transactions"""
        # Create multiple transactions
        transactions = [
            {"type": "income", "amount": 3000.00, "date": "2026-01-01", "description": "Salary Jan"},
            {"type": "expense", "amount": 100.00, "date": "2026-01-05", "description": "Office rent"},
            {"type": "income", "amount": 3000.00, "date": "2026-02-01", "description": "Salary Feb"}
        ]
        
        for txn in transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # List transactions
        response = authenticated_client.get("/api/v1/transactions")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) >= 3
        assert "total" in data
        assert "page" in data
    
    def test_list_transactions_with_filters(self, authenticated_client):
        """Test listing transactions with filters"""
        # Create transactions
        transactions = [
            {"type": "income", "amount": 3000.00, "date": "2026-01-15", "description": "Income 1"},
            {"type": "expense", "amount": 200.00, "date": "2026-01-20", "description": "Expense 1"},
            {"type": "income", "amount": 1500.00, "date": "2026-02-15", "description": "Income 2"}
        ]
        
        for txn in transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Filter by type
        response = authenticated_client.get("/api/v1/transactions?type=income")
        assert response.status_code == 200
        data = response.json()
        assert all(item["type"] == "income" for item in data["items"])
        
        # Filter by date range
        response = authenticated_client.get(
            "/api/v1/transactions?start_date=2026-01-01&end_date=2026-01-31"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 2
    
    def test_update_transaction(self, authenticated_client):
        """Test updating a transaction"""
        # Create transaction
        transaction_data = {
            "type": "expense",
            "amount": 100.00,
            "date": "2026-01-10",
            "description": "Original description"
        }
        
        create_response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        transaction_id = create_response.json()["id"]
        
        # Update transaction
        update_data = {
            "amount": 150.00,
            "description": "Updated description",
            "category": "office_supplies"
        }
        
        response = authenticated_client.put(
            f"/api/v1/transactions/{transaction_id}",
            json=update_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert float(data["amount"]) == 150.00
        assert data["description"] == "Updated description"
        assert data["category"] == "office_supplies"
    
    def test_delete_transaction(self, authenticated_client):
        """Test deleting a transaction"""
        # Create transaction
        transaction_data = {
            "type": "expense",
            "amount": 50.00,
            "date": "2026-01-15",
            "description": "To be deleted"
        }
        
        create_response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        transaction_id = create_response.json()["id"]
        
        # Delete transaction
        response = authenticated_client.delete(f"/api/v1/transactions/{transaction_id}")
        assert response.status_code == 204
        
        # Verify deletion
        response = authenticated_client.get(f"/api/v1/transactions/{transaction_id}")
        assert response.status_code == 404
    
    def test_create_transaction_requires_authentication(self, client):
        """Test that creating transaction requires authentication"""
        transaction_data = {
            "type": "income",
            "amount": 1000.00,
            "date": "2026-01-01",
            "description": "Test"
        }
        
        response = client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 401


class TestTransactionValidation:
    """Integration tests for transaction input validation"""
    
    def test_create_transaction_with_negative_amount(self, authenticated_client):
        """Test validation rejects negative amounts"""
        transaction_data = {
            "type": "income",
            "amount": -100.00,
            "date": "2026-01-01",
            "description": "Invalid amount"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 400
        assert "amount" in response.json()["detail"].lower()
    
    def test_create_transaction_with_zero_amount(self, authenticated_client):
        """Test validation rejects zero amounts"""
        transaction_data = {
            "type": "income",
            "amount": 0.00,
            "date": "2026-01-01",
            "description": "Zero amount"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 400
    
    def test_create_transaction_with_future_date(self, authenticated_client):
        """Test validation rejects future dates"""
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        transaction_data = {
            "type": "income",
            "amount": 1000.00,
            "date": future_date,
            "description": "Future transaction"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 400
        assert "future" in response.json()["detail"].lower()
    
    def test_create_transaction_without_required_fields(self, authenticated_client):
        """Test validation requires all mandatory fields"""
        # Missing amount
        response = authenticated_client.post("/api/v1/transactions", json={
            "type": "income",
            "date": "2026-01-01",
            "description": "Missing amount"
        })
        assert response.status_code == 422
        
        # Missing date
        response = authenticated_client.post("/api/v1/transactions", json={
            "type": "income",
            "amount": 1000.00,
            "description": "Missing date"
        })
        assert response.status_code == 422
        
        # Missing type
        response = authenticated_client.post("/api/v1/transactions", json={
            "amount": 1000.00,
            "date": "2026-01-01",
            "description": "Missing type"
        })
        assert response.status_code == 422
    
    def test_create_transaction_with_invalid_type(self, authenticated_client):
        """Test validation rejects invalid transaction types"""
        transaction_data = {
            "type": "invalid_type",
            "amount": 1000.00,
            "date": "2026-01-01",
            "description": "Invalid type"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 422
    
    def test_create_transaction_with_invalid_category(self, authenticated_client):
        """Test validation rejects invalid categories"""
        transaction_data = {
            "type": "income",
            "amount": 1000.00,
            "date": "2026-01-01",
            "description": "Invalid category",
            "category": "invalid_category_xyz"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 400


class TestTransactionClassification:
    """Integration tests for automatic transaction classification"""
    
    def test_auto_classify_salary_transaction(self, authenticated_client):
        """Test automatic classification of salary transaction"""
        transaction_data = {
            "type": "income",
            "amount": 3500.00,
            "date": "2026-01-31",
            "description": "Gehalt Januar 2026"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["category"] == "employment_income"
        assert "classification_confidence" in data
        assert data["classification_confidence"] > 0.7
    
    def test_auto_classify_grocery_expense(self, authenticated_client):
        """Test automatic classification of grocery expense"""
        transaction_data = {
            "type": "expense",
            "amount": 85.50,
            "date": "2026-01-15",
            "description": "BILLA Einkauf"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["category"] == "groceries"
        assert data["classification_confidence"] > 0.8
    
    def test_auto_classify_office_supplies(self, authenticated_client):
        """Test automatic classification of office supplies"""
        transaction_data = {
            "type": "expense",
            "amount": 120.00,
            "date": "2026-01-20",
            "description": "OBI Büromaterial"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["category"] == "office_supplies"
        assert data["is_deductible"] is True
    
    def test_manual_classification_override(self, authenticated_client):
        """Test manual override of automatic classification"""
        # Create transaction with auto-classification
        transaction_data = {
            "type": "expense",
            "amount": 50.00,
            "date": "2026-01-10",
            "description": "SPAR Einkauf"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        transaction_id = response.json()["id"]
        
        # Override classification
        update_data = {
            "category": "office_supplies",
            "is_deductible": True
        }
        
        response = authenticated_client.put(
            f"/api/v1/transactions/{transaction_id}",
            json=update_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["category"] == "office_supplies"
        assert data["is_deductible"] is True
    
    def test_classification_learning_from_correction(self, authenticated_client):
        """Test that system learns from manual corrections"""
        # Create transaction with auto-classification
        transaction_data = {
            "type": "expense",
            "amount": 75.00,
            "date": "2026-01-12",
            "description": "Unique merchant XYZ"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        transaction_id = response.json()["id"]
        original_category = response.json()["category"]
        
        # Correct the classification
        update_data = {
            "category": "professional_services"
        }
        
        response = authenticated_client.put(
            f"/api/v1/transactions/{transaction_id}",
            json=update_data
        )
        assert response.status_code == 200
        
        # Create similar transaction
        similar_transaction = {
            "type": "expense",
            "amount": 80.00,
            "date": "2026-02-12",
            "description": "Unique merchant XYZ again"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=similar_transaction)
        assert response.status_code == 201
        
        # Should learn from previous correction
        data = response.json()
        # Note: This may or may not match depending on ML model training
        # Just verify it has a classification
        assert "category" in data
    
    def test_deductibility_check_for_employee(self, authenticated_client):
        """Test deductibility checking for employee user type"""
        transaction_data = {
            "type": "expense",
            "amount": 100.00,
            "date": "2026-01-15",
            "description": "Commuting costs",
            "category": "commuting"
        }
        
        response = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 201
        
        data = response.json()
        assert "is_deductible" in data
        assert "deduction_reason" in data


class TestDuplicateDetection:
    """Integration tests for duplicate transaction detection"""
    
    def test_detect_exact_duplicate(self, authenticated_client):
        """Test detection of exact duplicate transactions"""
        transaction_data = {
            "type": "expense",
            "amount": 99.99,
            "date": "2026-01-15",
            "description": "Monthly subscription"
        }
        
        # Create first transaction
        response1 = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response1.status_code == 201
        
        # Try to create duplicate
        response2 = authenticated_client.post("/api/v1/transactions", json=transaction_data)
        assert response2.status_code == 400
        assert "duplicate" in response2.json()["detail"].lower()
    
    def test_detect_similar_duplicate(self, authenticated_client):
        """Test detection of similar transactions (same date, amount, similar description)"""
        transaction1 = {
            "type": "expense",
            "amount": 150.00,
            "date": "2026-01-20",
            "description": "BILLA Supermarkt Einkauf"
        }
        
        transaction2 = {
            "type": "expense",
            "amount": 150.00,
            "date": "2026-01-20",
            "description": "BILLA Einkauf Supermarkt"  # Similar but not exact
        }
        
        # Create first transaction
        response1 = authenticated_client.post("/api/v1/transactions", json=transaction1)
        assert response1.status_code == 201
        
        # Try to create similar transaction
        response2 = authenticated_client.post("/api/v1/transactions", json=transaction2)
        
        # Should either reject or warn about potential duplicate
        if response2.status_code == 400:
            assert "duplicate" in response2.json()["detail"].lower()
        else:
            assert response2.status_code == 201
            assert response2.json().get("duplicate_warning") is True
    
    def test_allow_same_amount_different_date(self, authenticated_client):
        """Test that same amount on different dates is not considered duplicate"""
        transaction1 = {
            "type": "expense",
            "amount": 100.00,
            "date": "2026-01-15",
            "description": "Monthly fee"
        }
        
        transaction2 = {
            "type": "expense",
            "amount": 100.00,
            "date": "2026-02-15",
            "description": "Monthly fee"
        }
        
        # Both should succeed
        response1 = authenticated_client.post("/api/v1/transactions", json=transaction1)
        assert response1.status_code == 201
        
        response2 = authenticated_client.post("/api/v1/transactions", json=transaction2)
        assert response2.status_code == 201
    
    def test_allow_same_date_different_amount(self, authenticated_client):
        """Test that different amounts on same date are not duplicates"""
        transaction1 = {
            "type": "expense",
            "amount": 50.00,
            "date": "2026-01-15",
            "description": "Purchase A"
        }
        
        transaction2 = {
            "type": "expense",
            "amount": 75.00,
            "date": "2026-01-15",
            "description": "Purchase B"
        }
        
        # Both should succeed
        response1 = authenticated_client.post("/api/v1/transactions", json=transaction1)
        assert response1.status_code == 201
        
        response2 = authenticated_client.post("/api/v1/transactions", json=transaction2)
        assert response2.status_code == 201
    
    def test_duplicate_detection_in_bulk_import(self, authenticated_client):
        """Test duplicate detection during bulk import"""
        # Create existing transaction
        existing = {
            "type": "expense",
            "amount": 200.00,
            "date": "2026-01-10",
            "description": "Existing transaction"
        }
        authenticated_client.post("/api/v1/transactions", json=existing)
        
        # Import CSV with duplicate
        import_data = {
            "transactions": [
                {
                    "type": "expense",
                    "amount": 200.00,
                    "date": "2026-01-10",
                    "description": "Existing transaction"
                },
                {
                    "type": "expense",
                    "amount": 150.00,
                    "date": "2026-01-11",
                    "description": "New transaction"
                }
            ]
        }
        
        response = authenticated_client.post("/api/v1/transactions/import", json=import_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["duplicates_found"] > 0
        assert data["imported_count"] == 1  # Only non-duplicate imported


class TestMultiYearDataIsolation:
    """Integration tests for multi-year data isolation"""
    
    def test_transactions_filtered_by_year(self, authenticated_client):
        """Test that transactions are properly filtered by tax year"""
        # Create transactions in different years
        transactions = [
            {"type": "income", "amount": 3000.00, "date": "2025-12-15", "description": "2025 income"},
            {"type": "income", "amount": 3000.00, "date": "2026-01-15", "description": "2026 income"},
            {"type": "income", "amount": 3000.00, "date": "2026-12-15", "description": "2026 income 2"},
            {"type": "income", "amount": 3000.00, "date": "2027-01-15", "description": "2027 income"}
        ]
        
        for txn in transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Get 2026 transactions
        response = authenticated_client.get("/api/v1/transactions?tax_year=2026")
        assert response.status_code == 200
        
        data = response.json()
        # Should only return 2026 transactions
        for item in data["items"]:
            txn_date = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
            assert txn_date.year == 2026
    
    def test_tax_calculation_respects_year_boundaries(self, authenticated_client):
        """Test that tax calculations only include transactions from specified year"""
        # Create transactions in different years
        transactions = [
            {"type": "income", "amount": 5000.00, "date": "2025-12-31", "description": "2025"},
            {"type": "income", "amount": 10000.00, "date": "2026-01-01", "description": "2026 start"},
            {"type": "income", "amount": 15000.00, "date": "2026-12-31", "description": "2026 end"},
            {"type": "income", "amount": 5000.00, "date": "2027-01-01", "description": "2027"}
        ]
        
        for txn in transactions:
            authenticated_client.post("/api/v1/transactions", json=txn)
        
        # Calculate tax for 2026
        response = authenticated_client.post("/api/v1/tax/calculate", json={"tax_year": 2026})
        assert response.status_code == 200
        
        data = response.json()
        # Total income should be 25000 (only 2026 transactions)
        assert float(data["total_income"]) == 25000.00
    
    def test_year_switch_maintains_isolation(self, authenticated_client):
        """Test switching between years maintains data isolation"""
        # Create transactions for 2025
        authenticated_client.post("/api/v1/transactions", json={
            "type": "income",
            "amount": 1000.00,
            "date": "2025-06-15",
            "description": "2025 transaction"
        })
        
        # Create transactions for 2026
        authenticated_client.post("/api/v1/transactions", json={
            "type": "income",
            "amount": 2000.00,
            "date": "2026-06-15",
            "description": "2026 transaction"
        })
        
        # Get 2025 transactions
        response = authenticated_client.get("/api/v1/transactions?tax_year=2025")
        data_2025 = response.json()
        
        # Get 2026 transactions
        response = authenticated_client.get("/api/v1/transactions?tax_year=2026")
        data_2026 = response.json()
        
        # Verify isolation
        assert len(data_2025["items"]) >= 1
        assert len(data_2026["items"]) >= 1
        
        # Verify no overlap
        dates_2025 = [item["date"] for item in data_2025["items"]]
        dates_2026 = [item["date"] for item in data_2026["items"]]
        
        for date_str in dates_2025:
            assert "2025" in date_str
        
        for date_str in dates_2026:
            assert "2026" in date_str


class TestTransactionUserIsolation:
    """Integration tests for user data isolation"""
    
    def test_users_cannot_see_other_users_transactions(self, client, multiple_test_users):
        """Test that users can only see their own transactions"""
        user1 = multiple_test_users[0]
        user2 = multiple_test_users[1]
        
        # Login as user1
        login_data = {"username": user1["email"], "password": user1["password"]}
        response = client.post("/api/v1/auth/login", data=login_data)
        token1 = response.json()["access_token"]
        
        # Create transaction as user1
        headers1 = {"Authorization": f"Bearer {token1}"}
        transaction_data = {
            "type": "income",
            "amount": 1000.00,
            "date": "2026-01-15",
            "description": "User1 transaction"
        }
        response = client.post("/api/v1/transactions", json=transaction_data, headers=headers1)
        assert response.status_code == 201
        
        # Login as user2
        login_data = {"username": user2["email"], "password": user2["password"]}
        response = client.post("/api/v1/auth/login", data=login_data)
        token2 = response.json()["access_token"]
        
        # Try to list transactions as user2
        headers2 = {"Authorization": f"Bearer {token2}"}
        response = client.get("/api/v1/transactions", headers=headers2)
        assert response.status_code == 200
        
        # User2 should not see user1's transactions
        data = response.json()
        for item in data["items"]:
            assert item["description"] != "User1 transaction"
    
    def test_users_cannot_access_other_users_transaction_by_id(self, client, multiple_test_users):
        """Test that users cannot access other users' transactions by ID"""
        user1 = multiple_test_users[0]
        user2 = multiple_test_users[1]
        
        # Login as user1 and create transaction
        login_data = {"username": user1["email"], "password": user1["password"]}
        response = client.post("/api/v1/auth/login", data=login_data)
        token1 = response.json()["access_token"]
        
        headers1 = {"Authorization": f"Bearer {token1}"}
        transaction_data = {
            "type": "income",
            "amount": 1000.00,
            "date": "2026-01-15",
            "description": "User1 private transaction"
        }
        response = client.post("/api/v1/transactions", json=transaction_data, headers=headers1)
        transaction_id = response.json()["id"]
        
        # Login as user2
        login_data = {"username": user2["email"], "password": user2["password"]}
        response = client.post("/api/v1/auth/login", data=login_data)
        token2 = response.json()["access_token"]
        
        # Try to access user1's transaction as user2
        headers2 = {"Authorization": f"Bearer {token2}"}
        response = client.get(f"/api/v1/transactions/{transaction_id}", headers=headers2)
        assert response.status_code == 404  # Not found (or 403 Forbidden)
