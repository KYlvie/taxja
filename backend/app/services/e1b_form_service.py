"""
E1b Form Service — Beilage zur Einkommensteuererklaerung (Vermietung und Verpachtung)

Generates per-property E1b supplement forms with detailed V+V Kennzahlen.
Each rental property gets its own E1b with income, expenses, AfA, loan interest,
management fees, insurance, and Grundsteuer broken down individually.

Reference: BMF FinanzOnline E1b form
"""
from decimal import Decimal
from datetime import date
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.property import Property, PropertyStatus
from app.models.user import User


def _sum_property_income(transactions: list, property_id) -> Decimal:
    """Sum rental income for a specific property."""
    return sum(
        (t.amount or Decimal("0"))
        for t in transactions
        if (t.type == TransactionType.INCOME
            and t.income_category == IncomeCategory.RENTAL
            and t.property_id == property_id)
    )


def _sum_property_expense(transactions: list, property_id, categories: list) -> Decimal:
    """Sum deductible expenses for a specific property, using line-item-level amounts."""
    total = Decimal("0")
    cat_values = {c.value if hasattr(c, "value") else str(c) for c in categories}
    for t in transactions:
        if t.type != TransactionType.EXPENSE:
            continue
        if t.property_id != property_id:
            continue
        has_line_items = bool(getattr(t, "has_line_items", False))
        line_items = getattr(t, "line_items", None)
        use_line_items = False

        if has_line_items and line_items is not None:
            try:
                line_items = list(line_items)
                use_line_items = True
            except TypeError:
                line_items = []

        if use_line_items:
            for li in line_items:
                if not li.is_deductible:
                    continue
                li_cat = li.category or "other"
                if li_cat not in cat_values:
                    continue
                total += li.amount * li.quantity
        else:
            if t.expense_category not in categories:
                continue
            if not t.is_deductible:
                continue
            total += t.amount or Decimal("0")
    return total


