"""VAT calculator for Austrian VAT system (Umsatzsteuer)

Austrian VAT rates (2025/2026):
- Standard rate: 20%
- Reduced rate 10%: residential rental, accommodation (Beherbergung),
  food/groceries, books/newspapers, public transport, camping
- Reduced rate 13%: live animals/plants, firewood, artist activities,
  film/circus performances, sporting event admissions

Kleinunternehmerregelung (small business exemption):
- Threshold: EUR 55,000 gross turnover (since 2025-01-01, previously EUR 35,000)
- Tolerance: EUR 63,250 (15% overshoot allowed once)

Source: https://www.usp.gv.at/en/themen/steuern-finanzen/umsatzsteuer-ueberblick/
"""
from decimal import Decimal
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class PropertyType(Enum):
    """Property type for rental income"""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"


class VATRateType(Enum):
    """Austrian VAT rate categories"""
    STANDARD = "standard"          # 20%
    REDUCED_10 = "reduced_10"      # 10%
    REDUCED_13 = "reduced_13"      # 13%
    REDUCED_5 = "reduced_5"        # 5% (essential foods, since 2024)
    ZERO_RATED = "zero_rated"      # 0% (menstrual products, contraceptives)
    EXEMPT = "exempt"              # 0% (Kleinunternehmer or genuine exemption)


@dataclass
class Transaction:
    """Transaction data for VAT calculation"""
    amount: Decimal
    is_income: bool
    property_type: Optional[PropertyType] = None
    vat_opted_in: bool = False  # For residential rental VAT opt-in
    category: Optional[str] = None  # expense_category or income_category value
    description: Optional[str] = None  # For keyword-based rate detection
    is_reverse_charge: bool = False  # §19 UStG: foreign B2B service (e.g. SaaS from EU)


@dataclass
class VATLineItem:
    """Individual VAT line item for detailed breakdown"""
    description: str
    net_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    rate_type: VATRateType


@dataclass
class ReverseChargeItem:
    """Individual reverse-charge transaction for UVA reporting"""
    description: str
    net_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal  # Self-assessed VAT (both output + input, net zero for Vorsteuer-eligible)


@dataclass
class VATResult:
    """Result of VAT calculation"""
    exempt: bool
    output_vat: Decimal = Decimal('0.00')
    input_vat: Decimal = Decimal('0.00')
    net_vat: Decimal = Decimal('0.00')
    reason: Optional[str] = None
    warning: Optional[str] = None
    line_items: List[VATLineItem] = field(default_factory=list)
    rates_applied: Dict[str, Decimal] = field(default_factory=dict)
    # Reverse charge (§19 UStG) — UVA fields KZ 057 (taxable amount) and KZ 066 (VAT)
    reverse_charge_items: List[ReverseChargeItem] = field(default_factory=list)
    reverse_charge_kz057: Decimal = Decimal('0.00')  # Total taxable amount (Bemessungsgrundlage)
    reverse_charge_kz066: Decimal = Decimal('0.00')  # Total self-assessed VAT


