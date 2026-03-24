"""Stripe webhook endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.stripe_payment_service import StripePaymentService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db)
):
    """
    Handle Stripe webhook events.
    
    Per Requirement 4.3: Verify webhook signature before processing.
    Per Requirement 4.4: Handle checkout.session.completed.
    Per Requirement 4.5: Handle invoice.payment_succeeded and invoice.payment_failed.
    Per Requirement 4.6: Handle customer.subscription.updated and deleted.
    
    Supported events:
    - checkout.session.completed: Activate subscription
    - invoice.payment_succeeded: Confirm payment
    - invoice.payment_failed: Mark past_due with 7-day grace period
    - customer.subscription.updated: Sync subscription changes
    - customer.subscription.deleted: Downgrade to Free tier
    """
    if not stripe_signature:
        logger.error("Missing Stripe signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature"
        )
    
    stripe_service = StripePaymentService(db)
    
    try:
        # Get raw request body
        payload = await request.body()
        
        # Handle webhook with signature verification
        result = stripe_service.handle_webhook_event(payload, stripe_signature)
        
        logger.info(f"Webhook processed: {result}")
        
        return {
            "status": "success",
            "result": result
        }
        
    except ValueError as e:
        logger.error(f"Webhook validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Webhook processing error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="payment_processing_error"
        )
