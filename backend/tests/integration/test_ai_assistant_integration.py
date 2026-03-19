"""
Integration tests for the current AI assistant API contracts.

These tests are aligned to the implemented endpoints and orchestration flow:
- /api/v1/ai/chat
- /api/v1/ai/history
- /api/v1/ai/chat-with-file

They exercise current source-of-truth behavior:
- feature gating via credits
- credit deduction headers
- chat-history persistence
- file-chat context building
- current orchestrator boundary instead of legacy ai_assistant_service mocks
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.api.v1.endpoints.ai_assistant import DISCLAIMERS
from app.models.chat_message import ChatMessage, MessageRole
from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.plan import BillingCycle, Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services.ai_orchestrator import OrchestratorResponse, UserIntent


def _assistant_text(language: str, body: str) -> str:
    return body + DISCLAIMERS.get(language, DISCLAIMERS["de"])


def _seed_ai_access(db, user: User) -> None:
    """Provision AI feature access via current plan + credit contracts."""
    now = datetime.utcnow()

    pro_plan = Plan(
        plan_type=PlanType.PRO,
        name="Pro",
        monthly_price=Decimal("9.90"),
        yearly_price=Decimal("99.00"),
        features={"ai_assistant": True},
        quotas={"ai_conversations": -1},
        monthly_credits=100,
        overage_price_per_credit=Decimal("0.0500"),
    )
    db.add(pro_plan)
    db.flush()

    subscription = Subscription(
        user_id=user.id,
        plan_id=pro_plan.id,
        status=SubscriptionStatus.ACTIVE,
        billing_cycle=BillingCycle.MONTHLY,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db.add(subscription)
    db.flush()

    user.subscription_id = subscription.id

    db.add(
        CreditCostConfig(
            operation="ai_conversation",
            credit_cost=10,
            description="AI conversation",
            pricing_version=1,
            is_active=True,
        )
    )
    db.add(
        CreditBalance(
            user_id=user.id,
            plan_balance=100,
            topup_balance=0,
            overage_enabled=False,
            overage_credits_used=0,
            has_unpaid_overage=False,
            unpaid_overage_periods=0,
        )
    )
    db.commit()


@pytest.fixture
def ai_enabled_user(db, test_user):
    user = db.query(User).filter(User.email == test_user["email"]).first()
    _seed_ai_access(db, user)
    db.refresh(user)
    return user


@pytest.fixture
def ai_authenticated_client(client, test_user, ai_enabled_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {token}",
    }
    return client


class TestAIChatMessageFlow:
    """Current AI chat behavior."""

    @patch("app.services.ai_orchestrator.AIOrchestrator.handle_message")
    def test_send_chat_message_and_get_response(
        self,
        mock_handle,
        ai_authenticated_client,
        db,
        ai_enabled_user,
    ):
        mock_handle.return_value = OrchestratorResponse(
            text=_assistant_text(
                "en",
                "This is a test AI response about Austrian taxes.",
            ),
            intent=UserIntent.TAX_QA,
            suggestions=["Ask about deductions"],
        )

        response = ai_authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "What is the income tax rate in Austria?",
                "language": "en",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "This is a test AI response" in data["message"]
        assert "Disclaimer" in data["message"]
        assert data["intent"] == "tax_qa"
        assert "message_id" in data
        assert "timestamp" in data
        assert response.headers["X-Credits-Remaining"] == "90"

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == ai_enabled_user.id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
        assert len(messages) == 2
        assert messages[0].role == MessageRole.USER
        assert messages[0].content == "What is the income tax rate in Austria?"
        assert messages[1].role == MessageRole.ASSISTANT
        assert "This is a test AI response" in messages[1].content

        balance = (
            db.query(CreditBalance)
            .filter(CreditBalance.user_id == ai_enabled_user.id)
            .first()
        )
        assert balance.plan_balance == 90
        mock_handle.assert_called_once()

    @patch("app.services.ai_orchestrator.AIOrchestrator.handle_message")
    def test_get_conversation_history(
        self,
        mock_handle,
        ai_authenticated_client,
    ):
        mock_handle.side_effect = [
            OrchestratorResponse(
                text=_assistant_text("en", "First answer"),
                intent=UserIntent.TAX_QA,
            ),
            OrchestratorResponse(
                text=_assistant_text("en", "Second answer"),
                intent=UserIntent.TAX_QA,
            ),
        ]

        first = ai_authenticated_client.post(
            "/api/v1/ai/chat",
            json={"message": "First question", "language": "en"},
        )
        second = ai_authenticated_client.post(
            "/api/v1/ai/chat",
            json={"message": "Second question", "language": "en"},
        )

        assert first.status_code == 200
        assert second.status_code == 200

        response = ai_authenticated_client.get("/api/v1/ai/history")

        assert response.status_code == 200
        data = response.json()

        assert data["total_count"] == 4
        assert data["has_more"] is False
        assert [item["role"] for item in data["messages"]] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]
        assert data["messages"][0]["content"] == "First question"
        assert "First answer" in data["messages"][1]["content"]
        assert data["messages"][2]["content"] == "Second question"
        assert "Second answer" in data["messages"][3]["content"]

    def test_clear_conversation_history(
        self,
        ai_authenticated_client,
        db,
        ai_enabled_user,
    ):
        db.add_all(
            [
                ChatMessage(
                    user_id=ai_enabled_user.id,
                    role=MessageRole.USER,
                    content="Question",
                    language="de",
                ),
                ChatMessage(
                    user_id=ai_enabled_user.id,
                    role=MessageRole.ASSISTANT,
                    content="Answer",
                    language="de",
                ),
            ]
        )
        db.commit()

        response = ai_authenticated_client.delete("/api/v1/ai/history")
        assert response.status_code == 204

        count = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == ai_enabled_user.id)
            .count()
        )
        assert count == 0

    def test_get_history_without_authentication(self, client):
        response = client.get("/api/v1/ai/history")
        assert response.status_code in (401, 403)


class TestAIFileChat:
    """Current file-chat behavior."""

    @patch("app.services.ai_orchestrator.AIOrchestrator.handle_message")
    def test_chat_with_csv_file_includes_file_context(
        self,
        mock_handle,
        ai_authenticated_client,
        db,
        ai_enabled_user,
    ):
        mock_handle.return_value = OrchestratorResponse(
            text=_assistant_text("en", "I analyzed your uploaded file."),
            intent=UserIntent.EXPLAIN_DOCUMENT,
        )

        csv_content = (
            "date,amount,merchant\n"
            "2026-01-15,8.50,BILLA\n"
        ).encode("utf-8")

        response = ai_authenticated_client.post(
            "/api/v1/ai/chat-with-file",
            files={"file": ("transactions.csv", csv_content, "text/csv")},
            data={
                "message": "Please explain this file",
                "language": "en",
                "context": "",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert "I analyzed your uploaded file." in payload["message"]
        assert payload["intent"] == "explain_doc"
        assert response.headers["X-Credits-Remaining"] == "90"

        called_message = mock_handle.call_args.kwargs["message"]
        assert "[Attached file: transactions.csv]" in called_message
        assert "BILLA" in called_message
        assert "Please explain this file" in called_message

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == ai_enabled_user.id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
        assert len(messages) == 2
        assert "transactions.csv" in messages[0].content
        assert "BILLA" in messages[0].content


class TestAICreditFailureHandling:
    """Credit-related AI behavior."""

    @patch("app.services.ai_orchestrator.AIOrchestrator.handle_message")
    def test_chat_refunds_credits_when_orchestrator_fails(
        self,
        mock_handle,
        ai_authenticated_client,
        db,
        ai_enabled_user,
    ):
        mock_handle.side_effect = RuntimeError("LLM failure")

        with pytest.raises(RuntimeError, match="LLM failure"):
            ai_authenticated_client.post(
                "/api/v1/ai/chat",
                json={"message": "Trigger a failure", "language": "en"},
            )

        balance = (
            db.query(CreditBalance)
            .filter(CreditBalance.user_id == ai_enabled_user.id)
            .first()
        )
        assert balance.plan_balance == 100

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == ai_enabled_user.id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
        assert len(messages) == 1
        assert messages[0].role == MessageRole.USER
