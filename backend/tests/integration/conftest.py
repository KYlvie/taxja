"""Pytest fixtures for integration tests"""
import pytest
import pyotp
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from app.main import app
from app.db.base import Base, get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.models.tax_configuration import TaxConfiguration, get_2026_tax_config
from decimal import Decimal
from datetime import datetime

# Use a stable in-memory database so full-suite and targeted runs behave the same.
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


def _create_sqlite_tables(engine, metadata):
    """Create SQLite tables while stripping PG-only server defaults."""
    excluded_tables = {
        "historical_import_sessions",
        "historical_import_uploads",
        "import_conflicts",
        "import_metrics",
    }

    tables_to_create = [
        table for table in metadata.sorted_tables
        if table.name not in excluded_tables
    ]
    patched = []
    for table in tables_to_create:
        for col in table.columns:
            if col.server_default is not None:
                default_text = (
                    str(col.server_default.arg)
                    if hasattr(col.server_default, "arg")
                    else str(col.server_default)
                )
                if "gen_random_uuid" in default_text:
                    patched.append((col, col.server_default))
                    col.server_default = None
    try:
        metadata.create_all(bind=engine, tables=tables_to_create, checkfirst=True)
    finally:
        for col, server_default in patched:
            col.server_default = server_default


@pytest.fixture(scope="function")
def db():
    """Create test database for each test"""
    Base.metadata.drop_all(bind=engine)
    _create_sqlite_tables(engine, Base.metadata)
    db = TestingSessionLocal()
    
    # Seed tax configuration for 2026
    tax_config = TaxConfiguration(**get_2026_tax_config())
    db.add(tax_config)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    """Create a test user without 2FA"""
    user = User(
        email="testuser@example.com",
        name="Test User",
        password_hash=get_password_hash("TestPassword123!"),
        user_type="employee",
        two_factor_enabled=False,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.name,
        "user_type": user.user_type,
        "password": "TestPassword123!"  # Plain password for testing
    }


@pytest.fixture
def test_user_with_2fa(db):
    """Create a test user with 2FA enabled"""
    secret = pyotp.random_base32()
    backup_codes = [f"backup{i:02d}" for i in range(10)]
    
    user = User(
        email="user2fa@example.com",
        name="2FA User",
        password_hash=get_password_hash("TestPassword123!"),
        user_type="employee",
        two_factor_enabled=True,
        two_factor_secret=secret,
        backup_codes=backup_codes,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.name,
        "user_type": user.user_type,
        "password": "TestPassword123!",
        "two_factor_secret": secret,
        "backup_codes": backup_codes
    }


@pytest.fixture
def authenticated_client(client, test_user):
    """Create an authenticated test client"""
    # Login to get access token
    login_data = {
        "email": test_user["email"],
        "password": test_user["password"]
    }
    
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    
    access_token = response.json()["access_token"]
    
    # Add authorization header to client
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {access_token}"
    }
    
    return client


@pytest.fixture
def authenticated_client_with_2fa(client, test_user_with_2fa):
    """Create an authenticated test client for user with 2FA"""
    # Current auth flow does not require a separate temp-token 2FA step.
    login_data = {
        "email": test_user_with_2fa["email"],
        "password": test_user_with_2fa["password"]
    }
    
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    
    access_token = response.json()["access_token"]
    
    # Add authorization header
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {access_token}"
    }
    
    return client


@pytest.fixture
def password_reset_token(db, test_user):
    """Generate a password reset token for test user"""
    from app.core.security import create_password_reset_token
    
    token = create_password_reset_token(test_user["email"])
    return token


