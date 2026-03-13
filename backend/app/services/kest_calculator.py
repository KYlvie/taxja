"""
KESt (Kapitalertragsteuer) calculator for Austrian capital gains tax.

Austrian capital income is subject to a flat special tax rate (Sondersteuersatz),
separate from the progressive income tax tariff:
- 25% on interest from bank deposits (savings accounts, giro accounts)
- 27.5% on all other capital income (dividends, securities gains, crypto, funds)

If a domestic custodian (e.g. bank) is involved, KESt is withheld at source.
Otherwise, the taxpayer must declare it in the tax return (E1kv).

Source: BMF — https://www.bmf.gv.at/en/topics/taxation/Income-Taxation-on-savings-and-investments/
"""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional


class CapitalIncomeType(str, Enum):
    """Type of capital income for KESt rate determination."""
    BANK_INTEREST = "bank_interest"          # 25% — Sparbuch, Girokonto
    DIVIDENDS = "dividends"                  # 27.5%
    SECURITIES_GAINS = "securities_gains"    # 27.5% — Aktien, Fonds, ETFs
    CRYPTO = "crypto"                        # 27.5% — since 01.03.2021
    BOND_INTEREST = "bond_interest"          # 27.5%
    FUND_DISTRIBUTIONS = "fund_distributions"  # 27.5%
    GMBH_SHARES = "gmbh_shares"             # 27.5% — sale of GmbH shares
    OTHER = "other"                          # 27.5% default


# Rates are stable and not subject to annual cold-progression adjustment
KEST_RATE_BANK = Decimal("0.25")     # 25%
KEST_RATE_OTHER = Decimal("0.275")   # 27.5%


@dataclass
class KEStLineItem:
    """Individual capital income item."""
    description: str
    income_type: CapitalIncomeType
    gross_amount: Decimal
    rate: Decimal
    tax_amount: Decimal
    withheld: bool = False  # True if already withheld by bank/broker


@dataclass
class KEStResult:
    """Result of KESt calculation."""
    total_gross: Decimal = Decimal("0.00")
    total_tax: Decimal = Decimal("0.00")
    total_already_withheld: Decimal = Decimal("0.00")
    remaining_tax_due: Decimal = Decimal("0.00")
    net_income: Decimal = Decimal("0.00")
    line_items: List[KEStLineItem] = field(default_factory=list)
    note: str = ""


def get_kest_rate(income_type: CapitalIncomeType) -> Decimal:
    """Return the applicable KESt rate for a given capital income type."""
    if income_type == CapitalIncomeType.BANK_INTEREST:
        return KEST_RATE_BANK
    return KEST_RATE_OTHER


def calculate_kest(
    items: List[Dict],
) -> KEStResult:
    """
    Calculate KESt for a list of capital income items.

    Args:
        items: List of dicts with keys:
            - description (str)
            - income_type (str or CapitalIncomeType)
            - gross_amount (Decimal or float)
            - withheld (bool, optional): whether KESt was already withheld

    Returns:
        KEStResult with totals and per-item breakdown.
    """
    line_items: List[KEStLineItem] = []
    total_gross = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_withheld = Decimal("0.00")

    for item in items:
        income_type = item.get("income_type", "other")
        if isinstance(income_type, str):
            income_type = CapitalIncomeType(income_type)

        gross = Decimal(str(item.get("gross_amount", 0)))
        withheld = bool(item.get("withheld", False))
        rate = get_kest_rate(income_type)
        tax = (gross * rate).quantize(Decimal("0.01"))

        line_items.append(KEStLineItem(
            description=item.get("description", ""),
            income_type=income_type,
            gross_amount=gross,
            rate=rate,
            tax_amount=tax,
            withheld=withheld,
        ))

        total_gross += gross
        total_tax += tax
        if withheld:
            total_withheld += tax

    remaining = (total_tax - total_withheld).quantize(Decimal("0.01"))
    net = (total_gross - total_tax).quantize(Decimal("0.01"))

    note = ""
    if total_withheld > Decimal("0"):
        note = (
            f"€{total_withheld:,.2f} bereits einbehalten (KESt-Abzug durch Bank/Broker). "
            f"Verbleibende Steuerschuld: €{remaining:,.2f}."
        )
    else:
        note = (
            f"Keine KESt einbehalten — gesamte Steuerschuld €{total_tax:,.2f} "
            f"muss in der Steuererklärung (E1kv) angegeben werden."
        )

    return KEStResult(
        total_gross=total_gross.quantize(Decimal("0.01")),
        total_tax=total_tax.quantize(Decimal("0.01")),
        total_already_withheld=total_withheld.quantize(Decimal("0.01")),
        remaining_tax_due=remaining,
        net_income=net,
        line_items=line_items,
        note=note,
    )
