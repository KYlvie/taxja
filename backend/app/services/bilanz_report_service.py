"""
Bilanz (Balance Sheet) + Gewinn- und Verlustrechnung (GuV) Service
Generates double-entry bookkeeping reports aligned with Austrian UGB/Kontenrahmen.

UGB §231 Gesamtkostenverfahren (Total Cost Method) for GuV.
UGB §224 for Bilanz structure.

Only applicable for:
- GmbH (always Bilanzierungspflicht)
- Self-employed / businesses with revenue > €700k (Buchführungspflicht)
"""
from decimal import Decimal
from datetime import date
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.transaction import (
    Transaction, TransactionType, IncomeCategory, ExpenseCategory,
)
from app.models.transaction_line_item import LineItemPostingType
from app.models.user import User
from app.services.posting_line_utils import iter_posting_records, sum_postings
from app.services.report_transaction_filters import (
    cash_balance_delta,
    should_include_in_bilanz_report,
)


# ── UGB §231 GuV Gesamtkostenverfahren ───────────────────────────────
# Numbered structure matching official Austrian annual report format.
# Each entry has a "nr" (display number), sub-items, and category mappings.

GUV_STRUCTURE = [
    {
        "nr": "1.",
        "key": "umsatzerloese",
        "label_de": "Umsatzerlöse",
        "label_en": "Revenue",
        "label_zh": "营业收入",
        "type": "income",
        "categories": [
            IncomeCategory.BUSINESS,
            IncomeCategory.SELF_EMPLOYMENT,
            IncomeCategory.AGRICULTURE,
            IncomeCategory.EMPLOYMENT,
            IncomeCategory.RENTAL,
            IncomeCategory.CAPITAL_GAINS,
            IncomeCategory.OTHER_INCOME,
        ],
        "sub_items": [],
    },
    {
        "nr": "2.",
        "key": "materialaufwand",
        "label_de": "Aufwendungen für Material und sonstige bezogene Herstellungsleistungen",
        "label_en": "Materials and Purchased Services",
        "label_zh": "材料及外购服务费用",
        "type": "expense",
        "categories": [ExpenseCategory.GROCERIES, ExpenseCategory.EQUIPMENT],
        "sub_items": [
            {
                "key": "materialaufwand_a",
                "label_de": "a) Materialaufwand",
                "label_en": "a) Material Costs",
                "label_zh": "a) 材料费用",
                "categories": [ExpenseCategory.GROCERIES],
            },
            {
                "key": "materialaufwand_b",
                "label_de": "b) Aufwendungen für bezogene Leistungen",
                "label_en": "b) Purchased Services",
                "label_zh": "b) 外购服务费用",
                "categories": [ExpenseCategory.EQUIPMENT],
            },
        ],
    },
    {
        "nr": "3.",
        "key": "personalaufwand",
        "label_de": "Personalaufwand",
        "label_en": "Personnel Expenses",
        "label_zh": "人工费用",
        "type": "expense",
        "categories": [],  # no direct mapping in our transaction model
        "sub_items": [
            {
                "key": "personalaufwand_a",
                "label_de": "a) Löhne und Gehälter",
                "label_en": "a) Wages and Salaries",
                "label_zh": "a) 工资薪金",
                "categories": [],
            },
            {
                "key": "personalaufwand_b",
                "label_de": "b) soziale Aufwendungen",
                "label_en": "b) Social Expenses",
                "label_zh": "b) 社会费用",
                "categories": [ExpenseCategory.SVS_CONTRIBUTIONS],
            },
        ],
    },
    {
        "nr": "4.",
        "key": "abschreibungen",
        "label_de": "Abschreibungen",
        "label_en": "Depreciation",
        "label_zh": "折旧",
        "type": "expense",
        "categories": [ExpenseCategory.DEPRECIATION],
        "sub_items": [
            {
                "key": "abschreibungen_a",
                "label_de": "a) auf Sachanlagen",
                "label_en": "a) on Tangible Assets",
                "label_zh": "a) 有形资产折旧",
                "categories": [ExpenseCategory.DEPRECIATION],
            },
        ],
    },
    {
        "nr": "5.",
        "key": "sonstige_betriebliche_aufwendungen",
        "label_de": "sonstige betriebliche Aufwendungen",
        "label_en": "Other Operating Expenses",
        "label_zh": "其他经营费用",
        "type": "expense",
        "categories": [
            ExpenseCategory.MAINTENANCE,
            ExpenseCategory.RENT,
            ExpenseCategory.VEHICLE,
            ExpenseCategory.COMMUTING,
            ExpenseCategory.TRAVEL,
            ExpenseCategory.TELECOM,
            ExpenseCategory.OFFICE_SUPPLIES,
            ExpenseCategory.HOME_OFFICE,
            ExpenseCategory.INSURANCE,
            ExpenseCategory.MARKETING,
            ExpenseCategory.PROFESSIONAL_SERVICES,
            ExpenseCategory.UTILITIES,
            ExpenseCategory.PROPERTY_TAX,
            ExpenseCategory.BANK_FEES,
            ExpenseCategory.LOAN_INTEREST,
            ExpenseCategory.OTHER,
        ],
        "sub_items": [],
    },
]


