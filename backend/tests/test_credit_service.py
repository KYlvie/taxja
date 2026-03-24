"""Unit tests for CreditService — get_balance, dataclasses, exceptions, and caching."""

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.credit_ledger import CreditLedger, CreditOperation, CreditSource, CreditLedgerStatus
from app.models.plan import Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.topup_purchase import TopupPurchase
from app.services.credit_service import (
    CACHE_KEY_PREFIX,
    CACHE_TTL_SECONDS,
    CreditBalanceInfo,
    CreditDeductionResult,
    CreditEstimateResult,
    CreditService,
    InsufficientCreditsError,
    OverageNotAvailableError,
    OverageSuspendedError,
    PeriodEndResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(
    plan_type=PlanType.PLUS,
    monthly_credits=500,
    overage_price=Decimal("0.04"),
) -> Plan:
    plan = Plan()
    plan.id = 1
    plan.plan_type = plan_type
    plan.name = plan_type.value.title()
    plan.monthly_price = Decimal("9.99")
    plan.yearly_price = Decimal("99.99")
    plan.features = {}
    plan.quotas = {}
    plan.monthly_credits = monthly_credits
    plan.overage_price_per_credit = overage_price
    return plan


def _make_subscription(user_id: int, plan: Plan) -> Subscription:
    sub = Subscription()
    sub.id = 1
    sub.user_id = user_id
    sub.plan_id = plan.id
    sub.plan = plan
    sub.status = SubscriptionStatus.ACTIVE
    sub.current_period_start = datetime(2025, 1, 1)
    sub.current_period_end = datetime(2025, 2, 1)
    return sub


def _make_credit_balance(user_id: int, plan_balance=500, topup_balance=0) -> CreditBalance:
    cb = CreditBalance()
    cb.id = 1
    cb.user_id = user_id
    cb.plan_balance = plan_balance
    cb.topup_balance = topup_balance
    cb.overage_enabled = False
    cb.overage_credits_used = 0
    cb.has_unpaid_overage = False
    cb.unpaid_overage_periods = 0
    cb.updated_at = datetime.utcnow()
    return cb


# ---------------------------------------------------------------------------
# Exception tests
# ---------------------------------------------------------------------------

class TestExceptions:
    def test_insufficient_credits_error_attributes(self):
        err = InsufficientCreditsError(required=10, available=3)
        assert err.required == 10
        assert err.available == 3
        assert "required 10" in str(err)
        assert "available 3" in str(err)

    def test_overage_not_available_error(self):
        err = OverageNotAvailableError()
        assert isinstance(err, Exception)

    def test_overage_suspended_error(self):
        err = OverageSuspendedError()
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestDataclasses:
    def test_credit_balance_info_fields(self):
        info = CreditBalanceInfo(
            plan_balance=300,
            topup_balance=50,
            total_balance=350,
            available_without_overage=350,
            monthly_credits=500,
            overage_enabled=True,
            overage_credits_used=10,
            overage_price_per_credit=Decimal("0.04"),
            estimated_overage_cost=Decimal("0.40"),
            has_unpaid_overage=False,
            reset_date=datetime(2025, 2, 1),
        )
        assert info.total_balance == info.plan_balance + info.topup_balance
        assert info.available_without_overage == info.plan_balance + info.topup_balance

    def test_credit_deduction_result(self):
        info = CreditBalanceInfo(
            plan_balance=295, topup_balance=50, total_balance=345,
            available_without_overage=345, monthly_credits=500,
            overage_enabled=False, overage_credits_used=0,
            overage_price_per_credit=Decimal("0.04"),
            estimated_overage_cost=Decimal("0"), has_unpaid_overage=False,
            reset_date=None,
        )
        result = CreditDeductionResult(
            success=True, plan_deducted=5, topup_deducted=0,
            overage_portion=0, total_deducted=5, balance_after=info,
        )
        assert result.total_deducted == result.plan_deducted + result.topup_deducted + result.overage_portion

    def test_period_end_result(self):
        r = PeriodEndResult(
            overage_settled=True, overage_amount=Decimal("1.88"),
            stripe_invoice_id="inv_123", topup_expired=20, new_plan_balance=500,
        )
        assert r.overage_settled is True

    def test_credit_estimate_result(self):
        r = CreditEstimateResult(
            operation="ocr_scan", cost=5, sufficient=True,
            sufficient_without_overage=True, would_use_overage=False,
        )
        assert r.cost == 5


# ---------------------------------------------------------------------------
# CreditService.get_balance tests
# ---------------------------------------------------------------------------

class TestGetBalance:
    """Tests for CreditService.get_balance method."""

    def test_get_balance_existing_record(self, db):
        """get_balance returns correct info when CreditBalance exists."""
        user_id = 1
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=320, topup_balance=45)

        db.add(plan)
        db.add(sub)
        db.add(cb)
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.get_balance(user_id)

        assert info.plan_balance == 320
        assert info.topup_balance == 45
        assert info.total_balance == 365
        assert info.available_without_overage == 365
        assert info.monthly_credits == 500
        assert info.overage_enabled is False
        assert info.overage_credits_used == 0
        assert info.overage_price_per_credit == Decimal("0.04")
        assert info.estimated_overage_cost == Decimal("0")
        assert info.has_unpaid_overage is False
        assert info.reset_date == datetime(2025, 2, 1)

    def test_get_balance_auto_creates_record(self, db):
        """get_balance auto-creates CreditBalance when none exists."""
        user_id = 2
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)

        db.add(plan)
        db.add(sub)
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.get_balance(user_id)

        # Should have auto-created with plan_balance = monthly_credits
        assert info.plan_balance == 500
        assert info.topup_balance == 0
        assert info.total_balance == 500

        # Verify record was persisted
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        assert cb is not None
        assert cb.plan_balance == 500

    def test_get_balance_no_subscription_defaults_to_zero(self, db):
        """get_balance returns 0 monthly_credits when user has no subscription."""
        user_id = 3

        service = CreditService(db, redis_client=None)
        info = service.get_balance(user_id)

        assert info.plan_balance == 0
        assert info.topup_balance == 0
        assert info.monthly_credits == 0
        assert info.reset_date is None

    def test_get_balance_with_overage_used(self, db):
        """get_balance calculates estimated_overage_cost correctly."""
        user_id = 4
        plan = _make_plan(overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=0)
        cb.overage_enabled = True
        cb.overage_credits_used = 47

        db.add(plan)
        db.add(sub)
        db.add(cb)
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.get_balance(user_id)

        assert info.overage_credits_used == 47
        assert info.estimated_overage_cost == Decimal("0.04") * 47  # 1.88

    def test_get_balance_free_plan_no_overage_price(self, db):
        """Free plan has overage_price_per_credit = None."""
        user_id = 5
        plan = _make_plan(plan_type=PlanType.FREE, monthly_credits=50, overage_price=None)
        sub = _make_subscription(user_id, plan)

        db.add(plan)
        db.add(sub)
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.get_balance(user_id)

        assert info.monthly_credits == 50
        assert info.overage_price_per_credit is None
        assert info.estimated_overage_cost == Decimal("0")


# ---------------------------------------------------------------------------
# Redis caching tests
# ---------------------------------------------------------------------------

class TestRedisCaching:
    """Tests for Redis cache read/write/delete logic."""

    def test_cache_hit_returns_cached_data(self, db):
        """get_balance returns cached data on cache hit."""
        user_id = 10
        cached_info = CreditBalanceInfo(
            plan_balance=100, topup_balance=20, total_balance=120,
            available_without_overage=120, monthly_credits=500,
            overage_enabled=False, overage_credits_used=0,
            overage_price_per_credit=Decimal("0.04"),
            estimated_overage_cost=Decimal("0"), has_unpaid_overage=False,
            reset_date=datetime(2025, 3, 1),
        )
        cached_json = json.dumps(CreditService._serialize_balance_info(cached_info))

        mock_redis = MagicMock()
        mock_redis.get.return_value = cached_json

        service = CreditService(db, redis_client=mock_redis)
        info = service.get_balance(user_id)

        mock_redis.get.assert_called_once_with(f"{CACHE_KEY_PREFIX}{user_id}")
        assert info.plan_balance == 100
        assert info.topup_balance == 20

    def test_cache_miss_loads_from_db_and_caches(self, db):
        """get_balance loads from DB on cache miss and caches result."""
        user_id = 11
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=200, topup_balance=30)

        db.add(plan)
        db.add(sub)
        db.add(cb)
        db.commit()

        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # cache miss

        service = CreditService(db, redis_client=mock_redis)
        info = service.get_balance(user_id)

        # Should have loaded from DB
        assert info.plan_balance == 200
        assert info.topup_balance == 30

        # Should have cached the result
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == f"{CACHE_KEY_PREFIX}{user_id}"
        assert call_args[1]["ex"] == CACHE_TTL_SECONDS

    def test_redis_error_falls_back_to_db(self, db):
        """get_balance falls back to DB when Redis raises an error."""
        user_id = 12
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=150, topup_balance=10)

        db.add(plan)
        db.add(sub)
        db.add(cb)
        db.commit()

        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Redis connection error")
        mock_redis.set.side_effect = Exception("Redis connection error")

        service = CreditService(db, redis_client=mock_redis)
        info = service.get_balance(user_id)

        # Should still return correct data from DB
        assert info.plan_balance == 150
        assert info.topup_balance == 10

    def test_no_redis_client_works(self, db):
        """get_balance works without Redis client (DB-only mode)."""
        user_id = 13
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=400, topup_balance=0)

        db.add(plan)
        db.add(sub)
        db.add(cb)
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.get_balance(user_id)

        assert info.plan_balance == 400


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

