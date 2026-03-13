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
    _DEFAULT_CHILD_DEDUCTION_MONTHLY = Decimal('70.90')  # 2025/2026/2027: €70.90 (frozen)
    _DEFAULT_SINGLE_PARENT_DEDUCTION = Decimal('612.00')  # 2026: €612 (same as Alleinerzieher)
    _DEFAULT_WERBUNGSKOSTENPAUSCHALE = Decimal('132.00')
    _DEFAULT_VERKEHRSABSETZBETRAG = Decimal('496.00')  # 2026: €496 (2025: €487)
    _DEFAULT_FAMILIENBONUS_UNDER_18 = Decimal('2000.16')  # since 2022
    _DEFAULT_FAMILIENBONUS_18_24 = Decimal('700.08')  # since 2024
    _DEFAULT_ALLEINVERDIENER_BASE = Decimal('612.00')  # 2026: €612 (2025: €601)
    _DEFAULT_ALLEINVERDIENER_PER_CHILD = Decimal('273.00')  # 2026: €273 per additional child
    # Zuschlag zum Verkehrsabsetzbetrag for low-income earners (§33 Abs 5 EStG)
    # Full Zuschlag if income ≤ €16,832 (2026), phases out to €0 at €28,326 (2026)
    _DEFAULT_ZUSCHLAG_VERKEHRSABSETZBETRAG = Decimal('752.00')  # 2026: €752
    _DEFAULT_ZUSCHLAG_INCOME_LOWER = Decimal('16832.00')  # Full Zuschlag up to this income
    _DEFAULT_ZUSCHLAG_INCOME_UPPER = Decimal('28326.00')  # Zuschlag phases out above this
    # Pensionistenabsetzbetrag (§33 Abs 6 EStG) — tax credit for pensioners
    _DEFAULT_PENSIONISTEN_ABSETZBETRAG = Decimal('954.00')  # 2026: €954
    _DEFAULT_PENSIONISTEN_INCOME_LOWER = Decimal('20233.00')  # Full amount up to this
    _DEFAULT_PENSIONISTEN_INCOME_UPPER = Decimal('30981.00')  # Phases out above this
    # Erhöhter Pensionistenabsetzbetrag (for single pensioners)
    _DEFAULT_ERHOEHTER_PENSIONISTEN = Decimal('1405.00')  # 2026: €1,405
    _DEFAULT_ERHOEHTER_PENSIONISTEN_UPPER = Decimal('25774.00')  # Phases out up to this
    # Sonderausgabenpauschale (§18 Abs 2 EStG) — automatic special expenses flat-rate
    _DEFAULT_SONDERAUSGABENPAUSCHALE = Decimal('60.00')  # €60/year (unchanged for years)

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
            self.ALLEINVERDIENER_PER_CHILD = Decimal(str(
                deduction_config.get('alleinverdiener_per_child', self._DEFAULT_ALLEINVERDIENER_PER_CHILD)
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
            self.ERHOEHTER_PENSIONISTEN_UPPER = Decimal(str(
                deduction_config.get('erhoehter_pensionisten_upper', self._DEFAULT_ERHOEHTER_PENSIONISTEN_UPPER)
            ))
            self.SONDERAUSGABENPAUSCHALE = Decimal(str(
                deduction_config.get('sonderausgabenpauschale', self._DEFAULT_SONDERAUSGABENPAUSCHALE)
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
            self.ALLEINVERDIENER_PER_CHILD = self._DEFAULT_ALLEINVERDIENER_PER_CHILD
            self.ZUSCHLAG_VERKEHRSABSETZBETRAG = self._DEFAULT_ZUSCHLAG_VERKEHRSABSETZBETRAG
            self.ZUSCHLAG_INCOME_LOWER = self._DEFAULT_ZUSCHLAG_INCOME_LOWER
            self.ZUSCHLAG_INCOME_UPPER = self._DEFAULT_ZUSCHLAG_INCOME_UPPER
            self.PENSIONISTEN_ABSETZBETRAG = self._DEFAULT_PENSIONISTEN_ABSETZBETRAG
            self.PENSIONISTEN_INCOME_LOWER = self._DEFAULT_PENSIONISTEN_INCOME_LOWER
            self.PENSIONISTEN_INCOME_UPPER = self._DEFAULT_PENSIONISTEN_INCOME_UPPER
            self.ERHOEHTER_PENSIONISTEN = self._DEFAULT_ERHOEHTER_PENSIONISTEN
            self.ERHOEHTER_PENSIONISTEN_UPPER = self._DEFAULT_ERHOEHTER_PENSIONISTEN_UPPER
            self.SONDERAUSGABENPAUSCHALE = self._DEFAULT_SONDERAUSGABENPAUSCHALE
    
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
        pendler_euro = Decimal(str(distance_km)) * self.PENDLER_EURO_PER_KM
        
        # Total deduction
        total = base_annual + pendler_euro
        
        # Prepare breakdown
        allowance_type = 'Kleines Pendlerpauschale' if public_transport_available else 'Großes Pendlerpauschale'
        
        return DeductionResult(
            amount=total.quantize(Decimal('0.01')),
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
    
    def calculate_home_office_deduction(self) -> DeductionResult:
        """
        Calculate home office deduction.
        
        Austria provides a flat-rate deduction of €300/year for home office expenses.
        
        Returns:
            DeductionResult with €300 annual deduction
        """
        return DeductionResult(
            amount=self.HOME_OFFICE_DEDUCTION,
            breakdown={
                'type': 'Home Office Deduction',
                'rate': 'Flat rate',
                'annual_amount': self.HOME_OFFICE_DEDUCTION
            },
            note="Home office flat-rate deduction of €300/year"
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

        base = self.ALLEINVERDIENER_BASE
        additional = Decimal('0.00')
        if family_info.num_children > 1:
            additional = self.ALLEINVERDIENER_PER_CHILD * Decimal(
                str(family_info.num_children - 1)
            )
        total = base + additional

        label = (
            "Alleinerzieherabsetzbetrag" if family_info.is_single_parent
            else "Alleinverdienerabsetzbetrag"
        )

        return DeductionResult(
            amount=total.quantize(Decimal('0.01')),
            breakdown={
                'type': label,
                'base': base.quantize(Decimal('0.01')),
                'additional_per_child': self.ALLEINVERDIENER_PER_CHILD,
                'additional_children': max(0, family_info.num_children - 1),
                'additional_total': additional.quantize(Decimal('0.01')),
            },
            note=f"{label}: €{base} + {max(0, family_info.num_children - 1)}×€{self.ALLEINVERDIENER_PER_CHILD} = €{total}"
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
            upper = self.ERHOEHTER_PENSIONISTEN_UPPER
        else:
            full_amount = self.PENSIONISTEN_ABSETZBETRAG
            upper = self.PENSIONISTEN_INCOME_UPPER

        lower = self.PENSIONISTEN_INCOME_LOWER

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
        family_info: Optional[FamilyInfo] = None,
        is_employee: bool = False,
        actual_werbungskosten: Decimal = Decimal('0.00')
    ) -> DeductionResult:
        """
        Calculate total deductions from all sources.

        Args:
            commuting_distance_km: One-way commuting distance (None if not applicable)
            public_transport_available: Whether public transport is available
            home_office_eligible: Whether eligible for home office deduction
            family_info: Family information (None if not applicable)
            is_employee: Whether the user is an employee (for Werbungskostenpauschale)
            actual_werbungskosten: Actual work-related expenses (employees only)

        Returns:
            DeductionResult with total deductions and detailed breakdown.
            For employees, breakdown includes 'verkehrsabsetzbetrag' (tax credit,
            to be applied separately from tax liability by the engine).
        """
        total_amount = Decimal('0.00')
        breakdown = {}

        # Commuting allowance
        if commuting_distance_km is not None and public_transport_available is not None:
            commuting_result = self.calculate_commuting_allowance(
                distance_km=commuting_distance_km,
                public_transport_available=public_transport_available
            )
            if commuting_result.amount > Decimal('0.00'):
                total_amount += commuting_result.amount
                breakdown['commuting_allowance'] = commuting_result.breakdown
                breakdown['commuting_amount'] = commuting_result.amount

        # Home office deduction
        if home_office_eligible:
            home_office_result = self.calculate_home_office_deduction()
            total_amount += home_office_result.amount
            breakdown['home_office'] = home_office_result.breakdown
            breakdown['home_office_amount'] = home_office_result.amount

        # Family deductions
        if family_info is not None and family_info.num_children > 0:
            family_result = self.calculate_family_deductions(family_info)
            total_amount += family_result.amount
            breakdown['family_deductions'] = family_result.breakdown
            breakdown['family_amount'] = family_result.amount

            # Familienbonus Plus (tax credit — stored for engine to apply from tax liability)
            familienbonus_result = self.calculate_familienbonus(family_info)
            if familienbonus_result.amount > Decimal('0.00'):
                breakdown['familienbonus'] = familienbonus_result.breakdown
                breakdown['familienbonus_amount'] = familienbonus_result.amount

            # Alleinverdiener/Alleinerzieher (tax credit — stored for engine)
            alleinverdiener_result = self.calculate_alleinverdiener(family_info)
            if alleinverdiener_result.amount > Decimal('0.00'):
                breakdown['alleinverdiener'] = alleinverdiener_result.breakdown
                breakdown['alleinverdiener_amount'] = alleinverdiener_result.amount

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

        return DeductionResult(
            amount=total_amount.quantize(Decimal('0.01')),
            breakdown=breakdown
        )

