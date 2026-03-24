"""Service layer for liabilities and asset-liability overview."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.liability import (
    Liability,
    LiabilityReportCategory,
    LiabilitySourceType,
    LiabilityType,
)
from app.models.property import Property, PropertyStatus
from app.models.property_loan import PropertyLoan
from app.models.transaction import ExpenseCategory, Transaction, TransactionType


MONEY = Decimal("0.01")


def _money(value: Decimal | int | float | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(MONEY)
    return Decimal(str(value)).quantize(MONEY)


class LiabilityService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def default_report_category(liability_type: LiabilityType) -> LiabilityReportCategory:
        if liability_type == LiabilityType.OTHER_LIABILITY:
            return LiabilityReportCategory.SONSTIGE_VERBINDLICHKEITEN
        return LiabilityReportCategory.DARLEHEN_UND_KREDITE

    @staticmethod
    def derive_active(end_date: Optional[date]) -> bool:
        return end_date is None or end_date >= date.today()

    @staticmethod
    def default_source_type(
        *,
        source_document_id: Optional[int] = None,
        linked_loan_id: Optional[int] = None,
    ) -> LiabilitySourceType:
        if source_document_id:
            return LiabilitySourceType.DOCUMENT_CONFIRMED
        if linked_loan_id:
            return LiabilitySourceType.SYSTEM_MIGRATED
        return LiabilitySourceType.MANUAL

    @staticmethod
    def can_manage_directly(liability: Liability) -> bool:
        return liability.can_edit_directly

    @staticmethod
    def _raise_source_managed_error() -> None:
        raise ValueError(
            "This liability is synced from a linked contract or loan. Open the source document or property flow to change it."
        )

    def list_liabilities(self, user_id: int, include_inactive: bool = False) -> list[Liability]:
        query = self.db.query(Liability).filter(Liability.user_id == user_id)
        if not include_inactive:
            query = query.filter(Liability.is_active.is_(True))
        return query.order_by(Liability.created_at.desc(), Liability.id.desc()).all()

    def get_liability(self, liability_id: int, user_id: int) -> Optional[Liability]:
        return (
            self.db.query(Liability)
            .filter(Liability.id == liability_id, Liability.user_id == user_id)
            .first()
        )

    def _build_opening_balance_transaction(self, liability: Liability) -> Transaction:
        return Transaction(
            user_id=liability.user_id,
            property_id=liability.linked_property_id,
            liability_id=liability.id,
            type=TransactionType.LIABILITY_DRAWDOWN,
            amount=_money(liability.outstanding_balance),
            transaction_date=liability.start_date,
            description=f"Opening balance - {liability.display_name}",
            is_system_generated=True,
            import_source="liability_service",
            classification_confidence=Decimal("1.00"),
            reviewed=True,
            locked=True,
        )

    def sync_outstanding_balance(self, liability_id: int) -> Liability:
        liability = self.db.query(Liability).filter(Liability.id == liability_id).first()
        if not liability:
            raise ValueError("Liability not found")

        drawdowns = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == liability.user_id,
                Transaction.liability_id == liability.id,
                Transaction.type == TransactionType.LIABILITY_DRAWDOWN,
            )
            .scalar()
        )
        repayments = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == liability.user_id,
                Transaction.liability_id == liability.id,
                Transaction.type == TransactionType.LIABILITY_REPAYMENT,
            )
            .scalar()
        )
        liability.outstanding_balance = max(_money(drawdowns) - _money(repayments), Decimal("0.00"))
        liability.updated_at = datetime.utcnow()
        self.db.flush()
        return liability

    def create_liability(
        self,
        user_id: int,
        *,
        liability_type: LiabilityType,
        display_name: str,
        currency: str,
        lender_name: str,
        principal_amount: Decimal,
        outstanding_balance: Decimal,
        start_date: date,
        interest_rate: Optional[Decimal] = None,
        end_date: Optional[date] = None,
        monthly_payment: Optional[Decimal] = None,
        tax_relevant: bool = False,
        tax_relevance_reason: Optional[str] = None,
        report_category: Optional[LiabilityReportCategory] = None,
        linked_property_id: Optional[str | UUID] = None,
        linked_loan_id: Optional[int] = None,
        source_document_id: Optional[int] = None,
        source_type: Optional[LiabilitySourceType] = None,
        notes: Optional[str] = None,
        create_recurring_plan: bool = False,
        recurring_day_of_month: Optional[int] = None,
    ) -> Liability:
        from app.services.recurring_transaction_service import RecurringTransactionService

        property_id = linked_property_id
        if isinstance(property_id, str):
            property_id = UUID(property_id)

        liability = Liability(
            user_id=user_id,
            liability_type=liability_type,
            source_type=source_type or self.default_source_type(
                source_document_id=source_document_id,
                linked_loan_id=linked_loan_id,
            ),
            display_name=display_name.strip(),
            currency=currency.upper(),
            lender_name=lender_name.strip(),
            principal_amount=_money(principal_amount),
            outstanding_balance=_money(outstanding_balance),
            interest_rate=interest_rate,
            start_date=start_date,
            end_date=end_date,
            monthly_payment=_money(monthly_payment) if monthly_payment is not None else None,
            tax_relevant=tax_relevant,
            tax_relevance_reason=tax_relevance_reason,
            report_category=report_category or self.default_report_category(liability_type),
            linked_property_id=property_id,
            linked_loan_id=linked_loan_id,
            source_document_id=source_document_id,
            is_active=self.derive_active(end_date),
            notes=notes,
        )
        self.db.add(liability)
        self.db.flush()

        self.db.add(self._build_opening_balance_transaction(liability))

        if create_recurring_plan and liability.monthly_payment:
            recurring_service = RecurringTransactionService(self.db)
            recurring_service.create_loan_repayment_recurring(
                user_id=user_id,
                monthly_payment=liability.monthly_payment,
                start_date=liability.start_date,
                end_date=liability.end_date,
                day_of_month=recurring_day_of_month or liability.start_date.day,
                description=f"Loan repayment - {liability.display_name}",
                source_document_id=liability.source_document_id,
                liability_id=liability.id,
            )

        self.db.commit()
        self.db.refresh(liability)
        return liability

    def update_liability(self, liability_id: int, user_id: int, updates: dict) -> Liability:
        liability = self.get_liability(liability_id, user_id)
        if not liability:
            raise ValueError("Liability not found")
        if not self.can_manage_directly(liability):
            self._raise_source_managed_error()

        if "linked_property_id" in updates:
            updates["linked_property_id"] = (
                UUID(updates["linked_property_id"]) if updates["linked_property_id"] else None
            )
        if "monthly_payment" in updates and updates["monthly_payment"] is not None:
            updates["monthly_payment"] = _money(updates["monthly_payment"])
        if "principal_amount" in updates and updates["principal_amount"] is not None:
            updates["principal_amount"] = _money(updates["principal_amount"])
        if "outstanding_balance" in updates and updates["outstanding_balance"] is not None:
            updates["outstanding_balance"] = _money(updates["outstanding_balance"])
        if "currency" in updates and updates["currency"]:
            updates["currency"] = updates["currency"].upper()
        if "end_date" in updates and "is_active" not in updates:
            updates["is_active"] = self.derive_active(updates["end_date"])

        for field, value in updates.items():
            setattr(liability, field, value)
        liability.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(liability)
        return liability

    def soft_delete_liability(self, liability_id: int, user_id: int) -> Liability:
        liability = self.get_liability(liability_id, user_id)
        if not liability:
            raise ValueError("Liability not found")
        if not liability.can_deactivate_directly:
            self._raise_source_managed_error()

        liability.is_active = False
        liability.updated_at = datetime.utcnow()
        for recurring in liability.recurring_transactions:
            recurring.is_active = False
            recurring.end_date = recurring.end_date or date.today()
            recurring.next_generation_date = None
        self.db.commit()
        self.db.refresh(liability)
        return liability

    def ensure_property_loan_liability(
        self,
        loan: PropertyLoan,
        *,
        source_document_id: Optional[int] = None,
        source_type: Optional[LiabilitySourceType] = None,
    ) -> Liability:
        liability = (
            self.db.query(Liability)
            .filter(Liability.linked_loan_id == loan.id, Liability.user_id == loan.user_id)
            .first()
        )
        resolved_source_type = source_type or self.default_source_type(
            source_document_id=source_document_id or loan.loan_contract_document_id,
            linked_loan_id=loan.id,
        )
        if liability is None:
            liability = Liability(
                user_id=loan.user_id,
                liability_type=LiabilityType.PROPERTY_LOAN,
                source_type=resolved_source_type,
                display_name=f"{loan.lender_name} mortgage",
                currency="EUR",
                lender_name=loan.lender_name,
                principal_amount=_money(loan.loan_amount),
                outstanding_balance=_money(loan.loan_amount),
                interest_rate=loan.interest_rate,
                start_date=loan.start_date,
                end_date=loan.end_date,
                monthly_payment=_money(loan.monthly_payment),
                tax_relevant=True,
                tax_relevance_reason="Property loan linked to rental/property financing",
                report_category=LiabilityReportCategory.DARLEHEN_UND_KREDITE,
                linked_property_id=loan.property_id,
                linked_loan_id=loan.id,
                source_document_id=source_document_id or loan.loan_contract_document_id,
                is_active=self.derive_active(loan.end_date),
                notes=loan.notes,
            )
            self.db.add(liability)
            self.db.flush()
            self.db.add(self._build_opening_balance_transaction(liability))
        else:
            liability.display_name = liability.display_name or f"{loan.lender_name} mortgage"
            liability.lender_name = loan.lender_name
            liability.source_type = resolved_source_type
            liability.principal_amount = _money(loan.loan_amount)
            liability.interest_rate = loan.interest_rate
            liability.start_date = loan.start_date
            liability.end_date = loan.end_date
            liability.monthly_payment = _money(loan.monthly_payment)
            liability.linked_property_id = loan.property_id
            liability.source_document_id = source_document_id or loan.loan_contract_document_id
            liability.tax_relevant = True
            liability.tax_relevance_reason = "Property loan linked to rental/property financing"
            liability.report_category = LiabilityReportCategory.DARLEHEN_UND_KREDITE
            liability.is_active = self.derive_active(loan.end_date)
            liability.notes = loan.notes
            if not liability.outstanding_balance or liability.outstanding_balance <= 0:
                liability.outstanding_balance = _money(loan.loan_amount)
        self.db.flush()
        return liability

    def detach_property_loan(self, loan: PropertyLoan) -> None:
        liability = (
            self.db.query(Liability)
            .filter(Liability.linked_loan_id == loan.id, Liability.user_id == loan.user_id)
            .first()
        )
        if liability:
            liability.linked_loan_id = None
            liability.is_active = False
            liability.updated_at = datetime.utcnow()
            self.db.flush()

    def get_summary(self, user_id: int) -> dict[str, Decimal | int]:
        total_assets = (
            self.db.query(func.coalesce(func.sum(Property.purchase_price), 0))
            .filter(
                Property.user_id == user_id,
                Property.status != PropertyStatus.ARCHIVED,
            )
            .scalar()
        )
        total_liabilities = (
            self.db.query(func.coalesce(func.sum(Liability.outstanding_balance), 0))
            .filter(Liability.user_id == user_id, Liability.is_active.is_(True))
            .scalar()
        )
        active_count = (
            self.db.query(func.count(Liability.id))
            .filter(Liability.user_id == user_id, Liability.is_active.is_(True))
            .scalar()
        ) or 0
        monthly_debt_service = (
            self.db.query(func.coalesce(func.sum(Liability.monthly_payment), 0))
            .filter(Liability.user_id == user_id, Liability.is_active.is_(True))
            .scalar()
        )
        current_year = date.today().year
        annual_deductible_interest = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.expense_category == ExpenseCategory.LOAN_INTEREST,
                Transaction.is_deductible.is_(True),
                func.extract("year", Transaction.transaction_date) == current_year,
            )
            .scalar()
        )
        total_assets_dec = _money(total_assets)
        total_liabilities_dec = _money(total_liabilities)
        return {
            "total_assets": total_assets_dec,
            "total_liabilities": total_liabilities_dec,
            "net_worth": _money(total_assets_dec - total_liabilities_dec),
            "active_liability_count": int(active_count),
            "monthly_debt_service": _money(monthly_debt_service),
            "annual_deductible_interest": _money(annual_deductible_interest),
        }