class TestSerialization:
    """Tests for JSON serialization/deserialization of CreditBalanceInfo."""

    def test_serialize_deserialize_roundtrip(self):
        """Serialization and deserialization produce equivalent objects."""
        original = CreditBalanceInfo(
            plan_balance=250, topup_balance=75, total_balance=325,
            available_without_overage=325, monthly_credits=500,
            overage_enabled=True, overage_credits_used=15,
            overage_price_per_credit=Decimal("0.03"),
            estimated_overage_cost=Decimal("0.45"), has_unpaid_overage=True,
            reset_date=datetime(2025, 4, 15, 12, 30, 0),
        )

        serialized = CreditService._serialize_balance_info(original)
        deserialized = CreditService._deserialize_balance_info(serialized)

        assert deserialized.plan_balance == original.plan_balance
        assert deserialized.topup_balance == original.topup_balance
        assert deserialized.total_balance == original.total_balance
        assert deserialized.available_without_overage == original.available_without_overage
        assert deserialized.monthly_credits == original.monthly_credits
        assert deserialized.overage_enabled == original.overage_enabled
        assert deserialized.overage_credits_used == original.overage_credits_used
        assert deserialized.overage_price_per_credit == original.overage_price_per_credit
        assert deserialized.estimated_overage_cost == original.estimated_overage_cost
        assert deserialized.has_unpaid_overage == original.has_unpaid_overage
        assert deserialized.reset_date == original.reset_date

    def test_serialize_with_none_values(self):
        """Serialization handles None values correctly."""
        info = CreditBalanceInfo(
            plan_balance=50, topup_balance=0, total_balance=50,
            available_without_overage=50, monthly_credits=50,
            overage_enabled=False, overage_credits_used=0,
            overage_price_per_credit=None,
            estimated_overage_cost=Decimal("0"), has_unpaid_overage=False,
            reset_date=None,
        )

        serialized = CreditService._serialize_balance_info(info)
        deserialized = CreditService._deserialize_balance_info(serialized)

        assert deserialized.overage_price_per_credit is None
        assert deserialized.reset_date is None


# ---------------------------------------------------------------------------
# Stub method tests
# ---------------------------------------------------------------------------

class TestStubMethods:
    """Verify stub methods raise NotImplementedError."""

    def test_refund_credits_requires_cost_config(self, db):
        """refund_credits raises ValueError when no CreditCostConfig exists."""
        user_id = 1
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100)
        db.add_all([plan, sub, cb])
        db.commit()
        service = CreditService(db, redis_client=None)
        with pytest.raises(ValueError, match="No active CreditCostConfig"):
            service.refund_credits(user_id=user_id, operation="nonexistent_op")

    def test_check_sufficient_unknown_op_returns_false(self, db):
        service = CreditService(db, redis_client=None)
        assert service.check_sufficient(user_id=1, operation="nonexistent_op") is False

    def test_add_topup_credits_placeholder(self, db):
        """Placeholder — real tests in TestAddTopupCredits."""
        pass

    def test_set_overage_enabled_placeholder(self, db):
        """Placeholder — real tests in TestSetOverageEnabled."""
        pass

    def test_process_period_end_placeholder(self, db):
        """Placeholder — real tests in TestProcessPeriodEnd."""
        pass

    def test_get_ledger_returns_list(self, db):
        service = CreditService(db, redis_client=None)
        result = service.get_ledger(user_id=1)
        assert result == []

    def test_get_credit_costs_placeholder(self, db):
        """Placeholder — real tests in TestGetCreditCosts."""
        pass

    def test_estimate_cost_placeholder(self, db):
        """Placeholder — real tests in TestEstimateCost."""
        pass


# ---------------------------------------------------------------------------
# Helpers for check_and_deduct tests
# ---------------------------------------------------------------------------

def _make_cost_config(operation="ocr_scan", credit_cost=5, pricing_version=1):
    cc = CreditCostConfig()
    cc.operation = operation
    cc.credit_cost = credit_cost
    cc.pricing_version = pricing_version
    cc.is_active = True
    cc.description = f"Test config for {operation}"
    return cc


def _make_topup_purchase(user_id, credits_remaining, purchased_at=None, expires_at=None):
    from datetime import timedelta
    tp = TopupPurchase()
    tp.user_id = user_id
    tp.credits_purchased = credits_remaining
    tp.credits_remaining = credits_remaining
    tp.price_paid = Decimal("4.99")
    tp.purchased_at = purchased_at or datetime(2025, 1, 1)
    tp.expires_at = expires_at or (tp.purchased_at + timedelta(days=365))
    tp.is_expired = False
    return tp


# ---------------------------------------------------------------------------
# check_and_deduct tests
# ---------------------------------------------------------------------------

