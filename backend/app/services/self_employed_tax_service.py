"""
Self-employed tax features for Austrian individual taxpayers.

Implements:
1. Gewinnfreibetrag (§10 EStG) - Profit tax-free allowance
   - Grundfreibetrag: 15% of profit up to €33,000 (max €4,950), no investment needed
   - Investitionsbedingter Freibetrag: 13%/7%/4.5% of profit above €33,000,
     requires qualifying fixed asset or securities investment
2. Basispauschalierung - Flat-rate expense deduction
   - Turnover up to €320,000: 13.5% of turnover as flat-rate expenses
   - Certain professions (Kaufmännische/technische Beratung): 6%
   - Cannot be combined with actual expense tracking in the same year
3. Kleinunternehmerregelung helpers
   - VAT exemption status determination
   - Quarterly USt-Voranmeldung obligation check

References:
- WKO: https://www.wko.at/en/tax-free-allowance
- BMF FinanzOnline E1a form fields 9221, 9227, 9229
- §10 EStG (Gewinnfreibetrag)
- §17 EStG (Basispauschalierung)
"""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class ExpenseMethod(str, Enum):
    """How the self-employed person tracks expenses."""
    ACTUAL = "actual"                  # Einnahmen-Ausgaben-Rechnung (actual receipts)
    FLAT_RATE = "flat_rate"            # Basispauschalierung (13.5% / 6%)
    SMALL_BUSINESS = "small_business"  # Kleinunternehmer-Pauschalierung (new since 2020)


class ProfessionType(str, Enum):
    """Profession category for flat-rate expense percentage."""
    GENERAL = "general"          # 13.5% flat rate
    CONSULTING = "consulting"    # 6% (kaufmännische/technische Beratung, Schriftsteller, etc.)


# ---------------------------------------------------------------------------
# Gewinnfreibetrag (§10 EStG) — Profit Tax-Free Allowance
# ---------------------------------------------------------------------------

# Default thresholds and rates (valid from 2024 assessment onward)
GRUNDFREIBETRAG_PROFIT_LIMIT = Decimal("33000.00")
GRUNDFREIBETRAG_RATE = Decimal("0.15")  # 15%
GRUNDFREIBETRAG_MAX = Decimal("4950.00")  # 15% × 33,000

# Investment-based tiers (§10 Abs 1 Z 2 EStG)
# Profit above €33,000 is split into tiers with decreasing rates.
INVESTMENT_TIERS: List[tuple[Decimal, Decimal, Decimal]] = [
    # (tier_width, rate, cumulative_start)
    (Decimal("175000.00"), Decimal("0.13"), GRUNDFREIBETRAG_PROFIT_LIMIT),
    (Decimal("175000.00"), Decimal("0.07"), GRUNDFREIBETRAG_PROFIT_LIMIT + Decimal("175000.00")),
    (Decimal("230000.00"), Decimal("0.045"), GRUNDFREIBETRAG_PROFIT_LIMIT + Decimal("350000.00")),
]
# Above €580,000 profit → no further investment-based allowance
INVESTMENT_FREIBETRAG_CAP = Decimal("580000.00")
MAX_TOTAL_FREIBETRAG = Decimal("46400.00")  # max per taxpayer per year


