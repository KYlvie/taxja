"""
Tests for structured logging in property services.

Verifies that property operations log structured data correctly.
"""

import pytest
import logging
from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.property_service import PropertyService
from app.services.historical_depreciation_service import HistoricalDepreciationService
from app.services.annual_depreciation_service import AnnualDepreciationService
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.user import User
from app.schemas.property import PropertyCreate


class LogCapture:
    """Helper class to capture log records"""
    
    def __init__(self):
        self.records = []
    
    def __call__(self, record):
        self.records.append(record)
        return True


@pytest.fixture
def log_capture():
    """Fixture to capture log records"""
    return LogCapture()


@pytest.fixture
def sample_user(db):
    """Create a sample user for testing"""
    user = User(
        email="test@example.com",
        name="Test User",
        hashed_password="hashed_password_here",
        user_type="landlord"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_property(db, sample_user):
    """Create a sample property for testing"""
    property = Property(
        user_id=sample_user.id,
        property_type=PropertyType.RENTAL,
        rental_percentage=Decimal("100.00"),
        address="Teststraße 123, 1010 Wien",
        street="Teststraße 123",
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
    db.add(property)
    db.commit()
    db.refresh(property)
    return property


def test_property_creation_logging(db, sample_user, log_capture):
    """Test that property creation logs structured data"""
    # Set up logger
    logger = logging.getLogger("app.services.property_service")
    handler = logging.Handler()
    handler.addFilter(log_capture)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        service = PropertyService(db)
        
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 6, 15),
            purchase_price=Decimal("350000.00"),
            building_value=Decimal("280000.00"),
            construction_year=1985,
            depreciation_rate=Decimal("0.02")
        )
        
        property = service.create_property(sample_user.id, property_data)
        
        # Verify log was created
        assert len(log_capture.records) > 0
        
        # Find the property creation log record
        creation_logs = [r for r in log_capture.records if hasattr(r, 'getMessage') and 'Property created' in r.getMessage()]
        assert len(creation_logs) > 0
        
        log_record = creation_logs[0]
        
        # Verify structured data in log record
        assert hasattr(log_record, 'user_id')
        assert log_record.user_id == sample_user.id
        assert hasattr(log_record, 'property_id')
        assert log_record.property_id == str(property.id)
        assert hasattr(log_record, 'property_type')
        assert log_record.property_type == PropertyType.RENTAL.value
        assert hasattr(log_record, 'address')
        assert "Teststraße 123" in log_record.address
        assert hasattr(log_record, 'purchase_price')
        assert log_record.purchase_price == 350000.00
        assert hasattr(log_record, 'building_value')
        assert log_record.building_value == 280000.00
        assert hasattr(log_record, 'depreciation_rate')
        assert log_record.depreciation_rate == 0.02
        
    finally:
        logger.removeHandler(handler)


def test_historical_depreciation_preview_logging(db, sample_property, log_capture):
    """Test that historical depreciation preview logs structured data"""
    logger = logging.getLogger("app.services.historical_depreciation_service")
    handler = logging.Handler()
    handler.addFilter(log_capture)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        service = HistoricalDepreciationService(db)
        
        # Calculate preview
        results = service.calculate_historical_depreciation(sample_property.id)
        
        # Verify log was created
        assert len(log_capture.records) > 0
        
        # Find the preview log record
        preview_logs = [r for r in log_capture.records if hasattr(r, 'getMessage') and 'preview calculated' in r.getMessage()]
        assert len(preview_logs) > 0
        
        log_record = preview_logs[0]
        
        # Verify structured data
        assert hasattr(log_record, 'property_id')
        assert log_record.property_id == str(sample_property.id)
        assert hasattr(log_record, 'property_address')
        assert hasattr(log_record, 'years_to_backfill')
        assert hasattr(log_record, 'total_amount')
        
    finally:
        logger.removeHandler(handler)


def test_historical_depreciation_backfill_logging(db, sample_property, log_capture):
    """Test that historical depreciation backfill logs structured data"""
    logger = logging.getLogger("app.services.historical_depreciation_service")
    handler = logging.Handler()
    handler.addFilter(log_capture)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        service = HistoricalDepreciationService(db)
        
        # Perform backfill
        result = service.backfill_depreciation(
            sample_property.id,
            sample_property.user_id,
            confirm=True
        )
        
        # Verify log was created
        assert len(log_capture.records) > 0
        
        # Find the backfill completion log record
        backfill_logs = [r for r in log_capture.records if hasattr(r, 'getMessage') and 'backfill completed' in r.getMessage()]
        assert len(backfill_logs) > 0
        
        log_record = backfill_logs[0]
        
        # Verify structured data
        assert hasattr(log_record, 'user_id')
        assert log_record.user_id == sample_property.user_id
        assert hasattr(log_record, 'property_id')
        assert log_record.property_id == str(sample_property.id)
        assert hasattr(log_record, 'property_address')
        assert hasattr(log_record, 'years_backfilled')
        assert log_record.years_backfilled == result.years_backfilled
        assert hasattr(log_record, 'total_amount')
        assert log_record.total_amount == float(result.total_amount)
        assert hasattr(log_record, 'year_range')
        assert hasattr(log_record, 'transaction_ids')
        
    finally:
        logger.removeHandler(handler)


