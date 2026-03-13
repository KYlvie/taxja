"""
Shared service fixtures for E2E and integration tests.

This module provides fixtures for service layer instances.
"""
import pytest
from sqlalchemy.orm import Session

from app.services.property_service import PropertyService
from app.services.afa_calculator import AfACalculator
from app.services.historical_depreciation_service import HistoricalDepreciationService
from app.services.annual_depreciation_service import AnnualDepreciationService
from app.services.address_matcher import AddressMatcher
from app.services.property_report_service import PropertyReportService
from app.services.e1_form_import_service import E1FormImportService
from app.services.bescheid_import_service import BescheidImportService


@pytest.fixture
def property_service(db_session: Session) -> PropertyService:
    """Create PropertyService instance."""
    return PropertyService(db_session)


@pytest.fixture
def afa_calculator(db_session: Session) -> AfACalculator:
    """Create AfACalculator instance."""
    return AfACalculator(db_session)


@pytest.fixture
def historical_service(db_session: Session) -> HistoricalDepreciationService:
    """Create HistoricalDepreciationService instance."""
    return HistoricalDepreciationService(db_session)


@pytest.fixture
def annual_service(db_session: Session) -> AnnualDepreciationService:
    """Create AnnualDepreciationService instance."""
    return AnnualDepreciationService(db_session)


@pytest.fixture
def address_matcher(db_session: Session) -> AddressMatcher:
    """Create AddressMatcher instance."""
    return AddressMatcher(db_session)


@pytest.fixture
def report_service(db_session: Session) -> PropertyReportService:
    """Create PropertyReportService instance."""
    return PropertyReportService(db_session)


@pytest.fixture
def e1_service(db_session: Session) -> E1FormImportService:
    """Create E1FormImportService instance."""
    return E1FormImportService(db_session)


@pytest.fixture
def bescheid_service(db_session: Session) -> BescheidImportService:
    """Create BescheidImportService instance."""
    return BescheidImportService(db_session)
