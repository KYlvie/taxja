"""
User Acceptance Testing (UAT) for Property Asset Management Feature

This module contains comprehensive UAT scenarios covering all major workflows
for the Property Asset Management feature. These tests simulate real user
interactions and validate the complete feature from end-to-end.

Test Categories:
1. Property Registration and Management
2. Depreciation Calculation and Backfill
3. Transaction Linking
4. E1/Bescheid Integration
5. Reports and Analytics
6. Multi-Property Portfolio
7. Performance and Scalability

Run with: pytest backend/tests/uat/test_property_uat.py -v
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory
from app.services.property_service import PropertyService
from app.services.afa_calculator import AfACalculator
from app.services.historical_depreciation_service import HistoricalDepreciationService
from app.services.annual_depreciation_service import AnnualDepreciationService


@pytest.fixture
def client():
    """Test client for API requests"""
    return TestClient(app)


@pytest.fixture
def landlord_user(db: Session) -> User:
    """Create a landlord user for testing"""
    user = User(
        email="landlord@test.com",
        name="Test Landlord",
        user_type=UserType.LANDLORD,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(landlord_user: User) -> Dict[str, str]:
    """Authentication headers for API requests"""
    # In real implementation, this would generate a JWT token
    return {"Authorization": f"Bearer test_token_{landlord_user.id}"}


class TestPropertyRegistrationUAT:
    """UAT Scenario 1: Property Registration and Management"""
    
    def test_landlord_registers_first_property(
        self, 
        client: TestClient, 
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-1.1: Landlord registers their first rental property
        
        Steps:
        1. User navigates to Properties page
        2. Clicks "Add Property" button
        3. Fills in property details
        4. System auto-calculates building_value and depreciation_rate
        5. User submits form
        6. Property is created successfully
        """
        property_data = {
            "property_type": "rental",
            "street": "Hauptstraße 123",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": "2020-06-15",
            "purchase_price": 350000.00,
            "construction_year": 1985
        }
        
        response = client.post(
            "/api/v1/properties",
            json=property_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify auto-calculations
        assert data["building_value"] == 280000.00  # 80% of purchase_price
        assert data["land_value"] == 70000.00
        assert data["depreciation_rate"] == 0.02  # 2% for post-1915 building
        assert data["status"] == "active"
        assert data["address"] == "Hauptstraße 123, 1010 Wien"
        
        print("✓ UAT-1.1 PASSED: Landlord successfully registered first property")
    
    def test_landlord_views_property_list(
        self,
        client: TestClient,
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-1.2: Landlord views their property portfolio
        
        Steps:
        1. User navigates to Properties page
        2. System displays list of all properties
        3. Each property shows key metrics
        """
        # Create test properties
        properties = [
            Property(
                user_id=landlord_user.id,
                property_type=PropertyType.RENTAL,
                street="Hauptstraße 123",
                city="Wien",
                postal_code="1010",
                purchase_date=date(2020, 6, 15),
                purchase_price=Decimal("350000"),
                building_value=Decimal("280000"),
                depreciation_rate=Decimal("0.02"),
                status=PropertyStatus.ACTIVE
            ),
            Property(
                user_id=landlord_user.id,
                property_type=PropertyType.RENTAL,
                street="Mariahilfer Straße 45",
                city="Wien",
                postal_code="1060",
                purchase_date=date(2019, 3, 1),
                purchase_price=Decimal("420000"),
                building_value=Decimal("336000"),
                depreciation_rate=Decimal("0.02"),
                status=PropertyStatus.ACTIVE
            )
        ]
        
        for prop in properties:
            db.add(prop)
        db.commit()
        
        response = client.get("/api/v1/properties", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["properties"]) == 2
        
        print("✓ UAT-1.2 PASSED: Landlord can view property portfolio")
    
    def test_landlord_edits_property_details(
        self,
        client: TestClient,
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-1.3: Landlord updates property information
        
        Steps:
        1. User selects a property
        2. Clicks "Edit" button
        3. Updates allowed fields (not purchase_date or purchase_price)
        4. Saves changes
        """
        property = Property(
            user_id=landlord_user.id,
            property_type=PropertyType.RENTAL,
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 6, 15),
            purchase_price=Decimal("350000"),
            building_value=Decimal("280000"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        
        update_data = {
            "construction_year": 1990,
            "depreciation_rate": 0.025  # Manual override
        }
        
        response = client.put(
            f"/api/v1/properties/{property.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["construction_year"] == 1990
        assert float(data["depreciation_rate"]) == 0.025
        
        print("✓ UAT-1.3 PASSED: Landlord can edit property details")


class TestDepreciationCalculationUAT:
    """UAT Scenario 2: Depreciation Calculation and Backfill"""
    
    def test_automatic_depreciation_calculation(
        self,
        db: Session,
        landlord_user: User
    ):
        """
        UAT-2.1: System calculates depreciation correctly
        
        Steps:
        1. Property is registered with purchase details
        2. System calculates annual depreciation
        3. Depreciation follows Austrian tax law (1.5% or 2%)
        """
        property = Property(
            user_id=landlord_user.id,
            property_type=PropertyType.RENTAL,
            street="Teststraße 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2025, 1, 1),
            purchase_price=Decimal("300000"),
            building_value=Decimal("240000"),
            construction_year=1920,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        
        calculator = AfACalculator(db)
        annual_depreciation = calculator.calculate_annual_depreciation(property, 2025)
        
        # Expected: 240,000 * 0.02 = 4,800 EUR
        assert annual_depreciation == Decimal("4800.00")
        
        print("✓ UAT-2.1 PASSED: Depreciation calculated correctly")
    
    def test_prorated_first_year_depreciation(
        self,
        db: Session,
        landlord_user: User
    ):
        """
        UAT-2.2: Pro-rated depreciation for mid-year purchase
        
        Steps:
        1. Property purchased mid-year (June 15)
        2. System calculates pro-rated depreciation
        3. Only 7 months counted (June-December)
        """
        property = Property(
            user_id=landlord_user.id,
            property_type=PropertyType.RENTAL,
            street="Teststraße 2",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2025, 6, 15),
            purchase_price=Decimal("300000"),
            building_value=Decimal("240000"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        
        calculator = AfACalculator(db)
        first_year_depreciation = calculator.calculate_annual_depreciation(property, 2025)
        
        # Expected: (240,000 * 0.02 * 7) / 12 = 2,800 EUR
        expected = Decimal("2800.00")
        assert abs(first_year_depreciation - expected) < Decimal("0.01")
        
        print("✓ UAT-2.2 PASSED: Pro-rated depreciation calculated correctly")
    
    def test_historical_depreciation_backfill(
        self,
        client: TestClient,
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-2.3: Backfill historical depreciation for existing property
        
        Steps:
        1. User registers property purchased in 2020
        2. System detects missing historical depreciation
        3. User previews backfill (2020-2025)
        4. User confirms backfill
        5. System creates depreciation transactions for all years
        """
        property = Property(
            user_id=landlord_user.id,
            property_type=PropertyType.RENTAL,
            street="Altbau Straße 10",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("300000"),
            building_value=Decimal("240000"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        
        # Preview backfill
        preview_response = client.get(
            f"/api/v1/properties/{property.id}/historical-depreciation",
            headers=auth_headers
        )
        
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        
        # Should have 6 years: 2020, 2021, 2022, 2023, 2024, 2025
        assert len(preview_data["years"]) == 6
        assert preview_data["total_amount"] == 28800.00  # 4,800 * 6
        
        # Execute backfill
        backfill_response = client.post(
            f"/api/v1/properties/{property.id}/backfill-depreciation",
            headers=auth_headers
        )
        
        assert backfill_response.status_code == 200
        backfill_data = backfill_response.json()
        assert backfill_data["years_backfilled"] == 6
        assert backfill_data["total_amount"] == 28800.00
        
        # Verify transactions created
        transactions = db.query(Transaction).filter(
            Transaction.property_id == property.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).all()
        
        assert len(transactions) == 6
        
        print("✓ UAT-2.3 PASSED: Historical depreciation backfilled successfully")


class TestTransactionLinkingUAT:
    """UAT Scenario 3: Transaction Linking"""
    
    def test_link_rental_income_to_property(
        self,
        client: TestClient,
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-3.1: Link rental income transaction to property
        
        Steps:
        1. User has rental income transaction
        2. User selects property to link
        3. System validates and creates link
        4. Transaction appears in property details
        """
        # Create property
        property = Property(
            user_id=landlord_user.id,
            property_type=PropertyType.RENTAL,
            street="Miethaus Straße 5",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2024, 1, 1),
            purchase_price=Decimal("300000"),
            building_value=Decimal("240000"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        
        # Create rental income transaction
        transaction = Transaction(
            user_id=landlord_user.id,
            type=TransactionType.INCOME,
            amount=Decimal("1200.00"),
            transaction_date=date(2025, 1, 1),
            description="Miete Januar 2025",
            income_category="rental_income"
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        # Link transaction to property
        link_response = client.post(
            f"/api/v1/properties/{property.id}/link-transaction",
            json={"transaction_id": transaction.id},
            headers=auth_headers
        )
        
        assert link_response.status_code == 200
        
        # Verify link
        db.refresh(transaction)
        assert transaction.property_id == property.id
        
        print("✓ UAT-3.1 PASSED: Rental income linked to property")
    
    def test_view_property_transactions(
        self,
        client: TestClient,
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-3.2: View all transactions for a property
        
        Steps:
        1. User selects a property
        2. System displays all linked transactions
        3. Transactions grouped by category
        """
        # Create property with transactions
        property = Property(
            user_id=landlord_user.id,
            property_type=PropertyType.RENTAL,
            street="Vermietung Straße 20",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2024, 1, 1),
            purchase_price=Decimal("300000"),
            building_value=Decimal("240000"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        
        # Create various transactions
        transactions = [
            Transaction(
                user_id=landlord_user.id,
                property_id=property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1200.00"),
                transaction_date=date(2025, 1, 1),
                description="Miete Januar",
                income_category="rental_income"
            ),
            Transaction(
                user_id=landlord_user.id,
                property_id=property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("150.00"),
                transaction_date=date(2025, 1, 15),
                description="Reparatur",
                expense_category=ExpenseCategory.MAINTENANCE_REPAIRS
            ),
            Transaction(
                user_id=landlord_user.id,
                property_id=property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("4800.00"),
                transaction_date=date(2025, 12, 31),
                description="AfA 2025",
                expense_category=ExpenseCategory.DEPRECIATION_AFA,
                is_system_generated=True
            )
        ]
        
        for txn in transactions:
            db.add(txn)
        db.commit()
        
        # Get property transactions
        response = client.get(
            f"/api/v1/properties/{property.id}/transactions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 3
        
        print("✓ UAT-3.2 PASSED: Property transactions displayed correctly")


class TestE1BescheidIntegrationUAT:
    """UAT Scenario 4: E1/Bescheid Integration"""
    
    @pytest.mark.skip(reason="Requires E1 import service integration")
    def test_e1_import_suggests_property_linking(
        self,
        client: TestClient,
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-4.1: E1 import detects rental income and suggests property linking
        
        Steps:
        1. User uploads E1 form with rental income (KZ 350)
        2. System extracts rental income
        3. System suggests linking to existing property or creating new
        4. User confirms linking
        """
        # This would test the E1 import integration
        # Placeholder for future implementation
        pass


class TestReportsAndAnalyticsUAT:
    """UAT Scenario 5: Reports and Analytics"""
    
    def test_generate_property_income_statement(
        self,
        client: TestClient,
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-5.1: Generate property income statement report
        
        Steps:
        1. User selects property
        2. User selects date range
        3. System generates income statement
        4. Report shows income, expenses, net income
        """
        # Create property with transactions
        property = Property(
            user_id=landlord_user.id,
            property_type=PropertyType.RENTAL,
            street="Report Test Straße 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2024, 1, 1),
            purchase_price=Decimal("300000"),
            building_value=Decimal("240000"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property)
        db.commit()
        db.refresh(property)
        
        # Add transactions for 2025
        transactions = [
            Transaction(
                user_id=landlord_user.id,
                property_id=property.id,
                type=TransactionType.INCOME,
                amount=Decimal("14400.00"),  # 1,200 * 12 months
                transaction_date=date(2025, 12, 31),
                description="Rental Income 2025",
                income_category="rental_income"
            ),
            Transaction(
                user_id=landlord_user.id,
                property_id=property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("1800.00"),
                transaction_date=date(2025, 12, 31),
                description="Maintenance 2025",
                expense_category=ExpenseCategory.MAINTENANCE_REPAIRS
            ),
            Transaction(
                user_id=landlord_user.id,
                property_id=property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("4800.00"),
                transaction_date=date(2025, 12, 31),
                description="AfA 2025",
                expense_category=ExpenseCategory.DEPRECIATION_AFA,
                is_system_generated=True
            )
        ]
        
        for txn in transactions:
            db.add(txn)
        db.commit()
        
        # Generate report
        response = client.get(
            f"/api/v1/properties/{property.id}/reports/income-statement",
            params={"year": 2025},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_income"] == 14400.00
        assert data["total_expenses"] == 6600.00  # 1,800 + 4,800
        assert data["net_income"] == 7800.00  # 14,400 - 6,600
        
        print("✓ UAT-5.1 PASSED: Income statement generated correctly")


class TestMultiPropertyPortfolioUAT:
    """UAT Scenario 6: Multi-Property Portfolio"""
    
    def test_portfolio_dashboard_metrics(
        self,
        client: TestClient,
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-6.1: View portfolio-level metrics
        
        Steps:
        1. User has multiple properties
        2. User views portfolio dashboard
        3. System shows aggregated metrics
        """
        # Create multiple properties
        properties = [
            Property(
                user_id=landlord_user.id,
                property_type=PropertyType.RENTAL,
                street=f"Portfolio Straße {i}",
                city="Wien",
                postal_code="1010",
                purchase_date=date(2024, 1, 1),
                purchase_price=Decimal("300000"),
                building_value=Decimal("240000"),
                depreciation_rate=Decimal("0.02"),
                status=PropertyStatus.ACTIVE
            )
            for i in range(1, 4)  # 3 properties
        ]
        
        for prop in properties:
            db.add(prop)
        db.commit()
        
        # Get portfolio metrics
        response = client.get(
            "/api/v1/properties/portfolio/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_properties"] == 3
        assert data["total_building_value"] == 720000.00  # 240,000 * 3
        assert data["total_annual_depreciation"] == 14400.00  # 4,800 * 3
        
        print("✓ UAT-6.1 PASSED: Portfolio metrics calculated correctly")


class TestPerformanceUAT:
    """UAT Scenario 7: Performance and Scalability"""
    
    def test_performance_with_100_properties(
        self,
        client: TestClient,
        landlord_user: User,
        auth_headers: Dict[str, str],
        db: Session
    ):
        """
        UAT-7.1: System performs well with 100+ properties
        
        Steps:
        1. Create 100 properties for user
        2. Measure list query performance
        3. Verify response time < 1 second
        """
        import time
        
        # Create 100 properties
        properties = []
        for i in range(100):
            prop = Property(
                user_id=landlord_user.id,
                property_type=PropertyType.RENTAL,
                street=f"Performance Test Straße {i}",
                city="Wien",
                postal_code="1010",
                purchase_date=date(2024, 1, 1),
                purchase_price=Decimal("300000"),
                building_value=Decimal("240000"),
                depreciation_rate=Decimal("0.02"),
                status=PropertyStatus.ACTIVE
            )
            properties.append(prop)
        
        db.bulk_save_objects(properties)
        db.commit()
        
        # Measure query performance
        start_time = time.time()
        response = client.get("/api/v1/properties", headers=auth_headers)
        end_time = time.time()
        
        query_time = end_time - start_time
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["properties"]) == 100
        assert query_time < 1.0  # Should complete in less than 1 second
        
        print(f"✓ UAT-7.1 PASSED: Query completed in {query_time:.3f}s (< 1s)")


# UAT Test Suite Summary
def print_uat_summary():
    """Print UAT test suite summary"""
    print("\n" + "="*70)
    print("PROPERTY ASSET MANAGEMENT - UAT TEST SUITE")
    print("="*70)
    print("\nTest Scenarios:")
    print("  1. Property Registration and Management")
    print("  2. Depreciation Calculation and Backfill")
    print("  3. Transaction Linking")
    print("  4. E1/Bescheid Integration")
    print("  5. Reports and Analytics")
    print("  6. Multi-Property Portfolio")
    print("  7. Performance and Scalability")
    print("\nRun with: pytest backend/tests/uat/test_property_uat.py -v")
    print("="*70 + "\n")


if __name__ == "__main__":
    print_uat_summary()
