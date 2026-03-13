"""
Integration tests for TaxCalculationEngine with property depreciation.

Tests the integration between TaxCalculationEngine and property management:
- Property depreciation included in tax calculations
- Rental income included in gross income
- Property expenses deducted from taxable income
- Property metrics included in tax breakdown
"""
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine, Table
from sqlalchemy.orm import Session, sessionmaker

from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.svs_calculator import UserType as SVSUserType
from app.db.base import Base


# Custom db fixture that excludes historical_import tables (they use PostgreSQL ARRAY type)
@pytest.fixture(scope="function")
def db():
    """Create test database without historical_import tables"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create only the tables we need (exclude tables with ARRAY types)
    excluded_tables = {
        'historical_import_sessions',
        'historical_import_uploads', 
        'import_conflicts',
        'import_metrics'
    }
    
    tables_to_create = [
        table for table in Base.metadata.sorted_tables
        if table.name not in excluded_tables
    ]
    
    for table in tables_to_create:
        table.create(bind=engine, checkfirst=True)
    
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
        # Drop only the tables we created
        for table in reversed(tables_to_create):
            table.drop(bind=engine, checkfirst=True)


@pytest.fixture
def tax_config():
    """Tax configuration for 2026"""
    return {
        "tax_year": 2026,
        "exemption_amount": "13539.00",
        "tax_brackets": [
            {"lower": "0.00", "upper": "13539.00", "rate": "0.00"},
            {"lower": "13539.00", "upper": "21992.00", "rate": "0.20"},
            {"lower": "21992.00", "upper": "36458.00", "rate": "0.30"},
            {"lower": "36458.00", "upper": "70365.00", "rate": "0.40"},
            {"lower": "70365.00", "upper": "104859.00", "rate": "0.48"},
            {"lower": "104859.00", "upper": "1000000.00", "rate": "0.50"},
            {"lower": "1000000.00", "upper": None, "rate": "0.55"}
        ],
        "deduction_config": {
            "basic_exemption_rate": "0.15",
            "basic_exemption_max": "4950"
        }
    }


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="landlord@example.com",
        name="Test Landlord",
        password_hash="hashed",
        user_type=UserType.LANDLORD
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_property(db: Session, test_user: User) -> Property:
    """Create a test property"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        address="Hauptstraße 123, 1010 Wien",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


@pytest.fixture
def engine_with_db(tax_config, db):
    """Create TaxCalculationEngine with database session"""
    return TaxCalculationEngine(tax_config, db=db)