@dataclass
class SelfEmployedConfig:
    """Year-specific configuration for self-employed tax calculations.

    All values have 2026 defaults for backward compatibility.
    """
    grundfreibetrag_profit_limit: Decimal = Decimal("33000.00")
    grundfreibetrag_rate: Decimal = Decimal("0.15")
    grundfreibetrag_max: Decimal = Decimal("4950.00")
    investment_tiers: List[tuple[Decimal, Decimal, Decimal]] = None  # type: ignore[assignment]
    max_total_freibetrag: Decimal = Decimal("46400.00")
    flat_rate_turnover_limit: Decimal = Decimal("320000.00")
    flat_rate_general: Decimal = Decimal("0.135")
    flat_rate_consulting: Decimal = Decimal("0.06")
    kleinunternehmer_threshold: Decimal = Decimal("55000.00")
    kleinunternehmer_tolerance: Decimal = Decimal("60500.00")
    ust_voranmeldung_monthly_threshold: Decimal = Decimal("100000.00")

    def __post_init__(self):
        if self.investment_tiers is None:
            limit = self.grundfreibetrag_profit_limit
            self.investment_tiers = [
                (Decimal("175000.00"), Decimal("0.13"), limit),
                (Decimal("175000.00"), Decimal("0.07"), limit + Decimal("175000.00")),
                (Decimal("230000.00"), Decimal("0.045"), limit + Decimal("350000.00")),
            ]

    @classmethod
    def from_deduction_config(cls, deduction_config: Optional[dict] = None) -> "SelfEmployedConfig":
        """Build from TaxConfiguration.deduction_config dict.

        Supports two config layouts:
        1. New layout with ``self_employed`` sub-dict (preferred).
        2. Legacy layout with top-level ``basic_exemption_rate`` /
           ``basic_exemption_max`` keys (used by older tests and configs).

        When no ``self_employed`` section exists, the legacy keys are used
        for Grundfreibetrag rate/max so that setting them to 0 correctly
        disables the exemption.
        """
        if not deduction_config:
            return cls()
        se = deduction_config.get("self_employed", {})

        # If there is no self_employed section, honour legacy top-level keys
        # for Grundfreibetrag so existing tests/configs keep working.
        if not se:
            legacy_rate = deduction_config.get("basic_exemption_rate")
            legacy_max = deduction_config.get("basic_exemption_max")
            grundfreibetrag_rate = (
                Decimal(str(legacy_rate)) if legacy_rate is not None
                else Decimal("0.15")
            )
            grundfreibetrag_max = (
                Decimal(str(legacy_max)) if legacy_max is not None
                else Decimal("4950.00")
            )
            return cls(
                grundfreibetrag_rate=grundfreibetrag_rate,
                grundfreibetrag_max=grundfreibetrag_max,
            )

        return cls(
            grundfreibetrag_profit_limit=Decimal(str(
                se.get("grundfreibetrag_profit_limit", "33000.00")
            )),
            grundfreibetrag_rate=Decimal(str(
                se.get("grundfreibetrag_rate", "0.15")
            )),
            grundfreibetrag_max=Decimal(str(
                se.get("grundfreibetrag_max", "4950.00")
            )),
            max_total_freibetrag=Decimal(str(
                se.get("max_total_freibetrag", "46400.00")
            )),
            flat_rate_turnover_limit=Decimal(str(
                se.get("flat_rate_turnover_limit", "320000.00")
            )),
            flat_rate_general=Decimal(str(
                se.get("flat_rate_general", "0.135")
            )),
            flat_rate_consulting=Decimal(str(
                se.get("flat_rate_consulting", "0.06")
            )),
            kleinunternehmer_threshold=Decimal(str(
                se.get("kleinunternehmer_threshold", "55000.00")
            )),
            kleinunternehmer_tolerance=Decimal(str(
                se.get("kleinunternehmer_tolerance", "60500.00")
            )),
            ust_voranmeldung_monthly_threshold=Decimal(str(
                se.get("ust_voranmeldung_monthly_threshold", "100000.00")
            )),
        )


@dataclass
class GewinnfreibetragResult:
    """Result of Gewinnfreibetrag calculation."""
    grundfreibetrag: Decimal = Decimal("0.00")
    investment_freibetrag: Decimal = Decimal("0.00")
    total_freibetrag: Decimal = Decimal("0.00")
    investment_required: Decimal = Decimal("0.00")  # how much must be invested
    investment_provided: Decimal = Decimal("0.00")   # how much was actually invested
    capped: bool = False
    details: str = ""