# Sub-detail mapping for "5. sonstige betriebliche Aufwendungen"
# These are shown as indented line items under section 5
SONSTIGE_DETAIL = [
    {
        "key": "instandhaltung",
        "label_de": "Aufwand für Instandhaltung, Betriebskosten",
        "label_en": "Maintenance and Operating Costs",
        "label_zh": "维修及运营费用",
        "categories": [ExpenseCategory.MAINTENANCE],
    },
    {
        "key": "reise_fahrtaufwand",
        "label_de": "Reise- und Fahrtaufwand",
        "label_en": "Travel Expenses",
        "label_zh": "差旅费用",
        "categories": [ExpenseCategory.TRAVEL],
    },
    {
        "key": "kfz_aufwand",
        "label_de": "KFZ-Aufwand",
        "label_en": "Vehicle Expenses",
        "label_zh": "车辆费用",
        "categories": [ExpenseCategory.VEHICLE, ExpenseCategory.COMMUTING],
    },
    {
        "key": "mietaufwand",
        "label_de": "Aufwand für Miete",
        "label_en": "Rent Expenses",
        "label_zh": "租赁费用",
        "categories": [ExpenseCategory.RENT],
    },
    {
        "key": "bueroaufwand",
        "label_de": "Aufwand für Büromaterial",
        "label_en": "Office Supplies",
        "label_zh": "办公用品费用",
        "categories": [ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.HOME_OFFICE],
    },
    {
        "key": "nachrichtenaufwand",
        "label_de": "Nachrichtenaufwand",
        "label_en": "Telecommunications",
        "label_zh": "通讯费用",
        "categories": [ExpenseCategory.TELECOM],
    },
    {
        "key": "werbeaufwand",
        "label_de": "Aufwand für Werbung",
        "label_en": "Advertising",
        "label_zh": "广告费用",
        "categories": [ExpenseCategory.MARKETING],
    },
    {
        "key": "versicherungsaufwand",
        "label_de": "Aufwand für Versicherungen",
        "label_en": "Insurance",
        "label_zh": "保险费用",
        "categories": [ExpenseCategory.INSURANCE],
    },
    {
        "key": "rechts_beratungsaufwand",
        "label_de": "Rechts- und Beratungsaufwand und Steuerberatung",
        "label_en": "Legal, Consulting and Tax Advisory",
        "label_zh": "法律及税务咨询费用",
        "categories": [ExpenseCategory.PROFESSIONAL_SERVICES],
    },
    {
        "key": "betriebsnebenkosten",
        "label_de": "Betriebsnebenkosten",
        "label_en": "Utilities",
        "label_zh": "水电气费用",
        "categories": [ExpenseCategory.UTILITIES, ExpenseCategory.PROPERTY_TAX],
    },
    {
        "key": "bankspesen",
        "label_de": "Spesen des Geldverkehrs",
        "label_en": "Bank Charges",
        "label_zh": "银行手续费",
        "categories": [ExpenseCategory.BANK_FEES],
    },
    {
        "key": "zinsaufwand",
        "label_de": "Zinsaufwand",
        "label_en": "Interest Expenses",
        "label_zh": "利息费用",
        "categories": [ExpenseCategory.LOAN_INTEREST],
    },
    {
        "key": "sonstiger_aufwand",
        "label_de": "diverse betriebliche Aufwendungen",
        "label_en": "Miscellaneous Operating Expenses",
        "label_zh": "其他杂项费用",
        "categories": [ExpenseCategory.OTHER],
    },
]


