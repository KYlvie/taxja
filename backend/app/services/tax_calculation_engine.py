"""Unified tax calculation engine integrating all tax calculators"""
from decimal import Decimal
from typing import Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass
import hashlib
import json
import logging

from .income_tax_calculator import IncomeTaxCalculator, IncomeTaxResult
from .vat_calculator import VATCalculator, VATResult, Transaction, PropertyType
from .svs_calculator import SVSCalculator, SVSResult, UserType
from .deduction_calculator import DeductionCalculator, DeductionResult, FamilyInfo
from .self_employed_tax_service import (
    calculate_gewinnfreibetrag,
    calculate_basispauschalierung,
    GewinnfreibetragResult,
    BasispauschalierungResult,
    SelfEmployedConfig,
    ExpenseMethod,
    ProfessionType,
)
from .kest_calculator import calculate_kest, KEStResult, CapitalIncomeType
from .immoest_calculator import calculate_immoest, ImmoEStResult, ExemptionType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Fallback list used when DB is unavailable (e.g. in tests without DB).
# In production the authoritative list comes from the tax_configurations table.
SUPPORTED_TAX_YEARS = [2022, 2023, 2024, 2025, 2026]


def get_supported_years_from_db(db) -> list[int]:
    """Query the database for all configured tax years."""
    try:
        from app.models.tax_configuration import TaxConfiguration
        rows = (
            db.query(TaxConfiguration.tax_year)
            .order_by(TaxConfiguration.tax_year)
            .all()
        )
        return [r[0] for r in rows]
    except Exception:
        return SUPPORTED_TAX_YEARS


@dataclass
class TaxBreakdown:
    """Detailed breakdown of all tax components"""
    income_tax: IncomeTaxResult
    vat: VATResult
    svs: SVSResult
    deductions: DeductionResult
    total_tax: Decimal
    net_income: Decimal
    gross_income: Decimal
    effective_tax_rate: Decimal
    warnings: List[Dict] = None  # Property tax warnings from AfACalculator
    gewinnfreibetrag: GewinnfreibetragResult = None  # §10 EStG profit allowance
    basispauschalierung: BasispauschalierungResult = None  # §17 EStG flat-rate expenses
    kest: KEStResult = None  # §27a EStG capital gains tax
    immoest: ImmoEStResult = None  # §30 EStG real estate gains tax
    
    def __post_init__(self):
        """Initialize warnings list if None"""
        if self.warnings is None:
            self.warnings = []


