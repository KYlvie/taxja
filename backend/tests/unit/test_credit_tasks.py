from datetime import datetime
from decimal import Decimal

from app.models.credit_balance import CreditBalance
from app.models.plan import Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.tasks.credit_tasks import (
    handle_overage_invoice_failed,
    handle_overage_invoice_paid,
)


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
    cb.overage_enabled = True
    cb.overage_credits_used = 0
    cb.has_unpaid_overage = False
    cb.unpaid_overage_periods = 0
    cb.updated_at = datetime.utcnow()
    return cb


class TestCreditTasks:
    def test_failed_overage_invoice_disables_overage_immediately(self, db):
        user_id = 400
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id)

        db.add_all([plan, sub, cb])
        db.commit()

        result = handle_overage_invoice_failed(
            db,
            {"metadata": {"type": "overage_settlement", "user_id": str(user_id)}},
        )

        db.refresh(cb)
        assert result["status"] == "processed"
        assert result["unpaid_overage_periods"] == 1
        assert cb.has_unpaid_overage is True
        assert cb.unpaid_overage_periods == 1
        assert cb.overage_enabled is False

    def test_failed_overage_invoice_does_not_double_increment_same_incident(self, db):
        user_id = 401
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id)
        cb.has_unpaid_overage = True
        cb.unpaid_overage_periods = 1
        cb.overage_enabled = False

        db.add_all([plan, sub, cb])
        db.commit()

        result = handle_overage_invoice_failed(
            db,
            {"metadata": {"type": "overage_settlement", "user_id": str(user_id)}},
        )

        db.refresh(cb)
        assert result["unpaid_overage_periods"] == 1
        assert cb.unpaid_overage_periods == 1
        assert cb.overage_enabled is False

    def test_paid_overage_invoice_clears_unpaid_and_reenables_overage(self, db):
        user_id = 402
        plan = _make_plan()
        sub = _make_subscription(user_id, plan)
        cb = _make_credit_balance(user_id)
        cb.has_unpaid_overage = True
        cb.unpaid_overage_periods = 1
        cb.overage_enabled = False

        db.add_all([plan, sub, cb])
        db.commit()

        result = handle_overage_invoice_paid(
            db,
            {"metadata": {"type": "overage_settlement", "user_id": str(user_id)}},
        )

        db.refresh(cb)
        assert result["status"] == "processed"
        assert result["overage_enabled"] is True
        assert cb.has_unpaid_overage is False
        assert cb.unpaid_overage_periods == 0
        assert cb.overage_enabled is True