# ── Bilanz structure (Balance Sheet) — UGB §224 ─────────────────────
AKTIVA_STRUCTURE = {
    "umlaufvermoegen": {
        "nr": "A.",
        "label_de": "Umlaufvermögen",
        "label_en": "Current Assets",
        "label_zh": "流动资产",
        "items": {
            "forderungen": {
                "label_de": "Forderungen und sonstige Vermögensgegenstände",
                "label_en": "Receivables and Other Assets",
                "label_zh": "应收款项及其他资产",
                "source": "receivables",
            },
            "bankguthaben": {
                "label_de": "Kassenbestand, Guthaben bei Kreditinstituten",
                "label_en": "Cash and Bank Balances",
                "label_zh": "现金及银行存款",
                "source": "cash_balance",
            },
        },
    },
}

PASSIVA_STRUCTURE = {
    "eigenkapital": {
        "nr": "A.",
        "label_de": "Eigenkapital",
        "label_en": "Equity",
        "label_zh": "所有者权益",
        "items": {
            "stammkapital": {
                "label_de": "eingefordertes Stammkapital",
                "label_en": "Called-up Share Capital",
                "label_zh": "实缴注册资本",
                "source": "equity_capital",
            },
            "bilanzgewinn": {
                "label_de": "Bilanzgewinn / -verlust",
                "label_en": "Retained Earnings / Loss",
                "label_zh": "留存收益 / 亏损",
                "source": "net_profit",
            },
        },
    },
    "rueckstellungen": {
        "nr": "B.",
        "label_de": "Rückstellungen",
        "label_en": "Provisions",
        "label_zh": "准备金",
        "items": {
            "steuerrueckstellungen": {
                "label_de": "Rückstellungen für Steuern",
                "label_en": "Tax Provisions",
                "label_zh": "税金准备",
                "source": "tax_provisions",
            },
        },
    },
    "verbindlichkeiten": {
        "nr": "C.",
        "label_de": "Verbindlichkeiten",
        "label_en": "Liabilities",
        "label_zh": "负债",
        "items": {
            "darlehen_kredite": {
                "label_de": "Darlehen und Kredite",
                "label_en": "Loans and Borrowings",
                "label_zh": "贷款及借款",
                "source": "loans",
            },
            "lieferverbindlichkeiten": {
                "label_de": "sonstige Verbindlichkeiten",
                "label_en": "Other Liabilities",
                "label_zh": "其他负债",
                "source": "payables",
            },
        },
    },
}