def calculate_gewinnfreibetrag(
    profit: Decimal,
    qualifying_investment: Decimal = Decimal("0.00"),
    config: Optional[SelfEmployedConfig] = None,
) -> GewinnfreibetragResult:
    """
    Calculate the Gewinnfreibetrag (§10 EStG).

    Args:
        profit: Annual business profit (Gewinn) before Freibetrag.
        qualifying_investment: Total acquisition cost of qualifying fixed assets
            or securities purchased in the same calendar year.
        config: Year-specific configuration. Uses defaults if None.

    Returns:
        GewinnfreibetragResult with breakdown.
    """
    if config is None:
        config = SelfEmployedConfig()

    if not isinstance(profit, Decimal):
        profit = Decimal(str(profit))
    if not isinstance(qualifying_investment, Decimal):
        qualifying_investment = Decimal(str(qualifying_investment))

    if profit <= Decimal("0"):
        return GewinnfreibetragResult(details="Kein Gewinn — kein Freibetrag.")

    # 1. Grundfreibetrag — automatic, no investment needed
    grundfreibetrag = min(
        profit * config.grundfreibetrag_rate,
        config.grundfreibetrag_max,
    ).quantize(Decimal("0.01"))

    # 2. Investment-based Freibetrag — only for profit above limit
    excess_profit = profit - config.grundfreibetrag_profit_limit
    if excess_profit <= Decimal("0"):
        return GewinnfreibetragResult(
            grundfreibetrag=grundfreibetrag,
            total_freibetrag=grundfreibetrag,
            details=(
                f"Grundfreibetrag: {float(config.grundfreibetrag_rate)*100:.0f}% von "
                f"€{profit:,.2f} = €{grundfreibetrag:,.2f}. "
                f"Kein investitionsbedingter Freibetrag "
                f"(Gewinn ≤ €{config.grundfreibetrag_profit_limit:,.0f})."
            ),
        )

    # Calculate maximum possible investment-based allowance per tier
    max_investment_freibetrag = Decimal("0.00")
    remaining = excess_profit

    for tier_width, rate, _ in config.investment_tiers:
        if remaining <= Decimal("0"):
            break
        taxable_in_tier = min(remaining, tier_width)
        max_investment_freibetrag += taxable_in_tier * rate
        remaining -= taxable_in_tier

    max_investment_freibetrag = max_investment_freibetrag.quantize(Decimal("0.01"))

    # Cap: investment-based allowance cannot exceed actual qualifying investment
    actual_investment_freibetrag = min(
        max_investment_freibetrag, qualifying_investment
    ).quantize(Decimal("0.01"))

    # Total cap per taxpayer per year
    total = grundfreibetrag + actual_investment_freibetrag
    capped = False
    if total > config.max_total_freibetrag:
        actual_investment_freibetrag = (config.max_total_freibetrag - grundfreibetrag).quantize(
            Decimal("0.01")
        )
        total = config.max_total_freibetrag
        capped = True

    return GewinnfreibetragResult(
        grundfreibetrag=grundfreibetrag,
        investment_freibetrag=actual_investment_freibetrag,
        total_freibetrag=total.quantize(Decimal("0.01")),
        investment_required=max_investment_freibetrag,
        investment_provided=qualifying_investment,
        capped=capped,
        details=(
            f"Grundfreibetrag: €{grundfreibetrag:,.2f}. "
            f"Investitionsbedingter Freibetrag: €{actual_investment_freibetrag:,.2f} "
            f"(max möglich: €{max_investment_freibetrag:,.2f}, "
            f"investiert: €{qualifying_investment:,.2f}). "
            f"Gesamt: €{total:,.2f}"
            + (" [gedeckelt]." if capped else ".")
        ),
    )


# ---------------------------------------------------------------------------
# Basispauschalierung (§17 EStG) — Flat-Rate Expense Deduction
# ---------------------------------------------------------------------------

# Thresholds and rates (valid from 2025 assessment onward, configurable per year)
FLAT_RATE_TURNOVER_LIMIT = Decimal("320000.00")  # max turnover to use flat-rate
FLAT_RATE_GENERAL = Decimal("0.135")              # 13.5% for most professions
FLAT_RATE_CONSULTING = Decimal("0.06")            # 6% for consulting/writing etc.

