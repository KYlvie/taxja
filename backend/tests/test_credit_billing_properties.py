"""
Property-based tests for Credit Billing system.

Uses Hypothesis to verify correctness properties of the CreditService.
Each test is linked to specific requirements from the credit-based-billing spec.
"""

import itertools
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import assume, given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.plan import Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.topup_purchase import TopupPurchase
from app.services.credit_service import (
    CreditBalanceInfo,
    CreditService,
    InsufficientCreditsError,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_user_id_counter = itertools.count(start=9000)


def _next_user_id() -> int:
    """Return a unique user_id to avoid unique-constraint violations."""
    return next(_user_id_counter)


def _setup_user_with_balance(
    db,
    plan_balance: int,
    topup_balance: int,
    plan_type: PlanType = PlanType.PLUS,
    monthly_credits: int = 500,
    overage_price: Decimal | None = Decimal("0.04"),
) -> int:
    """Create a Plan, Subscription, and CreditBalance for a fresh user.

    Returns the user_id.
    """
    user_id = _next_user_id()

    # Reuse existing plan for this plan_type if present
    plan = db.query(Plan).filter(Plan.plan_type == plan_type).first()
    if plan is None:
        plan = Plan(
            plan_type=plan_type,
            name=plan_type.value.title(),
            monthly_price=Decimal("9.99"),
            yearly_price=Decimal("99.99"),
            features={},
            quotas={},
            monthly_credits=monthly_credits,
            overage_price_per_credit=overage_price,
        )
        db.add(plan)
        db.flush()

    sub = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime(2025, 1, 1),
        current_period_end=datetime(2025, 2, 1),
    )
    db.add(sub)

    cb = CreditBalance(
        user_id=user_id,
        plan_balance=plan_balance,
        topup_balance=topup_balance,
        overage_enabled=False,
        overage_credits_used=0,
        has_unpaid_overage=False,
        unpaid_overage_periods=0,
    )
    db.add(cb)
    db.flush()

    # Create a TopupPurchase record so FIFO consumption works correctly
    if topup_balance > 0:
        now = datetime.utcnow()
        tp = TopupPurchase(
            user_id=user_id,
            credits_purchased=topup_balance,
            credits_remaining=topup_balance,
            price_paid=Decimal("0.00"),
            stripe_payment_id=None,
            purchased_at=now,
            expires_at=now + timedelta(days=365),
            is_expired=False,
        )
        db.add(tp)
        db.flush()

    return user_id


# ===========================================================================
# Property 1: total_balance invariant
# ===========================================================================


class TestProperty1_TotalBalanceInvariant:
    """
    **Validates: Requirements 1.2**

    Property 1: For any CreditBalance record, get_balance returns
    total_balance == plan_balance + topup_balance, and
    available_without_overage == plan_balance + topup_balance.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=10000),
        topup_balance=st.integers(min_value=0, max_value=10000),
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_total_balance_equals_plan_plus_topup(self, db, plan_balance, topup_balance):
        """
        For any non-negative plan_balance and topup_balance,
        get_balance().total_balance == plan_balance + topup_balance
        and get_balance().available_without_overage == plan_balance + topup_balance.
        """
        user_id = _setup_user_with_balance(db, plan_balance, topup_balance)

        service = CreditService(db, redis_client=None)
        info = service.get_balance(user_id)

        assert info.total_balance == plan_balance + topup_balance, (
            f"total_balance ({info.total_balance}) != "
            f"plan_balance ({plan_balance}) + topup_balance ({topup_balance})"
        )
        assert info.available_without_overage == plan_balance + topup_balance, (
            f"available_without_overage ({info.available_without_overage}) != "
            f"plan_balance ({plan_balance}) + topup_balance ({topup_balance})"
        )

        # Cleanup to avoid accumulation across Hypothesis examples
        db.rollback()


# ---------------------------------------------------------------------------
# Shared helper: CreditCostConfig setup
# ---------------------------------------------------------------------------

def _setup_credit_cost_config(
    db,
    operation: str = "test_op",
    credit_cost: int = 5,
    pricing_version: int = 1,
) -> CreditCostConfig:
    """Create (or reuse) a CreditCostConfig for the given operation.

    Returns the CreditCostConfig instance.
    """
    existing = (
        db.query(CreditCostConfig)
        .filter(CreditCostConfig.operation == operation)
        .first()
    )
    if existing is not None:
        # Update cost/version to match requested values
        existing.credit_cost = credit_cost
        existing.pricing_version = pricing_version
        existing.is_active = True
        db.flush()
        return existing

    config = CreditCostConfig(
        operation=operation,
        credit_cost=credit_cost,
        description=f"Test config for {operation}",
        pricing_version=pricing_version,
        is_active=True,
    )
    db.add(config)
    db.flush()
    return config


# ===========================================================================
# Property 2: 扣费分配守恒 (Deduction allocation conservation)
# ===========================================================================


class TestProperty2_DeductionAllocationConservation:
    """
    **Validates: Requirements 2.2, 2.3, 2.4**

    Property 2: For any deduction, plan_deducted + topup_deducted + overage_portion
    == cost × quantity, and deduction strictly follows plan → topup → overage order:
    topup is only used when plan_balance is insufficient, overage is only used when
    both plan_balance and topup_balance are insufficient.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=5000),
        topup_balance=st.integers(min_value=0, max_value=5000),
        credit_cost=st.integers(min_value=1, max_value=100),
        quantity=st.integers(min_value=1, max_value=10),
        overage_enabled=st.booleans(),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_deduction_conservation_and_order(
        self, db, plan_balance, topup_balance, credit_cost, quantity, overage_enabled
    ):
        total_cost = credit_cost * quantity

        # Only test cases where deduction should succeed
        assume(plan_balance + topup_balance >= total_cost or overage_enabled)

        user_id = _setup_user_with_balance(db, plan_balance, topup_balance)
        config = _setup_credit_cost_config(db, operation="prop2_op", credit_cost=credit_cost)

        # Set overage_enabled on the balance record
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_enabled = overage_enabled
        db.flush()

        service = CreditService(db, redis_client=None)
        result = service.check_and_deduct(user_id, "prop2_op", quantity=quantity)

        # --- Conservation: sum of parts == total cost ---
        assert result.plan_deducted + result.topup_deducted + result.overage_portion == total_cost, (
            f"Conservation violated: {result.plan_deducted} + {result.topup_deducted} + "
            f"{result.overage_portion} != {total_cost}"
        )
        assert result.total_deducted == total_cost

        # --- Order: plan → topup → overage ---
        # plan_deducted should be min(plan_balance, total_cost)
        expected_plan_deducted = min(plan_balance, total_cost)
        assert result.plan_deducted == expected_plan_deducted, (
            f"Plan deducted {result.plan_deducted} != expected {expected_plan_deducted}"
        )

        # topup_deducted should only be used if plan was exhausted
        remaining_after_plan = total_cost - expected_plan_deducted
        expected_topup_deducted = min(topup_balance, remaining_after_plan)
        assert result.topup_deducted == expected_topup_deducted, (
            f"Topup deducted {result.topup_deducted} != expected {expected_topup_deducted}"
        )

        # overage_portion should only be used if both plan and topup were exhausted
        expected_overage = total_cost - expected_plan_deducted - expected_topup_deducted
        assert result.overage_portion == expected_overage, (
            f"Overage portion {result.overage_portion} != expected {expected_overage}"
        )

        # If topup was used, plan must have been fully consumed
        if result.topup_deducted > 0:
            assert result.plan_deducted == plan_balance

        # If overage was used, both plan and topup must have been fully consumed
        if result.overage_portion > 0:
            assert result.plan_deducted == plan_balance
            assert result.topup_deducted == topup_balance

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 3: 余额不足拒绝 (Insufficient balance rejection)
# ===========================================================================