def generate_bilanz_report(
    db: Session,
    user: User,
    tax_year: int,
    language: str = "de",
) -> Dict[str, Any]:
    """Generate a Bilanz (Balance Sheet) + GuV (P&L) report.

    Follows UGB §231 Gesamtkostenverfahren for GuV and UGB §224 for Bilanz.
    Includes prior-year (Vorjahr) comparison column.
    """
    lang_key = f"label_{language}" if language in ("de", "en", "zh", "fr", "ru", "hu", "pl", "tr", "bs") else "label_de"

    # Current year transactions
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .order_by(Transaction.transaction_date)
        .all()
    )
    transactions = [t for t in transactions if should_include_in_bilanz_report(t)]

    # Prior year transactions (for Vorjahr column)
    prior_transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year - 1,
        )
        .all()
    )
    prior_transactions = [t for t in prior_transactions if should_include_in_bilanz_report(t)]

    # ── Build GuV (UGB §231) ─────────────────────────────────────────
    guv_lines = _build_guv(transactions, prior_transactions, lang_key)

    total_income = Decimal("0")
    total_expenses = Decimal("0")
    total_income_prior = Decimal("0")
    total_expenses_prior = Decimal("0")

    for line in guv_lines:
        if line["line_type"] == "income":
            total_income += Decimal(str(line["amount"]))
            total_income_prior += Decimal(str(line["amount_prior"]))
        elif line["line_type"] == "expense":
            total_expenses += Decimal(str(line["amount"]))
            total_expenses_prior += Decimal(str(line["amount_prior"]))

    # Betriebsergebnis (Z 1 bis 5)
    betriebsergebnis = total_income - total_expenses
    betriebsergebnis_prior = total_income_prior - total_expenses_prior

    # For now we skip Z 7 (Zinserträge) and Z 8 (Finanzergebnis) — they are 0
    # Z 9 = Ergebnis vor Steuern
    ergebnis_vor_steuern = betriebsergebnis
    ergebnis_vor_steuern_prior = betriebsergebnis_prior

    # Z 10 = Steuern vom Einkommen (KöSt 23% for GmbH, ESt estimate otherwise)
    koest_rate = Decimal("0.23")
    steuern = max(ergebnis_vor_steuern * koest_rate, Decimal("0"))
    steuern_prior = max(ergebnis_vor_steuern_prior * koest_rate, Decimal("0"))

    # Z 11 = Ergebnis nach Steuern
    ergebnis_nach_steuern = ergebnis_vor_steuern - steuern
    ergebnis_nach_steuern_prior = ergebnis_vor_steuern_prior - steuern_prior

    net_profit = ergebnis_nach_steuern

    # ── Build Bilanz ─────────────────────────────────────────────────
    equipment_total = sum_postings(
        transactions,
        posting_types={LineItemPostingType.ASSET_ACQUISITION},
        include_private_use=False,
    ) + sum_postings(
        transactions,
        posting_types={LineItemPostingType.EXPENSE},
        categories=_category_tokens([ExpenseCategory.EQUIPMENT, ExpenseCategory.VEHICLE]),
        include_private_use=False,
    )
    loan_drawdowns = sum_postings(
        transactions,
        posting_types={LineItemPostingType.LIABILITY_DRAWDOWN},
        include_private_use=False,
    )
    loan_repayments = sum_postings(
        transactions,
        posting_types={LineItemPostingType.LIABILITY_REPAYMENT},
        include_private_use=False,
    )
    cash_balance = Decimal("0")
    for t in transactions:
        cash_balance += cash_balance_delta(t)

    loan_balance = max(loan_drawdowns - loan_repayments, Decimal("0"))

    balance_values = {
        "equipment_net": float(equipment_total),
        "receivables": 0.0,
        "cash_balance": float(cash_balance),
        "equity_capital": 0.0,
        "net_profit": float(net_profit),
        "payables": 0.0,
        "loans": float(loan_balance),
        "tax_provisions": float(steuern),
    }

    aktiva = _build_balance_section(AKTIVA_STRUCTURE, balance_values, lang_key)
    passiva = _build_balance_section(PASSIVA_STRUCTURE, balance_values, lang_key)

    total_aktiva = sum(g["subtotal"] for g in aktiva)
    total_passiva = sum(g["subtotal"] for g in passiva)

    # VAT summary
    vat_collected = sum(
        (
            record.vat_amount
            for record in iter_posting_records(transactions, include_private_use=False)
            if record.posting_type == LineItemPostingType.INCOME
        ),
        Decimal("0"),
    )
    vat_paid = sum(
        (
            record.vat_amount
            for record in iter_posting_records(transactions, include_private_use=False)
            if record.posting_type in {
                LineItemPostingType.EXPENSE,
                LineItemPostingType.ASSET_ACQUISITION,
            }
        ),
        Decimal("0"),
    )

    return {
        "report_type": "bilanz",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "user_type": user.user_type.value if user.user_type else "mixed",
        "tax_number": user.tax_number or "",
        "generated_at": date.today().isoformat(),
        "guv": {
            "lines": guv_lines,
            "total_income": float(total_income),
            "total_expenses": float(total_expenses),
            "betriebsergebnis": float(betriebsergebnis),
            "betriebsergebnis_prior": float(betriebsergebnis_prior),
            "ergebnis_vor_steuern": float(ergebnis_vor_steuern),
            "ergebnis_vor_steuern_prior": float(ergebnis_vor_steuern_prior),
            "steuern": float(steuern),
            "steuern_prior": float(steuern_prior),
            "ergebnis_nach_steuern": float(ergebnis_nach_steuern),
            "ergebnis_nach_steuern_prior": float(ergebnis_nach_steuern_prior),
            "net_profit": float(net_profit),
        },
        "bilanz": {
            "aktiva": aktiva,
            "passiva": passiva,
            "total_aktiva": float(total_aktiva),
            "total_passiva": float(total_passiva),
        },
        "vat_summary": {
            "vat_collected": float(vat_collected),
            "vat_paid": float(vat_paid),
            "vat_balance": float(vat_collected - vat_paid),
        },
        "transaction_count": len(transactions),
    }


