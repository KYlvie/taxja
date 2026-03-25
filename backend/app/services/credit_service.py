"""CreditService — core credit management service for the Credit-Based Billing system (v1).

Handles balance queries, deductions, refunds, top-up, overage, monthly resets,
and ledger audit logging.  Redis caching is optional (graceful fallback to DB).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import redis
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.credit_ledger import CreditLedger, CreditOperation, CreditSource, CreditLedgerStatus
from app.models.plan import PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.topup_purchase import TopupPurchase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class InsufficientCreditsError(Exception):
    """Raised when user has insufficient credits and overage is not enabled."""

    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient credits: required {required}, available {available}"
        )


class OverageNotAvailableError(Exception):
    """Raised when a Free-plan user attempts to enable overage."""
    pass


class OverageSuspendedError(Exception):
    """Raised when overage is suspended due to ≥2 consecutive unpaid periods."""
    pass


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CreditBalanceInfo:
    plan_balance: int
    topup_balance: int
    total_balance: int  # plan + topup
    available_without_overage: int  # plan + topup (same as total_balance for v1)
    monthly_credits: int
    overage_enabled: bool
    overage_credits_used: int
    overage_price_per_credit: Optional[Decimal]
    estimated_overage_cost: Decimal
    has_unpaid_overage: bool
    reset_date: Optional[datetime]


@dataclass
class CreditDeductionResult:
    success: bool
    plan_deducted: int
    topup_deducted: int
    overage_portion: int
    total_deducted: int
    balance_after: CreditBalanceInfo


@dataclass
class PeriodEndResult:
    overage_settled: bool
    overage_amount: Optional[Decimal]
    stripe_invoice_id: Optional[str]
    topup_expired: int
    new_plan_balance: int


@dataclass
class CreditEstimateResult:
    operation: str
    cost: int
    sufficient: bool
    sufficient_without_overage: bool
    would_use_overage: bool


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_KEY_PREFIX = "credit_balance:"
CACHE_TTL_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# CreditService
# ---------------------------------------------------------------------------

class CreditService:
    """Core credit management service.

    Parameters
    ----------
    db : Session
        SQLAlchemy database session.
    redis_client : redis.Redis | None
        Optional Redis client for caching.  When *None* or unavailable the
        service falls back to DB-only mode transparently.
    """

    def __init__(self, db: Session, redis_client: Optional[redis.Redis] = None):
        self.db = db
        self.redis_client = redis_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_balance(self, user_id: int) -> CreditBalanceInfo:
        """Return the user's current credit balance information.

        1. Try Redis cache first (key ``credit_balance:{user_id}``, TTL 5 min).
        2. On cache miss, load from DB.
        3. If no ``CreditBalance`` record exists, auto-create a default one
           (plan_balance = monthly_credits from the user's plan, topup_balance = 0).
        4. Build and return a ``CreditBalanceInfo`` dataclass.
        5. Cache the result in Redis.
        """

        # 1. Try cache
        cached = self._cache_get(user_id)
        if cached is not None:
            return cached

        # 2. Load from DB (or auto-create)
        credit_balance = self._get_or_create_balance(user_id)

        # 3. Gather plan info via subscription
        monthly_credits, overage_price = self._get_plan_credit_info(user_id)

        # 4. Determine reset date from subscription
        reset_date = self._get_reset_date(user_id)

        # 5. Build info dataclass
        estimated_overage_cost = Decimal(0)
        if overage_price is not None and credit_balance.overage_credits_used > 0:
            estimated_overage_cost = overage_price * credit_balance.overage_credits_used

        info = CreditBalanceInfo(
            plan_balance=credit_balance.plan_balance,
            topup_balance=credit_balance.topup_balance,
            total_balance=credit_balance.plan_balance + credit_balance.topup_balance,
            available_without_overage=credit_balance.plan_balance + credit_balance.topup_balance,
            monthly_credits=monthly_credits,
            overage_enabled=credit_balance.overage_enabled,
            overage_credits_used=credit_balance.overage_credits_used,
            overage_price_per_credit=overage_price,
            estimated_overage_cost=estimated_overage_cost,
            has_unpaid_overage=credit_balance.has_unpaid_overage,
            reset_date=reset_date,
        )

        # 6. Cache
        self._cache_set(user_id, info)

        return info

    def check_and_deduct(
        self,
        user_id: int,
        operation: str,
        quantity: int = 1,
        context_type: Optional[str] = None,
        context_id: Optional[int] = None,
    ) -> CreditDeductionResult:
        """Deduct credits for an operation.

        Deduction order: plan_balance → topup_balance → overage.
        Uses atomic UPDATE for the fast path (plan_balance sufficient),
        SELECT FOR UPDATE for the slow path (cross-balance allocation).

        Raises
        ------
        ValueError
            If the operation has no active CreditCostConfig entry.
        InsufficientCreditsError
            If balance is insufficient and overage is not enabled.
        """

        # 1. Look up operation cost
        cost_config = (
            self.db.query(CreditCostConfig)
            .filter(
                CreditCostConfig.operation == operation,
                CreditCostConfig.is_active == True,
            )
            .first()
        )
        if cost_config is None:
            raise ValueError(f"No active CreditCostConfig for operation: {operation}")

        total_cost = cost_config.credit_cost * quantity
        pricing_version = cost_config.pricing_version

        # 2. Idempotency check: if a settled DEDUCTION already exists for this context, skip
        if self.has_settled_charge_for_context(user_id, operation, context_type, context_id):
            # Return current balance without double-charging
            balance_info = self.get_balance(user_id)
            return CreditDeductionResult(
                success=True,
                plan_deducted=0,
                topup_deducted=0,
                overage_portion=0,
                total_deducted=0,
                balance_after=balance_info,
            )

        # Ensure balance record exists
        self._get_or_create_balance(user_id)

        # 3. Fast path: plan_balance sufficient → atomic UPDATE
        stmt = (
            update(CreditBalance)
            .where(
                CreditBalance.user_id == user_id,
                CreditBalance.plan_balance >= total_cost,
            )
            .values(plan_balance=CreditBalance.plan_balance - total_cost)
        )
        result = self.db.execute(stmt)

        if result.rowcount == 1:
            # Fast path succeeded — read updated balance for ledger
            balance = (
                self.db.query(CreditBalance)
                .filter(CreditBalance.user_id == user_id)
                .first()
            )
            # Write ledger
            ledger = CreditLedger(
                user_id=user_id,
                operation=CreditOperation.DEDUCTION,
                operation_detail=operation,
                status=CreditLedgerStatus.SETTLED,
                credit_amount=-total_cost,
                source=CreditSource.PLAN,
                plan_balance_after=balance.plan_balance,
                topup_balance_after=balance.topup_balance,
                is_overage=False,
                overage_portion=0,
                context_type=context_type,
                context_id=context_id,
                pricing_version=pricing_version,
            )
            self.db.add(ledger)
            self.db.flush()

            # Delete Redis cache
            self._cache_delete(user_id)

            balance_info = self._build_balance_info(balance, user_id)
            return CreditDeductionResult(
                success=True,
                plan_deducted=total_cost,
                topup_deducted=0,
                overage_portion=0,
                total_deducted=total_cost,
                balance_after=balance_info,
            )

        # 4. Slow path: plan_balance insufficient → lock row and compute cross-balance
        balance = (
            self.db.query(CreditBalance)
            .filter(CreditBalance.user_id == user_id)
            .with_for_update()
            .first()
        )

        plan_deducted = min(balance.plan_balance, total_cost)
        remaining = total_cost - plan_deducted

        topup_deducted = 0
        if remaining > 0:
            topup_deducted = min(balance.topup_balance, remaining)
            if topup_deducted > 0:
                # FIFO consumption from TopupPurchase records
                actual_consumed = self._consume_topup_fifo(user_id, topup_deducted)
                topup_deducted = actual_consumed
            remaining = remaining - topup_deducted

        overage_portion = 0
        if remaining > 0:
            if balance.overage_enabled:
                overage_portion = remaining
                remaining = 0
            else:
                raise InsufficientCreditsError(
                    required=total_cost,
                    available=balance.plan_balance + balance.topup_balance,
                )

        # 5. Update CreditBalance
        balance.plan_balance -= plan_deducted
        balance.topup_balance -= topup_deducted
        balance.overage_credits_used += overage_portion

        # 6. Determine source
        sources_used = []
        if plan_deducted > 0:
            sources_used.append("plan")
        if topup_deducted > 0:
            sources_used.append("topup")
        if overage_portion > 0:
            sources_used.append("overage")

        if len(sources_used) > 1:
            source = CreditSource.MIXED
        elif "plan" in sources_used:
            source = CreditSource.PLAN
        elif "topup" in sources_used:
            source = CreditSource.TOPUP
        elif "overage" in sources_used:
            source = CreditSource.OVERAGE
        else:
            source = CreditSource.PLAN  # fallback (shouldn't happen)

        # Write ledger
        ledger = CreditLedger(
            user_id=user_id,
            operation=CreditOperation.DEDUCTION,
            operation_detail=operation,
            status=CreditLedgerStatus.SETTLED,
            credit_amount=-total_cost,
            source=source,
            plan_balance_after=balance.plan_balance,
            topup_balance_after=balance.topup_balance,
            is_overage=overage_portion > 0,
            overage_portion=overage_portion,
            context_type=context_type,
            context_id=context_id,
            pricing_version=pricing_version,
        )
        self.db.add(ledger)
        self.db.flush()

        # 7. Delete Redis cache
        self._cache_delete(user_id)

        balance_info = self._build_balance_info(balance, user_id)
        return CreditDeductionResult(
            success=True,
            plan_deducted=plan_deducted,
            topup_deducted=topup_deducted,
            overage_portion=overage_portion,
            total_deducted=total_cost,
            balance_after=balance_info,
        )

    def refund_credits(
        self,
        user_id: int,
        operation: str,
        quantity: int = 1,
        reason: str = "processing_failed",
        context_type: Optional[str] = None,
        context_id: Optional[int] = None,
        refund_key: Optional[str] = None,
    ) -> CreditBalanceInfo:
        """Refund credits for a failed operation.

        Refund order (opposite of deduction): overage → topup → plan.
        Writes a REFUND ledger record.

        Idempotency: if *refund_key* is provided and a REFUND ledger with that
        reference_id already exists, returns the current balance without
        double-refunding.
        """

        # 1. Look up operation cost
        cost_config = (
            self.db.query(CreditCostConfig)
            .filter(
                CreditCostConfig.operation == operation,
                CreditCostConfig.is_active == True,
            )
            .first()
        )
        if cost_config is None:
            raise ValueError(f"No active CreditCostConfig for operation: {operation}")

        total_refund = cost_config.credit_cost * quantity
        pricing_version = cost_config.pricing_version

        # 2. Idempotency check
        if refund_key is not None and self.has_refund_for_key(user_id, refund_key):
            return self.get_balance(user_id)

        # 3. Lock the balance row
        balance = (
            self.db.query(CreditBalance)
            .filter(CreditBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if balance is None:
            balance = self._get_or_create_balance(user_id)

        remaining = total_refund

        # 4a. Refund overage first
        overage_refund = min(balance.overage_credits_used, remaining)
        balance.overage_credits_used -= overage_refund
        remaining -= overage_refund

        # 4b. Refund topup (reverse FIFO — most recent purchase first)
        topup_refund = 0
        if remaining > 0:
            topup_refund = self._restore_topup_fifo(user_id, remaining)
            balance.topup_balance += topup_refund
            remaining -= topup_refund

        # 4c. Refund plan
        plan_refund = remaining
        balance.plan_balance += plan_refund
        remaining = 0

        # 5. Determine source for ledger
        sources_affected = []
        if overage_refund > 0:
            sources_affected.append("overage")
        if topup_refund > 0:
            sources_affected.append("topup")
        if plan_refund > 0:
            sources_affected.append("plan")

        if len(sources_affected) > 1:
            source = CreditSource.MIXED
        elif "overage" in sources_affected:
            source = CreditSource.OVERAGE
        elif "topup" in sources_affected:
            source = CreditSource.TOPUP
        elif "plan" in sources_affected:
            source = CreditSource.PLAN
        else:
            source = CreditSource.PLAN  # fallback

        # 6. Write REFUND ledger record
        ledger = CreditLedger(
            user_id=user_id,
            operation=CreditOperation.REFUND,
            operation_detail=operation,
            status=CreditLedgerStatus.SETTLED,
            credit_amount=+total_refund,
            source=source,
            plan_balance_after=balance.plan_balance,
            topup_balance_after=balance.topup_balance,
            is_overage=overage_refund > 0,
            overage_portion=overage_refund,
            context_type=context_type,
            context_id=context_id,
            reference_id=refund_key,
            reason=reason,
            pricing_version=pricing_version,
        )
        self.db.add(ledger)
        self.db.flush()

        # 7. Delete Redis cache
        self._cache_delete(user_id)

        return self._build_balance_info(balance, user_id)

    def check_sufficient(
        self,
        user_id: int,
        operation: str,
        quantity: int = 1,
        allow_overage: bool = True,
    ) -> bool:
        """Check whether the user has sufficient credits for an operation.

        This is a **read-only** check — no balance changes, no ledger writes,
        no cache writes.

        Parameters
        ----------
        allow_overage : bool
            * ``True`` (default): plan + topup + overage combined check.
              Returns ``True`` when natural balance covers the cost **or**
              when ``overage_enabled`` is ``True``.
            * ``False``: only check plan + topup natural balance, ignoring
              overage entirely.
        """

        # 1. Look up cost config
        cost_config = (
            self.db.query(CreditCostConfig)
            .filter(
                CreditCostConfig.operation == operation,
                CreditCostConfig.is_active == True,
            )
            .first()
        )
        if cost_config is None:
            return False

        total_cost = cost_config.credit_cost * quantity

        # 2. Get or create balance
        balance = self._get_or_create_balance(user_id)

        natural_balance = balance.plan_balance + balance.topup_balance

        if not allow_overage:
            # Only natural balance counts
            return natural_balance >= total_cost

        # allow_overage=True: sufficient if natural balance covers it OR overage is on
        if natural_balance >= total_cost:
            return True
        return balance.overage_enabled

    def add_topup_credits(
        self,
        user_id: int,
        amount: int,
        stripe_payment_id: str,
    ) -> CreditBalanceInfo:
        """Add top-up credits to a user's balance.

        Creates a TopupPurchase record (expires in 12 months), increments
        topup_balance, writes a TOPUP ledger entry, and invalidates cache.
        """
        from dateutil.relativedelta import relativedelta

        # 1. Get or create the user's CreditBalance
        balance = self._get_or_create_balance(user_id)

        # 2. Create TopupPurchase record
        purchased_at = datetime.utcnow()
        expires_at = purchased_at + relativedelta(months=12)

        purchase = TopupPurchase(
            user_id=user_id,
            credits_purchased=amount,
            credits_remaining=amount,
            price_paid=Decimal("0.00"),
            stripe_payment_id=stripe_payment_id,
            purchased_at=purchased_at,
            expires_at=expires_at,
            is_expired=False,
        )
        self.db.add(purchase)

        # 3. Increment topup_balance
        balance.topup_balance += amount

        # 4. Write TOPUP ledger entry
        ledger = CreditLedger(
            user_id=user_id,
            operation=CreditOperation.TOPUP,
            operation_detail="topup",
            status=CreditLedgerStatus.SETTLED,
            credit_amount=+amount,
            source=CreditSource.TOPUP,
            plan_balance_after=balance.plan_balance,
            topup_balance_after=balance.topup_balance,
            is_overage=False,
            overage_portion=0,
            reference_id=stripe_payment_id,
            reason=f"Top-up purchase: {amount} credits",
            pricing_version=1,
        )
        self.db.add(ledger)

        # 5. Flush DB
        self.db.flush()

        # 6. Delete Redis cache
        self._cache_delete(user_id)

        # 7. Return balance info
        return self._build_balance_info(balance, user_id)

    def set_overage_enabled(self, user_id: int, enabled: bool) -> CreditBalanceInfo:
        """Enable or disable overage for a user.

        Disabling overage (enabled=False) always succeeds regardless of plan
        type or unpaid periods.

        Enabling overage (enabled=True) is subject to:
        - Free plan → OverageNotAvailableError
        - unpaid overage invoice not settled → OverageSuspendedError
        - unpaid_overage_periods >= 2 → OverageSuspendedError

        Raises
        ------
        OverageNotAvailableError
            If the user is on the Free plan and tries to enable overage.
        OverageSuspendedError
            If the user has >= 2 consecutive unpaid overage periods and tries
            to enable overage.
        """

        if enabled:
            # Check plan type — Free plan cannot enable overage
            sub = (
                self.db.query(Subscription)
                .filter(
                    Subscription.user_id == user_id,
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIALING,
                        SubscriptionStatus.PAST_DUE,
                    ]),
                )
                .first()
            )
            if sub is not None and sub.plan is not None and sub.plan.plan_type == PlanType.FREE:
                raise OverageNotAvailableError()

        # Get or create balance
        balance = self._get_or_create_balance(user_id)

        if enabled and (
            balance.has_unpaid_overage or balance.unpaid_overage_periods >= 2
        ):
            raise OverageSuspendedError()

        balance.overage_enabled = enabled
        self.db.flush()

        # Invalidate cache
        self._cache_delete(user_id)

        return self._build_balance_info(balance, user_id)

    def process_period_end(self, user_id: int) -> PeriodEndResult:
        """Monthly period-end processing.

        Executes the following steps in a single DB transaction:
        1. Lock CreditBalance row (FOR UPDATE)
        2. Settle overage fees (create Stripe invoice when available)
        3. Clean up expired topups
        4. Reset plan_balance = monthly_credits
        5. Reset overage_credits_used = 0
        6. Update subscription period dates (+1 month)
        7. Write ledger entries (OVERAGE_SETTLEMENT / TOPUP_EXPIRY / MONTHLY_RESET)
        8. Flush (caller controls commit)
        9. Delete Redis cache (outside transaction)
        """

        # 1. Lock the CreditBalance row
        balance = (
            self.db.query(CreditBalance)
            .filter(CreditBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if balance is None:
            balance = self._get_or_create_balance(user_id)

        # 2. Get plan info
        monthly_credits, overage_price = self._get_plan_credit_info(user_id)
        sub = (
            self.db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING,
                    SubscriptionStatus.PAST_DUE,
                ]),
            )
            .first()
        )

        # 3. Settle overage
        overage_settled = False
        overage_amount = Decimal("0")
        stripe_invoice_id = None

        if balance.overage_credits_used > 0 and overage_price is not None:
            overage_amount = Decimal(str(balance.overage_credits_used)) * overage_price
            overage_settled = True

            stripe_invoice_id = self._maybe_create_stripe_overage_invoice(
                user_id,
                overage_amount=overage_amount,
                overage_credits_used=balance.overage_credits_used,
                subscription=sub,
            )
            logger.info(
                "Processed overage settlement for user %s: credits=%s, amount=%s, invoice=%s",
                user_id,
                balance.overage_credits_used,
                overage_amount,
                stripe_invoice_id,
            )

            # Write OVERAGE_SETTLEMENT ledger entry
            self.db.add(CreditLedger(
                user_id=user_id,
                operation=CreditOperation.OVERAGE_SETTLEMENT,
                operation_detail="overage_settlement",
                status=CreditLedgerStatus.SETTLED,
                credit_amount=-balance.overage_credits_used,
                source=CreditSource.OVERAGE,
                plan_balance_after=balance.plan_balance,
                topup_balance_after=balance.topup_balance,
                is_overage=True,
                overage_portion=balance.overage_credits_used,
                reference_id=stripe_invoice_id,
                reason=f"Overage settlement: {overage_amount}",
                pricing_version=1,
            ))

        # 4. Clean up expired topups
        now = datetime.utcnow()
        expired_purchases = (
            self.db.query(TopupPurchase)
            .filter(
                TopupPurchase.user_id == user_id,
                TopupPurchase.is_expired == False,
                TopupPurchase.expires_at < now,
            )
            .all()
        )

        topup_expired = 0
        for purchase in expired_purchases:
            topup_expired += purchase.credits_remaining
            purchase.is_expired = True

        if topup_expired > 0:
            balance.topup_balance = max(0, balance.topup_balance - topup_expired)

            # Write TOPUP_EXPIRY ledger entry
            self.db.add(CreditLedger(
                user_id=user_id,
                operation=CreditOperation.TOPUP_EXPIRY,
                operation_detail="topup_expiry",
                status=CreditLedgerStatus.SETTLED,
                credit_amount=-topup_expired,
                source=CreditSource.TOPUP,
                plan_balance_after=balance.plan_balance,
                topup_balance_after=balance.topup_balance,
                is_overage=False,
                overage_portion=0,
                reason=f"Expired {len(expired_purchases)} topup(s)",
                pricing_version=1,
            ))

        # 5. Reset plan_balance
        balance.plan_balance = monthly_credits

        # 6. Reset overage_credits_used
        balance.overage_credits_used = 0

        # 7. Update subscription period dates (+1 month)
        from dateutil.relativedelta import relativedelta

        if sub is not None:
            if sub.current_period_start is not None:
                sub.current_period_start = sub.current_period_start + relativedelta(months=1)
            if sub.current_period_end is not None:
                sub.current_period_end = sub.current_period_end + relativedelta(months=1)

        # 8. Write MONTHLY_RESET ledger entry (only if monthly_credits > 0)
        if monthly_credits > 0:
            self.db.add(CreditLedger(
                user_id=user_id,
                operation=CreditOperation.MONTHLY_RESET,
                operation_detail="monthly_reset",
                status=CreditLedgerStatus.SETTLED,
                credit_amount=monthly_credits,
                source=CreditSource.PLAN,
                plan_balance_after=balance.plan_balance,
                topup_balance_after=balance.topup_balance,
                is_overage=False,
                overage_portion=0,
                reason="Monthly credit reset",
                pricing_version=1,
            ))

        # 9. Flush
        self.db.flush()

        # 10. Delete Redis cache (outside transaction scope)
        self._cache_delete(user_id)

        return PeriodEndResult(
            overage_settled=overage_settled,
            overage_amount=overage_amount if overage_settled else None,
            stripe_invoice_id=stripe_invoice_id,
            topup_expired=topup_expired,
            new_plan_balance=monthly_credits,
        )

    def handle_plan_change_overage_impact(
        self,
        user_id: int,
        old_plan_type: PlanType,
        new_plan_type: PlanType,
    ) -> CreditBalanceInfo:
        """Handle the impact of a plan change on overage state.

        - Downgrade to FREE: disable overage, settle any outstanding overage.
        - Upgrade (higher tier): preserve overage_enabled as-is.

        Parameters
        ----------
        user_id : int
            The user whose plan is changing.
        old_plan_type : PlanType
            The plan type *before* the change.
        new_plan_type : PlanType
            The plan type *after* the change.

        Returns
        -------
        CreditBalanceInfo
            The updated balance information.
        """
        balance = self._get_or_create_balance(user_id)

        if new_plan_type == PlanType.FREE:
            # Downgrade to Free → disable overage and settle outstanding usage
            balance.overage_enabled = False

            if balance.overage_credits_used > 0:
                # Look up overage price from the *old* plan to settle
                _, overage_price = self._get_plan_credit_info_for_plan_type(old_plan_type)
                overage_amount = Decimal("0")
                if overage_price is not None:
                    overage_amount = Decimal(str(balance.overage_credits_used)) * overage_price

                # Write OVERAGE_SETTLEMENT ledger entry
                self.db.add(CreditLedger(
                    user_id=user_id,
                    operation=CreditOperation.OVERAGE_SETTLEMENT,
                    operation_detail="overage_settlement",
                    status=CreditLedgerStatus.SETTLED,
                    credit_amount=-balance.overage_credits_used,
                    source=CreditSource.OVERAGE,
                    plan_balance_after=balance.plan_balance,
                    topup_balance_after=balance.topup_balance,
                    is_overage=True,
                    overage_portion=balance.overage_credits_used,
                    reason=f"Plan downgrade overage settlement: {overage_amount}",
                    pricing_version=1,
                ))

                logger.info(
                    "Plan downgrade overage settlement stub: user_id=%s, "
                    "overage_credits=%s, amount=%s",
                    user_id,
                    balance.overage_credits_used,
                    overage_amount,
                )

                balance.overage_credits_used = 0

        # Upgrade → do nothing to overage_enabled (preserve current state)

        self.db.flush()
        self._cache_delete(user_id)
        return self._build_balance_info(balance, user_id)

    def grant_plan_allowance_for_activation(
        self,
        user_id: int,
        reason: str = "subscription_activation",
    ) -> CreditBalanceInfo:
        """Set the plan bucket to the current plan's monthly allowance.

        This is used when a user completes an initial paid checkout from the
        free tier and should immediately receive the new plan's allowance,
        without waiting for the next monthly reset.
        """
        balance = self._get_or_create_balance(user_id)
        monthly_credits, _ = self._get_plan_credit_info(user_id)

        if balance.plan_balance != monthly_credits:
            delta = monthly_credits - balance.plan_balance
            balance.plan_balance = monthly_credits

            if delta != 0:
                self.db.add(CreditLedger(
                    user_id=user_id,
                    operation=CreditOperation.ADMIN_ADJUSTMENT,
                    operation_detail="plan_activation_grant",
                    status=CreditLedgerStatus.SETTLED,
                    credit_amount=delta,
                    source=CreditSource.PLAN,
                    plan_balance_after=balance.plan_balance,
                    topup_balance_after=balance.topup_balance,
                    is_overage=False,
                    overage_portion=0,
                    reason=reason,
                    pricing_version=1,
                ))

        self.db.commit()
        self.db.refresh(balance)
        self._cache_delete(user_id)
        return self._build_balance_info(balance, user_id)

    def get_ledger(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[CreditLedger]:
        """Return paginated ledger entries for a user, ordered by created_at DESC."""
        return (
            self.db.query(CreditLedger)
            .filter(CreditLedger.user_id == user_id)
            .order_by(CreditLedger.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_credit_costs(self) -> Dict[str, int]:
        """Return a dict mapping operation name to credit cost for all active configs."""
        configs = (
            self.db.query(CreditCostConfig)
            .filter(CreditCostConfig.is_active == True)
            .all()
        )
        return {config.operation: config.credit_cost for config in configs}

    def _maybe_create_stripe_overage_invoice(
        self,
        user_id: int,
        overage_amount: Decimal,
        overage_credits_used: int,
        subscription: Optional[Subscription],
    ) -> Optional[str]:
        """Create a Stripe overage invoice when the user is fully Stripe-backed."""
        from app.core.config import settings

        if not settings.STRIPE_SECRET_KEY or "your_" in settings.STRIPE_SECRET_KEY:
            logger.info("Stripe not configured; skipping overage invoice for user %s", user_id)
            return None

        if subscription is None or not subscription.stripe_customer_id:
            logger.warning(
                "Skipping Stripe overage invoice for user %s: no Stripe customer attached",
                user_id,
            )
            return None

        from app.services.stripe_payment_service import StripePaymentService

        result = StripePaymentService(self.db).create_overage_invoice(
            user_id=user_id,
            overage_amount=overage_amount,
            overage_credits_used=overage_credits_used,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
        )
        return result["invoice_id"]

    def estimate_cost(
        self,
        user_id: int,
        operation: str,
        quantity: int = 1,
    ) -> CreditEstimateResult:
        """Estimate the cost of an operation without any side effects.

        Pure read-only: no ledger, no cache writes, no balance changes.

        Raises
        ------
        ValueError
            If the operation has no active CreditCostConfig entry.
        """
        # 1. Look up cost config
        cost_config = (
            self.db.query(CreditCostConfig)
            .filter(
                CreditCostConfig.operation == operation,
                CreditCostConfig.is_active == True,
            )
            .first()
        )
        if cost_config is None:
            raise ValueError(f"No active CreditCostConfig for operation: {operation}")

        total_cost = cost_config.credit_cost * quantity

        # 2. Get or create balance (read-only intent; auto-create if absent)
        balance = self._get_or_create_balance(user_id)

        # 3. Compute natural balance and flags
        natural_balance = balance.plan_balance + balance.topup_balance
        sufficient_without_overage = natural_balance >= total_cost
        sufficient = sufficient_without_overage or balance.overage_enabled
        would_use_overage = (not sufficient_without_overage) and balance.overage_enabled

        return CreditEstimateResult(
            operation=operation,
            cost=total_cost,
            sufficient=sufficient,
            sufficient_without_overage=sufficient_without_overage,
            would_use_overage=would_use_overage,
        )

    # ------------------------------------------------------------------
    # Idempotency & FIFO helpers
    # ------------------------------------------------------------------

    def has_settled_charge_for_context(
        self,
        user_id: int,
        operation: str,
        context_type: Optional[str],
        context_id: Optional[int],
    ) -> bool:
        """Check if a settled DEDUCTION ledger entry already exists for this context."""
        if context_type is None or context_id is None:
            return False
        return (
            self.db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.DEDUCTION,
                CreditLedger.status == CreditLedgerStatus.SETTLED,
                CreditLedger.operation_detail == operation,
                CreditLedger.context_type == context_type,
                CreditLedger.context_id == context_id,
            )
            .first()
            is not None
        )

    def has_refund_for_key(self, user_id: int, refund_key: str) -> bool:
        """Check if a REFUND ledger entry already exists for this refund_key."""
        return (
            self.db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.REFUND,
                CreditLedger.reference_id == refund_key,
            )
            .first()
            is not None
        )

    def _consume_topup_fifo(self, user_id: int, amount: int) -> int:
        """Consume topup credits in FIFO order (purchased_at ASC).

        Returns the actual consumed amount (may be less than *amount* if
        insufficient TopupPurchase records exist).
        """
        purchases = (
            self.db.query(TopupPurchase)
            .filter(
                TopupPurchase.user_id == user_id,
                TopupPurchase.is_expired == False,
                TopupPurchase.credits_remaining > 0,
            )
            .order_by(TopupPurchase.purchased_at.asc())
            .all()
        )

        consumed = 0
        remaining = amount
        for purchase in purchases:
            if remaining <= 0:
                break
            take = min(purchase.credits_remaining, remaining)
            purchase.credits_remaining -= take
            consumed += take
            remaining -= take
        return consumed

    def _restore_topup_fifo(self, user_id: int, amount: int) -> int:
        """Restore topup credits in reverse FIFO order (purchased_at DESC).

        Opposite of ``_consume_topup_fifo``: restores credits to the most
        recently purchased TopupPurchase records first, up to each record's
        ``credits_purchased`` ceiling.

        Returns the actual restored amount (may be less than *amount* if no
        TopupPurchase records have capacity to absorb the refund).
        """
        purchases = (
            self.db.query(TopupPurchase)
            .filter(
                TopupPurchase.user_id == user_id,
                TopupPurchase.is_expired == False,
            )
            .order_by(TopupPurchase.purchased_at.desc())
            .all()
        )

        restored = 0
        remaining = amount
        for purchase in purchases:
            if remaining <= 0:
                break
            capacity = purchase.credits_purchased - purchase.credits_remaining
            if capacity <= 0:
                continue
            give_back = min(capacity, remaining)
            purchase.credits_remaining += give_back
            restored += give_back
            remaining -= give_back
        return restored

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_balance_info(self, balance: CreditBalance, user_id: int) -> CreditBalanceInfo:
        """Build a CreditBalanceInfo from a CreditBalance record."""
        monthly_credits, overage_price = self._get_plan_credit_info(user_id)
        reset_date = self._get_reset_date(user_id)

        estimated_overage_cost = Decimal(0)
        if overage_price is not None and balance.overage_credits_used > 0:
            estimated_overage_cost = overage_price * balance.overage_credits_used

        return CreditBalanceInfo(
            plan_balance=balance.plan_balance,
            topup_balance=balance.topup_balance,
            total_balance=balance.plan_balance + balance.topup_balance,
            available_without_overage=balance.plan_balance + balance.topup_balance,
            monthly_credits=monthly_credits,
            overage_enabled=balance.overage_enabled,
            overage_credits_used=balance.overage_credits_used,
            overage_price_per_credit=overage_price,
            estimated_overage_cost=estimated_overage_cost,
            has_unpaid_overage=balance.has_unpaid_overage,
            reset_date=reset_date,
        )

    def _get_or_create_balance(self, user_id: int) -> CreditBalance:
        """Load the user's CreditBalance, creating a default record if absent."""

        balance = (
            self.db.query(CreditBalance)
            .filter(CreditBalance.user_id == user_id)
            .first()
        )
        if balance is not None:
            return balance

        # Auto-create: look up plan monthly_credits
        monthly_credits, _ = self._get_plan_credit_info(user_id)

        balance = CreditBalance(
            user_id=user_id,
            plan_balance=monthly_credits,
            topup_balance=0,
            overage_enabled=False,
            overage_credits_used=0,
            has_unpaid_overage=False,
            unpaid_overage_periods=0,
        )
        self.db.add(balance)
        self.db.flush()  # ensure id is assigned; caller controls commit
        return balance

    def _get_plan_credit_info_for_plan_type(
        self, plan_type: PlanType
    ) -> tuple[int, Optional[Decimal]]:
        """Return (monthly_credits, overage_price_per_credit) for a given PlanType.

        Falls back to (0, None) when no matching plan is found.
        """
        from app.models.plan import Plan as PlanModel

        plan = (
            self.db.query(PlanModel)
            .filter(PlanModel.plan_type == plan_type)
            .first()
        )
        if plan is None:
            return 0, None
        return plan.monthly_credits, plan.overage_price_per_credit

    def _get_plan_credit_info(self, user_id: int) -> tuple[int, Optional[Decimal]]:
        """Return (monthly_credits, overage_price_per_credit) for the user's plan.

        Falls back to (0, None) when no active subscription is found.
        """

        sub = (
            self.db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING,
                    SubscriptionStatus.PAST_DUE,
                ]),
            )
            .first()
        )
        if sub is None or sub.plan is None:
            return 0, None

        plan = sub.plan
        return plan.monthly_credits, plan.overage_price_per_credit

    def _get_reset_date(self, user_id: int) -> Optional[datetime]:
        """Return the subscription's current_period_end as the next reset date."""

        sub = (
            self.db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING,
                    SubscriptionStatus.PAST_DUE,
                ]),
            )
            .first()
        )
        if sub is None:
            return None
        return sub.current_period_end

    # ------------------------------------------------------------------
    # Redis cache helpers
    # ------------------------------------------------------------------

    def _cache_key(self, user_id: int) -> str:
        return f"{CACHE_KEY_PREFIX}{user_id}"

    def _cache_get(self, user_id: int) -> Optional[CreditBalanceInfo]:
        """Try to read CreditBalanceInfo from Redis.  Returns None on miss or error."""
        if self.redis_client is None:
            return None
        try:
            raw = self.redis_client.get(self._cache_key(user_id))
            if raw is None:
                return None
            data = json.loads(raw)
            return self._deserialize_balance_info(data)
        except Exception:
            logger.debug("Redis cache read failed for user %s", user_id, exc_info=True)
            return None

    def _cache_set(self, user_id: int, info: CreditBalanceInfo) -> None:
        """Write CreditBalanceInfo to Redis with TTL.  Silently ignores errors."""
        if self.redis_client is None:
            return
        try:
            data = self._serialize_balance_info(info)
            self.redis_client.set(
                self._cache_key(user_id),
                json.dumps(data),
                ex=CACHE_TTL_SECONDS,
            )
        except Exception:
            logger.debug("Redis cache write failed for user %s", user_id, exc_info=True)

    def _cache_delete(self, user_id: int) -> None:
        """Delete the cached balance for a user.  Silently ignores errors."""
        if self.redis_client is None:
            return
        try:
            self.redis_client.delete(self._cache_key(user_id))
        except Exception:
            logger.debug("Redis cache delete failed for user %s", user_id, exc_info=True)

    # ------------------------------------------------------------------
    # Serialization helpers (JSON ↔ CreditBalanceInfo)
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_balance_info(info: CreditBalanceInfo) -> dict:
        data = asdict(info)
        # Convert Decimal / datetime to JSON-safe types
        if data.get("overage_price_per_credit") is not None:
            data["overage_price_per_credit"] = str(data["overage_price_per_credit"])
        data["estimated_overage_cost"] = str(data["estimated_overage_cost"])
        if data.get("reset_date") is not None:
            data["reset_date"] = data["reset_date"].isoformat()
        return data

    @staticmethod
    def _deserialize_balance_info(data: dict) -> CreditBalanceInfo:
        overage_price = data.get("overage_price_per_credit")
        if overage_price is not None:
            overage_price = Decimal(overage_price)

        reset_date = data.get("reset_date")
        if reset_date is not None:
            reset_date = datetime.fromisoformat(reset_date)

        return CreditBalanceInfo(
            plan_balance=data["plan_balance"],
            topup_balance=data["topup_balance"],
            total_balance=data["total_balance"],
            available_without_overage=data["available_without_overage"],
            monthly_credits=data["monthly_credits"],
            overage_enabled=data["overage_enabled"],
            overage_credits_used=data["overage_credits_used"],
            overage_price_per_credit=overage_price,
            estimated_overage_cost=Decimal(data["estimated_overage_cost"]),
            has_unpaid_overage=data["has_unpaid_overage"],
            reset_date=reset_date,
        )