class TestCheckAndDeduct:
    """Tests for CreditService.check_and_deduct method."""

    def test_fast_path_plan_balance_sufficient(self, db):
        """When plan_balance >= cost, deduct only from plan (fast path)."""
        user_id = 20
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=50)
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert result.success is True
        assert result.plan_deducted == 5
        assert result.topup_deducted == 0
        assert result.overage_portion == 0
        assert result.total_deducted == 5
        assert result.balance_after.plan_balance == 95
        assert result.balance_after.topup_balance == 50

        # Verify ledger was written
        ledger = db.query(CreditLedger).filter(CreditLedger.user_id == user_id).first()
        assert ledger is not None
        assert ledger.credit_amount == -5
        assert ledger.source == CreditSource.PLAN
        assert ledger.is_overage is False
        assert ledger.pricing_version == 1

    def test_fast_path_with_quantity(self, db):
        """Fast path with quantity > 1."""
        user_id = 21
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=0)
        cc = _make_cost_config("transaction_entry", credit_cost=1)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.check_and_deduct(user_id, "transaction_entry", quantity=10)

        assert result.success is True
        assert result.plan_deducted == 10
        assert result.total_deducted == 10
        assert result.balance_after.plan_balance == 90

    def test_slow_path_plan_plus_topup(self, db):
        """When plan_balance < cost but plan + topup sufficient, use both."""
        user_id = 22
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=3, topup_balance=50)
        cc = _make_cost_config("ocr_scan", credit_cost=5)
        tp = _make_topup_purchase(user_id, credits_remaining=50)

        db.add_all([plan, sub, cb, cc, tp])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert result.success is True
        assert result.plan_deducted == 3
        assert result.topup_deducted == 2
        assert result.overage_portion == 0
        assert result.total_deducted == 5
        assert result.balance_after.plan_balance == 0
        assert result.balance_after.topup_balance == 48

        # Verify ledger source is MIXED
        ledger = db.query(CreditLedger).filter(CreditLedger.user_id == user_id).first()
        assert ledger.source == CreditSource.MIXED

    def test_slow_path_topup_only(self, db):
        """When plan_balance == 0, deduct entirely from topup."""
        user_id = 23
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=50)
        cc = _make_cost_config("ocr_scan", credit_cost=5)
        tp = _make_topup_purchase(user_id, credits_remaining=50)

        db.add_all([plan, sub, cb, cc, tp])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert result.success is True
        assert result.plan_deducted == 0
        assert result.topup_deducted == 5
        assert result.balance_after.topup_balance == 45

        ledger = db.query(CreditLedger).filter(CreditLedger.user_id == user_id).first()
        assert ledger.source == CreditSource.TOPUP

    def test_slow_path_with_overage(self, db):
        """When plan + topup insufficient but overage enabled, use overage."""
        user_id = 24
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=2, topup_balance=0)
        cb.overage_enabled = True
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert result.success is True
        assert result.plan_deducted == 2
        assert result.topup_deducted == 0
        assert result.overage_portion == 3
        assert result.total_deducted == 5
        assert result.balance_after.plan_balance == 0
        assert result.balance_after.overage_credits_used == 3

        ledger = db.query(CreditLedger).filter(CreditLedger.user_id == user_id).first()
        assert ledger.is_overage is True
        assert ledger.overage_portion == 3
        assert ledger.source == CreditSource.MIXED

    def test_insufficient_credits_no_overage(self, db):
        """When balance insufficient and overage disabled, raise error."""
        user_id = 25
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=2, topup_balance=1)
        cb.overage_enabled = False
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        with pytest.raises(InsufficientCreditsError) as exc_info:
            service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert exc_info.value.required == 5
        assert exc_info.value.available == 3

    def test_unknown_operation_raises_value_error(self, db):
        """When operation has no CreditCostConfig, raise ValueError."""
        user_id = 26
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        with pytest.raises(ValueError, match="No active CreditCostConfig"):
            service.check_and_deduct(user_id, "nonexistent_operation")

    def test_idempotency_with_context(self, db):
        """Duplicate deduction for same context returns without double-charging."""
        user_id = 27
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=0)
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)

        # First deduction
        result1 = service.check_and_deduct(
            user_id, "ocr_scan", context_type="document", context_id=42
        )
        assert result1.total_deducted == 5
        assert result1.balance_after.plan_balance == 95

        # Second deduction with same context — should be idempotent
        result2 = service.check_and_deduct(
            user_id, "ocr_scan", context_type="document", context_id=42
        )
        assert result2.total_deducted == 0  # no additional deduction
        assert result2.balance_after.plan_balance == 95  # balance unchanged

    def test_idempotency_without_context_charges_twice(self, db):
        """Without context_type/context_id, idempotency check is skipped."""
        user_id = 28
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=0)
        cc = _make_cost_config("ai_conversation", credit_cost=10)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)

        result1 = service.check_and_deduct(user_id, "ai_conversation")
        assert result1.balance_after.plan_balance == 90

        result2 = service.check_and_deduct(user_id, "ai_conversation")
        assert result2.balance_after.plan_balance == 80  # charged again

    def test_ledger_records_context_and_pricing(self, db):
        """Ledger entry records context_type, context_id, and pricing_version."""
        user_id = 29
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100)
        cc = _make_cost_config("e1_generation", credit_cost=20, pricing_version=2)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        service.check_and_deduct(
            user_id, "e1_generation",
            context_type="tax_form", context_id=99,
        )

        ledger = db.query(CreditLedger).filter(CreditLedger.user_id == user_id).first()
        assert ledger.context_type == "tax_form"
        assert ledger.context_id == 99
        assert ledger.pricing_version == 2
        assert ledger.operation_detail == "e1_generation"

    def test_redis_cache_deleted_after_deduction(self, db):
        """Redis cache key is deleted after successful deduction."""
        user_id = 30
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100)
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # cache miss on get_balance calls

        service = CreditService(db, redis_client=mock_redis)
        service.check_and_deduct(user_id, "ocr_scan")

        mock_redis.delete.assert_called_with(f"credit_balance:{user_id}")

    def test_topup_fifo_consumption_order(self, db):
        """Topup credits are consumed in FIFO order (oldest first)."""
        user_id = 31
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=30)
        cc = _make_cost_config("ai_conversation", credit_cost=10)

        # Two topup purchases: older one with 8 remaining, newer with 22
        tp1 = _make_topup_purchase(user_id, credits_remaining=8,
                                    purchased_at=datetime(2025, 1, 1))
        tp2 = _make_topup_purchase(user_id, credits_remaining=22,
                                    purchased_at=datetime(2025, 2, 1))

        db.add_all([plan, sub, cb, cc, tp1, tp2])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.check_and_deduct(user_id, "ai_conversation", quantity=1)

        assert result.topup_deducted == 10
        assert result.balance_after.topup_balance == 20

        # Verify FIFO: tp1 should be fully consumed first, then tp2
        db.refresh(tp1)
        db.refresh(tp2)
        assert tp1.credits_remaining == 0  # 8 - 8 = 0
        assert tp2.credits_remaining == 20  # 22 - 2 = 20


# ---------------------------------------------------------------------------
# add_topup_credits tests
# ---------------------------------------------------------------------------

class TestAddTopupCredits:
    """Tests for CreditService.add_topup_credits method."""

    def test_add_topup_basic_balance_increase(self, db):
        """topup_balance increases by the purchased amount."""
        user_id = 100
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.add_topup_credits(user_id, amount=100, stripe_payment_id="pi_abc123")

        assert info.topup_balance == 100
        assert info.plan_balance == 500
        assert info.total_balance == 600

    def test_add_topup_creates_purchase_record(self, db):
        """TopupPurchase record is created with correct fields."""
        from dateutil.relativedelta import relativedelta

        user_id = 101
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        service.add_topup_credits(user_id, amount=300, stripe_payment_id="pi_xyz789")

        purchase = db.query(TopupPurchase).filter(TopupPurchase.user_id == user_id).first()
        assert purchase is not None
        assert purchase.credits_purchased == 300
        assert purchase.credits_remaining == 300
        assert purchase.stripe_payment_id == "pi_xyz789"
        assert purchase.is_expired is False
        assert purchase.price_paid == Decimal("0.00")
        # expires_at should be ~12 months after purchased_at
        expected_expires = purchase.purchased_at + relativedelta(months=12)
        assert abs((purchase.expires_at - expected_expires).total_seconds()) < 2

    def test_add_topup_creates_ledger_entry(self, db):
        """A TOPUP ledger entry is created with correct fields."""
        user_id = 102
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        service.add_topup_credits(user_id, amount=200, stripe_payment_id="pi_ledger1")

        ledger = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.TOPUP,
            )
            .first()
        )
        assert ledger is not None
        assert ledger.credit_amount == 200
        assert ledger.source == CreditSource.TOPUP
        assert ledger.status == CreditLedgerStatus.SETTLED
        assert ledger.is_overage is False
        assert ledger.overage_portion == 0
        assert ledger.plan_balance_after == 500
        assert ledger.topup_balance_after == 200
        assert ledger.reference_id == "pi_ledger1"

    def test_add_topup_deletes_redis_cache(self, db):
        """Redis cache key is deleted after topup."""
        user_id = 103
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)

        db.add_all([plan, sub, cb])
        db.commit()

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        service = CreditService(db, redis_client=mock_redis)
        service.add_topup_credits(user_id, amount=100, stripe_payment_id="pi_cache1")

        mock_redis.delete.assert_called_with(f"credit_balance:{user_id}")

    def test_add_topup_multiple_accumulate(self, db):
        """Multiple topups accumulate correctly."""
        user_id = 104
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)

        info1 = service.add_topup_credits(user_id, amount=100, stripe_payment_id="pi_first")
        assert info1.topup_balance == 100

        info2 = service.add_topup_credits(user_id, amount=250, stripe_payment_id="pi_second")
        assert info2.topup_balance == 350

        # Verify two TopupPurchase records exist
        purchases = db.query(TopupPurchase).filter(TopupPurchase.user_id == user_id).all()
        assert len(purchases) == 2

        # Verify two TOPUP ledger entries exist
        ledger_count = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.TOPUP,
            )
            .count()
        )
        assert ledger_count == 2


# ---------------------------------------------------------------------------
# Helper method tests
# ---------------------------------------------------------------------------

class TestHelperMethods:
    """Tests for idempotency helper methods."""

    def test_has_settled_charge_returns_false_when_no_context(self, db):
        """Returns False when context_type or context_id is None."""
        service = CreditService(db, redis_client=None)
        assert service.has_settled_charge_for_context(1, "ocr_scan", None, None) is False
        assert service.has_settled_charge_for_context(1, "ocr_scan", "document", None) is False
        assert service.has_settled_charge_for_context(1, "ocr_scan", None, 42) is False

    def test_has_settled_charge_returns_false_when_no_match(self, db):
        """Returns False when no matching ledger entry exists."""
        service = CreditService(db, redis_client=None)
        assert service.has_settled_charge_for_context(
            1, "ocr_scan", "document", 42
        ) is False

    def test_has_refund_for_key_returns_false_when_no_match(self, db):
        """Returns False when no matching refund ledger exists."""
        service = CreditService(db, redis_client=None)
        assert service.has_refund_for_key(1, "refund:doc_123") is False


# ---------------------------------------------------------------------------
# refund_credits tests
# ---------------------------------------------------------------------------