# Additional deductions allowed ON TOP of flat-rate:
# - SVS contributions (Sozialversicherung)
# - Grundfreibetrag (basic profit allowance)
# NOT allowed: investment-based Gewinnfreibetrag


@dataclass
class BasispauschalierungResult:
    """Result of flat-rate expense calculation."""
    eligible: bool = False
    flat_rate_expenses: Decimal = Decimal("0.00")
    flat_rate_pct: Decimal = Decimal("0.00")
    turnover: Decimal = Decimal("0.00")
    estimated_profit: Decimal = Decimal("0.00")
    grundfreibetrag: Decimal = Decimal("0.00")  # still applicable
    taxable_profit: Decimal = Decimal("0.00")
    reason: str = ""
    note: str = ""


def calculate_basispauschalierung(
    gross_turnover: Decimal,
    profession_type: ProfessionType = ProfessionType.GENERAL,
    svs_contributions: Decimal = Decimal("0.00"),
    additional_deductible: Decimal = Decimal("0.00"),
    config: Optional[SelfEmployedConfig] = None,
) -> BasispauschalierungResult:
    """
    Calculate profit using Basispauschalierung (flat-rate expenses).

    Under this method, the taxpayer deducts a fixed percentage of turnover
    as business expenses instead of tracking actual receipts.

    Args:
        gross_turnover: Annual gross turnover (Umsatz).
        profession_type: GENERAL (13.5%) or CONSULTING (6%).
        svs_contributions: Annual SVS contributions (deductible on top).
        additional_deductible: Other deductible items allowed on top
            (e.g. Reise- und Fahrtkosten for consulting professions).
        config: Year-specific configuration. Uses defaults if None.

    Returns:
        BasispauschalierungResult with profit and tax-relevant figures.
    """
    if config is None:
        config = SelfEmployedConfig()

    if not isinstance(gross_turnover, Decimal):
        gross_turnover = Decimal(str(gross_turnover))
    if not isinstance(svs_contributions, Decimal):
        svs_contributions = Decimal(str(svs_contributions))

    # Eligibility check
    if gross_turnover > config.flat_rate_turnover_limit:
        return BasispauschalierungResult(
            eligible=False,
            turnover=gross_turnover,
            reason=(
                f"Umsatz €{gross_turnover:,.2f} übersteigt die Grenze "
                f"von €{config.flat_rate_turnover_limit:,.2f}."
            ),
        )

    # Determine rate
    if profession_type == ProfessionType.CONSULTING:
        rate = config.flat_rate_consulting
    else:
        rate = config.flat_rate_general

    flat_rate_expenses = (gross_turnover * rate).quantize(Decimal("0.01"))

    # Profit = turnover - flat-rate expenses - SVS - other deductible
    profit = gross_turnover - flat_rate_expenses - svs_contributions - additional_deductible
    profit = max(profit, Decimal("0.00"))

    # Grundfreibetrag is still applicable with Basispauschalierung
    # (but NOT the investment-based Freibetrag)
    grundfreibetrag = min(
        profit * config.grundfreibetrag_rate,
        config.grundfreibetrag_max,
    ).quantize(Decimal("0.01"))

    taxable_profit = max(profit - grundfreibetrag, Decimal("0.00"))

    note = (
        f"Bei Basispauschalierung ist nur der Grundfreibetrag "
        f"(max €{config.grundfreibetrag_max:,.0f}) "
        f"abziehbar, NICHT der investitionsbedingte Gewinnfreibetrag."
    )

    return BasispauschalierungResult(
        eligible=True,
        flat_rate_expenses=flat_rate_expenses,
        flat_rate_pct=rate,
        turnover=gross_turnover,
        estimated_profit=profit.quantize(Decimal("0.01")),
        grundfreibetrag=grundfreibetrag,
        taxable_profit=taxable_profit.quantize(Decimal("0.01")),
        reason=f"Pauschalierung mit {float(rate) * 100:.1f}% anwendbar.",
        note=note,
    )


