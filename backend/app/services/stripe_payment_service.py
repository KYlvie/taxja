"""Stripe payment service for subscriptions, portal access, and overage invoicing."""
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import logging
import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType, BillingCycle
from app.models.payment_event import PaymentEvent
from app.models.user import User

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

# Map (plan_type, billing_cycle) → Stripe Price ID
PRICE_MAP: Dict[tuple, str] = {
    ("plus", "monthly"): settings.STRIPE_PLUS_MONTHLY_PRICE_ID,
    ("plus", "yearly"): settings.STRIPE_PLUS_YEARLY_PRICE_ID,
    ("pro", "monthly"): settings.STRIPE_PRO_MONTHLY_PRICE_ID,
    ("pro", "yearly"): settings.STRIPE_PRO_YEARLY_PRICE_ID,
}
REVERSE_PRICE_MAP: Dict[str, Tuple[str, str]] = {
    price_id: plan_details
    for plan_details, price_id in PRICE_MAP.items()
    if price_id
}


class StripePaymentService:
    """Stripe integration using Checkout Sessions, Customer Portal, and invoices."""

    def __init__(self, db: Session):
        self.db = db

    # ── Checkout Session ──────────────────────────────────────────────
    def create_checkout_session(
        self,
        user_id: int,
        plan_id: int,
        billing_cycle: BillingCycle,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, str]:
        """Create a Stripe Checkout Session for a subscription."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        plan = self.db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        price_id = PRICE_MAP.get((plan.plan_type.value, billing_cycle.value))
        if not price_id:
            raise ValueError(
                f"No Stripe price configured for {plan.plan_type.value}/{billing_cycle.value}"
            )

        customer_id = self._get_or_create_customer(user)

        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user_id),
                    "plan_id": str(plan_id),
                    "billing_cycle": billing_cycle.value,
                },
            )
            logger.info(f"Checkout session created for user {user_id}: {session.id}")
            return {"session_id": session.id, "url": session.url}
        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout error: {e}")
            raise ValueError(f"Payment error: {str(e)}")

    # ── Customer Portal ───────────────────────────────────────────────
    def create_customer_portal_session(
        self, user_id: int, return_url: str
    ) -> Dict[str, str]:
        """Create a Stripe Customer Portal session for managing subscription."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        subscription = (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .first()
        )
        if not subscription or not subscription.stripe_customer_id:
            raise ValueError("No Stripe customer found for this user")

        try:
            session = stripe.billing_portal.Session.create(
                customer=subscription.stripe_customer_id,
                return_url=return_url,
            )
            return {"url": session.url}
        except stripe.error.StripeError as e:
            logger.error(f"Portal session error: {e}")
            raise ValueError(f"Portal error: {str(e)}")

    def create_overage_invoice(
        self,
        user_id: int,
        overage_amount: Decimal,
        overage_credits_used: int,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Create a one-off Stripe invoice for overage settlement."""
        if not settings.STRIPE_SECRET_KEY or "your_" in settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe is not configured")

        if overage_amount <= Decimal("0"):
            raise ValueError("Overage amount must be greater than zero")

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        subscription = self._get_subscription(user_id)
        if not subscription:
            raise ValueError(f"No subscription found for user {user_id}")
        if not subscription.stripe_customer_id:
            raise ValueError(f"No Stripe customer found for user {user_id}")

        amount_decimal = overage_amount.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        amount_cents = int(
            (amount_decimal * 100).to_integral_value(rounding=ROUND_HALF_UP)
        )
        if amount_cents <= 0:
            raise ValueError("Overage amount rounds to zero cents")

        metadata = {
            "type": "overage_settlement",
            "user_id": str(user_id),
            "overage_credits": str(overage_credits_used),
            "overage_amount": str(amount_decimal),
        }
        if period_start is not None:
            metadata["period_start"] = period_start.isoformat()
        if period_end is not None:
            metadata["period_end"] = period_end.isoformat()

        description = self._build_overage_description(
            overage_credits_used=overage_credits_used,
            period_start=period_start,
            period_end=period_end,
        )

        invoice_params: Dict[str, Any] = {
            "customer": subscription.stripe_customer_id,
            "collection_method": "charge_automatically",
            "auto_advance": False,
            "description": description,
            "metadata": metadata,
        }
        if subscription.stripe_subscription_id:
            invoice_params["subscription"] = subscription.stripe_subscription_id

        try:
            invoice = stripe.Invoice.create(**invoice_params)

            item_params: Dict[str, Any] = {
                "customer": subscription.stripe_customer_id,
                "invoice": invoice.id,
                "description": description,
                "quantity": 1,
                "metadata": metadata,
            }
            if (
                period_start is not None
                and period_end is not None
                and period_end >= period_start
            ):
                item_params["period"] = {
                    "start": int(period_start.timestamp()),
                    "end": int(period_end.timestamp()),
                }

            if settings.STRIPE_OVERAGE_PRODUCT_ID:
                item_params["price_data"] = {
                    "currency": "eur",
                    "product": settings.STRIPE_OVERAGE_PRODUCT_ID,
                    "unit_amount": amount_cents,
                }
            else:
                item_params["amount"] = amount_cents
                item_params["currency"] = "eur"

            stripe.InvoiceItem.create(**item_params)
            finalized_invoice = stripe.Invoice.finalize_invoice(
                invoice.id,
                auto_advance=True,
            )
        except stripe.error.StripeError as e:
            logger.error("Stripe overage invoice error for user %s: %s", user_id, e)
            raise ValueError(f"Failed to create overage invoice: {str(e)}")

        logger.info(
            "Created Stripe overage invoice %s for user %s (%s credits, %s)",
            finalized_invoice.id,
            user_id,
            overage_credits_used,
            amount_decimal,
        )
        return {
            "invoice_id": finalized_invoice.id,
            "status": getattr(finalized_invoice, "status", None),
            "amount": amount_decimal,
        }

    # ── Customer helper ───────────────────────────────────────────────
    def _get_or_create_customer(self, user: User) -> str:
        subscription = self._get_subscription(user.id)
        if subscription and subscription.stripe_customer_id:
            return subscription.stripe_customer_id

        try:
            customer = stripe.Customer.create(
                email=user.email,
                metadata={"user_id": str(user.id)},
            )
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            return customer.id
        except stripe.error.StripeError as e:
            raise ValueError(f"Failed to create customer: {str(e)}")

    def _get_subscription(self, user_id: int) -> Optional[Subscription]:
        return (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .first()
        )

    def cancel_subscription(self, stripe_subscription_id: str) -> Any:
        """Schedule Stripe subscription cancellation at period end."""
        try:
            return stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=True,
            )
        except stripe.error.StripeError as e:
            logger.error("Stripe cancel subscription error for %s: %s", stripe_subscription_id, e)
            raise ValueError(f"Failed to cancel subscription: {str(e)}")

    def reactivate_subscription(self, stripe_subscription_id: str) -> Any:
        """Reactivate a Stripe subscription scheduled for cancellation."""
        try:
            return stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=False,
            )
        except stripe.error.StripeError as e:
            logger.error("Stripe reactivate subscription error for %s: %s", stripe_subscription_id, e)
            raise ValueError(f"Failed to reactivate subscription: {str(e)}")

    def schedule_subscription_cancellation(self, user_id: int) -> Subscription:
        """Cancel a Stripe-backed subscription at period end and sync local state."""
        subscription = self._get_subscription(user_id)
        if not subscription:
            raise ValueError(f"No subscription found for user {user_id}")
        if not subscription.stripe_subscription_id:
            raise ValueError("No Stripe subscription found for this user")

        stripe_sub = self.cancel_subscription(subscription.stripe_subscription_id)
        return self._sync_local_subscription_from_stripe(
            stripe_sub,
            user_id=user_id,
            local_subscription=subscription,
        )

    def resume_scheduled_cancellation(self, user_id: int) -> Subscription:
        """Undo a scheduled Stripe cancellation and sync local state."""
        subscription = self._get_subscription(user_id)
        if not subscription:
            raise ValueError(f"No subscription found for user {user_id}")
        if not subscription.stripe_subscription_id:
            raise ValueError("No Stripe subscription found for this user")

        stripe_sub = self.reactivate_subscription(subscription.stripe_subscription_id)
        return self._sync_local_subscription_from_stripe(
            stripe_sub,
            user_id=user_id,
            local_subscription=subscription,
        )

    def _map_stripe_status(self, stripe_status: Optional[str]) -> SubscriptionStatus:
        if stripe_status == "trialing":
            return SubscriptionStatus.TRIALING
        if stripe_status in {"past_due", "unpaid"}:
            return SubscriptionStatus.PAST_DUE
        if stripe_status in {"canceled", "incomplete_expired"}:
            return SubscriptionStatus.CANCELED
        return SubscriptionStatus.ACTIVE

    def _resolve_plan_and_cycle(
        self,
        stripe_sub: Dict[str, Any],
        fallback_plan_id: Optional[int] = None,
        fallback_billing_cycle: Optional[BillingCycle] = None,
    ) -> Tuple[Optional[Plan], Optional[BillingCycle]]:
        items = stripe_sub.get("items", {}).get("data", [])
        price_id: Optional[str] = None
        if items:
            price_id = items[0].get("price", {}).get("id")

        if price_id and price_id in REVERSE_PRICE_MAP:
            plan_type_value, billing_cycle_value = REVERSE_PRICE_MAP[price_id]
            plan = self.db.query(Plan).filter(
                Plan.plan_type == PlanType(plan_type_value)
            ).first()
            return plan, BillingCycle(billing_cycle_value)

        plan = None
        if fallback_plan_id is not None:
            plan = self.db.query(Plan).filter(Plan.id == fallback_plan_id).first()
        return plan, fallback_billing_cycle

    def _sync_local_subscription_from_stripe(
        self,
        stripe_sub: Dict[str, Any],
        user_id: Optional[int] = None,
        fallback_plan_id: Optional[int] = None,
        fallback_billing_cycle: Optional[BillingCycle] = None,
        local_subscription: Optional[Subscription] = None,
    ) -> Subscription:
        from app.services.feature_gate_service import FeatureGateService
        from app.services.subscription_service import SubscriptionService

        subscription_id = stripe_sub["id"]
        customer_id = stripe_sub.get("customer")

        subscription = local_subscription or (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == subscription_id)
            .first()
        )

        if not subscription and customer_id:
            subscription = (
                self.db.query(Subscription)
                .filter(Subscription.stripe_customer_id == customer_id)
                .order_by(Subscription.created_at.desc())
                .first()
            )

        if not subscription and user_id is not None:
            subscription = SubscriptionService(self.db).get_user_subscription(user_id)

        if not subscription and user_id is None:
            raise ValueError(f"No local subscription found for Stripe subscription {subscription_id}")

        plan, billing_cycle = self._resolve_plan_and_cycle(
            stripe_sub,
            fallback_plan_id=fallback_plan_id,
            fallback_billing_cycle=fallback_billing_cycle,
        )
        if not plan:
            raise ValueError(f"Unable to resolve local plan for Stripe subscription {subscription_id}")

        period_start_ts = stripe_sub.get("current_period_start")
        period_end_ts = stripe_sub.get("current_period_end")
        status = self._map_stripe_status(stripe_sub.get("status"))

        if subscription:
            subscription.plan_id = plan.id
            subscription.billing_cycle = billing_cycle
            subscription.status = status
            subscription.stripe_subscription_id = subscription_id
            subscription.stripe_customer_id = customer_id
            subscription.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
            if period_start_ts:
                subscription.current_period_start = datetime.fromtimestamp(period_start_ts)
            if period_end_ts:
                subscription.current_period_end = datetime.fromtimestamp(period_end_ts)
            self.db.commit()
            self.db.refresh(subscription)
        else:
            created = SubscriptionService(self.db).create_subscription(
                user_id=user_id,
                plan_id=plan.id,
                billing_cycle=billing_cycle,
                stripe_subscription_id=subscription_id,
                stripe_customer_id=customer_id,
                status=status,
                current_period_start=datetime.fromtimestamp(period_start_ts) if period_start_ts else None,
                current_period_end=datetime.fromtimestamp(period_end_ts) if period_end_ts else None,
            )
            subscription = created
            subscription.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
            self.db.commit()
            self.db.refresh(subscription)

        FeatureGateService(self.db).invalidate_user_plan_cache(subscription.user_id)
        return subscription

    def _build_overage_description(
        self,
        overage_credits_used: int,
        period_start: Optional[datetime],
        period_end: Optional[datetime],
    ) -> str:
        if period_start is not None and period_end is not None:
            return (
                "Taxja overage settlement "
                f"({period_start.date().isoformat()} to {period_end.date().isoformat()}, "
                f"{overage_credits_used} credits)"
            )
        return f"Taxja overage settlement ({overage_credits_used} credits)"

    # ── Webhook handling ──────────────────────────────────────────────
    def handle_webhook_event(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Verify and process a Stripe webhook event."""
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        if not webhook_secret or "your_" in webhook_secret:
            logger.error("Stripe webhook secret not configured")
            raise ValueError("Webhook secret not configured")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError:
            raise ValueError("Invalid webhook signature")

        logger.info(f"Webhook received: {event['type']}")

        # Idempotency check
        if PaymentEvent.is_duplicate(self.db, event["id"]):
            return {"status": "duplicate", "event_id": event["id"]}

        self._log_payment_event(event)
        return self._process_event(event)

    def _process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        handlers = {
            "checkout.session.completed": self._on_checkout_completed,
            "invoice.payment_succeeded": self._on_payment_succeeded,
            "invoice.paid": self._on_payment_succeeded,
            "invoice.payment_failed": self._on_payment_failed,
            "customer.subscription.updated": self._on_subscription_updated,
            "customer.subscription.deleted": self._on_subscription_deleted,
        }
        handler = handlers.get(event["type"])
        if handler:
            return handler(event)
        return {"status": "unhandled", "event_type": event["type"]}

    def _grant_initial_paid_plan_allowance(
        self,
        user_id: int,
        previous_plan_type: Optional[PlanType],
        subscription: Subscription,
    ) -> None:
        if subscription.plan is None:
            return

        new_plan_type = subscription.plan.plan_type
        if new_plan_type == PlanType.FREE:
            return

        if previous_plan_type not in {None, PlanType.FREE}:
            return

        from app.services.credit_service import CreditService

        CreditService(self.db).grant_plan_allowance_for_activation(
            user_id=user_id,
            reason=f"subscription_activation:{previous_plan_type or 'none'}->{new_plan_type.value}",
        )

    def _activate_subscription_from_checkout_session(
        self,
        session: Dict[str, Any],
        expected_user_id: Optional[int] = None,
    ) -> Subscription:
        metadata = session.get("metadata", {}) or {}
        user_id = int(metadata.get("user_id", 0))
        plan_id = int(metadata.get("plan_id", 0))
        billing_cycle_str = metadata.get("billing_cycle", "monthly")
        stripe_subscription_id = session.get("subscription")
        stripe_customer_id = session.get("customer")

        if not user_id or not plan_id:
            raise ValueError("Missing checkout metadata")

        if expected_user_id is not None and user_id != expected_user_id:
            raise ValueError("Checkout session does not belong to the current user")

        billing_cycle = (
            BillingCycle.YEARLY if billing_cycle_str == "yearly" else BillingCycle.MONTHLY
        )

        previous_subscription = self._get_subscription(user_id)
        previous_plan_type = (
            previous_subscription.plan.plan_type
            if previous_subscription and previous_subscription.plan
            else None
        )

        if not stripe_subscription_id:
            raise ValueError("Completed checkout session has no subscription reference")

        try:
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
            subscription = self._sync_local_subscription_from_stripe(
                stripe_sub,
                user_id=user_id,
                fallback_plan_id=plan_id,
                fallback_billing_cycle=billing_cycle,
            )
        except stripe.error.StripeError as e:
            logger.warning(
                "Failed to retrieve Stripe subscription %s after checkout; falling back to checkout metadata: %s",
                stripe_subscription_id,
                e,
            )
            subscription = self._sync_local_subscription_from_stripe(
                {
                    "id": stripe_subscription_id,
                    "customer": stripe_customer_id,
                    "status": "active",
                    "cancel_at_period_end": False,
                    "current_period_start": int(datetime.utcnow().timestamp()),
                    "current_period_end": None,
                    "items": {"data": []},
                },
                user_id=user_id,
                fallback_plan_id=plan_id,
                fallback_billing_cycle=billing_cycle,
            )

        self._grant_initial_paid_plan_allowance(
            user_id=user_id,
            previous_plan_type=previous_plan_type,
            subscription=subscription,
        )
        return subscription

    def sync_checkout_session(self, session_id: str, user_id: int) -> Subscription:
        """Actively reconcile a completed Stripe Checkout session."""
        if not session_id:
            raise ValueError("Missing checkout session id")

        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as e:
            logger.error("Stripe checkout session retrieval error for %s: %s", session_id, e)
            raise ValueError(f"Failed to retrieve checkout session: {str(e)}")

        if session.get("mode") != "subscription":
            raise ValueError("Checkout session is not a subscription checkout")

        if session.get("status") != "complete":
            raise ValueError("Checkout session is not complete yet")

        payment_status = session.get("payment_status")
        if payment_status not in {None, "paid", "no_payment_required"}:
            raise ValueError("Checkout session payment is not completed")

        return self._activate_subscription_from_checkout_session(
            session=session,
            expected_user_id=user_id,
        )

    # ── Webhook handlers ──────────────────────────────────────────────
    def _on_checkout_completed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Activate subscription after successful checkout."""
        session = event["data"]["object"]
        user_id = int((session.get("metadata") or {}).get("user_id", 0))
        plan_id = int((session.get("metadata") or {}).get("plan_id", 0))

        if not user_id or not plan_id:
            logger.error(f"Missing metadata in checkout session: {session['id']}")
            return {"status": "error", "reason": "missing_metadata"}

        try:
            self._activate_subscription_from_checkout_session(session)
        except ValueError as e:
            logger.error("Checkout completion processing failed for %s: %s", session.get("id"), e)
            return {"status": "error", "reason": str(e)}

        logger.info(f"Checkout completed: user {user_id} → plan {plan_id}")
        return {"status": "processed", "action": "subscription_activated"}

    def _on_payment_succeeded(self, event: Dict[str, Any]) -> Dict[str, Any]:
        invoice = event["data"]["object"]
        metadata = invoice.get("metadata", {})
        if metadata.get("type") == "overage_settlement":
            from app.tasks.credit_tasks import handle_overage_invoice_paid

            result = handle_overage_invoice_paid(self.db, invoice)
            self.db.commit()
            result.setdefault("action", "overage_payment_confirmed")
            return result

        sub_id = invoice.get("subscription")
        sub = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == sub_id)
            .first()
        )
        if sub and sub.status == SubscriptionStatus.PAST_DUE:
            sub.status = SubscriptionStatus.ACTIVE
            self.db.commit()
        return {"status": "processed", "action": "payment_confirmed"}

    def _on_payment_failed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        invoice = event["data"]["object"]
        metadata = invoice.get("metadata", {})
        if metadata.get("type") == "overage_settlement":
            from app.tasks.credit_tasks import handle_overage_invoice_failed

            result = handle_overage_invoice_failed(self.db, invoice)
            self.db.commit()
            result.setdefault("action", "overage_payment_failed")
            return result

        sub_id = invoice.get("subscription")
        sub = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == sub_id)
            .first()
        )
        if sub:
            sub.status = SubscriptionStatus.PAST_DUE
            self.db.commit()
        return {"status": "processed", "action": "payment_failed_grace_period"}

    def _on_subscription_updated(self, event: Dict[str, Any]) -> Dict[str, Any]:
        stripe_sub = event["data"]["object"]
        self._sync_local_subscription_from_stripe(stripe_sub)
        return {"status": "processed", "action": "subscription_synced"}

    def _on_subscription_deleted(self, event: Dict[str, Any]) -> Dict[str, Any]:
        stripe_sub = event["data"]["object"]
        sub = (
            self.db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub["id"])
            .first()
        )
        if sub:
            from app.services.feature_gate_service import FeatureGateService

            free_plan = self.db.query(Plan).filter(Plan.plan_type == PlanType.FREE).first()
            if free_plan:
                sub.plan_id = free_plan.id
            sub.status = SubscriptionStatus.CANCELED
            sub.billing_cycle = None
            sub.cancel_at_period_end = False
            sub.stripe_subscription_id = None
            self.db.commit()
            FeatureGateService(self.db).invalidate_user_plan_cache(sub.user_id)
        return {"status": "processed", "action": "downgraded_to_free"}

    def _log_payment_event(self, event: Dict[str, Any]) -> None:
        try:
            pe = PaymentEvent(
                stripe_event_id=event["id"],
                event_type=event["type"],
                payload=event,
                user_id=None,
            )
            self.db.add(pe)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log payment event: {e}")
            self.db.rollback()
