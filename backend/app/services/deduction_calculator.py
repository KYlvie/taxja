"""Deduction calculator for Austrian tax deductions"""
from decimal import Decimal
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class FamilyInfo:
    """Family information for deduction calculation"""
    num_children: int
    is_single_parent: bool = False
    children_under_18: int = 0
    children_18_to_24: int = 0
    is_sole_earner: bool = False



@dataclass
class DeductionResult:
    """Result of a deduction calculation"""
    amount: Decimal
    breakdown: Dict
    note: Optional[str] = None


class DeductionCalculator:
    """
    Calculator for Austrian tax deductions including:
    - Commuting allowance (Pendlerpauschale)
    - Home office deduction
    - Family deductions (Kinderabsetzbetrag)
    - Single parent deduction

    All amounts are loaded from year-specific TaxConfiguration.
    Defaults match 2026 values for backward compatibility.
    """

    # Default values (2026 fallback)
    _DEFAULT_COMMUTE_BRACKETS_SMALL = {
        20: Decimal('58.00'),
        40: Decimal('113.00'),
        60: Decimal('168.00'),
    }
    _DEFAULT_COMMUTE_BRACKETS_LARGE = {
        2: Decimal('31.00'),
        20: Decimal('123.00'),
        40: Decimal('214.00'),
        60: Decimal('306.00'),
    }
    _DEFAULT_PENDLER_EURO_PER_KM = Decimal('6.00')
    _DEFAULT_HOME_OFFICE_DEDUCTION = Decimal('300.00')
    _DEFAULT_CHILD_DEDUCTION_MONTHLY = Decimal('67.80')  # 2025/2026/2027: €67.80 (frozen per BMF)
    _DEFAULT_SINGLE_PARENT_DEDUCTION = Decimal('612.00')  # 2026: €612 (same as Alleinerzieher)
    _DEFAULT_WERBUNGSKOSTENPAUSCHALE = Decimal('132.00')
    _DEFAULT_VERKEHRSABSETZBETRAG = Decimal('496.00')  # 2026: €496 (2025: €487)
    _DEFAULT_FAMILIENBONUS_UNDER_18 = Decimal('2000.16')  # since 2022
    _DEFAULT_FAMILIENBONUS_18_24 = Decimal('700.08')  # since 2024
    _DEFAULT_ALLEINVERDIENER_BASE = Decimal('612.00')  # 2026: 1-child total (BMF)
    _DEFAULT_ALLEINVERDIENER_2_CHILDREN = Decimal('828.00')  # 2026: 2-children total (BMF)
    _DEFAULT_ALLEINVERDIENER_PER_EXTRA_CHILD = Decimal('273.00')  # 2026: per child from 3rd (BMF)
    # Zuschlag zum Verkehrsabsetzbetrag for low-income earners (§33 Abs 5 EStG)
    # Full Zuschlag if income ≤ €16,832 (2026), phases out to €0 at €28,326 (2026)
    _DEFAULT_ZUSCHLAG_VERKEHRSABSETZBETRAG = Decimal('804.00')  # 2026: €804 (BMF)
    _DEFAULT_ZUSCHLAG_INCOME_LOWER = Decimal('19761.00')  # Full Zuschlag up to this income
    _DEFAULT_ZUSCHLAG_INCOME_UPPER = Decimal('30259.00')  # Zuschlag phases out above this
    _DEFAULT_ERHOEHTER_VERKEHRSABSETZBETRAG = Decimal('853.00')  # 2026: €853 (BMF)
    # Pensionistenabsetzbetrag (§33 Abs 6 EStG) — tax credit for pensioners
    _DEFAULT_PENSIONISTEN_ABSETZBETRAG = Decimal('1020.00')  # 2026: €1,020 (BMF)
    _DEFAULT_PENSIONISTEN_INCOME_LOWER = Decimal('21614.00')  # Full amount up to this
    _DEFAULT_PENSIONISTEN_INCOME_UPPER = Decimal('31494.00')  # Phases out above this
    # Erhöhter Pensionistenabsetzbetrag (for single pensioners)
    _DEFAULT_ERHOEHTER_PENSIONISTEN = Decimal('1502.00')  # 2026: €1,502 (BMF)
    _DEFAULT_ERHOEHTER_PENSIONISTEN_INCOME_LOWER = Decimal('24616.00')  # Full amount up to this income
    # Sonderausgabenpauschale (§18 Abs 2 EStG) — automatic special expenses flat-rate
    _DEFAULT_SONDERAUSGABENPAUSCHALE = Decimal('60.00')  # €60/year (unchanged for years)
    # Kirchenbeitrag (§18 Abs 1 Z 5 EStG) — church contributions deductible up to cap
    # Year-dependent: €400 for ≤2023, €600 for 2024+ (AbgÄG 2023, BGBl I Nr. 110/2023)
    _DEFAULT_KIRCHENBEITRAG_CAP = Decimal('600.00')  # €600/year (2024+)
    _KIRCHENBEITRAG_CAP_2023 = Decimal('400.00')  # €400/year (≤2023)
    # Spenden (§18 Abs 1 Z 7 EStG) — donations to qualifying orgs, capped at 10% of
    # Gesamtbetrag der Einkünfte from the previous year's tax return
    _DEFAULT_SPENDEN_INCOME_RATIO = Decimal('0.10')  # 10% of income

    def __init__(self, deduction_config: Optional[Dict] = None):
        """
        Initialize deduction calculator with year-specific configuration.

        Args:
            deduction_config: Deduction configuration dict from
                TaxConfiguration.deduction_config. If None, uses 2026 defaults.
        """
        if deduction_config:
            self.HOME_OFFICE_DEDUCTION = Decimal(str(
                deduction_config.get('home_office', self._DEFAULT_HOME_OFFICE_DEDUCTION)
            ))
            self.CHILD_DEDUCTION_MONTHLY = Decimal(str(
                deduction_config.get('child_deduction_monthly', self._DEFAULT_CHILD_DEDUCTION_MONTHLY)
            ))
            self.SINGLE_PARENT_DEDUCTION = Decimal(str(
                deduction_config.get('single_parent_deduction', self._DEFAULT_SINGLE_PARENT_DEDUCTION)
            ))
            self.PENDLER_EURO_PER_KM = Decimal(str(
                deduction_config.get('pendler_euro_per_km', self._DEFAULT_PENDLER_EURO_PER_KM)
            ))
            self.WERBUNGSKOSTENPAUSCHALE = Decimal(str(
                deduction_config.get('werbungskostenpauschale', self._DEFAULT_WERBUNGSKOSTENPAUSCHALE)
            ))
            self.VERKEHRSABSETZBETRAG = Decimal(str(
                deduction_config.get('verkehrsabsetzbetrag', self._DEFAULT_VERKEHRSABSETZBETRAG)
            ))
            self.FAMILIENBONUS_UNDER_18 = Decimal(str(
                deduction_config.get('familienbonus_under_18', self._DEFAULT_FAMILIENBONUS_UNDER_18)
            ))
            self.FAMILIENBONUS_18_24 = Decimal(str(
                deduction_config.get('familienbonus_18_24', self._DEFAULT_FAMILIENBONUS_18_24)
            ))
            self.ALLEINVERDIENER_BASE = Decimal(str(
                deduction_config.get('alleinverdiener_base', self._DEFAULT_ALLEINVERDIENER_BASE)
            ))
            self.ALLEINVERDIENER_2_CHILDREN = Decimal(str(
                deduction_config.get('alleinverdiener_2_children', self._DEFAULT_ALLEINVERDIENER_2_CHILDREN)
            ))
            self.ALLEINVERDIENER_PER_EXTRA_CHILD = Decimal(str(
                deduction_config.get('alleinverdiener_per_extra_child', self._DEFAULT_ALLEINVERDIENER_PER_EXTRA_CHILD)
            ))
            self.ZUSCHLAG_VERKEHRSABSETZBETRAG = Decimal(str(
                deduction_config.get('zuschlag_verkehrsabsetzbetrag', self._DEFAULT_ZUSCHLAG_VERKEHRSABSETZBETRAG)
            ))
            self.ZUSCHLAG_INCOME_LOWER = Decimal(str(
                deduction_config.get('zuschlag_income_lower', self._DEFAULT_ZUSCHLAG_INCOME_LOWER)
            ))
            self.ZUSCHLAG_INCOME_UPPER = Decimal(str(
                deduction_config.get('zuschlag_income_upper', self._DEFAULT_ZUSCHLAG_INCOME_UPPER)
            ))
            self.ERHOEHTER_VERKEHRSABSETZBETRAG = Decimal(str(
                deduction_config.get('erhoehter_verkehrsabsetzbetrag', self._DEFAULT_ERHOEHTER_VERKEHRSABSETZBETRAG)
            ))
            self.PENSIONISTEN_ABSETZBETRAG = Decimal(str(
                deduction_config.get('pensionisten_absetzbetrag', self._DEFAULT_PENSIONISTEN_ABSETZBETRAG)
            ))
            self.PENSIONISTEN_INCOME_LOWER = Decimal(str(
                deduction_config.get('pensionisten_income_lower', self._DEFAULT_PENSIONISTEN_INCOME_LOWER)
            ))
            self.PENSIONISTEN_INCOME_UPPER = Decimal(str(
                deduction_config.get('pensionisten_income_upper', self._DEFAULT_PENSIONISTEN_INCOME_UPPER)
            ))
            self.ERHOEHTER_PENSIONISTEN = Decimal(str(
                deduction_config.get('erhoehter_pensionisten', self._DEFAULT_ERHOEHTER_PENSIONISTEN)
            ))
            self.ERHOEHTER_PENSIONISTEN_INCOME_LOWER = Decimal(str(
                deduction_config.get('erhoehter_pensionisten_income_lower',
                    deduction_config.get('erhoehter_pensionisten_upper',  # backwards compat
                        self._DEFAULT_ERHOEHTER_PENSIONISTEN_INCOME_LOWER))
            ))
            # Erhöhter PAB phase-out upper; falls back to regular PAB upper if not set
            _epiu = deduction_config.get('erhoehter_pensionisten_income_upper')
            if _epiu is not None:
                self.ERHOEHTER_PENSIONISTEN_INCOME_UPPER = Decimal(str(_epiu))
            else:
                self.ERHOEHTER_PENSIONISTEN_INCOME_UPPER = Decimal(str(
                    deduction_config.get('pensionisten_income_upper', self._DEFAULT_PENSIONISTEN_INCOME_UPPER)
                ))
            self.SONDERAUSGABENPAUSCHALE = Decimal(str(
                deduction_config.get('sonderausgabenpauschale', self._DEFAULT_SONDERAUSGABENPAUSCHALE)
            ))
            self.KIRCHENBEITRAG_CAP = Decimal(str(
                deduction_config.get('kirchenbeitrag_cap', self._DEFAULT_KIRCHENBEITRAG_CAP)
            ))
            self.SPENDEN_INCOME_RATIO = Decimal(str(
                deduction_config.get('spenden_income_ratio', self._DEFAULT_SPENDEN_INCOME_RATIO)
            ))

            # Commuting brackets from config
            commuting = deduction_config.get('commuting_brackets', {})
            if commuting.get('small'):
                self.COMMUTE_BRACKETS_SMALL = {
                    int(k): Decimal(str(v)) for k, v in commuting['small'].items()
                }
            else:
                self.COMMUTE_BRACKETS_SMALL = dict(self._DEFAULT_COMMUTE_BRACKETS_SMALL)
            if commuting.get('large'):
                self.COMMUTE_BRACKETS_LARGE = {
                    int(k): Decimal(str(v)) for k, v in commuting['large'].items()
                }
            else:
                self.COMMUTE_BRACKETS_LARGE = dict(self._DEFAULT_COMMUTE_BRACKETS_LARGE)
        else:
            self.COMMUTE_BRACKETS_SMALL = dict(self._DEFAULT_COMMUTE_BRACKETS_SMALL)
            self.COMMUTE_BRACKETS_LARGE = dict(self._DEFAULT_COMMUTE_BRACKETS_LARGE)
            self.PENDLER_EURO_PER_KM = self._DEFAULT_PENDLER_EURO_PER_KM
            self.HOME_OFFICE_DEDUCTION = self._DEFAULT_HOME_OFFICE_DEDUCTION
            self.CHILD_DEDUCTION_MONTHLY = self._DEFAULT_CHILD_DEDUCTION_MONTHLY
            self.SINGLE_PARENT_DEDUCTION = self._DEFAULT_SINGLE_PARENT_DEDUCTION
            self.WERBUNGSKOSTENPAUSCHALE = self._DEFAULT_WERBUNGSKOSTENPAUSCHALE
            self.VERKEHRSABSETZBETRAG = self._DEFAULT_VERKEHRSABSETZBETRAG
            self.FAMILIENBONUS_UNDER_18 = self._DEFAULT_FAMILIENBONUS_UNDER_18
            self.FAMILIENBONUS_18_24 = self._DEFAULT_FAMILIENBONUS_18_24
            self.ALLEINVERDIENER_BASE = self._DEFAULT_ALLEINVERDIENER_BASE
            self.ALLEINVERDIENER_2_CHILDREN = self._DEFAULT_ALLEINVERDIENER_2_CHILDREN
            self.ALLEINVERDIENER_PER_EXTRA_CHILD = self._DEFAULT_ALLEINVERDIENER_PER_EXTRA_CHILD
            self.ZUSCHLAG_VERKEHRSABSETZBETRAG = self._DEFAULT_ZUSCHLAG_VERKEHRSABSETZBETRAG
            self.ZUSCHLAG_INCOME_LOWER = self._DEFAULT_ZUSCHLAG_INCOME_LOWER
            self.ZUSCHLAG_INCOME_UPPER = self._DEFAULT_ZUSCHLAG_INCOME_UPPER
            self.ERHOEHTER_VERKEHRSABSETZBETRAG = self._DEFAULT_ERHOEHTER_VERKEHRSABSETZBETRAG
            self.PENSIONISTEN_ABSETZBETRAG = self._DEFAULT_PENSIONISTEN_ABSETZBETRAG
            self.PENSIONISTEN_INCOME_LOWER = self._DEFAULT_PENSIONISTEN_INCOME_LOWER
            self.PENSIONISTEN_INCOME_UPPER = self._DEFAULT_PENSIONISTEN_INCOME_UPPER
            self.ERHOEHTER_PENSIONISTEN = self._DEFAULT_ERHOEHTER_PENSIONISTEN
            self.ERHOEHTER_PENSIONISTEN_INCOME_LOWER = self._DEFAULT_ERHOEHTER_PENSIONISTEN_INCOME_LOWER
            self.ERHOEHTER_PENSIONISTEN_INCOME_UPPER = self._DEFAULT_PENSIONISTEN_INCOME_UPPER
            self.SONDERAUSGABENPAUSCHALE = self._DEFAULT_SONDERAUSGABENPAUSCHALE
            self.KIRCHENBEITRAG_CAP = self._DEFAULT_KIRCHENBEITRAG_CAP
            self.SPENDEN_INCOME_RATIO = self._DEFAULT_SPENDEN_INCOME_RATIO

    def calculate_commuting_allowance(
        self,
        distance_km: int,
        public_transport_available: bool,
        working_days_per_year: int = 220
    ) -> DeductionResult:
        """
        Calculate commuting allowance (Pendlerpauschale).
        
        The calculation includes:
        1. Base monthly amount based on distance brackets
        2. Pendlereuro (€6/km/year)
        
        Args:
            distance_km: One-way commuting distance in kilometers
            public_transport_available: Whether public transport is available
            working_days_per_year: Number of working days (default 220)
            
        Returns:
            DeductionResult with total annual amount and breakdown
        """
        # Minimum distance: 20km for Kleines, 2km for Großes Pendlerpauschale
        min_distance = 20 if public_transport_available else 2
        if distance_km < min_distance:
            note = (
                "Commuting distance less than 20km - not eligible for Kleines Pendlerpauschale"
                if public_transport_available
                else "Commuting distance less than 2km - not eligible for Großes Pendlerpauschale"
            )
            return DeductionResult(
                amount=Decimal('0.00'),
                breakdown={},
                note=note
            )
        
        # Select bracket type based on public transport availability
        bracket_type = 'small' if public_transport_available else 'large'
        brackets = self.COMMUTE_BRACKETS_SMALL if public_transport_available else self.COMMUTE_BRACKETS_LARGE
        
        # Determine base monthly amount based on distance
        if distance_km >= 60:
            base_monthly = brackets[60]
            distance_bracket = "60km+"
        elif distance_km >= 40:
            base_monthly = brackets[40]
            distance_bracket = "40-60km"
        elif distance_km >= 20:
            base_monthly = brackets[20]
            distance_bracket = "20-40km"
        else:  # distance_km >= 2, only for Großes Pendlerpauschale
            base_monthly = brackets[2]
            distance_bracket = "2-20km"
        
        # Calculate annual base amount
        base_annual = base_monthly * Decimal('12')
        
        # Calculate Pendlereuro (€6 per km per year)
        # IMPORTANT: Pendlereuro is an Absetzbetrag (tax credit), NOT an income deduction.
        # It is stored in breakdown for the calling engine to apply separately from tax liability.
        # Only Pendlerpauschale (base_annual) is an income deduction (Werbungskosten/Freibetrag).
        pendler_euro = Decimal(str(distance_km)) * self.PENDLER_EURO_PER_KM
        
        # amount = only Pendlerpauschale (income deduction / Freibetrag)
        # Pendlereuro is in breakdown['pendler_euro'] for the engine to use as tax credit
        allowance_type = 'Kleines Pendlerpauschale' if public_transport_available else 'Großes Pendlerpauschale'
        
        return DeductionResult(
            amount=base_annual.quantize(Decimal('0.01')),
            breakdown={
                'type': allowance_type,
                'distance_km': distance_km,
                'distance_bracket': distance_bracket,
                'base_monthly': base_monthly.quantize(Decimal('0.01')),
                'base_annual': base_annual.quantize(Decimal('0.01')),
                'pendler_euro': pendler_euro.quantize(Decimal('0.01')),
                'public_transport_available': public_transport_available
            }
        )
    
    def calculate_home_office_deduction(
        self,
        telearbeit_days: Optional[int] = None,
        employer_telearbeit_pauschale: Decimal = Decimal("0.00"),
    ) -> DeductionResult:
        """
        Calculate Telearbeitspauschale / Home Office deduction (Werbungskosten).

        BMF rules (since 2025):
        - €3.00 per Telearbeit/Home-Office day
        - Maximum 100 days per year → annual cap €300
        - If employer pays tax-free Telearbeitspauschale, the employee can only
          claim the shortfall (max_allowed − employer_paid)

        Semantics:
        - telearbeit_days is None → legacy/unknown data → flat €300 fallback
        - telearbeit_days == 0    → user explicitly has 0 home-office days → €0

        Args:
            telearbeit_days: Number of home-office days (None = unknown/legacy)
            employer_telearbeit_pauschale: Amount already paid tax-free by employer

        Returns:
            DeductionResult with deductible amount and breakdown
        """
        if not isinstance(employer_telearbeit_pauschale, Decimal):
            employer_telearbeit_pauschale = Decimal(str(employer_telearbeit_pauschale))

        # Legacy fallback: no day info → flat €300
        if telearbeit_days is None:
            return DeductionResult(
                amount=self.HOME_OFFICE_DEDUCTION,
                breakdown={
                    'type': 'Telearbeitspauschale',
                    'mode': 'flat_rate_fallback',
                    'annual_amount': self.HOME_OFFICE_DEDUCTION,
                },
                note="Home office flat-rate €300/year (no day count provided)"
            )

        # Precise calculation (telearbeit_days is an int here, including 0)
        eligible_days = min(max(telearbeit_days, 0), 100)
        rate_per_day = Decimal("3.00")
        max_allowed = rate_per_day * Decimal(str(eligible_days))
        deductible = max(Decimal("0.00"), max_allowed - employer_telearbeit_pauschale)
        deductible = deductible.quantize(Decimal("0.01"))

        return DeductionResult(
            amount=deductible,
            breakdown={
                'type': 'Telearbeitspauschale',
                'mode': 'precise',
                'telearbeit_days': telearbeit_days,
                'eligible_days': eligible_days,
                'rate_per_day': rate_per_day,
                'max_allowed': max_allowed.quantize(Decimal("0.01")),
                'employer_paid': employer_telearbeit_pauschale.quantize(Decimal("0.01")),
                'deductible': deductible,
            },
            note=(
                f"Telearbeitspauschale: {eligible_days} Tage × €3.00 = €{max_allowed:.2f}"
                f" − €{employer_telearbeit_pauschale:.2f} AG-Pauschale"
                f" = €{deductible} absetzbar"
            )
        )
    
    def calculate_family_deductions(
        self,
        family_info: FamilyInfo
    ) -> DeductionResult:
        """
        Calculate family-related deductions.
        
        Includes:
        1. Child deduction (Kinderabsetzbetrag)
        2. Single parent deduction (if applicable)
        
        Args:
            family_info: FamilyInfo object with number of children and single parent status
            
        Returns:
            DeductionResult with total family deductions and breakdown
        """
        # Calculate child deduction
        child_deduction = (
            self.CHILD_DEDUCTION_MONTHLY * 
            Decimal('12') * 
            Decimal(str(family_info.num_children))
        )
        
        # Calculate single parent deduction
        single_parent_deduction = (
            self.SINGLE_PARENT_DEDUCTION 
            if family_info.is_single_parent 
            else Decimal('0.00')
        )
        
        # Total deduction
        total = child_deduction + single_parent_deduction
        
        return DeductionResult(
            amount=total.quantize(Decimal('0.01')),
            breakdown={
                'child_deduction': child_deduction.quantize(Decimal('0.01')),
                'child_deduction_monthly': self.CHILD_DEDUCTION_MONTHLY,
                'num_children': family_info.num_children,
                'single_parent_deduction': single_parent_deduction.quantize(Decimal('0.01')),
                'is_single_parent': family_info.is_single_parent
            }
        )
    
    def calculate_single_parent_deduction(self) -> DeductionResult:
        """
        Calculate single parent deduction.
        
        Returns:
            DeductionResult with annual deduction for single parents
        """
        return DeductionResult(
            amount=self.SINGLE_PARENT_DEDUCTION,
            breakdown={
                'type': 'Single Parent Deduction',
                'annual_amount': self.SINGLE_PARENT_DEDUCTION
            },
            note=f"Single parent deduction of €{self.SINGLE_PARENT_DEDUCTION}/year"
        )
    
    def calculate_familienbonus(self, family_info: FamilyInfo) -> DeductionResult:
        """
        Calculate Familienbonus Plus (tax credit).

        €2,000/year per child under 18, €700/year per child aged 18-24.
        This is an Absetzbetrag — deducted directly from tax liability.

        Args:
            family_info: FamilyInfo with children_under_18 and children_18_to_24

        Returns:
            DeductionResult with total Familienbonus amount
        """
        bonus_under_18 = self.FAMILIENBONUS_UNDER_18 * Decimal(str(family_info.children_under_18))
        bonus_18_24 = self.FAMILIENBONUS_18_24 * Decimal(str(family_info.children_18_to_24))
        total = bonus_under_18 + bonus_18_24

        return DeductionResult(
            amount=total.quantize(Decimal('0.01')),
            breakdown={
                'children_under_18': family_info.children_under_18,
                'bonus_per_child_under_18': self.FAMILIENBONUS_UNDER_18,
                'bonus_under_18_total': bonus_under_18.quantize(Decimal('0.01')),
                'children_18_to_24': family_info.children_18_to_24,
                'bonus_per_child_18_24': self.FAMILIENBONUS_18_24,
                'bonus_18_24_total': bonus_18_24.quantize(Decimal('0.01')),
            },
            note=f"Familienbonus Plus: {family_info.children_under_18}×€{self.FAMILIENBONUS_UNDER_18} + "
                 f"{family_info.children_18_to_24}×€{self.FAMILIENBONUS_18_24} = €{total}"
        )

    def calculate_alleinverdiener(self, family_info: FamilyInfo) -> DeductionResult:
        """
        Calculate Alleinverdienerabsetzbetrag / Alleinerzieherabsetzbetrag (tax credit).

        Applies to sole earners or single parents with at least 1 child.
        Base: €520/year. Additional: €704 for each child beyond the first.
        This is an Absetzbetrag — deducted directly from tax liability.

        Args:
            family_info: FamilyInfo with is_sole_earner or is_single_parent and num_children

        Returns:
            DeductionResult with Alleinverdiener/Alleinerzieher amount
        """
        eligible = (
            (family_info.is_sole_earner or family_info.is_single_parent)
            and family_info.num_children > 0
        )

        if not eligible:
            return DeductionResult(
                amount=Decimal('0.00'),
                breakdown={},
                note="Not eligible for Alleinverdiener/Alleinerzieherabsetzbetrag"
            )

        n = family_info.num_children
        # Official BMF total amounts: base=1-child total, 2_children=2-children total,
        # 3+ = 2_children + per_extra_child * (n-2)
        if n == 1:
            total = self.ALLEINVERDIENER_BASE
        elif n == 2:
            total = self.ALLEINVERDIENER_2_CHILDREN
        else:
            total = self.ALLEINVERDIENER_2_CHILDREN + self.ALLEINVERDIENER_PER_EXTRA_CHILD * Decimal(str(n - 2))

        label = (
            "Alleinerzieherabsetzbetrag" if family_info.is_single_parent
            else "Alleinverdienerabsetzbetrag"
        )

        return DeductionResult(
            amount=total.quantize(Decimal('0.01')),
            breakdown={
                'type': label,
                'num_children': n,
                'total': total.quantize(Decimal('0.01')),
            },
            note=f"{label}: €{total} for {n} child(ren)"
        )

    def calculate_zuschlag_verkehrsabsetzbetrag(
        self,
        annual_income: Decimal,
    ) -> DeductionResult:
        """
        Calculate Zuschlag zum Verkehrsabsetzbetrag for low-income employees.

        The Zuschlag is a tax credit (Absetzbetrag) that phases out linearly
        between a lower and upper income threshold. It applies to employees
        with low income to compensate for commuting costs.

        Since 2023 (cold-progression adjustment), the thresholds are adjusted
        annually. For 2026: full €752 up to €16,832, phases out to €0 at €28,326.

        Args:
            annual_income: Annual gross income (before deductions)

        Returns:
            DeductionResult with Zuschlag amount
        """
        if not isinstance(annual_income, Decimal):
            annual_income = Decimal(str(annual_income))

        if annual_income <= self.ZUSCHLAG_INCOME_LOWER:
            amount = self.ZUSCHLAG_VERKEHRSABSETZBETRAG
        elif annual_income >= self.ZUSCHLAG_INCOME_UPPER:
            amount = Decimal('0.00')
        else:
            # Linear phase-out
            income_range = self.ZUSCHLAG_INCOME_UPPER - self.ZUSCHLAG_INCOME_LOWER
            excess = annual_income - self.ZUSCHLAG_INCOME_LOWER
            reduction = (excess / income_range) * self.ZUSCHLAG_VERKEHRSABSETZBETRAG
            amount = (self.ZUSCHLAG_VERKEHRSABSETZBETRAG - reduction).quantize(Decimal('0.01'))

        return DeductionResult(
            amount=amount,
            breakdown={
                'type': 'Zuschlag zum Verkehrsabsetzbetrag',
                'full_amount': self.ZUSCHLAG_VERKEHRSABSETZBETRAG,
                'income': annual_income,
                'lower_threshold': self.ZUSCHLAG_INCOME_LOWER,
                'upper_threshold': self.ZUSCHLAG_INCOME_UPPER,
            },
            note=f"Zuschlag zum Verkehrsabsetzbetrag: €{amount}"
        )

    def calculate_pensionisten_absetzbetrag(
        self,
        pension_income: Decimal,
        is_single: bool = False,
    ) -> DeductionResult:
        """
        Calculate Pensionistenabsetzbetrag (tax credit for pensioners).

        §33 Abs 6 EStG. Phases out linearly between lower and upper thresholds.
        An increased amount (Erhöhter Pensionistenabsetzbetrag) applies to
        single pensioners without a partner earning > €2,455/year.

        Args:
            pension_income: Annual pension income
            is_single: Whether the pensioner is single (for increased amount)

        Returns:
            DeductionResult with Pensionistenabsetzbetrag amount
        """
        if not isinstance(pension_income, Decimal):
            pension_income = Decimal(str(pension_income))

        if is_single:
            full_amount = self.ERHOEHTER_PENSIONISTEN
            lower = self.ERHOEHTER_PENSIONISTEN_INCOME_LOWER
            upper = self.ERHOEHTER_PENSIONISTEN_INCOME_UPPER
        else:
            full_amount = self.PENSIONISTEN_ABSETZBETRAG
            lower = self.PENSIONISTEN_INCOME_LOWER
            upper = self.PENSIONISTEN_INCOME_UPPER

        if pension_income <= lower:
            amount = full_amount
        elif pension_income >= upper:
            amount = Decimal('0.00')
        else:
            income_range = upper - lower
            excess = pension_income - lower
            reduction = (excess / income_range) * full_amount
            amount = (full_amount - reduction).quantize(Decimal('0.01'))

        label = (
            "Erhöhter Pensionistenabsetzbetrag" if is_single
            else "Pensionistenabsetzbetrag"
        )

        return DeductionResult(
            amount=amount,
            breakdown={
                'type': label,
                'full_amount': full_amount,
                'pension_income': pension_income,
                'lower_threshold': lower,
                'upper_threshold': upper,
                'is_single': is_single,
            },
            note=f"{label}: €{amount}"
        )

    def calculate_sonderausgabenpauschale(self) -> DeductionResult:
        """
        Calculate Sonderausgabenpauschale (§18 Abs 2 EStG).

        A fixed €60/year flat-rate deduction for special expenses (Sonderausgaben)
        that is automatically applied to all taxpayers without documentation.

        Note: The old Topfsonderausgaben (insurance premiums, building savings,
        etc.) were phased out from 2021. Only contracts from before 2016 may
        still claim them during the transition period (until 2020 was the last
        year for new contracts).

        Returns:
            DeductionResult with €60 annual deduction
        """
        return DeductionResult(
            amount=self.SONDERAUSGABENPAUSCHALE,
            breakdown={
                'type': 'Sonderausgabenpauschale',
                'annual_amount': self.SONDERAUSGABENPAUSCHALE,
            },
            note="Sonderausgabenpauschale: €60/Jahr (automatisch für alle Steuerpflichtigen)"
        )

    def calculate_sonderausgaben(
        self,
        kirchenbeitrag: Decimal = Decimal("0.00"),
        spenden: Decimal = Decimal("0.00"),
        previous_year_income: Optional[Decimal] = None,
        tax_year: Optional[int] = None,
    ) -> DeductionResult:
        """
        Calculate deductible Sonderausgaben (special expenses) per §18 EStG.

        Covers:
        1. Kirchenbeitrag (§18 Abs 1 Z 5 EStG) — church contributions, year-dependent cap:
           - ≤2023: €400/year
           - 2024+: €600/year (AbgÄG 2023, BGBl I Nr. 110/2023)
        2. Spenden (§18 Abs 1 Z 7 EStG) — donations to qualifying organisations (BMF list),
           capped at 10% of Gesamtbetrag der Einkünfte from previous year's tax return
        3. Sonderausgabenpauschale (§18 Abs 2 EStG) — flat €60, applied automatically;
           subsumed when actual Sonderausgaben exceed €60

        Args:
            kirchenbeitrag: Church contribution amount paid in the year
            spenden: Donation amount to qualifying organisations
            previous_year_income: Previous year's Gesamtbetrag der Einkünfte (for Spenden cap);
                if None, no cap is applied (caller may pre-cap)
            tax_year: Tax year (determines Kirchenbeitrag cap). If None, uses default (2024+ cap).

        Returns:
            DeductionResult with total deductible Sonderausgaben and breakdown
        """
        if not isinstance(kirchenbeitrag, Decimal):
            kirchenbeitrag = Decimal(str(kirchenbeitrag))
        if not isinstance(spenden, Decimal):
            spenden = Decimal(str(spenden))

        # Kirchenbeitrag: year-dependent cap (€400 for ≤2023, €600 for 2024+)
        if tax_year is not None and tax_year <= 2023:
            kirchenbeitrag_cap = self._KIRCHENBEITRAG_CAP_2023
        else:
            kirchenbeitrag_cap = self.KIRCHENBEITRAG_CAP
        kirchenbeitrag_deductible = min(kirchenbeitrag, kirchenbeitrag_cap)

        # Spenden: capped at 10% of previous year's income
        if previous_year_income is not None:
            if not isinstance(previous_year_income, Decimal):
                previous_year_income = Decimal(str(previous_year_income))
            spenden_cap = (previous_year_income * self.SPENDEN_INCOME_RATIO).quantize(Decimal("0.01"))
            spenden_deductible = min(spenden, spenden_cap)
        else:
            spenden_deductible = spenden
            spenden_cap = None

        actual_total = kirchenbeitrag_deductible + spenden_deductible

        # §18 Abs 2: Sonderausgabenpauschale (€60) is subsumed when actual > €60
        if actual_total > self.SONDERAUSGABENPAUSCHALE:
            total = actual_total
            pauschale_applied = False
        else:
            total = self.SONDERAUSGABENPAUSCHALE
            pauschale_applied = True

        breakdown = {
            'type': 'Sonderausgaben',
            'kirchenbeitrag_paid': kirchenbeitrag.quantize(Decimal("0.01")),
            'kirchenbeitrag_cap': kirchenbeitrag_cap,
            'kirchenbeitrag_deductible': kirchenbeitrag_deductible.quantize(Decimal("0.01")),
            'spenden_paid': spenden.quantize(Decimal("0.01")),
            'spenden_deductible': spenden_deductible.quantize(Decimal("0.01")),
            'pauschale_applied': pauschale_applied,
        }
        if spenden_cap is not None:
            breakdown['spenden_cap'] = spenden_cap

        return DeductionResult(
            amount=total.quantize(Decimal("0.01")),
            breakdown=breakdown,
            note=(
                f"Sonderausgaben: Kirchenbeitrag {kirchenbeitrag_deductible}"
                f" + Spenden {spenden_deductible}"
                f" = {actual_total}"
                + (f" (Pauschale {self.SONDERAUSGABENPAUSCHALE} applied)" if pauschale_applied else "")
            ),
        )

    def calculate_employee_deductions(
        self,
        actual_werbungskosten: Decimal = Decimal('0.00')
    ) -> DeductionResult:
        """
        Calculate employee-specific deductions.

        Includes:
        1. Werbungskostenpauschale (€132/year) - deducted from income,
           unless actual Werbungskosten are higher
        2. Verkehrsabsetzbetrag - deducted from tax liability

        Args:
            actual_werbungskosten: Actual work-related expenses claimed by employee

        Returns:
            DeductionResult with income deduction amount and tax credit in breakdown
        """
        # Werbungskostenpauschale: apply only if actual expenses are lower
        if actual_werbungskosten > self.WERBUNGSKOSTENPAUSCHALE:
            werbungskosten_deduction = Decimal('0.00')
            werbungskosten_note = (
                f"Actual Werbungskosten (€{actual_werbungskosten}) exceed "
                f"Pauschale (€{self.WERBUNGSKOSTENPAUSCHALE}) - Pauschale not applied"
            )
        else:
            werbungskosten_deduction = self.WERBUNGSKOSTENPAUSCHALE
            werbungskosten_note = "Werbungskostenpauschale applied (€132/year)"

        return DeductionResult(
            amount=werbungskosten_deduction,
            breakdown={
                'werbungskostenpauschale': werbungskosten_deduction.quantize(Decimal('0.01')),
                'verkehrsabsetzbetrag': self.VERKEHRSABSETZBETRAG.quantize(Decimal('0.01')),
                'actual_werbungskosten': actual_werbungskosten.quantize(Decimal('0.01')),
            },
            note=werbungskosten_note
        )

    def calculate_total_deductions(
        self,
        commuting_distance_km: Optional[int] = None,
        public_transport_available: Optional[bool] = None,
        home_office_eligible: bool = False,
        telearbeit_days: Optional[int] = None,
        employer_telearbeit_pauschale: Decimal = Decimal("0.00"),
        family_info: Optional[FamilyInfo] = None,
        is_employee: bool = False,
        actual_werbungskosten: Decimal = Decimal('0.00'),
        annual_income: Optional[Decimal] = None,
        kirchenbeitrag: Decimal = Decimal('0.00'),
        spenden: Decimal = Decimal('0.00'),
        previous_year_income: Optional[Decimal] = None,
    ) -> DeductionResult:
        """
        Calculate total deductions from all sources.

        Returns a DeductionResult where:
        - amount = total INCOME deductions (reduce taxable_income)
        - breakdown contains both income deductions and tax credits (Absetzbeträge)

        Tax credits (Absetzbeträge) are stored in breakdown but NOT included in amount.
        The calling engine must apply them separately: final_tax = max(0, tariff_tax - credits).

        Breakdown keys for tax credits (Absetzbeträge — reduce tax, not income):
        - 'verkehrsabsetzbetrag': VAB amount
        - 'pendlereuro': Pendlereuro (€6/km/year) — Absetzbetrag per §33 Abs 5 EStG
        - 'zuschlag_verkehrsabsetzbetrag': Zuschlag for low-income employees
        - 'familienbonus_amount': Familienbonus Plus
        - 'alleinverdiener_amount': AVAB/AEAB (includes single parent = Alleinerzieher)

        Breakdown keys for informational items (NOT included in amount):
        - 'kinderabsetzbetrag_info': Kinderabsetzbetrag (paid via Familienbeihilfe,
          not an income deduction or Absetzbetrag in the tax return)

        Args:
            commuting_distance_km: One-way commuting distance (None if not applicable)
            public_transport_available: Whether public transport is available
            home_office_eligible: Whether eligible for home office deduction
            telearbeit_days: Number of home office days (None = legacy fallback)
            employer_telearbeit_pauschale: Employer-paid tax-free home office allowance
            family_info: Family information (None if not applicable)
            is_employee: Whether the user is an employee (for Werbungskostenpauschale)
            actual_werbungskosten: Actual work-related expenses (employees only)
            annual_income: Annual gross income (needed for Zuschlag calculation)

        Returns:
            DeductionResult with income deductions total and detailed breakdown.
        """
        total_amount = Decimal('0.00')
        breakdown = {}

        # Commuting: Pendlerpauschale = income deduction, Pendlereuro = tax credit
        if commuting_distance_km is not None and public_transport_available is not None:
            commuting_result = self.calculate_commuting_allowance(
                distance_km=commuting_distance_km,
                public_transport_available=public_transport_available
            )
            if commuting_result.amount > Decimal('0.00'):
                # Pendlerpauschale (base_annual) → income deduction
                total_amount += commuting_result.amount
                breakdown['commuting_allowance'] = commuting_result.breakdown
                breakdown['commuting_amount'] = commuting_result.amount
            # Pendlereuro → tax credit (Absetzbetrag), stored separately
            pendlereuro = commuting_result.breakdown.get('pendler_euro', Decimal('0.00'))
            if pendlereuro > Decimal('0.00'):
                breakdown['pendlereuro'] = pendlereuro

        # Telearbeitspauschale / Home office — income deduction
        if home_office_eligible or telearbeit_days is not None:
            home_office_result = self.calculate_home_office_deduction(
                telearbeit_days=telearbeit_days,
                employer_telearbeit_pauschale=employer_telearbeit_pauschale,
            )
            total_amount += home_office_result.amount
            breakdown['telearbeit'] = home_office_result.breakdown
            breakdown['telearbeit_amount'] = home_office_result.amount

        # Family-related items
        if family_info is not None and family_info.num_children > 0:
            # Kinderabsetzbetrag — informational only.
            # This is paid automatically via Familienbeihilfe and should NOT be
            # treated as an income deduction or tax credit in the Veranlagung.
            family_result = self.calculate_family_deductions(family_info)
            breakdown['kinderabsetzbetrag_info'] = family_result.breakdown
            breakdown['kinderabsetzbetrag_info_amount'] = family_result.amount
            # NOTE: deliberately NOT added to total_amount

            # NOTE: Alleinerzieherabsetzbetrag (AEAB) is a TAX CREDIT (Absetzbetrag),
            # NOT an income deduction. It is handled via calculate_alleinverdiener()
            # below and stored in breakdown for the engine to apply from tax liability.
            # Do NOT add SINGLE_PARENT_DEDUCTION to total_amount here.

            # Familienbonus Plus (tax credit — stored for engine to apply from tax liability)
            familienbonus_result = self.calculate_familienbonus(family_info)
            if familienbonus_result.amount > Decimal('0.00'):
                breakdown['familienbonus'] = familienbonus_result.breakdown
                breakdown['familienbonus_amount'] = familienbonus_result.amount

            # Alleinverdiener/Alleinerzieher (tax credit — stored for engine)
            # This includes both AVAB (sole earner) and AEAB (single parent).
            alleinverdiener_result = self.calculate_alleinverdiener(family_info)
            if alleinverdiener_result.amount > Decimal('0.00'):
                breakdown['alleinverdiener'] = alleinverdiener_result.breakdown
                breakdown['alleinverdiener_amount'] = alleinverdiener_result.amount

        # Sonderausgaben (§18 EStG): Kirchenbeitrag + Spenden
        # Replaces the flat Sonderausgabenpauschale (€60) when actual amounts exceed it
        if kirchenbeitrag > Decimal('0.00') or spenden > Decimal('0.00'):
            sonderausgaben_result = self.calculate_sonderausgaben(
                kirchenbeitrag=kirchenbeitrag,
                spenden=spenden,
                previous_year_income=previous_year_income,
            )
            total_amount += sonderausgaben_result.amount
            breakdown['sonderausgaben'] = sonderausgaben_result.breakdown
            breakdown['sonderausgaben_amount'] = sonderausgaben_result.amount
        else:
            # Automatic Sonderausgabenpauschale (€60)
            pauschale_result = self.calculate_sonderausgabenpauschale()
            total_amount += pauschale_result.amount
            breakdown['sonderausgaben'] = pauschale_result.breakdown
            breakdown['sonderausgaben_amount'] = pauschale_result.amount

        # Employee-specific deductions
        if is_employee:
            employee_result = self.calculate_employee_deductions(
                actual_werbungskosten=actual_werbungskosten
            )
            # Werbungskostenpauschale is an income deduction
            total_amount += employee_result.amount
            breakdown['employee_deductions'] = employee_result.breakdown
            breakdown['werbungskostenpauschale_amount'] = employee_result.amount
            # Verkehrsabsetzbetrag is a tax credit - stored in breakdown for the engine
            breakdown['verkehrsabsetzbetrag'] = employee_result.breakdown['verkehrsabsetzbetrag']

            # Zuschlag zum Verkehrsabsetzbetrag for low-income employees (§33 Abs 5 EStG)
            if annual_income is not None:
                zuschlag_result = self.calculate_zuschlag_verkehrsabsetzbetrag(annual_income)
                if zuschlag_result.amount > Decimal('0.00'):
                    breakdown['zuschlag_verkehrsabsetzbetrag'] = zuschlag_result.amount
                    breakdown['zuschlag_details'] = zuschlag_result.breakdown

        return DeductionResult(
            amount=total_amount.quantize(Decimal('0.01')),
            breakdown=breakdown
        )

