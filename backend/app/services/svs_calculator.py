"""
SVS (Social Insurance) calculator for Austrian self-employed persons.

Calculates GSVG and Neue Selbständige contributions for Steuerjahr 2025
(filed in 2026). All rates and thresholds are based on official sources.

Data sources:
- SVS (Sozialversicherungsanstalt der Selbständigen): https://www.svs.at/
- WKO (Wirtschaftskammer Österreich): https://www.wko.at/en/social-insurance-of-trade-professionals
- BMF Steuerbuch 2026: https://www.bmf.gv.at/services/publikationen/das-steuerbuch.html

Note: The percentage rates (pension, health, supplementary pension) are stable
and confirmed across multiple sources. The fixed amounts (accident insurance,
minimum/maximum contribution bases) are subject to annual adjustment via the
Aufwertungszahl. The values below reflect the best available data for the
2025 contribution year. If official SVS publications for 2025 differ, these
values should be updated accordingly.
"""
from decimal import Decimal
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum


class UserType(str, Enum):
    """User type for SVS calculation"""
    EMPLOYEE = "employee"
    GSVG = "gsvg"  # Gewerbliches Sozialversicherungsgesetz (commercial self-employed)
    NEUE_SELBSTAENDIGE = "neue_selbstaendige"  # New self-employed (freelancers)


@dataclass
class SVSResult:
    """Result of SVS contribution calculation"""
    monthly_total: Decimal
    annual_total: Decimal
    breakdown: Dict[str, Decimal]
    contribution_base: Decimal
    deductible: bool = True
    note: Optional[str] = None


