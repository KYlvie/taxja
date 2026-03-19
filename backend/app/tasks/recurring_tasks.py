"""Celery tasks for recurring transaction generation"""
from celery import shared_task
from datetime import date
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.recurring_transaction_service import RecurringTransactionService


@shared_task(name="generate_recurring_transactions")
def generate_recurring_transactions_task():
    """
    Daily task to generate all due recurring transactions.
    
    This task should be scheduled to run daily (e.g., at midnight).
    Configured in celery beat schedule.
    """
    db: Session = SessionLocal()
    
    try:
        service = RecurringTransactionService(db)
        
        # Generate transactions for today
        generated = service.generate_due_transactions(target_date=date.today())
        
        return {
            "success": True,
            "generated_count": len(generated),
            "date": str(date.today()),
            "transaction_ids": [t.id for t in generated]
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "date": str(date.today())
        }
    
    finally:
        db.close()


@shared_task(name="check_property_status_changes")
def check_property_status_changes_task():
    """
    Task to check for property status changes and auto-pause recurring transactions.
    
    This task should run daily to detect sold/archived properties.
    """
    from app.models.property import Property, PropertyStatus
    from app.models.recurring_transaction import RecurringTransaction
    
    db: Session = SessionLocal()
    
    try:
        service = RecurringTransactionService(db)
        
        # Find properties that were recently sold/archived
        sold_properties = db.query(Property).filter(
            Property.status.in_([PropertyStatus.SOLD, PropertyStatus.ARCHIVED])
        ).all()
        
        paused_count = 0
        for prop in sold_properties:
            # Check if there are active recurring transactions
            active_recurrings = service.get_property_recurring_transactions(
                property_id=str(prop.id),
                active_only=True
            )
            
            if active_recurrings:
                paused = service.auto_pause_for_sold_property(str(prop.id))
                paused_count += len(paused)
        
        return {
            "success": True,
            "properties_checked": len(sold_properties),
            "recurring_transactions_paused": paused_count
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    
    finally:
        db.close()


@shared_task(name="sync_expired_rental_contracts")
def sync_expired_rental_contracts_task():
    """
    Catch-up task: find rental contracts that have expired (end_date < today)
    but whose linked property still has stale rental_percentage / property_type.

    This handles cases where:
    - The daily generate task was missed or failed
    - Existing data was created before the auto-recalculate logic was added
    - Manual edits left the property in an inconsistent state

    Should run daily, after generate_recurring_transactions.
    """
    import logging
    from app.models.property import Property, PropertyStatus
    from app.models.recurring_transaction import (
        RecurringTransaction,
        RecurringTransactionType,
    )
    from app.services.property_service import PropertyService

    logger = logging.getLogger(__name__)
    db: Session = SessionLocal()

    try:
        today = date.today()

        # Find rental contracts that are expired but still marked active
        expired_active = (
            db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
                RecurringTransaction.is_active == True,
                RecurringTransaction.end_date.isnot(None),
                RecurringTransaction.end_date < today,
            )
            .all()
        )

        deactivated_count = 0
        recalculated_props = set()

        for rt in expired_active:
            rt.is_active = False
            deactivated_count += 1

            if rt.property_id:
                recalculated_props.add((rt.property_id, rt.user_id))

        if deactivated_count > 0:
            db.commit()

        ps = PropertyService(db)
        recalc_count = 0
        for prop_id, user_id in recalculated_props:
            try:
                ps.recalculate_rental_percentage(prop_id, user_id)
                recalc_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to recalculate rental_percentage for property "
                    f"{prop_id}: {e}"
                )

        return {
            "success": True,
            "contracts_deactivated": deactivated_count,
            "properties_recalculated": recalc_count,
        }

    except Exception as e:
        logger.error(f"sync_expired_rental_contracts failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()