class TestRefundCredits:
    """Tests for CreditService.refund_credits method."""

    def test_refund_plan_only(self, db):
        """Refund restores plan_balance when no overage or topup was used."""
        user_id = 40
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=95, topup_balance=0)
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.refund_credits(user_id, "ocr_scan", quantity=1, reason="ocr_processing_failed")

        assert info.plan_balance == 100  # 95 + 5
        assert info.topup_balance == 0
        assert info.overage_credits_used == 0

        # Verify ledger
        ledger = (
            db.query(CreditLedger)
            .filter(CreditLedger.user_id == user_id, CreditLedger.operation == CreditOperation.REFUND)
            .first()
        )
        assert ledger is not None
        assert ledger.credit_amount == 5
        assert ledger.source == CreditSource.PLAN
        assert ledger.reason == "ocr_processing_failed"
        assert ledger.status == CreditLedgerStatus.SETTLED
        assert ledger.operation_detail == "ocr_scan"

    def test_refund_overage_first(self, db):
        """Refund reduces overage_credits_used before touching topup/plan."""
        user_id = 41
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=0)
        cb.overage_enabled = True
        cb.overage_credits_used = 5
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.refund_credits(user_id, "ocr_scan", quantity=1)

        assert info.overage_credits_used == 0
        assert info.plan_balance == 0
        assert info.topup_balance == 0

        ledger = (
            db.query(CreditLedger)
            .filter(CreditLedger.user_id == user_id, CreditLedger.operation == CreditOperation.REFUND)
            .first()
        )
        assert ledger.source == CreditSource.OVERAGE
        assert ledger.is_overage is True
        assert ledger.overage_portion == 5

    def test_refund_overage_then_plan(self, db):
        """Refund reduces overage first, then restores plan_balance."""
        user_id = 42
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=0)
        cb.overage_enabled = True
        cb.overage_credits_used = 3  # only 3 of the 5 were overage
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.refund_credits(user_id, "ocr_scan", quantity=1)

        assert info.overage_credits_used == 0
        assert info.plan_balance == 2  # remaining 2 goes to plan
        assert info.topup_balance == 0

        ledger = (
            db.query(CreditLedger)
            .filter(CreditLedger.user_id == user_id, CreditLedger.operation == CreditOperation.REFUND)
            .first()
        )
        assert ledger.source == CreditSource.MIXED
        assert ledger.overage_portion == 3

    def test_refund_topup_reverse_fifo(self, db):
        """Refund restores topup credits in reverse FIFO (most recent first)."""
        user_id = 43
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=20)
        cc = _make_cost_config("ai_conversation", credit_cost=10)

        # Two topup purchases: older fully consumed, newer partially consumed
        tp1 = _make_topup_purchase(user_id, credits_remaining=0, purchased_at=datetime(2025, 1, 1))
        tp1.credits_purchased = 15  # was 15, now 0 remaining
        tp2 = _make_topup_purchase(user_id, credits_remaining=20, purchased_at=datetime(2025, 2, 1))
        tp2.credits_purchased = 25  # was 25, now 20 remaining (5 consumed)

        db.add_all([plan, sub, cb, cc, tp1, tp2])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.refund_credits(user_id, "ai_conversation", quantity=1)

        # 10 credits refunded to topup: tp2 first (capacity=5), then tp1 (capacity=15, take 5)
        assert info.topup_balance == 30  # 20 + 10
        assert info.plan_balance == 0

        db.refresh(tp2)
        db.refresh(tp1)
        assert tp2.credits_remaining == 25  # restored 5 (back to full)
        assert tp1.credits_remaining == 5   # restored 5

    def test_refund_idempotency_with_refund_key(self, db):
        """Duplicate refund with same refund_key returns balance without double-refunding."""
        user_id = 44
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=95, topup_balance=0)
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)

        # First refund
        info1 = service.refund_credits(
            user_id, "ocr_scan", quantity=1,
            reason="ocr_processing_failed", refund_key="refund:doc_100",
        )
        assert info1.plan_balance == 100

        # Second refund with same key — idempotent
        info2 = service.refund_credits(
            user_id, "ocr_scan", quantity=1,
            reason="ocr_processing_failed", refund_key="refund:doc_100",
        )
        assert info2.plan_balance == 100  # no double refund

        # Only one REFUND ledger entry
        refund_count = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.REFUND,
            )
            .count()
        )
        assert refund_count == 1

    def test_refund_without_refund_key_allows_multiple(self, db):
        """Without refund_key, multiple refunds are allowed."""
        user_id = 45
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=90, topup_balance=0)
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)

        info1 = service.refund_credits(user_id, "ocr_scan", quantity=1)
        assert info1.plan_balance == 95

        info2 = service.refund_credits(user_id, "ocr_scan", quantity=1)
        assert info2.plan_balance == 100

    def test_refund_with_quantity(self, db):
        """Refund with quantity > 1 refunds cost * quantity."""
        user_id = 46
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=80, topup_balance=0)
        cc = _make_cost_config("transaction_entry", credit_cost=1)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.refund_credits(user_id, "transaction_entry", quantity=10)

        assert info.plan_balance == 90  # 80 + 10

    def test_refund_redis_cache_deleted(self, db):
        """Redis cache key is deleted after refund."""
        user_id = 47
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=95)
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        service = CreditService(db, redis_client=mock_redis)
        service.refund_credits(user_id, "ocr_scan")

        mock_redis.delete.assert_called_with(f"credit_balance:{user_id}")

    def test_refund_ledger_records_context(self, db):
        """Refund ledger records context_type, context_id, and reference_id."""
        user_id = 48
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=95)
        cc = _make_cost_config("ocr_scan", credit_cost=5, pricing_version=2)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        service.refund_credits(
            user_id, "ocr_scan",
            reason="ocr_service_timeout",
            context_type="document", context_id=77,
            refund_key="refund:doc_77",
        )

        ledger = (
            db.query(CreditLedger)
            .filter(CreditLedger.user_id == user_id, CreditLedger.operation == CreditOperation.REFUND)
            .first()
        )
        assert ledger.context_type == "document"
        assert ledger.context_id == 77
        assert ledger.reference_id == "refund:doc_77"
        assert ledger.reason == "ocr_service_timeout"
        assert ledger.pricing_version == 2

    def test_refund_unknown_operation_raises_value_error(self, db):
        """Refund with unknown operation raises ValueError."""
        user_id = 49
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        with pytest.raises(ValueError, match="No active CreditCostConfig"):
            service.refund_credits(user_id, "nonexistent_operation")

    def test_deduct_then_refund_round_trip(self, db):
        """Deduct then refund restores balance to original state."""
        user_id = 50
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=50)
        cc = _make_cost_config("ocr_scan", credit_cost=5)
        tp = _make_topup_purchase(user_id, credits_remaining=50)

        db.add_all([plan, sub, cb, cc, tp])
        db.commit()

        service = CreditService(db, redis_client=None)

        # Deduct
        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)
        assert result.balance_after.plan_balance == 95

        # Refund
        info = service.refund_credits(user_id, "ocr_scan", quantity=1)
        assert info.plan_balance == 100
        assert info.topup_balance == 50

    def test_deduct_mixed_then_refund_round_trip(self, db):
        """Deduct across plan+topup+overage, then refund restores all."""
        user_id = 51
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=2, topup_balance=1)
        cb.overage_enabled = True
        cc = _make_cost_config("ocr_scan", credit_cost=5)
        tp = _make_topup_purchase(user_id, credits_remaining=1)

        db.add_all([plan, sub, cb, cc, tp])
        db.commit()

        service = CreditService(db, redis_client=None)

        # Deduct: 2 from plan, 1 from topup, 2 from overage
        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)
        assert result.plan_deducted == 2
        assert result.topup_deducted == 1
        assert result.overage_portion == 2
        assert result.balance_after.plan_balance == 0
        assert result.balance_after.topup_balance == 0
        assert result.balance_after.overage_credits_used == 2

        # Refund: 2 from overage, 1 to topup, 2 to plan
        info = service.refund_credits(user_id, "ocr_scan", quantity=1)
        assert info.overage_credits_used == 0
        assert info.topup_balance == 1
        assert info.plan_balance == 2


# ---------------------------------------------------------------------------
# check_sufficient tests
# ---------------------------------------------------------------------------