def _category_tokens(categories: list) -> set[str]:
    return {
        category.value if hasattr(category, "value") else str(category)
        for category in categories
    }


def _sum_by_categories(
    transactions: List[Transaction],
    *,
    posting_type: LineItemPostingType,
    categories: list,
) -> Decimal:
    """Sum canonical posting lines matching the given category bucket."""
    return sum_postings(
        transactions,
        posting_types={posting_type},
        categories=_category_tokens(categories),
        include_private_use=False,
    )


def _build_guv(
    transactions: List[Transaction],
    prior_transactions: List[Transaction],
    lang_key: str,
) -> List[Dict[str, Any]]:
    """Build GuV lines following UGB §231 Gesamtkostenverfahren.

    Returns a flat list of line dicts, each with:
      nr, key, label, amount, amount_prior, line_type, depth, sub_items
    """
    lines = []
    for section in GUV_STRUCTURE:
        is_income = section["type"] == "income"
        posting_type = (
            LineItemPostingType.INCOME
            if is_income
            else LineItemPostingType.EXPENSE
        )

        # Collect all categories for this section (including sub-items)
        all_cats = list(section["categories"])
        for sub in section.get("sub_items", []):
            all_cats.extend(sub["categories"])

        amount = _sum_by_categories(
            transactions,
            posting_type=posting_type,
            categories=all_cats,
        )
        amount_prior = _sum_by_categories(
            prior_transactions,
            posting_type=posting_type,
            categories=all_cats,
        )

        # Build sub-item details for section 5 (sonstige betriebliche Aufwendungen)
        sub_lines = []
        if section["key"] == "sonstige_betriebliche_aufwendungen":
            # Use SONSTIGE_DETAIL for detailed breakdown
            for detail in SONSTIGE_DETAIL:
                d_amt = _sum_by_categories(
                    transactions,
                    posting_type=posting_type,
                    categories=detail["categories"],
                )
                d_amt_prior = _sum_by_categories(
                    prior_transactions,
                    posting_type=posting_type,
                    categories=detail["categories"],
                )
                if d_amt or d_amt_prior:
                    sub_lines.append({
                        "key": detail["key"],
                        "label": detail.get(lang_key, detail["label_de"]),
                        "amount": float(d_amt),
                        "amount_prior": float(d_amt_prior),
                    })
        elif section.get("sub_items"):
            for sub in section["sub_items"]:
                s_amt = _sum_by_categories(
                    transactions,
                    posting_type=posting_type,
                    categories=sub["categories"],
                )
                s_amt_prior = _sum_by_categories(
                    prior_transactions,
                    posting_type=posting_type,
                    categories=sub["categories"],
                )
                if s_amt or s_amt_prior:
                    sub_lines.append({
                        "key": sub["key"],
                        "label": sub.get(lang_key, sub["label_de"]),
                        "amount": float(s_amt),
                        "amount_prior": float(s_amt_prior),
                    })

        if amount or amount_prior:
            lines.append({
                "nr": section["nr"],
                "key": section["key"],
                "label": section.get(lang_key, section["label_de"]),
                "amount": float(amount),
                "amount_prior": float(amount_prior),
                "line_type": section["type"],
                "sub_items": sub_lines,
            })

    return lines


def _build_balance_section(
    structure: Dict, values: Dict[str, float], lang_key: str
) -> List[Dict[str, Any]]:
    """Build balance sheet groups from structure definition."""
    groups = []
    for group_key, group_def in structure.items():
        items = []
        group_total = Decimal("0")
        for item_key, item_def in group_def["items"].items():
            val = values.get(item_def["source"], 0.0)
            items.append({
                "key": item_key,
                "label": item_def.get(lang_key, item_def["label_de"]),
                "amount": val,
            })
            group_total += Decimal(str(val))
        groups.append({
            "key": group_key,
            "label": group_def.get(lang_key, group_def["label_de"]),
            "items": items,
            "subtotal": float(group_total),
        })
    return groups