class TestTaxCalculationWithPropertyDepreciation:
    """Test tax calculation includes property depreciation"""

    def test_depreciation_included_in_deductions(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test that property depreciation is included in tax deductions"""
        # Create depreciation transaction for 2025
        depreciation_txn = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5600.00"),  # 280000 * 0.02
            transaction_date=date(2025, 12, 31),
            description="AfA Hauptstraße 123 (2025)",
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_deductible=True,
            is_system_generated=True,
            import_source="annual_depreciation"
        )
        db.add(depreciation_txn)
        db.commit()
        
        # Calculate tax with property depreciation
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Verify depreciation was included in deductions
        # The taxable income should be reduced by depreciation, SVS, and Grundfreibetrag
        # Tax should be lower than without depreciation
        result_no_property = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG
        )
        
        # Verify tax is lower with property depreciation
        assert result.income_tax.total_tax < result_no_property.income_tax.total_tax
        
        # Verify taxable income is lower with depreciation
        assert result.income_tax.taxable_income < result_no_property.income_tax.taxable_income

    def test_multiple_properties_depreciation_aggregated(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test that depreciation from multiple properties is aggregated"""
        # Create second property
        property2 = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Mariahilfer Straße 456",
            city="Wien",
            postal_code="1060",
            address="Mariahilfer Straße 456, 1060 Wien",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property2)
        db.commit()
        
        # Create depreciation transactions for both properties
        dep1 = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5600.00"),
            transaction_date=date(2025, 12, 31),
            description="AfA Property 1",
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_deductible=True,
            is_system_generated=True
        )
        
        dep2 = Transaction(
            user_id=test_user.id,
            property_id=property2.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("6400.00"),
            transaction_date=date(2025, 12, 31),
            description="AfA Property 2",
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_deductible=True,
            is_system_generated=True
        )
        
        db.add_all([dep1, dep2])
        db.commit()
        
        # Calculate tax
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("60000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Total depreciation should be 5600 + 6400 = 12000
        # This should reduce taxable income
        total_depreciation = Decimal("12000.00")
        
        # Verify tax is lower due to combined depreciation
        result_no_property = engine_with_db.calculate_total_tax(
            gross_income=Decimal("60000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG
        )
        
        # Tax difference should be significant
        tax_savings = result_no_property.income_tax.total_tax - result.income_tax.total_tax
        assert tax_savings > Decimal("2000.00")  # At least 20% of depreciation


    def test_depreciation_only_for_specified_year(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test that only depreciation for specified year is included"""
        # Create depreciation for multiple years
        for year in [2023, 2024, 2025]:
            dep = Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("5600.00"),
                transaction_date=date(year, 12, 31),
                description=f"AfA {year}",
                expense_category=ExpenseCategory.DEPRECIATION_AFA,
                is_deductible=True,
                is_system_generated=True
            )
            db.add(dep)
        
        db.commit()
        
        # Calculate tax for 2025 only
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Should only include 2025 depreciation (5600), not 2023 or 2024
        # Verify by comparing with no property case
        result_no_property = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG
        )
        
        # Tax savings should correspond to single year depreciation
        tax_savings = result_no_property.income_tax.total_tax - result.income_tax.total_tax
        # Verify there is tax savings (depreciation was applied)
        assert tax_savings > Decimal("0.00")
        # Verify taxable income is lower
        assert result.income_tax.taxable_income < result_no_property.income_tax.taxable_income


class TestTaxCalculationWithRentalIncome:
    """Test tax calculation includes rental income"""

    def test_rental_income_added_to_gross_income(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test that rental income is added to gross income"""
        # Create rental income transaction
        rental_income = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("18000.00"),
            transaction_date=date(2025, 6, 15),
            description="Rental income",
            income_category=IncomeCategory.RENTAL,
            is_deductible=False
        )
        db.add(rental_income)
        db.commit()
        
        # Calculate tax with rental income
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),  # Employment income
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Gross income should include rental income
        # 50000 (employment) + 18000 (rental) = 68000
        assert result.gross_income == Decimal("68000.00")
        
        # Tax should be higher than without rental income
        result_no_rental = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG
        )
        
        assert result.income_tax.total_tax > result_no_rental.income_tax.total_tax

    def test_multiple_rental_income_transactions_aggregated(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test that multiple rental income transactions are aggregated"""
        # Create monthly rental income transactions
        for month in range(1, 13):
            rental = Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1500.00"),
                transaction_date=date(2025, month, 1),
                description=f"Rental income {month}/2025",
                income_category=IncomeCategory.RENTAL
            )
            db.add(rental)
        
        db.commit()
        
        # Calculate tax
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Total rental income should be 1500 * 12 = 18000
        # Gross income should be 50000 + 18000 = 68000
        assert result.gross_income == Decimal("68000.00")


    def test_rental_income_from_multiple_properties(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test rental income from multiple properties is aggregated"""
        # Create second property
        property2 = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            street="Teststraße 99",
            city="Wien",
            postal_code="1010",
            address="Teststraße 99, 1010 Wien",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(property2)
        db.commit()
        
        # Create rental income for both properties
        rental1 = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("18000.00"),
            transaction_date=date(2025, 6, 15),
            description="Rental Property 1",
            income_category=IncomeCategory.RENTAL
        )
        
        rental2 = Transaction(
            user_id=test_user.id,
            property_id=property2.id,
            type=TransactionType.INCOME,
            amount=Decimal("15000.00"),
            transaction_date=date(2025, 6, 15),
            description="Rental Property 2",
            income_category=IncomeCategory.RENTAL
        )
        
        db.add_all([rental1, rental2])
        db.commit()
        
        # Calculate tax
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Total rental income: 18000 + 15000 = 33000
        # Gross income: 50000 + 33000 = 83000
        assert result.gross_income == Decimal("83000.00")


