"""
AfA (Absetzung für Abnutzung) Calculator Service

Calculates depreciation for rental properties according to Austrian tax law.

Austrian Tax Law Rules (current, since 1. StRefG 2015/2016):
- Residential buildings (Wohngebäude): 1.5% annual depreciation (§16 Abs 1 Z 8 EStG)
- Commercial buildings (Betriebsgebäude): 2.5% annual depreciation (§8 Abs 1 EStG)
- Accelerated depreciation (beschleunigte AfA, §8 Abs 1a EStG / KonStG 2020):
  - Buildings completed after 30.06.2020
  - Year 1: 3× rate (residential: 4.5%, commercial: 7.5%)
  - Year 2: 2× rate (residential: 3.0%, commercial: 5.0%)
  - Year 3+: normal rate
- Extended eco acceleration (BMF erweiterte beschleunigte AfA):
  - Residential buildings completed 2024-2026 meeting klimaaktiv standard
  - Years 1-3: all 3× rate (4.5%), then normal 1.5%
- Only building value is depreciable (not land)
- Pro-rated for partial year ownership
- Stops when accumulated depreciation reaches building value
- Mixed-use properties: only rental percentage is depreciable

Note: The old pre-1915 vs post-1915 distinction was replaced by the 2016 reform.
All residential rental buildings now uniformly use 1.5%.

Note: Halbjahresregel (§7 Abs 2 EStG) for movable assets is implemented in
  AssetLifecycleService._is_half_year_start() — H2 acquisitions get 50% Y1 AfA.
  GWG immediate write-off (≤€800 pre-2023, ≤€1,000 2023+) is also handled there.
  This file delegates non-real-estate assets to AssetLifecycleService at line ~274.
"""

from decimal import Decimal
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models.property import Property, PropertyType, BuildingUse
from app.models.transaction import Transaction, IncomeCategory
from app.services.asset_lifecycle_service import AssetLifecycleService
from app.services.property_error_integration import track_depreciation_errors
import logging

logger = logging.getLogger(__name__)


