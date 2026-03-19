"""
E1a Form Service — Beilage zur Einkommensteuererklaerung (Einzelunternehmer)

Generates E1a supplement form for sole proprietors (Einzelunternehmen)
with EA-Rechnung (Einnahmen-Ausgaben-Rechnung) breakdown per §4 Abs 3 EStG.

Includes: Gewinnfreibetrag, Basispauschalierung, detailed expense categories.
All thresholds loaded from DB TaxConfiguration per year.

Reference: BMF FinanzOnline E1a form
"""
import logging
from decimal import Decimal
from datetime import date
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User

logger = logging.getLogger(__name__)

# Fallback defaults (2026 values) — used only when DB config unavailable
_FALLBACK_SELF_EMPLOYED = {
    "grundfreibetrag_profit_limit": 33000.00,
    "grundfreibetrag_rate": 0.15,
    "grundfreibetrag_max": 4950.00,
    "flat_rate_turnover_limit": 420000.00,
    "flat_rate_general": 0.15,
    "flat_rate_consulting": 0.06,
}

# Investitionsfreibetrag is statutory and doesn't change by year
INVESTITIONSFREIBETRAG_RATE = Decimal("0.13")  # 13% on EUR 33,001-175,000
INVESTITIONSFREIBETRAG_MAX_BASE = Decimal("175000")


def _load_self_employed_config(db: Session, tax_year: int) -> dict:
    """Load self-employed config from DB for the given tax year."""
    try:
        from app.models.tax_configuration import TaxConfiguration
        config_row = db.query(TaxConfiguration).filter(
            TaxConfiguration.tax_year == tax_year
        ).first()
        if config_row and config_row.deduction_config:
            se = config_row.deduction_config.get("self_employed", {})
            if se:
                return se
    except Exception as e:
        logger.warning("Failed to load self-employed config for %d: %s", tax_year, e)
    return _FALLBACK_SELF_EMPLOYED


def _sum_income(transactions: list, cats: list) -> Decimal:
    return sum(
        (t.amount or Decimal("0"))
        for t in transactions
        if t.type == TransactionType.INCOME and t.income_category in cats
    )


def _sum_expense(transactions: list, cats: list, deductible_only: bool = True) -> Decimal:
    """Sum expenses by category, using line-item-level amounts when available."""
    total = Decimal("0")
    cat_values = {c.value if hasattr(c, "value") else str(c) for c in cats}
    for t in transactions:
        if t.type != TransactionType.EXPENSE:
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
                li_cat = li.category or "other"
                if li_cat not in cat_values:
                    continue
                if deductible_only and not li.is_deductible:
                    continue
                total += li.amount * li.quantity
        else:
            if t.expense_category not in cats:
                continue
            if deductible_only and not t.is_deductible:
                continue
            total += t.amount or Decimal("0")
    return total


def _calculate_gewinnfreibetrag(profit: Decimal, se_config: dict) -> Dict[str, Decimal]:
    """Calculate Gewinnfreibetrag (§10 EStG) using year-specific config.

    Grundfreibetrag: rate% on first profit_limit of profit
    Investitionsbedingter GFB: 13% on profit_limit+1 - 175,000
    """
    if profit <= 0:
        return {"grundfreibetrag": Decimal("0"), "investitions_gfb": Decimal("0"), "total": Decimal("0")}

    grund_rate = Decimal(str(se_config.get("grundfreibetrag_rate", 0.15)))
    grund_limit = Decimal(str(se_config.get("grundfreibetrag_profit_limit", 33000)))

    grund_base = min(profit, grund_limit)
    grundfreibetrag = (grund_base * grund_rate).quantize(Decimal("0.01"))

    invest_base = Decimal("0")
    if profit > grund_limit:
        invest_base = min(profit, INVESTITIONSFREIBETRAG_MAX_BASE) - grund_limit
    investitions_gfb = (invest_base * INVESTITIONSFREIBETRAG_RATE).quantize(Decimal("0.01"))

    return {
        "grundfreibetrag": grundfreibetrag,
        "investitions_gfb": investitions_gfb,
        "total": grundfreibetrag + investitions_gfb,
    }


