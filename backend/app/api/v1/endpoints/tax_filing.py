"""Tax Filing Summary API — aggregates confirmed TaxFilingData for a given year."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from decimal import Decimal
from sqlalchemy import extract, func, case

from app.db.base import get_db
from app.models.user import User
from app.models.tax_filing_data import TaxFilingData
from app.models.transaction import Transaction
from app.core.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# Category grouping for summary
INCOME_TYPES = {"lohnzettel", "e1a", "e1b", "e1kv"}
DEDUCTION_TYPES = {"l1", "l1k", "l1ab"}
VAT_TYPES = {"u1", "u30"}
OTHER_TYPES = {"jahresabschluss", "svs", "grundsteuer", "bank_statement"}


@router.get("/tax-filing/years")
def get_available_years(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return list of tax years from confirmed TaxFilingData AND transactions."""
    # Years from confirmed tax filing data (SVS, Lohnzettel, etc.)
    filing_rows = (
        db.query(TaxFilingData.tax_year)
        .filter(
            TaxFilingData.user_id == current_user.id,
            TaxFilingData.status == "confirmed",
        )
        .distinct()
        .all()
    )
    filing_years = {r[0] for r in filing_rows if r[0]}

    # Years from transactions (income, expenses, rent, etc.)
    txn_rows = (
        db.query(func.distinct(extract("year", Transaction.transaction_date)))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.transaction_date.isnot(None),
        )
        .all()
    )
    txn_years = {int(r[0]) for r in txn_rows if r[0]}

    all_years = sorted(filing_years | txn_years, reverse=True)
    return {"years": all_years}