class TestCheckSufficient:
    """Tests for CreditService.check_sufficient method."""

    def test_sufficient_balance_returns_true(self, db):
        """Returns True when plan + topup covers the cost."""
        user_id = 60
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=50)
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        assert service.check_sufficient(user_id, "ocr_scan") is True

    def test_insufficient_balance_overage_disabled_returns_false(self, db):
        """Returns False when balance insufficient and overage disabled."""
        user_id = 61
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=2, topup_balance=1)
        cb.overage_enabled = False
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        assert service.check_sufficient(user_id, "ocr_scan") is False

    def test_insufficient_balance_overage_enabled_allow_overage_true(self, db):
        """Returns True when balance insufficient but overage enabled and allow_overage=True."""
        user_id = 62
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=1, topup_balance=0)
        cb.overage_enabled = True
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        assert service.check_sufficient(user_id, "ocr_scan", allow_overage=True) is True

    def test_insufficient_balance_overage_enabled_allow_overage_false(self, db):
        """Returns False when balance insufficient, overage enabled, but allow_overage=False."""
        user_id = 63
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=1, topup_balance=0)
        cb.overage_enabled = True
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        assert service.check_sufficient(user_id, "ocr_scan", allow_overage=False) is False

    def test_unknown_operation_returns_false(self, db):
        """Returns False when operation has no active CreditCostConfig."""
        user_id = 64
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        assert service.check_sufficient(user_id, "nonexistent_operation") is False


# ---------------------------------------------------------------------------
# get_credit_costs tests
# ---------------------------------------------------------------------------

class TestGetCreditCosts:
    """Tests for CreditService.get_credit_costs method."""

    def test_returns_only_active_configs(self, db):
        """get_credit_costs returns only is_active=True configs."""
        cc1 = _make_cost_config("ocr_scan", credit_cost=5)
        cc2 = _make_cost_config("ai_conversation", credit_cost=10)
        cc3 = _make_cost_config("tax_calc", credit_cost=2)
        cc3.is_active = False  # inactive — should be excluded

        db.add_all([cc1, cc2, cc3])
        db.commit()

        service = CreditService(db, redis_client=None)
        costs = service.get_credit_costs()

        assert costs == {"ocr_scan": 5, "ai_conversation": 10}
        assert "tax_calc" not in costs

    def test_excludes_all_inactive_configs(self, db):
        """get_credit_costs excludes every inactive config."""
        cc1 = _make_cost_config("ocr_scan", credit_cost=5)
        cc1.is_active = False
        cc2 = _make_cost_config("ai_conversation", credit_cost=10)
        cc2.is_active = False

        db.add_all([cc1, cc2])
        db.commit()

        service = CreditService(db, redis_client=None)
        costs = service.get_credit_costs()

        assert costs == {}

    def test_returns_empty_dict_when_no_configs(self, db):
        """get_credit_costs returns empty dict when no CreditCostConfig records exist."""
        service = CreditService(db, redis_client=None)
        costs = service.get_credit_costs()

        assert costs == {}


# ---------------------------------------------------------------------------
# get_ledger tests
# ---------------------------------------------------------------------------

def _make_ledger_entry(user_id, credit_amount=-5, operation=CreditOperation.DEDUCTION, created_at=None):
    """Helper to create a CreditLedger entry for testing."""
    entry = CreditLedger()
    entry.user_id = user_id
    entry.operation = operation
    entry.operation_detail = "ocr_scan"
    entry.status = CreditLedgerStatus.SETTLED
    entry.credit_amount = credit_amount
    entry.source = CreditSource.PLAN
    entry.plan_balance_after = 100
    entry.topup_balance_after = 0
    entry.is_overage = False
    entry.overage_portion = 0
    entry.pricing_version = 1
    if created_at is not None:
        entry.created_at = created_at
    return entry


class TestGetLedger:
    """Tests for CreditService.get_ledger method."""

    def test_returns_records_in_created_at_desc_order(self, db):
        """get_ledger returns records ordered by created_at DESC."""
        user_id = 70
        e1 = _make_ledger_entry(user_id, created_at=datetime(2025, 1, 1))
        e2 = _make_ledger_entry(user_id, created_at=datetime(2025, 1, 3))
        e3 = _make_ledger_entry(user_id, created_at=datetime(2025, 1, 2))

        db.add_all([e1, e2, e3])
        db.commit()

        service = CreditService(db, redis_client=None)
        results = service.get_ledger(user_id)

        assert len(results) == 3
        assert results[0].created_at == datetime(2025, 1, 3)
        assert results[1].created_at == datetime(2025, 1, 2)
        assert results[2].created_at == datetime(2025, 1, 1)

    def test_respects_limit_parameter(self, db):
        """get_ledger returns at most `limit` records."""
        user_id = 71
        for i in range(5):
            db.add(_make_ledger_entry(user_id, created_at=datetime(2025, 1, i + 1)))
        db.commit()

        service = CreditService(db, redis_client=None)
        results = service.get_ledger(user_id, limit=3)

        assert len(results) == 3

    def test_respects_offset_parameter(self, db):
        """get_ledger skips `offset` records."""
        user_id = 72
        for i in range(5):
            db.add(_make_ledger_entry(user_id, created_at=datetime(2025, 1, i + 1)))
        db.commit()

        service = CreditService(db, redis_client=None)
        results = service.get_ledger(user_id, limit=50, offset=2)

        assert len(results) == 3
        # After skipping 2 newest (Jan 5, Jan 4), should get Jan 3, Jan 2, Jan 1
        assert results[0].created_at == datetime(2025, 1, 3)
        assert results[1].created_at == datetime(2025, 1, 2)
        assert results[2].created_at == datetime(2025, 1, 1)

    def test_returns_empty_list_when_no_records(self, db):
        """get_ledger returns empty list when user has no ledger entries."""
        user_id = 73
        service = CreditService(db, redis_client=None)
        results = service.get_ledger(user_id)

        assert results == []

    def test_only_returns_records_for_specified_user(self, db):
        """get_ledger only returns records belonging to the given user_id."""
        user_a = 74
        user_b = 75
        db.add(_make_ledger_entry(user_a, created_at=datetime(2025, 1, 1)))
        db.add(_make_ledger_entry(user_a, created_at=datetime(2025, 1, 2)))
        db.add(_make_ledger_entry(user_b, created_at=datetime(2025, 1, 3)))

        db.commit()

        service = CreditService(db, redis_client=None)
        results_a = service.get_ledger(user_a)
        results_b = service.get_ledger(user_b)

        assert len(results_a) == 2
        assert all(r.user_id == user_a for r in results_a)
        assert len(results_b) == 1
        assert results_b[0].user_id == user_b


# ---------------------------------------------------------------------------
# estimate_cost tests
# ---------------------------------------------------------------------------

class TestEstimateCost:
    """Tests for CreditService.estimate_cost method."""

    def test_sufficient_balance(self, db):
        """Sufficient natural balance: sufficient=True, sufficient_without_overage=True, would_use_overage=False."""
        user_id = 80
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=50)
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.estimate_cost(user_id, "ocr_scan")

        assert result.operation == "ocr_scan"
        assert result.cost == 5
        assert result.sufficient is True
        assert result.sufficient_without_overage is True
        assert result.would_use_overage is False

    def test_insufficient_balance_overage_disabled(self, db):
        """Insufficient balance, overage disabled: sufficient=False, would_use_overage=False."""
        user_id = 81
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=2, topup_balance=1)
        cb.overage_enabled = False
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.estimate_cost(user_id, "ocr_scan")

        assert result.cost == 5
        assert result.sufficient is False
        assert result.sufficient_without_overage is False
        assert result.would_use_overage is False

    def test_insufficient_balance_overage_enabled(self, db):
        """Insufficient balance, overage enabled: sufficient=True, would_use_overage=True."""
        user_id = 82
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=1, topup_balance=0)
        cb.overage_enabled = True
        cc = _make_cost_config("ocr_scan", credit_cost=5)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.estimate_cost(user_id, "ocr_scan")

        assert result.cost == 5
        assert result.sufficient is True
        assert result.sufficient_without_overage is False
        assert result.would_use_overage is True

    def test_unknown_operation_raises_value_error(self, db):
        """Unknown operation raises ValueError."""
        user_id = 83
        service = CreditService(db, redis_client=None)

        with pytest.raises(ValueError, match="No active CreditCostConfig"):
            service.estimate_cost(user_id, "nonexistent_operation")

    def test_cost_matches_credit_cost_times_quantity(self, db):
        """Cost calculation matches credit_cost * quantity."""
        user_id = 84
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=200, topup_balance=0)
        cc = _make_cost_config("transaction_entry", credit_cost=1)

        db.add_all([plan, sub, cb, cc])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.estimate_cost(user_id, "transaction_entry", quantity=25)

        assert result.cost == 25
        assert result.sufficient is True
        assert result.sufficient_without_overage is True
        assert result.would_use_overage is False


