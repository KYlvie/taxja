"""
ImmoESt (Immobilienertragsteuer) calculator for Austrian real estate capital gains.

When selling real property in Austria, the capital gain is taxed at a flat 30%
(Immobilienertragsteuer, §30 EStG). This is separate from the progressive
income tax tariff.

Key rules:
- Rate: 30% on the gain (sale price minus acquisition cost minus improvement costs)
- Hauptwohnsitzbefreiung: exempt if the property was the seller's main residence
  for at least 2 years continuously before the sale, OR for at least 5 of the
  last 10 years
- Herstellerbefreiung: exempt if the seller built the property themselves and
  never used it for income generation
- Old properties (acquired before 31.03.2002): special flat-rate calculation
  with 14% effective rate (or 60% of gain × 30% = 18% if reclassified)
- Reclassification surcharge: from 01.07.2025, a 30% surcharge on gains from
  land reclassified from green space to building land after 31.12.2024

Source: https://www.oesterreich.gv.at/en/themen/steuern_und_finanzen/immobilienertragsteuer/
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional
from datetime import date


IMMOEST_RATE = Decimal("0.30")  # 30%
OLD_PROPERTY_EFFECTIVE_RATE = Decimal("0.14")  # 14% for pre-2002 acquisitions
OLD_PROPERTY_RECLASSIFIED_RATE = Decimal("0.18")  # 18% for reclassified pre-2002
OLD_PROPERTY_CUTOFF = date(2002, 3, 31)
RECLASSIFICATION_SURCHARGE_START = date(2025, 7, 1)
RECLASSIFICATION_SURCHARGE_RATE = Decimal("0.30")  # 30% surcharge on gain


class ExemptionType(str, Enum):
    """Exemption types for ImmoESt."""
    NONE = "none"
    HAUPTWOHNSITZ = "hauptwohnsitz"      # Main residence exemption
    HERSTELLER = "hersteller"            # Self-built property exemption


@dataclass
class ImmoEStResult:
    """Result of ImmoESt calculation."""
    exempt: bool = False
    exemption_type: ExemptionType = ExemptionType.NONE
    sale_price: Decimal = Decimal("0.00")
    acquisition_cost: Decimal = Decimal("0.00")
    improvement_costs: Decimal = Decimal("0.00")
    selling_costs: Decimal = Decimal("0.00")
    taxable_gain: Decimal = Decimal("0.00")
    tax_rate: Decimal = IMMOEST_RATE
    tax_amount: Decimal = Decimal("0.00")
    reclassification_surcharge: Decimal = Decimal("0.00")
    total_tax: Decimal = Decimal("0.00")
    net_proceeds: Decimal = Decimal("0.00")
    is_old_property: bool = False
    note: str = ""


def calculate_immoest(
    sale_price: Decimal,
    acquisition_cost: Decimal,
    acquisition_date: Optional[date] = None,
    improvement_costs: Decimal = Decimal("0.00"),
    selling_costs: Decimal = Decimal("0.00"),
    exemption: ExemptionType = ExemptionType.NONE,
    was_reclassified: bool = False,
    reclassification_date: Optional[date] = None,
    sale_date: Optional[date] = None,
) -> ImmoEStResult:
    """
    Calculate Immobilienertragsteuer on a property sale.

    Args:
        sale_price: Gross sale price of the property.
        acquisition_cost: Original purchase price (Anschaffungskosten).
        acquisition_date: Date of original acquisition (for old-property rule).
        improvement_costs: Costs of improvements (Herstellungsaufwendungen).
        selling_costs: Costs of selling (Makler, Notar, etc.).
        exemption: Applicable exemption type.
        was_reclassified: Whether the land was reclassified (Umwidmung).
        reclassification_date: Date of reclassification (for surcharge rule).
        sale_date: Date of sale (defaults to today).

    Returns:
        ImmoEStResult with tax calculation details.
    """
    sale_price = Decimal(str(sale_price))
    acquisition_cost = Decimal(str(acquisition_cost))
    improvement_costs = Decimal(str(improvement_costs))
    selling_costs = Decimal(str(selling_costs))

    if sale_date is None:
        sale_date = date.today()

    # Check exemptions
    if exemption == ExemptionType.HAUPTWOHNSITZ:
        return ImmoEStResult(
            exempt=True,
            exemption_type=ExemptionType.HAUPTWOHNSITZ,
            sale_price=sale_price,
            acquisition_cost=acquisition_cost,
            net_proceeds=sale_price - selling_costs,
            note=(
                "Hauptwohnsitzbefreiung: Keine ImmoESt, da die Immobilie "
                "als Hauptwohnsitz genutzt wurde (mind. 2 Jahre durchgehend "
                "oder 5 der letzten 10 Jahre)."
            ),
        )

    if exemption == ExemptionType.HERSTELLER:
        return ImmoEStResult(
            exempt=True,
            exemption_type=ExemptionType.HERSTELLER,
            sale_price=sale_price,
            acquisition_cost=acquisition_cost,
            net_proceeds=sale_price - selling_costs,
            note=(
                "Herstellerbefreiung: Keine ImmoESt, da die Immobilie "
                "selbst errichtet und nicht zur Einkunftserzielung genutzt wurde."
            ),
        )

    # Determine if old property (acquired before 01.04.2002)
    is_old = False
    if acquisition_date and acquisition_date <= OLD_PROPERTY_CUTOFF:
        is_old = True

    if is_old:
        # Old property: flat-rate calculation
        if was_reclassified:
            # Reclassified old property: 60% of gain × 30% = 18% effective
            rate = OLD_PROPERTY_RECLASSIFIED_RATE
            note_detail = "Altgrundstück (Umwidmung): 18% Pauschalbesteuerung"
        else:
            # Non-reclassified old property: 14% effective
            rate = OLD_PROPERTY_EFFECTIVE_RATE
            note_detail = "Altgrundstück: 14% Pauschalbesteuerung"

        tax = (sale_price * rate).quantize(Decimal("0.01"))
        return ImmoEStResult(
            sale_price=sale_price,
            acquisition_cost=acquisition_cost,
            tax_rate=rate,
            tax_amount=tax,
            total_tax=tax,
            net_proceeds=(sale_price - selling_costs - tax).quantize(Decimal("0.01")),
            is_old_property=True,
            note=note_detail,
        )

    # New property: gain = sale price - acquisition cost - improvements - selling costs
    gain = sale_price - acquisition_cost - improvement_costs - selling_costs
    gain = max(gain, Decimal("0.00"))

    tax = (gain * IMMOEST_RATE).quantize(Decimal("0.01"))

    # Reclassification surcharge (from 01.07.2025)
    surcharge = Decimal("0.00")
    if (
        was_reclassified
        and reclassification_date
        and reclassification_date > date(2024, 12, 31)
        and sale_date >= RECLASSIFICATION_SURCHARGE_START
    ):
        surcharge = (gain * RECLASSIFICATION_SURCHARGE_RATE).quantize(Decimal("0.01"))

    total = tax + surcharge
    net = (sale_price - selling_costs - total).quantize(Decimal("0.01"))

    note = f"ImmoESt: 30% auf Veräußerungsgewinn €{gain:,.2f} = €{tax:,.2f}."
    if surcharge > Decimal("0"):
        note += (
            f" Umwidmungszuschlag 30%: €{surcharge:,.2f}. "
            f"Gesamt: €{total:,.2f}."
        )

    return ImmoEStResult(
        sale_price=sale_price,
        acquisition_cost=acquisition_cost,
        improvement_costs=improvement_costs,
        selling_costs=selling_costs,
        taxable_gain=gain.quantize(Decimal("0.01")),
        tax_rate=IMMOEST_RATE,
        tax_amount=tax,
        reclassification_surcharge=surcharge,
        total_tax=total,
        net_proceeds=net,
        note=note,
    )
