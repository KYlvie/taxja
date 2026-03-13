"""
Unit tests for PropertyReportService

Tests income statement generation with various scenarios:
- No transactions
- Multiple income/expense transactions
- Date range filtering
- Default date range (current year)
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User
from app.services.property_report_service import PropertyReportService


# Test database URL
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session with only required tables"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    
    # Only create the tables we need for testing
    from app.models.user import User
    from app.models.property import Property
    from app.models.transaction import Transaction
    
    User.__table__.create(bind=engine, checkfirst=True)
    Property.__table__.create(bind=engine, checkfirst=True)
    Transaction.__table__.create(bind=engine, checkfirst=True)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop only the tables we created
        Transaction.__table__.drop(bind=engine, checkfirst=True)
        Property.__table__.drop(bind=engine, checkfirst=True)
        User.__table__.drop(bind=engine, checkfirst=True)


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test User",
        user_type="employee"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_property(db_session, test_user):
    """Create a test property"""
    property = Property(
        id=uuid4(),
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    # Set encrypted fields using property setters
    property.street = "Teststraße 123"
    property.city = "Wien"
    property.postal_code = "1010"
    property.address = "Teststraße 123, 1010 Wien"
    
    db_session.add(property)
    db_session.commit()
    db_session.refresh(property)
    return property


class TestPropertyReportService:
    """Test suite for PropertyReportService"""

    def test_generate_income_statement_no_transactions(self, db_session, test_property):
        """Test income statement generation with no transactions"""
        service = PropertyReportService(db_session)
        
        report = service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31)
        )
        
        # Verify structure
        assert "property" in report
        assert "period" in report
        assert "income" in report
        assert "expenses" in report
        assert "net_income" in report
        
        # Verify property details
        assert report["property"]["id"] == str(test_property.id)
        assert report["property"]["address"] == "Teststraße 123, 1010 Wien"
        assert report["property"]["building_value"] == 280000.00
        
        # Verify period
        assert report["period"]["start_date"] == "2026-01-01"
        assert report["period"]["end_date"] == "2026-12-31"
        
        # Verify zero amounts
        assert report["income"]["rental_income"] == 0.0
        assert report["income"]["total_income"] == 0.0
        assert report["expenses"]["total_expenses"] == 0.0
        assert report["net_income"] == 0.0
        assert report["expenses"]["by_category"] == {}

    def test_generate_income_statement_with_income(self, db_session, test_property, test_user):
        """Test income statement with rental income transactions"""
        service = PropertyReportService(db_session)
        
        # Create rental income transactions
        transactions = [
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, 1, 1),
                description="Miete Januar 2026",
                income_category=IncomeCategory.RENTAL
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, 2, 1),
                description="Miete Februar 2026",
                income_category=IncomeCategory.RENTAL
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, 3, 1),
                description="Miete März 2026",
                income_category=IncomeCategory.RENTAL
            ),
        ]
        
        for txn in transactions:
            db_session.add(txn)
        db_session.commit()
        
        # Generate report
        report = service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31)
        )
        
        # Verify income
        assert report["income"]["rental_income"] == 4500.00
        assert report["income"]["total_income"] == 4500.00
        assert report["net_income"] == 4500.00

    def test_generate_income_statement_with_expenses(self, db_session, test_property, test_user):
        """Test income statement with expense transactions"""
        service = PropertyReportService(db_session)
        
        # Create expense transactions
        transactions = [
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("5600.00"),
                transaction_date=date(2025, 12, 31),
                description="AfA 2025",
                expense_category=ExpenseCategory.DEPRECIATION_AFA,
                is_system_generated=True
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("350.00"),
                transaction_date=date(2026, 2, 15),
                description="Hausverwaltung",
                expense_category=ExpenseCategory.PROPERTY_MANAGEMENT_FEES
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("800.00"),
                transaction_date=date(2026, 3, 10),
                description="Gebäudeversicherung",
                expense_category=ExpenseCategory.PROPERTY_INSURANCE
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("1200.00"),
                transaction_date=date(2026, 5, 20),
                description="Reparatur Heizung",
                expense_category=ExpenseCategory.MAINTENANCE
            ),
        ]
        
        for txn in transactions:
            db_session.add(txn)
        db_session.commit()
        
        # Generate report for 2026 only (should exclude 2025 depreciation)
        report = service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31)
        )
        
        # Verify expenses
        assert report["expenses"]["total_expenses"] == 2350.00
        assert report["expenses"]["by_category"]["property_management_fees"] == 350.00
        assert report["expenses"]["by_category"]["property_insurance"] == 800.00
        assert report["expenses"]["by_category"]["maintenance"] == 1200.00
        assert "depreciation_afa" not in report["expenses"]["by_category"]  # 2025 transaction excluded

    def test_generate_income_statement_complete(self, db_session, test_property, test_user):
        """Test complete income statement with both income and expenses"""
        service = PropertyReportService(db_session)
        
        # Create income transactions
        income_transactions = [
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, month, 1),
                description=f"Miete {month}/2026",
                income_category=IncomeCategory.RENTAL
            )
            for month in range(1, 13)  # 12 months
        ]
        
        # Create expense transactions
        expense_transactions = [
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("5600.00"),
                transaction_date=date(2026, 12, 31),
                description="AfA 2026",
                expense_category=ExpenseCategory.DEPRECIATION_AFA,
                is_system_generated=True
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("350.00"),
                transaction_date=date(2026, 2, 15),
                description="Hausverwaltung",
                expense_category=ExpenseCategory.PROPERTY_MANAGEMENT_FEES
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("800.00"),
                transaction_date=date(2026, 3, 10),
                description="Gebäudeversicherung",
                expense_category=ExpenseCategory.PROPERTY_INSURANCE
            ),
        ]
        
        for txn in income_transactions + expense_transactions:
            db_session.add(txn)
        db_session.commit()
        
        # Generate report
        report = service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31)
        )
        
        # Verify income
        assert report["income"]["rental_income"] == 18000.00  # 12 * 1500
        assert report["income"]["total_income"] == 18000.00
        
        # Verify expenses
        assert report["expenses"]["total_expenses"] == 6750.00  # 5600 + 350 + 800
        assert report["expenses"]["by_category"]["depreciation_afa"] == 5600.00
        assert report["expenses"]["by_category"]["property_management_fees"] == 350.00
        assert report["expenses"]["by_category"]["property_insurance"] == 800.00
        
        # Verify net income
        assert report["net_income"] == 11250.00  # 18000 - 6750

    def test_generate_income_statement_date_range_filtering(self, db_session, test_property, test_user):
        """Test that date range filtering works correctly"""
        service = PropertyReportService(db_session)
        
        # Create transactions across multiple years
        transactions = [
            # 2025 transactions (should be excluded)
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2025, 12, 1),
                description="Miete Dezember 2025",
                income_category=IncomeCategory.RENTAL
            ),
            # 2026 Q1 transactions (should be included)
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, 1, 1),
                description="Miete Januar 2026",
                income_category=IncomeCategory.RENTAL
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, 2, 1),
                description="Miete Februar 2026",
                income_category=IncomeCategory.RENTAL
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, 3, 1),
                description="Miete März 2026",
                income_category=IncomeCategory.RENTAL
            ),
            # 2026 Q2 transactions (should be excluded)
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, 4, 1),
                description="Miete April 2026",
                income_category=IncomeCategory.RENTAL
            ),
        ]
        
        for txn in transactions:
            db_session.add(txn)
        db_session.commit()
        
        # Generate report for Q1 2026 only
        report = service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31)
        )
        
        # Should only include 3 months (Jan, Feb, Mar 2026)
        assert report["income"]["rental_income"] == 4500.00  # 3 * 1500
        assert report["period"]["start_date"] == "2026-01-01"
        assert report["period"]["end_date"] == "2026-03-31"

    def test_generate_income_statement_default_date_range(self, db_session, test_property, test_user):
        """Test that default date range is current year"""
        service = PropertyReportService(db_session)
        
        current_year = date.today().year
        
        # Create transaction in current year
        transaction = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1500.00"),
            transaction_date=date(current_year, 1, 1),
            description=f"Miete Januar {current_year}",
            income_category=IncomeCategory.RENTAL
        )
        db_session.add(transaction)
        db_session.commit()
        
        # Generate report without specifying dates
        report = service.generate_income_statement(str(test_property.id))
        
        # Verify default date range
        assert report["period"]["start_date"] == f"{current_year}-01-01"
        assert report["period"]["end_date"] == date.today().isoformat()
        assert report["income"]["rental_income"] == 1500.00

    def test_generate_income_statement_property_not_found(self, db_session):
        """Test that ValueError is raised for non-existent property"""
        service = PropertyReportService(db_session)
        
        non_existent_id = uuid4()  # Use UUID object, not string
        
        with pytest.raises(ValueError, match="Property .* not found"):
            service.generate_income_statement(
                str(non_existent_id),  # Convert to string when calling
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31)
            )

    def test_generate_income_statement_multiple_expense_categories(self, db_session, test_property, test_user):
        """Test income statement with multiple transactions in same category"""
        service = PropertyReportService(db_session)
        
        # Create multiple maintenance expenses
        transactions = [
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("500.00"),
                transaction_date=date(2026, 2, 10),
                description="Reparatur Fenster",
                expense_category=ExpenseCategory.MAINTENANCE
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("800.00"),
                transaction_date=date(2026, 5, 15),
                description="Reparatur Heizung",
                expense_category=ExpenseCategory.MAINTENANCE
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("300.00"),
                transaction_date=date(2026, 8, 20),
                description="Reparatur Tür",
                expense_category=ExpenseCategory.MAINTENANCE
            ),
        ]
        
        for txn in transactions:
            db_session.add(txn)
        db_session.commit()
        
        # Generate report
        report = service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31)
        )
        
        # Verify that maintenance expenses are summed correctly
        assert report["expenses"]["by_category"]["maintenance"] == 1600.00  # 500 + 800 + 300
        assert report["expenses"]["total_expenses"] == 1600.00


class TestDepreciationScheduleGeneration:
    """Test suite for depreciation schedule generation"""

    def test_generate_depreciation_schedule_basic(self, db_session, test_property, test_user):
        """Test basic depreciation schedule generation"""
        service = PropertyReportService(db_session)
        
        # Generate schedule without future projections
        report = service.generate_depreciation_schedule(
            str(test_property.id),
            include_future=False
        )
        
        # Verify structure
        assert "property" in report
        assert "schedule" in report
        assert "summary" in report
        
        # Verify property details
        assert report["property"]["id"] == str(test_property.id)
        assert report["property"]["address"] == "Teststraße 123, 1010 Wien"
        assert report["property"]["building_value"] == 280000.00
        assert report["property"]["depreciation_rate"] == 0.02
        assert report["property"]["status"] == "active"
        
        # Verify schedule exists (2020-2026 = 7 years)
        current_year = date.today().year
        expected_years = current_year - 2020 + 1
        assert len(report["schedule"]) == expected_years
        
        # Verify all entries are not projected
        for year_data in report["schedule"]:
            assert year_data["is_projected"] is False

    def test_generate_depreciation_schedule_with_future_projections(self, db_session, test_property, test_user):
        """Test depreciation schedule with future projections"""
        service = PropertyReportService(db_session)
        
        # Generate schedule with 5 years of future projections
        report = service.generate_depreciation_schedule(
            str(test_property.id),
            include_future=True,
            future_years=5
        )
        
        # Verify schedule includes both historical and projected
        assert len(report["schedule"]) > 0
        
        # Check that some entries are projected
        projected_entries = [y for y in report["schedule"] if y["is_projected"]]
        actual_entries = [y for y in report["schedule"] if not y["is_projected"]]
        
        assert len(actual_entries) > 0
        assert len(projected_entries) > 0
        assert len(projected_entries) <= 5  # Should not exceed requested future_years
        
        # Verify summary
        assert report["summary"]["years_elapsed"] == len(actual_entries)
        assert report["summary"]["years_projected"] == len(projected_entries)
        assert report["summary"]["total_years"] == len(actual_entries) + len(projected_entries)

    def test_generate_depreciation_schedule_partial_first_year(self, db_session, test_user):
        """Test depreciation schedule with mid-year purchase"""
        # Create property purchased mid-year
        property = Property(
            id=uuid4(),
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            purchase_date=date(2025, 7, 1),  # Mid-year purchase
            purchase_price=Decimal("240000.00"),
            building_value=Decimal("192000.00"),
            construction_year=2000,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        property.street = "Midyear Property"
        property.city = "Wien"
        property.postal_code = "1010"
        property.address = "Midyear Property, 1010 Wien"
        
        db_session.add(property)
        db_session.commit()
        db_session.refresh(property)
        
        service = PropertyReportService(db_session)
        report = service.generate_depreciation_schedule(
            str(property.id),
            include_future=False
        )
        
        # First year should have pro-rated depreciation (6 months)
        first_year = report["schedule"][0]
        assert first_year["year"] == 2025
        # Expected: (192000 * 0.02 * 6) / 12 = 1920
        assert abs(first_year["annual_depreciation"] - 1920.00) < 0.01

    def test_generate_depreciation_schedule_sold_property(self, db_session, test_user):
        """Test depreciation schedule for sold property"""
        # Create sold property
        property = Property(
            id=uuid4(),
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            construction_year=1990,
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.SOLD,
            sale_date=date(2024, 6, 30)
        )
        property.street = "Sold Property"
        property.city = "Wien"
        property.postal_code = "1010"
        property.address = "Sold Property, 1010 Wien"
        
        db_session.add(property)
        db_session.commit()
        db_session.refresh(property)
        
        service = PropertyReportService(db_session)
        report = service.generate_depreciation_schedule(
            str(property.id),
            include_future=True  # Should not include future for sold property
        )
        
        # Should only include years up to sale year
        assert all(y["year"] <= 2024 for y in report["schedule"])
        
        # Should have no projected entries
        projected_entries = [y for y in report["schedule"] if y["is_projected"]]
        assert len(projected_entries) == 0
        
        # Verify sale date in property details
        assert report["property"]["sale_date"] == "2024-06-30"

    def test_generate_depreciation_schedule_accumulated_calculation(self, db_session, test_property, test_user):
        """Test that accumulated depreciation is calculated correctly"""
        service = PropertyReportService(db_session)
        
        report = service.generate_depreciation_schedule(
            str(test_property.id),
            include_future=False
        )
        
        # Verify accumulated depreciation increases monotonically
        previous_accumulated = Decimal("0")
        for year_data in report["schedule"]:
            current_accumulated = Decimal(str(year_data["accumulated_depreciation"]))
            annual_dep = Decimal(str(year_data["annual_depreciation"]))
            
            assert current_accumulated >= previous_accumulated
            assert abs(current_accumulated - (previous_accumulated + annual_dep)) < Decimal("0.01")
            previous_accumulated = current_accumulated
        
        # Verify remaining value decreases
        for year_data in report["schedule"]:
            accumulated = Decimal(str(year_data["accumulated_depreciation"]))
            remaining = Decimal(str(year_data["remaining_value"]))
            expected_remaining = test_property.building_value - accumulated
            assert abs(remaining - expected_remaining) < Decimal("0.01")

    def test_generate_depreciation_schedule_summary_metrics(self, db_session, test_property, test_user):
        """Test that summary metrics are calculated correctly"""
        service = PropertyReportService(db_session)
        
        report = service.generate_depreciation_schedule(
            str(test_property.id),
            include_future=True,
            future_years=10
        )
        
        summary = report["summary"]
        
        # Verify summary fields exist
        assert "total_years" in summary
        assert "years_elapsed" in summary
        assert "years_projected" in summary
        assert "accumulated_depreciation" in summary
        assert "remaining_value" in summary
        assert "years_remaining" in summary
        
        # Verify totals match schedule
        assert summary["total_years"] == len(report["schedule"])
        
        # Verify accumulated matches last historical entry
        historical_entries = [y for y in report["schedule"] if not y["is_projected"]]
        if historical_entries:
            last_historical = historical_entries[-1]
            assert summary["accumulated_depreciation"] == last_historical["accumulated_depreciation"]


class TestReportExportFunctionality:
    """Test suite for report export to PDF and CSV"""

    def test_export_income_statement_pdf(self, db_session, test_property, test_user):
        """Test PDF export of income statement"""
        service = PropertyReportService(db_session)
        
        # Create some transactions
        transactions = [
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, 1, 1),
                description="Miete Januar",
                income_category=IncomeCategory.RENTAL
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("500.00"),
                transaction_date=date(2026, 1, 15),
                description="Reparatur",
                expense_category=ExpenseCategory.MAINTENANCE
            ),
        ]
        for txn in transactions:
            db_session.add(txn)
        db_session.commit()
        
        # Export to PDF
        pdf_bytes = service.export_income_statement_pdf(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            language="de"
        )
        
        # Verify PDF was generated
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # PDF files start with %PDF
        assert pdf_bytes[:4] == b'%PDF'

    def test_export_income_statement_csv(self, db_session, test_property, test_user):
        """Test CSV export of income statement"""
        service = PropertyReportService(db_session)
        
        # Create some transactions
        transactions = [
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2026, 1, 1),
                description="Miete Januar",
                income_category=IncomeCategory.RENTAL
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("500.00"),
                transaction_date=date(2026, 1, 15),
                description="Reparatur",
                expense_category=ExpenseCategory.MAINTENANCE
            ),
        ]
        for txn in transactions:
            db_session.add(txn)
        db_session.commit()
        
        # Export to CSV
        csv_content = service.export_income_statement_csv(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            language="de"
        )
        
        # Verify CSV was generated
        assert isinstance(csv_content, str)
        assert len(csv_content) > 0
        # Check for key content
        assert "Teststraße 123, 1010 Wien" in csv_content
        assert "1500.00" in csv_content
        assert "500.00" in csv_content

    def test_export_depreciation_schedule_pdf(self, db_session, test_property, test_user):
        """Test PDF export of depreciation schedule"""
        service = PropertyReportService(db_session)
        
        # Export to PDF
        pdf_bytes = service.export_depreciation_schedule_pdf(
            str(test_property.id),
            include_future=True,
            future_years=5,
            language="de"
        )
        
        # Verify PDF was generated
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'

    def test_export_depreciation_schedule_csv(self, db_session, test_property, test_user):
        """Test CSV export of depreciation schedule"""
        service = PropertyReportService(db_session)
        
        # Export to CSV
        csv_content = service.export_depreciation_schedule_csv(
            str(test_property.id),
            include_future=True,
            future_years=5,
            language="de"
        )
        
        # Verify CSV was generated
        assert isinstance(csv_content, str)
        assert len(csv_content) > 0
        # Check for key content
        assert "Teststraße 123, 1010 Wien" in csv_content
        assert "280000.00" in csv_content
        assert "0.02" in csv_content or "2.00%" in csv_content

    def test_export_with_english_language(self, db_session, test_property, test_user):
        """Test export with English language"""
        service = PropertyReportService(db_session)
        
        # Export income statement in English
        csv_content = service.export_income_statement_csv(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            language="en"
        )
        
        # Verify English translations are used
        assert "Income Statement" in csv_content or "Property Details" in csv_content
        assert "Address" in csv_content

    def test_export_income_statement_with_negative_net_income(self, db_session, test_property, test_user):
        """Test export handles negative net income correctly"""
        service = PropertyReportService(db_session)
        
        # Create transactions with more expenses than income
        transactions = [
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("500.00"),
                transaction_date=date(2026, 1, 1),
                description="Miete",
                income_category=IncomeCategory.RENTAL
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("5000.00"),
                transaction_date=date(2026, 1, 15),
                description="Major Repair",
                expense_category=ExpenseCategory.MAINTENANCE
            ),
        ]
        for txn in transactions:
            db_session.add(txn)
        db_session.commit()
        
        # Export to PDF (should handle negative values)
        pdf_bytes = service.export_income_statement_pdf(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            language="de"
        )
        
        # Should generate successfully even with negative net income
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