class TestProperty3_InsufficientBalanceRejection:
    """
    **Validates: Requirement 2.5**

    Property 3: When plan_balance + topup_balance < cost × quantity and
    overage is not enabled, check_and_deduct raises InsufficientCreditsError
    and balances remain unchanged.
    """

    @given(
        credit_cost=st.integers(min_value=1, max_value=100),
        quantity=st.integers(min_value=1, max_value=10),
        data=st.data(),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_insufficient_balance_raises_and_unchanged(
        self, db, credit_cost, quantity, data
    ):
        total_cost = credit_cost * quantity

        # Generate balances that are guaranteed to be insufficient
        max_total = total_cost - 1  # must be strictly less than total_cost
        if max_total < 0:
            max_total = 0
        combined = data.draw(st.integers(min_value=0, max_value=max_total))
        plan_balance = data.draw(st.integers(min_value=0, max_value=combined))
        topup_balance = combined - plan_balance

        user_id = _setup_user_with_balance(db, plan_balance, topup_balance)
        _setup_credit_cost_config(db, operation="prop3_op", credit_cost=credit_cost)

        # Ensure overage is disabled
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_enabled = False
        db.flush()

        service = CreditService(db, redis_client=None)

        with pytest.raises(InsufficientCreditsError):
            service.check_and_deduct(user_id, "prop3_op", quantity=quantity)

        # Verify balances are unchanged
        db.refresh(cb)
        assert cb.plan_balance == plan_balance, (
            f"plan_balance changed: {cb.plan_balance} != {plan_balance}"
        )
        assert cb.topup_balance == topup_balance, (
            f"topup_balance changed: {cb.topup_balance} != {topup_balance}"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 14: 扣费金额等于配置成本 (Deduction equals configured cost)
# ===========================================================================


class TestProperty14_DeductionEqualsConfiguredCost:
    """
    **Validates: Requirements 2.1, 7.2, 7.3**

    Property 14: The actual deduction total == CreditCostConfig.credit_cost × quantity,
    and the ledger entry's pricing_version matches the config's pricing_version.
    """

    @given(
        credit_cost=st.integers(min_value=1, max_value=100),
        quantity=st.integers(min_value=1, max_value=10),
        plan_balance=st.integers(min_value=0, max_value=5000),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_deduction_matches_config_cost_and_version(
        self, db, credit_cost, quantity, plan_balance
    ):
        total_cost = credit_cost * quantity

        # Ensure plan_balance is sufficient so deduction succeeds without overage
        assume(plan_balance >= total_cost)

        user_id = _setup_user_with_balance(db, plan_balance, topup_balance=0)
        pricing_version = 3  # Use a non-default version to verify it propagates
        config = _setup_credit_cost_config(
            db,
            operation="prop14_op",
            credit_cost=credit_cost,
            pricing_version=pricing_version,
        )

        service = CreditService(db, redis_client=None)
        result = service.check_and_deduct(user_id, "prop14_op", quantity=quantity)

        # Verify total deducted matches config cost × quantity
        assert result.total_deducted == total_cost, (
            f"total_deducted ({result.total_deducted}) != "
            f"credit_cost ({credit_cost}) × quantity ({quantity}) = {total_cost}"
        )

        # Verify ledger pricing_version matches config
        from app.models.credit_ledger import CreditLedger, CreditOperation

        ledger_entry = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.DEDUCTION,
                CreditLedger.operation_detail == "prop14_op",
            )
            .order_by(CreditLedger.id.desc())
            .first()
        )
        assert ledger_entry is not None, "No ledger entry found for deduction"
        assert ledger_entry.pricing_version == pricing_version, (
            f"Ledger pricing_version ({ledger_entry.pricing_version}) != "
            f"config pricing_version ({pricing_version})"
        )
        assert ledger_entry.credit_amount == -total_cost, (
            f"Ledger credit_amount ({ledger_entry.credit_amount}) != -{total_cost}"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 4: 扣费-退款 round trip (Deduct-Refund Round Trip)
# ===========================================================================


class TestProperty4_DeductRefundRoundTrip:
    """
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

    Property 4: For any successful deduction, if refund_credits is called
    for the same operation, the sum plan_balance + topup_balance +
    overage_credits_used returns to the pre-deduction state.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=5000),
        topup_balance=st.integers(min_value=0, max_value=5000),
        credit_cost=st.integers(min_value=1, max_value=100),
        quantity=st.integers(min_value=1, max_value=10),
        overage_enabled=st.booleans(),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_deduct_then_refund_restores_balances(
        self, db, plan_balance, topup_balance, credit_cost, quantity, overage_enabled
    ):
        total_cost = credit_cost * quantity

        # Only test cases where deduction should succeed
        assume(plan_balance + topup_balance >= total_cost or overage_enabled)

        user_id = _setup_user_with_balance(db, plan_balance, topup_balance)
        _setup_credit_cost_config(db, operation="prop4_op", credit_cost=credit_cost)

        # Set overage_enabled on the balance record
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_enabled = overage_enabled
        db.flush()

        # Record original state (overage_credits_used starts at 0)
        original_plan = plan_balance
        original_topup = topup_balance
        original_overage = 0
        original_total = original_plan + original_topup + original_overage

        service = CreditService(db, redis_client=None)

        # Perform deduction
        service.check_and_deduct(user_id, "prop4_op", quantity=quantity)

        # Perform refund
        service.refund_credits(
            user_id,
            "prop4_op",
            quantity=quantity,
            reason="test_round_trip",
            context_type="test",
            context_id=user_id,
            refund_key=f"prop4_refund_{user_id}",
        )

        # Verify round-trip: balances restored
        db.refresh(cb)
        restored_total = cb.plan_balance + cb.topup_balance + cb.overage_credits_used

        assert restored_total == original_total, (
            f"Round-trip violated: "
            f"plan={cb.plan_balance} + topup={cb.topup_balance} + overage={cb.overage_credits_used} "
            f"= {restored_total} != original {original_total} "
            f"(was plan={original_plan}, topup={original_topup}, overage={original_overage})"
        )

        # Cleanup to avoid accumulation across Hypothesis examples
        db.rollback()


# ===========================================================================
# Property 5: 退款顺序与扣费相反 (Refund order opposite of deduction)
# ===========================================================================


class TestProperty5_RefundOrderOppositeOfDeduction:
    """
    **Validates: Requirements 3.2, 3.3, 3.4**

    Property 5: For any refund operation, the refund allocation strictly
    follows overage → topup → plan order: overage portion is restored first,
    then topup_balance, then plan_balance.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=5000),
        topup_balance=st.integers(min_value=0, max_value=5000),
        credit_cost=st.integers(min_value=1, max_value=100),
        quantity=st.integers(min_value=1, max_value=10),
        overage_enabled=st.booleans(),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_refund_order_is_overage_topup_plan(
        self, db, plan_balance, topup_balance, credit_cost, quantity, overage_enabled
    ):
        total_cost = credit_cost * quantity

        # Only test cases where deduction should succeed
        assume(plan_balance + topup_balance >= total_cost or overage_enabled)

        user_id = _setup_user_with_balance(db, plan_balance, topup_balance)
        _setup_credit_cost_config(db, operation="prop5_op", credit_cost=credit_cost)

        # Set overage_enabled on the balance record
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_enabled = overage_enabled
        db.flush()

        service = CreditService(db, redis_client=None)

        # --- Step 1: Perform deduction and capture the breakdown ---
        deduction_result = service.check_and_deduct(user_id, "prop5_op", quantity=quantity)
        plan_deducted = deduction_result.plan_deducted
        topup_deducted = deduction_result.topup_deducted
        overage_portion = deduction_result.overage_portion

        # --- Step 2: Record intermediate balances (after deduction, before refund) ---
        db.refresh(cb)
        mid_plan = cb.plan_balance
        mid_topup = cb.topup_balance
        mid_overage = cb.overage_credits_used

        # --- Step 3: Perform refund ---
        service.refund_credits(
            user_id,
            "prop5_op",
            quantity=quantity,
            reason="test_refund_order",
            context_type="test",
            context_id=user_id,
            refund_key=f"prop5_refund_{user_id}",
        )

        # --- Step 4: Read post-refund balances ---
        db.refresh(cb)
        post_plan = cb.plan_balance
        post_topup = cb.topup_balance
        post_overage = cb.overage_credits_used

        # Compute actual refund deltas
        overage_refunded = mid_overage - post_overage  # should decrease
        topup_refunded = post_topup - mid_topup        # should increase
        plan_refunded = post_plan - mid_plan            # should increase

        # --- Verify refund order: overage → topup → plan ---

        # 1. If there was an overage portion in the deduction, it must be
        #    refunded first (overage_credits_used decreased by overage_portion).
        if overage_portion > 0:
            assert overage_refunded == overage_portion, (
                f"Overage refund mismatch: expected {overage_portion}, "
                f"got {overage_refunded} (mid_overage={mid_overage}, post_overage={post_overage})"
            )

        # 2. If topup was deducted, it must be refunded after overage.
        if topup_deducted > 0:
            assert topup_refunded == topup_deducted, (
                f"Topup refund mismatch: expected {topup_deducted}, "
                f"got {topup_refunded} (mid_topup={mid_topup}, post_topup={post_topup})"
            )

        # 3. Plan portion is refunded last.
        if plan_deducted > 0:
            assert plan_refunded == plan_deducted, (
                f"Plan refund mismatch: expected {plan_deducted}, "
                f"got {plan_refunded} (mid_plan={mid_plan}, post_plan={post_plan})"
            )

        # 4. Total refund conservation: all parts sum to total_cost
        assert overage_refunded + topup_refunded + plan_refunded == total_cost, (
            f"Refund conservation violated: "
            f"overage_refunded={overage_refunded} + topup_refunded={topup_refunded} + "
            f"plan_refunded={plan_refunded} != total_cost={total_cost}"
        )

        # --- Verify REFUND ledger entry exists with correct operation ---
        from app.models.credit_ledger import CreditLedger, CreditOperation

        refund_ledger = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.REFUND,
                CreditLedger.operation_detail == "prop5_op",
            )
            .order_by(CreditLedger.id.desc())
            .first()
        )
        assert refund_ledger is not None, "No REFUND ledger entry found"
        assert refund_ledger.credit_amount == total_cost, (
            f"REFUND ledger credit_amount ({refund_ledger.credit_amount}) != {total_cost}"
        )

        # If overage was involved in the refund, is_overage should be True
        if overage_portion > 0:
            assert refund_ledger.is_overage is True, (
                "REFUND ledger is_overage should be True when overage was refunded"
            )
            assert refund_ledger.overage_portion == overage_portion, (
                f"REFUND ledger overage_portion ({refund_ledger.overage_portion}) "
                f"!= expected {overage_portion}"
            )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 6: 每次余额变动都有 Ledger 记录