@router.get("/tax-filing/{year}/summary")
def get_tax_filing_summary(
    year: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Aggregate all confirmed TaxFilingData for a given tax year.

    Groups data into income / deductions / VAT / other categories,
    computes totals, and flags potential conflicts.
    """
    records = (
        db.query(TaxFilingData)
        .filter(
            TaxFilingData.user_id == current_user.id,
            TaxFilingData.tax_year == year,
            TaxFilingData.status == "confirmed",
        )
        .all()
    )

    if not records:
        txn_summary = _aggregate_transactions(db, current_user.id, year)
        return {
            "year": year,
            "income": [],
            "deductions": [],
            "vat": [],
            "other": [],
            "totals": _empty_totals(),
            "conflicts": [],
            "record_count": 0,
            "transactions": txn_summary,
        }

    income_items = []
    deduction_items = []
    vat_items = []
    other_items = []
    conflicts = []

    for rec in records:
        entry = _build_entry(rec)
        dt = rec.data_type
        if dt in INCOME_TYPES:
            income_items.append(entry)
        elif dt in DEDUCTION_TYPES:
            deduction_items.append(entry)
        elif dt in VAT_TYPES:
            vat_items.append(entry)
        else:
            other_items.append(entry)

    # Compute totals
    total_income = _sum_income(income_items)
    total_deductions = _sum_deductions(deduction_items)
    total_vat_payable = _sum_vat(vat_items)

    # Conflict detection: multiple L16 with different employer but same merged record is OK
    # Check if L16 total vs Bescheid income differ
    l16_income = sum(
        float(r.data.get("kz_245") or 0) for r in records if r.data_type == "lohnzettel"
    )
    e1a_income = sum(
        float(r.data.get("gewinn_verlust") or 0) for r in records if r.data_type == "e1a"
    )

    # Estimate tax (simplified — use income tax brackets)
    estimated_tax = _estimate_tax(total_income)
    withheld_tax = sum(
        float(r.data.get("kz_260") or r.data.get("withheld_tax") or 0)
        for r in records if r.data_type == "lohnzettel"
    )

    txn_summary = _aggregate_transactions(db, current_user.id, year)

    return {
        "year": year,
        "income": income_items,
        "deductions": deduction_items,
        "vat": vat_items,
        "other": other_items,
        "totals": {
            "total_income": round(total_income, 2),
            "total_deductions": round(total_deductions, 2),
            "taxable_income": round(max(total_income - total_deductions, 0), 2),
            "estimated_tax": round(estimated_tax, 2),
            "withheld_tax": round(withheld_tax, 2),
            "estimated_refund": round(withheld_tax - estimated_tax, 2),
            "total_vat_payable": round(total_vat_payable, 2),
        },
        "conflicts": conflicts,
        "record_count": len(records),
        "transactions": txn_summary,
    }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _build_entry(rec: TaxFilingData) -> dict:
    """Build a summary entry from a TaxFilingData record."""
    data = rec.data or {}
    return {
        "id": rec.id,
        "data_type": rec.data_type,
        "source_document_id": rec.source_document_id,
        "confirmed_at": rec.confirmed_at.isoformat() if rec.confirmed_at else None,
        "data": data,
    }


def _sum_income(items: list) -> float:
    total = 0.0
    for item in items:
        d = item["data"]
        dt = item["data_type"]
        if dt == "lohnzettel":
            total += float(d.get("kz_245") or d.get("gross_income") or 0)
        elif dt == "e1a":
            total += max(float(d.get("gewinn_verlust") or 0), 0)
        elif dt == "e1b":
            # Sum all property net incomes
            props = d.get("properties", [])
            for p in props:
                total += float(p.get("net_income") or p.get("ueberschuss") or 0)
            if not props:
                total += float(d.get("total_income") or 0)
        elif dt == "e1kv":
            total += float(d.get("total_capital_gains") or d.get("kz_981") or 0)
    return total


def _sum_deductions(items: list) -> float:
    total = 0.0
    for item in items:
        d = item["data"]
        dt = item["data_type"]
        if dt == "l1":
            for k in ("kz_717", "kz_718", "kz_719", "kz_720", "kz_721",
                       "kz_722", "kz_723", "kz_724", "kz_450", "kz_458",
                       "kz_459", "kz_730", "kz_740"):
                total += float(d.get(k) or 0)
        elif dt == "l1k":
            total += float(d.get("familienbonus_total") or 0)
        elif dt == "l1ab":
            for k in ("alleinverdiener", "alleinerzieher", "pendlerpauschale",
                       "pendlereuro", "freibetrag"):
                total += float(d.get(k) or 0)
    return total


def _sum_vat(items: list) -> float:
    total = 0.0
    for item in items:
        d = item["data"]
        total += float(d.get("zahllast") or d.get("vat_payable") or 0)
    return total


def _estimate_tax(taxable_income: float) -> float:
    """Simplified 2026 Austrian income tax brackets."""
    if taxable_income <= 12816:
        return 0
    brackets = [
        (12816, 20818, 0.20),
        (20818, 34513, 0.30),
        (34513, 66612, 0.40),
        (66612, 99266, 0.48),
        (99266, 1000000, 0.50),
        (1000000, float("inf"), 0.55),
    ]
    tax = 0.0
    for lower, upper, rate in brackets:
        if taxable_income <= lower:
            break
        band = min(taxable_income, upper) - lower
        tax += band * rate
    return tax


def _empty_totals() -> dict:
    return {
        "total_income": 0,
        "total_deductions": 0,
        "taxable_income": 0,
        "estimated_tax": 0,
        "withheld_tax": 0,
        "estimated_refund": 0,
        "total_vat_payable": 0,
    }


def _aggregate_transactions(db: Session, user_id: int, year: int) -> dict:
    """Aggregate transactions for a given year, grouped by type and category."""
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            extract("year", Transaction.transaction_date) == year,
        )
        .all()
    )
    if not txns:
        return {
            "transaction_count": 0,
            "income_total": 0,
            "expense_total": 0,
            "deductible_total": 0,
            "by_category": [],
        }

    cat_map: dict[str, dict] = {}
    income_total = Decimal("0")
    expense_total = Decimal("0")
    deductible_total = Decimal("0")

    for t in txns:
        amt = t.amount or Decimal("0")
        txn_type = t.type.value if hasattr(t.type, "value") else str(t.type)

        if txn_type == "income":
            income_total += amt
            cat = (
                t.income_category.value
                if t.income_category and hasattr(t.income_category, "value")
                else str(t.income_category or "other")
            )
        elif txn_type == "expense":
            expense_total += amt
            if t.is_deductible:
                deductible_total += amt
            cat = (
                t.expense_category.value
                if t.expense_category and hasattr(t.expense_category, "value")
                else str(t.expense_category or "other")
            )
        else:
            cat = txn_type

        key = f"{txn_type}:{cat}"
        if key not in cat_map:
            cat_map[key] = {
                "type": txn_type,
                "category": cat,
                "count": 0,
                "total": Decimal("0"),
                "deductible_total": Decimal("0"),
            }
        cat_map[key]["count"] += 1
        cat_map[key]["total"] += amt
        if txn_type == "expense" and t.is_deductible:
            cat_map[key]["deductible_total"] += amt

    by_category = sorted(cat_map.values(), key=lambda x: (-float(x["total"]), x["category"]))
    for item in by_category:
        item["total"] = round(float(item["total"]), 2)
        item["deductible_total"] = round(float(item["deductible_total"]), 2)

    return {
        "transaction_count": len(txns),
        "income_total": round(float(income_total), 2),
        "expense_total": round(float(expense_total), 2),
        "deductible_total": round(float(deductible_total), 2),
        "by_category": by_category,
    }
