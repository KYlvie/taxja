"""
Dashboard API Endpoints

Provides dashboard data, suggestions, and calendar.
"""

from typing import Optional
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(
    tax_year: Optional[int] = Query(None, alias="tax_year", description="Tax year"),
    year: Optional[int] = Query(None, description="Tax year (alias)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get comprehensive dashboard data."""
    resolved_year = tax_year or year or datetime.now().year
    try:
        dashboard_service = DashboardService(db)
        data = dashboard_service.get_dashboard_data(current_user.id, resolved_year, user=current_user)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/suggestions")
def get_savings_suggestions(
    tax_year: Optional[int] = Query(None, description="Tax year"),
    language: str = Query("de", description="Language (de, en, zh)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get personalized tax savings suggestions based on user data."""
    resolved_year = tax_year or datetime.now().year
    try:
        dashboard_service = DashboardService(db)
        return dashboard_service.get_suggestions(current_user.id, resolved_year, language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/income-profile")
def get_income_profile(
    tax_year: Optional[int] = Query(None, description="Tax year"),
    language: str = Query("de", description="Language (de, en, zh)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detect active income types from transactions and compare with user profile."""
    resolved_year = tax_year or datetime.now().year
    try:
        dashboard_service = DashboardService(db)
        return dashboard_service.detect_active_income_types(
            current_user.id, resolved_year, language
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/calendar")
def get_tax_calendar(
    tax_year: Optional[int] = Query(None, description="Tax year"),
    language: str = Query("de", description="Language (de, en, zh)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get upcoming Austrian tax deadlines."""
    resolved_year = tax_year or datetime.now().year
    try:
        dashboard_service = DashboardService(db)
        return dashboard_service.get_calendar(resolved_year, language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/property-metrics")
def get_property_metrics(
    tax_year: Optional[int] = Query(None, description="Tax year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get property portfolio metrics for landlord users."""
    resolved_year = tax_year or datetime.now().year
    try:
        dashboard_service = DashboardService(db)
        return dashboard_service.get_property_metrics(current_user.id, resolved_year)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