def generate_e1a_form_data(
    db: Session,
    user: User,
    tax_year: int,
) -> Dict[str, Any]:
    """Generate E1a form data for sole proprietors.

    EA-Rechnung breakdown with official Kennzahlen.
    Thresholds loaded from DB TaxConfiguration for the given tax_year.
    """
    # Load year-specific config
    se_config = _load_self_employed_config(db, tax_year)

    pauschalierung_rate = Decimal(str(se_config.get("flat_rate_general", 0.12)))
    pauschalierung_reduced = Decimal(str(se_config.get("flat_rate_consulting", 0.06)))
    pauschalierung_max = Decimal(str(se_config.get("flat_rate_turnover_limit", 220000)))

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .order_by(Transaction.transaction_date)
        .all()
    )

    # Income
    business_income = _sum_income(transactions, [IncomeCategory.BUSINESS, IncomeCategory.SELF_EMPLOYMENT])

    # Expenses by EA-Rechnung category
    material = _sum_expense(transactions, [ExpenseCategory.GROCERIES])
    personnel = Decimal("0")  # Einzelunternehmer typically no employees; placeholder
    afa = _sum_expense(transactions, [ExpenseCategory.DEPRECIATION, ExpenseCategory.EQUIPMENT])
    rent = _sum_expense(transactions, [ExpenseCategory.RENT, ExpenseCategory.HOME_OFFICE])
    travel = _sum_expense(transactions, [ExpenseCategory.TRAVEL, ExpenseCategory.COMMUTING, ExpenseCategory.VEHICLE])
    telecom = _sum_expense(transactions, [ExpenseCategory.TELECOM])
    marketing = _sum_expense(transactions, [ExpenseCategory.MARKETING])
    insurance = _sum_expense(transactions, [ExpenseCategory.INSURANCE])
    professional = _sum_expense(transactions, [ExpenseCategory.PROFESSIONAL_SERVICES])
    bank_fees = _sum_expense(transactions, [ExpenseCategory.BANK_FEES])
    interest = _sum_expense(transactions, [ExpenseCategory.LOAN_INTEREST])
    svs = _sum_expense(transactions, [ExpenseCategory.SVS_CONTRIBUTIONS])
    utilities = _sum_expense(transactions, [ExpenseCategory.UTILITIES, ExpenseCategory.PROPERTY_TAX])
    maintenance = _sum_expense(transactions, [ExpenseCategory.MAINTENANCE])
    other = _sum_expense(transactions, [ExpenseCategory.OTHER])

    total_expenses = (
        material + personnel + afa + rent + travel + telecom + marketing
        + insurance + professional + bank_fees + interest + svs + utilities
        + maintenance + other
    )

    profit = business_income - total_expenses

    # Gewinnfreibetrag (year-specific)
    gfb = _calculate_gewinnfreibetrag(profit, se_config)

    # Basispauschalierung option (year-specific rates)
    pauschalierung_eligible = business_income <= pauschalierung_max
    pauschalierung_std = (business_income * pauschalierung_rate).quantize(Decimal("0.01"))
    pauschalierung_svc = (business_income * pauschalierung_reduced).quantize(Decimal("0.01"))

    # Taxable profit after GFB
    taxable_profit = max(profit - gfb["total"], Decimal("0"))

    # Format label with year-specific rates
    pct_label = f"{float(pauschalierung_rate)*100:.0f}%"
    pct_svc_label = f"{float(pauschalierung_reduced)*100:.0f}%"
    max_label = f"{float(pauschalierung_max):,.0f}"

    fields = [
        # ═══ Einnahmen ═══
        {
            "kz": "9040",
            "label_de": "Betriebseinnahmen (Umsatzerloese)",
            "label_en": "Business revenue",
            "label_zh": "经营收入",
            "value": float(business_income),
            "section": "einnahmen",
            "editable": True,
        },
        # ═══ Ausgaben (EA-Rechnung) ═══
        {
            "kz": "9050",
            "label_de": "Waren-/Materialeinsatz",
            "label_en": "Cost of goods / materials",
            "label_zh": "材料成本/进货",
            "value": float(material),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9060",
            "label_de": "Personalaufwand",
            "label_en": "Personnel costs",
            "label_zh": "人员成本",
            "value": float(personnel),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9070",
            "label_de": "Abschreibungen (AfA)",
            "label_en": "Depreciation (AfA)",
            "label_zh": "折旧 (AfA)",
            "value": float(afa),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9080",
            "label_de": "Miet- und Pachtaufwand",
            "label_en": "Rent expenses",
            "label_zh": "租金支出",
            "value": float(rent),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9081",
            "label_de": "Reise- und Fahrtkosten",
            "label_en": "Travel and vehicle expenses",
            "label_zh": "差旅及车辆费用",
            "value": float(travel),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9082",
            "label_de": "Nachrichtenaufwand (Telefon, Internet)",
            "label_en": "Telecommunications",
            "label_zh": "通讯费用",
            "value": float(telecom),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9083",
            "label_de": "Werbeaufwand",
            "label_en": "Marketing expenses",
            "label_zh": "广告费用",
            "value": float(marketing),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9084",
            "label_de": "Versicherungsaufwand",
            "label_en": "Insurance expenses",
            "label_zh": "保险费用",
            "value": float(insurance),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9085",
            "label_de": "Rechts- und Beratungskosten",
            "label_en": "Legal and consulting fees",
            "label_zh": "法律及咨询费用",
            "value": float(professional),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9086",
            "label_de": "SVS-Beitraege",
            "label_en": "SVS contributions",
            "label_zh": "SVS社保缴费",
            "value": float(svs),
            "section": "ausgaben",
            "editable": True,
            "note_de": "Pflichtbeitraege zur Sozialversicherung der Selbstaendigen",
        },
        {
            "kz": "9087",
            "label_de": "Zinsen und Bankspesen",
            "label_en": "Interest and bank fees",
            "label_zh": "利息及银行费用",
            "value": float(interest + bank_fees),
            "section": "ausgaben",
            "editable": True,
        },
        {
            "kz": "9090",
            "label_de": "Sonstige Betriebsausgaben",
            "label_en": "Other operating expenses",
            "label_zh": "其他经营费用",
            "value": float(utilities + maintenance + other),
            "section": "ausgaben",
            "editable": True,
        },
        # ═══ Ergebnis ═══
        {
            "kz": "9100",
            "label_de": "Gewinn / Verlust (Betriebsergebnis)",
            "label_en": "Profit / loss (operating result)",
            "label_zh": "经营利润/亏损",
            "value": float(profit),
            "section": "ergebnis",
            "editable": False,
        },
        # ═══ Gewinnfreibetrag (§10 EStG) ═══
        {
            "kz": "9221",
            "label_de": "Grundfreibetrag (15% bis EUR 33.000)",
            "label_en": "Basic profit exemption (15% up to EUR 33,000)",
            "label_zh": "基本利润免税额（15%，上限33,000欧元）",
            "value": float(gfb["grundfreibetrag"]),
            "section": "gewinnfreibetrag",
            "editable": True,
            "note_de": "Steht jedem Steuerpflichtigen automatisch zu (§10 Abs.1 Z1 EStG)",
        },
        {
            "kz": "9227",
            "label_de": "Investitionsbedingter Gewinnfreibetrag (13%)",
            "label_en": "Investment-based profit exemption (13%)",
            "label_zh": "投资性利润免税额（13%）",
            "value": float(gfb["investitions_gfb"]),
            "section": "gewinnfreibetrag",
            "editable": True,
            "note_de": "Erfordert Nachweis begeunstigter Investitionen (§10 Abs.1 Z2-4 EStG)",
        },
        # ═══ Basispauschalierung ═══
        {
            "kz": "9150",
            "label_de": f"Basispauschalierung ({pct_label} / {pct_svc_label})",
            "label_en": f"Flat-rate expense deduction ({pct_label} / {pct_svc_label})",
            "label_zh": f"基础固定费率（{pct_label}/{pct_svc_label}）",
            "value": float(pauschalierung_std),
            "section": "pauschalierung",
            "editable": True,
            "note_de": (
                f"Alternative zur Einzelaufzeichnung: {pct_label} der Einnahmen "
                f"({pct_svc_label} fuer Dienstleistungsbetriebe). Max. EUR {max_label} Umsatz."
            ),
        },
    ]

    return {
        "form_type": "E1a",
        "form_name_de": "Beilage zur Einkommensteuererklaerung — Einzelunternehmen",
        "form_name_en": "Supplement to Income Tax Return — Sole Proprietorship",
        "form_name_zh": "所得税申报附表 — 个体经营者",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "tax_number": user.tax_number or "",
        "generated_at": date.today().isoformat(),
        "fields": fields,
        "summary": {
            "business_income": float(business_income),
            "total_expenses": float(total_expenses),
            "profit": float(profit),
            "grundfreibetrag": float(gfb["grundfreibetrag"]),
            "investitions_gfb": float(gfb["investitions_gfb"]),
            "total_gewinnfreibetrag": float(gfb["total"]),
            "taxable_profit": float(taxable_profit),
            "pauschalierung_eligible": pauschalierung_eligible,
            "pauschalierung_general_pct": float(pauschalierung_std),
            "pauschalierung_consulting_pct": float(pauschalierung_svc),
        },
        "disclaimer_de": (
            "Diese Daten dienen als Ausfuellhilfe fuer die Beilage E1a. "
            "Die Wahl zwischen tatsaechlichen Ausgaben und Pauschalierung "
            "ist bindend fuer das Steuerjahr. Keine Steuerberatung."
        ),
        "disclaimer_en": (
            "This data is a filling aid for the E1a supplement. "
            "The choice between actual expenses and flat-rate deduction "
            "is binding for the tax year. Not tax advice."
        ),
    }
