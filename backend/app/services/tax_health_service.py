"""
Tax Health Check Service

Analyses user data across transactions, documents, properties and recurring
transactions to produce a prioritised list of actionable health-check items.
All text is returned as i18n keys + params so the frontend can render in the
user's language.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentType
from app.models.property import Property, PropertyStatus, PropertyType
from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType
from app.models.transaction import (
    ExpenseCategory,
    IncomeCategory,
    Transaction,
    TransactionType,
)
from app.models.user import User, UserType

logger = logging.getLogger(__name__)

# Severity weights for score calculation
_SEVERITY_PENALTY = {"high": 15, "medium": 8, "low": 3}

# Austrian tax deadlines (month, day, label i18n key)
_ANNUAL_DEADLINES = [
    (4, 30, "healthCheck.deadlines.paperSubmission"),
    (6, 30, "healthCheck.deadlines.annualReturn"),
]

# Quarterly VAT deadlines – day-15 of month following quarter end
_VAT_QUARTER_DEADLINES = [
    (2, 15, "healthCheck.deadlines.vatQ4"),
    (5, 15, "healthCheck.deadlines.vatQ1"),
    (8, 15, "healthCheck.deadlines.vatQ2"),
    (11, 15, "healthCheck.deadlines.vatQ3"),
]

# Document requirements per user type
_REQUIRED_DOCS: Dict[UserType, List[DocumentType]] = {
    UserType.EMPLOYEE: [DocumentType.LOHNZETTEL],
    UserType.SELF_EMPLOYED: [DocumentType.SVS_NOTICE],
    UserType.LANDLORD: [],
    UserType.MIXED: [DocumentType.LOHNZETTEL, DocumentType.SVS_NOTICE],
    UserType.GMBH: [DocumentType.EINKOMMENSTEUERBESCHEID],
}


class TaxHealthService:
    """Runs a comprehensive health check across a user's tax data."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def check_health(self, user_id: int, tax_year: int) -> dict:
        """Return a health-check report for *user_id* and *tax_year*.

        The method is wrapped in a broad try/except so it never crashes
        the login flow – on failure it returns a neutral result.
        """
        try:
            return self._run_checks(user_id, tax_year)
        except Exception:
            logger.exception("Tax health check failed for user %s", user_id)
            return {
                "check_date": date.today().isoformat(),
                "tax_year": tax_year,
                "score": 100,
                "items": [],
                "summary": {"high": 0, "medium": 0, "low": 0},
            }

    # ------------------------------------------------------------------
    # Internal orchestration
    # ------------------------------------------------------------------

    def _run_checks(self, user_id: int, tax_year: int) -> dict:
        user = self.db.query(User).filter(User.id == user_id).first()
        if user is None:
            return self._empty_result(tax_year)

        # Pre-fetch lightweight aggregates used by multiple checks
        ctx = self._build_context(user, tax_year)

        # Early exit for brand-new users
        if ctx["total_transactions"] == 0 and ctx["total_documents"] == 0:
            return self._new_user_result(user, tax_year)

        items: List[Dict[str, Any]] = []
        items.extend(self._check_income_document_consistency(user, tax_year, ctx))
        items.extend(self._check_missing_deduction(user, tax_year, ctx))
        items.extend(self._check_property_completeness(user, tax_year, ctx))
        items.extend(self._check_document_freshness(user, tax_year))
        items.extend(self._check_data_quality(user, tax_year))
        items.extend(self._check_threshold_warnings(user, tax_year, ctx))
        items.extend(self._check_deadline_reminders(user, tax_year))

        # Build summary and score
        summary = {"high": 0, "medium": 0, "low": 0}
        for item in items:
            summary[item["severity"]] += 1

        score = max(
            0,
            100
            - summary["high"] * _SEVERITY_PENALTY["high"]
            - summary["medium"] * _SEVERITY_PENALTY["medium"]
            - summary["low"] * _SEVERITY_PENALTY["low"],
        )

        return {
            "check_date": date.today().isoformat(),
            "tax_year": tax_year,
            "score": score,
            "items": items,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Context builder – aggregate queries reused across checks
    # ------------------------------------------------------------------

    def _build_context(self, user: User, tax_year: int) -> dict:
        """Pre-fetch counts and sums used by several checks."""
        user_id = user.id

        total_transactions = (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.user_id == user_id)
            .scalar()
        ) or 0

        total_documents = (
            self.db.query(func.count(Document.id))
            .filter(Document.user_id == user_id)
            .scalar()
        ) or 0

        # Income sums by category for the tax year
        income_sums = (
            self.db.query(
                Transaction.income_category,
                func.sum(Transaction.amount).label("total"),
            )
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.INCOME,
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .group_by(Transaction.income_category)
            .all()
        )
        income_by_category: Dict[Optional[IncomeCategory], Decimal] = {
            row[0]: row[1] or Decimal("0") for row in income_sums
        }

        # Properties
        properties = (
            self.db.query(Property)
            .filter(
                Property.user_id == user_id,
                Property.status == PropertyStatus.ACTIVE,
            )
            .all()
        )

        return {
            "total_transactions": total_transactions,
            "total_documents": total_documents,
            "income_by_category": income_by_category,
            "properties": properties,
        }

    # ------------------------------------------------------------------
    # 1. Income / document consistency
    # ------------------------------------------------------------------

    def _check_income_document_consistency(
        self, user: User, tax_year: int, ctx: dict
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        income_map = ctx["income_by_category"]

        # Documents uploaded in this tax year or the previous one
        doc_year_filter = extract("year", Document.uploaded_at) >= tax_year - 1

        def _has_doc(doc_type: DocumentType) -> bool:
            return (
                self.db.query(func.count(Document.id))
                .filter(
                    Document.user_id == user.id,
                    Document.document_type == doc_type,
                    doc_year_filter,
                )
                .scalar()
                or 0
            ) > 0

        # Employment income but no Lohnzettel
        emp_amount = income_map.get(IncomeCategory.EMPLOYMENT, Decimal("0"))
        if emp_amount > 0 and not _has_doc(DocumentType.LOHNZETTEL):
            items.append(
                self._item(
                    category="income_document_consistency",
                    severity="medium",
                    key="healthCheck.missingLohnzettel",
                    params={"amount": float(emp_amount), "year": tax_year},
                    action_url="/documents",
                    action_label_key="healthCheck.actions.uploadDocument",
                )
            )

        # Rental income but no rental contract
        rental_amount = income_map.get(IncomeCategory.RENTAL, Decimal("0"))
        if rental_amount > 0 and not _has_doc(DocumentType.RENTAL_CONTRACT):
            items.append(
                self._item(
                    category="income_document_consistency",
                    severity="medium",
                    key="healthCheck.missingRentalContract",
                    params={"amount": float(rental_amount)},
                    action_url="/documents",
                    action_label_key="healthCheck.actions.uploadDocument",
                )
            )

        # Self-employment income but no invoices/receipts
        se_amount = income_map.get(IncomeCategory.SELF_EMPLOYMENT, Decimal("0"))
        biz_amount = income_map.get(IncomeCategory.BUSINESS, Decimal("0"))
        combined_se = se_amount + biz_amount
        if combined_se > 0:
            has_biz_docs = (
                self.db.query(func.count(Document.id))
                .filter(
                    Document.user_id == user.id,
                    Document.document_type.in_(
                        [DocumentType.INVOICE, DocumentType.RECEIPT]
                    ),
                    doc_year_filter,
                )
                .scalar()
                or 0
            ) > 0
            if not has_biz_docs:
                items.append(
                    self._item(
                        category="income_document_consistency",
                        severity="medium",
                        key="healthCheck.missingBusinessDocs",
                        params={"amount": float(combined_se), "year": tax_year},
                        action_url="/documents",
                        action_label_key="healthCheck.actions.uploadDocument",
                    )
                )

        return items

    # ------------------------------------------------------------------
    # 2. Missing deductions
    # ------------------------------------------------------------------

    def _check_missing_deduction(
        self, user: User, tax_year: int, ctx: dict
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        properties: List[Property] = ctx["properties"]

        # Rental/mixed-use properties with zero rental percentage
        for prop in properties:
            if prop.property_type in (PropertyType.RENTAL, PropertyType.MIXED_USE):
                if prop.rental_percentage is not None and prop.rental_percentage == 0:
                    items.append(
                        self._item(
                            category="missing_deduction",
                            severity="medium",
                            key="healthCheck.rentalPercentageZero",
                            params={"address": prop.address or str(prop.id)},
                            action_url="/properties",
                            action_label_key="healthCheck.actions.goToProperties",
                        )
                    )

        # Properties exist but no depreciation recurring transaction
        if properties:
            dep_count = (
                self.db.query(func.count(RecurringTransaction.id))
                .filter(
                    RecurringTransaction.user_id == user.id,
                    RecurringTransaction.recurring_type
                    == RecurringTransactionType.DEPRECIATION,
                    RecurringTransaction.is_active == True,  # noqa: E712
                )
                .scalar()
                or 0
            )
            if dep_count == 0:
                # Estimate potential savings: 1.5% of total building value
                total_building_value = sum(
                    (p.building_value or Decimal("0")) for p in properties
                )
                potential = (
                    float(total_building_value * Decimal("0.015"))
                    if total_building_value > 0
                    else None
                )
                items.append(
                    self._item(
                        category="missing_deduction",
                        severity="medium",
                        key="healthCheck.missingAfaSetup",
                        params={"property_count": len(properties)},
                        potential_savings=potential,
                        action_data={
                            "detail_items": [
                                self._asset_detail_item(prop) for prop in properties
                            ],
                        },
                        action_label_key="healthCheck.actions.goToProperties",
                    )
                )

        return items

    # ------------------------------------------------------------------
    # 3. Property completeness
    # ------------------------------------------------------------------

    def _check_property_completeness(
        self, user: User, tax_year: int, ctx: dict
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        properties: List[Property] = ctx["properties"]

        if not properties:
            return items

        # Pre-fetch recurring transactions linked to properties (avoid N+1)
        rental_income_property_ids = set(
            row[0]
            for row in self.db.query(RecurringTransaction.property_id)
            .filter(
                RecurringTransaction.user_id == user.id,
                RecurringTransaction.recurring_type
                == RecurringTransactionType.RENTAL_INCOME,
                RecurringTransaction.is_active == True,  # noqa: E712
                RecurringTransaction.property_id.isnot(None),
            )
            .all()
        )

        for prop in properties:
            address = prop.address or str(prop.id)
            is_rental = prop.property_type != PropertyType.OWNER_OCCUPIED
            severity = "high" if prop.property_type == PropertyType.RENTAL else "medium"

            # Missing depreciation rate (non owner-occupied)
            if is_rental and (
                prop.depreciation_rate is None or prop.depreciation_rate == 0
            ):
                potential = (
                    float((prop.building_value or Decimal("0")) * Decimal("0.015"))
                    if prop.building_value and prop.building_value > 0
                    else None
                )
                items.append(
                    self._item(
                        category="property_completeness",
                        severity=severity,
                        key="healthCheck.propertyNoAfaRate",
                        params={"address": address},
                        potential_savings=potential,
                        action_url=f"/properties/{prop.id}",
                        action_data={
                            "detail_items": [self._asset_detail_item(prop)],
                        },
                        action_label_key="healthCheck.actions.goToProperties",
                    )
                )

            # Rental property without rental income recurring transaction
            if prop.property_type in (
                PropertyType.RENTAL,
                PropertyType.MIXED_USE,
            ) and prop.id not in rental_income_property_ids:
                items.append(
                    self._item(
                        category="property_completeness",
                        severity=severity,
                        key="healthCheck.propertyNoRentalIncome",
                        params={"address": address},
                        action_url=f"/properties/{prop.id}",
                        action_data={
                            "detail_items": [self._asset_detail_item(prop)],
                        },
                        action_label_key="healthCheck.actions.goToProperties",
                    )
                )

            # Missing Kaufvertrag
            if prop.kaufvertrag_document_id is None:
                items.append(
                    self._item(
                        category="property_completeness",
                        severity="medium",
                        key="healthCheck.propertyNoKaufvertrag",
                        params={"address": address},
                        action_url=f"/properties/{prop.id}",
                        action_data={
                            "detail_items": [self._asset_detail_item(prop)],
                        },
                        action_label_key="healthCheck.actions.goToProperties",
                    )
                )

        return items

    # ------------------------------------------------------------------
    # 4. Document freshness
    # ------------------------------------------------------------------

    def _check_document_freshness(
        self, user: User, tax_year: int
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        required_types = _REQUIRED_DOCS.get(user.user_type, [])

        if not required_types:
            return items

        # Single query: count documents per required type for this tax year
        existing_counts = dict(
            self.db.query(Document.document_type, func.count(Document.id))
            .filter(
                Document.user_id == user.id,
                Document.document_type.in_(required_types),
                extract("year", Document.uploaded_at) >= tax_year,
            )
            .group_by(Document.document_type)
            .all()
        )

        for doc_type in required_types:
            if existing_counts.get(doc_type, 0) == 0:
                items.append(
                    self._item(
                        category="document_freshness",
                        severity="medium",
                        key="healthCheck.missingDocument",
                        params={
                            "document_type": doc_type.value,
                            "year": tax_year,
                        },
                        action_url="/documents",
                        action_label_key="healthCheck.actions.uploadDocument",
                    )
                )

        return items

    # ------------------------------------------------------------------
    # 5. Data quality
    # ------------------------------------------------------------------

    def _check_data_quality(
        self, user: User, tax_year: int
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        # Large deductible expenses without a receipt
        row = (
            self.db.query(
                func.count(Transaction.id).label("cnt"),
                func.sum(Transaction.amount).label("total"),
            )
            .filter(
                Transaction.user_id == user.id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.is_deductible == True,  # noqa: E712
                Transaction.amount > 500,
                Transaction.document_id.is_(None),
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .first()
        )
        if row and row.cnt and row.cnt > 0:
            severity = "high" if row.total and row.total > 2000 else "medium"
            items.append(
                self._item(
                    category="data_quality",
                    severity=severity,
                    key="healthCheck.largeExpenseNoReceipt",
                    params={
                        "count": row.cnt,
                        "total_amount": float(row.total or 0),
                    },
                    action_url="/transactions",
                    action_label_key="healthCheck.actions.reviewTransactions",
                )
            )

        # Low-confidence documents needing review
        low_conf_docs = (
            self.db.query(Document)
            .filter(
                Document.user_id == user.id,
                Document.confidence_score < Decimal("0.6"),
                Document.confidence_score.isnot(None),
            )
            .order_by(Document.uploaded_at.desc())
            .all()
        )
        low_conf_count = len(low_conf_docs)
        if low_conf_count > 0:
            items.append(
                self._item(
                    category="data_quality",
                    severity="medium",
                    key="healthCheck.lowConfidenceDocuments",
                    params={"count": low_conf_count},
                    action_url=(
                        f"/documents/{low_conf_docs[0].id}"
                        if low_conf_count == 1
                        else None
                    ),
                    action_data={
                        "detail_items": [
                            self._document_detail_item(doc) for doc in low_conf_docs
                        ],
                    },
                    action_label_key="healthCheck.actions.reviewDocuments",
                )
            )

        return items

    # ------------------------------------------------------------------
    # 6. Threshold warnings
    # ------------------------------------------------------------------

    def _check_threshold_warnings(
        self, user: User, tax_year: int, ctx: dict
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        income_map = ctx["income_by_category"]

        # Kleinunternehmer VAT threshold for self-employed / mixed
        if user.user_type in (UserType.SELF_EMPLOYED, UserType.MIXED):
            se_income = income_map.get(
                IncomeCategory.SELF_EMPLOYMENT, Decimal("0")
            ) + income_map.get(IncomeCategory.BUSINESS, Decimal("0"))
            if se_income >= 30000:
                items.append(
                    self._item(
                        category="threshold_warning",
                        severity="high",
                        key="healthCheck.vatThresholdApproaching",
                        params={
                            "amount": float(se_income),
                            "threshold": 35000,
                        },
                        action_url="/transactions",
                        action_label_key="healthCheck.actions.reviewIncome",
                    )
                )

        # Side-income threshold for employees
        if user.user_type == UserType.EMPLOYEE:
            other_income = income_map.get(
                IncomeCategory.OTHER_INCOME, Decimal("0")
            )
            if other_income > 600:
                items.append(
                    self._item(
                        category="threshold_warning",
                        severity="high",
                        key="healthCheck.sideIncomeThreshold",
                        params={
                            "amount": float(other_income),
                            "threshold": 730,
                        },
                        action_url="/transactions",
                        action_label_key="healthCheck.actions.reviewIncome",
                    )
                )

        return items

    # ------------------------------------------------------------------
    # 7. Deadline reminders
    # ------------------------------------------------------------------

    def _check_deadline_reminders(
        self, user: User, tax_year: int
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        today = date.today()

        # Annual deadlines are for the tax year's filing (filed in the
        # following calendar year).
        filing_year = tax_year + 1

        for month, day, name_key in _ANNUAL_DEADLINES:
            deadline = date(filing_year, month, day)
            days_remaining = (deadline - today).days
            if 0 < days_remaining <= 90:
                severity = "high" if days_remaining < 30 else "medium"
                items.append(
                    self._item(
                        category="deadline_reminder",
                        severity=severity,
                        key="healthCheck.deadlineApproaching",
                        params={
                            "deadline_name": name_key,
                            "date": deadline.isoformat(),
                            "days_remaining": days_remaining,
                        },
                    )
                )

        # Quarterly VAT deadlines (relevant for self-employed / mixed / GmbH)
        if user.user_type in (
            UserType.SELF_EMPLOYED,
            UserType.MIXED,
            UserType.GMBH,
        ):
            for month, day, name_key in _VAT_QUARTER_DEADLINES:
                # Check both this year and next year for upcoming deadlines
                for year in (today.year, today.year + 1):
                    deadline = date(year, month, day)
                    days_remaining = (deadline - today).days
                    if 0 < days_remaining <= 90:
                        severity = "high" if days_remaining < 30 else "medium"
                        items.append(
                            self._item(
                                category="deadline_reminder",
                                severity=severity,
                                key="healthCheck.deadlineApproaching",
                                params={
                                    "deadline_name": name_key,
                                    "date": deadline.isoformat(),
                                    "days_remaining": days_remaining,
                                },
                            )
                        )
                        break  # only the nearest occurrence

        return items

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _item(
        *,
        category: str,
        severity: str,
        key: str,
        params: Dict[str, Any],
        potential_savings: Optional[float] = None,
        action_url: Optional[str] = None,
        action_label_key: Optional[str] = None,
        action_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "category": category,
            "severity": severity,
            "i18n_key": key,
            "i18n_params": params,
            "potential_savings": potential_savings,
            "action_url": action_url,
            "action_label_key": action_label_key,
            "action_data": action_data or {},
        }

    @staticmethod
    def _asset_detail_item(prop: Property) -> Dict[str, Any]:
        label = prop.name or prop.address or str(prop.id)
        return {
            "kind": "asset",
            "asset_id": str(prop.id),
            "label": label,
            "href": f"/properties/{prop.id}",
        }

    @staticmethod
    def _document_detail_item(doc: Document) -> Dict[str, Any]:
        return {
            "kind": "document",
            "document_id": doc.id,
            "label": doc.file_name,
            "href": f"/documents/{doc.id}",
        }

    def _empty_result(self, tax_year: int) -> dict:
        return {
            "check_date": date.today().isoformat(),
            "tax_year": tax_year,
            "score": 100,
            "items": [],
            "summary": {"high": 0, "medium": 0, "low": 0},
        }

    def _new_user_result(self, user: User, tax_year: int) -> dict:
        """Return a gentle 'getting started' result for brand-new users."""
        items = [
            self._item(
                category="getting_started",
                severity="low",
                key="healthCheck.gettingStarted.addTransaction",
                params={},
                action_url="/transactions",
                action_label_key="healthCheck.actions.addTransaction",
            ),
            self._item(
                category="getting_started",
                severity="low",
                key="healthCheck.gettingStarted.uploadDocument",
                params={},
                action_url="/documents",
                action_label_key="healthCheck.actions.uploadDocument",
            ),
        ]

        # If user is a landlord or mixed, nudge them to add a property
        if user.user_type in (UserType.LANDLORD, UserType.MIXED):
            items.append(
                self._item(
                    category="getting_started",
                    severity="low",
                    key="healthCheck.gettingStarted.addProperty",
                    params={},
                    action_url="/properties",
                    action_label_key="healthCheck.actions.goToProperties",
                )
            )

        summary = {"high": 0, "medium": 0, "low": len(items)}
        score = max(0, 100 - summary["low"] * _SEVERITY_PENALTY["low"])

        return {
            "check_date": date.today().isoformat(),
            "tax_year": tax_year,
            "score": score,
            "items": items,
            "summary": summary,
        }