# ---------------------------------------------------------------------------
# Kleinunternehmerregelung helpers
# ---------------------------------------------------------------------------

KLEINUNTERNEHMER_THRESHOLD = Decimal("55000.00")   # gross turnover
KLEINUNTERNEHMER_TOLERANCE = Decimal("60500.00")    # 10% overshoot, once in 5 years
UST_VORANMELDUNG_MONTHLY_THRESHOLD = Decimal("100000.00")  # monthly UVA if > €100k


@dataclass
class KleinunternehmerStatus:
    """VAT exemption status for small businesses."""
    exempt: bool = True
    turnover: Decimal = Decimal("0.00")
    threshold: Decimal = KLEINUNTERNEHMER_THRESHOLD
    tolerance_applies: bool = False
    ust_voranmeldung_required: bool = False
    ust_voranmeldung_frequency: str = ""  # "quarterly" or "monthly"
    voluntary_registration_recommended: bool = False
    reason: str = ""
    warnings: List[str] = field(default_factory=list)


def determine_kleinunternehmer_status(
    gross_turnover: Decimal,
    has_significant_input_vat: bool = False,
    previous_year_exceeded: bool = False,
    config: Optional[SelfEmployedConfig] = None,
) -> KleinunternehmerStatus:
    """
    Determine Kleinunternehmerregelung status and VAT obligations.

    Args:
        gross_turnover: Annual gross turnover.
        has_significant_input_vat: Whether the business has significant
            input VAT (Vorsteuer) that could be reclaimed if registered.
        previous_year_exceeded: Whether the previous year already exceeded
            the threshold (tolerance rule is one-time).
        config: Year-specific configuration. Uses defaults if None.

    Returns:
        KleinunternehmerStatus with exemption status and obligations.
    """
    if config is None:
        config = SelfEmployedConfig()

    if not isinstance(gross_turnover, Decimal):
        gross_turnover = Decimal(str(gross_turnover))

    threshold = config.kleinunternehmer_threshold
    tolerance = config.kleinunternehmer_tolerance
    monthly_uva_threshold = config.ust_voranmeldung_monthly_threshold
    warnings: List[str] = []

    # Under threshold → exempt
    if gross_turnover <= threshold:
        reason = (
            f"Umsatz €{gross_turnover:,.2f} ≤ €{threshold:,.2f}: "
            f"Kleinunternehmerregelung anwendbar, keine USt-Pflicht."
        )
        if has_significant_input_vat:
            warnings.append(
                "Sie haben hohe Vorsteuern. Eine freiwillige USt-Registrierung "
                "könnte vorteilhaft sein (Vorsteuerabzug). "
                "Bitte Steuerberater konsultieren."
            )
        return KleinunternehmerStatus(
            exempt=True,
            turnover=gross_turnover,
            threshold=threshold,
            reason=reason,
            voluntary_registration_recommended=has_significant_input_vat,
            warnings=warnings,
        )

    # Tolerance zone
    if gross_turnover <= tolerance and not previous_year_exceeded:
        warnings.append(
            "Umsatz liegt in der Toleranzzone. Die Befreiung gilt dieses Jahr noch, "
            "aber im nächsten Jahr besteht USt-Pflicht."
        )
        return KleinunternehmerStatus(
            exempt=True,
            turnover=gross_turnover,
            threshold=threshold,
            tolerance_applies=True,
            reason=(
                f"Toleranzregel: Umsatz €{gross_turnover:,.2f} ≤ €{tolerance:,.2f}. "
                f"Dieses Jahr noch befreit."
            ),
            warnings=warnings,
        )

    # Above threshold → VAT liable
    if gross_turnover > monthly_uva_threshold:
        frequency = "monthly"
    else:
        frequency = "quarterly"

    return KleinunternehmerStatus(
        exempt=False,
        turnover=gross_turnover,
        threshold=threshold,
        ust_voranmeldung_required=True,
        ust_voranmeldung_frequency=frequency,
        reason=(
            f"Umsatz €{gross_turnover:,.2f} > €{threshold:,.2f}: "
            f"USt-Pflicht. UVA {frequency} erforderlich."
        ),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Comparison helper: flat-rate vs actual expenses
# ---------------------------------------------------------------------------

@dataclass
class ExpenseMethodComparison:
    """Compare flat-rate vs actual expense tracking."""
    flat_rate_profit: Decimal = Decimal("0.00")
    actual_profit: Decimal = Decimal("0.00")
    difference: Decimal = Decimal("0.00")
    recommended_method: ExpenseMethod = ExpenseMethod.ACTUAL
    reason: str = ""


def compare_expense_methods(
    gross_turnover: Decimal,
    actual_expenses: Decimal,
    profession_type: ProfessionType = ProfessionType.GENERAL,
    svs_contributions: Decimal = Decimal("0.00"),
    qualifying_investment: Decimal = Decimal("0.00"),
    config: Optional[SelfEmployedConfig] = None,
) -> ExpenseMethodComparison:
    """
    Compare Basispauschalierung vs actual expense tracking to recommend
    the more tax-efficient method.

    Args:
        gross_turnover: Annual gross turnover.
        actual_expenses: Total actual business expenses (without SVS).
        profession_type: Profession category for flat-rate percentage.
        svs_contributions: Annual SVS contributions.
        qualifying_investment: Qualifying fixed asset investment for
            investment-based Gewinnfreibetrag (only with actual method).
        config: Year-specific configuration. Uses defaults if None.

    Returns:
        ExpenseMethodComparison with recommendation.
    """
    if config is None:
        config = SelfEmployedConfig()

    if not isinstance(gross_turnover, Decimal):
        gross_turnover = Decimal(str(gross_turnover))
    if not isinstance(actual_expenses, Decimal):
        actual_expenses = Decimal(str(actual_expenses))

    # Flat-rate method
    flat = calculate_basispauschalierung(
        gross_turnover=gross_turnover,
        profession_type=profession_type,
        svs_contributions=svs_contributions,
        config=config,
    )

    # Actual method: profit = turnover - actual expenses - SVS
    actual_profit = max(
        gross_turnover - actual_expenses - svs_contributions, Decimal("0.00")
    )

    # With actual method, full Gewinnfreibetrag (including investment-based) applies
    gfb = calculate_gewinnfreibetrag(actual_profit, qualifying_investment, config=config)
    actual_taxable = max(actual_profit - gfb.total_freibetrag, Decimal("0.00"))

    flat_taxable = flat.taxable_profit if flat.eligible else actual_taxable

    diff = flat_taxable - actual_taxable

    if not flat.eligible:
        return ExpenseMethodComparison(
            flat_rate_profit=Decimal("0.00"),
            actual_profit=actual_taxable.quantize(Decimal("0.01")),
            difference=Decimal("0.00"),
            recommended_method=ExpenseMethod.ACTUAL,
            reason="Basispauschalierung nicht anwendbar (Umsatz > €320.000).",
        )

    if flat_taxable < actual_taxable:
        recommended = ExpenseMethod.FLAT_RATE
        reason = (
            f"Pauschalierung ergibt €{diff.quantize(Decimal('0.01')):,.2f} weniger "
            f"steuerpflichtigen Gewinn."
        )
    elif flat_taxable > actual_taxable:
        recommended = ExpenseMethod.ACTUAL
        reason = (
            f"Tatsächliche Ausgaben ergeben €{(-diff).quantize(Decimal('0.01')):,.2f} weniger "
            f"steuerpflichtigen Gewinn."
        )
    else:
        recommended = ExpenseMethod.FLAT_RATE
        reason = "Beide Methoden ergeben denselben steuerpflichtigen Gewinn. Pauschalierung ist einfacher."

    return ExpenseMethodComparison(
        flat_rate_profit=flat_taxable.quantize(Decimal("0.01")),
        actual_profit=actual_taxable.quantize(Decimal("0.01")),
        difference=diff.quantize(Decimal("0.01")),
        recommended_method=recommended,
        reason=reason,
    )