# ---------------------------------------------------------------------------
# set_overage_enabled tests
# ---------------------------------------------------------------------------

class TestSetOverageEnabled:
    """Tests for CreditService.set_overage_enabled method."""

    def test_free_plan_enable_raises_overage_not_available(self, db):
        """Free plan user enabling overage raises OverageNotAvailableError."""
        user_id = 90
        plan = _make_plan(plan_type=PlanType.FREE, monthly_credits=50, overage_price=None)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=50, topup_balance=0)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        with pytest.raises(OverageNotAvailableError):
            service.set_overage_enabled(user_id, enabled=True)

    def test_free_plan_disable_succeeds(self, db):
        """Free plan user disabling overage succeeds without error."""
        user_id = 91
        plan = _make_plan(plan_type=PlanType.FREE, monthly_credits=50, overage_price=None)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=50, topup_balance=0)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.set_overage_enabled(user_id, enabled=False)

        assert info.overage_enabled is False

    def test_plus_plan_enable_succeeds(self, db):
        """Plus plan user enabling overage sets overage_enabled=True."""
        user_id = 92
        plan = _make_plan(plan_type=PlanType.PLUS, monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.set_overage_enabled(user_id, enabled=True)

        assert info.overage_enabled is True

    def test_plus_plan_disable_succeeds(self, db):
        """Plus plan user disabling overage sets overage_enabled=False."""
        user_id = 93
        plan = _make_plan(plan_type=PlanType.PLUS, monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)
        cb.overage_enabled = True

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.set_overage_enabled(user_id, enabled=False)

        assert info.overage_enabled is False

    def test_unpaid_overage_enable_raises_suspended_even_on_first_failed_period(self, db):
        """A currently unpaid overage invoice blocks re-enabling overage immediately."""
        user_id = 931
        plan = _make_plan(plan_type=PlanType.PLUS, monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)
        cb.unpaid_overage_periods = 1
        cb.has_unpaid_overage = True
        cb.overage_enabled = False

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        with pytest.raises(OverageSuspendedError):
            service.set_overage_enabled(user_id, enabled=True)

    def test_unpaid_overage_periods_gte_2_enable_raises_suspended(self, db):
        """User with unpaid_overage_periods >= 2 enabling overage raises OverageSuspendedError."""
        user_id = 94
        plan = _make_plan(plan_type=PlanType.PLUS, monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)
        cb.unpaid_overage_periods = 2
        cb.has_unpaid_overage = True

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        with pytest.raises(OverageSuspendedError):
            service.set_overage_enabled(user_id, enabled=True)

    def test_unpaid_overage_periods_gte_2_disable_succeeds(self, db):
        """User with unpaid_overage_periods >= 2 can still disable overage."""
        user_id = 95
        plan = _make_plan(plan_type=PlanType.PLUS, monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=500, topup_balance=0)
        cb.overage_enabled = True
        cb.unpaid_overage_periods = 3
        cb.has_unpaid_overage = True

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        info = service.set_overage_enabled(user_id, enabled=False)

        assert info.overage_enabled is False


# ---------------------------------------------------------------------------
# process_period_end tests
# ---------------------------------------------------------------------------

class TestProcessPeriodEnd:
    """Tests for CreditService.process_period_end method."""

    def test_basic_monthly_reset(self, db):
        """plan_balance resets to monthly_credits, overage_credits_used = 0."""
        user_id = 100
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=50, topup_balance=30)
        cb.overage_credits_used = 0

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.process_period_end(user_id)

        assert result.new_plan_balance == 500
        assert result.overage_settled is False
        assert result.overage_amount is None
        assert result.stripe_invoice_id is None
        assert result.topup_expired == 0

        db.refresh(cb)
        assert cb.plan_balance == 500
        assert cb.overage_credits_used == 0

    def test_overage_settlement(self, db):
        """Overage amount calculated correctly when overage_credits_used > 0."""
        user_id = 101
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=0)
        cb.overage_enabled = True
        cb.overage_credits_used = 47

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.process_period_end(user_id)

        assert result.overage_settled is True
        assert result.overage_amount == Decimal("0.04") * 47  # 1.88
        assert result.stripe_invoice_id is None  # v1 stub
        assert result.new_plan_balance == 500

        db.refresh(cb)
        assert cb.overage_credits_used == 0

    def test_overage_settlement_creates_stripe_invoice_when_customer_present(self, db):
        """Stripe invoice ID is recorded when the subscription is Stripe-backed."""
        user_id = 110
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        sub.stripe_customer_id = "cus_test_123"
        sub.stripe_subscription_id = "sub_test_123"
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=0)
        cb.overage_enabled = True
        cb.overage_credits_used = 47

        db.add_all([plan, sub, cb])
        db.commit()

        with patch.object(
            __import__("app.core.config", fromlist=["settings"]).settings,
            "STRIPE_SECRET_KEY",
            "sk_test_123",
        ), patch(
            "app.services.stripe_payment_service.StripePaymentService.create_overage_invoice",
            return_value={"invoice_id": "in_test_123", "status": "open"},
        ) as mock_create_invoice:
            service = CreditService(db, redis_client=None)
            result = service.process_period_end(user_id)

        mock_create_invoice.assert_called_once_with(
            user_id=user_id,
            overage_amount=Decimal("1.88"),
            overage_credits_used=47,
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 2, 1),
        )
        assert result.stripe_invoice_id == "in_test_123"

        settlement = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.OVERAGE_SETTLEMENT,
            )
            .first()
        )
        assert settlement is not None
        assert settlement.reference_id == "in_test_123"

    def test_overage_settlement_skips_stripe_without_customer(self, db):
        """Users without a Stripe customer keep local settlement but skip remote invoicing."""
        user_id = 111
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=0)
        cb.overage_enabled = True
        cb.overage_credits_used = 12

        db.add_all([plan, sub, cb])
        db.commit()

        with patch(
            "app.services.stripe_payment_service.StripePaymentService.create_overage_invoice"
        ) as mock_create_invoice:
            service = CreditService(db, redis_client=None)
            result = service.process_period_end(user_id)

        mock_create_invoice.assert_not_called()
        assert result.overage_settled is True
        assert result.stripe_invoice_id is None

    def test_expired_topup_cleanup(self, db):
        """Expired TopupPurchase marked is_expired=True, topup_balance reduced."""
        from datetime import timedelta

        user_id = 102
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=80)

        # Expired topup: purchased 13 months ago, expired 1 month ago
        tp_expired = _make_topup_purchase(
            user_id, credits_remaining=30,
            purchased_at=datetime(2024, 1, 1),
            expires_at=datetime(2025, 1, 1),  # already expired
        )

        db.add_all([plan, sub, cb, tp_expired])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.process_period_end(user_id)

        assert result.topup_expired == 30

        db.refresh(tp_expired)
        assert tp_expired.is_expired is True

        db.refresh(cb)
        assert cb.topup_balance == 50  # 80 - 30

    def test_non_expired_topup_preserved(self, db):
        """TopupPurchase with future expires_at not affected."""
        from datetime import timedelta

        user_id = 103
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=50)

        # Non-expired topup: expires far in the future
        tp_valid = _make_topup_purchase(
            user_id, credits_remaining=50,
            purchased_at=datetime(2025, 6, 1),
            expires_at=datetime.utcnow() + timedelta(days=365),  # 1 year from now
        )

        db.add_all([plan, sub, cb, tp_valid])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.process_period_end(user_id)

        assert result.topup_expired == 0

        db.refresh(tp_valid)
        assert tp_valid.is_expired is False
        assert tp_valid.credits_remaining == 50

        db.refresh(cb)
        assert cb.topup_balance == 50  # unchanged

    def test_ledger_entries_created(self, db):
        """Ledger entries created for overage settlement, topup expiry, and monthly reset."""
        from datetime import timedelta

        user_id = 104
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=10, topup_balance=20)
        cb.overage_enabled = True
        cb.overage_credits_used = 10

        tp_expired = _make_topup_purchase(
            user_id, credits_remaining=15,
            purchased_at=datetime(2024, 1, 1),
            expires_at=datetime(2025, 1, 1),
        )

        db.add_all([plan, sub, cb, tp_expired])
        db.commit()

        service = CreditService(db, redis_client=None)
        service.process_period_end(user_id)

        ledgers = (
            db.query(CreditLedger)
            .filter(CreditLedger.user_id == user_id)
            .order_by(CreditLedger.id.asc())
            .all()
        )

        # Should have 3 ledger entries: OVERAGE_SETTLEMENT, TOPUP_EXPIRY, MONTHLY_RESET
        ops = [l.operation for l in ledgers]
        assert CreditOperation.OVERAGE_SETTLEMENT in ops
        assert CreditOperation.TOPUP_EXPIRY in ops
        assert CreditOperation.MONTHLY_RESET in ops

        # All should be settled
        for l in ledgers:
            assert l.status == CreditLedgerStatus.SETTLED

    def test_subscription_period_dates_updated(self, db):
        """Subscription period_start and period_end advanced by 1 month."""
        user_id = 105
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        sub.current_period_start = datetime(2025, 1, 1)
        sub.current_period_end = datetime(2025, 2, 1)
        cb = _make_credit_balance(user_id, plan_balance=100)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        service.process_period_end(user_id)

        db.refresh(sub)
        assert sub.current_period_start == datetime(2025, 2, 1)
        assert sub.current_period_end == datetime(2025, 3, 1)

    def test_redis_cache_deleted(self, db):
        """Redis cache key is deleted after process_period_end."""
        user_id = 106
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100)

        db.add_all([plan, sub, cb])
        db.commit()

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        service = CreditService(db, redis_client=mock_redis)
        service.process_period_end(user_id)

        mock_redis.delete.assert_called_with(f"credit_balance:{user_id}")

    def test_no_overage_when_zero_credits_used(self, db):
        """No overage settlement when overage_credits_used is 0."""
        user_id = 107
        plan = _make_plan(monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=200)
        cb.overage_enabled = True
        cb.overage_credits_used = 0

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.process_period_end(user_id)

        assert result.overage_settled is False
        assert result.overage_amount is None

        # No OVERAGE_SETTLEMENT ledger entry
        overage_ledgers = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.OVERAGE_SETTLEMENT,
            )
            .all()
        )
        assert len(overage_ledgers) == 0

    def test_multiple_expired_topups(self, db):
        """Multiple expired topups are all cleaned up correctly."""
        user_id = 108
        plan = _make_plan(monthly_credits=500)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=70)

        tp1 = _make_topup_purchase(
            user_id, credits_remaining=20,
            purchased_at=datetime(2023, 6, 1),
            expires_at=datetime(2024, 6, 1),
        )
        tp2 = _make_topup_purchase(
            user_id, credits_remaining=10,
            purchased_at=datetime(2023, 12, 1),
            expires_at=datetime(2024, 12, 1),
        )

        db.add_all([plan, sub, cb, tp1, tp2])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.process_period_end(user_id)

        assert result.topup_expired == 30  # 20 + 10

        db.refresh(tp1)
        db.refresh(tp2)
        assert tp1.is_expired is True
        assert tp2.is_expired is True

        db.refresh(cb)
        assert cb.topup_balance == 40  # 70 - 30

    def test_monthly_reset_ledger_has_correct_amount(self, db):
        """MONTHLY_RESET ledger entry has credit_amount = monthly_credits."""
        user_id = 109
        plan = _make_plan(monthly_credits=2000)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=50)

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        service.process_period_end(user_id)

        reset_ledger = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.MONTHLY_RESET,
            )
            .first()
        )
        assert reset_ledger is not None
        assert reset_ledger.credit_amount == 2000
        assert reset_ledger.plan_balance_after == 2000
        assert reset_ledger.source == CreditSource.PLAN


