"""
End-to-End Tests for Property Asset Management

Comprehensive E2E tests covering complete user workflows:
1. Register property → Calculate depreciation → View details
2. Import E1 with rental income → Link to property → Verify transactions
3. Import Bescheid → Auto-match property → Confirm link
4. Create property → Backfill historical depreciation → Verify all years
5. Multi-property portfolio → Calculate totals → Generate reports
6. Archive property → Verify transactions preserved

These tests validate the entire property management system from user actions
through API endpoints, services, and database persistence.
"""
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import Base
from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.services.property_service import PropertyService
from app.services.afa_calculator import AfACalculator
from app.services.historical_depreciation_service import HistoricalDepreciationService
from app.services.annual_depreciation_service import AnnualDepreciationService
from app.services.e1_form_import_service import E1FormImportService
from app.services.bescheid_import_service import BescheidImportService
from app.services.e1_form_extractor import E1FormData
from app.services.bescheid_extractor import BescheidData
from app.schemas.property import PropertyCreate, PropertyUpdate


# Test database setup
# Use PostgreSQL for E2E tests (required for ARRAY types and other PostgreSQL-specific features)
# Set TEST_DATABASE_URL environment variable to override
import os
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://taxja:taxja_password@localhost:5432/taxja_test"
)


@pytest.fixture
def db_session():
    """
    Create a test database session with clean state.
    
    Note: Requires PostgreSQL database. Start with:
        docker-compose up -d postgres
    
    Or set TEST_DATABASE_URL environment variable to point to your test database.
    """
    from sqlalchemy.dialects import postgresql
    
    engine = create_engine(TEST_DATABASE_URL)
    
    # Create enums first (required for PostgreSQL)
    with engine.connect() as conn:
        # Create property_type enum if it doesn't exist
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE propertytype AS ENUM ('rental', 'owner_occupied', 'mixed_use');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Create property_status enum if it doesn't exist
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE propertystatus AS ENUM ('active', 'sold', 'archived');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    # Cleanup
    session.close()
    
    # Drop all tables to ensure clean state for next test
    Base.metadata.drop_all(bind=engine)
    
    # Drop enums
    with engine.connect() as conn:
        conn.execute(text("DROP TYPE IF EXISTS propertytype CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS propertystatus CASCADE"))
        conn.commit()
    
    engine.dispose()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test landlord user"""
    user = User(
        email="landlord@example.com",
        name="Test Landlord",
        hashed_password="hashed_password_123",
        user_type=UserType.LANDLORD
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def property_service(db_session: Session) -> PropertyService:
    """Create PropertyService instance"""
    return PropertyService(db_session)


@pytest.fixture
def afa_calculator(db_session: Session) -> AfACalculator:
    """Create AfACalculator instance"""
    return AfACalculator(db_session)


@pytest.fixture
def historical_service(db_session: Session) -> HistoricalDepreciationService:
    """Create HistoricalDepreciationService instance"""
    return HistoricalDepreciationService(db_session)


@pytest.fixture
def annual_service(db_session: Session) -> AnnualDepreciationService:
    """Create AnnualDepreciationService instance"""
    return AnnualDepreciationService(db_session)


@pytest.fixture
def e1_service(db_session: Session) -> E1FormImportService:
    """Create E1FormImportService instance"""
    return E1FormImportService(db_session)


@pytest.fixture
def bescheid_service(db_session: Session) -> BescheidImportService:
    """Create BescheidImportService instance"""
    return BescheidImportService(db_session)



class TestE2E_RegisterPropertyCalculateDepreciationViewDetails:
    """
    E2E Test 1: Register property → Calculate depreciation → View details
    
    User story: Landlord registers a new property, system calculates depreciation,
    and user views property details with accumulated depreciation.
    """

    def test_complete_property_registration_workflow(
        self,
        property_service: PropertyService,
        afa_calculator: AfACalculator,
        test_user: User,
        db_session: Session
    ):
        """Test complete workflow from registration to viewing details"""
        # Step 1: User registers a new property
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Mariahilfer Straße 100",
            city="Wien",
            postal_code="1060",
            purchase_date=date(2024, 3, 15),
            purchase_price=Decimal("450000.00"),
            building_value=Decimal("360000.00"),
            construction_year=1995,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        # Verify property created with auto-calculations
        assert property.id is not None
        assert property.depreciation_rate == Decimal("0.02")  # 2% for post-1915
        assert property.status == PropertyStatus.ACTIVE
        assert property.address == "Mariahilfer Straße 100, 1060 Wien"
        
        # Step 2: Calculate annual depreciation for 2024
        annual_depreciation = afa_calculator.calculate_annual_depreciation(property, 2024)
        
        # Should be pro-rated for partial year (9.5 months: mid-March to Dec 31)
        # (360000 * 0.02 * 9.5) / 12 = 5700
        assert annual_depreciation == Decimal("5700.00")
        
        # Step 3: Calculate full year depreciation for 2025
        annual_depreciation_2025 = afa_calculator.calculate_annual_depreciation(property, 2025)
        
        # Full year: 360000 * 0.02 = 7200
        assert annual_depreciation_2025 == Decimal("7200.00")
        
        # Step 4: Get property details with metrics
        retrieved_property = property_service.get_property(property.id, test_user.id)
        
        assert retrieved_property.id == property.id
        assert retrieved_property.building_value == Decimal("360000.00")
        assert retrieved_property.depreciation_rate == Decimal("0.02")
        
        # Step 5: List all properties for user
        properties = property_service.list_properties(test_user.id, include_archived=False)
        
        assert len(properties) == 1
        assert properties[0].id == property.id
        assert properties[0].status == PropertyStatus.ACTIVE



class TestE2E_ImportE1LinkPropertyVerifyTransactions:
    """
    E2E Test 2: Import E1 with rental income → Link to property → Verify transactions
    
    User story: Landlord imports E1 form with rental income (KZ 350), links it to
    an existing property, and verifies the transaction is properly linked.
    """

    def test_e1_import_link_verify_workflow(
        self,
        e1_service: E1FormImportService,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """Test E1 import, property linking, and transaction verification"""
        # Step 1: Create existing property
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Neubaugasse 50",
            city="Wien",
            postal_code="1070",
            purchase_date=date(2023, 1, 1),
            purchase_price=Decimal("380000.00"),
            building_value=Decimal("304000.00"),
            construction_year=1988,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        # Step 2: Import E1 form with rental income
        e1_data = E1FormData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            steuernummer="12-345/6789",
            kz_350=Decimal("18000.00"),  # Rental income
            confidence=0.95,
        )
        
        import_result = e1_service.import_e1_data(e1_data, test_user.id)
        
        # Verify import created transaction
        assert import_result["transactions_created"] == 1
        assert import_result["requires_property_linking"] is True
        
        transaction_id = import_result["transactions"][0]["id"]
        
        # Step 3: Link transaction to property
        linked_transaction = e1_service.link_imported_rental_income(
            transaction_id=transaction_id,
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Verify linking
        assert linked_transaction.property_id == property.id
        assert linked_transaction.income_category == IncomeCategory.RENTAL
        assert linked_transaction.amount == Decimal("18000.00")
        
        # Step 4: Get property transactions
        property_transactions = property_service.get_property_transactions(
            property_id=property.id,
            user_id=test_user.id,
            year=2025
        )
        
        assert len(property_transactions) == 1
        assert property_transactions[0].id == transaction_id
        assert property_transactions[0].property_id == property.id
        
        # Step 5: Verify transaction persisted in database
        txn_from_db = db_session.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        assert txn_from_db is not None
        assert txn_from_db.property_id == property.id
        assert txn_from_db.user_id == test_user.id
        assert txn_from_db.type == TransactionType.INCOME



class TestE2E_ImportBescheidAutoMatchConfirmLink:
    """
    E2E Test 3: Import Bescheid → Auto-match property → Confirm link
    
    User story: Landlord imports Bescheid with property address, system auto-matches
    to existing property with high confidence, user confirms the link.
    """

    def test_bescheid_import_auto_match_workflow(
        self,
        bescheid_service: BescheidImportService,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """Test Bescheid import with automatic property matching"""
        # Step 1: Create existing property
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Landstraßer Hauptstraße 123",
            city="Wien",
            postal_code="1030",
            purchase_date=date(2022, 6, 1),
            purchase_price=Decimal("420000.00"),
            building_value=Decimal("336000.00"),
            construction_year=1992,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        # Step 2: Import Bescheid with matching address
        bescheid_data = BescheidData(
            tax_year=2025,
            taxpayer_name="Test Landlord",
            einkommen=Decimal("65000.00"),
            vermietung_details=[
                {
                    "address": "Landstraßer Hauptstraße 123, 1030 Wien",
                    "amount": Decimal("16500.00")
                }
            ]
        )
        
        import_result = bescheid_service.import_bescheid_data(bescheid_data, test_user.id)
        
        # Step 3: Verify auto-match suggestion
        assert import_result["requires_property_linking"] is True
        assert len(import_result["property_linking_suggestions"]) == 1
        
        suggestion = import_result["property_linking_suggestions"][0]
        assert suggestion["matched_property_id"] == str(property.id)
        assert suggestion["confidence_score"] >= 0.9  # High confidence
        assert suggestion["suggested_action"] == "auto_link"
        
        # Step 4: User confirms and links transaction
        transaction_id = import_result["transactions"][0]["id"]
        
        property_service.link_transaction_to_property(
            transaction_id=transaction_id,
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Step 5: Verify link confirmed
        txn = db_session.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        assert txn.property_id == property.id
        assert txn.amount == Decimal("16500.00")
        assert txn.income_category == IncomeCategory.RENTAL
        
        # Step 6: Verify property shows linked transaction
        property_txns = property_service.get_property_transactions(
            property_id=property.id,
            user_id=test_user.id
        )
        
        assert len(property_txns) == 1
        assert property_txns[0].id == transaction_id



class TestE2E_CreatePropertyBackfillHistoricalDepreciation:
    """
    E2E Test 4: Create property → Backfill historical depreciation → Verify all years
    
    User story: New user registers a property purchased in 2020, backfills historical
    depreciation for 2020-2025, and verifies all depreciation transactions created.
    """

    def test_property_creation_with_historical_backfill(
        self,
        property_service: PropertyService,
        historical_service: HistoricalDepreciationService,
        test_user: User,
        db_session: Session
    ):
        """Test creating property and backfilling historical depreciation"""
        # Step 1: User registers property purchased in 2020
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Währinger Straße 200",
            city="Wien",
            postal_code="1090",
            purchase_date=date(2020, 4, 1),  # April 2020
            purchase_price=Decimal("500000.00"),
            building_value=Decimal("400000.00"),
            construction_year=1980,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        assert property.depreciation_rate == Decimal("0.02")
        
        # Step 2: Preview historical depreciation
        preview = historical_service.calculate_historical_depreciation(property.id)
        
        # Should show 6 years: 2020 (partial), 2021, 2022, 2023, 2024, 2025
        assert len(preview) == 6
        
        # Verify 2020 is pro-rated (9 months: April to December)
        year_2020 = next(y for y in preview if y.year == 2020)
        # (400000 * 0.02 * 9) / 12 = 6000
        assert year_2020.amount == Decimal("6000.00")
        
        # Verify full years
        year_2021 = next(y for y in preview if y.year == 2021)
        assert year_2021.amount == Decimal("8000.00")  # 400000 * 0.02
        
        # Step 3: User confirms and backfills
        backfill_result = historical_service.backfill_depreciation(
            property_id=property.id,
            user_id=test_user.id
        )
        
        assert backfill_result.years_backfilled == 6
        assert backfill_result.total_amount == Decimal("46000.00")  # 6000 + 5*8000
        
        # Step 4: Verify all transactions created in database
        depreciation_txns = db_session.query(Transaction).filter(
            Transaction.property_id == property.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).order_by(Transaction.transaction_date).all()
        
        assert len(depreciation_txns) == 6
        
        # Verify each transaction
        for txn in depreciation_txns:
            assert txn.is_system_generated is True
            assert txn.type == TransactionType.EXPENSE
            assert txn.is_deductible is True
            assert txn.transaction_date.month == 12
            assert txn.transaction_date.day == 31
        
        # Step 5: Verify accumulated depreciation
        from app.services.afa_calculator import AfACalculator
        afa_calc = AfACalculator(db_session)
        
        accumulated = afa_calc.get_accumulated_depreciation(property.id)
        assert accumulated == Decimal("46000.00")
        
        # Step 6: Verify remaining depreciable value
        remaining = property.building_value - accumulated
        assert remaining == Decimal("354000.00")



class TestE2E_MultiPropertyPortfolioCalculateTotals:
    """
    E2E Test 5: Multi-property portfolio → Calculate totals → Generate reports
    
    User story: Landlord with multiple properties views portfolio metrics,
    calculates total rental income and expenses, and generates reports.
    """

    def test_multi_property_portfolio_workflow(
        self,
        property_service: PropertyService,
        annual_service: AnnualDepreciationService,
        test_user: User,
        db_session: Session
    ):
        """Test managing multiple properties with portfolio calculations and report generation"""
        # Step 1: Create three properties
        properties = []
        
        property_data_list = [
            {
                "street": "Gumpendorfer Straße 10",
                "city": "Wien",
                "postal_code": "1060",
                "purchase_date": date(2021, 1, 1),
                "purchase_price": Decimal("350000.00"),
                "building_value": Decimal("280000.00"),
                "construction_year": 1985,
            },
            {
                "street": "Josefstädter Straße 25",
                "city": "Wien",
                "postal_code": "1080",
                "purchase_date": date(2022, 1, 1),
                "purchase_price": Decimal("420000.00"),
                "building_value": Decimal("336000.00"),
                "construction_year": 1990,
            },
            {
                "street": "Alser Straße 40",
                "city": "Wien",
                "postal_code": "1090",
                "purchase_date": date(2023, 1, 1),
                "purchase_price": Decimal("480000.00"),
                "building_value": Decimal("384000.00"),
                "construction_year": 2000,
            },
        ]
        
        for data in property_data_list:
            property_create = PropertyCreate(
                property_type=PropertyType.RENTAL,
                **data
            )
            prop = property_service.create_property(
                user_id=test_user.id,
                property_data=property_create
            )
            properties.append(prop)
        
        # Step 2: Add rental income transactions for each property
        for i, prop in enumerate(properties):
            rental_income = Transaction(
                user_id=test_user.id,
                property_id=prop.id,
                type=TransactionType.INCOME,
                amount=Decimal(f"{12000 + i * 2000}.00"),  # 12000, 14000, 16000
                transaction_date=date(2025, 12, 31),
                description=f"Rental income {prop.address}",
                income_category=IncomeCategory.RENTAL,
                is_deductible=False,
            )
            db_session.add(rental_income)
        
        # Step 3: Add property expenses for each property
        expense_categories = [
            ExpenseCategory.PROPERTY_INSURANCE,
            ExpenseCategory.MAINTENANCE_REPAIRS,
            ExpenseCategory.PROPERTY_TAX,
        ]
        
        for i, prop in enumerate(properties):
            expense = Transaction(
                user_id=test_user.id,
                property_id=prop.id,
                type=TransactionType.EXPENSE,
                amount=Decimal(f"{1000 + i * 500}.00"),  # 1000, 1500, 2000
                transaction_date=date(2025, 6, 15),
                description=f"Property expense {prop.address}",
                expense_category=expense_categories[i],
                is_deductible=True,
            )
            db_session.add(expense)
        
        db_session.commit()
        
        # Step 4: Generate annual depreciation for all properties
        depreciation_result = annual_service.generate_annual_depreciation(
            year=2025,
            user_id=test_user.id
        )
        
        assert depreciation_result.properties_processed == 3
        assert depreciation_result.transactions_created == 3
        
        # Expected depreciation: 5600 + 6720 + 7680 = 20000
        assert depreciation_result.total_amount == Decimal("20000.00")
        
        # Step 5: Calculate portfolio totals
        all_properties = property_service.list_properties(test_user.id)
        
        total_building_value = sum(p.building_value for p in all_properties)
        assert total_building_value == Decimal("1000000.00")  # 280k + 336k + 384k
        
        # Step 6: Calculate total rental income
        total_rental_income_amount = db_session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == test_user.id,
            Transaction.income_category == IncomeCategory.RENTAL,
            Transaction.type == TransactionType.INCOME
        ).scalar()
        
        assert total_rental_income_amount == Decimal("42000.00")  # 12000 + 14000 + 16000
        
        # Step 7: Calculate total expenses (depreciation + other expenses)
        total_expenses_amount = db_session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == test_user.id,
            Transaction.type == TransactionType.EXPENSE
        ).scalar()
        
        # 20000 (depreciation) + 4500 (other expenses) = 24500
        assert total_expenses_amount == Decimal("24500.00")
        
        # Step 8: Verify each property has correct transactions
        for prop in properties:
            prop_txns = property_service.get_property_transactions(
                property_id=prop.id,
                user_id=test_user.id,
                year=2025
            )
            # Should have 1 rental income + 1 depreciation + 1 expense = 3
            assert len(prop_txns) == 3
        
        # Step 9: Generate income statement report for each property
        from app.services.property_report_service import PropertyReportService
        report_service = PropertyReportService(db_session)
        
        income_statements = []
        for prop in properties:
            income_statement = report_service.generate_income_statement(
                property_id=str(prop.id),
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31)
            )
            income_statements.append(income_statement)
            
            # Verify report structure
            assert "property" in income_statement
            assert "period" in income_statement
            assert "income" in income_statement
            assert "expenses" in income_statement
            assert "net_income" in income_statement
            
            # Verify property details
            assert income_statement["property"]["id"] == str(prop.id)
            assert income_statement["property"]["address"] == prop.address
            
            # Verify income is positive
            assert income_statement["income"]["rental_income"] > 0
            
            # Verify expenses include depreciation
            assert income_statement["expenses"]["total_expenses"] > 0
            
            # Verify net income calculation
            net_income = (
                income_statement["income"]["rental_income"] - 
                income_statement["expenses"]["total_expenses"]
            )
            assert abs(income_statement["net_income"] - net_income) < 0.01
        
        # Step 10: Generate depreciation schedule for each property
        depreciation_schedules = []
        for prop in properties:
            schedule = report_service.generate_depreciation_schedule(
                property_id=str(prop.id)
            )
            depreciation_schedules.append(schedule)
            
            # Verify schedule structure
            assert "property" in schedule
            assert "schedule" in schedule
            assert "summary" in schedule
            
            # Verify property details
            assert schedule["property"]["id"] == str(prop.id)
            assert schedule["property"]["depreciation_rate"] == float(prop.depreciation_rate)
            
            # Verify schedule has entries for all years
            purchase_year = prop.purchase_date.year
            current_year = 2025
            expected_years = current_year - purchase_year + 1
            assert len(schedule["schedule"]) == expected_years
            
            # Verify accumulated depreciation increases each year
            for i in range(1, len(schedule["schedule"])):
                assert (
                    schedule["schedule"][i]["accumulated_depreciation"] >= 
                    schedule["schedule"][i-1]["accumulated_depreciation"]
                )
            
            # Verify remaining value decreases
            for i in range(1, len(schedule["schedule"])):
                assert (
                    schedule["schedule"][i]["remaining_value"] <= 
                    schedule["schedule"][i-1]["remaining_value"]
                )
        
        # Step 11: Verify portfolio-level aggregations
        total_rental_income_from_reports = sum(
            stmt["income"]["rental_income"] for stmt in income_statements
        )
        assert abs(total_rental_income_from_reports - 42000.00) < 0.01
        
        total_expenses_from_reports = sum(
            stmt["expenses"]["total_expenses"] for stmt in income_statements
        )
        assert abs(total_expenses_from_reports - 24500.00) < 0.01
        
        total_net_income = sum(
            stmt["net_income"] for stmt in income_statements
        )
        assert abs(total_net_income - 17500.00) < 0.01  # 42000 - 24500
        
        # Step 12: Verify total accumulated depreciation across portfolio
        total_accumulated_depreciation = sum(
            schedule["summary"]["total_depreciation"] for schedule in depreciation_schedules
        )
        
        # Property 1: 5 years (2021-2025) = 5 * 5600 = 28000
        # Property 2: 4 years (2022-2025) = 4 * 6720 = 26880
        # Property 3: 3 years (2023-2025) = 3 * 7680 = 23040
        # Total = 77920
        assert abs(total_accumulated_depreciation - 77920.00) < 0.01
        
        # Step 13: Verify portfolio metrics calculation
        portfolio_metrics = {
            "total_properties": len(properties),
            "total_building_value": float(total_building_value),
            "total_rental_income": float(total_rental_income_amount),
            "total_expenses": float(total_expenses_amount),
            "total_net_income": float(total_rental_income_amount - total_expenses_amount),
            "total_accumulated_depreciation": total_accumulated_depreciation,
            "average_net_income_per_property": float(
                (total_rental_income_amount - total_expenses_amount) / len(properties)
            ),
        }
        
        assert portfolio_metrics["total_properties"] == 3
        assert portfolio_metrics["total_building_value"] == 1000000.00
        assert portfolio_metrics["total_rental_income"] == 42000.00
        assert portfolio_metrics["total_expenses"] == 24500.00
        assert portfolio_metrics["total_net_income"] == 17500.00
        assert abs(portfolio_metrics["average_net_income_per_property"] - 5833.33) < 0.01



class TestE2E_ArchivePropertyVerifyTransactionsPreserved:
    """
    E2E Test 6: Archive property → Verify transactions preserved
    
    User story: Landlord sells a property and archives it. System preserves all
    historical transactions and depreciation records for tax purposes.
    """

    def test_archive_property_preserves_transactions(
        self,
        property_service: PropertyService,
        historical_service: HistoricalDepreciationService,
        test_user: User,
        db_session: Session
    ):
        """Test archiving property preserves all transaction history"""
        # Step 1: Create property with historical data
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Praterstraße 75",
            city="Wien",
            postal_code="1020",
            purchase_date=date(2022, 1, 1),
            purchase_price=Decimal("390000.00"),
            building_value=Decimal("312000.00"),
            construction_year=1995,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        # Step 2: Backfill historical depreciation (2022-2025)
        backfill_result = historical_service.backfill_depreciation(
            property_id=property.id,
            user_id=test_user.id
        )
        
        assert backfill_result.years_backfilled == 4  # 2022, 2023, 2024, 2025
        
        # Step 3: Add rental income transactions
        for year in [2022, 2023, 2024, 2025]:
            rental_txn = Transaction(
                user_id=test_user.id,
                property_id=property.id,
                type=TransactionType.INCOME,
                amount=Decimal("15000.00"),
                transaction_date=date(year, 12, 31),
                description=f"Rental income {year}",
                income_category=IncomeCategory.RENTAL,
            )
            db_session.add(rental_txn)
        
        # Step 4: Add property expenses
        expense_txn = Transaction(
            user_id=test_user.id,
            property_id=property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("2500.00"),
            transaction_date=date(2025, 6, 15),
            description="Roof repair",
            expense_category=ExpenseCategory.MAINTENANCE_REPAIRS,
            is_deductible=True,
        )
        db_session.add(expense_txn)
        db_session.commit()
        
        # Step 5: Count transactions before archival
        txns_before = db_session.query(Transaction).filter(
            Transaction.property_id == property.id
        ).count()
        
        # Should have: 4 depreciation + 4 rental income + 1 expense = 9
        assert txns_before == 9
        
        # Step 6: Archive property (sold on Dec 31, 2025)
        archived_property = property_service.archive_property(
            property_id=property.id,
            user_id=test_user.id,
            sale_date=date(2025, 12, 31)
        )
        
        assert archived_property.status == PropertyStatus.ARCHIVED
        assert archived_property.sale_date == date(2025, 12, 31)
        
        # Step 7: Verify all transactions still exist
        txns_after = db_session.query(Transaction).filter(
            Transaction.property_id == property.id
        ).count()
        
        assert txns_after == 9  # All transactions preserved
        
        # Step 8: Verify property not in active list
        active_properties = property_service.list_properties(
            test_user.id,
            include_archived=False
        )
        assert len(active_properties) == 0
        
        # Step 9: Verify property in archived list
        all_properties = property_service.list_properties(
            test_user.id,
            include_archived=True
        )
        assert len(all_properties) == 1
        assert all_properties[0].status == PropertyStatus.ARCHIVED
        
        # Step 10: Verify can still retrieve property details
        retrieved = property_service.get_property(property.id, test_user.id)
        assert retrieved.id == property.id
        assert retrieved.status == PropertyStatus.ARCHIVED
        
        # Step 11: Verify can still get property transactions
        archived_txns = property_service.get_property_transactions(
            property_id=property.id,
            user_id=test_user.id
        )
        assert len(archived_txns) == 9



class TestE2E_CompletePropertyLifecycle:
    """
    E2E Test 7: Complete property lifecycle from creation to archival
    
    Comprehensive test covering: registration → import linking → expense tracking →
    depreciation → reporting → archival
    """

    def test_complete_property_lifecycle(
        self,
        property_service: PropertyService,
        e1_service: E1FormImportService,
        historical_service: HistoricalDepreciationService,
        annual_service: AnnualDepreciationService,
        test_user: User,
        db_session: Session
    ):
        """Test complete property lifecycle from creation to sale"""
        # Step 1: Register property
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            street="Favoritenstraße 150",
            city="Wien",
            postal_code="1100",
            purchase_date=date(2023, 3, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            construction_year=1998,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        assert property.status == PropertyStatus.ACTIVE
        
        # Step 2: Backfill historical depreciation (2023-2025)
        backfill_result = historical_service.backfill_depreciation(
            property_id=property.id,
            user_id=test_user.id
        )
        
        assert backfill_result.years_backfilled == 3
        
        # Step 3: Import E1 with rental income
        e1_data = E1FormData(
            tax_year=2025,
            kz_350=Decimal("17500.00"),
            confidence=0.95,
        )
        
        import_result = e1_service.import_e1_data(e1_data, test_user.id)
        transaction_id = import_result["transactions"][0]["id"]
        
        # Step 4: Link rental income to property
        e1_service.link_imported_rental_income(
            transaction_id=transaction_id,
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Step 5: Add property expenses
        expenses = [
            {
                "amount": Decimal("1200.00"),
                "description": "Property insurance",
                "category": ExpenseCategory.PROPERTY_INSURANCE,
            },
            {
                "amount": Decimal("800.00"),
                "description": "Property tax",
                "category": ExpenseCategory.PROPERTY_TAX,
            },
            {
                "amount": Decimal("3500.00"),
                "description": "Heating system repair",
                "category": ExpenseCategory.MAINTENANCE_REPAIRS,
            },
        ]
        
        for expense in expenses:
            txn = Transaction(
                user_id=test_user.id,
                property_id=property.id,
                type=TransactionType.EXPENSE,
                amount=expense["amount"],
                transaction_date=date(2025, 6, 15),
                description=expense["description"],
                expense_category=expense["category"],
                is_deductible=True,
            )
            db_session.add(txn)
        
        db_session.commit()
        
        # Step 6: Calculate property metrics
        metrics = property_service.calculate_property_metrics(property.id)
        
        # Rental income: 17500
        assert metrics["rental_income"] == Decimal("17500.00")
        
        # Expenses: 1200 + 800 + 3500 + depreciation (5866.67 for 2025)
        # Total expenses should include depreciation
        assert metrics["total_expenses"] > Decimal("5500.00")
        
        # Net income should be positive
        assert metrics["net_income"] > Decimal("0.00")
        
        # Step 7: Verify all transactions linked to property
        all_txns = property_service.get_property_transactions(
            property_id=property.id,
            user_id=test_user.id
        )
        
        # Should have: 3 depreciation + 1 rental income + 3 expenses = 7
        assert len(all_txns) >= 7
        
        # Step 8: Update property details
        update_data = PropertyUpdate(
            status=PropertyStatus.ACTIVE,
        )
        
        updated_property = property_service.update_property(
            property_id=property.id,
            user_id=test_user.id,
            updates=update_data
        )
        
        assert updated_property.id == property.id
        
        # Step 9: Archive property (sold)
        archived = property_service.archive_property(
            property_id=property.id,
            user_id=test_user.id,
            sale_date=date(2026, 1, 15)
        )
        
        assert archived.status == PropertyStatus.ARCHIVED
        assert archived.sale_date == date(2026, 1, 15)
        
        # Step 10: Verify all data preserved after archival
        final_txns = db_session.query(Transaction).filter(
            Transaction.property_id == property.id
        ).count()
        
        assert final_txns >= 7  # All transactions preserved
        
        # Step 11: Verify property still retrievable
        final_property = property_service.get_property(property.id, test_user.id)
        assert final_property.status == PropertyStatus.ARCHIVED
        assert final_property.sale_date == date(2026, 1, 15)


class TestE2E_MixedUsePropertyWorkflow:
    """
    E2E Test 8: Mixed-use property workflow
    
    Test property with both rental and personal use portions.
    """

    def test_mixed_use_property_depreciation(
        self,
        property_service: PropertyService,
        test_user: User,
        db_session: Session
    ):
        """Test mixed-use property with partial rental depreciation"""
        # Step 1: Create mixed-use property (60% rental, 40% personal)
        property_data = PropertyCreate(
            property_type=PropertyType.MIXED_USE,
            rental_percentage=Decimal("60.00"),
            street="Schönbrunner Straße 88",
            city="Wien",
            postal_code="1050",
            purchase_date=date(2024, 1, 1),
            purchase_price=Decimal("500000.00"),
            building_value=Decimal("400000.00"),
            construction_year=2005,
        )
        
        property = property_service.create_property(
            user_id=test_user.id,
            property_data=property_data
        )
        
        assert property.property_type == PropertyType.MIXED_USE
        assert property.rental_percentage == Decimal("60.00")
        
        # Step 2: Calculate depreciation (should be 60% of full amount)
        from app.services.afa_calculator import AfACalculator
        afa_calc = AfACalculator(db_session)
        
        annual_dep = afa_calc.calculate_annual_depreciation(property, 2024)
        
        # Full depreciation: 400000 * 0.02 = 8000
        # Mixed-use (60%): 8000 * 0.60 = 4800
        assert annual_dep == Decimal("4800.00")
        
        # Step 3: Verify only rental portion is depreciable
        depreciable_value = property.building_value * (property.rental_percentage / 100)
        assert depreciable_value == Decimal("240000.00")  # 400000 * 0.60


# Summary comment for test coverage
"""
E2E Test Coverage Summary:

✓ Test 1: Basic property registration and depreciation calculation
✓ Test 2: E1 import integration with property linking
✓ Test 3: Bescheid import with automatic address matching
✓ Test 4: Historical depreciation backfill for existing properties
✓ Test 5: Multi-property portfolio management and calculations
✓ Test 6: Property archival with transaction preservation
✓ Test 7: Complete property lifecycle from creation to sale
✓ Test 8: Mixed-use property with partial depreciation

All tests validate:
- Database persistence
- Service layer integration
- Business logic correctness
- Austrian tax law compliance
- Transaction referential integrity
- User ownership validation
"""
