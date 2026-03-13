"""
Celery tasks for property management operations.

This module contains background tasks for:
- Annual depreciation generation (scheduled for year-end)
- Property metrics calculation
- Bulk property operations
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional
import logging

from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.property import Property, PropertyStatus
from app.models.user import User
from app.services.annual_depreciation_service import AnnualDepreciationService
from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management"""
    _db: Optional[Session] = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="property.generate_annual_depreciation",
    max_retries=3,
    default_retry_delay=300  # 5 minutes
)
def generate_annual_depreciation_task(
    self,
    year: Optional[int] = None,
    user_id: Optional[int] = None
) -> Dict:
    """
    Generate annual depreciation transactions for all active properties.
    
    This task is typically scheduled to run on December 31 at 23:00 via Celery Beat.
    It can also be triggered manually for specific users or years.
    
    Args:
        year: Tax year to generate depreciation for (default: current year)
        user_id: If provided, only generate for this user's properties
        
    Returns:
        Dict with summary of generated transactions:
        {
            'year': int,
            'properties_processed': int,
            'transactions_created': int,
            'properties_skipped': int,
            'total_amount': float,
            'users_affected': int,
            'errors': List[str]
        }
    """
    try:
        # Default to current year if not specified
        if year is None:
            year = datetime.now().year
        
        logger.info(f"Starting annual depreciation generation for year {year}")
        
        # Initialize service
        service = AnnualDepreciationService(self.db)
        
        # Generate depreciation
        result = service.generate_annual_depreciation(year=year, user_id=user_id)
        
        # Prepare summary
        summary = {
            'year': year,
            'properties_processed': result.properties_processed,
            'transactions_created': result.transactions_created,
            'properties_skipped': result.properties_skipped,
            'total_amount': float(result.total_amount),
            'users_affected': len(set(t.user_id for t in result.transactions)),
            'errors': [str(s) for s in result.skipped_details if 'error' in str(s).lower()],
            'task_id': self.request.id,
            'completed_at': datetime.now().isoformat()
        }
        
        logger.info(
            f"Annual depreciation generation completed: "
            f"{result.transactions_created} transactions created for "
            f"{result.properties_processed} properties"
        )
        
        # Send notification emails if configured
        if settings.ENABLE_EMAIL_NOTIFICATIONS and result.transactions_created > 0:
            try:
                _send_depreciation_notifications(self.db, year, result)
            except Exception as e:
                logger.error(f"Failed to send depreciation notifications: {e}")
                summary['notification_error'] = str(e)
        
        return summary
        
    except Exception as exc:
        logger.error(f"Error generating annual depreciation: {exc}", exc_info=True)
        
        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        
        # Return error summary if max retries exceeded
        return {
            'year': year,
            'error': str(exc),
            'task_id': self.request.id,
            'failed_at': datetime.now().isoformat()
        }


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="property.calculate_portfolio_metrics",
    max_retries=2
)
def calculate_portfolio_metrics_task(self, user_id: int, year: int) -> Dict:
    """
    Calculate portfolio-level metrics for a user.
    
    This task can be used to pre-calculate and cache portfolio metrics
    for dashboard display.
    
    Args:
        user_id: User ID
        year: Tax year
        
    Returns:
        Dict with portfolio metrics
    """
    try:
        from app.services.property_service import PropertyService
        
        logger.info(f"Calculating portfolio metrics for user {user_id}, year {year}")
        
        service = PropertyService(self.db)
        
        # Get all active properties
        properties = service.list_properties(user_id, include_archived=False)
        
        # Calculate metrics for each property
        metrics = []
        total_building_value = Decimal("0")
        total_depreciation = Decimal("0")
        total_rental_income = Decimal("0")
        total_expenses = Decimal("0")
        
        for prop in properties:
            prop_metrics = service.calculate_property_metrics(prop.id)
            metrics.append({
                'property_id': str(prop.id),
                'address': prop.address,
                'building_value': float(prop.building_value),
                'rental_income': float(prop_metrics.get('rental_income', 0)),
                'expenses': float(prop_metrics.get('expenses', 0)),
                'net_income': float(prop_metrics.get('net_income', 0)),
                'depreciation': float(prop_metrics.get('depreciation', 0))
            })
            
            total_building_value += prop.building_value
            total_depreciation += Decimal(str(prop_metrics.get('depreciation', 0)))
            total_rental_income += Decimal(str(prop_metrics.get('rental_income', 0)))
            total_expenses += Decimal(str(prop_metrics.get('expenses', 0)))
        
        summary = {
            'user_id': user_id,
            'year': year,
            'property_count': len(properties),
            'total_building_value': float(total_building_value),
            'total_depreciation': float(total_depreciation),
            'total_rental_income': float(total_rental_income),
            'total_expenses': float(total_expenses),
            'total_net_income': float(total_rental_income - total_expenses),
            'properties': metrics,
            'calculated_at': datetime.now().isoformat()
        }
        
        logger.info(f"Portfolio metrics calculated for user {user_id}: {len(properties)} properties")
        
        return summary
        
    except Exception as exc:
        logger.error(f"Error calculating portfolio metrics: {exc}", exc_info=True)
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        
        return {
            'user_id': user_id,
            'year': year,
            'error': str(exc),
            'failed_at': datetime.now().isoformat()
        }


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="property.bulk_archive_properties",
    max_retries=2
)
def bulk_archive_properties_task(
    self,
    property_ids: List[str],
    user_id: int,
    sale_date: str
) -> Dict:
    """
    Archive multiple properties in bulk.
    
    Args:
        property_ids: List of property UUIDs to archive
        user_id: User ID (for ownership validation)
        sale_date: Sale date in ISO format (YYYY-MM-DD)
        
    Returns:
        Dict with summary of archived properties
    """
    try:
        from app.services.property_service import PropertyService
        from uuid import UUID
        
        logger.info(f"Bulk archiving {len(property_ids)} properties for user {user_id}")
        
        service = PropertyService(self.db)
        sale_date_obj = datetime.fromisoformat(sale_date).date()
        
        archived = []
        failed = []
        
        for prop_id_str in property_ids:
            try:
                prop_id = UUID(prop_id_str)
                property = service.archive_property(prop_id, user_id, sale_date_obj)
                archived.append({
                    'property_id': str(property.id),
                    'address': property.address
                })
            except Exception as e:
                logger.error(f"Failed to archive property {prop_id_str}: {e}")
                failed.append({
                    'property_id': prop_id_str,
                    'error': str(e)
                })
        
        summary = {
            'user_id': user_id,
            'requested': len(property_ids),
            'archived': len(archived),
            'failed': len(failed),
            'archived_properties': archived,
            'failed_properties': failed,
            'completed_at': datetime.now().isoformat()
        }
        
        logger.info(f"Bulk archive completed: {len(archived)} archived, {len(failed)} failed")
        
        return summary
        
    except Exception as exc:
        logger.error(f"Error in bulk archive: {exc}", exc_info=True)
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        
        return {
            'user_id': user_id,
            'error': str(exc),
            'failed_at': datetime.now().isoformat()
        }


def _send_depreciation_notifications(db: Session, year: int, result) -> None:
    """
    Send email notifications to users about generated depreciation.
    """
    from app.services.email_service import email_service

    user_ids = set(t.user_id for t in result.transactions)

    for user_id in user_ids:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.email:
                continue

            user_transactions = [t for t in result.transactions if t.user_id == user_id]
            user_total = float(sum(t.amount for t in user_transactions))

            email_service.send_depreciation_notification(
                to_email=user.email,
                user_name=user.name,
                year=year,
                property_count=len(user_transactions),
                total_amount=user_total,
            )
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
            continue


# Task for testing purposes
@celery_app.task(name="property.test_task")
def test_property_task(message: str = "Hello from property tasks!") -> Dict:
    """Simple test task to verify Celery is working"""
    logger.info(f"Test task executed: {message}")
    return {
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'status': 'success'
    }