# ---------------------------------------------------------------------------
# handle_plan_change_overage_impact tests
# ---------------------------------------------------------------------------

class TestHandlePlanChangeOverageImpact:
    """Tests for CreditService.handle_plan_change_overage_impact method."""

    def test_downgrade_to_free_disables_overage(self, db):
        """Downgrade to Free: overage_enabled becomes False, overage_credits_used reset."""
        user_id = 200
        plan = _make_plan(plan_type=PlanType.PLUS, monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=100, topup_balance=20)
        cb.overage_enabled = True
        cb.overage_credits_used = 0

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.handle_plan_change_overage_impact(
            user_id, PlanType.PLUS, PlanType.FREE
        )

        assert result.overage_enabled is False
        assert result.overage_credits_used == 0

        # Verify DB state
        balance = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        assert balance.overage_enabled is False

    def test_downgrade_to_free_settles_overage(self, db):
        """Downgrade to Free with overage_credits_used > 0: OVERAGE_SETTLEMENT ledger created."""
        user_id = 201
        plan = _make_plan(plan_type=PlanType.PLUS, monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=0, topup_balance=0)
        cb.overage_enabled = True
        cb.overage_credits_used = 25

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.handle_plan_change_overage_impact(
            user_id, PlanType.PLUS, PlanType.FREE
        )

        assert result.overage_enabled is False
        assert result.overage_credits_used == 0

        # Verify OVERAGE_SETTLEMENT ledger entry
        settlement = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.OVERAGE_SETTLEMENT,
            )
            .first()
        )
        assert settlement is not None
        assert settlement.credit_amount == -25
        assert settlement.is_overage is True
        assert settlement.overage_portion == 25
        assert settlement.source == CreditSource.OVERAGE
        assert "downgrade" in settlement.reason.lower()

    def test_upgrade_free_to_plus_preserves_overage_false(self, db):
        """Upgrade from Free to Plus: overage_enabled stays False if it was False."""
        user_id = 202
        plan = _make_plan(plan_type=PlanType.FREE, monthly_credits=50, overage_price=None)
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=50, topup_balance=0)
        cb.overage_enabled = False

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.handle_plan_change_overage_impact(
            user_id, PlanType.FREE, PlanType.PLUS
        )

        assert result.overage_enabled is False

        # No settlement ledger should exist
        settlement_count = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.OVERAGE_SETTLEMENT,
            )
            .count()
        )
        assert settlement_count == 0

    def test_upgrade_plus_to_pro_preserves_overage_true(self, db):
        """Upgrade from Plus to Pro: overage_enabled stays True if it was True."""
        user_id = 203
        plan = _make_plan(plan_type=PlanType.PLUS, monthly_credits=500, overage_price=Decimal("0.04"))
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id, plan_balance=200, topup_balance=0)
        cb.overage_enabled = True
        cb.overage_credits_used = 10

        db.add_all([plan, sub, cb])
        db.commit()

        service = CreditService(db, redis_client=None)
        result = service.handle_plan_change_overage_impact(
            user_id, PlanType.PLUS, PlanType.PRO
        )

        assert result.overage_enabled is True
        # overage_credits_used should be preserved on upgrade
        assert result.overage_credits_used == 10

        # No settlement ledger should exist
        settlement_count = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.OVERAGE_SETTLEMENT,
            )
            .count()
        )
        assert settlement_count == 0


# ---------------------------------------------------------------------------
# Concurrent deduction safety tests (Task 8.1)
# ---------------------------------------------------------------------------

