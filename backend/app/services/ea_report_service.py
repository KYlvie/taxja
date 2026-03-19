"""
Einnahmen-Ausgaben-Rechnung (E/A Rechnung) Service
Generates professional Austrian income-expense reports grouped by category.
Aligned with standard Austrian Kontenrahmen for Einzelunternehmen.
"""
from decimal import Decimal
from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User, UserType


INCOME_GROUPS = {
    "land_forstwirtschaft": {
        "label_de": "Einkünfte aus Land- und Forstwirtschaft",
        "label_en": "Agriculture and Forestry Income",
        "label_zh": "农林业收入",
        "categories": [IncomeCategory.AGRICULTURE],
    },
    "selbstaendige_arbeit": {
        "label_de": "Einkünfte aus selbständiger Arbeit",
        "label_en": "Self-Employment Income (Freelance)",
        "label_zh": "自由职业收入",
        "categories": [IncomeCategory.SELF_EMPLOYMENT],
    },
    "gewerbebetrieb": {
        "label_de": "Einkünfte aus Gewerbebetrieb",
        "label_en": "Business Income",
        "label_zh": "工商营业收入",
        "categories": [IncomeCategory.BUSINESS],
    },
    "lohneinkuenfte": {
        "label_de": "Einkünfte aus nichtselbständiger Arbeit",
        "label_en": "Employment Income",
        "label_zh": "工资收入",
        "categories": [IncomeCategory.EMPLOYMENT],
    },
    "kapitaleinkuenfte": {
        "label_de": "Einkünfte aus Kapitalvermögen",
        "label_en": "Capital Gains",
        "label_zh": "资本收益",
        "categories": [IncomeCategory.CAPITAL_GAINS],
    },
    "mieteinkuenfte": {
        "label_de": "Einkünfte aus Vermietung und Verpachtung",
        "label_en": "Rental Income",
        "label_zh": "租金收入",
        "categories": [IncomeCategory.RENTAL],
    },
    "sonstige_einkuenfte": {
        "label_de": "Sonstige Einkünfte",
        "label_en": "Other Income",
        "label_zh": "其他收入",
        "categories": [IncomeCategory.OTHER_INCOME],
    },
}

EXPENSE_GROUPS = {
    "materialaufwand": {
        "label_de": "Aufwendungen für Material und Waren",
        "label_en": "Materials / Cost of Goods",
        "label_zh": "材料及商品成本",
        "categories": [ExpenseCategory.GROCERIES],
    },
    "instandhaltung": {
        "label_de": "Aufwand für Instandhaltung, Betriebskosten",
        "label_en": "Maintenance and Operating Costs",
        "label_zh": "维修及运营成本",
        "categories": [ExpenseCategory.MAINTENANCE],
    },
    "reisekosten": {
        "label_de": "Reise- und Fahrtaufwand",
        "label_en": "Travel Expenses",
        "label_zh": "差旅费用",
        "categories": [ExpenseCategory.TRAVEL],
    },
    "kfz": {
        "label_de": "KFZ-Aufwand",
        "label_en": "Vehicle Expenses",
        "label_zh": "车辆费用",
        "categories": [ExpenseCategory.VEHICLE, ExpenseCategory.COMMUTING],
    },
    "miete": {
        "label_de": "Aufwand für Miete",
        "label_en": "Rent Expenses",
        "label_zh": "租金支出",
        "categories": [ExpenseCategory.RENT],
    },
    "bueromaterial": {
        "label_de": "Aufwand für Büromaterial",
        "label_en": "Office Supplies",
        "label_zh": "办公用品",
        "categories": [ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.HOME_OFFICE],
    },
    "nachrichtenaufwand": {
        "label_de": "Nachrichtenaufwand",
        "label_en": "Telecommunications",
        "label_zh": "通讯费用",
        "categories": [ExpenseCategory.TELECOM],
    },
    "marketing": {
        "label_de": "Aufwand für Werbung",
        "label_en": "Advertising and Marketing",
        "label_zh": "广告及营销",
        "categories": [ExpenseCategory.MARKETING],
    },
    "versicherung": {
        "label_de": "Aufwand für Versicherungen",
        "label_en": "Insurance",
        "label_zh": "保险费用",
        "categories": [ExpenseCategory.INSURANCE],
    },
    "beratung": {
        "label_de": "Rechts- und Beratungsaufwand und Steuerberatung",
        "label_en": "Legal, Consulting and Tax Advisory",
        "label_zh": "法律及税务咨询",
        "categories": [ExpenseCategory.PROFESSIONAL_SERVICES],
    },
    "abschreibung": {
        "label_de": "Abschreibungen (AfA)",
        "label_en": "Depreciation",
        "label_zh": "折旧",
        "categories": [ExpenseCategory.DEPRECIATION],
    },
    "betriebsmittel": {
        "label_de": "Betriebsmittel und Ausstattung",
        "label_en": "Equipment and Supplies",
        "label_zh": "设备及用品",
        "categories": [ExpenseCategory.EQUIPMENT],
    },
    "nebenkosten": {
        "label_de": "Betriebsnebenkosten",
        "label_en": "Utilities",
        "label_zh": "水电费",
        "categories": [ExpenseCategory.UTILITIES, ExpenseCategory.PROPERTY_TAX],
    },
    "svs_beitraege": {
        "label_de": "Gebühren und Beiträge (SVS)",
        "label_en": "Social Insurance Contributions (SVS)",
        "label_zh": "社会保险缴费 (SVS)",
        "categories": [ExpenseCategory.SVS_CONTRIBUTIONS],
    },
    "bankspesen": {
        "label_de": "Spesen des Geldverkehrs",
        "label_en": "Bank Fees",
        "label_zh": "银行手续费",
        "categories": [ExpenseCategory.BANK_FEES],
    },
    "zinsen": {
        "label_de": "Zinsaufwand",
        "label_en": "Interest Expenses",
        "label_zh": "利息支出",
        "categories": [ExpenseCategory.LOAN_INTEREST],
    },
    "sonstige": {
        "label_de": "Sonstige betriebliche Aufwendungen",
        "label_en": "Other Operating Expenses",
        "label_zh": "其他经营费用",
        "categories": [ExpenseCategory.OTHER],
    },
}


