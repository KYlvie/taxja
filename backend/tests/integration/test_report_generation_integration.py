"""Integration tests for current report and transaction export contracts."""

from datetime import date, datetime, timedelta
from decimal import Decimal
import csv
from io import StringIO
from unittest.mock import patch

import pytest

from app.models.credit_balance import CreditBalance
from app.models.credit_cost_config import CreditCostConfig
from app.models.document import Document, DocumentType
from app.models.plan import BillingCycle, Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.recurring_transaction import (
    RecurrenceFrequency,
    RecurringTransaction,
    RecurringTransactionType,
)
from app.models.transaction import ExpenseCategory, IncomeCategory, Transaction, TransactionType
from app.models.user import User
from app.api.deps import get_redis_client
from app.services.feature_gate_service import FeatureGateService


def _seed_reporting_access(db, user: User, *, report_credits: int = 5, transaction_credits: int = 5) -> None:
    now = datetime.utcnow()

    pro_plan = Plan(
        plan_type=PlanType.PRO,
        name="Pro",
        monthly_price=Decimal("9.90"),
        yearly_price=Decimal("99.00"),
        features={
            "advanced_reports": True,
            "e1_generation": True,
        },
        quotas={"reports": -1},
        monthly_credits=report_credits + transaction_credits,
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

    db.add_all(
        [
            CreditCostConfig(
                operation="e1_generation",
                credit_cost=2,
                description="Tax form generation",
                pricing_version=1,
                is_active=True,
            ),
            CreditCostConfig(
                operation="transaction_entry",
                credit_cost=1,
                description="Transaction entry",
                pricing_version=1,
                is_active=True,
            ),
            CreditBalance(
                user_id=user.id,
                plan_balance=report_credits + transaction_credits,
                topup_balance=0,
                overage_enabled=False,
                overage_credits_used=0,
                has_unpaid_overage=False,
                unpaid_overage_periods=0,
            ),
        ]
    )
    db.commit()

    # Feature-gate plan fallback uses Redis caching; clear any stale plan for this
    # user so Advanced Reports tests don't inherit a previous test's entitlement.
    FeatureGateService(db, get_redis_client()).invalidate_user_plan_cache(user.id)


def _add_transaction(
    db,
    *,
    user_id: int,
    txn_type: TransactionType,
    amount: str,
    txn_date: date,
    description: str,
    income_category: IncomeCategory | None = None,
    expense_category: ExpenseCategory | None = None,
    is_deductible: bool = False,
):
    transaction = Transaction(
        user_id=user_id,
        type=txn_type,
        amount=Decimal(amount),
        transaction_date=txn_date,
        description=description,
        income_category=income_category,
        expense_category=expense_category,
        is_deductible=is_deductible,
    )
    db.add(transaction)
    db.flush()
    return transaction


@pytest.fixture
def reporting_enabled_user(db, test_user):
    user = db.query(User).filter(User.email == test_user["email"]).first()
    _seed_reporting_access(db, user)
    db.refresh(user)
    return user


@pytest.fixture
def reporting_authenticated_client(client, test_user, reporting_enabled_user):
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


@pytest.fixture
def seeded_transactions(db, reporting_enabled_user):
    _add_transaction(
        db,
        user_id=reporting_enabled_user.id,
        txn_type=TransactionType.INCOME,
        amount="36000.00",
        txn_date=date(2026, 1, 31),
        description="Employment income",
        income_category=IncomeCategory.EMPLOYMENT,
    )
    _add_transaction(
        db,
        user_id=reporting_enabled_user.id,
        txn_type=TransactionType.INCOME,
        amount="12000.00",
        txn_date=date(2026, 2, 1),
        description="Rental income",
        income_category=IncomeCategory.RENTAL,
    )
    _add_transaction(
        db,
        user_id=reporting_enabled_user.id,
        txn_type=TransactionType.EXPENSE,
        amount="1500.00",
        txn_date=date(2026, 2, 10),
        description="Office supplies",
        expense_category=ExpenseCategory.OFFICE_SUPPLIES,
        is_deductible=True,
    )
    db.commit()


class TestCurrentReportEndpoints:
    """Current report routes backed by tax-form and advanced-report services."""

    @patch("app.services.e1_form_service.generate_tax_form_data")
    def test_generate_tax_form_json_deducts_credits(
        self,
        mock_generate,
        reporting_authenticated_client,
        reporting_enabled_user,
        seeded_transactions,
        db,
    ):
        mock_generate.return_value = {
            "form_type": "E1",
            "tax_year": 2026,
            "income_total": 48000,
            "expense_total": 1500,
        }

        response = reporting_authenticated_client.post(
            "/api/v1/reports/tax-form",
            json={"tax_year": 2026, "language": "de"},
        )

        assert response.status_code == 200
        assert response.json()["form_type"] == "E1"
        assert response.headers["X-Credits-Remaining"] == "8"

        balance = (
            db.query(CreditBalance)
            .filter(CreditBalance.user_id == reporting_enabled_user.id)
            .first()
        )
        assert balance.plan_balance == 8

    @patch("app.services.finanzonline_xml_generator.FinanzOnlineXMLGenerator.generate_from_form_data")
    @patch("app.services.e1_form_service.generate_tax_form_data")
    def test_generate_tax_form_xml_download(
        self,
        mock_form_data,
        mock_xml,
        reporting_authenticated_client,
        seeded_transactions,
    ):
        mock_form_data.return_value = {"form_type": "E1", "tax_year": 2026}
        mock_xml.return_value = '<?xml version="1.0" encoding="UTF-8"?><E1 year="2026" />'

        response = reporting_authenticated_client.post(
            "/api/v1/reports/tax-form-xml",
            json={"tax_year": 2026, "language": "de"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/xml")
        assert response.text.startswith('<?xml version="1.0"')
        assert 'filename="Taxja-E1-2026.xml"' in response.headers["content-disposition"]

    @patch("app.services.ea_pdf_service.generate_ea_pdf")
    @patch("app.services.ea_report_service.generate_ea_report")
    def test_generate_ea_report_pdf(
        self,
        mock_ea_report,
        mock_ea_pdf,
        reporting_authenticated_client,
        seeded_transactions,
    ):
        mock_ea_report.return_value = {
            "year": 2026,
            "income_total": 48000,
            "expense_total": 1500,
        }
        mock_ea_pdf.return_value = b"%PDF-1.4\n%Taxja EA report"

        response = reporting_authenticated_client.post(
            "/api/v1/reports/ea-report-pdf",
            json={"tax_year": 2026, "language": "de"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")

    def test_audit_checklist_uses_current_summary_shape(
        self,
        reporting_authenticated_client,
        seeded_transactions,
    ):
        response = reporting_authenticated_client.get(
            "/api/v1/reports/audit-checklist?tax_year=2026"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "overall_status" in data
        assert "missing_documents" in data
        assert any("transactions recorded" in item["message"] for item in data["items"])

    def test_audit_checklist_counts_documents_by_document_year_when_exact_date_missing(
        self,
        reporting_authenticated_client,
        reporting_enabled_user,
        db,
    ):
        db.add(
            Transaction(
                user_id=reporting_enabled_user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("72.78"),
                transaction_date=date(2024, 12, 16),
                description="T-Mobile bill",
                expense_category=ExpenseCategory.TELECOM,
                is_deductible=True,
            )
        )
        db.add(
            Document(
                user_id=reporting_enabled_user.id,
                document_type=DocumentType.BANK_STATEMENT,
                file_path="documents/statement-2024.pdf",
                file_name="statement-2024.pdf",
                uploaded_at=datetime(2026, 3, 24, 10, 0, 0),
                processed_at=datetime(2026, 3, 24, 10, 0, 0),
                document_date=None,
                document_year=2024,
                year_basis="statement_period_start",
                year_confidence=Decimal("1.00"),
                ocr_result={"document_year": 2024},
                raw_text="statement 2024",
                confidence_score=Decimal("0.95"),
            )
        )
        db.commit()

        response = reporting_authenticated_client.get(
            "/api/v1/reports/audit-checklist?tax_year=2024"
        )

        assert response.status_code == 200
        payload = response.json()
        documents_item = next(item for item in payload["items"] if item["category"] == "documents")
        assert documents_item["status"] == "pass"
        assert "1 supporting documents uploaded" in documents_item["message"]

    def test_audit_checklist_ignores_legacy_loan_repayment_for_category_warning(
        self,
        reporting_authenticated_client,
        reporting_enabled_user,
        db,
    ):
        recurring = RecurringTransaction(
            user_id=reporting_enabled_user.id,
            recurring_type=RecurringTransactionType.LOAN_REPAYMENT,
            description="Legacy principal repayment",
            amount=Decimal("1508.33"),
            transaction_type=TransactionType.EXPENSE.value,
            category="loan_repayment",
            frequency=RecurrenceFrequency.MONTHLY,
            start_date=date(2026, 1, 1),
            day_of_month=1,
        )
        db.add(recurring)
        db.flush()

        db.add(
            Transaction(
                user_id=reporting_enabled_user.id,
                type=TransactionType.LIABILITY_REPAYMENT,
                amount=Decimal("602.08"),
                transaction_date=date(2026, 2, 3),
                description="Loan principal repayment",
            )
        )
        db.add(
            Transaction(
                user_id=reporting_enabled_user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("1508.33"),
                transaction_date=date(2026, 2, 3),
                description="Legacy loan repayment",
                source_recurring_id=recurring.id,
            )
        )
        db.commit()

        response = reporting_authenticated_client.get(
            "/api/v1/reports/audit-checklist?tax_year=2026"
        )

        assert response.status_code == 200
        payload = response.json()
        completeness_item = next(
            item for item in payload["items"] if item["category"] == "completeness"
        )
        assert completeness_item["status"] == "pass"

    def test_report_generation_requires_authentication(self, client):
        response = client.post(
            "/api/v1/reports/tax-form",
            json={"tax_year": 2026, "language": "de"},
        )
        assert response.status_code in (401, 403)


class TestCurrentCSVExportImport:
    """Current transaction CSV export/import contracts."""

    def test_export_transactions_to_csv(
        self,
        reporting_authenticated_client,
        seeded_transactions,
    ):
        response = reporting_authenticated_client.get(
            "/api/v1/transactions/export?start_date=2026-01-01&end_date=2026-12-31"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        reader = csv.DictReader(StringIO(response.text))
        rows = list(reader)
        assert len(rows) == 3
        assert reader.fieldnames == [
            "date",
            "type",
            "amount",
            "description",
            "category",
            "is_deductible",
        ]

    def test_import_transactions_from_csv_consumes_transaction_credits(
        self,
        reporting_authenticated_client,
        reporting_enabled_user,
        db,
    ):
        csv_content = "\n".join(
            [
                "date,type,amount,description,category",
                "2026-01-15,income,3500.00,Salary,employment",
                "2026-01-20,expense,150.50,Office supplies,office_supplies",
            ]
        )

        files = {
            "file": ("transactions.csv", csv_content, "text/csv")
        }
        response = reporting_authenticated_client.post("/api/v1/transactions/import", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == 2
        assert data["failed"] == 0
        assert len(data["transactions"]) == 2
        assert response.headers["X-Credits-Remaining"] == "8"

        count = (
            db.query(Transaction)
            .filter(Transaction.user_id == reporting_enabled_user.id)
            .count()
        )
        assert count == 2

    def test_export_user_data_includes_documents_and_transactions(
        self,
        reporting_authenticated_client,
        reporting_enabled_user,
        db,
    ):
        _add_transaction(
            db,
            user_id=reporting_enabled_user.id,
            txn_type=TransactionType.EXPENSE,
            amount="42.00",
            txn_date=date(2026, 3, 1),
            description="Business lunch",
            expense_category=ExpenseCategory.OTHER,
        )
        db.add(
            Document(
                user_id=reporting_enabled_user.id,
                document_type=DocumentType.OTHER,
                file_path="/exports/test.pdf",
                file_name="test.pdf",
                file_size=123,
                mime_type="application/pdf",
            )
        )
        db.commit()

        response = reporting_authenticated_client.post("/api/v1/reports/export-user-data")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        export_data = response.json()
        assert export_data["user"]["email"] == reporting_enabled_user.email
        assert len(export_data["transactions"]) == 1
        assert len(export_data["documents"]) == 1
