"""
Tests for Property Report Export Service

Tests PDF and CSV export functionality for:
- Income statements
- Depreciation schedules
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, ExpenseCategory, IncomeCategory
from app.models.user import User
from app.services.property_report_export_service import PropertyReportExportService
from app.services.property_report_service import PropertyReportService


@pytest.fixture
def test_user(db: Session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        name="Test User",
        user_type="landlord",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_property(db: Session, test_user: User):
    """Create a test property"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Teststraße 123",
        city="Wien",
        postal_code="1010",
        address="Teststraße 123, 1010 Wien",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE,
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


@pytest.fixture
def test_transactions(db: Session, test_user: User, test_property: Property):
    """Create test transactions for the property"""
    transactions = [
        # Rental income
        Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1500.00"),
            transaction_date=date(2026, 1, 1),
            description="Rent January",
            income_category=IncomeCategory.RENTAL_INCOME,
            is_deductible=False,
        ),
        Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1500.00"),
            transaction_date=date(2026, 2, 1),
            description="Rent February",
            income_category=IncomeCategory.RENTAL_INCOME,
            is_deductible=False,
        ),
        # Expenses
        Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5600.00"),
            transaction_date=date(2026, 12, 31),
            description="AfA 2026",
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_deductible=True,
            is_system_generated=True,
        ),
        Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("100.00"),
            transaction_date=date(2026, 3, 15),
            description="Property management fee",
            expense_category=ExpenseCategory.PROPERTY_MANAGEMENT_FEES,
            is_deductible=True,
        ),
        Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("200.00"),
            transaction_date=date(2026, 5, 20),
            description="Maintenance",
            expense_category=ExpenseCategory.MAINTENANCE_REPAIRS,
            is_deductible=True,
        ),
    ]
    
    for transaction in transactions:
        db.add(transaction)
    
    db.commit()
    return transactions