class TestConcurrentDeductionSafety:
    """Tests verifying concurrent deduction safety.

    Since SQLite doesn't support true concurrent transactions, these tests
    verify the *logic correctness* of both the fast path (atomic UPDATE ...
    WHERE plan_balance >= cost) and the slow path (SELECT FOR UPDATE), and
    ensure that sequential deductions with limited balance never drive the
    balance negative.

    Validates requirements: 8.1, 8.2, 8.3, 8.4
    """

    # -- helpers ----------------------------------------------------------

    def _setup(self, db, plan_balance=100, topup_balance=0, overage_enabled=False):
        """Create plan, subscription, credit balance, and cost config."""
        user_id = 800
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
            topup_balance=topup_balance,
            overage_enabled=overage_enabled,
            overage_credits_used=0,
            has_unpaid_overage=False,
            unpaid_overage_periods=0,
        )
        db.add(cb)

        cc = CreditCostConfig(
            operation="ocr_scan",
            credit_cost=5,
            pricing_version=1,
            is_active=True,
            description="OCR scan",
        )
        db.add(cc)

        if topup_balance > 0:
            from datetime import timedelta
            tp = TopupPurchase(
                user_id=user_id,
                credits_purchased=topup_balance,
                credits_remaining=topup_balance,
                price_paid=Decimal("4.99"),
                purchased_at=datetime(2025, 1, 1),
                expires_at=datetime(2025, 1, 1) + timedelta(days=365),
                is_expired=False,
            )
            db.add(tp)

        db.commit()
        return user_id

    # -- fast path tests --------------------------------------------------

    def test_fast_path_atomic_update_succeeds_when_balance_sufficient(self, db):
        """Fast path: atomic UPDATE succeeds when plan_balance >= cost.

        The UPDATE ... WHERE plan_balance >= cost should affect exactly 1 row
        and deduct only from plan_balance.
        """
        user_id = self._setup(db, plan_balance=50)
        service = CreditService(db, redis_client=None)

        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert result.success is True
        assert result.plan_deducted == 5
        assert result.topup_deducted == 0
        assert result.overage_portion == 0
        assert result.balance_after.plan_balance == 45

    def test_fast_path_falls_through_when_balance_insufficient(self, db):
        """Fast path: atomic UPDATE affects 0 rows when plan_balance < cost,
        causing the service to fall through to the slow path.
        """
        user_id = self._setup(db, plan_balance=3, topup_balance=20)
        service = CreditService(db, redis_client=None)

        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        # Should have used slow path: plan + topup
        assert result.success is True
        assert result.plan_deducted == 3
        assert result.topup_deducted == 2
        assert result.total_deducted == 5
        assert result.balance_after.plan_balance == 0
        assert result.balance_after.topup_balance == 18

    def test_fast_path_exact_balance_succeeds(self, db):
        """Fast path: UPDATE succeeds when plan_balance == cost exactly."""
        user_id = self._setup(db, plan_balance=5)
        service = CreditService(db, redis_client=None)

        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert result.success is True
        assert result.plan_deducted == 5
        assert result.balance_after.plan_balance == 0

    # -- slow path tests --------------------------------------------------

    def test_slow_path_cross_balance_allocation(self, db):
        """Slow path: correctly allocates across plan + topup balances."""
        user_id = self._setup(db, plan_balance=2, topup_balance=50)
        service = CreditService(db, redis_client=None)

        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert result.success is True
        assert result.plan_deducted == 2
        assert result.topup_deducted == 3
        assert result.overage_portion == 0
        assert result.balance_after.plan_balance == 0
        assert result.balance_after.topup_balance == 47

    def test_slow_path_with_overage_fallback(self, db):
        """Slow path: when plan + topup insufficient, overage absorbs remainder."""
        user_id = self._setup(db, plan_balance=1, topup_balance=2, overage_enabled=True)
        service = CreditService(db, redis_client=None)

        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert result.success is True
        assert result.plan_deducted == 1
        assert result.topup_deducted == 2
        assert result.overage_portion == 2
        assert result.total_deducted == 5
        assert result.balance_after.plan_balance == 0
        assert result.balance_after.topup_balance == 0
        assert result.balance_after.overage_credits_used == 2

    def test_slow_path_insufficient_no_overage_raises(self, db):
        """Slow path: raises InsufficientCreditsError when all balances exhausted
        and overage is disabled.
        """
        user_id = self._setup(db, plan_balance=1, topup_balance=2, overage_enabled=False)
        service = CreditService(db, redis_client=None)

        with pytest.raises(InsufficientCreditsError) as exc_info:
            service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert exc_info.value.required == 5
        assert exc_info.value.available == 3

    # -- sequential deduction safety (simulating concurrency) -------------

    def test_sequential_deductions_one_succeeds_one_fails(self, db):
        """Two sequential deductions with limited balance: first succeeds,
        second raises InsufficientCreditsError. Balance never goes negative.
        """
        user_id = self._setup(db, plan_balance=7, topup_balance=0, overage_enabled=False)
        service = CreditService(db, redis_client=None)

        # First deduction: 5 credits — should succeed (7 >= 5)
        result1 = service.check_and_deduct(user_id, "ocr_scan", quantity=1)
        assert result1.success is True
        assert result1.balance_after.plan_balance == 2

        # Second deduction: 5 credits — should fail (2 < 5)
        with pytest.raises(InsufficientCreditsError) as exc_info:
            service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert exc_info.value.required == 5
        assert exc_info.value.available == 2

        # Verify balance never went negative
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        assert cb.plan_balance >= 0
        assert cb.topup_balance >= 0

    def test_multiple_deductions_exhaust_balance_gracefully(self, db):
        """Multiple deductions exhaust balance; balance stays >= 0 throughout."""
        user_id = self._setup(db, plan_balance=25, topup_balance=0, overage_enabled=False)
        service = CreditService(db, redis_client=None)

        success_count = 0
        fail_count = 0

        for _ in range(10):
            try:
                result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)
                assert result.success is True
                success_count += 1
            except InsufficientCreditsError:
                fail_count += 1

        # 25 credits / 5 per deduction = exactly 5 successes
        assert success_count == 5
        assert fail_count == 5

        # Final balance must be exactly 0
        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        assert cb.plan_balance == 0
        assert cb.topup_balance == 0

    def test_multiple_deductions_cross_balance_never_negative(self, db):
        """Deductions spanning plan + topup never drive either balance negative."""
        user_id = self._setup(db, plan_balance=8, topup_balance=12, overage_enabled=False)
        service = CreditService(db, redis_client=None)

        success_count = 0
        fail_count = 0

        for _ in range(10):
            try:
                result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)
                assert result.success is True
                success_count += 1

                # After every deduction, verify non-negative invariant
                cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
                db.refresh(cb)
                assert cb.plan_balance >= 0, f"plan_balance went negative: {cb.plan_balance}"
                assert cb.topup_balance >= 0, f"topup_balance went negative: {cb.topup_balance}"
            except InsufficientCreditsError:
                fail_count += 1

        # Total available = 8 + 12 = 20 credits, cost = 5 each → 4 successes
        assert success_count == 4
        assert fail_count == 6

        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        assert cb.plan_balance == 0
        assert cb.topup_balance == 0

    def test_deductions_with_overage_never_negative_natural_balance(self, db):
        """With overage enabled, plan + topup hit 0 and overage absorbs the rest.
        Natural balances (plan, topup) never go negative.
        """
        user_id = self._setup(db, plan_balance=12, topup_balance=0, overage_enabled=True)
        service = CreditService(db, redis_client=None)

        results = []
        for _ in range(5):
            result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)
            assert result.success is True
            results.append(result)

        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        assert cb.plan_balance >= 0
        assert cb.topup_balance >= 0

        # 12 plan credits / 5 per deduction:
        #   deduction 1: plan 12→7 (fast path)
        #   deduction 2: plan 7→2  (fast path)
        #   deduction 3: plan 2→0, overage 3 (slow path)
        #   deduction 4: plan 0, overage +5 (slow path)
        #   deduction 5: plan 0, overage +5 (slow path)
        assert cb.plan_balance == 0
        assert cb.overage_credits_used == 13  # 3 + 5 + 5

    def test_ledger_count_matches_successful_deductions(self, db):
        """Each successful deduction produces exactly one DEDUCTION ledger entry."""
        user_id = self._setup(db, plan_balance=15, topup_balance=0, overage_enabled=False)
        service = CreditService(db, redis_client=None)

        success_count = 0
        for _ in range(5):
            try:
                service.check_and_deduct(user_id, "ocr_scan", quantity=1)
                success_count += 1
            except InsufficientCreditsError:
                pass

        assert success_count == 3  # 15 / 5 = 3

        ledger_count = (
            db.query(CreditLedger)
            .filter(
                CreditLedger.user_id == user_id,
                CreditLedger.operation == CreditOperation.DEDUCTION,
            )
            .count()
        )
        assert ledger_count == success_count

    def test_fast_path_rowcount_zero_triggers_slow_path(self, db):
        """Verify that when the fast-path UPDATE affects 0 rows (plan_balance < cost),
        the slow path is entered and correctly handles the deduction.
        """
        # plan_balance=4 < cost=5 → fast path UPDATE WHERE plan_balance >= 5 → rowcount=0
        user_id = self._setup(db, plan_balance=4, topup_balance=10)
        service = CreditService(db, redis_client=None)

        result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)

        assert result.success is True
        # Slow path should use plan(4) + topup(1)
        assert result.plan_deducted == 4
        assert result.topup_deducted == 1
        assert result.balance_after.plan_balance == 0
        assert result.balance_after.topup_balance == 9

    def test_balance_conservation_across_deductions(self, db):
        """Total credits consumed + remaining balance == initial balance."""
        initial_plan = 30
        initial_topup = 20
        user_id = self._setup(
            db, plan_balance=initial_plan, topup_balance=initial_topup, overage_enabled=False
        )
        service = CreditService(db, redis_client=None)

        total_deducted = 0
        for _ in range(20):
            try:
                result = service.check_and_deduct(user_id, "ocr_scan", quantity=1)
                total_deducted += result.total_deducted
            except InsufficientCreditsError:
                pass

        cb = db.query(CreditBalance).filter(CreditBalance.user_id == user_id).first()
        remaining = cb.plan_balance + cb.topup_balance

        assert total_deducted + remaining == initial_plan + initial_topup