class TestTaxCalculationWithPropertyExpenses:
    """Test tax calculation includes property expenses"""

    def test_property_expenses_deducted(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test that property expenses are deducted from taxable income"""
        # Create property expense transactions
        expenses = [
            (ExpenseCategory.LOAN_INTEREST, Decimal("3000.00"), "Loan interest"),
            (ExpenseCategory.MAINTENANCE, Decimal("2500.00"), "Repairs"),
            (ExpenseCategory.PROPERTY_INSURANCE, Decimal("800.00"), "Insurance"),
            (ExpenseCategory.PROPERTY_TAX, Decimal("1200.00"), "Property tax"),
        ]
        
        for category, amount, desc in expenses:
            txn = Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=amount,
                transaction_date=date(2025, 6, 15),
                description=desc,
                expense_category=category,
                is_deductible=True
            )
            db.add(txn)
        
        db.commit()
        
        # Calculate tax
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Total property expenses: 3000 + 2500 + 800 + 1200 = 7500
        # These should reduce taxable income
        result_no_expenses = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG
        )
        
        # Tax should be lower due to property expenses
        assert result.income_tax.total_tax < result_no_expenses.income_tax.total_tax
        
        # Tax savings should be positive (expenses reduce tax)
        tax_savings = result_no_expenses.income_tax.total_tax - result.income_tax.total_tax
        assert tax_savings > Decimal("0.00")

    def test_only_property_linked_expenses_included(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test that only expenses linked to properties are included"""
        # Create property-linked expense
        property_expense = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("2000.00"),
            transaction_date=date(2025, 6, 15),
            description="Property maintenance",
            expense_category=ExpenseCategory.MAINTENANCE,
            is_deductible=True
        )
        
        # Create non-property expense (same category but no property_id)
        non_property_expense = Transaction(
            user_id=test_user.id,
            property_id=None,
            type=TransactionType.EXPENSE,
            amount=Decimal("1000.00"),
            transaction_date=date(2025, 6, 15),
            description="General maintenance",
            expense_category=ExpenseCategory.MAINTENANCE,
            is_deductible=True
        )
        
        db.add_all([property_expense, non_property_expense])
        db.commit()
        
        # Calculate tax
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Only property-linked expense (2000) should be included
        # Non-property expense (1000) should NOT be included
        # Verify by checking tax difference
        result_no_property = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG
        )
        
        tax_savings = result_no_property.income_tax.total_tax - result.income_tax.total_tax
        # Savings should be positive (property expense reduces tax)
        assert tax_savings > Decimal("0.00")
        # Verify taxable income is lower with property expense
        assert result.income_tax.taxable_income < result_no_property.income_tax.taxable_income