class VATCalculator:
    """
    Calculator for Austrian VAT (Umsatzsteuer) system.

    Key features:
    - Small business exemption (Kleinunternehmerregelung): EUR 55,000 threshold
    - Tolerance rule: EUR 63,250 (15% overshoot, once)
    - Standard rate: 20%
    - Reduced 10%: residential rental, accommodation, food, books, transport
    - Reduced 13%: live animals/plants, artist, film/circus, sporting events

    All rates and thresholds are loaded from year-specific TaxConfiguration.
    Defaults match 2026 values for backward compatibility.
    """

    # Default VAT rates (2026 fallback)
    _DEFAULT_STANDARD_RATE = Decimal('0.20')
    _DEFAULT_REDUCED_RATE_10 = Decimal('0.10')
    _DEFAULT_REDUCED_RATE_13 = Decimal('0.13')
    _DEFAULT_REDUCED_RATE_5 = Decimal('0.05')
    _DEFAULT_ZERO_RATE = Decimal('0.00')
    _DEFAULT_SMALL_BUSINESS_THRESHOLD = Decimal('55000.00')
    _DEFAULT_TOLERANCE_THRESHOLD = Decimal('63250.00')

    def __init__(self, vat_config: Optional[Dict] = None):
        """
        Initialize VAT calculator with year-specific configuration.

        Args:
            vat_config: VAT configuration dict from TaxConfiguration.vat_rates.
                Expected keys: standard, residential, reduced_13,
                small_business_threshold, tolerance_threshold.
                If None, uses 2026 defaults for backward compatibility.
        """
        if vat_config:
            self.STANDARD_RATE = Decimal(str(vat_config.get('standard', self._DEFAULT_STANDARD_RATE)))
            self.REDUCED_RATE_10 = Decimal(str(vat_config.get('residential', self._DEFAULT_REDUCED_RATE_10)))
            self.REDUCED_RATE_13 = Decimal(str(vat_config.get('reduced_13', self._DEFAULT_REDUCED_RATE_13)))
            self.REDUCED_RATE_5 = Decimal(str(vat_config.get('reduced_5', self._DEFAULT_REDUCED_RATE_5)))
            self.ZERO_RATE = Decimal(str(vat_config.get('zero_rated', self._DEFAULT_ZERO_RATE)))
            self.SMALL_BUSINESS_THRESHOLD = Decimal(str(
                vat_config.get('small_business_threshold', self._DEFAULT_SMALL_BUSINESS_THRESHOLD)
            ))
            self.TOLERANCE_THRESHOLD = Decimal(str(
                vat_config.get('tolerance_threshold', self._DEFAULT_TOLERANCE_THRESHOLD)
            ))
        else:
            self.STANDARD_RATE = self._DEFAULT_STANDARD_RATE
            self.REDUCED_RATE_10 = self._DEFAULT_REDUCED_RATE_10
            self.REDUCED_RATE_13 = self._DEFAULT_REDUCED_RATE_13
            self.REDUCED_RATE_5 = self._DEFAULT_REDUCED_RATE_5
            self.ZERO_RATE = self._DEFAULT_ZERO_RATE
            self.SMALL_BUSINESS_THRESHOLD = self._DEFAULT_SMALL_BUSINESS_THRESHOLD
            self.TOLERANCE_THRESHOLD = self._DEFAULT_TOLERANCE_THRESHOLD

    # Categories that qualify for 10% reduced rate
    # Residential rental, accommodation/Beherbergung, food/groceries, books
    REDUCED_10_CATEGORIES: Set[str] = {
        'rental',           # Residential rental income (Vermietung Wohnzwecke)
        'groceries',        # Food / Lebensmittel
        'accommodation',    # Beherbergung (short-term lodging, Airbnb, etc.)
    }

    # Keywords in description that suggest 10% rate
    REDUCED_10_KEYWORDS: Set[str] = {
        'miete', 'miet', 'wohnung', 'apartment',
        'lebensmittel', 'food', 'groceries', 'nahrung',
        'buch', 'book', 'zeitung', 'newspaper', 'magazin',
        'unterkunft', 'beherbergung', 'accommodation', 'lodging',
        'airbnb', 'ferienwohnung', 'pension', 'hostel',
        'camping', 'campingplatz',
        'nahverkehr', 'fahrkarte', 'oebb', 'wiener linien',
    }

    # Categories that qualify for 13% reduced rate
    REDUCED_13_CATEGORIES: Set[str] = {
        'art',              # Artist activities
        'culture',          # Cultural events
        'sports_event',     # Sporting event admissions
    }

    # Keywords in description that suggest 13% rate
    REDUCED_13_KEYWORDS: Set[str] = {
        'kunst', 'artist', 'kuenstler',
        'film', 'kino', 'cinema', 'zirkus', 'circus',
        'sport', 'veranstaltung', 'konzert', 'concert',
        'theater', 'theatre', 'oper', 'opera',
        'blumen', 'flower', 'pflanze', 'plant',
        'brennholz', 'firewood',
        'tier', 'animal',
        'eintrittskarte', 'ticket',
    }

    # Keywords for 0% zero-rated (menstrual/contraceptive products)
    ZERO_RATED_KEYWORDS: Set[str] = {
        'tampon', 'binde', 'menstruation', 'menstrual',
        'kondom', 'condom', 'verhütung', 'contraceptive',
        'pille', 'birth control',
    }

    # Keywords for 5% reduced rate (essential foods)
    REDUCED_5_KEYWORDS: Set[str] = {
        'grundnahrungsmittel', 'brot', 'bread', 'mehl', 'flour',
        'milch', 'milk', 'butter', 'eier', 'eggs',
        'zucker', 'sugar', 'reis', 'rice', 'nudeln', 'pasta',
        'speiseöl', 'cooking oil',
    }

    def determine_vat_rate(
        self,
        category: Optional[str] = None,
        description: Optional[str] = None,
        property_type: Optional[PropertyType] = None,
        vat_opted_in: bool = False,
    ) -> tuple[Decimal, VATRateType]:
        """
        Determine the applicable VAT rate for a transaction.

        Priority:
        1. Property type (residential rental = 10% if opted in, commercial = 20%)
        2. Category-based lookup
        3. Description keyword matching
        4. Default: standard 20%

        Returns:
            Tuple of (rate as Decimal, VATRateType)
        """
        # Residential rental: 10% if opted in, otherwise exempt from VAT
        if property_type == PropertyType.RESIDENTIAL:
            if vat_opted_in:
                return (self.REDUCED_RATE_10, VATRateType.REDUCED_10)
            else:
                return (Decimal('0'), VATRateType.EXEMPT)

        # Commercial rental: always 20%
        if property_type == PropertyType.COMMERCIAL:
            return (self.STANDARD_RATE, VATRateType.STANDARD)

        # Category-based rate
        cat_lower = (category or '').lower().strip()
        if cat_lower in self.REDUCED_10_CATEGORIES:
            return (self.REDUCED_RATE_10, VATRateType.REDUCED_10)
        if cat_lower in self.REDUCED_13_CATEGORIES:
            return (self.REDUCED_RATE_13, VATRateType.REDUCED_13)

        # Description keyword matching (check most specific first)
        if description:
            desc_lower = description.lower()
            for kw in self.ZERO_RATED_KEYWORDS:
                if kw in desc_lower:
                    return (self.ZERO_RATE, VATRateType.ZERO_RATED)
            for kw in self.REDUCED_5_KEYWORDS:
                if kw in desc_lower:
                    return (self.REDUCED_RATE_5, VATRateType.REDUCED_5)
            for kw in self.REDUCED_13_KEYWORDS:
                if kw in desc_lower:
                    return (self.REDUCED_RATE_13, VATRateType.REDUCED_13)
            for kw in self.REDUCED_10_KEYWORDS:
                if kw in desc_lower:
                    return (self.REDUCED_RATE_10, VATRateType.REDUCED_10)

        # Default: standard 20%
        return (self.STANDARD_RATE, VATRateType.STANDARD)

    def calculate_vat_liability(
        self,
        gross_turnover: Decimal,
        transactions: List[Transaction],
        property_type: Optional[PropertyType] = None,
    ) -> VATResult:
        """
        Calculate VAT liability based on gross turnover and transactions.

        Args:
            gross_turnover: Annual gross turnover
            transactions: List of income and expense transactions
            property_type: Default property type for rental income (if applicable)

        Returns:
            VATResult with exemption status, output VAT, input VAT, and net VAT
        """
        if not isinstance(gross_turnover, Decimal):
            gross_turnover = Decimal(str(gross_turnover))

        # Check small business exemption (Kleinunternehmerregelung)
        if gross_turnover <= self.SMALL_BUSINESS_THRESHOLD:
            # Kleinunternehmer: no VAT obligation, no reverse charge
            # (KU is exempt from USt — RC does not apply)
            return VATResult(
                exempt=True,
                reason=(
                    f"Kleinunternehmerregelung: turnover EUR {gross_turnover:,.2f} "
                    f"<= EUR {self.SMALL_BUSINESS_THRESHOLD:,.2f} threshold. "
                    f"No VAT obligation."
                ),
            )

        # Check tolerance rule (15% overshoot) — still exempt, no RC
        if gross_turnover <= self.TOLERANCE_THRESHOLD:
            return VATResult(
                exempt=True,
                reason=(
                    f"Tolerance rule: turnover EUR {gross_turnover:,.2f} "
                    f"<= EUR {self.TOLERANCE_THRESHOLD:,.2f}. "
                    f"Exempt this year, but exemption cancelled next year."
                ),
                warning=(
                    "Your turnover exceeds EUR 55,000 but is within the 15% tolerance. "
                    "You are exempt this year, but will be VAT-liable next year. "
                    "Consider consulting a Steuerberater about voluntary registration "
                    "to deduct input VAT (Vorsteuerabzug)."
                ),
            )

        # Above threshold: regelbesteuert — calculate VAT + reverse charge
        rc_items, rc_kz057, rc_kz066 = self.calculate_reverse_charge(transactions)

        line_items: List[VATLineItem] = []
        output_vat = Decimal('0.00')
        input_vat = Decimal('0.00')
        rates_summary: Dict[str, Decimal] = {}

        for txn in transactions:
            amount = txn.amount if isinstance(txn.amount, Decimal) else Decimal(str(txn.amount))

            # Determine rate for this transaction
            txn_property_type = txn.property_type or property_type
            rate, rate_type = self.determine_vat_rate(
                category=txn.category,
                description=txn.description,
                property_type=txn_property_type,
                vat_opted_in=txn.vat_opted_in,
            )

            if rate == Decimal('0'):
                continue

            # VAT = gross * rate / (1 + rate)
            vat_amount = (amount * rate / (Decimal('1') + rate)).quantize(Decimal('0.01'))

            rate_label = f"{float(rate) * 100:.0f}%"
            if rate_label not in rates_summary:
                rates_summary[rate_label] = Decimal('0.00')

            if txn.is_income:
                output_vat += vat_amount
                rates_summary[rate_label] += vat_amount
                line_items.append(VATLineItem(
                    description=txn.description or f"Income ({txn.category or 'unknown'})",
                    net_amount=(amount - vat_amount).quantize(Decimal('0.01')),
                    vat_rate=rate,
                    vat_amount=vat_amount,
                    rate_type=rate_type,
                ))
            else:
                input_vat += vat_amount
                rates_summary[rate_label] += vat_amount

        output_vat = output_vat.quantize(Decimal('0.01'))
        input_vat = input_vat.quantize(Decimal('0.01'))
        net_vat = (output_vat - input_vat).quantize(Decimal('0.01'))

        # For Vorsteuer-eligible businesses, reverse charge is net-zero:
        # self-assessed output VAT + equal input VAT deduction cancel out.
        # But we still report KZ 057/066 for UVA.
        # (output_vat and input_vat each increase by rc_kz066, net unchanged)
        if rc_items:
            output_vat += rc_kz066
            input_vat += rc_kz066
            output_vat = output_vat.quantize(Decimal('0.01'))
            input_vat = input_vat.quantize(Decimal('0.01'))
            net_vat = (output_vat - input_vat).quantize(Decimal('0.01'))

        return VATResult(
            exempt=False,
            output_vat=output_vat,
            input_vat=input_vat,
            net_vat=net_vat,
            line_items=line_items,
            rates_applied=rates_summary,
            reverse_charge_items=rc_items,
            reverse_charge_kz057=rc_kz057,
            reverse_charge_kz066=rc_kz066,
        )

    def calculate_reverse_charge(
        self,
        transactions: List[Transaction],
    ) -> tuple[List[ReverseChargeItem], Decimal, Decimal]:
        """
        Calculate reverse-charge self-assessment for §19 UStG transactions.

        When an Austrian business receives a service from a foreign EU business
        (e.g., SaaS subscriptions, cloud hosting, freelance services), the
        recipient must self-assess VAT at 20% (standard rate).

        For the UVA (Umsatzsteuervoranmeldung):
        - KZ 057: Taxable amount (Bemessungsgrundlage)
        - KZ 066: Self-assessed VAT (20% of KZ 057)

        If the recipient is Vorsteuer-eligible, the self-assessed VAT is
        simultaneously deductible as input VAT, making it net-zero.

        Args:
            transactions: List of transactions (only is_reverse_charge=True processed)

        Returns:
            (reverse_charge_items, kz057_total, kz066_total)
        """
        items: List[ReverseChargeItem] = []
        kz057 = Decimal('0.00')
        kz066 = Decimal('0.00')

        for txn in transactions:
            if not txn.is_reverse_charge:
                continue

            amount = txn.amount if isinstance(txn.amount, Decimal) else Decimal(str(txn.amount))
            # Reverse charge applies at 20% standard rate
            vat_amount = (amount * self.STANDARD_RATE).quantize(Decimal('0.01'))

            items.append(ReverseChargeItem(
                description=txn.description or f"Reverse Charge ({txn.category or 'foreign service'})",
                net_amount=amount.quantize(Decimal('0.01')),
                vat_rate=self.STANDARD_RATE,
                vat_amount=vat_amount,
            ))

            kz057 += amount
            kz066 += vat_amount

        return items, kz057.quantize(Decimal('0.01')), kz066.quantize(Decimal('0.01'))

    def check_small_business_exemption(self, gross_turnover: Decimal) -> bool:
        """Check if small business exemption applies."""
        if not isinstance(gross_turnover, Decimal):
            gross_turnover = Decimal(str(gross_turnover))
        return gross_turnover <= self.SMALL_BUSINESS_THRESHOLD

    def apply_tolerance_rule(self, gross_turnover: Decimal) -> tuple[bool, Optional[str]]:
        """
        Check if tolerance rule applies (turnover between 55k and 60.5k).

        Returns:
            Tuple of (applies, warning_message)
        """
        if not isinstance(gross_turnover, Decimal):
            gross_turnover = Decimal(str(gross_turnover))

        if self.SMALL_BUSINESS_THRESHOLD < gross_turnover <= self.TOLERANCE_THRESHOLD:
            return (
                True,
                "Tolerance rule applies - exempt this year but "
                "exemption automatically cancelled next year.",
            )
        return (False, None)