# (Every balance change has a Ledger record)
# ===========================================================================


class TestProperty6_EveryBalanceChangeHasLedger:
    """
    **Validates: Requirements 2.6, 3.5, 5.5, 5.6, 6.4**

    Property 6: For any operation that changes CreditBalance (deduction,
    refund), a corresponding CreditLedger entry is created, and its
    plan_balance_after and topup_balance_after match the actual CreditBalance.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=5000),
        topup_balance=st.integers(min_value=0, max_value=5000),
        credit_cost=st.integers(min_value=1, max_value=100),
        quantity=st.integers(min_value=1, max_value=10),
        overage_enabled=st.booleans(),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_every_balance_change_has_ledger(
        self, db, plan_balance, topup_balance, credit_cost, quantity, overage_enabled
    ):
        from app.models.credit_ledger import CreditLedger, CreditOperation

        total_cost = credit_cost * quantity

        # Only test cases where deduction should succeed
        assume(plan_balance + topup_balance >= total_cost or overage_enabled)

        user_id = _setup_user_with_balance(db, plan_balance, topup_balance)
        _setup_credit_cost_config(db, operation="prop6_op", credit_cost=credit_cost)

        # Set overage_enabled on the balance record
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_enabled = overage_enabled
        db.flush()

        service = CreditService(db, redis_client=None)

        # --- Step 1: Perform deduction ---
        service.check_and_deduct(user_id, "prop6_op", quantity=quantity)

        # Verify DEDUCTION ledger entry exists with correct balance_after
        db.refresh(cb)
        deduction_ledger = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.DEDUCTION,
                CreditLedger.operation_detail == "prop6_op",
            )
            .order_by(CreditLedger.id.desc())
            .first()
        )
        assert deduction_ledger is not None, "No DEDUCTION ledger entry found"
        assert deduction_ledger.plan_balance_after == cb.plan_balance, (
            f"DEDUCTION ledger plan_balance_after ({deduction_ledger.plan_balance_after}) "
            f"!= actual plan_balance ({cb.plan_balance})"
        )
        assert deduction_ledger.topup_balance_after == cb.topup_balance, (
            f"DEDUCTION ledger topup_balance_after ({deduction_ledger.topup_balance_after}) "
            f"!= actual topup_balance ({cb.topup_balance})"
        )

        # --- Step 2: Perform refund ---
        service.refund_credits(
            user_id,
            "prop6_op",
            quantity=quantity,
            reason="test_ledger_audit",
            context_type="test",
            context_id=user_id,
            refund_key=f"prop6_refund_{user_id}",
        )

        # Verify REFUND ledger entry exists with correct balance_after
        db.refresh(cb)
        refund_ledger = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.REFUND,
                CreditLedger.operation_detail == "prop6_op",
            )
            .order_by(CreditLedger.id.desc())
            .first()
        )
        assert refund_ledger is not None, "No REFUND ledger entry found"
        assert refund_ledger.plan_balance_after == cb.plan_balance, (
            f"REFUND ledger plan_balance_after ({refund_ledger.plan_balance_after}) "
            f"!= actual plan_balance ({cb.plan_balance})"
        )
        assert refund_ledger.topup_balance_after == cb.topup_balance, (
            f"REFUND ledger topup_balance_after ({refund_ledger.topup_balance_after}) "
            f"!= actual topup_balance ({cb.topup_balance})"
        )

        # --- Step 3: Verify exactly 2 ledger entries for this user/operation ---
        ledger_count = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation_detail == "prop6_op",
            )
            .count()
        )
        assert ledger_count == 2, (
            f"Expected exactly 2 ledger entries (1 DEDUCTION + 1 REFUND), "
            f"got {ledger_count}"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 15: 成本列表仅返回活跃配置
# (Cost list only returns active configurations)
# ===========================================================================


class TestProperty15_CostListOnlyActiveConfigs:
    """
    **Validates: Requirements 7.5, 10.3**

    Property 15: get_credit_costs returns exactly the set of operations
    where is_active=True. No active config is omitted, and no inactive
    config is included.
    """

    @given(
        configs=st.lists(
            st.tuples(
                st.text(
                    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
                    min_size=1,
                    max_size=30,
                ),
                st.integers(min_value=1, max_value=500),
                st.booleans(),
            ),
            min_size=1,
            max_size=20,
        ),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_get_credit_costs_returns_only_active(self, db, configs):
        """
        Generate a list of (operation_name, credit_cost, is_active) tuples,
        create CreditCostConfig records, then verify get_credit_costs()
        returns exactly the active ones.
        """
        # Deduplicate operation names (keep last occurrence)
        seen = {}
        for op_name, cost, active in configs:
            seen[op_name] = (cost, active)

        # Clear any pre-existing CreditCostConfig records to isolate this test
        db.query(CreditCostConfig).delete()
        db.flush()

        # Create CreditCostConfig records
        expected_active = {}
        for op_name, (cost, active) in seen.items():
            config = CreditCostConfig(
                operation=op_name,
                credit_cost=cost,
                description=f"Test config for {op_name}",
                pricing_version=1,
                is_active=active,
            )
            db.add(config)
            if active:
                expected_active[op_name] = cost
        db.flush()

        # Call get_credit_costs
        service = CreditService(db, redis_client=None)
        result = service.get_credit_costs()

        # 1. Every returned operation has is_active=True in the DB
        for op_name in result:
            db_config = (
                db.query(CreditCostConfig)
                .filter(CreditCostConfig.operation == op_name)
                .first()
            )
            assert db_config is not None, (
                f"Returned operation '{op_name}' not found in DB"
            )
            assert db_config.is_active is True, (
                f"Returned operation '{op_name}' has is_active=False in DB"
            )

        # 2. Every is_active=True config in the DB is present in the result
        for op_name in expected_active:
            assert op_name in result, (
                f"Active operation '{op_name}' missing from get_credit_costs result"
            )
            assert result[op_name] == expected_active[op_name], (
                f"Cost mismatch for '{op_name}': "
                f"expected {expected_active[op_name]}, got {result[op_name]}"
            )

        # 3. No is_active=False config appears in the result
        inactive_ops = {op for op, (_, active) in seen.items() if not active}
        for op_name in inactive_ops:
            assert op_name not in result, (
                f"Inactive operation '{op_name}' should not appear in result"
            )

        # 4. Result size matches expected active count
        assert len(result) == len(expected_active), (
            f"Result size {len(result)} != expected active count {len(expected_active)}"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 18: 历史分页正确性
# (History pagination correctness)
# ===========================================================================


class TestProperty18_HistoryPaginationCorrectness:
    """
    **Validates: Requirements 10.2**

    Property 18: get_ledger returns at most `limit` records, sorted by
    created_at DESC, and `offset` correctly skips the first N records.
    """

    @given(
        num_entries=st.integers(min_value=0, max_value=20),
        limit=st.integers(min_value=1, max_value=50),
        offset=st.integers(min_value=0, max_value=20),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_history_pagination_correctness(self, db, num_entries, limit, offset):
        """
        Create num_entries CreditLedger records with distinct created_at
        timestamps, then verify get_ledger pagination behaviour:
        1. len(results) <= limit
        2. len(results) == max(0, min(limit, num_entries - offset))
        3. Results sorted by created_at DESC
        4. Offset correctly skips the first `offset` records
        """
        from app.models.credit_ledger import (
            CreditLedger,
            CreditOperation,
            CreditSource,
            CreditLedgerStatus,
        )

        user_id = _next_user_id()

        # Create num_entries ledger records with distinct created_at timestamps
        base_time = datetime(2025, 1, 1)
        all_entries = []
        for i in range(num_entries):
            entry = CreditLedger(
                user_id=user_id,
                operation=CreditOperation.DEDUCTION,
                operation_detail="prop18_op",
                status=CreditLedgerStatus.SETTLED,
                credit_amount=-1,
                source=CreditSource.PLAN,
                plan_balance_after=100,
                topup_balance_after=0,
                is_overage=False,
                overage_portion=0,
                pricing_version=1,
                created_at=base_time + timedelta(minutes=i),
            )
            db.add(entry)
            all_entries.append(entry)
        db.flush()

        # Call get_ledger
        service = CreditService(db, redis_client=None)
        results = service.get_ledger(user_id, limit=limit, offset=offset)

        # 1. len(results) <= limit
        assert len(results) <= limit, (
            f"Returned {len(results)} records, exceeds limit {limit}"
        )

        # 2. Exact count: max(0, min(limit, num_entries - offset))
        expected_count = max(0, min(limit, num_entries - offset))
        assert len(results) == expected_count, (
            f"Expected {expected_count} results "
            f"(num_entries={num_entries}, limit={limit}, offset={offset}), "
            f"got {len(results)}"
        )

        # 3. Results sorted by created_at DESC
        for i in range(len(results) - 1):
            assert results[i].created_at >= results[i + 1].created_at, (
                f"Results not sorted DESC at index {i}: "
                f"{results[i].created_at} < {results[i + 1].created_at}"
            )

        # 4. Offset correctly skips the first `offset` records
        # The full DESC-sorted list has the newest entry first.
        # After offset, we expect entries starting from index `offset` in that order.
        if expected_count > 0:
            # Build expected order: all entries sorted by created_at DESC
            all_sorted_desc = sorted(
                all_entries, key=lambda e: e.created_at, reverse=True
            )
            expected_slice = all_sorted_desc[offset : offset + limit]
            for i, result in enumerate(results):
                assert result.created_at == expected_slice[i].created_at, (
                    f"Offset skip incorrect at position {i}: "
                    f"expected created_at={expected_slice[i].created_at}, "
                    f"got {result.created_at}"
                )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 7: Free 套餐不支持 overage
# (Free plan does not support overage)
# ===========================================================================


class TestProperty7_FreePlanNoOverage:
    """
    **Validates: Requirements 4.1, 13.2**

    Property 7: For any Free-plan user, calling set_overage_enabled(user_id, True)
    always raises OverageNotAvailableError. Disabling overage (enabled=False)
    always succeeds regardless of plan type.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=10000),
        topup_balance=st.integers(min_value=0, max_value=10000),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_free_plan_enable_overage_always_raises(self, db, plan_balance, topup_balance):
        """
        For any non-negative plan_balance and topup_balance on a Free plan,
        set_overage_enabled(user_id, enabled=True) always raises OverageNotAvailableError.
        """
        from app.services.credit_service import OverageNotAvailableError

        user_id = _setup_user_with_balance(
            db,
            plan_balance=plan_balance,
            topup_balance=topup_balance,
            plan_type=PlanType.FREE,
            monthly_credits=50,
            overage_price=None,
        )

        service = CreditService(db, redis_client=None)

        with pytest.raises(OverageNotAvailableError):
            service.set_overage_enabled(user_id, enabled=True)

        # Also verify that disabling overage always succeeds for Free plan
        result = service.set_overage_enabled(user_id, enabled=False)
        assert result.overage_enabled is False

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 10: 连续未结清自动禁用 overage
# (Consecutive unpaid periods auto-disable overage)
# ===========================================================================