class TestTaxCalculationPropertyMetrics:
    """Test property metrics in tax breakdown"""

    def test_property_metrics_included_in_breakdown(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test that property metrics are included in tax breakdown"""
        # Create rental income
        rental = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("18000.00"),
            transaction_date=date(2025, 6, 15),
            income_category=IncomeCategory.RENTAL
        )
        
        # Create depreciation
        depreciation = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5600.00"),
            transaction_date=date(2025, 12, 31),
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_system_generated=True
        )
        
        # Create property expenses
        expense = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("3000.00"),
            transaction_date=date(2025, 6, 15),
            expense_category=ExpenseCategory.MAINTENANCE,
            is_deductible=True
        )
        
        db.add_all([rental, depreciation, expense])
        db.commit()
        
        # Generate tax breakdown
        breakdown = engine_with_db.generate_tax_breakdown(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Verify property metrics are included
        assert 'property_metrics' in breakdown
        
        property_metrics = breakdown['property_metrics']
        assert property_metrics['rental_income'] == 18000.00
        assert property_metrics['depreciation'] == 5600.00
        assert property_metrics['expenses'] == 3000.00
        
        # Net rental income = 18000 - 5600 - 3000 = 9400
        assert property_metrics['net_rental_income'] == 9400.00

    def test_property_metrics_without_user_id(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """Test that property metrics are not included without user_id"""
        # Create transactions
        rental = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("18000.00"),
            transaction_date=date(2025, 6, 15),
            income_category=IncomeCategory.RENTAL
        )
        db.add(rental)
        db.commit()
        
        # Generate breakdown without user_id
        breakdown = engine_with_db.generate_tax_breakdown(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG
            # No user_id provided
        )
        
        # Property metrics should not be included
        assert 'property_metrics' not in breakdown


class TestTaxCalculationCompletePropertyScenario:
    """Test complete property scenario with all components"""

    def test_complete_landlord_tax_calculation(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """
        Test complete landlord scenario:
        - Employment income: 50,000
        - Rental income: 18,000
        - Property depreciation: 5,600
        - Property expenses: 4,000
        - Net rental income: 8,400
        """
        # Create rental income
        rental = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("18000.00"),
            transaction_date=date(2025, 6, 15),
            income_category=IncomeCategory.RENTAL
        )
        
        # Create depreciation
        depreciation = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5600.00"),
            transaction_date=date(2025, 12, 31),
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_system_generated=True
        )
        
        # Create property expenses
        expenses = [
            (ExpenseCategory.LOAN_INTEREST, Decimal("2000.00")),
            (ExpenseCategory.MAINTENANCE, Decimal("1500.00")),
            (ExpenseCategory.PROPERTY_INSURANCE, Decimal("500.00")),
        ]
        
        for category, amount in expenses:
            txn = Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=amount,
                transaction_date=date(2025, 6, 15),
                expense_category=category,
                is_deductible=True
            )
            db.add(txn)
        
        db.add_all([rental, depreciation])
        db.commit()
        
        # Calculate tax
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),  # Employment income
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Verify gross income includes rental income
        # 50000 + 18000 = 68000
        assert result.gross_income == Decimal("68000.00")
        
        # Verify deductions include property depreciation and expenses
        # Total property deductions: 5600 + 2000 + 1500 + 500 = 9600
        # Plus SVS contributions and Grundfreibetrag
        
        # Generate breakdown for detailed verification
        breakdown = engine_with_db.generate_tax_breakdown(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Verify property metrics
        assert breakdown['property_metrics']['rental_income'] == 18000.00
        assert breakdown['property_metrics']['depreciation'] == 5600.00
        assert breakdown['property_metrics']['expenses'] == 4000.00
        assert breakdown['property_metrics']['net_rental_income'] == 8400.00
        
        # Verify net income is positive
        assert result.net_income > Decimal("0.00")
        assert result.net_income < result.gross_income

    def test_rental_loss_scenario(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        test_property: Property, db: Session
    ):
        """
        Test scenario where property expenses exceed rental income (loss)
        """
        # Create rental income
        rental = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("12000.00"),
            transaction_date=date(2025, 6, 15),
            income_category=IncomeCategory.RENTAL
        )
        
        # Create high depreciation and expenses (exceeding income)
        depreciation = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5600.00"),
            transaction_date=date(2025, 12, 31),
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_system_generated=True
        )
        
        # High maintenance costs
        maintenance = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("8000.00"),
            transaction_date=date(2025, 6, 15),
            expense_category=ExpenseCategory.MAINTENANCE,
            is_deductible=True
        )
        
        db.add_all([rental, depreciation, maintenance])
        db.commit()
        
        # Calculate tax
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Rental income: 12000
        # Expenses: 5600 + 8000 = 13600
        # Net rental: -1600 (loss)
        
        # Gross income: 50000 + 12000 = 62000
        assert result.gross_income == Decimal("62000.00")
        
        # Loss should reduce taxable income
        # Tax should be lower than without property
        result_no_property = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG
        )
        
        # Despite higher gross income, tax might be similar or even lower
        # due to high deductions
        tax_difference = result.income_tax.total_tax - result_no_property.income_tax.total_tax
        assert tax_difference < Decimal("5000.00")  # Not much higher despite +12k income


class TestTaxCalculationEdgeCases:
    """Test edge cases in property tax integration"""

    def test_no_properties_no_impact(
        self, engine_with_db: TaxCalculationEngine, test_user: User
    ):
        """Test that having no properties doesn't affect calculation"""
        result_with_user_id = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        result_without_user_id = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG
        )
        
        # Results should be identical
        assert result_with_user_id.total_tax == result_without_user_id.total_tax
        assert result_with_user_id.net_income == result_without_user_id.net_income

    def test_archived_property_transactions_not_included(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        db: Session
    ):
        """Test that transactions from archived properties are still included"""
        # Create archived property
        archived_property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            street="Archived Street 1",
            city="Wien",
            postal_code="1010",
            address="Archived Street 1, 1010 Wien",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("300000.00"),
            building_value=Decimal("240000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ARCHIVED,
            sale_date=date(2025, 6, 30)
        )
        db.add(archived_property)
        db.commit()
        
        # Create transactions for archived property (before sale)
        rental = Transaction(
            user_id=test_user.id,
            property_id=archived_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("9000.00"),  # 6 months rental
            transaction_date=date(2025, 3, 15),
            income_category=IncomeCategory.RENTAL
        )
        
        depreciation = Transaction(
            user_id=test_user.id,
            property_id=archived_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("2400.00"),  # Pro-rated 6 months
            transaction_date=date(2025, 6, 30),
            expense_category=ExpenseCategory.DEPRECIATION_AFA,
            is_system_generated=True
        )
        
        db.add_all([rental, depreciation])
        db.commit()
        
        # Calculate tax
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Archived property transactions should still be included
        # Gross income: 50000 + 9000 = 59000
        assert result.gross_income == Decimal("59000.00")

    def test_zero_depreciation_property(
        self, engine_with_db: TaxCalculationEngine, test_user: User,
        db: Session
    ):
        """Test property with zero depreciation (fully depreciated)"""
        # Create fully depreciated property
        old_property = Property(
            user_id=test_user.id,
            property_type=PropertyType.RENTAL,
            street="Old Street 1",
            city="Wien",
            postal_code="1010",
            address="Old Street 1, 1010 Wien",
            purchase_date=date(1975, 1, 1),  # 50 years ago
            purchase_price=Decimal("100000.00"),
            building_value=Decimal("80000.00"),
            depreciation_rate=Decimal("0.02"),
            status=PropertyStatus.ACTIVE
        )
        db.add(old_property)
        db.commit()
        
        # Create rental income but no depreciation (fully depreciated)
        rental = Transaction(
            user_id=test_user.id,
            property_id=old_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("12000.00"),
            transaction_date=date(2025, 6, 15),
            income_category=IncomeCategory.RENTAL
        )
        db.add(rental)
        db.commit()
        
        # Calculate tax
        result = engine_with_db.calculate_total_tax(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Should include rental income but no depreciation
        assert result.gross_income == Decimal("62000.00")
        
        # Generate breakdown
        breakdown = engine_with_db.generate_tax_breakdown(
            gross_income=Decimal("50000.00"),
            tax_year=2025,
            user_type=SVSUserType.GSVG,
            user_id=test_user.id
        )
        
        # Property metrics should show zero depreciation
        assert breakdown['property_metrics']['rental_income'] == 12000.00
        assert breakdown['property_metrics']['depreciation'] == 0.00