class AfACalculator:
    """
    Calculates depreciation (Absetzung für Abnutzung) for rental properties.
    
    All calculations use Decimal for precision and round to 2 decimal places.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize AfA calculator.
        
        Args:
            db: SQLAlchemy database session (required for accumulated depreciation queries)
        """
        self.db = db
        self.warnings = []  # Store warnings for tax report
    
    # Standard AfA rates (since 1. StRefG 2015/2016)
    RESIDENTIAL_RATE = Decimal("0.015")  # 1.5% — Wohngebäude (§16 Abs 1 Z 8 / §8 Abs 1 EStG)
    COMMERCIAL_RATE = Decimal("0.025")   # 2.5% — Betriebsgebäude (§8 Abs 1 EStG)

    # Accelerated depreciation (§8 Abs 1a EStG, KonStG 2020)
    # Buildings completed after 30.06.2020:
    #   Year 1 (erstmalige Berücksichtigung): 3× base rate
    #   Year 2 (darauffolgendes Jahr): 2× base rate
    #   Year 3+: normal base rate
    ACCELERATED_YEAR1_MULTIPLIER = Decimal("3")  # dreifacher Betrag
    ACCELERATED_YEAR2_MULTIPLIER = Decimal("2")  # zweifacher Betrag
    ACCELERATED_CUTOFF_YEAR = 2020  # construction_year > 2020 qualifies (simplified)

    def determine_depreciation_rate(
        self,
        construction_year: Optional[int] = None,
        is_commercial: bool = False,
    ) -> Decimal:
        """
        Determine base depreciation rate per Austrian tax law (since 2016 reform).

        The old pre-1915 vs post-1915 distinction no longer applies.
        The rate depends on building usage type:
        - Residential (Wohngebäude): 1.5%
        - Commercial (Betriebsgebäude): 2.5%

        Args:
            construction_year: Year the building was constructed (used for accelerated AfA check)
            is_commercial: True for commercial buildings (Betriebsgebäude)

        Returns:
            Decimal base depreciation rate (before accelerated AfA adjustment)
        """
        if is_commercial:
            return self.COMMERCIAL_RATE
        return self.RESIDENTIAL_RATE

    def get_effective_rate(
        self,
        base_rate: Decimal,
        construction_year: Optional[int],
        ownership_year: int,
        purchase_year: int,
        is_residential: bool = True,
        eco_standard: bool = False,
    ) -> Decimal:
        """
        Get effective depreciation rate, applying accelerated AfA if eligible.

        General accelerated AfA (§8 Abs 1a EStG / KonStG 2020):
        - Applies to buildings completed after 30.06.2020
        - Year 1 (erstmalige Berücksichtigung): 3× base rate
        - Year 2 (darauffolgendes Jahr): 2× base rate
        - Year 3+: normal base rate

        Extended eco-standard acceleration (BMF erweiterte beschleunigte AfA):
        - Only for NEW RESIDENTIAL buildings completed 2024-01-01 to 2026-12-31
        - Must meet eco/klimaaktiv standard
        - Years 1-3: all 3× base rate (4.5% for residential)

        Examples (general, residential 1.5%):
          Year 1: 4.5%, Year 2: 3.0%, Year 3+: 1.5%
        Examples (eco residential 2024-2026):
          Year 1: 4.5%, Year 2: 4.5%, Year 3: 4.5%, Year 4+: 1.5%

        Args:
            base_rate: Base depreciation rate (0.015 or 0.025)
            construction_year: Year the building was constructed/completed
            ownership_year: The tax year being calculated
            purchase_year: Year the property was purchased
            is_residential: True for Wohngebäude
            eco_standard: True if building meets eco/klimaaktiv standard

        Returns:
            Effective rate with applicable acceleration
        """
        if not construction_year or construction_year <= self.ACCELERATED_CUTOFF_YEAR:
            return base_rate

        # Building qualifies for accelerated AfA
        depreciation_year_number = ownership_year - purchase_year + 1

        # Check for extended eco-standard acceleration (residential, 2024-2026, klimaaktiv)
        eco_extended = (
            is_residential
            and eco_standard
            and 2024 <= construction_year <= 2026
        )

        if depreciation_year_number == 1:
            # Year 1: dreifacher Betrag (3×) — both general and eco
            return (base_rate * self.ACCELERATED_YEAR1_MULTIPLIER).quantize(Decimal("0.0001"))
        elif depreciation_year_number == 2:
            if eco_extended:
                # Eco: Year 2 still 3×
                return (base_rate * self.ACCELERATED_YEAR1_MULTIPLIER).quantize(Decimal("0.0001"))
            # General: Year 2 = 2×
            return (base_rate * self.ACCELERATED_YEAR2_MULTIPLIER).quantize(Decimal("0.0001"))
        elif depreciation_year_number == 3 and eco_extended:
            # Eco: Year 3 still 3×
            return (base_rate * self.ACCELERATED_YEAR1_MULTIPLIER).quantize(Decimal("0.0001"))

        return base_rate
    
    def _get_rental_percentage_for_year(
        self, property_id, year: int
    ) -> Decimal:
        """
        Determine the effective rental percentage for a property in a specific year
        by checking historical rental contracts (recurring_transactions).

        This allows correct AfA calculation even when the current property_type
        is owner_occupied but the property was rented in past years.

        Args:
            property_id: UUID of the property
            year: Tax year to check

        Returns:
            Decimal rental percentage (0-100) for that year
        """
        if self.db is None:
            return Decimal("0")

        from app.models.recurring_transaction import (
            RecurringTransaction,
            RecurringTransactionType,
        )

        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)

        # Find rental contracts that overlap with this year
        # A contract overlaps if: start_date <= year_end AND (end_date IS NULL OR end_date >= year_start)
        contracts = (
            self.db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.property_id == property_id,
                RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
                RecurringTransaction.start_date <= year_end,
            )
            .filter(
                (RecurringTransaction.end_date == None) |  # noqa: E711
                (RecurringTransaction.end_date >= year_start)
            )
            .all()
        )

        if not contracts:
            return Decimal("0")

        total_pct = sum(
            float(c.unit_percentage or 100) for c in contracts
        )
        return Decimal(str(min(total_pct, 100)))

    def _resolve_real_estate_rental_percentage_for_year(
        self,
        property: Property,
        year: int,
    ) -> Decimal:
        """
        Resolve the effective rental percentage for real-estate AfA.

        Prefer historical contract coverage when available, but fall back to the
        property's current rental state for legacy records that do not yet have
        recurring rental contracts.
        """
        historical_rental_pct = Decimal("0")
        if self.db is not None:
            historical_rental_pct = self._get_rental_percentage_for_year(
                property.id,
                year,
            )
            if historical_rental_pct > 0:
                return historical_rental_pct

        if property.property_type == PropertyType.OWNER_OCCUPIED:
            return Decimal("0")

        fallback_pct = getattr(property, "rental_percentage", None)
        if fallback_pct is None:
            return Decimal("100")

        return Decimal(str(fallback_pct))

    @track_depreciation_errors
    def calculate_annual_depreciation(
        self, 
        property: Property, 
        year: int
    ) -> Decimal:
        """
        Calculate annual depreciation for a property in a given year.
        
        Handles:
        - Full year depreciation
        - Pro-rated first year (based on purchase month)
        - Pro-rated last year (if sold mid-year)
        - Building value limit (stops when fully depreciated)
        - Mixed-use properties (only rental percentage)
        - Owner-occupied properties (no depreciation)
        - Historical rental periods (checks contracts per year, not current property_type)
        
        Args:
            property: Property model instance
            year: Tax year to calculate depreciation for
            
        Returns:
            Decimal amount rounded to 2 decimal places
        """
        asset_type = getattr(property, 'asset_type', 'real_estate')
        if asset_type != 'real_estate':
            if self.db is None:
                raise ValueError("Database session required for accumulated depreciation calculation")
            lifecycle_service = AssetLifecycleService(self.db)
            return lifecycle_service.calculate_annual_depreciation(property, year)

        if not getattr(property, "building_value", None):
            return Decimal("0")

        # For real estate: determine rental percentage from historical contracts
        # This correctly handles properties that were rented in the past but are now owner_occupied
        if asset_type == 'real_estate' and self.db is not None:
            historical_rental_pct = self._resolve_real_estate_rental_percentage_for_year(
                property,
                year,
            )
            if historical_rental_pct <= 0:
                # No effective rental usage in this year → no depreciation
                return Decimal("0")
        else:
            # Non-real-estate or no DB: fall back to current property_type
            if property.property_type == PropertyType.OWNER_OCCUPIED:
                return Decimal("0")
            historical_rental_pct = None
        
        # Check for rental income (warn if rental property has no income)
        if historical_rental_pct and historical_rental_pct >= 100 and asset_type == 'real_estate':
            self._check_rental_income_warning(property, year)
        
        # Check if property was owned during this year
        if year < property.purchase_date.year:
            return Decimal("0")
        
        if property.sale_date and year > property.sale_date.year:
            return Decimal("0")
        
        # Get accumulated depreciation up to previous year
        if self.db is None:
            raise ValueError("Database session required for accumulated depreciation calculation")
        
        accumulated = self.get_accumulated_depreciation(property.id, year - 1)
        
        # Calculate depreciable value using historical rental percentage
        depreciable_value = property.building_value
        if historical_rental_pct is not None:
            # Use historical rental percentage from contracts
            if historical_rental_pct < Decimal("100"):
                rental_pct = historical_rental_pct / Decimal("100")
                depreciable_value = depreciable_value * rental_pct
        elif getattr(property, 'asset_type', 'real_estate') != 'real_estate':
            # Non-real-estate assets: apply business_use_percentage
            biz_pct = getattr(property, 'business_use_percentage', None)
            if biz_pct is not None and biz_pct < Decimal("100"):
                depreciable_value = depreciable_value * (biz_pct / Decimal("100"))
        
        # Check if already fully depreciated
        if accumulated >= depreciable_value:
            return Decimal("0")
        
        # Calculate effective depreciation rate
        # For real estate: use building_use to determine residential/commercial rate
        # For non-real-estate assets: use stored property.depreciation_rate
        asset_type = getattr(property, 'asset_type', 'real_estate')
        if asset_type == 'real_estate':
            building_use = getattr(property, 'building_use', BuildingUse.RESIDENTIAL)
            is_commercial = (building_use == BuildingUse.COMMERCIAL)
            is_residential = not is_commercial
            eco_standard = getattr(property, 'eco_standard', False)

            base_rate = self.determine_depreciation_rate(
                construction_year=property.construction_year,
                is_commercial=is_commercial,
            )
            effective_rate = self.get_effective_rate(
                base_rate=base_rate,
                construction_year=property.construction_year,
                ownership_year=year,
                purchase_year=property.purchase_date.year,
                is_residential=is_residential,
                eco_standard=eco_standard,
            )
        else:
            effective_rate = property.depreciation_rate

        # Calculate base annual depreciation
        annual_amount = depreciable_value * effective_rate
        
        # Pro-rate for partial year
        months_owned = self._calculate_months_owned(property, year)
        if months_owned < 12:
            annual_amount = (annual_amount * months_owned) / 12
        
        # Ensure we don't exceed building value
        remaining = depreciable_value - accumulated
        final_amount = min(annual_amount, remaining)
        
        return final_amount.quantize(Decimal("0.01"))
    
    def calculate_prorated_depreciation(
        self, 
        property: Property,
        months_owned: int
    ) -> Decimal:
        """
        Calculate pro-rated depreciation for partial year ownership.
        
        Args:
            property: Property model instance
            months_owned: Number of months owned in the year (1-12)
            
        Returns:
            Decimal amount rounded to 2 decimal places
        """
        # Owner-occupied properties are not depreciable
        if property.property_type == PropertyType.OWNER_OCCUPIED:
            return Decimal("0")
        
        # Calculate depreciable value (considering rental percentage for mixed-use)
        depreciable_value = property.building_value
        if property.property_type == PropertyType.MIXED_USE:
            rental_pct = property.rental_percentage / Decimal("100")
            depreciable_value = depreciable_value * rental_pct
        
        # Calculate annual depreciation
        annual = depreciable_value * property.depreciation_rate
        
        # Pro-rate for months owned
        prorated = (annual * months_owned) / 12
        
        return prorated.quantize(Decimal("0.01"))
    
    def get_accumulated_depreciation(
        self,
        property_id,
        up_to_year: Optional[int] = None
    ) -> Decimal:
        """
        Calculate total accumulated depreciation for a property up to a given year.

        Computes mathematically from property data (purchase_date, building_value,
        depreciation_rate) instead of querying transaction records.

        Args:
            property_id: UUID of the property
            up_to_year: Optional year limit (inclusive). If None, calculates up to current year.

        Returns:
            Decimal total accumulated depreciation
        """
        if self.db is None:
            raise ValueError("Database session required for accumulated depreciation calculation")

        prop = self.db.query(Property).filter(Property.id == property_id).first()
        if not prop:
            return Decimal("0")

        if not prop.building_value or not prop.depreciation_rate:
            return Decimal("0")

        asset_type = getattr(prop, 'asset_type', 'real_estate')
        if asset_type != 'real_estate':
            lifecycle_service = AssetLifecycleService(self.db)
            return lifecycle_service.calculate_accumulated_depreciation(prop, up_to_year)

        purchase_year = prop.purchase_date.year
        end_year = up_to_year if up_to_year else date.today().year

        if end_year < purchase_year:
            return Decimal("0")

        accumulated = Decimal("0")

        # Determine base rate for this property
        if asset_type == 'real_estate':
            building_use = getattr(prop, 'building_use', BuildingUse.RESIDENTIAL)
            is_commercial = (building_use == BuildingUse.COMMERCIAL)
            is_residential = not is_commercial
            eco_standard = getattr(prop, 'eco_standard', False)

            base_rate = self.determine_depreciation_rate(
                construction_year=prop.construction_year,
                is_commercial=is_commercial,
            )
        else:
            # Non-real-estate: check current property_type
            if prop.property_type == PropertyType.OWNER_OCCUPIED:
                return Decimal("0")
            base_rate = prop.depreciation_rate
            is_residential = True
            eco_standard = False

        for yr in range(purchase_year, end_year + 1):
            # Skip years after sale
            if prop.sale_date and yr > prop.sale_date.year:
                break

            # For real estate: determine rental percentage from historical contracts
            if asset_type == 'real_estate':
                historical_rental_pct = self._resolve_real_estate_rental_percentage_for_year(
                    prop,
                    yr,
                )
                if historical_rental_pct <= 0:
                    continue  # No rental in this year, no depreciation

                depreciable_value = prop.building_value
                if historical_rental_pct < Decimal("100"):
                    depreciable_value = depreciable_value * (historical_rental_pct / Decimal("100"))
            else:
                depreciable_value = prop.building_value
                biz_pct = getattr(prop, 'business_use_percentage', None)
                if biz_pct is not None and biz_pct < Decimal("100"):
                    depreciable_value = depreciable_value * (biz_pct / Decimal("100"))

            # Get effective rate (handles accelerated AfA per year)
            if asset_type == 'real_estate':
                effective_rate = self.get_effective_rate(
                    base_rate=base_rate,
                    construction_year=prop.construction_year,
                    ownership_year=yr,
                    purchase_year=purchase_year,
                    is_residential=is_residential,
                    eco_standard=eco_standard,
                )
            else:
                effective_rate = base_rate

            annual_amount = depreciable_value * effective_rate

            # Pro-rate for partial year
            months = self._calculate_months_owned(prop, yr)
            if months < 12:
                yr_amount = (annual_amount * months) / 12
            else:
                yr_amount = annual_amount

            # Don't exceed building value
            remaining = depreciable_value - accumulated
            if remaining <= Decimal("0"):
                break
            yr_amount = min(yr_amount, remaining)

            accumulated += yr_amount.quantize(Decimal("0.01"))

        return accumulated

    
    def _calculate_months_owned(self, property: Property, year: int) -> int:
        """
        Calculate number of months property was owned in given year.
        
        Args:
            property: Property model instance
            year: Tax year
            
        Returns:
            Number of months (1-12)
        """
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        
        # Determine ownership period within the year
        ownership_start = max(property.purchase_date, year_start)
        ownership_end = min(property.sale_date or year_end, year_end)
        
        # Calculate months (inclusive)
        months = (ownership_end.year - ownership_start.year) * 12
        months += ownership_end.month - ownership_start.month + 1
        
        return min(months, 12)
    
    def _get_rental_income_for_year(self, property_id, year: int) -> Decimal:
        """
        Get total rental income for a property in a given year.
        
        Args:
            property_id: UUID of the property
            year: Tax year
            
        Returns:
            Decimal total rental income
        """
        if self.db is None:
            return Decimal("0")
        
        result = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.property_id == property_id,
            Transaction.income_category == IncomeCategory.RENTAL,
            extract('year', Transaction.transaction_date) == year
        ).scalar()
        
        return result or Decimal("0")
    
    def _check_rental_income_warning(self, property: Property, year: int) -> None:
        """
        Check if rental property has rental income and add warning if not.
        
        Args:
            property: Property model instance
            year: Tax year
        """
        rental_income = self._get_rental_income_for_year(property.id, year)
        
        if rental_income == 0:
            # Calculate months since purchase
            year_start = date(year, 1, 1)
            ownership_start = max(property.purchase_date, year_start)
            months_since_purchase = (date(year, 12, 31).year - ownership_start.year) * 12
            months_since_purchase += date(year, 12, 31).month - ownership_start.month + 1
            
            # Add appropriate warning based on vacancy duration
            addr = property.address
            mo = months_since_purchase

            if mo <= 6:
                warning_level = "info"
                messages = {
                    "de": (
                        f"Keine Mieteinnahmen fuer {addr} im Jahr {year}. "
                        f"Leerstandsphase: {mo} Monate. "
                        f"Dokumentieren Sie Ihre Vermietungsbemuehungen (Inserate, Besichtigungen)."
                    ),
                    "en": (
                        f"No rental income for {addr} in {year}. "
                        f"Vacancy period: {mo} months. "
                        f"Document your rental efforts (listings, viewings)."
                    ),
                    "zh": (
                        f"{addr} 在 {year} 年无租金收入。"
                        f"空置期：{mo} 个月。"
                        f"请记录您的出租努力（广告、看房）。"
                    ),
                    "fr": (
                        f"Aucun revenu locatif pour {addr} en {year}. "
                        f"Periode de vacance : {mo} mois. "
                        f"Documentez vos efforts de location (annonces, visites)."
                    ),
                    "ru": (
                        f"Нет арендного дохода для {addr} за {year} год. "
                        f"Период простоя: {mo} месяцев. "
                        f"Документируйте ваши усилия по сдаче в аренду (объявления, показы)."
                    ),
                    "hu": (
                        f"Nincs berletidij-bevetel a(z) {addr} cimre {year}-ben. "
                        f"Uresedesi idoszak: {mo} honap. "
                        f"Dokumentalja berbeadasi erofesziteseit (hirdetesek, megtekintesek)."
                    ),
                    "pl": (
                        f"Brak dochodu z wynajmu dla {addr} w {year}. "
                        f"Okres pustostanu: {mo} miesiecy. "
                        f"Udokumentuj swoje starania o wynajem (ogloszenia, ogl. nieruchomosci)."
                    ),
                    "tr": (
                        f"{addr} icin {year} yilinda kira geliri yok. "
                        f"Bos kalma suresi: {mo} ay. "
                        f"Kiralama cabanizi belgeleyin (ilanlar, gosterimler)."
                    ),
                    "bs": (
                        f"Nema prihoda od najma za {addr} u {year}. "
                        f"Period praznog stanja: {mo} mjeseci. "
                        f"Dokumentujte vase napore za iznajmljivanje (oglasi, razgledanja)."
                    ),
                }
            elif mo <= 12:
                warning_level = "warning"
                messages = {
                    "de": (
                        f"Laengere Leerstandsphase fuer {addr}: {mo} Monate ohne Mieteinnahmen. "
                        f"Das Finanzamt koennte die Vermietungsabsicht anzweifeln. "
                        f"Dokumentieren Sie: Inserate, Besichtigungen, Ablehnungsgruende."
                    ),
                    "en": (
                        f"Extended vacancy for {addr}: {mo} months without rental income. "
                        f"Tax office may question rental intent. "
                        f"Document: Listings, viewings, rejection reasons."
                    ),
                    "zh": (
                        f"{addr} 长期空置：{mo} 个月无租金收入。"
                        f"税务局可能质疑出租意图。"
                        f"请记录：广告、看房、拒绝原因。"
                    ),
                    "fr": (
                        f"Vacance prolongee pour {addr} : {mo} mois sans revenu locatif. "
                        f"Le fisc pourrait remettre en question l'intention de location. "
                        f"Documentez : annonces, visites, motifs de refus."
                    ),
                    "ru": (
                        f"Длительный простой для {addr}: {mo} месяцев без арендного дохода. "
                        f"Налоговая может поставить под сомнение намерение сдавать в аренду. "
                        f"Документируйте: объявления, показы, причины отказов."
                    ),
                    "hu": (
                        f"Hosszabb uresedesi idoszak a(z) {addr} cimnel: {mo} honap berletidij-bevetel nelkul. "
                        f"Az adohivatal megkerdojelezheti a berbeadasi szandekot. "
                        f"Dokumentalja: hirdetesek, megtekintesek, elutasitasi okok."
                    ),
                    "pl": (
                        f"Dlugi okres pustostanu dla {addr}: {mo} miesiecy bez dochodu z wynajmu. "
                        f"Urzad skarbowy moze zakwestionowac zamiar wynajmu. "
                        f"Udokumentuj: ogloszenia, prezentacje, powody odmow."
                    ),
                    "tr": (
                        f"{addr} icin uzun sureli bos kalma: {mo} ay kira geliri yok. "
                        f"Vergi dairesi kiralama niyetini sorgulayabilir. "
                        f"Belgeleyin: ilanlar, gosterimler, ret nedenleri."
                    ),
                    "bs": (
                        f"Produzeni period praznog stanja za {addr}: {mo} mjeseci bez prihoda od najma. "
                        f"Porezna uprava moze dovesti u pitanje namjeru iznajmljivanja. "
                        f"Dokumentujte: oglase, razgledanja, razloge odbijanja."
                    ),
                }
            else:
                warning_level = "error"
                messages = {
                    "de": (
                        f"ACHTUNG: {addr} hat seit ueber 12 Monaten keine Mieteinnahmen! "
                        f"Das Finanzamt wird die Vermietungsabsicht stark anzweifeln. "
                        f"Ihr AfA-Abzug ist gefaehrdet! "
                        f"Erwaegen Sie, die Immobilie als 'Eigengenutzt' umzuklassifizieren."
                    ),
                    "en": (
                        f"WARNING: {addr} has no rental income for over 12 months! "
                        f"Tax office will strongly question rental intent. "
                        f"Your depreciation deduction is at risk! "
                        f"Consider reclassifying the property as 'Owner-Occupied'."
                    ),
                    "zh": (
                        f"警告：{addr} 超过12个月无租金收入！"
                        f"税务局将强烈质疑出租意图。"
                        f"您的折旧抵扣有风险！"
                        f"考虑将房产重新分类为'自住'。"
                    ),
                    "fr": (
                        f"ATTENTION : {addr} n'a aucun revenu locatif depuis plus de 12 mois ! "
                        f"Le fisc remettra fortement en question l'intention de location. "
                        f"Votre deduction d'amortissement est en danger ! "
                        f"Envisagez de reclasser le bien comme 'Usage personnel'."
                    ),
                    "ru": (
                        f"ВНИМАНИЕ: {addr} не имеет арендного дохода более 12 месяцев! "
                        f"Налоговая будет серьезно сомневаться в намерении сдавать в аренду. "
                        f"Ваш вычет на амортизацию под угрозой! "
                        f"Рассмотрите переклассификацию недвижимости как 'Для собственного использования'."
                    ),
                    "hu": (
                        f"FIGYELEM: A(z) {addr} cimnek tobb mint 12 honapja nincs berletidij-bevetele! "
                        f"Az adohivatal erossen megkerdojelezi a berbeadasi szandekot. "
                        f"Az ertekcsokkenesi levonasa veszelyben van! "
                        f"Fontolja meg az ingatlan 'Sajat hasznalatu'-kent valo atkategorizalasat."
                    ),
                    "pl": (
                        f"UWAGA: {addr} nie ma dochodu z wynajmu od ponad 12 miesiecy! "
                        f"Urzad skarbowy bedzie mocno kwestionowal zamiar wynajmu. "
                        f"Twoje odliczenie amortyzacyjne jest zagrozone! "
                        f"Rozwaz przeklasyfikowanie nieruchomosci jako 'Do uzytku wlasnego'."
                    ),
                    "tr": (
                        f"DIKKAT: {addr} 12 aydan fazla suredir kira geliri yok! "
                        f"Vergi dairesi kiralama niyetini ciddi sekilde sorgulayacaktir. "
                        f"Amortisman kesintiniz risk altinda! "
                        f"Mulku 'Sahsi kullanim' olarak yeniden siniflandirmayi dusunun."
                    ),
                    "bs": (
                        f"UPOZORENJE: {addr} nema prihoda od najma vise od 12 mjeseci! "
                        f"Porezna uprava ce ozbiljno dovesti u pitanje namjeru iznajmljivanja. "
                        f"Vas odbitak za amortizaciju je u opasnosti! "
                        f"Razmotrite preklasifikaciju nekretnine kao 'Za vlastitu upotrebu'."
                    ),
                }

            self.warnings.append({
                "property_id": str(property.id),
                "property_address": property.address,
                "year": year,
                "level": warning_level,
                "type": "NO_RENTAL_INCOME",
                "months_vacant": months_since_purchase,
                **{f"message_{lang}": msg for lang, msg in messages.items()},
            })
            
            logger.warning(
                f"Property {property.id} ({property.address}) has no rental income in {year}. "
                f"Vacancy: {months_since_purchase} months. Level: {warning_level}"
            )
    
    def get_warnings(self) -> list:
        """
        Get all warnings generated during depreciation calculations.
        
        Returns:
            List of warning dictionaries
        """
        return self.warnings
    
    def clear_warnings(self) -> None:
        """Clear all warnings."""
        self.warnings = []