def test_annual_depreciation_generation_logging(db, sample_property, log_capture):
    """Test that annual depreciation generation logs structured data with counts"""
    logger = logging.getLogger("app.services.annual_depreciation_service")
    handler = logging.Handler()
    handler.addFilter(log_capture)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        service = AnnualDepreciationService(db)
        
        # Generate depreciation for current year
        current_year = date.today().year
        result = service.generate_annual_depreciation(
            year=current_year,
            user_id=sample_property.user_id
        )
        
        # Verify log was created
        assert len(log_capture.records) > 0
        
        # Find the generation completion log record
        generation_logs = [r for r in log_capture.records if hasattr(r, 'getMessage') and 'generation completed' in r.getMessage()]
        assert len(generation_logs) > 0
        
        log_record = generation_logs[0]
        
        # Verify structured data with counts
        assert hasattr(log_record, 'year')
        assert log_record.year == current_year
        assert hasattr(log_record, 'user_id')
        assert hasattr(log_record, 'properties_processed')
        assert log_record.properties_processed == result.properties_processed
        assert hasattr(log_record, 'transactions_created')
        assert log_record.transactions_created == result.transactions_created
        assert hasattr(log_record, 'properties_skipped')
        assert log_record.properties_skipped == result.properties_skipped
        assert hasattr(log_record, 'total_amount')
        assert log_record.total_amount == float(result.total_amount)
        assert hasattr(log_record, 'skip_reasons')
        assert isinstance(log_record.skip_reasons, dict)
        assert 'already_exists' in log_record.skip_reasons
        assert 'fully_depreciated' in log_record.skip_reasons
        assert 'errors' in log_record.skip_reasons
        
    finally:
        logger.removeHandler(handler)


def test_annual_depreciation_individual_property_logging(db, sample_property, log_capture):
    """Test that individual property depreciation creation is logged"""
    logger = logging.getLogger("app.services.annual_depreciation_service")
    handler = logging.Handler()
    handler.addFilter(log_capture)
    logger.setLevel(logging.INFO)
    
    try:
        service = AnnualDepreciationService(db)
        
        # Generate depreciation for a specific year
        result = service.generate_annual_depreciation(
            year=date.today().year,
            user_id=sample_property.user_id
        )
        
        # Verify individual property logs exist
        property_logs = [r for r in log_capture.records if hasattr(r, 'getMessage') and 'Created depreciation transaction' in r.getMessage()]
        
        # Should have logs for each created transaction
        assert len(property_logs) == result.transactions_created
        
    finally:
        logger.removeHandler(handler)


def test_logging_format_consistency(db, sample_user, sample_property, log_capture):
    """Test that all logging uses consistent structured format"""
    # Set up loggers for all services
    loggers = [
        logging.getLogger("app.services.property_service"),
        logging.getLogger("app.services.historical_depreciation_service"),
        logging.getLogger("app.services.annual_depreciation_service")
    ]
    
    handler = logging.Handler()
    handler.addFilter(log_capture)
    
    for logger in loggers:
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    try:
        # Trigger various operations
        property_service = PropertyService(db)
        hist_service = HistoricalDepreciationService(db)
        annual_service = AnnualDepreciationService(db)
        
        # Create property
        property_data = PropertyCreate(
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Teststraße 456",
            city="Wien",
            postal_code="1020",
            purchase_date=date(2021, 1, 1),
            purchase_price=Decimal("400000.00"),
            building_value=Decimal("320000.00"),
            construction_year=1990,
            depreciation_rate=Decimal("0.02")
        )
        new_property = property_service.create_property(sample_user.id, property_data)
        
        # Calculate preview
        hist_service.calculate_historical_depreciation(new_property.id)
        
        # Generate annual depreciation
        annual_service.generate_annual_depreciation(
            year=date.today().year,
            user_id=sample_user.id
        )
        
        # Verify all logs have structured data (extra attributes)
        for record in log_capture.records:
            if hasattr(record, 'getMessage'):
                message = record.getMessage()
                # All our structured logs should have at least one extra attribute
                if any(keyword in message for keyword in ['created', 'calculated', 'completed', 'generated']):
                    # Check that record has extra attributes beyond standard ones
                    standard_attrs = {'name', 'msg', 'args', 'created', 'filename', 'funcName', 
                                    'levelname', 'levelno', 'lineno', 'module', 'msecs', 
                                    'message', 'pathname', 'process', 'processName', 
                                    'relativeCreated', 'thread', 'threadName', 'exc_info', 
                                    'exc_text', 'stack_info'}
                    extra_attrs = set(dir(record)) - standard_attrs
                    assert len(extra_attrs) > 0, f"Log record missing structured data: {message}"
        
    finally:
        for logger in loggers:
            logger.removeHandler(handler)