class TaxCalculationEngine:
    """
    Unified tax calculation engine for Austrian tax system.
    
    Integrates:
    - Income tax calculation (progressive tax with 2026 USP rates)
    - VAT calculation (small business exemption, tolerance rule)
    - SVS social insurance contributions
    - Deductions (commuting, home office, family)
    
    Calculates:
    - Total tax liability (income tax + VAT + SVS)
    - Net income (gross income - all taxes and contributions)
    - Comprehensive tax breakdown
    
    Caching:
    - Tax calculations are cached for 1 hour
    - Cache is invalidated when user data changes
    """
    
    def __init__(self, tax_config_or_db=None, db: Optional['Session'] = None):
        """
        Initialize the tax calculation engine.

        Accepts either:
          - A dict tax_config (legacy / test usage), with optional db session
          - A SQLAlchemy Session (convenience shortcut used by services)

        When a Session is passed as the first argument the engine loads the
        latest tax config from the database automatically.
        """
        from sqlalchemy.orm import Session as _Session

        # Detect whether the first arg is a DB session or a config dict
        if isinstance(tax_config_or_db, _Session):
            # Caller passed db as first positional arg
            self.db = tax_config_or_db
            tax_config = self._load_default_config_from_db(self.db)
        elif isinstance(tax_config_or_db, dict):
            tax_config = tax_config_or_db
            self.db = db
        elif tax_config_or_db is None:
            # No config and no db — use hardcoded 2026 fallback
            tax_config = self._get_hardcoded_fallback()
            self.db = db
        else:
            raise TypeError(
                f"Expected dict or Session, got {type(tax_config_or_db).__name__}"
            )

        self.tax_config = tax_config
        # Default calculators (from provided config, typically 2026)
        self.income_tax_calculator = IncomeTaxCalculator(tax_config)
        self.vat_calculator = VATCalculator(tax_config.get('vat_rates'))
        self.svs_calculator = SVSCalculator(tax_config.get('svs_rates'))
        self.deduction_calculator = DeductionCalculator(tax_config.get('deduction_config'))
        self.self_employed_config = SelfEmployedConfig.from_deduction_config(
            tax_config.get('deduction_config')
        )
        self._default_tax_year = tax_config.get('tax_year')
        self._cache: Dict[str, TaxBreakdown] = {}
        # Cache of year-specific calculator sets: {year: (income, vat, svs, deduction, se_config)}
        self._year_calculators: Dict[int, tuple] = {}

    @staticmethod
    def _load_default_config_from_db(db) -> Dict:
        """Load the most recent tax config from the database."""
        try:
            from app.models.tax_configuration import TaxConfiguration
            config_row = (
                db.query(TaxConfiguration)
                .order_by(TaxConfiguration.tax_year.desc())
                .first()
            )
            if config_row:
                return {
                    'tax_year': config_row.tax_year,
                    'tax_brackets': config_row.tax_brackets,
                    'exemption_amount': float(config_row.exemption_amount),
                    'vat_rates': config_row.vat_rates,
                    'svs_rates': config_row.svs_rates,
                    'deduction_config': config_row.deduction_config,
                }
        except Exception as e:
            logger.warning("Failed to load tax config from DB: %s", e)
        return TaxCalculationEngine._get_hardcoded_fallback()

    @staticmethod
    def _get_hardcoded_fallback() -> Dict:
        """Minimal 2026 fallback config when no DB is available."""
        return {
            'tax_year': 2026,
            'tax_brackets': [
                {"min": 0, "max": 12816, "rate": 0},
                {"min": 12816, "max": 20818, "rate": 20},
                {"min": 20818, "max": 34513, "rate": 30},
                {"min": 34513, "max": 66612, "rate": 40},
                {"min": 66612, "max": 99266, "rate": 48},
                {"min": 99266, "max": 1000000, "rate": 50},
                {"min": 1000000, "max": None, "rate": 55},
            ],
            'exemption_amount': 12816,
            'vat_rates': None,
            'svs_rates': None,
            'deduction_config': None,
        }

    def _get_calculators_for_year(self, tax_year: int) -> tuple:
        """
        Get year-specific calculators.

        Resolution order:
        1. Default year → pre-built calculators
        2. In-memory cache
        3. TaxConfiguration DB table (primary source of truth)
        4. Fallback to default calculators with warning

        Returns:
            Tuple of (income_tax_calc, vat_calc, svs_calc, deduction_calc, se_config)
        """
        # If this is the default year, use pre-built calculators
        if tax_year == self._default_tax_year:
            return (
                self.income_tax_calculator,
                self.vat_calculator,
                self.svs_calculator,
                self.deduction_calculator,
                self.self_employed_config,
            )

        # Check year calculator cache
        if tax_year in self._year_calculators:
            return self._year_calculators[tax_year]

        year_config = None

        # Load from database (the single source of truth)
        if self.db is not None:
            try:
                from app.models.tax_configuration import TaxConfiguration
                config_row = self.db.query(TaxConfiguration).filter(
                    TaxConfiguration.tax_year == tax_year
                ).first()
                if config_row:
                    year_config = {
                        'tax_brackets': config_row.tax_brackets,
                        'exemption_amount': float(config_row.exemption_amount),
                        'vat_rates': config_row.vat_rates,
                        'svs_rates': config_row.svs_rates,
                        'deduction_config': config_row.deduction_config,
                    }
            except Exception as e:
                logger.warning(
                    "Failed to load tax config for year %d from DB: %s", tax_year, e
                )

        if year_config is not None:
            calculators = (
                IncomeTaxCalculator(year_config),
                VATCalculator(year_config.get('vat_rates')),
                SVSCalculator(year_config.get('svs_rates')),
                DeductionCalculator(year_config.get('deduction_config')),
                SelfEmployedConfig.from_deduction_config(
                    year_config.get('deduction_config')
                ),
            )
            self._year_calculators[tax_year] = calculators
            logger.info("Using year-specific tax config for %d", tax_year)
            return calculators

        # Last resort: use default calculators with a warning
        logger.warning(
            "No tax config for year %d in database. "
            "Using default config (year %s). "
            "Add the year via admin API: POST /api/v1/tax-configs/",
            tax_year, self._default_tax_year,
        )
        return (
            self.income_tax_calculator,
            self.vat_calculator,
            self.svs_calculator,
            self.deduction_calculator,
            self.self_employed_config,
        )


    
    def _generate_cache_key(self, **kwargs) -> str:
        """Generate cache key from calculation parameters"""
        # Sort kwargs for consistent key generation
        sorted_items = sorted(kwargs.items())
        key_string = json.dumps(sorted_items, default=str)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[TaxBreakdown]:
        """Get calculation from in-memory cache"""
        return self._cache.get(cache_key)
    
    def _set_in_cache(self, cache_key: str, result: TaxBreakdown):
        """Store calculation in in-memory cache"""
        # Simple LRU: keep only last 1000 calculations
        if len(self._cache) > 1000:
            # Remove oldest 100 entries
            keys_to_remove = list(self._cache.keys())[:100]
            for key in keys_to_remove:
                del self._cache[key]
        
        self._cache[cache_key] = result
    
    def invalidate_cache(self):
        """Invalidate all cached calculations"""
        self._cache.clear()
    
    def calculate_total_tax(
        self,
        gross_income: Decimal,
        tax_year: int,
        user_type: UserType,
        user_id: Optional[int] = None,
        transactions: Optional[List[Transaction]] = None,
        gross_turnover: Optional[Decimal] = None,
        property_type: Optional[PropertyType] = None,
        commuting_distance_km: Optional[int] = None,
        public_transport_available: Optional[bool] = None,
        home_office_eligible: bool = False,
        family_info: Optional[FamilyInfo] = None,
        loss_carryforward_applied: Decimal = Decimal('0.00'),
        remaining_loss_balance: Decimal = Decimal('0.00'),
        expense_method: ExpenseMethod = ExpenseMethod.ACTUAL,
        profession_type: ProfessionType = ProfessionType.GENERAL,
        qualifying_investment: Decimal = Decimal('0.00'),
        capital_income_items: Optional[List[Dict]] = None,
        property_sale: Optional[Dict] = None,
        use_cache: bool = True
    ) -> TaxBreakdown:
        """
        Calculate total tax liability including income tax, VAT, and SVS.
        
        This is the main entry point for comprehensive tax calculation.
        
        Args:
            gross_income: Annual gross income
            tax_year: Tax year for calculation
            user_type: User type (EMPLOYEE, GSVG, NEUE_SELBSTAENDIGE)
            user_id: User ID for property calculations (optional)
            transactions: List of transactions for VAT calculation (optional)
            gross_turnover: Annual gross turnover for VAT (optional)
            property_type: Property type for rental income (optional)
            commuting_distance_km: Commuting distance for Pendlerpauschale (optional)
            public_transport_available: Public transport availability (optional)
            home_office_eligible: Whether eligible for home office deduction
            family_info: Family information for deductions (optional)
            loss_carryforward_applied: Amount of loss carryforward applied
            remaining_loss_balance: Remaining loss balance after application
            capital_income_items: List of capital income dicts for KESt (optional).
                Each dict: {description, income_type, gross_amount, withheld}
            property_sale: Dict with property sale data for ImmoESt (optional).
                Keys: sale_price, acquisition_cost, acquisition_date, improvement_costs,
                selling_costs, exemption, was_reclassified, reclassification_date, sale_date
            use_cache: Whether to use cached results (default: True)
            
        Returns:
            TaxBreakdown with all tax components and net income
        """
        # Generate cache key
        cache_params = {
            'gross_income': str(gross_income),
            'tax_year': tax_year,
            'user_type': user_type.value,
            'user_id': user_id,
            'gross_turnover': str(gross_turnover) if gross_turnover else None,
            'property_type': property_type.value if property_type else None,
            'commuting_distance_km': commuting_distance_km,
            'public_transport_available': public_transport_available,
            'home_office_eligible': home_office_eligible,
            'family_info': str(family_info) if family_info else None,
            'loss_carryforward_applied': str(loss_carryforward_applied),
            'remaining_loss_balance': str(remaining_loss_balance),
            'expense_method': expense_method.value,
            'profession_type': profession_type.value,
            'qualifying_investment': str(qualifying_investment),
            'capital_income_items': json.dumps(capital_income_items, default=str)
                if capital_income_items else None,
            'property_sale': json.dumps(property_sale, default=str)
                if property_sale else None,
        }
        cache_key = self._generate_cache_key(**cache_params)
        
        # Check cache
        if use_cache:
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
        
        # Ensure gross_income is Decimal
        if not isinstance(gross_income, Decimal):
            gross_income = Decimal(str(gross_income))
        
        # Load year-specific calculators
        (
            income_tax_calc,
            vat_calc,
            svs_calc,
            deduction_calc,
            se_config,
        ) = self._get_calculators_for_year(tax_year)

        # 1. Calculate deductions
        is_employee = user_type == UserType.EMPLOYEE
        deductions = deduction_calc.calculate_total_deductions(
            commuting_distance_km=commuting_distance_km,
            public_transport_available=public_transport_available,
            home_office_eligible=home_office_eligible,
            family_info=family_info,
            is_employee=is_employee
        )
        
        # 2. Calculate SVS contributions
        svs = svs_calc.calculate_contributions(
            annual_income=gross_income,
            user_type=user_type
        )
        
        # 3. Calculate income after deductions and SVS
        # SVS contributions are deductible as Sonderausgaben
        total_deductions = deductions.amount
        if svs.deductible:
            total_deductions += svs.annual_total
        
        # 3a. Add property-related deductions (if user_id and db provided)
        property_depreciation = Decimal('0.00')
        property_expenses = Decimal('0.00')
        rental_income = Decimal('0.00')
        property_warnings = []
        
        if user_id is not None and self.db is not None:
            # Calculate property depreciation (deductible expense) with warnings
            property_depreciation, property_warnings = self._calculate_property_depreciation(user_id, tax_year)
            total_deductions += property_depreciation
            
            # Calculate property expenses (deductible)
            property_expenses = self._calculate_property_expenses(user_id, tax_year)
            total_deductions += property_expenses
            
            # Calculate rental income (added to gross income)
            rental_income = self._calculate_rental_income(user_id, tax_year)
            gross_income = gross_income + rental_income
        
        taxable_income = gross_income - total_deductions
        
        # 3b. Apply Gewinnfreibetrag for self-employed (§10 EStG)
        gewinnfreibetrag_result = None
        basispauschalierung_result = None
        is_self_employed = user_type in (UserType.GSVG, UserType.NEUE_SELBSTAENDIGE)

        if is_self_employed and taxable_income > 0:
            if expense_method == ExpenseMethod.FLAT_RATE and gross_turnover is not None:
                # Basispauschalierung: flat-rate expenses replace actual expense tracking
                basispauschalierung_result = calculate_basispauschalierung(
                    gross_turnover=gross_turnover,
                    profession_type=profession_type,
                    svs_contributions=svs.annual_total if svs.deductible else Decimal('0.00'),
                    config=se_config,
                )
                if basispauschalierung_result.eligible:
                    # Override taxable income with flat-rate calculated profit
                    taxable_income = basispauschalierung_result.taxable_profit
                    # Grundfreibetrag is already included in basispauschalierung_result
                    gewinnfreibetrag_result = GewinnfreibetragResult(
                        grundfreibetrag=basispauschalierung_result.grundfreibetrag,
                        total_freibetrag=basispauschalierung_result.grundfreibetrag,
                        details="Nur Grundfreibetrag bei Basispauschalierung.",
                    )
            else:
                # Actual expense method: full Gewinnfreibetrag applies
                gewinnfreibetrag_result = calculate_gewinnfreibetrag(
                    profit=taxable_income,
                    qualifying_investment=qualifying_investment,
                    config=se_config,
                )
                taxable_income = taxable_income - gewinnfreibetrag_result.total_freibetrag
                taxable_income = max(taxable_income, Decimal('0.00'))
        
        # 4. Calculate income tax with loss carryforward
        income_tax = income_tax_calc.calculate_tax_with_loss_carryforward(
            gross_income=taxable_income,
            tax_year=tax_year,
            loss_carryforward_applied=loss_carryforward_applied,
            remaining_loss_balance=remaining_loss_balance
        )
        
        # 4b. Apply tax credits (Absetzbeträge) — deducted from tax liability
        tax_credits = Decimal('0.00')

        # Verkehrsabsetzbetrag for employees
        verkehrsabsetzbetrag = Decimal('0.00')
        if is_employee and 'verkehrsabsetzbetrag' in deductions.breakdown:
            verkehrsabsetzbetrag = Decimal(str(deductions.breakdown['verkehrsabsetzbetrag']))
            tax_credits += verkehrsabsetzbetrag

        # Familienbonus Plus
        familienbonus = Decimal('0.00')
        if 'familienbonus_amount' in deductions.breakdown:
            familienbonus = Decimal(str(deductions.breakdown['familienbonus_amount']))
            tax_credits += familienbonus

        # Alleinverdiener/Alleinerzieherabsetzbetrag
        alleinverdiener = Decimal('0.00')
        if 'alleinverdiener_amount' in deductions.breakdown:
            alleinverdiener = Decimal(str(deductions.breakdown['alleinverdiener_amount']))
            tax_credits += alleinverdiener

        # Apply all tax credits (cannot go below zero)
        if tax_credits > Decimal('0.00'):
            adjusted_tax = max(
                income_tax.total_tax - tax_credits, Decimal('0.00')
            )
            income_tax.total_tax = adjusted_tax.quantize(Decimal('0.01'))

        # 5. Calculate VAT (if applicable)
        if transactions is not None and gross_turnover is not None:
            vat = vat_calc.calculate_vat_liability(
                gross_turnover=gross_turnover,
                transactions=transactions,
                property_type=property_type
            )
        else:
            # No VAT liability if not provided
            vat = VATResult(exempt=True, reason="No transaction data provided")
        
        # 6. Calculate KESt (if capital income provided)
        kest_result = None
        if capital_income_items:
            kest_result = calculate_kest(capital_income_items)

        # 7. Calculate ImmoESt (if property sale provided)
        immoest_result = None
        if property_sale:
            from datetime import date as date_type
            ps = property_sale
            acq_date = ps.get('acquisition_date')
            if isinstance(acq_date, str):
                acq_date = date_type.fromisoformat(acq_date)
            recl_date = ps.get('reclassification_date')
            if isinstance(recl_date, str):
                recl_date = date_type.fromisoformat(recl_date)
            sale_dt = ps.get('sale_date')
            if isinstance(sale_dt, str):
                sale_dt = date_type.fromisoformat(sale_dt)
            immoest_result = calculate_immoest(
                sale_price=Decimal(str(ps.get('sale_price', 0))),
                acquisition_cost=Decimal(str(ps.get('acquisition_cost', 0))),
                acquisition_date=acq_date,
                improvement_costs=Decimal(str(ps.get('improvement_costs', 0))),
                selling_costs=Decimal(str(ps.get('selling_costs', 0))),
                exemption=ExemptionType(ps.get('exemption', 'none')),
                was_reclassified=bool(ps.get('was_reclassified', False)),
                reclassification_date=recl_date,
                sale_date=sale_dt,
            )

        # 8. Calculate total tax
        total_tax = income_tax.total_tax + svs.annual_total
        if not vat.exempt:
            total_tax += vat.net_vat
        if kest_result:
            total_tax += kest_result.remaining_tax_due
        if immoest_result and not immoest_result.exempt:
            total_tax += immoest_result.total_tax
        
        # 9. Calculate net income
        net_income = gross_income - total_tax
        
        # 10. Calculate effective tax rate
        effective_tax_rate = (total_tax / gross_income) if gross_income > 0 else Decimal('0.00')
        
        # 11. Add unsupported year warning if applicable
        supported = (
            get_supported_years_from_db(self.db)
            if self.db is not None
            else SUPPORTED_TAX_YEARS
        )
        if tax_year not in supported:
            property_warnings.append({
                "type": "unsupported_year",
                "message": (
                    f"Tax year {tax_year} is not officially supported. "
                    f"Supported years: {', '.join(str(y) for y in supported)}. "
                    f"Calculations use fallback rates and may be inaccurate."
                ),
            })
        
        result = TaxBreakdown(
            income_tax=income_tax,
            vat=vat,
            svs=svs,
            deductions=deductions,
            total_tax=total_tax.quantize(Decimal('0.01')),
            net_income=net_income.quantize(Decimal('0.01')),
            gross_income=gross_income,
            effective_tax_rate=effective_tax_rate.quantize(Decimal('0.0001')),
            warnings=property_warnings,
            gewinnfreibetrag=gewinnfreibetrag_result,
            basispauschalierung=basispauschalierung_result,
            kest=kest_result,
            immoest=immoest_result,
        )
        
        # Store in cache
        if use_cache:
            self._set_in_cache(cache_key, result)
        
        return result
    
    def calculate_net_income(
        self,
        gross_income: Decimal,
        tax_year: int,
        user_type: UserType,
        **kwargs
    ) -> Decimal:
        """
        Calculate net income after all taxes and contributions.
        
        This is a convenience method that returns only the net income.
        
        Args:
            gross_income: Annual gross income
            tax_year: Tax year for calculation
            user_type: User type
            **kwargs: Additional parameters for calculate_total_tax
            
        Returns:
            Net income (gross income - all taxes and contributions)
        """
        breakdown = self.calculate_total_tax(
            gross_income=gross_income,
            tax_year=tax_year,
            user_type=user_type,
            **kwargs
        )
        
        return breakdown.net_income
    
    def generate_tax_breakdown(
        self,
        gross_income: Decimal,
        tax_year: int,
        user_type: UserType,
        **kwargs
    ) -> Dict:
        """
        Generate a detailed tax breakdown as a dictionary.
        
        This method provides a structured breakdown suitable for API responses
        or report generation.
        
        Args:
            gross_income: Annual gross income
            tax_year: Tax year for calculation
            user_type: User type
            **kwargs: Additional parameters for calculate_total_tax
            
        Returns:
            Dictionary with detailed tax breakdown
        """
        breakdown = self.calculate_total_tax(
            gross_income=gross_income,
            tax_year=tax_year,
            user_type=user_type,
            **kwargs
        )
        
        # Build structured breakdown
        result = {
            'gross_income': float(breakdown.gross_income),
            'tax_year': tax_year,
            'user_type': user_type.value,
            
            # Deductions
            'deductions': {
                'total': float(breakdown.deductions.amount),
                'breakdown': self._format_deduction_breakdown(breakdown.deductions)
            },
            
            # Income tax
            'income_tax': {
                'total': float(breakdown.income_tax.total_tax),
                'taxable_income': float(breakdown.income_tax.taxable_income),
                'effective_rate': float(breakdown.income_tax.effective_rate),
                'brackets': [
                    {
                        'range': bracket.bracket_range,
                        'rate': bracket.rate,
                        'taxable_amount': float(bracket.taxable_amount),
                        'tax_amount': float(bracket.tax_amount)
                    }
                    for bracket in breakdown.income_tax.breakdown
                ]
            },
            
            # SVS contributions
            'svs': {
                'total_monthly': float(breakdown.svs.monthly_total),
                'total_annual': float(breakdown.svs.annual_total),
                'contribution_base': float(breakdown.svs.contribution_base),
                'deductible': breakdown.svs.deductible,
                'breakdown': {
                    key: float(value) 
                    for key, value in breakdown.svs.breakdown.items()
                },
                'note': breakdown.svs.note
            },
            
            # VAT
            'vat': {
                'exempt': breakdown.vat.exempt,
                'output_vat': float(breakdown.vat.output_vat),
                'input_vat': float(breakdown.vat.input_vat),
                'net_vat': float(breakdown.vat.net_vat),
                'reason': breakdown.vat.reason,
                'warning': breakdown.vat.warning
            },
            
            # Totals
            'total_tax': float(breakdown.total_tax),
            'net_income': float(breakdown.net_income),
            'effective_tax_rate': float(breakdown.effective_tax_rate),
            
            # Property tax warnings
            'warnings': breakdown.warnings if breakdown.warnings else []
        }
        
        # Add Gewinnfreibetrag info if applicable
        if breakdown.gewinnfreibetrag is not None:
            result['gewinnfreibetrag'] = {
                'grundfreibetrag': float(breakdown.gewinnfreibetrag.grundfreibetrag),
                'investment_freibetrag': float(breakdown.gewinnfreibetrag.investment_freibetrag),
                'total_freibetrag': float(breakdown.gewinnfreibetrag.total_freibetrag),
                'investment_required': float(breakdown.gewinnfreibetrag.investment_required),
                'investment_provided': float(breakdown.gewinnfreibetrag.investment_provided),
                'capped': breakdown.gewinnfreibetrag.capped,
                'details': breakdown.gewinnfreibetrag.details,
            }

        # Add Basispauschalierung info if applicable
        if breakdown.basispauschalierung is not None:
            result['basispauschalierung'] = {
                'eligible': breakdown.basispauschalierung.eligible,
                'flat_rate_expenses': float(breakdown.basispauschalierung.flat_rate_expenses),
                'flat_rate_pct': float(breakdown.basispauschalierung.flat_rate_pct),
                'turnover': float(breakdown.basispauschalierung.turnover),
                'estimated_profit': float(breakdown.basispauschalierung.estimated_profit),
                'grundfreibetrag': float(breakdown.basispauschalierung.grundfreibetrag),
                'taxable_profit': float(breakdown.basispauschalierung.taxable_profit),
                'reason': breakdown.basispauschalierung.reason,
                'note': breakdown.basispauschalierung.note,
            }
        
        # Add loss carryforward info if applicable
        if breakdown.income_tax.loss_carryforward_applied is not None:
            result['income_tax']['loss_carryforward_applied'] = float(
                breakdown.income_tax.loss_carryforward_applied
            )
            result['income_tax']['remaining_loss_balance'] = float(
                breakdown.income_tax.remaining_loss_balance
            )

        # Add KESt info if applicable
        if breakdown.kest is not None:
            result['kest'] = {
                'total_gross': float(breakdown.kest.total_gross),
                'total_tax': float(breakdown.kest.total_tax),
                'total_already_withheld': float(breakdown.kest.total_already_withheld),
                'remaining_tax_due': float(breakdown.kest.remaining_tax_due),
                'net_income': float(breakdown.kest.net_income),
                'note': breakdown.kest.note,
                'line_items': [
                    {
                        'description': li.description,
                        'income_type': li.income_type.value,
                        'gross_amount': float(li.gross_amount),
                        'rate': float(li.rate),
                        'tax_amount': float(li.tax_amount),
                        'withheld': li.withheld,
                    }
                    for li in breakdown.kest.line_items
                ],
            }

        # Add ImmoESt info if applicable
        if breakdown.immoest is not None:
            result['immoest'] = {
                'exempt': breakdown.immoest.exempt,
                'exemption_type': breakdown.immoest.exemption_type.value,
                'sale_price': float(breakdown.immoest.sale_price),
                'acquisition_cost': float(breakdown.immoest.acquisition_cost),
                'taxable_gain': float(breakdown.immoest.taxable_gain),
                'tax_rate': float(breakdown.immoest.tax_rate),
                'tax_amount': float(breakdown.immoest.tax_amount),
                'reclassification_surcharge': float(
                    breakdown.immoest.reclassification_surcharge
                ),
                'total_tax': float(breakdown.immoest.total_tax),
                'net_proceeds': float(breakdown.immoest.net_proceeds),
                'is_old_property': breakdown.immoest.is_old_property,
                'note': breakdown.immoest.note,
            }
        
        # Add property metrics if user_id provided
        user_id = kwargs.get('user_id')
        if user_id is not None and self.db is not None:
            property_depreciation, _ = self._calculate_property_depreciation(user_id, tax_year)
            property_expenses = self._calculate_property_expenses(user_id, tax_year)
            rental_income = self._calculate_rental_income(user_id, tax_year)
            
            result['property_metrics'] = {
                'rental_income': float(rental_income),
                'depreciation': float(property_depreciation),
                'expenses': float(property_expenses),
                'net_rental_income': float(rental_income - property_depreciation - property_expenses)
            }
        
        return result
    
    def _format_deduction_breakdown(self, deductions: DeductionResult) -> Dict:
        """
        Format deduction breakdown for API response.
        
        Args:
            deductions: DeductionResult object
            
        Returns:
            Formatted breakdown dictionary
        """
        formatted = {}
        
        # Commuting allowance
        if 'commuting_allowance' in deductions.breakdown:
            commuting = deductions.breakdown['commuting_allowance']
            formatted['commuting_allowance'] = {
                'type': commuting.get('type'),
                'distance_km': commuting.get('distance_km'),
                'distance_bracket': commuting.get('distance_bracket'),
                'base_annual': float(commuting.get('base_annual', 0)),
                'pendler_euro': float(commuting.get('pendler_euro', 0)),
                'total': float(deductions.breakdown.get('commuting_amount', 0))
            }
        
        # Home office
        if 'home_office' in deductions.breakdown:
            formatted['home_office'] = {
                'amount': float(deductions.breakdown.get('home_office_amount', 0))
            }
        
        # Family deductions
        if 'family_deductions' in deductions.breakdown:
            family = deductions.breakdown['family_deductions']
            formatted['family_deductions'] = {
                'child_deduction': float(family.get('child_deduction', 0)),
                'num_children': family.get('num_children', 0),
                'single_parent_deduction': float(family.get('single_parent_deduction', 0)),
                'is_single_parent': family.get('is_single_parent', False),
                'total': float(deductions.breakdown.get('family_amount', 0))
            }
        
        return formatted
    
    def calculate_quarterly_prepayment(
        self,
        gross_income: Decimal,
        tax_year: int,
        user_type: UserType,
        **kwargs
    ) -> Dict[str, Decimal]:
        """
        Calculate quarterly prepayment amounts for income tax and SVS.
        
        Args:
            gross_income: Estimated annual gross income
            tax_year: Tax year
            user_type: User type
            **kwargs: Additional parameters for tax calculation
            
        Returns:
            Dictionary with quarterly prepayment amounts
        """
        # Calculate total tax
        breakdown = self.calculate_total_tax(
            gross_income=gross_income,
            tax_year=tax_year,
            user_type=user_type,
            **kwargs
        )
        
        # Quarterly income tax prepayment
        quarterly_income_tax = breakdown.income_tax.total_tax / Decimal('4')
        
        # Quarterly SVS prepayment
        quarterly_svs = breakdown.svs.annual_total / Decimal('4')
        
        # Total quarterly prepayment
        total_quarterly = quarterly_income_tax + quarterly_svs
        
        return {
            'income_tax': quarterly_income_tax.quantize(Decimal('0.01')),
            'svs': quarterly_svs.quantize(Decimal('0.01')),
            'total': total_quarterly.quantize(Decimal('0.01'))
        }
    
    def _calculate_property_depreciation(self, user_id: int, year: int) -> tuple[Decimal, List[Dict]]:
        """
        Calculate depreciation for all user properties and collect warnings.
        
        Args:
            user_id: User ID
            year: Tax year
            
        Returns:
            Tuple of (total_depreciation, warnings_list)
        """
        from app.models.property import Property
        from app.services.afa_calculator import AfACalculator
        
        # Get all active properties for user
        properties = self.db.query(Property).filter(
            Property.user_id == user_id,
            Property.status == 'active'
        ).all()
        
        if not properties:
            return Decimal("0"), []
        
        # Calculate depreciation with warnings
        afa_calculator = AfACalculator(db=self.db)
        total_depreciation = Decimal("0")
        
        for property in properties:
            depreciation = afa_calculator.calculate_annual_depreciation(property, year)
            total_depreciation += depreciation
        
        # Get all warnings
        warnings = afa_calculator.get_warnings()
        
        return total_depreciation, warnings
    
    def _calculate_rental_income(self, user_id: int, year: int) -> Decimal:
        """
        Sum all rental income transactions in year.
        
        Args:
            user_id: User ID
            year: Tax year
            
        Returns:
            Total rental income for the year
        """
        from sqlalchemy import func, extract
        from app.models.transaction import Transaction, TransactionType, IncomeCategory
        
        total = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.INCOME,
            Transaction.income_category == IncomeCategory.RENTAL,
            extract('year', Transaction.transaction_date) == year
        ).scalar()
        
        return total or Decimal("0")
    
    def _calculate_property_expenses(self, user_id: int, year: int) -> Decimal:
        """
        Sum all property-related expenses (excluding depreciation).
        
        Only includes expenses that are linked to a property (property_id is not None).
        
        Args:
            user_id: User ID
            year: Tax year
            
        Returns:
            Total property expenses for the year
        """
        from sqlalchemy import func, extract
        from app.models.transaction import Transaction, TransactionType, ExpenseCategory
        
        property_expense_categories = [
            ExpenseCategory.LOAN_INTEREST,
            ExpenseCategory.MAINTENANCE,
            ExpenseCategory.PROPERTY_MANAGEMENT_FEES,
            ExpenseCategory.PROPERTY_INSURANCE,
            ExpenseCategory.PROPERTY_TAX,
            ExpenseCategory.UTILITIES
        ]
        
        total = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.expense_category.in_(property_expense_categories),
            Transaction.property_id.isnot(None),
            extract('year', Transaction.transaction_date) == year
        ).scalar()
        
        return total or Decimal("0")
