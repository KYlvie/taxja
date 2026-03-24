"""Admin endpoints for subscription management and account cancellation"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, File
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

logger = logging.getLogger(__name__)

from app.db.base import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType
from app.models.payment_event import PaymentEvent
from app.schemas.subscription import SubscriptionResponse
from app.schemas.account import AdminCancellationStatsResponse
from app.schemas.plan import PlanResponse, PlanCreate, PlanUpdate
from app.services.subscription_service import SubscriptionService
from app.services.account_cancellation_service import AccountCancellationService, COOLING_OFF_DAYS

router = APIRouter()


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
def list_all_subscriptions(
    status: Optional[SubscriptionStatus] = None,
    plan_type: Optional[PlanType] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    List all subscriptions with optional filters.
    
    Admin only endpoint.
    """
    query = db.query(Subscription)
    
    if status:
        query = query.filter(Subscription.status == status)
    
    if plan_type:
        query = query.join(Plan).filter(Plan.plan_type == plan_type)
    
    subscriptions = query.offset(skip).limit(limit).all()
    return subscriptions


@router.get("/subscriptions/{user_id}", response_model=SubscriptionResponse)
def get_user_subscription_admin(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get subscription details for a specific user.
    
    Admin only endpoint.
    """
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    return subscription


@router.post("/subscriptions/{user_id}/grant-trial")
def grant_trial(
    user_id: int,
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Grant trial period to a user.
    
    Admin only endpoint.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user already used trial
    if user.trial_used:
        raise HTTPException(status_code=400, detail="User has already used trial")
    
    # Get Pro plan
    pro_plan = db.query(Plan).filter(Plan.plan_type == PlanType.PRO).first()
    if not pro_plan:
        raise HTTPException(status_code=404, detail="Pro plan not found")
    
    # Create or update subscription
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    
    trial_end = datetime.utcnow() + timedelta(days=days)
    
    if not subscription:
        subscription = Subscription(
            user_id=user_id,
            plan_id=pro_plan.id,
            status=SubscriptionStatus.TRIALING,
            current_period_start=datetime.utcnow(),
            current_period_end=trial_end
        )
        db.add(subscription)
    else:
        subscription.plan_id = pro_plan.id
        subscription.status = SubscriptionStatus.TRIALING
        subscription.current_period_end = trial_end
    
    # Update user trial status
    user.trial_used = True
    user.trial_end_date = trial_end
    
    db.commit()
    db.refresh(subscription)
    
    return {
        "message": f"Trial granted for {days} days",
        "subscription_id": subscription.id,
        "trial_end_date": trial_end
    }


@router.put("/subscriptions/{user_id}/change-plan")
def change_user_plan(
    user_id: int,
    plan_type: PlanType,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Change user's subscription plan.
    
    Admin only endpoint. Bypasses payment.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    plan = db.query(Plan).filter(Plan.plan_type == plan_type).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    subscription_service = SubscriptionService(db)
    subscription = subscription_service.get_user_subscription(user_id)
    
    if not subscription:
        # Create new subscription
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30)
        )
        db.add(subscription)
    else:
        # Update existing subscription
        subscription.plan_id = plan.id
        subscription.status = SubscriptionStatus.ACTIVE
    
    db.commit()
    db.refresh(subscription)
    
    return {
        "message": f"Plan changed to {plan_type.value}",
        "subscription": subscription
    }


@router.post("/subscriptions/{user_id}/extend")
def extend_subscription(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Extend user's subscription period.
    
    Admin only endpoint.
    """
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    subscription.current_period_end += timedelta(days=days)
    db.commit()
    
    return {
        "message": f"Subscription extended by {days} days",
        "new_end_date": subscription.current_period_end
    }


@router.get("/analytics/revenue")
def get_revenue_analytics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get revenue analytics (MRR, ARR).
    
    Admin only endpoint.
    """
    # Calculate MRR — include active and trialing subscriptions
    active_statuses = [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    active_subscriptions = (
        db.query(Subscription)
        .join(Plan, Subscription.plan_id == Plan.id)
        .filter(Subscription.status.in_(active_statuses))
        .all()
    )
    
    mrr = sum(
        float(sub.plan.monthly_price or 0)
        for sub in active_subscriptions
    )
    
    arr = mrr * 12
    
    # Count subscriptions by plan
    plan_counts = (
        db.query(Plan.plan_type, func.count(Subscription.id))
        .join(Subscription, Subscription.plan_id == Plan.id)
        .filter(Subscription.status.in_(active_statuses))
        .group_by(Plan.plan_type)
        .all()
    )
    
    return {
        "mrr": float(mrr),
        "arr": float(arr),
        "active_subscriptions": len(active_subscriptions),
        "plan_distribution": {
            plan_type.value: count 
            for plan_type, count in plan_counts
        }
    }


@router.get("/analytics/subscriptions")
def get_subscription_analytics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get subscription counts by plan and status.
    
    Admin only endpoint.
    """
    # Count by status
    status_counts = (
        db.query(Subscription.status, func.count(Subscription.id))
        .group_by(Subscription.status)
        .all()
    )
    
    # Count by plan
    plan_counts = (
        db.query(Plan.plan_type, func.count(Subscription.id))
        .join(Subscription, Subscription.plan_id == Plan.id)
        .group_by(Plan.plan_type)
        .all()
    )
    
    return {
        "by_status": {
            status.value: count 
            for status, count in status_counts
        },
        "by_plan": {
            plan_type.value: count 
            for plan_type, count in plan_counts
        }
    }


@router.get("/analytics/conversion")
def get_conversion_analytics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get trial to paid conversion rate.
    
    Admin only endpoint.
    """
    # Count users who used trial
    trial_users = db.query(User).filter(User.trial_used == True).count()
    
    # Count users who converted to paid
    converted_users = (
        db.query(User)
        .join(Subscription)
        .join(Plan)
        .filter(
            and_(
                User.trial_used == True,
                Plan.plan_type != PlanType.FREE,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        )
        .count()
    )
    
    conversion_rate = (converted_users / trial_users * 100) if trial_users > 0 else 0
    
    return {
        "trial_users": trial_users,
        "converted_users": converted_users,
        "conversion_rate": round(conversion_rate, 2)
    }


@router.get("/analytics/churn")
def get_churn_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Get churn rate by plan.
    
    Admin only endpoint.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Count canceled subscriptions in period
    canceled = (
        db.query(Plan.plan_type, func.count(Subscription.id))
        .join(Subscription)
        .filter(
            and_(
                Subscription.status == SubscriptionStatus.CANCELED,
                Subscription.updated_at >= start_date
            )
        )
        .group_by(Plan.plan_type)
        .all()
    )
    
    # Count total active at start of period
    total_active = (
        db.query(Plan.plan_type, func.count(Subscription.id))
        .join(Subscription)
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
        .group_by(Plan.plan_type)
        .all()
    )
    
    churn_by_plan = {}
    for plan_type, active_count in total_active:
        canceled_count = next(
            (count for pt, count in canceled if pt == plan_type),
            0
        )
        churn_rate = (canceled_count / active_count * 100) if active_count > 0 else 0
        churn_by_plan[plan_type.value] = {
            "canceled": canceled_count,
            "active": active_count,
            "churn_rate": round(churn_rate, 2)
        }
    
    return {
        "period_days": days,
        "churn_by_plan": churn_by_plan
    }


@router.post("/plans", response_model=PlanResponse)
def create_plan_admin(
    plan: PlanCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Create a new subscription plan.
    
    Admin only endpoint.
    """
    # Check if plan already exists
    existing = db.query(Plan).filter(Plan.plan_type == plan.plan_type).first()
    if existing:
        raise HTTPException(status_code=400, detail="Plan already exists")
    
    db_plan = Plan(**plan.dict())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    
    return db_plan


@router.put("/plans/{plan_id}", response_model=PlanResponse)
def update_plan_admin(
    plan_id: int,
    plan_update: PlanUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Update plan configuration.
    
    Admin only endpoint. Only affects new subscriptions.
    """
    db_plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    update_data = plan_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_plan, field, value)
    
    db.commit()
    db.refresh(db_plan)
    
    return db_plan


@router.get("/payment-events")
def list_payment_events(
    event_type: Optional[str] = None,
    user_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    List payment events with filters.
    
    Admin only endpoint.
    """
    query = db.query(PaymentEvent)
    
    if event_type:
        query = query.filter(PaymentEvent.event_type == event_type)
    
    if user_id:
        query = query.filter(PaymentEvent.user_id == user_id)
    
    events = query.order_by(PaymentEvent.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": query.count(),
        "events": [
            {
                "id": event.id,
                "stripe_event_id": event.stripe_event_id,
                "event_type": event.event_type,
                "user_id": event.user_id,
                "created_at": event.created_at,
                "payload": event.payload
            }
            for event in events
        ]
    }



# ------------------------------------------------------------------
# Account cancellation management endpoints
# ------------------------------------------------------------------


@router.get("/users")
def list_users(
    status: Optional[str] = Query(None, description="Filter by account_status (active, deactivated, deletion_pending)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    List users with optional account status filter.

    Admin only endpoint. Returns user details including cancellation-related
    fields and computed cooling-off days remaining.
    """
    query = db.query(User)

    if status:
        query = query.filter(User.account_status == status)

    users = query.offset(skip).limit(limit).all()
    now = datetime.utcnow()

    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "account_status": u.account_status,
            "deactivated_at": u.deactivated_at,
            "scheduled_deletion_at": u.scheduled_deletion_at,
            "cooling_off_days_remaining": (
                max(0, (u.scheduled_deletion_at - now).days)
                if u.scheduled_deletion_at and u.scheduled_deletion_at > now
                else 0
            ),
        }
        for u in users
    ]


@router.post("/users/{user_id}/hard-delete")
def admin_hard_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Manually trigger hard deletion for a specific user.

    Admin only endpoint. Skips the cooling-off period and immediately
    performs permanent data deletion.
    """
    try:
        result = AccountCancellationService.hard_delete_account(user_id, "admin", db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create admin audit log (user is already deleted, so log with admin's id)
    audit = AuditLog(
        user_id=admin.id,
        operation_type="delete",
        entity_type="property",
        entity_id=str(user_id),
        details={
            "action": "admin_hard_delete",
            "target_user_id": user_id,
            "admin_id": admin.id,
        },
    )
    db.add(audit)
    db.commit()

    return result


@router.post("/users/{user_id}/reactivate")
def admin_reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Manually reactivate a deactivated user account.

    Admin only endpoint. Restores the account to active status.
    """
    try:
        result = AccountCancellationService.reactivate_account(user_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create admin audit log
    audit = AuditLog(
        user_id=admin.id,
        operation_type="update",
        entity_type="property",
        entity_id=str(user_id),
        details={
            "action": "admin_reactivate",
            "target_user_id": user_id,
            "admin_id": admin.id,
        },
    )
    db.add(audit)
    db.commit()

    return result


@router.get("/cancellation-stats", response_model=AdminCancellationStatsResponse)
def get_cancellation_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Get cancellation statistics for the admin dashboard.

    Admin only endpoint. Returns monthly cancellations, reason distribution,
    reactivation rate, and average user lifetime.
    """
    return AccountCancellationService.get_admin_cancellation_stats(db)


# ═══════════════════════════════════════════════════════════════════════════
# Tax Form Template Management (PDF upload/update/delete)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/tax-form-templates")
async def upload_tax_form_template(
    tax_year: int = Query(..., ge=2022, le=2030),
    form_type: str = Query(..., description="E1, E1a, E1b, L1, L1k, K1, U1, UVA"),
    field_mapping: str = Query("{}", description="JSON string: {kz: pdf_field_name}"),
    display_name: Optional[str] = Query(None),
    source_url: Optional[str] = Query(None),
    bmf_version: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Upload or replace a blank BMF PDF form template.

    POST /admin/tax-form-templates?tax_year=2025&form_type=E1&field_mapping={...}
    Body: multipart/form-data with 'file' field containing the PDF

    If a template for the same year+type exists, it is replaced.
    """
    from fastapi import UploadFile, File, Form
    from app.models.tax_form_template import TaxFormTemplate, TaxFormType
    import json as json_lib

    # Validate form_type
    try:
        ft_enum = TaxFormType(form_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid form_type: {form_type}. Valid: {[t.value for t in TaxFormType]}"
        )

    # Parse field_mapping JSON
    try:
        mapping = json_lib.loads(field_mapping)
        if not isinstance(mapping, dict):
            raise ValueError("field_mapping must be a JSON object")
    except (json_lib.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid field_mapping JSON: {e}")

    # For now, accept raw PDF body (will be enhanced with UploadFile in production)
    # Placeholder: this endpoint needs the PDF bytes from the request body
    raise HTTPException(
        status_code=501,
        detail="Use POST /admin/tax-form-templates/upload with multipart form data"
    )


@router.post("/tax-form-templates/upload")
async def upload_tax_form_template_file(
    file: bytes = File(..., description="Blank BMF PDF form template"),
    tax_year: int = Query(..., ge=2022, le=2030),
    form_type: str = Query(..., description="E1, E1a, E1b, L1, L1k, K1, U1, UVA"),
    field_mapping_json: str = Query("{}", description="JSON: {kz: pdf_field_name}"),
    display_name: Optional[str] = Query(None),
    source_url: Optional[str] = Query(None),
    bmf_version: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Upload a blank BMF PDF form template via multipart form.

    curl -X POST /admin/tax-form-templates/upload \\
      -F "file=@E1_2025.pdf" \\
      -G -d "tax_year=2025&form_type=E1&field_mapping_json={\"245\":\"Kz245\"}"

    If a template for the same year+type already exists, it is replaced.
    """
    from app.models.tax_form_template import TaxFormTemplate, TaxFormType
    import json as json_lib

    # Validate form_type
    try:
        ft_enum = TaxFormType(form_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid form_type: {form_type}. Valid: {[t.value for t in TaxFormType]}"
        )

    # Validate PDF magic bytes
    if not file[:5] == b"%PDF-":
        raise HTTPException(status_code=400, detail="File is not a valid PDF")

    # Parse field_mapping
    try:
        mapping = json_lib.loads(field_mapping_json)
        if not isinstance(mapping, dict):
            raise ValueError("Must be a JSON object")
    except (json_lib.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid field_mapping_json: {e}")

    # Upsert: replace if exists
    existing = db.query(TaxFormTemplate).filter(
        TaxFormTemplate.tax_year == tax_year,
        TaxFormTemplate.form_type == ft_enum,
    ).first()

    if existing:
        existing.pdf_template = file
        existing.field_mapping = mapping
        existing.display_name = display_name or existing.display_name
        existing.source_url = source_url or existing.source_url
        existing.bmf_version = bmf_version or existing.bmf_version
        existing.file_size_bytes = len(file)
        existing.original_filename = f"{form_type}_{tax_year}.pdf"
        template = existing
    else:
        template = TaxFormTemplate(
            tax_year=tax_year,
            form_type=ft_enum,
            display_name=display_name or f"{form_type} {tax_year}",
            pdf_template=file,
            field_mapping=mapping,
            original_filename=f"{form_type}_{tax_year}.pdf",
            file_size_bytes=len(file),
            source_url=source_url,
            bmf_version=bmf_version,
        )
        db.add(template)

    db.commit()
    db.refresh(template)

    return {
        "id": template.id,
        "tax_year": template.tax_year,
        "form_type": template.form_type.value,
        "display_name": template.display_name,
        "file_size_bytes": template.file_size_bytes,
        "field_count": len(mapping),
        "action": "replaced" if existing else "created",
    }


@router.put("/tax-form-templates/{template_id}/field-mapping")
async def update_field_mapping(
    template_id: int,
    mapping: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Update the field_mapping for an existing template.

    Body: JSON object mapping KZ numbers to PDF AcroForm field names.
    Example: {"245": "Kz245", "220": "FamBon_Voll", "_user_name": "Zuname_Vorname"}
    """
    from app.models.tax_form_template import TaxFormTemplate

    template = db.query(TaxFormTemplate).filter(TaxFormTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.field_mapping = mapping
    db.commit()

    return {
        "id": template.id,
        "form_type": template.form_type.value,
        "tax_year": template.tax_year,
        "field_count": len(mapping),
    }


@router.delete("/tax-form-templates/{template_id}")
async def delete_tax_form_template(
    template_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Delete a tax form template."""
    from app.models.tax_form_template import TaxFormTemplate

    template = db.query(TaxFormTemplate).filter(TaxFormTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(template)
    db.commit()
    return {"detail": f"Template {template.form_type.value} {template.tax_year} deleted"}


# ---------------------------------------------------------------------------
# ⑥ OCR extraction accuracy statistics
# ---------------------------------------------------------------------------

@router.get("/ocr-accuracy")
def get_ocr_accuracy(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Return per-field OCR extraction accuracy statistics.

    Scans all documents with learning_data (user corrections) and computes
    accuracy per (document_type, field). Low-accuracy fields (< 80% with
    >= 5 samples) are flagged.
    """
    from app.services.classification_learning import ClassificationLearningService

    service = ClassificationLearningService(db)
    return service.get_extraction_accuracy()


# ---------------------------------------------------------------------------
# ⑦ Knowledge base management
# ---------------------------------------------------------------------------

@router.post("/knowledge/scan")
def scan_knowledge_updates(
    admin: User = Depends(get_current_admin),
):
    """
    Manually trigger a scan of the knowledge_updates/ directory.

    Processes new or changed .md/.json/.txt files, chunks them, and
    upserts into the ChromaDB admin_knowledge_updates collection.
    Returns a summary of new/updated files and total chunks ingested.
    """
    from app.tasks.knowledge_update_tasks import scan_and_ingest

    result = scan_and_ingest()
    return result


@router.get("/knowledge/manifest")
def get_knowledge_manifest(
    admin: User = Depends(get_current_admin),
):
    """
    Return the manifest of already-ingested knowledge update files.

    Each entry shows the filename, MD5 hash, ingestion timestamp,
    and number of chunks.
    """
    from app.tasks.knowledge_update_tasks import _load_manifest, _DEFAULT_UPDATES_DIR

    manifest = _load_manifest(_DEFAULT_UPDATES_DIR)
    return {
        "last_scan": manifest.get("last_scan"),
        "files": manifest.get("ingested_files", {}),
        "total_files": len(manifest.get("ingested_files", {})),
    }


# ---------------------------------------------------------------------------
# ⑧ Governance observability metrics
# ---------------------------------------------------------------------------

@router.get("/governance/metrics")
def get_governance_metrics(
    user_id: Optional[int] = Query(None, description="Scope to a specific user"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Unified governance metrics report.

    Returns rule system metrics (soft/strict hit rates, frozen count),
    training data source distribution, and soft→strict upgrade count.
    """
    from app.services.governance_metrics import GovernanceMetricsService

    svc = GovernanceMetricsService(db)
    return svc.get_full_report(user_id=user_id)


@router.get("/governance/training-audit")
def get_training_audit(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Training data audit report.

    Shows correction source distribution, trainable vs excluded counts,
    and whether the system has enough clean samples for retraining.
    """
    from app.services.classification_learning import ClassificationLearningService

    svc = ClassificationLearningService(db)
    return svc.get_training_audit_report()


@router.post("/governance/decay-rules")
def trigger_rule_decay(
    user_id: int = Query(..., description="User whose soft rules to decay"),
    stale_days: int = Query(90, description="Days without a hit before decay"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Manually trigger confidence decay on stale soft rules for a user.

    Soft rules not hit in `stale_days` lose 0.10 confidence (floor 0.50).
    """
    from app.services.user_classification_service import UserClassificationService

    svc = UserClassificationService(db)
    count = svc.decay_stale_soft_rules(user_id=user_id, stale_days=stale_days)
    db.commit()
    return {"decayed_count": count, "user_id": user_id, "stale_days": stale_days}


@router.post("/governance/archive-rules")
def trigger_rule_archive(
    user_id: int = Query(..., description="User whose low-hit rules to archive"),
    min_hits: int = Query(1, description="Max hit count to consider for archival"),
    stale_days: int = Query(180, description="Days without a hit before archival"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Manually archive (delete) low-hit stale rules for a user.

    Rules with <= min_hits and no hit in stale_days are removed.
    """
    from app.services.user_classification_service import UserClassificationService

    svc = UserClassificationService(db)
    count = svc.archive_low_hit_rules(user_id=user_id, min_hits=min_hits, stale_days=stale_days)
    db.commit()
    return {"archived_count": count, "user_id": user_id, "min_hits": min_hits, "stale_days": stale_days}
