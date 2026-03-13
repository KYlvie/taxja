"""
Körperschaftsteuer (KöSt) Calculator for Austrian GmbH

GmbH taxation differs fundamentally from Einzelunternehmen (ESt):
- KöSt: flat 23% on corporate profit (since 2024, previously 25%)
- KESt: 27.5% on dividend distributions to shareholders
- Mindestkörperschaftsteuer: €500/quarter (€2,000/year) regardless of profit
- No progressive tax brackets — flat rate only
- No Grundfreibetrag, no Pendlerpauschale, no Familienbonus at corporate level
  (these apply to the Geschäftsführer's personal ESt if applicable)

References:
- KStG §22 (Körperschaftsteuersatz)
- EStG §27a (KESt on dividends)
- KStG §24 (Mindestkörperschaftsteuer)
"""
from decimal import Decimal
from typing import Dict, Any, Optional
from dataclasses import dataclass


# KöSt rate: 23% since 2024 (was 25% until 2022, 24% in 2023)
KOEST_RATE = Decimal("0.23")

# KESt on dividends: 27.5%
KEST_RATE = Decimal("0.275")

# Mindestkörperschaftsteuer: €500/quarter = €2,000/year
# Applies from the 4th year after incorporation (first 4 years: reduced rates)
MINDEST_KOEST_ANNUAL = Decimal("2000.00")
MINDEST_KOEST_QUARTERLY = Decimal("500.00")

# Reduced Mindestkörperschaftsteuer for first years:
# Year 1-4 after incorporation: €500/year (was previously tiered)
MINDEST_KOEST_FIRST_YEARS = Decimal("500.00")


@dataclass
class KoEstResult:
    """Result of KöSt calculation"""
    corporate_profit: Decimal
    koest_amount: Decimal          # KöSt on profit
    koest_rate: Decimal            # 23%
    mindest_koest: Decimal         # Minimum KöSt (if applicable)
    effective_koest: Decimal       # max(koest_amount, mindest_koest)
    profit_after_koest: Decimal    # Available for distribution or retention
    # Dividend scenario
    dividend_amount: Decimal       # How much is distributed
    kest_on_dividend: Decimal      # 27.5% KESt on dividend
    net_dividend: Decimal          # What shareholder actually receives
    # Combined burden
    total_tax_burden: Decimal      # KöSt + KESt
    effective_total_rate: Decimal  # Combined effective rate on profit


class KoEstCalculator:
    """
    Calculator for Austrian Körperschaftsteuer (corporate income tax).

    Usage:
        calc = KoEstCalculator()
        result = calc.calculate(profit=Decimal("100000"))
        # result.effective_koest = €23,000
        # result.kest_on_dividend = €21,175 (if fully distributed)
        # result.total_tax_burden = €44,175
        # result.effective_total_rate ≈ 44.175%
    """

    def calculate(
        self,
        profit: Decimal,
        dividend_pct: Decimal = Decimal("1.0"),
        years_since_incorporation: int = 10,
    ) -> KoEstResult:
        """
        Calculate KöSt and optional KESt on dividends.

        Args:
            profit: Corporate profit (Gewinn) before KöSt
            dividend_pct: Fraction of after-tax profit distributed as dividend (0.0-1.0)
            years_since_incorporation: Years since GmbH was founded (affects Mindestkörperschaftsteuer)

        Returns:
            KoEstResult with full breakdown
        """
        if not isinstance(profit, Decimal):
            profit = Decimal(str(profit))
        if not isinstance(dividend_pct, Decimal):
            dividend_pct = Decimal(str(dividend_pct))

        # 1. KöSt on profit
        koest_amount = max(profit * KOEST_RATE, Decimal("0")).quantize(Decimal("0.01"))

        # 2. Mindestkörperschaftsteuer
        if years_since_incorporation <= 4:
            mindest_koest = MINDEST_KOEST_FIRST_YEARS
        else:
            mindest_koest = MINDEST_KOEST_ANNUAL

        # Effective KöSt = max(calculated, minimum)
        effective_koest = max(koest_amount, mindest_koest) if profit >= 0 else mindest_koest

        # 3. Profit after KöSt
        profit_after_koest = max(profit - effective_koest, Decimal("0"))

        # 4. Dividend distribution
        dividend_amount = (profit_after_koest * dividend_pct).quantize(Decimal("0.01"))
        kest_on_dividend = (dividend_amount * KEST_RATE).quantize(Decimal("0.01"))
        net_dividend = dividend_amount - kest_on_dividend

        # 5. Total tax burden
        total_tax_burden = effective_koest + kest_on_dividend

        # 6. Effective total rate
        if profit > 0:
            effective_total_rate = (total_tax_burden / profit).quantize(Decimal("0.0001"))
        else:
            effective_total_rate = Decimal("0")

        return KoEstResult(
            corporate_profit=profit,
            koest_amount=koest_amount,
            koest_rate=KOEST_RATE,
            mindest_koest=mindest_koest,
            effective_koest=effective_koest,
            profit_after_koest=profit_after_koest,
            dividend_amount=dividend_amount,
            kest_on_dividend=kest_on_dividend,
            net_dividend=net_dividend,
            total_tax_burden=total_tax_burden,
            effective_total_rate=effective_total_rate,
        )

    def compare_with_est(
        self,
        profit: Decimal,
        est_tax: Decimal,
    ) -> Dict[str, Any]:
        """
        Compare GmbH (KöSt+KESt) vs Einzelunternehmen (ESt) tax burden.

        Args:
            profit: Same profit amount for comparison
            est_tax: Pre-calculated ESt amount for the same profit

        Returns:
            Comparison dict
        """
        gmbh = self.calculate(profit, dividend_pct=Decimal("1.0"))

        savings = est_tax - gmbh.total_tax_burden
        recommendation = "gmbh" if savings > 0 else "einzelunternehmen"

        return {
            "profit": float(profit),
            "gmbh": {
                "koest": float(gmbh.effective_koest),
                "kest_dividend": float(gmbh.kest_on_dividend),
                "total_tax": float(gmbh.total_tax_burden),
                "net_after_tax": float(profit - gmbh.total_tax_burden),
                "effective_rate": float(gmbh.effective_total_rate),
            },
            "einzelunternehmen": {
                "est": float(est_tax),
                "total_tax": float(est_tax),
                "net_after_tax": float(profit - est_tax),
                "effective_rate": float(est_tax / profit) if profit > 0 else 0.0,
            },
            "savings": float(savings),
            "recommendation": recommendation,
            "note": (
                "GmbH becomes advantageous at higher profits (~€80k+) due to flat 23% KöSt. "
                "However, dividend distribution adds 27.5% KESt. "
                "Retaining profits in the GmbH is tax-efficient."
            ),
        }