@pytest.fixture
def multiple_test_users(db):
    """Create multiple test users with different types"""
    users = []
    
    user_data = [
        ("employee1@example.com", "Employee One", "employee"),
        ("selfemployed1@example.com", "Self Employed One", "self_employed"),
        ("landlord1@example.com", "Landlord One", "landlord"),
        ("business1@example.com", "Business One", "small_business")
    ]
    
    for email, name, user_type in user_data:
        user = User(
            email=email,
            name=name,
            password_hash=get_password_hash("TestPassword123!"),
            user_type=user_type,
            two_factor_enabled=False,
            email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        users.append({
            "id": user.id,
            "email": user.email,
            "full_name": user.name,
            "user_type": user.user_type,
            "password": "TestPassword123!"
        })
    
    return users



# OCR Test Fixtures

@pytest.fixture
def sample_receipt_image():
    """Create a sample receipt image for testing"""
    from PIL import Image, ImageDraw, ImageFont
    
    # Create image with receipt-like content
    image = Image.new('RGB', (800, 1000), color='white')
    draw = ImageDraw.Draw(image)
    
    # Add text (simulating receipt)
    text_lines = [
        "BILLA",
        "Supermarkt",
        "",
        "Datum: 15.01.2026",
        "Zeit: 14:30",
        "",
        "Artikel:",
        "Brot                 2.50",
        "Milch                1.20",
        "Käse                 4.80",
        "",
        "Summe:              8.50 EUR",
        "20% USt:            1.42 EUR",
        "",
        "Vielen Dank!"
    ]
    
    y = 50
    for line in text_lines:
        draw.text((50, y), line, fill='black')
        y += 40
    
    # Convert to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    
    return img_byte_arr


@pytest.fixture
def document_with_ocr(db, authenticated_client, sample_receipt_image):
    """Create a document with completed OCR processing"""
    from app.models.document import Document
    from app.models.user import User
    
    # Get user from authenticated client
    user = db.query(User).filter(User.email == "testuser@example.com").first()
    
    # Create document
    document = Document(
        user_id=user.id,
        file_path="/test/receipt.jpg",
        document_type="receipt",
        ocr_status="completed",
        ocr_result={
            "raw_text": "BILLA Supermarkt\nDatum: 15.01.2026\nSumme: 8.50 EUR",
            "extracted_data": {
                "date": "2026-01-15",
                "amount": 8.50,
                "merchant": "BILLA",
                "vat_amount": 1.42
            },
            "confidence_score": 0.85,
            "needs_review": False
        }
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return {
        "id": document.id,
        "document_type": document.document_type,
        "ocr_result": document.ocr_result
    }


@pytest.fixture
def low_confidence_document(db, authenticated_client):
    """Create a document with low confidence OCR results"""
    from app.models.document import Document
    from app.models.user import User
    
    user = db.query(User).filter(User.email == "testuser@example.com").first()
    
    document = Document(
        user_id=user.id,
        file_path="/test/poor_quality.jpg",
        document_type="receipt",
        ocr_status="completed",
        ocr_result={
            "raw_text": "unclear text...",
            "extracted_data": {
                "date": None,
                "amount": None
            },
            "confidence_score": 0.35,
            "needs_review": True
        }
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return {
        "id": document.id,
        "ocr_result": document.ocr_result
    }


@pytest.fixture
def high_confidence_document(db, authenticated_client):
    """Create a document with high confidence OCR results"""
    from app.models.document import Document
    from app.models.user import User
    
    user = db.query(User).filter(User.email == "testuser@example.com").first()
    
    document = Document(
        user_id=user.id,
        file_path="/test/clear_receipt.jpg",
        document_type="receipt",
        ocr_status="completed",
        ocr_result={
            "raw_text": "SPAR Supermarkt\nDatum: 20.01.2026\nSumme: 45.80 EUR",
            "extracted_data": {
                "date": "2026-01-20",
                "amount": 45.80,
                "merchant": "SPAR"
            },
            "confidence_score": 0.92,
            "needs_review": False
        }
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return {
        "id": document.id,
        "ocr_result": document.ocr_result
    }


@pytest.fixture
def receipt_ocr_data(db, authenticated_client):
    """Create receipt with OCR data ready for transaction creation"""
    from app.models.document import Document
    from app.models.user import User
    
    user = db.query(User).filter(User.email == "testuser@example.com").first()
    
    document = Document(
        user_id=user.id,
        file_path="/test/receipt_for_transaction.jpg",
        document_type="receipt",
        ocr_status="completed",
        ocr_result={
            "raw_text": "HOFER\nDatum: 25.01.2026\nSumme: 32.50 EUR",
            "extracted_data": {
                "date": "2026-01-25",
                "amount": 32.50,
                "merchant": "HOFER",
                "category": "groceries"
            },
            "confidence_score": 0.88,
            "needs_review": False
        }
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return {
        "document_id": document.id,
        "extracted_data": document.ocr_result["extracted_data"]
    }


@pytest.fixture
def invoice_ocr_data(db, authenticated_client):
    """Create invoice with OCR data including VAT"""
    from app.models.document import Document
    from app.models.user import User
    
    user = db.query(User).filter(User.email == "testuser@example.com").first()
    
    document = Document(
        user_id=user.id,
        file_path="/test/invoice.jpg",
        document_type="invoice",
        ocr_status="completed",
        ocr_result={
            "raw_text": "Rechnung Nr. 12345\nDatum: 10.01.2026\nBetrag: 120.00 EUR\n20% USt: 20.00 EUR",
            "extracted_data": {
                "date": "2026-01-10",
                "amount": 120.00,
                "merchant": "Office Supplies GmbH",
                "vat_rate": 0.20,
                "vat_amount": 20.00,
                "category": "office_supplies"
            },
            "confidence_score": 0.90,
            "needs_review": False
        }
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return {
        "document_id": document.id,
        "extracted_data": document.ocr_result["extracted_data"]
    }


@pytest.fixture
def payslip_ocr_data(db, authenticated_client):
    """Create payslip with OCR data"""
    from app.models.document import Document
    from app.models.user import User
    
    user = db.query(User).filter(User.email == "testuser@example.com").first()
    
    document = Document(
        user_id=user.id,
        file_path="/test/payslip.jpg",
        document_type="payslip",
        ocr_status="completed",
        ocr_result={
            "raw_text": "Lohnzettel\nBrutto: 3500.00 EUR\nNetto: 2450.00 EUR",
            "extracted_data": {
                "date": "2026-01-31",
                "amount": 3500.00,
                "gross_income": 3500.00,
                "net_income": 2450.00,
                "employer": "Test Company GmbH",
                "category": "employment_income"
            },
            "confidence_score": 0.87,
            "needs_review": False
        }
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return {
        "document_id": document.id,
        "extracted_data": document.ocr_result["extracted_data"]
    }


@pytest.fixture
def transaction_with_document(db, authenticated_client):
    """Create a transaction with associated document"""
    from app.models.transaction import Transaction
    from app.models.document import Document
    from app.models.user import User
    
    user = db.query(User).filter(User.email == "testuser@example.com").first()
    
    # Create document
    document = Document(
        user_id=user.id,
        file_path="/test/receipt_with_transaction.jpg",
        document_type="receipt",
        ocr_status="completed"
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Create transaction
    transaction = Transaction(
        user_id=user.id,
        type="expense",
        amount=Decimal("55.00"),
        date=datetime(2026, 1, 15).date(),
        description="Groceries",
        category="groceries",
        document_id=document.id
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    # Update document with transaction reference
    document.transaction_id = transaction.id
    db.commit()
    
    return {
        "transaction_id": transaction.id,
        "document_id": document.id
    }


@pytest.fixture
def transaction_with_multiple_documents(db, authenticated_client):
    """Create a transaction with multiple associated documents"""
    from app.models.transaction import Transaction
    from app.models.document import Document
    from app.models.user import User
    
    user = db.query(User).filter(User.email == "testuser@example.com").first()
    
    # Create transaction
    transaction = Transaction(
        user_id=user.id,
        type="expense",
        amount=Decimal("200.00"),
        date=datetime(2026, 1, 20).date(),
        description="Business expense with multiple receipts",
        category="office_supplies"
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    # Create multiple documents
    for i in range(3):
        document = Document(
            user_id=user.id,
            file_path=f"/test/receipt_{i}.jpg",
            document_type="receipt",
            ocr_status="completed",
            transaction_id=transaction.id
        )
        db.add(document)
    
    db.commit()
    
    return {
        "transaction_id": transaction.id
    }


# Report Generation Test Fixtures

@pytest.fixture
def test_transactions():
    """Sample transactions for report generation testing"""
    return [
        {
            "type": "income",
            "amount": 3500.00,
            "date": "2026-01-31",
            "description": "Monthly salary January",
            "category": "employment_income"
        },
        {
            "type": "income",
            "amount": 3500.00,
            "date": "2026-02-28",
            "description": "Monthly salary February",
            "category": "employment_income"
        },
        {
            "type": "expense",
            "amount": 150.00,
            "date": "2026-01-15",
            "description": "Office supplies",
            "category": "office_supplies",
            "is_deductible": True,
            "vat_rate": 0.20,
            "vat_amount": 25.00
        },
        {
            "type": "expense",
            "amount": 85.50,
            "date": "2026-01-20",
            "description": "BILLA groceries",
            "category": "groceries",
            "is_deductible": False
        },
        {
            "type": "income",
            "amount": 1200.00,
            "date": "2026-02-01",
            "description": "Rental income",
            "category": "rental_income"
        }
    ]


@pytest.fixture
def comprehensive_tax_data():
    """Comprehensive tax data for report generation"""
    return {
        "income_summary": {
            "employment": Decimal("42000.00"),
            "rental": Decimal("14400.00"),
            "self_employment": Decimal("18000.00"),
            "capital_gains": Decimal("2000.00"),
            "total": Decimal("76400.00")
        },
        "expense_summary": {
            "deductible": Decimal("8500.00"),
            "non_deductible": Decimal("3200.00"),
            "total": Decimal("11700.00")
        },
        "deductions": {
            "svs_contributions": Decimal("6500.00"),
            "commuting_allowance": Decimal("1356.00"),
            "home_office": Decimal("300.00"),
            "family_deductions": Decimal("700.80"),
            "total": Decimal("8856.80")
        },
        "tax_calculation": {
            "gross_income": Decimal("76400.00"),
            "deductions": Decimal("17356.80"),
            "taxable_income": Decimal("59043.20"),
            "income_tax": Decimal("15217.28"),
            "vat": Decimal("0.00"),
            "vat_exempt": True,
            "svs": Decimal("6500.00"),
            "total_tax": Decimal("21717.28"),
            "net_income": Decimal("54682.72"),
            "breakdown": [
                {
                    "bracket": "€13,539 - €21,992",
                    "rate": "20%",
                    "taxable_amount": Decimal("8453.00"),
                    "tax_amount": Decimal("1690.60")
                },
                {
                    "bracket": "€21,992 - €36,458",
                    "rate": "30%",
                    "taxable_amount": Decimal("14466.00"),
                    "tax_amount": Decimal("4339.80")
                },
                {
                    "bracket": "€36,458 - €70,365",
                    "rate": "40%",
                    "taxable_amount": Decimal("22585.20"),
                    "tax_amount": Decimal("9034.08")
                }
            ]
        }
    }


@pytest.fixture
def user_data_for_report(test_user):
    """User data formatted for report generation"""
    return {
        "name": test_user["full_name"],
        "tax_number": "12-345/6789",
        "address": "Teststraße 123, 1010 Wien, Austria",
        "user_type": test_user["user_type"],
        "vat_number": None
    }
