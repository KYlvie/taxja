"""
Investitionsfreibetrag (IFB) calculator — §11 EStG.

Introduced from Steuerjahr 2023 (Veranlagung 2024) by the
Öko-soziale Steuerreform 2022 (BGBl I Nr. 10/2022).

Rules:
- 10% of acquisition/production costs of qualifying tangible fixed assets
- 15% for climate-friendly investments (Ökologisierungszuschlag):
  - Zero-emission vehicles (BEV, FCEV)
  - Heating systems using renewable energy
  - Thermal insulation / energy efficiency improvements
- Maximum IFB per year: 10%/15% of up to €1,000,000 eligible investment
  → max €100,000 (standard) or €150,000 (eco)
- NOT available for:
  - Buildings and land (Gebäude, Grundstücke)
  - Passenger vehicles (except zero-emission)
  - Used assets (gebrauchte Wirtschaftsgüter)
  - Assets with useful life < 4 years
  - Assets that are immediately expensed (GWG up to €1,000)
- MUTUAL EXCLUSION with investitionsbedingter Gewinnfreibetrag (§10 EStG):
  The same investment cannot be used for both IFB and the investment-based
  portion of GFB.  The Grundfreibetrag (15% of profit up to €33,000) is
  unaffected — only the investitionsbedingter GFB competes with IFB.
- Only for income from business (§23) or self-employment (§22)
- NOT available with Basispauschalierung

References:
- §11 EStG (Investitionsfreibetrag)
- BMF Info zur ökologischen Staffelung
- WKO: https://www.wko.at/steuern/investitionsfreibetrag
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class IFBAssetType(str, Enum):
    """Asset type for IFB rate determination."""
    STANDARD = "standard"              # 10% — standard tangible fixed assets
    ECO_VEHICLE = "eco_vehicle"        # 15% — zero-emission vehicles
    ECO_HEATING = "eco_heating"        # 15% — renewable energy heating
    ECO_INSULATION = "eco_insulation"  # 15% — thermal insulation
    ECO_OTHER = "eco_other"            # 15% — other ecological investments


# Rates
IFB_STANDARD_RATE = Decimal("0.10")   # 10%
IFB_ECO_RATE = Decimal("0.15")        # 15% ecological surcharge

# Doubled rates (Konjunkturpaket: Nov 2025 – Dec 2026)
IFB_STANDARD_RATE_DOUBLED = Decimal("0.20")  # 20%
IFB_ECO_RATE_DOUBLED = Decimal("0.22")       # 22% (15% + 7% eco surcharge doubled proportionally? No — 15% × 2 would be 30%, but the actual legislation doubles standard to 20% and eco to 22%)
IFB_DOUBLED_START = date(2025, 11, 1)
IFB_DOUBLED_END = date(2026, 12, 31)

# Maximum eligible investment per year
IFB_MAX_ELIGIBLE_INVESTMENT = Decimal("1000000.00")  # €1,000,000


@dataclass
class IFBLineItem:
    """Individual investment item for IFB calculation."""
    description: str
    asset_type: IFBAssetType
    acquisition_cost: Decimal
    rate: Decimal
    ifb_amount: Decimal
    note: str = ""


@dataclass
class IFBResult:
    """Result of Investitionsfreibetrag calculation."""
    total_eligible_investment: Decimal = Decimal("0.00")
    total_ifb: Decimal = Decimal("0.00")
    standard_ifb: Decimal = Decimal("0.00")
    eco_ifb: Decimal = Decimal("0.00")
    line_items: List[IFBLineItem] = field(default_factory=list)
    capped: bool = False
    note: str = ""


def get_ifb_rate(
    asset_type: IFBAssetType,
    acquisition_date: Optional[date] = None,
) -> Decimal:
    """Return the applicable IFB rate for an asset type.

    If acquisition_date falls within the doubled-rate window (Nov 2025 – Dec 2026),
    the temporarily increased rates apply.
    """
    is_doubled = (
        acquisition_date is not None
        and IFB_DOUBLED_START <= acquisition_date <= IFB_DOUBLED_END
    )

    if asset_type in (
        IFBAssetType.ECO_VEHICLE,
        IFBAssetType.ECO_HEATING,
        IFBAssetType.ECO_INSULATION,
        IFBAssetType.ECO_OTHER,
    ):
        return IFB_ECO_RATE_DOUBLED if is_doubled else IFB_ECO_RATE
    return IFB_STANDARD_RATE_DOUBLED if is_doubled else IFB_STANDARD_RATE


def calculate_ifb(
    investments: List[dict],
    tax_year: int = 2026,
) -> IFBResult:
    """
    Calculate Investitionsfreibetrag for a list of qualifying investments.

    The IFB is only available from Steuerjahr 2023 onward and cannot be used
    together with Basispauschalierung.

    Args:
        investments: List of dicts with keys:
            - description (str): Description of the asset
            - asset_type (str or IFBAssetType): Type of asset
            - acquisition_cost (Decimal or float): Acquisition/production cost
        tax_year: Tax year (IFB only available from 2023)

    Returns:
        IFBResult with breakdown per investment.
    """
    # IFB not available before 2023
    if tax_year < 2023:
        return IFBResult(
            note="Investitionsfreibetrag erst ab Steuerjahr 2023 verfügbar (§11 EStG)."
        )

    line_items: List[IFBLineItem] = []
    total_eligible = Decimal("0.00")
    total_ifb = Decimal("0.00")
    standard_ifb = Decimal("0.00")
    eco_ifb = Decimal("0.00")
    capped = False

    # TODO(P2): Enforce §11 EStG exclusion rules before calculating IFB:
    #   - Used assets (gebrauchte Wirtschaftsgüter) → not eligible
    #   - GWG immediately expensed (≤ €1,000) → not eligible
    #   - Intangible assets (immaterielle WG) → not eligible
    #   - Assets with useful life < 4 years → not eligible
    #   - Passenger vehicles with CO₂ > 0 g/km → not eligible (only BEV/FCEV qualify)
    #   - Buildings and land (Gebäude, Grundstücke) → not eligible
    #   - Not available with Basispauschalierung
    #   - IFB+GFB mutual exclusion: investments used for IFB cannot also be
    #     used for investitionsbedingter Gewinnfreibetrag (§10 EStG).
    #     The GFB side is enforced via ifb_claimed_investment parameter in
    #     calculate_gewinnfreibetrag(); the IFB side should mirror this.
    # Currently the caller is responsible for pre-filtering; add validation here.

    for inv in investments:
        asset_type = inv.get("asset_type", "standard")
        if isinstance(asset_type, str):
            asset_type = IFBAssetType(asset_type)

        cost = Decimal(str(inv.get("acquisition_cost", 0)))
        if cost <= Decimal("0"):
            continue

        # Check cap: only up to €1,000,000 total eligible investment
        remaining_eligible = IFB_MAX_ELIGIBLE_INVESTMENT - total_eligible
        if remaining_eligible <= Decimal("0"):
            capped = True
            line_items.append(IFBLineItem(
                description=inv.get("description", ""),
                asset_type=asset_type,
                acquisition_cost=cost,
                rate=Decimal("0"),
                ifb_amount=Decimal("0"),
                note="Investitionsobergrenze von €1.000.000 bereits ausgeschöpft.",
            ))
            continue

        eligible_cost = min(cost, remaining_eligible)
        if eligible_cost < cost:
            capped = True

        acq_date = inv.get("acquisition_date")
        if isinstance(acq_date, str):
            acq_date = date.fromisoformat(acq_date)
        rate = get_ifb_rate(asset_type, acquisition_date=acq_date)
        ifb_amount = (eligible_cost * rate).quantize(Decimal("0.01"))

        total_eligible += eligible_cost
        total_ifb += ifb_amount

        if asset_type == IFBAssetType.STANDARD:
            standard_ifb += ifb_amount
        else:
            eco_ifb += ifb_amount

        note = ""
        if eligible_cost < cost:
            note = (
                f"Nur €{eligible_cost:,.2f} von €{cost:,.2f} berücksichtigt "
                f"(Obergrenze €1.000.000)."
            )

        line_items.append(IFBLineItem(
            description=inv.get("description", ""),
            asset_type=asset_type,
            acquisition_cost=cost,
            rate=rate,
            ifb_amount=ifb_amount,
            note=note,
        ))

    note = (
        f"Investitionsfreibetrag §11 EStG: "
        f"€{total_ifb:,.2f} auf €{total_eligible:,.2f} Investitionen."
    )
    if capped:
        note += " Obergrenze von €1.000.000 erreicht."

    return IFBResult(
        total_eligible_investment=total_eligible.quantize(Decimal("0.01")),
        total_ifb=total_ifb.quantize(Decimal("0.01")),
        standard_ifb=standard_ifb.quantize(Decimal("0.01")),
        eco_ifb=eco_ifb.quantize(Decimal("0.01")),
        line_items=line_items,
        capped=capped,
        note=note,
    )