def generate_e1b_form_data(
    db: Session,
    user: User,
    tax_year: int,
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate E1b form data — per-property V+V breakdown.

    If property_id is specified, generates for one property only.
    Otherwise generates for all rental properties of the user.
    Returns a structure with one E1b per property.
    """
    # Query properties
    query = db.query(Property).filter(
        Property.user_id == user.id,
        Property.status.in_([PropertyStatus.ACTIVE, PropertyStatus.SOLD]),
    )
    if property_id:
        query = query.filter(Property.id == property_id)
    properties = query.all()

    # Query all transactions for the tax year
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .all()
    )

    property_forms: List[Dict[str, Any]] = []

    for prop in properties:
        pid = prop.id

        # Income
        rental_income = _sum_property_income(transactions, pid)
        betriebskosten_income = sum(
            (t.amount or Decimal("0"))
            for t in transactions
            if (t.type == TransactionType.INCOME
                and t.expense_category in [ExpenseCategory.UTILITIES, ExpenseCategory.PROPERTY_TAX]
                and t.property_id == pid)
        )

        # Expenses by category
        instandsetzung = _sum_property_expense(transactions, pid, [ExpenseCategory.MAINTENANCE])
        instandhaltung = _sum_property_expense(transactions, pid, [ExpenseCategory.OTHER])
        # Building AfA: always calculate from property data (not from transactions)
        from app.services.afa_calculator import AfACalculator
        afa_calc = AfACalculator(db)
        afa_building = afa_calc.calculate_annual_depreciation(prop, tax_year)
        afa_equipment = _sum_property_expense(transactions, pid, [ExpenseCategory.DEPRECIATION])
        loan_interest = _sum_property_expense(transactions, pid, [ExpenseCategory.LOAN_INTEREST])
        mgmt_fees = _sum_property_expense(transactions, pid, [ExpenseCategory.PROPERTY_MANAGEMENT_FEES])
        insurance = _sum_property_expense(transactions, pid, [ExpenseCategory.PROPERTY_INSURANCE, ExpenseCategory.INSURANCE])
        grundsteuer = _sum_property_expense(transactions, pid, [ExpenseCategory.PROPERTY_TAX])
        other_vv = _sum_property_expense(transactions, pid, [
            ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.PROFESSIONAL_SERVICES,
            ExpenseCategory.BANK_FEES, ExpenseCategory.TELECOM,
        ])

        total_expenses = (
            instandsetzung + instandhaltung + afa_building + afa_equipment
            + loan_interest + mgmt_fees + insurance + grundsteuer + other_vv
        )
        surplus = rental_income - total_expenses

        # (AfA is now always calculated from property data above)

        fields = [
            {
                "kz": "9410",
                "label_de": "Mieteinnahmen (brutto)",
                "label_en": "Rental income (gross)",
                "label_zh": "租金收入（毛）",
                "value": float(rental_income),
                "section": "einnahmen",
                "editable": True,
            },
            {
                "kz": "9411",
                "label_de": "Betriebskosteneinnahmen (umgelegte Kosten)",
                "label_en": "Operating cost income (passed through)",
                "label_zh": "运营费用收入（转嫁部分）",
                "value": float(betriebskosten_income),
                "section": "einnahmen",
                "editable": True,
            },
            {
                "kz": "9420",
                "label_de": "Instandsetzung (grosse Reparaturen, 10/15 Jahre verteilt)",
                "label_en": "Major repairs (amortized 10/15 years)",
                "label_zh": "大修（10/15年分摊）",
                "value": float(instandsetzung),
                "section": "werbungskosten",
                "editable": True,
                "note_de": "Verteilung auf 10 Jahre (Mietwohngebaeude: 15 Jahre, §28 Abs.2 EStG)",
            },
            {
                "kz": "9421",
                "label_de": "Instandhaltung (kleine Reparaturen, sofort absetzbar)",
                "label_en": "Minor repairs (immediately deductible)",
                "label_zh": "小修（当年全额扣除）",
                "value": float(instandhaltung),
                "section": "werbungskosten",
                "editable": True,
            },
            {
                "kz": "9430",
                "label_de": "Gebaeude-AfA (Absetzung fuer Abnutzung)",
                "label_en": "Building depreciation (AfA)",
                "label_zh": "建筑折旧 (AfA)",
                "value": float(afa_building),
                "section": "werbungskosten",
                "editable": True,
                "note_de": "1,5% p.a. des Gebaeudewertes (§16 Abs.1 Z8 EStG)",
            },
            {
                "kz": "9431",
                "label_de": "Einrichtungs-AfA (Moebel, Geraete)",
                "label_en": "Equipment depreciation",
                "label_zh": "设备折旧",
                "value": float(afa_equipment),
                "section": "werbungskosten",
                "editable": True,
            },
            {
                "kz": "9440",
                "label_de": "Finanzierungskosten (Kreditzinsen)",
                "label_en": "Loan interest",
                "label_zh": "贷款利息",
                "value": float(loan_interest),
                "section": "werbungskosten",
                "editable": True,
            },
            {
                "kz": "9450",
                "label_de": "Hausverwaltungskosten",
                "label_en": "Property management fees",
                "label_zh": "物业管理费",
                "value": float(mgmt_fees),
                "section": "werbungskosten",
                "editable": True,
            },
            {
                "kz": "9451",
                "label_de": "Versicherungen (Gebaeude)",
                "label_en": "Building insurance",
                "label_zh": "建筑保险",
                "value": float(insurance),
                "section": "werbungskosten",
                "editable": True,
            },
            {
                "kz": "9452",
                "label_de": "Grundsteuer",
                "label_en": "Property tax (Grundsteuer)",
                "label_zh": "房产税",
                "value": float(grundsteuer),
                "section": "werbungskosten",
                "editable": True,
            },
            {
                "kz": "9460",
                "label_de": "Sonstige Werbungskosten (V+V)",
                "label_en": "Other rental expenses",
                "label_zh": "其他租赁费用",
                "value": float(other_vv),
                "section": "werbungskosten",
                "editable": True,
            },
            {
                "kz": "9470",
                "label_de": "Ueberschuss / Verlust (diese Liegenschaft)",
                "label_en": "Surplus / loss (this property)",
                "label_zh": "盈余/亏损（此物业）",
                "value": float(surplus),
                "section": "ergebnis",
                "editable": False,
            },
        ]

        prop_address = ""
        try:
            prop_address = prop.address or ""
        except Exception:
            pass

        property_forms.append({
            "property_id": str(pid),
            "property_name": prop.name or prop_address,
            "property_address": prop_address,
            "purchase_date": prop.purchase_date.isoformat() if prop.purchase_date else None,
            "purchase_price": float(prop.purchase_price) if prop.purchase_price else None,
            "building_value": float(prop.building_value) if prop.building_value else None,
            "depreciation_rate": float(prop.depreciation_rate) if prop.depreciation_rate else None,
            "rental_percentage": float(prop.rental_percentage) if prop.rental_percentage else 100.0,
            "fields": fields,
            "summary": {
                "rental_income": float(rental_income),
                "total_expenses": float(total_expenses),
                "surplus": float(surplus),
                "afa_building": float(afa_building),
                "loan_interest": float(loan_interest),
            },
        })

    # Aggregate totals across all properties
    total_vv_income = sum(f["summary"]["rental_income"] for f in property_forms)
    total_vv_expenses = sum(f["summary"]["total_expenses"] for f in property_forms)
    total_vv_surplus = sum(f["summary"]["surplus"] for f in property_forms)

    return {
        "form_type": "E1b",
        "form_name_de": "Beilage zur Einkommensteuererklaerung — Vermietung und Verpachtung",
        "form_name_en": "Supplement to Income Tax Return — Rental Income",
        "form_name_zh": "所得税申报附表 — 租赁收入",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "tax_number": user.tax_number or "",
        "generated_at": date.today().isoformat(),
        "properties": property_forms,
        "aggregate_summary": {
            "property_count": len(property_forms),
            "total_rental_income": total_vv_income,
            "total_rental_expenses": total_vv_expenses,
            "total_surplus": total_vv_surplus,
        },
        "disclaimer_de": (
            "Diese Daten dienen als Ausfuellhilfe fuer die Beilage E1b. "
            "Bitte pruefen Sie alle Werte je Liegenschaft sorgfaeltig. "
            "Keine Steuerberatung."
        ),
        "disclaimer_en": (
            "This data is a filling aid for the E1b supplement. "
            "Please verify all values per property carefully. Not tax advice."
        ),
    }
