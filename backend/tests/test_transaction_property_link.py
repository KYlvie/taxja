"""Unit tests for Transaction-Property linking functionality"""
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.models.user import User, UserType
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="landlord@test.com",
        password_hash="hashed_password",
        name="Test Landlord",
        user_type=UserType.LANDLORD,
        language="de"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_property(db_session, test_user):
    """Create a test property"""
    property = Property(
        user_id=test_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Hauptstraße 123, 1010 Wien",
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 6, 15),
        purchase_price=Decimal("350000.00"),
        building_value=Decimal("280000.00"),
        land_value=Decimal("70000.00"),
        construction_year=1985,
        depreciation_rate=Decimal("0.02"),
        status=PropertyStatus.ACTIVE
    )
    db_session.add(property)
    db_session.commit()
    return property


class TestTransactionPropertyLink:
    """Test Transaction-Property linking functionality"""
    
    def test_transaction_without_property(self, db_session, test_user):
        """Test creating a transaction without property link"""
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("150.00"),
            transaction_date=date(2026, 3, 1),
            description="Office supplies",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
            is_system_generated=False
        )
        db_session.add(transaction)
        db_session.commit()
        
        assert transaction.id is not None
        assert transaction.property_id is None
        assert transaction.is_system_generated is False
    
    def test_transaction_with_property_link(self, db_session, test_user, test_property):
        """Test creating a transaction linked to a property"""
        transaction = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1200.00"),
            transaction_date=date(2026, 3, 1),
            description="Rental income - March 2026",
            income_category=IncomeCategory.RENTAL,
            is_deductible=False,
            is_system_generated=False
        )
        db_session.add(transaction)
        db_session.commit()
        
        assert transaction.id is not None
        assert transaction.property_id == test_property.id
        assert transaction.property.address == "Hauptstraße 123, 1010 Wien"
    
    def test_system_generated_depreciation_transaction(self, db_session, test_user, test_property):
        """Test creating a system-generated depreciation transaction"""
        transaction = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5600.00"),
            transaction_date=date(2025, 12, 31),
            description=f"AfA {test_property.address} (2025)",
            expense_category=ExpenseCategory.DEPRECIATION,
            is_deductible=True,
            is_system_generated=True
        )
        db_session.add(transaction)
        db_session.commit()
        
        assert transaction.id is not None
        assert transaction.property_id == test_property.id
        assert transaction.is_system_generated is True
        assert transaction.expense_category == ExpenseCategory.DEPRECIATION
    
    def test_query_transactions_by_property(self, db_session, test_user, test_property):
        """Test querying all transactions for a property"""
        # Create multiple transactions for the property
        transactions = [
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.INCOME,
                amount=Decimal("1200.00"),
                transaction_date=date(2026, 1, 1),
                description="Rental income - January",
                income_category=IncomeCategory.RENTAL
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("150.00"),
                transaction_date=date(2026, 1, 15),
                description="Property maintenance",
                expense_category=ExpenseCategory.MAINTENANCE,
                is_deductible=True
            ),
            Transaction(
                user_id=test_user.id,
                property_id=test_property.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("5600.00"),
                transaction_date=date(2025, 12, 31),
                description="AfA 2025",
                expense_category=ExpenseCategory.DEPRECIATION,
                is_deductible=True,
                is_system_generated=True
            )
        ]
        
        for t in transactions:
            db_session.add(t)
        db_session.commit()
        
        # Query transactions by property
        property_transactions = db_session.query(Transaction).filter(
            Transaction.property_id == test_property.id
        ).all()
        
        assert len(property_transactions) == 3
        assert all(t.property_id == test_property.id for t in property_transactions)
    
    def test_filter_system_generated_transactions(self, db_session, test_user, test_property):
        """Test filtering system-generated vs manual transactions"""
        # Create manual transaction
        manual = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("200.00"),
            transaction_date=date(2026, 3, 1),
            description="Manual expense",
            expense_category=ExpenseCategory.MAINTENANCE,
            is_system_generated=False
        )
        
        # Create system-generated transaction
        system = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("5600.00"),
            transaction_date=date(2025, 12, 31),
            description="AfA 2025",
            expense_category=ExpenseCategory.DEPRECIATION,
            is_system_generated=True
        )
        
        db_session.add_all([manual, system])
        db_session.commit()
        
        # Query only manual transactions
        manual_transactions = db_session.query(Transaction).filter(
            Transaction.property_id == test_property.id,
            Transaction.is_system_generated == False
        ).all()
        
        assert len(manual_transactions) == 1
        assert manual_transactions[0].description == "Manual expense"
        
        # Query only system-generated transactions
        system_transactions = db_session.query(Transaction).filter(
            Transaction.property_id == test_property.id,
            Transaction.is_system_generated == True
        ).all()
        
        assert len(system_transactions) == 1
        assert system_transactions[0].description == "AfA 2025"
    
    def test_property_relationship_from_transaction(self, db_session, test_user, test_property):
        """Test accessing property from transaction via relationship"""
        transaction = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1200.00"),
            transaction_date=date(2026, 3, 1),
            description="Rental income",
            income_category=IncomeCategory.RENTAL
        )
        db_session.add(transaction)
        db_session.commit()
        
        # Access property via relationship
        assert transaction.property is not None
        assert transaction.property.id == test_property.id
        assert transaction.property.address == "Hauptstraße 123, 1010 Wien"
        assert transaction.property.user_id == test_user.id
    
    def test_transactions_relationship_from_property(self, db_session, test_user, test_property):
        """Test accessing transactions from property via relationship"""
        # Create transactions
        t1 = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.INCOME,
            amount=Decimal("1200.00"),
            transaction_date=date(2026, 3, 1),
            income_category=IncomeCategory.RENTAL
        )
        t2 = Transaction(
            user_id=test_user.id,
            property_id=test_property.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("150.00"),
            transaction_date=date(2026, 3, 5),
            expense_category=ExpenseCategory.MAINTENANCE
        )
        db_session.add_all([t1, t2])
        db_session.commit()
        
        # Access transactions via property relationship
        assert len(test_property.transactions) == 2
        assert all(t.property_id == test_property.id for t in test_property.transactions)
    
    def test_nullable_property_id(self, db_session, test_user):
        """Test that property_id can be null for non-property transactions"""
        transaction = Transaction(
            user_id=test_user.id,
            property_id=None,  # Explicitly set to None
            type=TransactionType.EXPENSE,
            amount=Decimal("50.00"),
            transaction_date=date(2026, 3, 1),
            description="General business expense",
            expense_category=ExpenseCategory.OFFICE_SUPPLIES
        )
        db_session.add(transaction)
        db_session.commit()
        
        assert transaction.property_id is None
        assert transaction.property is None
    
    def test_default_is_system_generated_false(self, db_session, test_user):
        """Test that is_system_generated defaults to False"""
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("100.00"),
            transaction_date=date(2026, 3, 1),
            expense_category=ExpenseCategory.OFFICE_SUPPLIES
            # is_system_generated not specified
        )
        db_session.add(transaction)
        db_session.commit()
        
        assert transaction.is_system_generated is False