def generate_ea_report(
    db: Session,
    user: User,
    tax_year: int,
    language: str = "de",
) -> Dict[str, Any]:
    """Generate a structured E/A Rechnung report."""
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .order_by(Transaction.transaction_date)
        .all()
    )

    lang_key = f"label_{language}" if language in ("de", "en", "zh") else "label_de"

    # Build income section
    income_sections = []
    total_income = Decimal("0")

    for group_key, group_def in INCOME_GROUPS.items():
        items = []
        group_total = Decimal("0")
        for t in transactions:
            if t.type == TransactionType.INCOME and t.income_category in group_def["categories"]:
                items.append({
                    "date": t.transaction_date.isoformat() if t.transaction_date else "",
                    "description": t.description or "",
                    "amount": float(t.amount or 0),
                    "is_deductible": t.is_deductible,
                })
                group_total += t.amount or Decimal("0")

        if items:
            income_sections.append({
                "key": group_key,
                "label": group_def.get(lang_key, group_def["label_de"]),
                "items": items,
                "subtotal": float(group_total),
            })
            total_income += group_total

    # Build expense section
    expense_sections = []
    total_expenses = Decimal("0")
    total_deductible = Decimal("0")
    assigned_expense_ids = set()

    # Build reverse map: category_value → group_key for line-item routing
    _cat_to_group: dict = {}
    for gk, gdef in EXPENSE_GROUPS.items():
        for cat_enum in gdef["categories"]:
            _cat_to_group[cat_enum.value if hasattr(cat_enum, "value") else str(cat_enum)] = gk

    def _ensure_section(group_key):
        """Get or create an expense section for the given group key."""
        for s in expense_sections:
            if s["key"] == group_key:
                return s
        gdef = EXPENSE_GROUPS.get(group_key, EXPENSE_GROUPS["sonstige"])
        section = {
            "key": group_key,
            "label": gdef.get(lang_key, gdef["label_de"]),
            "items": [],
            "subtotal": 0.0,
            "deductible_subtotal": 0.0,
        }
        expense_sections.append(section)
        return section

    for t in transactions:
        if t.type != TransactionType.EXPENSE:
            continue
        if t.id in assigned_expense_ids:
            continue
        assigned_expense_ids.add(t.id)

        if t.has_line_items:
            # Expand line items into individual report rows per category group
            for li in t.line_items:
                li_cat = li.category or "other"
                gk = _cat_to_group.get(li_cat, "sonstige")
                section = _ensure_section(gk)
                li_amt = float(li.amount * li.quantity)
                section["items"].append({
                    "date": t.transaction_date.isoformat() if t.transaction_date else "",
                    "description": f"{t.description or ''} — {li.description}",
                    "amount": li_amt,
                    "is_deductible": li.is_deductible,
                })
                section["subtotal"] += li_amt
                total_expenses += Decimal(str(li_amt))
                if li.is_deductible:
                    section["deductible_subtotal"] += li_amt
                    total_deductible += Decimal(str(li_amt))
        else:
            # Legacy: whole-transaction amount
            cat_val = (
                t.expense_category.value
                if t.expense_category and hasattr(t.expense_category, "value")
                else str(t.expense_category) if t.expense_category else "other"
            )
            gk = _cat_to_group.get(cat_val, "sonstige")
            section = _ensure_section(gk)
            amt = t.amount or Decimal("0")
            section["items"].append({
                "date": t.transaction_date.isoformat() if t.transaction_date else "",
                "description": t.description or "",
                "amount": float(amt),
                "is_deductible": t.is_deductible,
            })
            section["subtotal"] += float(amt)
            total_expenses += amt
            if t.is_deductible:
                section["deductible_subtotal"] += float(amt)
                total_deductible += amt

    # Remove empty sections
    expense_sections = [s for s in expense_sections if s["items"]]

    # VAT summary
    total_vat_collected = Decimal("0")
    total_vat_paid = Decimal("0")
    for t in transactions:
        if t.vat_amount:
            if t.type == TransactionType.INCOME:
                total_vat_collected += t.vat_amount
            else:
                total_vat_paid += t.vat_amount

    betriebsergebnis = total_income - total_expenses

    return {
        "report_type": "ea_rechnung",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "user_type": user.user_type.value if user.user_type else "mixed",
        "tax_number": user.tax_number or "",
        "generated_at": date.today().isoformat(),
        "income_sections": income_sections,
        "expense_sections": expense_sections,
        "summary": {
            "total_income": float(total_income),
            "total_expenses": float(total_expenses),
            "total_deductible": float(total_deductible),
            "betriebsergebnis": float(betriebsergebnis),
            "total_vat_collected": float(total_vat_collected),
            "total_vat_paid": float(total_vat_paid),
            "vat_balance": float(total_vat_collected - total_vat_paid),
        },
        "transaction_count": len(transactions),
    }