class TestProperty10_ConsecutiveUnpaidDisablesOverage:
    """
    **Validates: Requirements 4.7**

    Property 10: When unpaid_overage_periods >= 2, calling
    set_overage_enabled(user_id, enabled=True) always raises OverageSuspendedError.
    Disabling overage (enabled=False) always succeeds even with unpaid periods.
    """

    @given(
        unpaid_overage_periods=st.integers(min_value=2, max_value=10),
        plan_balance=st.integers(min_value=0, max_value=10000),
        topup_balance=st.integers(min_value=0, max_value=10000),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_unpaid_periods_gte2_blocks_enable_overage(
        self, db, unpaid_overage_periods, plan_balance, topup_balance
    ):
        """
        For any unpaid_overage_periods >= 2 on a paid plan (PLUS),
        set_overage_enabled(user_id, enabled=True) raises OverageSuspendedError.
        """
        from app.services.credit_service import OverageSuspendedError

        user_id = _setup_user_with_balance(
            db,
            plan_balance=plan_balance,
            topup_balance=topup_balance,
            plan_type=PlanType.PLUS,
            monthly_credits=500,
            overage_price=Decimal("0.04"),
        )

        # Set unpaid overage state
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.unpaid_overage_periods = unpaid_overage_periods
        cb.has_unpaid_overage = True
        db.flush()

        service = CreditService(db, redis_client=None)

        # Enabling overage must raise OverageSuspendedError
        with pytest.raises(OverageSuspendedError):
            service.set_overage_enabled(user_id, enabled=True)

        # Disabling overage must succeed even with unpaid periods
        result = service.set_overage_enabled(user_id, enabled=False)
        assert result.overage_enabled is False

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 9: Overage 费用计算
# (Overage fee calculation)
# ===========================================================================


class TestProperty9_OverageFeeCalculation:
    """
    **Validates: Requirements 4.5, 10.6**

    Property 9: For any period-end processing, the overage settlement amount
    equals overage_credits_used × overage_price_per_credit. When
    overage_credits_used == 0, no overage is settled.
    """

    @given(
        overage_credits_used=st.integers(min_value=0, max_value=1000),
        overage_price=st.sampled_from([
            Decimal("0.01"),
            Decimal("0.02"),
            Decimal("0.04"),
            Decimal("0.05"),
            Decimal("0.10"),
        ]),
        plan_balance=st.integers(min_value=0, max_value=5000),
        topup_balance=st.integers(min_value=0, max_value=5000),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_overage_fee_equals_credits_times_price(
        self, db, overage_credits_used, overage_price, plan_balance, topup_balance
    ):
        """
        For any overage_credits_used and overage_price, process_period_end
        settles overage_amount == overage_credits_used × overage_price when
        overage_credits_used > 0, and does not settle when == 0.
        """
        user_id = _setup_user_with_balance(
            db,
            plan_balance=plan_balance,
            topup_balance=topup_balance,
            plan_type=PlanType.PLUS,
            monthly_credits=500,
            overage_price=overage_price,
        )

        # Set overage_credits_used on the CreditBalance
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_credits_used = overage_credits_used
        db.flush()

        service = CreditService(db, redis_client=None)
        result = service.process_period_end(user_id)

        if overage_credits_used > 0:
            expected_amount = Decimal(str(overage_credits_used)) * overage_price
            assert result.overage_settled is True, (
                f"Expected overage_settled=True when overage_credits_used={overage_credits_used}"
            )
            assert result.overage_amount == expected_amount, (
                f"Overage amount mismatch: {result.overage_amount} != "
                f"{overage_credits_used} × {overage_price} = {expected_amount}"
            )
        else:
            assert result.overage_settled is False, (
                "Expected overage_settled=False when overage_credits_used=0"
            )
            assert result.overage_amount is None, (
                f"Expected overage_amount=None when overage_credits_used=0, "
                f"got {result.overage_amount}"
            )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 11: 月度重置行为
# (Monthly reset behavior)
# ===========================================================================


class TestProperty11_MonthlyResetBehavior:
    """
    **Validates: Requirements 5.1, 5.2, 5.3**

    Property 11: After process_period_end, plan_balance == monthly_credits,
    overage_credits_used == 0, and unexpired topup_balance remains unchanged.
    result.new_plan_balance == monthly_credits.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=5000),
        topup_balance=st.integers(min_value=0, max_value=5000),
        monthly_credits=st.integers(min_value=50, max_value=2000),
        overage_credits_used=st.integers(min_value=0, max_value=500),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_monthly_reset_behavior(
        self, db, plan_balance, topup_balance, monthly_credits, overage_credits_used
    ):
        """
        For any user with arbitrary plan_balance, topup_balance, monthly_credits,
        and overage_credits_used, after process_period_end:
        1. cb.plan_balance == monthly_credits
        2. cb.overage_credits_used == 0
        3. cb.topup_balance == topup_balance (unchanged, no expired topups)
        4. result.new_plan_balance == monthly_credits
        """
        user_id = _setup_user_with_balance(
            db,
            plan_balance=plan_balance,
            topup_balance=topup_balance,
            plan_type=PlanType.PLUS,
            monthly_credits=monthly_credits,
            overage_price=Decimal("0.04"),
        )

        # Set overage_credits_used on the CreditBalance
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_credits_used = overage_credits_used
        db.flush()

        # Ensure all TopupPurchase records have future expires_at (no expired topups)
        future_date = datetime.utcnow() + timedelta(days=365)
        topup_purchases = (
            db.query(TopupPurchase)
            .filter(
                TopupPurchase.user_id == user_id,
                TopupPurchase.is_expired == False,
            )
            .all()
        )
        for tp in topup_purchases:
            tp.expires_at = future_date
        db.flush()

        service = CreditService(db, redis_client=None)
        result = service.process_period_end(user_id)

        # Refresh the CreditBalance from DB
        db.refresh(cb)

        # 1. After reset: plan_balance == monthly_credits
        assert cb.plan_balance == monthly_credits, (
            f"After reset plan_balance ({cb.plan_balance}) != "
            f"monthly_credits ({monthly_credits})"
        )

        # 2. After reset: overage_credits_used == 0
        assert cb.overage_credits_used == 0, (
            f"After reset overage_credits_used ({cb.overage_credits_used}) != 0"
        )

        # 3. After reset: topup_balance unchanged (no expired topups)
        assert cb.topup_balance == topup_balance, (
            f"After reset topup_balance ({cb.topup_balance}) != "
            f"original topup_balance ({topup_balance})"
        )

        # 4. result.new_plan_balance == monthly_credits
        assert result.new_plan_balance == monthly_credits, (
            f"result.new_plan_balance ({result.new_plan_balance}) != "
            f"monthly_credits ({monthly_credits})"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 12: Topup 过期清理
# (Topup expiry cleanup)
# ===========================================================================


class TestProperty12_TopupExpiryCleanup:
    """
    **Validates: Requirements 5.4**

    Property 12: When process_period_end is called, expired TopupPurchase
    records (expires_at in the past) are marked is_expired=True, and
    topup_balance is reduced by the sum of their credits_remaining.
    Valid (non-expired) TopupPurchase records remain unchanged.
    """

    @given(
        num_expired=st.integers(min_value=0, max_value=5),
        num_valid=st.integers(min_value=0, max_value=5),
        expired_credits=st.lists(
            st.integers(min_value=1, max_value=100), min_size=0, max_size=5
        ),
        valid_credits=st.lists(
            st.integers(min_value=1, max_value=100), min_size=0, max_size=5
        ),
        plan_balance=st.integers(min_value=0, max_value=5000),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_topup_expiry_cleanup(
        self, db, num_expired, num_valid, expired_credits, valid_credits, plan_balance
    ):
        """
        For any mix of expired and valid TopupPurchase records,
        process_period_end marks expired ones is_expired=True,
        deducts their credits_remaining from topup_balance,
        and leaves valid ones unchanged.
        """
        # Trim credit lists to match num_expired / num_valid
        expired_credits = expired_credits[:num_expired]
        while len(expired_credits) < num_expired:
            expired_credits.append(1)
        valid_credits = valid_credits[:num_valid]
        while len(valid_credits) < num_valid:
            valid_credits.append(1)

        total_expired_credits = sum(expired_credits)
        total_valid_credits = sum(valid_credits)
        total_topup = total_expired_credits + total_valid_credits

        user_id = _next_user_id()

        # Create Plan and Subscription manually
        plan = db.query(Plan).filter(Plan.plan_type == PlanType.PLUS).first()
        if plan is None:
            plan = Plan(
                plan_type=PlanType.PLUS,
                name="Plus",
                monthly_price=Decimal("9.99"),
                yearly_price=Decimal("99.99"),
                features={},
                quotas={},
                monthly_credits=500,
                overage_price_per_credit=Decimal("0.04"),
            )
            db.add(plan)
            db.flush()

        sub = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime(2025, 1, 1),
            current_period_end=datetime(2025, 2, 1),
        )
        db.add(sub)

        cb = CreditBalance(
            user_id=user_id,
            plan_balance=plan_balance,
            topup_balance=total_topup,
            overage_enabled=False,
            overage_credits_used=0,
            has_unpaid_overage=False,
            unpaid_overage_periods=0,
        )
        db.add(cb)
        db.flush()

        now = datetime.utcnow()

        # Create expired TopupPurchase records (expires_at in the past)
        expired_ids = []
        for cr in expired_credits:
            tp = TopupPurchase(
                user_id=user_id,
                credits_purchased=cr,
                credits_remaining=cr,
                price_paid=Decimal("0.00"),
                stripe_payment_id=None,
                purchased_at=now - timedelta(days=400),
                expires_at=now - timedelta(days=1),
                is_expired=False,
            )
            db.add(tp)
            db.flush()
            expired_ids.append(tp.id)

        # Create valid TopupPurchase records (expires_at in the future)
        valid_ids = []
        for cr in valid_credits:
            tp = TopupPurchase(
                user_id=user_id,
                credits_purchased=cr,
                credits_remaining=cr,
                price_paid=Decimal("0.00"),
                stripe_payment_id=None,
                purchased_at=now - timedelta(days=30),
                expires_at=now + timedelta(days=335),
                is_expired=False,
            )
            db.add(tp)
            db.flush()
            valid_ids.append(tp.id)

        db.flush()

        # Call process_period_end
        service = CreditService(db, redis_client=None)
        result = service.process_period_end(user_id)

        # Verify 1: All expired TopupPurchase records have is_expired=True
        for tp_id in expired_ids:
            tp = db.query(TopupPurchase).filter(TopupPurchase.id == tp_id).first()
            assert tp.is_expired is True, (
                f"Expired TopupPurchase id={tp_id} should have is_expired=True"
            )

        # Verify 2: All valid TopupPurchase records have is_expired=False
        #           and credits_remaining unchanged
        for i, tp_id in enumerate(valid_ids):
            tp = db.query(TopupPurchase).filter(TopupPurchase.id == tp_id).first()
            assert tp.is_expired is False, (
                f"Valid TopupPurchase id={tp_id} should have is_expired=False"
            )
            assert tp.credits_remaining == valid_credits[i], (
                f"Valid TopupPurchase id={tp_id} credits_remaining changed: "
                f"{tp.credits_remaining} != {valid_credits[i]}"
            )

        # Verify 3: result.topup_expired == sum of expired credits_remaining
        assert result.topup_expired == total_expired_credits, (
            f"result.topup_expired ({result.topup_expired}) != "
            f"sum of expired credits ({total_expired_credits})"
        )

        # Verify 4: cb.topup_balance == sum of valid credits_remaining
        db.refresh(cb)
        assert cb.topup_balance == total_valid_credits, (
            f"cb.topup_balance ({cb.topup_balance}) != "
            f"expected valid credits ({total_valid_credits}), "
            f"original topup_balance was {total_topup}, "
            f"expired amount was {total_expired_credits}"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 13: 充值增加 topup_balance
# (Top-up increases topup_balance)
# ===========================================================================


class TestProperty13_TopupIncreasesBalance:
    """
    **Validates: Requirements 6.2, 6.3**

    Property 13: After calling add_topup_credits, topup_balance equals
    the pre-topup value plus the purchased amount, and a TopupPurchase
    record exists with credits_purchased == amount, credits_remaining == amount,
    and expires_at approximately equal to purchased_at + 12 months.
    """

    @given(
        initial_topup_balance=st.integers(min_value=0, max_value=5000),
        topup_amount=st.integers(min_value=1, max_value=1000),
        plan_balance=st.integers(min_value=0, max_value=5000),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_topup_increases_balance_and_creates_purchase(
        self, db, initial_topup_balance, topup_amount, plan_balance
    ):
        """
        For any initial_topup_balance and topup_amount, after add_topup_credits:
        1. cb.topup_balance == initial_topup_balance + topup_amount
        2. A TopupPurchase record exists with credits_purchased == topup_amount
           and credits_remaining == topup_amount
        3. TopupPurchase.expires_at == purchased_at + 12 months (approx)
        """
        from dateutil.relativedelta import relativedelta

        user_id = _setup_user_with_balance(db, plan_balance, initial_topup_balance)

        service = CreditService(db, redis_client=None)
        service.add_topup_credits(user_id, amount=topup_amount, stripe_payment_id="test_pi")

        # 1. Verify topup_balance increased correctly
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        assert cb.topup_balance == initial_topup_balance + topup_amount, (
            f"topup_balance ({cb.topup_balance}) != "
            f"initial ({initial_topup_balance}) + amount ({topup_amount})"
        )

        # 2. Verify TopupPurchase record exists with correct credits
        purchase = (
            db.query(TopupPurchase)
            .filter(
                TopupPurchase.user_id == user_id,
                TopupPurchase.stripe_payment_id == "test_pi",
            )
            .first()
        )
        assert purchase is not None, "No TopupPurchase record found for the topup"
        assert purchase.credits_purchased == topup_amount, (
            f"credits_purchased ({purchase.credits_purchased}) != topup_amount ({topup_amount})"
        )
        assert purchase.credits_remaining == topup_amount, (
            f"credits_remaining ({purchase.credits_remaining}) != topup_amount ({topup_amount})"
        )

        # 3. Verify expires_at == purchased_at + 12 months (within 5 seconds tolerance)
        expected_expires = purchase.purchased_at + relativedelta(months=12)
        delta = abs((purchase.expires_at - expected_expires).total_seconds())
        assert delta < 5, (
            f"expires_at ({purchase.expires_at}) not within 5s of "
            f"purchased_at + 12 months ({expected_expires}), delta={delta}s"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 8: 套餐变更对 overage 的影响
# (Plan change overage impact)
# ===========================================================================


class TestProperty8_PlanChangeOverageImpact:
    """
    **Validates: Requirements 4.3, 4.4**

    Property 8: When a user downgrades to Free, overage_enabled becomes False.
    When a user upgrades (to a higher tier), overage_enabled is preserved as-is.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=5000),
        topup_balance=st.integers(min_value=0, max_value=5000),
        overage_enabled=st.booleans(),
        overage_credits_used=st.integers(min_value=0, max_value=500),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_downgrade_to_free_disables_overage(
        self, db, plan_balance, topup_balance, overage_enabled, overage_credits_used
    ):
        """
        For any user on PLUS with any overage_enabled state and any
        overage_credits_used, downgrading to FREE always results in
        overage_enabled=False and overage_credits_used=0.
        """
        user_id = _setup_user_with_balance(
            db,
            plan_balance=plan_balance,
            topup_balance=topup_balance,
            plan_type=PlanType.PLUS,
            monthly_credits=500,
            overage_price=Decimal("0.04"),
        )

        # Ensure a FREE plan exists for the lookup
        free_plan = db.query(Plan).filter(Plan.plan_type == PlanType.FREE).first()
        if free_plan is None:
            free_plan = Plan(
                plan_type=PlanType.FREE,
                name="Free",
                monthly_price=Decimal("0.00"),
                yearly_price=Decimal("0.00"),
                features={},
                quotas={},
                monthly_credits=50,
                overage_price_per_credit=None,
            )
            db.add(free_plan)
            db.flush()

        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_enabled = overage_enabled
        cb.overage_credits_used = overage_credits_used
        db.flush()

        service = CreditService(db, redis_client=None)
        result = service.handle_plan_change_overage_impact(
            user_id, PlanType.PLUS, PlanType.FREE
        )

        # After downgrade to Free: overage must be disabled
        assert result.overage_enabled is False, (
            f"After downgrade to FREE, overage_enabled should be False, "
            f"got {result.overage_enabled}"
        )

        # overage_credits_used must be settled (reset to 0)
        db.refresh(cb)
        assert cb.overage_credits_used == 0, (
            f"After downgrade to FREE, overage_credits_used should be 0, "
            f"got {cb.overage_credits_used}"
        )

        # Cleanup
        db.rollback()

    @given(
        plan_balance=st.integers(min_value=0, max_value=5000),
        topup_balance=st.integers(min_value=0, max_value=5000),
        overage_enabled=st.booleans(),
        upgrade_path=st.sampled_from([
            (PlanType.FREE, PlanType.PLUS),
            (PlanType.FREE, PlanType.PRO),
            (PlanType.PLUS, PlanType.PRO),
        ]),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_upgrade_preserves_overage_enabled(
        self, db, plan_balance, topup_balance, overage_enabled, upgrade_path
    ):
        """
        For any upgrade path (FREE→PLUS, FREE→PRO, PLUS→PRO),
        overage_enabled is preserved as-is after the plan change.
        """
        old_plan_type, new_plan_type = upgrade_path

        user_id = _setup_user_with_balance(
            db,
            plan_balance=plan_balance,
            topup_balance=topup_balance,
            plan_type=old_plan_type,
            monthly_credits=50 if old_plan_type == PlanType.FREE else 500,
            overage_price=None if old_plan_type == PlanType.FREE else Decimal("0.04"),
        )

        # Ensure the target plan exists
        target_plan = db.query(Plan).filter(Plan.plan_type == new_plan_type).first()
        if target_plan is None:
            target_plan = Plan(
                plan_type=new_plan_type,
                name=new_plan_type.value.title(),
                monthly_price=Decimal("9.99") if new_plan_type == PlanType.PLUS else Decimal("19.99"),
                yearly_price=Decimal("99.99") if new_plan_type == PlanType.PLUS else Decimal("199.99"),
                features={},
                quotas={},
                monthly_credits=500 if new_plan_type == PlanType.PLUS else 2000,
                overage_price_per_credit=Decimal("0.04") if new_plan_type == PlanType.PLUS else Decimal("0.02"),
            )
            db.add(target_plan)
            db.flush()

        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_enabled = overage_enabled
        db.flush()

        service = CreditService(db, redis_client=None)
        result = service.handle_plan_change_overage_impact(
            user_id, old_plan_type, new_plan_type
        )

        # After upgrade: overage_enabled must be preserved
        assert result.overage_enabled == overage_enabled, (
            f"After upgrade {old_plan_type.value}→{new_plan_type.value}, "
            f"overage_enabled should be {overage_enabled}, got {result.overage_enabled}"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 16: 并发扣费余额不为负
# (Concurrent deductions never produce negative balance)
# ===========================================================================


class TestProperty16_ConcurrentDeductionsNeverNegative:
    """
    **Validates: Requirements 8.3**

    Property 16: After a batch of sequential deductions (simulating
    concurrency in SQLite), plan_balance >= 0 and topup_balance >= 0.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=500),
        topup_balance=st.integers(min_value=0, max_value=500),
        credit_cost=st.integers(min_value=1, max_value=50),
        num_deductions=st.integers(min_value=1, max_value=10),
        overage_enabled=st.booleans(),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sequential_deductions_never_negative(
        self, db, plan_balance, topup_balance, credit_cost, num_deductions, overage_enabled
    ):
        """
        For any initial balance and any number of deductions, after all
        deductions complete (some may raise InsufficientCreditsError),
        plan_balance >= 0 and topup_balance >= 0.
        """
        user_id = _setup_user_with_balance(db, plan_balance, topup_balance)
        _setup_credit_cost_config(db, operation="prop16_op", credit_cost=credit_cost)

        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_enabled = overage_enabled
        db.flush()

        service = CreditService(db, redis_client=None)

        for _ in range(num_deductions):
            try:
                service.check_and_deduct(user_id, "prop16_op", quantity=1)
            except InsufficientCreditsError:
                pass

        # After all deductions: balances must never be negative
        db.refresh(cb)
        assert cb.plan_balance >= 0, (
            f"plan_balance went negative: {cb.plan_balance}"
        )
        assert cb.topup_balance >= 0, (
            f"topup_balance went negative: {cb.topup_balance}"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 17: FeatureGateService 委托 CreditService
# (FeatureGateService delegates to CreditService)
# ===========================================================================


class TestProperty17_FeatureGateDelegatesToCreditService:
    """
    **Validates: Requirements 9.1, 9.3, 9.4**

    Property 17: For any user and feature that has a credit operation mapping,
    FeatureGateService.check_feature_access returns the same value as
    CreditService.check_sufficient.
    """

    @given(
        plan_balance=st.integers(min_value=0, max_value=5000),
        topup_balance=st.integers(min_value=0, max_value=5000),
        overage_enabled=st.booleans(),
        feature_op=st.sampled_from([
            ("ocr_scan", 5),
            ("ai_conversation", 10),
            ("transaction_entry", 1),
            ("bank_import", 3),
            ("e1_generation", 20),
            ("tax_calc", 2),
        ]),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_feature_gate_matches_credit_sufficient(
        self, db, plan_balance, topup_balance, overage_enabled, feature_op
    ):
        """
        For any balance state and any feature with a credit operation mapping,
        FeatureGateService.check_feature_access == CreditService.check_sufficient.
        """
        from app.services.feature_gate_service import FeatureGateService, Feature

        operation, cost = feature_op

        user_id = _setup_user_with_balance(db, plan_balance, topup_balance)
        _setup_credit_cost_config(db, operation=operation, credit_cost=cost)

        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        cb.overage_enabled = overage_enabled
        db.flush()

        credit_service = CreditService(db, redis_client=None)
        credit_result = credit_service.check_sufficient(
            user_id, operation, quantity=1, allow_overage=True
        )

        # Find the Feature enum that maps to this operation
        feature_gate = FeatureGateService(db, redis_client=None)
        feature = None
        for f, op in feature_gate._FEATURE_CREDIT_OPERATION.items():
            if op == operation:
                feature = f
                break

        assert feature is not None, f"No Feature maps to operation '{operation}'"

        gate_result = feature_gate.check_feature_access(user_id, feature)

        assert gate_result == credit_result, (
            f"FeatureGateService ({gate_result}) != CreditService ({credit_result}) "
            f"for feature={feature.value}, operation={operation}, "
            f"plan_balance={plan_balance}, topup_balance={topup_balance}, "
            f"overage_enabled={overage_enabled}"
        )

        # Cleanup
        db.rollback()


# ===========================================================================
# Property 19: 迁移后状态正确性
# (Post-migration state correctness)
# ===========================================================================


class TestProperty19_PostMigrationStateCorrectness:
    """
    **Validates: Requirements 12.1, 12.2, 12.3**

    Property 19: After migration (simulated via CreditService auto-create),
    plan_balance == monthly_credits, topup_balance == 0,
    overage_enabled == False. A MIGRATION ledger entry can be written
    and verified.
    """

    @given(
        monthly_credits=st.sampled_from([50, 500, 2000]),
        plan_type=st.sampled_from([PlanType.FREE, PlanType.PLUS, PlanType.PRO]),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_migration_creates_correct_initial_state(self, db, monthly_credits, plan_type):
        """
        For any plan type and monthly_credits value, when a user has no
        CreditBalance record, the auto-created record has:
        1. plan_balance == monthly_credits
        2. topup_balance == 0
        3. overage_enabled == False
        A MIGRATION ledger entry can be written and verified.
        """
        from app.models.credit_ledger import CreditLedger, CreditOperation, CreditLedgerStatus

        user_id = _next_user_id()

        # Create Plan and Subscription but NO CreditBalance
        overage_price = None if plan_type == PlanType.FREE else Decimal("0.04")
        plan = db.query(Plan).filter(Plan.plan_type == plan_type).first()
        if plan is None:
            plan = Plan(
                plan_type=plan_type,
                name=plan_type.value.title(),
                monthly_price=Decimal("0.00"),
                yearly_price=Decimal("0.00"),
                features={},
                quotas={},
                monthly_credits=monthly_credits,
                overage_price_per_credit=overage_price,
            )
            db.add(plan)
            db.flush()
        else:
            # Update monthly_credits to match test parameter
            plan.monthly_credits = monthly_credits
            db.flush()

        sub = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime(2025, 1, 1),
            current_period_end=datetime(2025, 2, 1),
        )
        db.add(sub)
        db.flush()

        # Verify no CreditBalance exists yet
        existing = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        assert existing is None

        # Trigger auto-creation via get_balance
        service = CreditService(db, redis_client=None)
        info = service.get_balance(user_id)

        # 1. plan_balance == monthly_credits
        assert info.plan_balance == monthly_credits, (
            f"plan_balance ({info.plan_balance}) != monthly_credits ({monthly_credits})"
        )

        # 2. topup_balance == 0
        assert info.topup_balance == 0, (
            f"topup_balance ({info.topup_balance}) != 0"
        )

        # 3. overage_enabled == False
        assert info.overage_enabled is False, (
            f"overage_enabled should be False, got {info.overage_enabled}"
        )

        # 4. Simulate writing a MIGRATION ledger entry (as the migration script would)
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        migration_ledger = CreditLedger(
            user_id=user_id,
            operation=CreditOperation.MIGRATION,
            operation_detail="migration",
            status=CreditLedgerStatus.SETTLED,
            credit_amount=monthly_credits,
            source="plan",
            plan_balance_after=cb.plan_balance,
            topup_balance_after=cb.topup_balance,
            is_overage=False,
            overage_portion=0,
            reason="Initial credit migration from quota-based billing",
            pricing_version=1,
        )
        db.add(migration_ledger)
        db.flush()

        # Verify MIGRATION ledger entry exists
        found = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.MIGRATION,
            )
            .first()
        )
        assert found is not None, "No MIGRATION ledger entry found"
        assert found.credit_amount == monthly_credits
        assert found.plan_balance_after == monthly_credits
        assert found.topup_balance_after == 0

        # Cleanup
        db.rollback()
