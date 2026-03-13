"""Celery application configuration"""
import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, task_success
from app.core.config import settings

# Configure logging for Celery tasks
logger = logging.getLogger(__name__)

celery_app = Celery(
    "taxja",
    broker=settings.CELERY_BROKER,
    backend=settings.CELERY_BACKEND,
    include=["app.tasks.ocr_tasks", "app.tasks.property_tasks", "app.tasks.recurring_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Vienna",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    # Task result backend settings
    result_expires=3600 * 24 * 7,  # Keep results for 7 days
    result_extended=True,  # Store additional task metadata
    # Task execution settings
    task_acks_late=True,  # Acknowledge tasks after completion
    task_reject_on_worker_lost=True,  # Reject tasks if worker crashes
    worker_prefetch_multiplier=1,  # Fetch one task at a time for long-running tasks
)

# Celery Beat schedule configuration
celery_app.conf.beat_schedule = {
    # Daily recurring transaction generation - runs at 00:05 Vienna time
    'generate-recurring-transactions-daily': {
        'task': 'generate_recurring_transactions',
        'schedule': {
            'minute': '5',
            'hour': '0',
        },
        'args': (),
        'kwargs': {},
        'options': {
            'expires': 3600,  # Task expires after 1 hour if not picked up
            'priority': 8,  # High priority
        },
    },
    # Daily property status check - runs at 01:00 Vienna time
    'check-property-status-changes-daily': {
        'task': 'check_property_status_changes',
        'schedule': {
            'minute': '0',
            'hour': '1',
        },
        'args': (),
        'kwargs': {},
        'options': {
            'expires': 3600,
            'priority': 7,
        },
    },
    # Annual depreciation generation - runs on December 31 at 23:00 Vienna time
    'generate-annual-depreciation': {
        'task': 'property.generate_annual_depreciation',
        'schedule': {
            'minute': '0',
            'hour': '23',
            'day_of_month': '31',
            'month_of_year': '12',
        },
        'args': (),  # No arguments - will use current year by default
        'kwargs': {},
        'options': {
            'expires': 3600 * 2,  # Task expires after 2 hours if not picked up
            'priority': 9,  # High priority (0-9 scale, 9 is highest)
        },
    },
}

# Import all models so SQLAlchemy relationships resolve correctly
import app.models.user  # noqa
import app.models.transaction  # noqa
import app.models.document  # noqa
import app.models.chat_message  # noqa
import app.models.tax_report  # noqa
import app.models.tax_configuration  # noqa
import app.models.classification_correction  # noqa
import app.models.loss_carryforward  # noqa
import app.models.property  # noqa
import app.models.recurring_transaction  # noqa


# Task monitoring signals for logging and observability

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log task execution start with structured logging"""
    logger.info(
        f"Task started: {task.name}",
        extra={
            'task_id': task_id,
            'task_name': task.name,
            'task_args': str(args),
            'task_kwargs': str(kwargs),
            'event': 'task_started'
        }
    )


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra):
    """Log task execution completion with structured logging"""
    logger.info(
        f"Task completed: {task.name}",
        extra={
            'task_id': task_id,
            'task_name': task.name,
            'task_state': state,
            'event': 'task_completed'
        }
    )


@task_success.connect
def task_success_handler(sender=None, result=None, **extra):
    """Log successful task execution with result summary"""
    task_name = sender.name if sender else 'unknown'
    
    # Special handling for annual depreciation task
    if task_name == 'property.generate_annual_depreciation' and isinstance(result, dict):
        logger.info(
            f"Annual depreciation generation successful",
            extra={
                'task_name': task_name,
                'year': result.get('year'),
                'properties_processed': result.get('properties_processed'),
                'transactions_created': result.get('transactions_created'),
                'total_amount': result.get('total_amount'),
                'users_affected': result.get('users_affected'),
                'event': 'annual_depreciation_success'
            }
        )
    else:
        logger.info(
            f"Task succeeded: {task_name}",
            extra={
                'task_name': task_name,
                'event': 'task_success'
            }
        )


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **extra):
    """Log task failures with error details"""
    task_name = sender.name if sender else 'unknown'
    
    logger.error(
        f"Task failed: {task_name}",
        extra={
            'task_id': task_id,
            'task_name': task_name,
            'exception': str(exception),
            'exception_type': type(exception).__name__,
            'task_args': str(args),
            'task_kwargs': str(kwargs),
            'event': 'task_failure'
        },
        exc_info=einfo
    )
    
    # Special alert for annual depreciation failures
    if task_name == 'property.generate_annual_depreciation':
        logger.critical(
            f"CRITICAL: Annual depreciation generation failed",
            extra={
                'task_id': task_id,
                'exception': str(exception),
                'event': 'annual_depreciation_failure'
            }
        )