class TestPropertyReportExportService:
    """Test PropertyReportExportService"""

    def test_export_income_statement_pdf_german(
        self, db: Session, test_property: Property, test_transactions
    ):
        """Test exporting income statement to PDF in German"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="de")
        
        # Generate report data
        report_data = report_service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        
        # Export to PDF
        pdf_bytes = export_service.export_income_statement_pdf(report_data)
        
        # Verify PDF was generated
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"  # PDF magic number
        
        # Verify it's a valid PDF (contains PDF structure)
        pdf_content = pdf_bytes.decode("latin-1", errors="ignore")
        assert "Einnahmen-Ausgaben-Rechnung" in pdf_content  # German title
        assert "Teststraße 123" in pdf_content  # Property address

    def test_export_income_statement_pdf_english(
        self, db: Session, test_property: Property, test_transactions
    ):
        """Test exporting income statement to PDF in English"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="en")
        
        # Generate report data
        report_data = report_service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        
        # Export to PDF
        pdf_bytes = export_service.export_income_statement_pdf(report_data)
        
        # Verify PDF was generated
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"
        
        # Verify English content
        pdf_content = pdf_bytes.decode("latin-1", errors="ignore")
        assert "Income Statement" in pdf_content  # English title

    def test_export_income_statement_csv_german(
        self, db: Session, test_property: Property, test_transactions
    ):
        """Test exporting income statement to CSV in German"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="de")
        
        # Generate report data
        report_data = report_service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        
        # Export to CSV
        csv_content = export_service.export_income_statement_csv(report_data)
        
        # Verify CSV was generated
        assert csv_content is not None
        assert len(csv_content) > 0
        
        # Verify CSV structure and content
        lines = csv_content.strip().split("\n")
        assert len(lines) > 5  # Should have multiple lines
        
        # Check for German headers
        assert "Immobiliendetails" in csv_content
        assert "Adresse" in csv_content
        assert "Einnahmen" in csv_content
        assert "Ausgaben" in csv_content
        assert "Nettoeinkommen" in csv_content
        
        # Check for property data
        assert "Teststraße 123" in csv_content
        assert "280000.00" in csv_content  # Building value

    def test_export_income_statement_csv_english(
        self, db: Session, test_property: Property, test_transactions
    ):
        """Test exporting income statement to CSV in English"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="en")
        
        # Generate report data
        report_data = report_service.generate_income_statement(
            str(test_property.id),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        
        # Export to CSV
        csv_content = export_service.export_income_statement_csv(report_data)
        
        # Verify English headers
        assert "Property Details" in csv_content
        assert "Address" in csv_content
        assert "Income" in csv_content
        assert "Expenses" in csv_content
        assert "Net Income" in csv_content

    def test_export_depreciation_schedule_pdf_german(
        self, db: Session, test_property: Property
    ):
        """Test exporting depreciation schedule to PDF in German"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="de")
        
        # Generate report data
        report_data = report_service.generate_depreciation_schedule(
            str(test_property.id),
            include_future=True,
            future_years=5,
        )
        
        # Export to PDF
        pdf_bytes = export_service.export_depreciation_schedule_pdf(report_data)
        
        # Verify PDF was generated
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"
        
        # Verify German content
        pdf_content = pdf_bytes.decode("latin-1", errors="ignore")
        assert "AfA-Plan" in pdf_content  # German title
        assert "Teststraße 123" in pdf_content

    def test_export_depreciation_schedule_pdf_english(
        self, db: Session, test_property: Property
    ):
        """Test exporting depreciation schedule to PDF in English"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="en")
        
        # Generate report data
        report_data = report_service.generate_depreciation_schedule(
            str(test_property.id),
            include_future=True,
            future_years=5,
        )
        
        # Export to PDF
        pdf_bytes = export_service.export_depreciation_schedule_pdf(report_data)
        
        # Verify English content
        pdf_content = pdf_bytes.decode("latin-1", errors="ignore")
        assert "Depreciation Schedule" in pdf_content

    def test_export_depreciation_schedule_csv_german(
        self, db: Session, test_property: Property
    ):
        """Test exporting depreciation schedule to CSV in German"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="de")
        
        # Generate report data
        report_data = report_service.generate_depreciation_schedule(
            str(test_property.id),
            include_future=True,
            future_years=5,
        )
        
        # Export to CSV
        csv_content = export_service.export_depreciation_schedule_csv(report_data)
        
        # Verify CSV was generated
        assert csv_content is not None
        assert len(csv_content) > 0
        
        # Verify German headers
        assert "AfA-Plan" in csv_content
        assert "Jahr" in csv_content
        assert "Jährliche AfA" in csv_content
        assert "Kumulierte AfA" in csv_content
        assert "Restwert" in csv_content
        
        # Check for property data
        assert "Teststraße 123" in csv_content
        assert "2020" in csv_content  # Purchase year

    def test_export_depreciation_schedule_csv_english(
        self, db: Session, test_property: Property
    ):
        """Test exporting depreciation schedule to CSV in English"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="en")
        
        # Generate report data
        report_data = report_service.generate_depreciation_schedule(
            str(test_property.id),
            include_future=True,
            future_years=5,
        )
        
        # Export to CSV
        csv_content = export_service.export_depreciation_schedule_csv(report_data)
        
        # Verify English headers
        assert "Depreciation Schedule" in csv_content
        assert "Year" in csv_content
        assert "Annual Depreciation" in csv_content
        assert "Accumulated Depreciation" in csv_content
        assert "Remaining Value" in csv_content

    def test_export_includes_property_details_in_header(
        self, db: Session, test_property: Property, test_transactions
    ):
        """Test that exports include property details in header"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="de")
        
        # Generate income statement
        report_data = report_service.generate_income_statement(
            str(test_property.id)
        )
        
        # Export to CSV
        csv_content = export_service.export_income_statement_csv(report_data)
        
        # Verify property details are in header
        assert "Teststraße 123, 1010 Wien" in csv_content
        assert "2020-06-15" in csv_content  # Purchase date
        assert "280000.00" in csv_content  # Building value

    def test_export_csv_parseable(
        self, db: Session, test_property: Property, test_transactions
    ):
        """Test that exported CSV is parseable"""
        import csv
        import io
        
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="de")
        
        # Generate and export
        report_data = report_service.generate_income_statement(
            str(test_property.id)
        )
        csv_content = export_service.export_income_statement_csv(report_data)
        
        # Parse CSV
        csv_file = io.StringIO(csv_content)
        reader = csv.reader(csv_file)
        rows = list(reader)
        
        # Verify we can parse it
        assert len(rows) > 0
        assert all(isinstance(row, list) for row in rows)

    def test_export_depreciation_schedule_with_projections(
        self, db: Session, test_property: Property
    ):
        """Test depreciation schedule export includes projected years"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="de")
        
        # Generate with future projections
        report_data = report_service.generate_depreciation_schedule(
            str(test_property.id),
            include_future=True,
            future_years=10,
        )
        
        # Export to CSV
        csv_content = export_service.export_depreciation_schedule_csv(report_data)
        
        # Verify projected years are marked
        assert "Projiziert" in csv_content
        assert "Tatsächlich" in csv_content

    def test_export_handles_empty_expenses(
        self, db: Session, test_property: Property
    ):
        """Test export handles properties with no expenses"""
        report_service = PropertyReportService(db)
        export_service = PropertyReportExportService(language="de")
        
        # Generate report (no transactions created)
        report_data = report_service.generate_income_statement(
            str(test_property.id)
        )
        
        # Export should not fail
        pdf_bytes = export_service.export_income_statement_pdf(report_data)
        assert pdf_bytes is not None
        
        csv_content = export_service.export_income_statement_csv(report_data)
        assert csv_content is not None

    def test_export_filename_generation(
        self, db: Session, test_property: Property
    ):
        """Test that export filenames are properly formatted"""
        # This would be tested at the API level, but we can verify
        # the service returns valid data for filename generation
        report_service = PropertyReportService(db)
        
        report_data = report_service.generate_income_statement(
            str(test_property.id)
        )
        
        # Verify property ID is in the data
        assert "id" in report_data["property"]
        assert report_data["property"]["id"] == str(test_property.id)
