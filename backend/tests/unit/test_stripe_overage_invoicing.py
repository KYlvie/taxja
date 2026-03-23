from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services import stripe_payment_service as stripe_payment_service_module
from app.services.stripe_payment_service import StripePaymentService


class TestStripeOverageInvoicing:
    def setup_method(self):
        self.mock_db = Mock()
        self.service = StripePaymentService(self.mock_db)

    @patch("app.services.stripe_payment_service.stripe.Invoice.finalize_invoice")
    @patch("app.services.stripe_payment_service.stripe.InvoiceItem.create")
    @patch("app.services.stripe_payment_service.stripe.Invoice.create")
    def test_create_overage_invoice_uses_product_id(
        self,
        mock_invoice_create,
        mock_invoice_item_create,
        mock_finalize_invoice,
    ):
        user = User(id=1, email="billing@example.com")
        subscription = Subscription(
            id=1,
            user_id=1,
            plan_id=2,
            status=SubscriptionStatus.ACTIVE,
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123",
            current_period_start=datetime(2025, 1, 1),
            current_period_end=datetime(2025, 2, 1),
        )

        user_query = Mock()
        user_query.filter.return_value.first.return_value = user
        subscription_query = Mock()
        subscription_query.filter.return_value.order_by.return_value.first.return_value = (
            subscription
        )
        self.mock_db.query.side_effect = [user_query, subscription_query]

        draft_invoice = MagicMock()
        draft_invoice.id = "in_draft_123"
        mock_invoice_create.return_value = draft_invoice

        finalized_invoice = MagicMock()
        finalized_invoice.id = "in_final_123"
        finalized_invoice.status = "open"
        mock_finalize_invoice.return_value = finalized_invoice

        with patch.object(
            stripe_payment_service_module.settings,
            "STRIPE_SECRET_KEY",
            "sk_test_123",
        ), patch.object(
            stripe_payment_service_module.settings,
            "STRIPE_OVERAGE_PRODUCT_ID",
            "prod_test_overage",
        ):
            result = self.service.create_overage_invoice(
                user_id=1,
                overage_amount=Decimal("1.88"),
                overage_credits_used=47,
                period_start=datetime(2025, 1, 1),
                period_end=datetime(2025, 2, 1),
            )

        assert result["invoice_id"] == "in_final_123"
        mock_invoice_create.assert_called_once()
        expected_period = {
            "start": int(datetime(2025, 1, 1).timestamp()),
            "end": int(datetime(2025, 2, 1).timestamp()),
        }
        mock_invoice_item_create.assert_called_once_with(
            customer="cus_test_123",
            invoice="in_draft_123",
            description="Taxja overage settlement (2025-01-01 to 2025-02-01, 47 credits)",
            quantity=1,
            metadata={
                "type": "overage_settlement",
                "user_id": "1",
                "overage_credits": "47",
                "overage_amount": "1.88",
                "period_start": "2025-01-01T00:00:00",
                "period_end": "2025-02-01T00:00:00",
            },
            period=expected_period,
            price_data={
                "currency": "eur",
                "product": "prod_test_overage",
                "unit_amount": 188,
            },
        )
        mock_finalize_invoice.assert_called_once_with("in_draft_123", auto_advance=True)

    @patch("app.tasks.credit_tasks.handle_overage_invoice_paid")
    def test_payment_succeeded_routes_to_overage_helper(self, mock_handle_paid):
        mock_handle_paid.return_value = {"status": "processed", "user_id": 1}

        result = self.service._on_payment_succeeded(
            {
                "data": {
                    "object": {
                        "metadata": {"type": "overage_settlement", "user_id": "1"},
                    }
                }
            }
        )

        mock_handle_paid.assert_called_once()
        self.mock_db.commit.assert_called_once()
        assert result["action"] == "overage_payment_confirmed"

    @patch("app.tasks.credit_tasks.handle_overage_invoice_failed")
    def test_payment_failed_routes_to_overage_helper(self, mock_handle_failed):
        mock_handle_failed.return_value = {
            "status": "processed",
            "user_id": 1,
            "unpaid_overage_periods": 1,
        }

        result = self.service._on_payment_failed(
            {
                "data": {
                    "object": {
                        "metadata": {"type": "overage_settlement", "user_id": "1"},
                    }
                }
            }
        )

        mock_handle_failed.assert_called_once()
        self.mock_db.commit.assert_called_once()
        assert result["action"] == "overage_payment_failed"
