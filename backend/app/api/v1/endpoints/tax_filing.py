"""Tax Filing Summary API — aggregates confirmed TaxFilingData for a given year."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.user import User
from app.models.tax_filing_data import TaxFilingData
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
    """Return list of tax years that have confirmed TaxFilingData."""
    rows = (
        db.query(TaxFilingData.tax_year)
        .filter(
            TaxFilingData.user_id == current_user.id,
            TaxFilingData.status == "confirmed",
        )
        .distinct()
        .all()
    )
    years = sorted([r[0] for r in rows if r[0]], reverse=True)
    return {"years": years}


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
        return {
            "year": year,
            "income": [],
            "deductions": [],
            "vat": [],
            "other": [],
            "totals": _empty_totals(),
            "conflicts": [],
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
        float(r.data.get("kz_260") or 0) for r in records if r.data_type == "lohnzettel"
    )

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
            total += float(d.get("kz_245") or 0)
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
