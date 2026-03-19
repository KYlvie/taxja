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
async def get_dashboard(
    tax_year: Optional[int] = Query(None, alias="tax_year", description="Tax year"),
    year: Optional[int] = Query(None, description="Tax year (alias)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get comprehensive dashboard data.

    Results are cached in Redis for 5 minutes per user+year to reduce DB load.
    Cache is invalidated when transactions are created/updated/deleted.
    """
    from app.core.cache import cache

    resolved_year = tax_year or year or datetime.now().year
    cache_key = f"dashboard:{current_user.id}:{resolved_year}"

    try:
        # Auto-generate any due recurring transactions (backfills missed months)
        try:
            from app.services.recurring_transaction_service import RecurringTransactionService
            recurring_service = RecurringTransactionService(db)
            generated = recurring_service.generate_due_transactions(
                target_date=date.today(),
                user_id=current_user.id,
            )
            if generated:
                import logging
                logging.getLogger(__name__).info(
                    f"Auto-generated {len(generated)} recurring transactions for user {current_user.id}"
                )
                await cache.delete_pattern(f"dashboard:{current_user.id}:*")
        except Exception as gen_err:
            import logging
            logging.getLogger(__name__).warning(f"Recurring generation failed: {gen_err}", exc_info=True)

        # Try cache after any due recurring generation has been applied
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        dashboard_service = DashboardService(db)
        data = dashboard_service.get_dashboard_data(current_user.id, resolved_year, user=current_user)

        # Cache for 5 minutes
        await cache.set(cache_key, data, ttl=300)

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


@router.get("/dashboard/alerts")
def get_dashboard_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get actionable alerts for the current user on login.

    Returns:
    - pending_suggestions: Documents with unconfirmed recurring transaction suggestions
    - expiring_contracts: Recurring transactions whose end_date is approaching (within 30 days)
    - expired_contracts: Recurring transactions that have already expired
    """
    from app.models.document import Document
    from app.models.recurring_transaction import RecurringTransaction
    from datetime import timedelta
    from sqlalchemy import and_, cast, String
    from sqlalchemy.dialects.postgresql import JSONB

    alerts = {
        "pending_suggestions": [],
        "expiring_contracts": [],
        "expired_contracts": [],
    }

    today = date.today()
    soon = today + timedelta(days=30)

    # 1. Find documents with pending import suggestions
    try:
        docs = (
            db.query(Document)
            .filter(
                Document.user_id == current_user.id,
                Document.ocr_result.isnot(None),
            )
            .all()
        )
        for doc in docs:
            ocr = doc.ocr_result
            if not isinstance(ocr, dict):
                continue
            suggestion = ocr.get("import_suggestion")
            if not suggestion or suggestion.get("status") != "pending":
                continue
            stype = suggestion.get("type", "")
            if stype not in (
                "create_recurring_income",
                "create_recurring_expense",
                "create_property",
            ) and not stype.startswith("import_"):
                continue
            data = suggestion.get("data", {})
            alerts["pending_suggestions"].append(
                {
                    "document_id": doc.id,
                    "file_name": doc.file_name,
                    "document_type": doc.document_type.value if doc.document_type else "other",
                    "suggestion_type": stype,
                    "description": data.get("description")
                    or data.get("address")
                    or doc.file_name,
                    "amount": data.get("monthly_rent") or data.get("amount"),
                    "frequency": data.get("frequency"),
                    "start_date": data.get("start_date"),
                    "end_date": data.get("end_date"),
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                }
            )
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Failed to fetch pending suggestions: {e}")

    # 2. Find recurring transactions expiring soon or already expired
    try:
        recurrings = (
            db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.user_id == current_user.id,
                RecurringTransaction.end_date.isnot(None),
            )
            .all()
        )
        for rt in recurrings:
            item = {
                "recurring_id": rt.id,
                "description": rt.description,
                "amount": float(rt.amount),
                "frequency": rt.frequency.value if rt.frequency else "monthly",
                "end_date": rt.end_date.isoformat(),
                "is_active": rt.is_active,
                "recurring_type": rt.recurring_type.value if rt.recurring_type else "manual",
                "property_id": str(rt.property_id) if rt.property_id else None,
            }
            if rt.end_date < today:
                # Already expired
                item["days_expired"] = (today - rt.end_date).days
                alerts["expired_contracts"].append(item)
            elif rt.end_date <= soon:
                # Expiring within 30 days
                item["days_remaining"] = (rt.end_date - today).days
                alerts["expiring_contracts"].append(item)
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Failed to fetch contract expiry alerts: {e}")

    return alerts


@router.get("/dashboard/health-check")
def get_health_check(
    tax_year: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Comprehensive tax health check triggered on user login.

    Analyzes user data across all sources (transactions, documents, properties,
    recurring transactions) and returns prioritized, actionable items with i18n keys.
    Results are cached for 5 minutes per user+year.
    """
    from app.core.cache import cache
    import asyncio

    resolved_year = tax_year or (datetime.now().year - 1)
    cache_key = f"health_check:{current_user.id}:{resolved_year}"

    # Try cache (sync wrapper for async cache)
    try:
        loop = asyncio.new_event_loop()
        cached_data = loop.run_until_complete(cache.get(cache_key))
        loop.close()
        if cached_data is not None:
            return cached_data
    except Exception:
        cached_data = None

    try:
        from app.services.tax_health_service import TaxHealthService
        service = TaxHealthService(db)
        result = service.check_health(current_user.id, resolved_year)

        # Cache for 5 minutes
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(cache.set(cache_key, result, ttl=300))
            loop.close()
        except Exception:
            pass

        return result
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Health check failed for user {current_user.id}: {e}")
        # Never break the login flow
        return {
            "check_date": str(date.today()),
            "tax_year": resolved_year,
            "score": 100,
            "items": [],
            "summary": {"high": 0, "medium": 0, "low": 0},
        }
