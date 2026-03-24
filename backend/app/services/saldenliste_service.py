"""
Saldenliste Service
Generates Saldenliste mit Vorjahresvergleich and Periodensaldenliste reports.
Supports both EA (personal) and GmbH account plans based on Austrian Kontenrahmen.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.transaction import IncomeCategory, ExpenseCategory, Transaction, TransactionType
from app.models.transaction_line_item import LineItemPostingType
from app.models.user import User, UserType
from app.services.posting_line_utils import iter_transaction_posting_records
from app.services.report_transaction_filters import (
    should_include_in_saldenliste,
)


@dataclass
class AccountDef:
    """Definition of a single account (Konto) in the chart of accounts."""

    konto: str
    kontenklasse: int
    label_de: str
    label_en: str
    label_zh: str
    income_categories: List[IncomeCategory] = field(default_factory=list)
    expense_categories: List[ExpenseCategory] = field(default_factory=list)


# ── EA users: Kontenklasse 4 (income) + 7 (expense) ─────────────────────
# Derived from ea_report_service.py INCOME_GROUPS / EXPENSE_GROUPS.
# EA users only use Kontenklasse 4 and 7 per design requirement.

KONTENPLAN_EA: List[AccountDef] = [
    # ── Kontenklasse 4 – Erträge (Income) ────────────────────────────────
    AccountDef(
        konto="4000",
        kontenklasse=4,
        label_de="Einkünfte aus Land- und Forstwirtschaft",
        label_en="Agriculture and Forestry Income",
        label_zh="农林业收入",
        income_categories=[IncomeCategory.AGRICULTURE],
    ),
    AccountDef(
        konto="4100",
        kontenklasse=4,
        label_de="Einkünfte aus selbständiger Arbeit",
        label_en="Self-Employment Income (Freelance)",
        label_zh="自由职业收入",
        income_categories=[IncomeCategory.SELF_EMPLOYMENT],
    ),
    AccountDef(
        konto="4200",
        kontenklasse=4,
        label_de="Einkünfte aus Gewerbebetrieb",
        label_en="Business Income",
        label_zh="工商营业收入",
        income_categories=[IncomeCategory.BUSINESS],
    ),
    AccountDef(
        konto="4400",
        kontenklasse=4,
        label_de="Einkünfte aus nichtselbständiger Arbeit",
        label_en="Employment Income",
        label_zh="工资收入",
        income_categories=[IncomeCategory.EMPLOYMENT],
    ),
    AccountDef(
        konto="4500",
        kontenklasse=4,
        label_de="Einkünfte aus Kapitalvermögen",
        label_en="Capital Gains",
        label_zh="资本收益",
        income_categories=[IncomeCategory.CAPITAL_GAINS],
    ),
    AccountDef(
        konto="4600",
        kontenklasse=4,
        label_de="Einkünfte aus Vermietung und Verpachtung",
        label_en="Rental Income",
        label_zh="租金收入",
        income_categories=[IncomeCategory.RENTAL],
    ),
    AccountDef(
        konto="4700",
        kontenklasse=4,
        label_de="Sonstige Einkünfte",
        label_en="Other Income",
        label_zh="其他收入",
        income_categories=[IncomeCategory.OTHER_INCOME],
    ),
    # ── Kontenklasse 7 – Aufwendungen (Expenses) ────────────────────────
    AccountDef(
        konto="7010",
        kontenklasse=7,
        label_de="Aufwendungen für Material und Waren",
        label_en="Materials / Cost of Goods",
        label_zh="材料及商品成本",
        expense_categories=[ExpenseCategory.GROCERIES],
    ),
    AccountDef(
        konto="7020",
        kontenklasse=7,
        label_de="Aufwand für Instandhaltung, Betriebskosten",
        label_en="Maintenance and Operating Costs",
        label_zh="维修及运营成本",
        expense_categories=[ExpenseCategory.MAINTENANCE],
    ),
    AccountDef(
        konto="7030",
        kontenklasse=7,
        label_de="Reise- und Fahrtaufwand",
        label_en="Travel Expenses",
        label_zh="差旅费用",
        expense_categories=[ExpenseCategory.TRAVEL],
    ),
    AccountDef(
        konto="7040",
        kontenklasse=7,
        label_de="KFZ-Aufwand",
        label_en="Vehicle Expenses",
        label_zh="车辆费用",
        expense_categories=[ExpenseCategory.VEHICLE, ExpenseCategory.COMMUTING],
    ),
    AccountDef(
        konto="7050",
        kontenklasse=7,
        label_de="Aufwand für Miete",
        label_en="Rent Expenses",
        label_zh="租金支出",
        expense_categories=[ExpenseCategory.RENT],
    ),
    AccountDef(
        konto="7060",
        kontenklasse=7,
        label_de="Aufwand für Büromaterial",
        label_en="Office Supplies",
        label_zh="办公用品",
        expense_categories=[ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.HOME_OFFICE],
    ),
    AccountDef(
        konto="7070",
        kontenklasse=7,
        label_de="Nachrichtenaufwand",
        label_en="Telecommunications",
        label_zh="通讯费用",
        expense_categories=[ExpenseCategory.TELECOM],
    ),
    AccountDef(
        konto="7080",
        kontenklasse=7,
        label_de="Aufwand für Werbung",
        label_en="Advertising and Marketing",
        label_zh="广告及营销",
        expense_categories=[ExpenseCategory.MARKETING],
    ),
    AccountDef(
        konto="7090",
        kontenklasse=7,
        label_de="Aufwand für Versicherungen",
        label_en="Insurance",
        label_zh="保险费用",
        expense_categories=[ExpenseCategory.INSURANCE],
    ),
    AccountDef(
        konto="7100",
        kontenklasse=7,
        label_de="Rechts- und Beratungsaufwand und Steuerberatung",
        label_en="Legal, Consulting and Tax Advisory",
        label_zh="法律及税务咨询",
        expense_categories=[ExpenseCategory.PROFESSIONAL_SERVICES],
    ),
    AccountDef(
        konto="7110",
        kontenklasse=7,
        label_de="Abschreibungen (AfA)",
        label_en="Depreciation",
        label_zh="折旧",
        expense_categories=[ExpenseCategory.DEPRECIATION],
    ),
    AccountDef(
        konto="7120",
        kontenklasse=7,
        label_de="Betriebsmittel und Ausstattung",
        label_en="Equipment and Supplies",
        label_zh="设备及用品",
        expense_categories=[ExpenseCategory.EQUIPMENT],
    ),
    AccountDef(
        konto="7130",
        kontenklasse=7,
        label_de="Betriebsnebenkosten",
        label_en="Utilities",
        label_zh="水电费",
        expense_categories=[ExpenseCategory.UTILITIES, ExpenseCategory.PROPERTY_TAX],
    ),
    AccountDef(
        konto="7140",
        kontenklasse=7,
        label_de="Gebühren und Beiträge (SVS)",
        label_en="Social Insurance Contributions (SVS)",
        label_zh="社会保险缴费 (SVS)",
        expense_categories=[ExpenseCategory.SVS_CONTRIBUTIONS],
    ),
    AccountDef(
        konto="7150",
        kontenklasse=7,
        label_de="Spesen des Geldverkehrs",
        label_en="Bank Fees",
        label_zh="银行手续费",
        expense_categories=[ExpenseCategory.BANK_FEES],
    ),
    AccountDef(
        konto="7160",
        kontenklasse=7,
        label_de="Zinsaufwand",
        label_en="Interest Expenses",
        label_zh="利息支出",
        expense_categories=[ExpenseCategory.LOAN_INTEREST],
    ),
    AccountDef(
        konto="7900",
        kontenklasse=7,
        label_de="Sonstige betriebliche Aufwendungen",
        label_en="Other Operating Expenses",
        label_zh="其他经营费用",
        expense_categories=[ExpenseCategory.OTHER],
    ),
]


# ── GmbH users: full Kontenklassen 0-9 ───────────────────────────────────
# Derived from bilanz_report_service.py GUV accounts + AKTIVA/PASSIVA structure.
# GmbH uses the complete Austrian Kontenrahmen.

KONTENPLAN_GMBH: List[AccountDef] = [
    # ── Kontenklasse 0 – Anlagevermögen (Non-Current Assets) ─────────────
    AccountDef(
        konto="0600",
        kontenklasse=0,
        label_de="Sachanlagen (Ausstattung, KFZ)",
        label_en="Tangible Assets (Equipment, Vehicles)",
        label_zh="有形资产（设备、车辆）",
    ),
    # ── Kontenklasse 1 – Umlaufvermögen / Forderungen (Current Assets) ──
    AccountDef(
        konto="1200",
        kontenklasse=1,
        label_de="Forderungen aus Lieferungen und Leistungen",
        label_en="Trade Receivables",
        label_zh="应收账款",
    ),
    AccountDef(
        konto="1400",
        kontenklasse=1,
        label_de="Kassenbestand und Bankguthaben",
        label_en="Cash and Bank Balances",
        label_zh="现金及银行存款",
    ),
    # ── Kontenklasse 2 – Eigenkapital / Verbindlichkeiten (Equity/Liabilities)
    AccountDef(
        konto="2000",
        kontenklasse=2,
        label_de="Stammkapital / Einlagen",
        label_en="Share Capital / Contributions",
        label_zh="注册资本 / 出资",
    ),
    AccountDef(
        konto="2300",
        kontenklasse=2,
        label_de="Jahresüberschuss / -fehlbetrag",
        label_en="Net Profit / Loss for the Year",
        label_zh="本年度净利润 / 亏损",
    ),
    AccountDef(
        konto="2700",
        kontenklasse=2,
        label_de="Verbindlichkeiten aus Lieferungen und Leistungen",
        label_en="Trade Payables",
        label_zh="应付账款",
    ),
    AccountDef(
        konto="2800",
        kontenklasse=2,
        label_de="Darlehen und Kredite",
        label_en="Loans and Borrowings",
        label_zh="贷款及借款",
    ),
    AccountDef(
        konto="2900",
        kontenklasse=2,
        label_de="Steuerrückstellungen",
        label_en="Tax Provisions",
        label_zh="税金准备",
    ),
    # ── Kontenklasse 3 – Vorräte (Inventory) ─────────────────────────────
    AccountDef(
        konto="3000",
        kontenklasse=3,
        label_de="Vorräte und Bestände",
        label_en="Inventory and Stock",
        label_zh="存货",
    ),
    # ── Kontenklasse 4 – Erträge (Income) ────────────────────────────────
    AccountDef(
        konto="4000",
        kontenklasse=4,
        label_de="Einkünfte aus Land- und Forstwirtschaft",
        label_en="Agriculture and Forestry Income",
        label_zh="农林业收入",
        income_categories=[IncomeCategory.AGRICULTURE],
    ),
    AccountDef(
        konto="4100",
        kontenklasse=4,
        label_de="Einkünfte aus selbständiger Arbeit",
        label_en="Self-Employment Income (Freelance)",
        label_zh="自由职业收入",
        income_categories=[IncomeCategory.SELF_EMPLOYMENT],
    ),
    AccountDef(
        konto="4200",
        kontenklasse=4,
        label_de="Einkünfte aus Gewerbebetrieb",
        label_en="Business Income",
        label_zh="工商营业收入",
        income_categories=[IncomeCategory.BUSINESS],
    ),
    AccountDef(
        konto="4400",
        kontenklasse=4,
        label_de="Einkünfte aus nichtselbständiger Arbeit",
        label_en="Employment Income",
        label_zh="工资收入",
        income_categories=[IncomeCategory.EMPLOYMENT],
    ),
    AccountDef(
        konto="4500",
        kontenklasse=4,
        label_de="Einkünfte aus Kapitalvermögen",
        label_en="Capital Gains",
        label_zh="资本收益",
        income_categories=[IncomeCategory.CAPITAL_GAINS],
    ),
    AccountDef(
        konto="4550",
        kontenklasse=4,
        label_de="Erträge aus Vermietung und Verpachtung",
        label_en="Rental Income",
        label_zh="租赁收入",
        income_categories=[IncomeCategory.RENTAL],
    ),
    AccountDef(
        konto="4600",
        kontenklasse=4,
        label_de="Sonstige Einkünfte",
        label_en="Other Income",
        label_zh="其他收入",
        income_categories=[IncomeCategory.OTHER_INCOME],
    ),
    # ── Kontenklasse 5 – Materialaufwand (Material Expenses) ─────────────
    AccountDef(
        konto="5000",
        kontenklasse=5,
        label_de="Materialaufwand und Aufwand für bezogene Leistungen",
        label_en="Materials and Purchased Services",
        label_zh="材料及外购服务费用",
        expense_categories=[ExpenseCategory.GROCERIES],
    ),
    # ── Kontenklasse 6 – Personalaufwand (Personnel Expenses) ────────────
    AccountDef(
        konto="6000",
        kontenklasse=6,
        label_de="Personalaufwand",
        label_en="Personnel Expenses",
        label_zh="人工费用",
    ),
    # ── Kontenklasse 7 – Sonstiger Aufwand (Other Operating Expenses) ────
    AccountDef(
        konto="7000",
        kontenklasse=7,
        label_de="Abschreibungen auf Sachanlagen und immaterielle Vermögensgegenstände",
        label_en="Depreciation of Tangible and Intangible Assets",
        label_zh="有形及无形资产折旧",
        expense_categories=[ExpenseCategory.DEPRECIATION],
    ),
    AccountDef(
        konto="7100",
        kontenklasse=7,
        label_de="Geringwertige Wirtschaftsgüter und Ausstattung",
        label_en="Low-Value Assets and Equipment",
        label_zh="低值资产及设备",
        expense_categories=[ExpenseCategory.EQUIPMENT],
    ),
    AccountDef(
        konto="7200",
        kontenklasse=7,
        label_de="Instandhaltung und Reparaturen",
        label_en="Maintenance and Repairs",
        label_zh="维修保养费用",
        expense_categories=[ExpenseCategory.MAINTENANCE],
    ),
    AccountDef(
        konto="7300",
        kontenklasse=7,
        label_de="Miet- und Pachtaufwand",
        label_en="Rent and Lease Expenses",
        label_zh="租赁费用",
        expense_categories=[ExpenseCategory.RENT],
    ),
    AccountDef(
        konto="7320",
        kontenklasse=7,
        label_de="KFZ-Aufwand",
        label_en="Vehicle Expenses",
        label_zh="车辆费用",
        expense_categories=[ExpenseCategory.VEHICLE, ExpenseCategory.COMMUTING],
    ),
    AccountDef(
        konto="7330",
        kontenklasse=7,
        label_de="Reise- und Fahrtaufwand",
        label_en="Travel Expenses",
        label_zh="差旅费用",
        expense_categories=[ExpenseCategory.TRAVEL],
    ),
    AccountDef(
        konto="7340",
        kontenklasse=7,
        label_de="Nachrichtenaufwand (Telefon, Internet, Porto)",
        label_en="Telecommunications (Phone, Internet, Postage)",
        label_zh="通讯费用（电话、网络、邮资）",
        expense_categories=[ExpenseCategory.TELECOM],
    ),
    AccountDef(
        konto="7350",
        kontenklasse=7,
        label_de="Büromaterial und Verwaltungsaufwand",
        label_en="Office Supplies and Administration",
        label_zh="办公及行政费用",
        expense_categories=[ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.HOME_OFFICE],
    ),
    AccountDef(
        konto="7400",
        kontenklasse=7,
        label_de="Versicherungsaufwand",
        label_en="Insurance Expenses",
        label_zh="保险费用",
        expense_categories=[ExpenseCategory.INSURANCE],
    ),
    AccountDef(
        konto="7600",
        kontenklasse=7,
        label_de="Werbeaufwand",
        label_en="Advertising Expenses",
        label_zh="广告费用",
        expense_categories=[ExpenseCategory.MARKETING],
    ),
    AccountDef(
        konto="7690",
        kontenklasse=7,
        label_de="Pflichtbeiträge SVS/SVA",
        label_en="Mandatory Social Insurance (SVS)",
        label_zh="社会保险缴费 (SVS)",
        expense_categories=[ExpenseCategory.SVS_CONTRIBUTIONS],
    ),
    AccountDef(
        konto="7700",
        kontenklasse=7,
        label_de="Rechts- und Beratungsaufwand",
        label_en="Legal and Consulting Expenses",
        label_zh="法律及咨询费用",
        expense_categories=[ExpenseCategory.PROFESSIONAL_SERVICES],
    ),
    AccountDef(
        konto="7790",
        kontenklasse=7,
        label_de="Spesen des Geldverkehrs",
        label_en="Bank Charges",
        label_zh="银行手续费",
        expense_categories=[ExpenseCategory.BANK_FEES],
    ),
    AccountDef(
        konto="7800",
        kontenklasse=7,
        label_de="Betriebsnebenkosten (Strom, Wasser, Gas)",
        label_en="Utilities (Electricity, Water, Gas)",
        label_zh="水电气费用",
        expense_categories=[ExpenseCategory.UTILITIES, ExpenseCategory.PROPERTY_TAX],
    ),
    AccountDef(
        konto="7890",
        kontenklasse=7,
        label_de="Sonstiger betrieblicher Aufwand",
        label_en="Other Operating Expenses",
        label_zh="其他经营费用",
        expense_categories=[ExpenseCategory.OTHER],
    ),
    # ── Kontenklasse 8 – Finanzerträge/-aufwendungen (Financial) ─────────
    AccountDef(
        konto="8200",
        kontenklasse=8,
        label_de="Zins- und Finanzierungsaufwand",
        label_en="Interest and Financing Expenses",
        label_zh="利息及融资费用",
        expense_categories=[ExpenseCategory.LOAN_INTEREST],
    ),
    # ── Kontenklasse 9 – Abschlusskonten (Closing Accounts) ─────────────
    AccountDef(
        konto="9000",
        kontenklasse=9,
        label_de="Abschlusskonten",
        label_en="Closing Accounts",
        label_zh="结转科目",
    ),
]


# ── Kontenklasse labels (for grouping headers) ──────────────────────────

KONTENKLASSE_LABELS = {
    0: {"de": "Anlagevermögen", "en": "Non-Current Assets", "zh": "非流动资产", "fr": "Immobilisations", "ru": "Внеоборотные активы", "hu": "Befektetett eszközök", "pl": "Aktywa trwałe", "tr": "Duran Varlıklar", "bs": "Dugotrajna imovina"},
    1: {"de": "Umlaufvermögen", "en": "Current Assets", "zh": "流动资产", "fr": "Actifs circulants", "ru": "Оборотные активы", "hu": "Forgóeszközök", "pl": "Aktywa obrotowe", "tr": "Dönen Varlıklar", "bs": "Kratkotrajna imovina"},
    2: {"de": "Eigenkapital und Verbindlichkeiten", "en": "Equity and Liabilities", "zh": "权益及负债", "fr": "Capitaux propres et dettes", "ru": "Собственный капитал и обязательства", "hu": "Saját tőke és kötelezettségek", "pl": "Kapitał własny i zobowiązania", "tr": "Özkaynak ve Yükümlülükler", "bs": "Kapital i obaveze"},
    3: {"de": "Vorräte", "en": "Inventory", "zh": "存货", "fr": "Stocks", "ru": "Запасы", "hu": "Készletek", "pl": "Zapasy", "tr": "Stoklar", "bs": "Zalihe"},
    4: {"de": "Erträge", "en": "Income", "zh": "收入", "fr": "Revenus", "ru": "Доходы", "hu": "Bevételek", "pl": "Przychody", "tr": "Gelirler", "bs": "Prihodi"},
    5: {"de": "Materialaufwand", "en": "Material Expenses", "zh": "材料费用", "fr": "Charges de matières", "ru": "Материальные затраты", "hu": "Anyagköltségek", "pl": "Koszty materiałowe", "tr": "Malzeme Giderleri", "bs": "Troškovi materijala"},
    6: {"de": "Personalaufwand", "en": "Personnel Expenses", "zh": "人工费用", "fr": "Charges de personnel", "ru": "Расходы на персонал", "hu": "Személyi jellegű ráfordítások", "pl": "Koszty osobowe", "tr": "Personel Giderleri", "bs": "Troškovi osoblja"},
    7: {"de": "Sonstiger betrieblicher Aufwand", "en": "Other Operating Expenses", "zh": "其他经营费用", "fr": "Autres charges d'exploitation", "ru": "Прочие операционные расходы", "hu": "Egyéb üzemi ráfordítások", "pl": "Pozostałe koszty operacyjne", "tr": "Diğer Faaliyet Giderleri", "bs": "Ostali poslovni rashodi"},
    8: {"de": "Finanzerträge und -aufwendungen", "en": "Financial Income and Expenses", "zh": "财务收支", "fr": "Produits et charges financiers", "ru": "Финансовые доходы и расходы", "hu": "Pénzügyi bevételek és ráfordítások", "pl": "Przychody i koszty finansowe", "tr": "Finansal Gelir ve Giderler", "bs": "Finansijski prihodi i rashodi"},
    9: {"de": "Abschlusskonten", "en": "Closing Accounts", "zh": "结转", "fr": "Comptes de clôture", "ru": "Заключительные счета", "hu": "Záró számlák", "pl": "Konta zamknięcia", "tr": "Kapanış Hesapları", "bs": "Zaključni računi"},
}

# EA user types that use the simplified EA account plan
_EA_USER_TYPES = {UserType.EMPLOYEE, UserType.SELF_EMPLOYED, UserType.LANDLORD, UserType.MIXED}


def _allowed_saldenliste_posting_types(user_type: UserType) -> set[LineItemPostingType]:
    if user_type in _EA_USER_TYPES:
        return {LineItemPostingType.INCOME, LineItemPostingType.EXPENSE}
    return {
        LineItemPostingType.INCOME,
        LineItemPostingType.EXPENSE,
        LineItemPostingType.ASSET_ACQUISITION,
        LineItemPostingType.LIABILITY_DRAWDOWN,
        LineItemPostingType.LIABILITY_REPAYMENT,
    }


def get_account_plan(user_type: UserType) -> List[AccountDef]:
    """Return the appropriate account plan based on user type.

    EA users (employee, self_employed, landlord, mixed) get Kontenklasse 4+7 only.
    GmbH users get the full Kontenklassen 0-9.
    """
    if user_type in _EA_USER_TYPES:
        return KONTENPLAN_EA
    return KONTENPLAN_GMBH


def _find_sonstige_account(account_plan: List[AccountDef]) -> Optional[AccountDef]:
    """Find the 'Sonstige' (other) fallback account in the plan."""
    for acct in account_plan:
        if ExpenseCategory.OTHER in acct.expense_categories:
            return acct
    return None


def _find_account_by_konto(account_plan: List[AccountDef], konto: str) -> Optional[AccountDef]:
    """Find an account definition by its konto number."""
    for acct in account_plan:
        if acct.konto == konto:
            return acct
    return None


def _map_transaction_to_konto(transaction, account_plan: List[AccountDef]) -> str:
    """Map a transaction to its konto number based on category.

    For income transactions, matches on income_category.
    For expense transactions, matches on expense_category.
    Transactions with no matching category fall back to the 'Sonstige' (other) account.

    Args:
        transaction: A Transaction object (or any object with .type,
                     .income_category, .expense_category attributes).
        account_plan: The list of AccountDef to search.

    Returns:
        The konto string of the matching account.
    """
    if transaction.type == TransactionType.INCOME and transaction.income_category is not None:
        for acct in account_plan:
            if transaction.income_category in acct.income_categories:
                return acct.konto

    if transaction.type == TransactionType.EXPENSE and transaction.expense_category is not None:
        for acct in account_plan:
            if transaction.expense_category in acct.expense_categories:
                return acct.konto

    if transaction.type == TransactionType.ASSET_ACQUISITION:
        asset_account = _find_account_by_konto(account_plan, "0600")
        if asset_account is not None:
            return asset_account.konto

    if transaction.type in {
        TransactionType.LIABILITY_DRAWDOWN,
        TransactionType.LIABILITY_REPAYMENT,
    }:
        loan_account = _find_account_by_konto(account_plan, "2800")
        if loan_account is not None:
            return loan_account.konto

    # Fallback: map to "Sonstige" (other) account
    fallback = _find_sonstige_account(account_plan)
    if fallback is not None:
        return fallback.konto

    # Last resort: return the last account in the plan
    return account_plan[-1].konto


def _saldenliste_entry_amount(entry) -> Decimal:
    """Return the signed posting amount for a transaction or posting record."""
    total_amount = getattr(entry, "total_amount", None)
    amount = total_amount if total_amount is not None else getattr(entry, "amount", Decimal("0"))
    amount = amount or Decimal("0")
    if getattr(entry, "type", None) == TransactionType.LIABILITY_REPAYMENT:
        return -amount
    return amount


def _compute_yearly_balances(
    transactions, account_plan: List[AccountDef], user_type: UserType
) -> Dict[str, Decimal]:
    """Compute yearly cumulative balance (Saldo) for each konto.

    Initialises every konto from *account_plan* to ``Decimal("0")``, then
    iterates over *transactions* and accumulates each transaction's amount
    into the konto returned by ``_map_transaction_to_konto``.

    Args:
        transactions: Iterable of transaction objects (must have ``.amount``
            and the attributes expected by ``_map_transaction_to_konto``).
        account_plan: The chart of accounts to use.

    Returns:
        Dict mapping konto string → total Decimal amount.
    """
    balances: Dict[str, Decimal] = {acct.konto: Decimal("0") for acct in account_plan}
    allowed_posting_types = _allowed_saldenliste_posting_types(user_type)
    for txn in transactions:
        for record in iter_transaction_posting_records(txn, include_private_use=False):
            if record.posting_type not in allowed_posting_types:
                continue
            konto = _map_transaction_to_konto(record, account_plan)
            amount = _saldenliste_entry_amount(record)
            balances[konto] = balances.get(konto, Decimal("0")) + amount
    return balances


def _compute_deviation(current: Decimal, prior: Decimal) -> dict:
    """Compute absolute and percentage deviation between current and prior values.

    Args:
        current: The current period value.
        prior: The prior period (Vorjahr) value.

    Returns:
        ``{"abs": <Decimal>, "pct": <Decimal|None>}``
        *pct* is ``None`` when *prior* is zero (division-by-zero protection).
    """
    abs_dev = current - prior
    if prior != Decimal("0"):
        pct_dev = abs_dev / prior * Decimal("100")
    else:
        pct_dev = None
    return {"abs": abs_dev, "pct": pct_dev}


def _group_by_kontenklasse(
    balances: Dict[str, Decimal],
    account_plan: List[AccountDef],
    language: str = "de",
) -> List[dict]:
    """Group account balances by Kontenklasse and compute subtotals.

    Only Kontenklassen that have at least one account in *account_plan* are
    included.  Groups are sorted by Kontenklasse number.

    Args:
        balances: Mapping of konto → Decimal balance.
        account_plan: The chart of accounts.
        language: Language code for labels (``"de"``, ``"en"``, or ``"zh"``).

    Returns:
        Sorted list of group dicts, each containing:
        - ``kontenklasse``: int
        - ``label``: str (localised Kontenklasse label)
        - ``accounts``: list of ``{"konto", "label", "saldo"}`` dicts
        - ``subtotal``: Decimal sum of all account saldos in the group
    """
    if language not in ("de", "en", "zh", "fr", "ru", "hu", "pl", "tr", "bs"):
        language = "de"

    # Collect accounts into groups keyed by kontenklasse
    groups_map: Dict[int, List[dict]] = {}
    for acct in account_plan:
        kk = acct.kontenklasse
        if kk not in groups_map:
            groups_map[kk] = []
        label = getattr(acct, f"label_{language}", acct.label_de)
        groups_map[kk].append(
            {
                "konto": acct.konto,
                "label": label,
                "saldo": balances.get(acct.konto, Decimal("0")),
            }
        )

    # Build sorted result list
    result: List[dict] = []
    for kk in sorted(groups_map.keys()):
        accounts = groups_map[kk]
        subtotal = sum((a["saldo"] for a in accounts), Decimal("0"))
        kk_labels = KONTENKLASSE_LABELS.get(kk, {})
        group_label = kk_labels.get(language, kk_labels.get("de", f"Kontenklasse {kk}"))
        result.append(
            {
                "kontenklasse": kk,
                "label": group_label,
                "accounts": accounts,
                "subtotal": subtotal,
            }
        )
    return result


def _build_summary_totals(groups: List[dict], user_type: UserType) -> dict:
    """Build the summary totals row from grouped balances.

    Computes:
    - **aktiva**: Kontenklasse 0 + 1 + 3 (assets)
    - **passiva**: Kontenklasse 2 (equity & liabilities)
    - **ertrag**: Kontenklasse 4 (income)
    - **aufwand**: Kontenklasse 5 + 6 + 7 + 8 (expenses)
    - **gewinn_verlust**: ertrag − aufwand

    For EA users, aktiva and passiva will be ``Decimal("0")`` because those
    Kontenklassen are not present in the EA account plan.

    Args:
        groups: Output of ``_group_by_kontenklasse``.
        user_type: The user's type (determines which Kontenklassen exist).

    Returns:
        Dict with keys ``aktiva``, ``passiva``, ``ertrag``, ``aufwand``,
        ``gewinn_verlust``, each a Decimal.
    """
    subtotals_by_kk: Dict[int, Decimal] = {}
    for g in groups:
        subtotals_by_kk[g["kontenklasse"]] = g["subtotal"]

    aktiva = sum(
        (subtotals_by_kk.get(kk, Decimal("0")) for kk in (0, 1, 3)), Decimal("0")
    )
    passiva = subtotals_by_kk.get(2, Decimal("0"))
    ertrag = subtotals_by_kk.get(4, Decimal("0"))
    aufwand = sum(
        (subtotals_by_kk.get(kk, Decimal("0")) for kk in (5, 6, 7, 8)), Decimal("0")
    )
    gewinn_verlust = ertrag - aufwand

    return {
        "aktiva": aktiva,
        "passiva": passiva,
        "ertrag": ertrag,
        "aufwand": aufwand,
        "gewinn_verlust": gewinn_verlust,
    }


def generate_saldenliste(
    db: Session,
    user: User,
    tax_year: int,
    language: str = "de",
) -> dict:
    """Generate a Saldenliste mit Vorjahresvergleich report.

    Queries transactions for the current *tax_year* and the prior year,
    computes per-account balances, deviations, groups them by Kontenklasse,
    and assembles the full report response structure.

    When no transactions exist for a given year the report still returns a
    complete structure with all amounts set to zero (requirement 4.5).

    Args:
        db: SQLAlchemy database session.
        user: The authenticated user requesting the report.
        tax_year: The fiscal year to report on.
        language: Language code (``"de"``, ``"en"``, or ``"zh"``).

    Returns:
        A dict matching the Saldenliste mit VJ response schema.
    """
    if language not in ("de", "en", "zh", "fr", "ru", "hu", "pl", "tr", "bs"):
        language = "de"

    account_plan = get_account_plan(user.user_type)

    # Query current-year and prior-year transactions
    current_txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .all()
    )
    current_txns = [
        txn for txn in current_txns
        if should_include_in_saldenliste(txn, user.user_type)
    ]
    prior_txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year - 1,
        )
        .all()
    )
    prior_txns = [
        txn for txn in prior_txns
        if should_include_in_saldenliste(txn, user.user_type)
    ]

    # Compute balances
    current_balances = _compute_yearly_balances(current_txns, account_plan, user.user_type)
    prior_balances = _compute_yearly_balances(prior_txns, account_plan, user.user_type)

    # Build groups with current + prior data and deviations
    current_groups = _group_by_kontenklasse(current_balances, account_plan, language)
    prior_groups = _group_by_kontenklasse(prior_balances, account_plan, language)

    # Index prior groups by kontenklasse for easy lookup
    prior_by_kk: Dict[int, dict] = {g["kontenklasse"]: g for g in prior_groups}

    groups: List[dict] = []
    for cg in current_groups:
        kk = cg["kontenklasse"]
        pg = prior_by_kk.get(kk)

        # Build per-account rows with deviations
        prior_acct_map: Dict[str, Decimal] = {}
        if pg:
            for pa in pg["accounts"]:
                prior_acct_map[pa["konto"]] = pa["saldo"]

        accounts: List[dict] = []
        for acct in cg["accounts"]:
            cur_saldo = acct["saldo"]
            pri_saldo = prior_acct_map.get(acct["konto"], Decimal("0"))
            dev = _compute_deviation(cur_saldo, pri_saldo)
            accounts.append(
                {
                    "konto": acct["konto"],
                    "label": acct["label"],
                    "current_saldo": float(cur_saldo),
                    "prior_saldo": float(pri_saldo),
                    "deviation_abs": float(dev["abs"]),
                    "deviation_pct": float(dev["pct"]) if dev["pct"] is not None else None,
                }
            )

        subtotal_current = cg["subtotal"]
        subtotal_prior = pg["subtotal"] if pg else Decimal("0")
        sub_dev = _compute_deviation(subtotal_current, subtotal_prior)

        groups.append(
            {
                "kontenklasse": kk,
                "label": cg["label"],
                "accounts": accounts,
                "subtotal_current": float(subtotal_current),
                "subtotal_prior": float(subtotal_prior),
                "subtotal_deviation_abs": float(sub_dev["abs"]),
                "subtotal_deviation_pct": (
                    float(sub_dev["pct"]) if sub_dev["pct"] is not None else None
                ),
            }
        )

    # Build summary for current and prior
    current_summary = _build_summary_totals(current_groups, user.user_type)
    prior_summary = _build_summary_totals(prior_groups, user.user_type)

    summary = {
        "aktiva_current": float(current_summary["aktiva"]),
        "aktiva_prior": float(prior_summary["aktiva"]),
        "passiva_current": float(current_summary["passiva"]),
        "passiva_prior": float(prior_summary["passiva"]),
        "ertrag_current": float(current_summary["ertrag"]),
        "ertrag_prior": float(prior_summary["ertrag"]),
        "aufwand_current": float(current_summary["aufwand"]),
        "aufwand_prior": float(prior_summary["aufwand"]),
        "gewinn_verlust_current": float(current_summary["gewinn_verlust"]),
        "gewinn_verlust_prior": float(prior_summary["gewinn_verlust"]),
    }

    return {
        "report_type": "saldenliste",
        "tax_year": tax_year,
        "comparison_year": tax_year - 1,
        "user_name": user.name,
        "user_type": user.user_type.value,
        "generated_at": str(date.today()),
        "groups": groups,
        "summary": summary,
    }


# ── Periodensaldenliste helpers ──────────────────────────────────────────


def _compute_monthly_balances(
    transactions, account_plan: List[AccountDef], user_type: UserType
) -> Dict[str, Dict[int, Decimal]]:
    """Compute monthly balances for each konto across months 1-12.

    Initialises every konto from *account_plan* with all 12 months set to
    ``Decimal("0")``, then accumulates each transaction's amount into the
    appropriate konto and month (derived from ``transaction.transaction_date.month``).

    Args:
        transactions: Iterable of transaction objects.
        account_plan: The chart of accounts to use.

    Returns:
        Dict mapping konto string → {1: Decimal, 2: Decimal, …, 12: Decimal}.
    """
    balances: Dict[str, Dict[int, Decimal]] = {
        acct.konto: {m: Decimal("0") for m in range(1, 13)} for acct in account_plan
    }
    allowed_posting_types = _allowed_saldenliste_posting_types(user_type)
    for txn in transactions:
        for record in iter_transaction_posting_records(txn, include_private_use=False):
            if record.posting_type not in allowed_posting_types:
                continue
            if not record.transaction_date:
                continue
            konto = _map_transaction_to_konto(record, account_plan)
            month = record.transaction_date.month
            amount = _saldenliste_entry_amount(record)
            if konto not in balances:
                balances[konto] = {m: Decimal("0") for m in range(1, 13)}
            balances[konto][month] += amount
    return balances


def _group_by_kontenklasse_monthly(
    monthly_balances: Dict[str, Dict[int, Decimal]],
    account_plan: List[AccountDef],
    language: str = "de",
) -> List[dict]:
    """Group monthly account balances by Kontenklasse with monthly subtotals.

    Similar to ``_group_by_kontenklasse`` but operates on monthly data.
    Each account carries a list of 12 monthly amounts plus a *gesamt* (total).
    Each group carries *subtotal_months* (12 monthly sums) and *subtotal_gesamt*.

    Args:
        monthly_balances: Mapping of konto → {month: Decimal}.
        account_plan: The chart of accounts.
        language: Language code for labels.

    Returns:
        Sorted list of group dicts with monthly data.
    """
    if language not in ("de", "en", "zh", "fr", "ru", "hu", "pl", "tr", "bs"):
        language = "de"

    groups_map: Dict[int, List[dict]] = {}
    for acct in account_plan:
        kk = acct.kontenklasse
        if kk not in groups_map:
            groups_map[kk] = []
        label = getattr(acct, f"label_{language}", acct.label_de)
        konto_months = monthly_balances.get(acct.konto, {m: Decimal("0") for m in range(1, 13)})
        months_list = [konto_months.get(m, Decimal("0")) for m in range(1, 13)]
        gesamt = sum(months_list, Decimal("0"))
        groups_map[kk].append(
            {
                "konto": acct.konto,
                "label": label,
                "months": months_list,
                "gesamt": gesamt,
            }
        )

    result: List[dict] = []
    for kk in sorted(groups_map.keys()):
        accounts = groups_map[kk]
        subtotal_months = [
            sum((a["months"][i] for a in accounts), Decimal("0")) for i in range(12)
        ]
        subtotal_gesamt = sum(subtotal_months, Decimal("0"))
        kk_labels = KONTENKLASSE_LABELS.get(kk, {})
        group_label = kk_labels.get(language, kk_labels.get("de", f"Kontenklasse {kk}"))
        result.append(
            {
                "kontenklasse": kk,
                "label": group_label,
                "accounts": accounts,
                "subtotal_months": subtotal_months,
                "subtotal_gesamt": subtotal_gesamt,
            }
        )
    return result


def _build_summary_totals_monthly(groups: List[dict], user_type: UserType) -> dict:
    """Build summary totals for the Periodensaldenliste from grouped monthly data.

    Computes monthly and yearly totals for:
    - **aktiva**: Kontenklasse 0 + 1 + 3
    - **passiva**: Kontenklasse 2
    - **ertrag**: Kontenklasse 4
    - **aufwand**: Kontenklasse 5 + 6 + 7 + 8
    - **gewinn_verlust**: ertrag − aufwand

    Args:
        groups: Output of ``_group_by_kontenklasse_monthly``.
        user_type: The user's type.

    Returns:
        Dict with ``*_months`` (list of 12 Decimals) and ``*_gesamt`` (Decimal)
        for each category.
    """
    zero_months = [Decimal("0")] * 12

    subtotals_by_kk: Dict[int, dict] = {}
    for g in groups:
        subtotals_by_kk[g["kontenklasse"]] = {
            "months": g["subtotal_months"],
            "gesamt": g["subtotal_gesamt"],
        }

    def _sum_kk_months(kk_list):
        result = list(zero_months)
        for kk in kk_list:
            kk_data = subtotals_by_kk.get(kk)
            if kk_data:
                for i in range(12):
                    result[i] += kk_data["months"][i]
        return result

    def _sum_kk_gesamt(kk_list):
        return sum(
            (subtotals_by_kk.get(kk, {"gesamt": Decimal("0")})["gesamt"] for kk in kk_list),
            Decimal("0"),
        )

    aktiva_months = _sum_kk_months([0, 1, 3])
    aktiva_gesamt = _sum_kk_gesamt([0, 1, 3])
    passiva_months = _sum_kk_months([2])
    passiva_gesamt = _sum_kk_gesamt([2])
    ertrag_months = _sum_kk_months([4])
    ertrag_gesamt = _sum_kk_gesamt([4])
    aufwand_months = _sum_kk_months([5, 6, 7, 8])
    aufwand_gesamt = _sum_kk_gesamt([5, 6, 7, 8])
    gewinn_verlust_months = [ertrag_months[i] - aufwand_months[i] for i in range(12)]
    gewinn_verlust_gesamt = ertrag_gesamt - aufwand_gesamt

    return {
        "aktiva_months": aktiva_months,
        "aktiva_gesamt": aktiva_gesamt,
        "passiva_months": passiva_months,
        "passiva_gesamt": passiva_gesamt,
        "ertrag_months": ertrag_months,
        "ertrag_gesamt": ertrag_gesamt,
        "aufwand_months": aufwand_months,
        "aufwand_gesamt": aufwand_gesamt,
        "gewinn_verlust_months": gewinn_verlust_months,
        "gewinn_verlust_gesamt": gewinn_verlust_gesamt,
    }


def generate_periodensaldenliste(
    db: Session,
    user: User,
    tax_year: int,
    language: str = "de",
) -> dict:
    """Generate a Periodensaldenliste (monthly balance list) report.

    Queries transactions for the given *tax_year*, computes per-account
    monthly balances, groups them by Kontenklasse, and assembles the full
    report response structure.

    When no transactions exist for the year the report returns a complete
    structure with all amounts set to zero (requirement 4.5).

    All Decimal values are converted to float for JSON serialisation.

    Args:
        db: SQLAlchemy database session.
        user: The authenticated user requesting the report.
        tax_year: The fiscal year to report on.
        language: Language code (``"de"``, ``"en"``, or ``"zh"``).

    Returns:
        A dict matching the Periodensaldenliste response schema.
    """
    if language not in ("de", "en", "zh", "fr", "ru", "hu", "pl", "tr", "bs"):
        language = "de"

    account_plan = get_account_plan(user.user_type)

    # Query transactions for the tax year
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .all()
    )
    transactions = [
        txn for txn in transactions
        if should_include_in_saldenliste(txn, user.user_type)
    ]

    # Compute monthly balances and build groups
    monthly_balances = _compute_monthly_balances(transactions, account_plan, user.user_type)
    groups = _group_by_kontenklasse_monthly(monthly_balances, account_plan, language)
    summary = _build_summary_totals_monthly(groups, user.user_type)

    # Convert Decimals to floats for JSON serialisation
    def _to_float_list(decimal_list):
        return [float(v) for v in decimal_list]

    serialised_groups = []
    for g in groups:
        serialised_accounts = []
        for acct in g["accounts"]:
            serialised_accounts.append(
                {
                    "konto": acct["konto"],
                    "label": acct["label"],
                    "months": _to_float_list(acct["months"]),
                    "gesamt": float(acct["gesamt"]),
                }
            )
        serialised_groups.append(
            {
                "kontenklasse": g["kontenklasse"],
                "label": g["label"],
                "accounts": serialised_accounts,
                "subtotal_months": _to_float_list(g["subtotal_months"]),
                "subtotal_gesamt": float(g["subtotal_gesamt"]),
            }
        )

    serialised_summary = {
        "aktiva_months": _to_float_list(summary["aktiva_months"]),
        "aktiva_gesamt": float(summary["aktiva_gesamt"]),
        "passiva_months": _to_float_list(summary["passiva_months"]),
        "passiva_gesamt": float(summary["passiva_gesamt"]),
        "ertrag_months": _to_float_list(summary["ertrag_months"]),
        "ertrag_gesamt": float(summary["ertrag_gesamt"]),
        "aufwand_months": _to_float_list(summary["aufwand_months"]),
        "aufwand_gesamt": float(summary["aufwand_gesamt"]),
        "gewinn_verlust_months": _to_float_list(summary["gewinn_verlust_months"]),
        "gewinn_verlust_gesamt": float(summary["gewinn_verlust_gesamt"]),
    }

    return {
        "report_type": "periodensaldenliste",
        "tax_year": tax_year,
        "user_name": user.name,
        "user_type": user.user_type.value,
        "generated_at": str(date.today()),
        "groups": serialised_groups,
        "summary": serialised_summary,
    }