class SVSCalculator:
    """
    Calculator for Austrian social insurance contributions (SVS).

    Supports:
    - GSVG (Gewerbliches Sozialversicherungsgesetz) for commercial self-employed
    - Neue Selbständige for freelancers and new self-employed

    Key features:
    - Dynamic rate calculation based on income
    - Minimum and maximum contribution bases
    - Automatic deductibility as Sonderausgaben

    All rates and thresholds are loaded from year-specific TaxConfiguration.
    Defaults match Steuerjahr 2025 (Veranlagung 2026) for backward compatibility.
    """

    # Default rates (2026 fallback — matches get_2026_tax_config() svs_rates)
    _DEFAULT_PENSION_RATE = Decimal('0.185')
    _DEFAULT_HEALTH_RATE = Decimal('0.068')
    _DEFAULT_SUPPLEMENTARY_PENSION_RATE = Decimal('0.0153')
    _DEFAULT_ACCIDENT_FIXED = Decimal('12.25')           # 2026: €12.25/month (BVAEB/SVS)
    _DEFAULT_GSVG_MIN_BASE_MONTHLY = Decimal('551.10')
    _DEFAULT_GSVG_MIN_INCOME_YEARLY = Decimal('6613.20')
    _DEFAULT_NEUE_MIN_MONTHLY = Decimal('160.81')
    _DEFAULT_MAX_BASE_MONTHLY = Decimal('7720.50')       # 2026: €7,720.50/month (BVAEB/SVS)

    def __init__(self, svs_config: Optional[Dict] = None):
        """
        Initialize SVS calculator with year-specific configuration.

        Args:
            svs_config: SVS configuration dict from TaxConfiguration.svs_rates.
                Expected keys: pension, health, supplementary_pension, accident_fixed,
                gsvg_min_base_monthly, gsvg_min_income_yearly, neue_min_monthly,
                max_base_monthly.
                If None, uses 2025/2026 defaults for backward compatibility.
        """
        if svs_config:
            self.PENSION_RATE = Decimal(str(svs_config.get('pension', self._DEFAULT_PENSION_RATE)))
            self.HEALTH_RATE = Decimal(str(svs_config.get('health', self._DEFAULT_HEALTH_RATE)))
            self.SUPPLEMENTARY_PENSION_RATE = Decimal(str(
                svs_config.get('supplementary_pension', self._DEFAULT_SUPPLEMENTARY_PENSION_RATE)
            ))
            self.ACCIDENT_FIXED = Decimal(str(
                svs_config.get('accident_fixed', self._DEFAULT_ACCIDENT_FIXED)
            ))
            self.GSVG_MIN_BASE_MONTHLY = Decimal(str(
                svs_config.get('gsvg_min_base_monthly', self._DEFAULT_GSVG_MIN_BASE_MONTHLY)
            ))
            self.GSVG_MIN_INCOME_YEARLY = Decimal(str(
                svs_config.get('gsvg_min_income_yearly', self._DEFAULT_GSVG_MIN_INCOME_YEARLY)
            ))
            self.NEUE_MIN_MONTHLY = Decimal(str(
                svs_config.get('neue_min_monthly', self._DEFAULT_NEUE_MIN_MONTHLY)
            ))
            self.MAX_BASE_MONTHLY = Decimal(str(
                svs_config.get('max_base_monthly', self._DEFAULT_MAX_BASE_MONTHLY)
            ))
        else:
            self.PENSION_RATE = self._DEFAULT_PENSION_RATE
            self.HEALTH_RATE = self._DEFAULT_HEALTH_RATE
            self.SUPPLEMENTARY_PENSION_RATE = self._DEFAULT_SUPPLEMENTARY_PENSION_RATE
            self.ACCIDENT_FIXED = self._DEFAULT_ACCIDENT_FIXED
            self.GSVG_MIN_BASE_MONTHLY = self._DEFAULT_GSVG_MIN_BASE_MONTHLY
            self.GSVG_MIN_INCOME_YEARLY = self._DEFAULT_GSVG_MIN_INCOME_YEARLY
            self.NEUE_MIN_MONTHLY = self._DEFAULT_NEUE_MIN_MONTHLY
            self.MAX_BASE_MONTHLY = self._DEFAULT_MAX_BASE_MONTHLY
    
    def calculate_contributions(
        self,
        annual_income: Decimal,
        user_type: UserType
    ) -> SVSResult:
        """
        Calculate social insurance contributions based on income and user type.
        
        Args:
            annual_income: Annual gross income
            user_type: Type of user (EMPLOYEE, GSVG, NEUE_SELBSTAENDIGE)
            
        Returns:
            SVSResult with monthly/annual totals and breakdown
        """
        # Ensure annual_income is Decimal
        if not isinstance(annual_income, Decimal):
            annual_income = Decimal(str(annual_income))
        
        # Employees have contributions deducted by employer
        if user_type == UserType.EMPLOYEE:
            return SVSResult(
                monthly_total=Decimal('0.00'),
                annual_total=Decimal('0.00'),
                breakdown={},
                contribution_base=Decimal('0.00'),
                deductible=False,
                note="Employee contributions are deducted by employer. "
                    "Reference rates: Pension 10.25%, Health 3.87%, Unemployment 3%. "
                    "Max contribution base: €6,060/month (2025)."
            )
        
        # Calculate monthly income
        monthly_income = annual_income / Decimal('12')
        
        # Route to appropriate calculation method
        if user_type == UserType.GSVG:
            return self._calculate_gsvg(monthly_income, annual_income)
        elif user_type == UserType.NEUE_SELBSTAENDIGE:
            return self._calculate_neue_selbstaendige(monthly_income, annual_income)
        
        raise ValueError(f"Unsupported user type: {user_type}")
    
    def _calculate_gsvg(
        self,
        monthly_income: Decimal,
        annual_income: Decimal
    ) -> SVSResult:
        """
        Calculate GSVG (commercial self-employed) contributions.
        
        GSVG applies to:
        - Business owners (Gewerbetreibende)
        - Commercial self-employed persons
        
        Rules:
        - Minimum annual income: €6,613.20
        - Minimum contribution base: €551.10/month
        - Maximum contribution base: €8,085/month
        - Dynamic rates based on contribution base
        
        Args:
            monthly_income: Monthly gross income
            annual_income: Annual gross income
            
        Returns:
            SVSResult with contribution details
        """
        # Check minimum income requirement
        if annual_income < self.GSVG_MIN_INCOME_YEARLY:
            return SVSResult(
                monthly_total=Decimal('0.00'),
                annual_total=Decimal('0.00'),
                breakdown={},
                contribution_base=Decimal('0.00'),
                deductible=False,
                note=f"Annual income below €{self.GSVG_MIN_INCOME_YEARLY:,.2f} - no GSVG contributions required"
            )
        
        # Apply minimum and maximum contribution base
        contribution_base = self._apply_contribution_base_limits(monthly_income)
        
        # Calculate individual contributions with dynamic rates
        pension = contribution_base * self.PENSION_RATE
        health = contribution_base * self.HEALTH_RATE
        accident = self.ACCIDENT_FIXED  # Fixed amount
        supplementary = contribution_base * self.SUPPLEMENTARY_PENSION_RATE
        
        # Calculate totals
        monthly_total = pension + health + accident + supplementary
        annual_total = monthly_total * Decimal('12')
        
        return SVSResult(
            monthly_total=monthly_total.quantize(Decimal('0.01')),
            annual_total=annual_total.quantize(Decimal('0.01')),
            breakdown={
                'pension': pension.quantize(Decimal('0.01')),
                'health': health.quantize(Decimal('0.01')),
                'accident': accident.quantize(Decimal('0.01')),
                'supplementary': supplementary.quantize(Decimal('0.01'))
            },
            contribution_base=contribution_base.quantize(Decimal('0.01')),
            deductible=True,
            note="GSVG contributions are deductible as Sonderausgaben"
        )
    
    def _calculate_neue_selbstaendige(
        self,
        monthly_income: Decimal,
        annual_income: Decimal
    ) -> SVSResult:
        """
        Calculate Neue Selbständige (new self-employed) contributions.
        
        Neue Selbständige applies to:
        - Freelancers (Freiberufler)
        - New self-employed without commercial license
        - Contract workers
        
        Rules:
        - Minimum contribution: €160.81/month
        - Maximum contribution base: €8,085/month
        - Dynamic rates based on contribution base
        
        Args:
            monthly_income: Monthly gross income
            annual_income: Annual gross income
            
        Returns:
            SVSResult with contribution details
        """
        # Apply maximum contribution base (no minimum income requirement for Neue Selbständige)
        contribution_base = min(monthly_income, self.MAX_BASE_MONTHLY)
        
        # Calculate individual contributions with dynamic rates
        pension = contribution_base * self.PENSION_RATE
        health = contribution_base * self.HEALTH_RATE
        accident = self.ACCIDENT_FIXED  # Fixed amount
        supplementary = contribution_base * self.SUPPLEMENTARY_PENSION_RATE
        
        # Calculate monthly total
        monthly_total = pension + health + accident + supplementary
        
        # Apply minimum contribution
        if monthly_total < self.NEUE_MIN_MONTHLY:
            monthly_total = self.NEUE_MIN_MONTHLY
            note = f"Minimum contribution of €{self.NEUE_MIN_MONTHLY:,.2f}/month applied"
        else:
            note = "Neue Selbständige contributions are deductible as Sonderausgaben"
        
        annual_total = monthly_total * Decimal('12')
        
        return SVSResult(
            monthly_total=monthly_total.quantize(Decimal('0.01')),
            annual_total=annual_total.quantize(Decimal('0.01')),
            breakdown={
                'pension': pension.quantize(Decimal('0.01')),
                'health': health.quantize(Decimal('0.01')),
                'accident': accident.quantize(Decimal('0.01')),
                'supplementary': supplementary.quantize(Decimal('0.01'))
            },
            contribution_base=contribution_base.quantize(Decimal('0.01')),
            deductible=True,
            note=note
        )
    
    def _apply_contribution_base_limits(
        self,
        monthly_income: Decimal
    ) -> Decimal:
        """
        Apply minimum and maximum contribution base limits.
        
        Args:
            monthly_income: Monthly gross income
            
        Returns:
            Contribution base after applying limits
        """
        # Apply minimum base
        contribution_base = max(monthly_income, self.GSVG_MIN_BASE_MONTHLY)
        
        # Apply maximum base
        contribution_base = min(contribution_base, self.MAX_BASE_MONTHLY)
        
        return contribution_base
    
    def get_dynamic_rate(
        self,
        income_base: Decimal,
        contribution_type: str
    ) -> Decimal:
        """
        Get the dynamic contribution rate for a given income base.
        
        Note: In the current implementation, rates are fixed percentages.
        This method is provided for future extensibility if rates become
        truly dynamic based on income brackets.
        
        Args:
            income_base: Monthly income base
            contribution_type: Type of contribution (pension, health, accident, supplementary)
            
        Returns:
            Contribution rate as a decimal
        """
        rate_map = {
            'pension': self.PENSION_RATE,
            'health': self.HEALTH_RATE,
            'accident': Decimal('0.00'),  # Fixed amount, not a rate
            'supplementary': self.SUPPLEMENTARY_PENSION_RATE
        }
        
        return rate_map.get(contribution_type, Decimal('0.00'))
    
    def calculate_quarterly_prepayment(
        self,
        annual_income: Decimal,
        user_type: UserType
    ) -> Decimal:
        """
        Calculate quarterly SVS prepayment amount.
        
        SVS contributions are typically paid quarterly in advance.
        
        Args:
            annual_income: Estimated annual income
            user_type: Type of user
            
        Returns:
            Quarterly prepayment amount
        """
        result = self.calculate_contributions(annual_income, user_type)
        
        # Quarterly payment is annual total divided by 4
        quarterly = result.annual_total / Decimal('4')
        
        return quarterly.quantize(Decimal('0.01'))
