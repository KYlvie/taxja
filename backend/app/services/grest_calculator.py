"""
GrESt (Grunderwerbsteuer) Calculator — Austrian Property Transfer Tax

Standard rate: 3.5% of Grundstueckswert (property value)
Family transfer (§7 Abs 1 Z 2 GrEstG) stepped rates:
  - up to EUR 250,000: 0.5%
  - EUR 250,001 - 400,000: 2.0%
  - above EUR 400,000: 3.5%

Note: Base is Grundstueckswert, not necessarily the purchase price.
For family transfers, the Grundstueckswert is typically assessed value.

Source: https://www.oesterreich.gv.at/themen/steuern_und_finanzen/grunderwerbsteuer
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


STANDARD_RATE = Decimal("0.035")  # 3.5%

# Family transfer stepped thresholds (§7 Abs 1 Z 2 GrEstG)
FAMILY_TIER_1_LIMIT = Decimal("250000")
FAMILY_TIER_1_RATE = Decimal("0.005")   # 0.5%
FAMILY_TIER_2_LIMIT = Decimal("400000")
FAMILY_TIER_2_RATE = Decimal("0.02")    # 2.0%
FAMILY_TIER_3_RATE = Decimal("0.035")   # 3.5%


@dataclass
class GrEStResult:
    """Result of GrESt calculation."""
    grundstueckswert: Decimal = Decimal("0.00")
    is_family_transfer: bool = False
    tax_amount: Decimal = Decimal("0.00")
    effective_rate: Decimal = Decimal("0.00")
    tier_breakdown: Optional[list] = None
    note: str = ""


def calculate_grest(
    grundstueckswert: Decimal,
    is_family_transfer: bool = False,
) -> GrEStResult:
    """Calculate Grunderwerbsteuer.

    Args:
        grundstueckswert: Property value (Grundstueckswert) as assessment base.
        is_family_transfer: Whether this is a transfer within family
            (§7 Abs 1 Z 2 GrEstG — applies stepped rates).

    Returns:
        GrEStResult with tax calculation details.
    """
    grundstueckswert = Decimal(str(grundstueckswert))

    if grundstueckswert <= 0:
        return GrEStResult(note="Grundstueckswert must be positive")

    if not is_family_transfer:
        # Standard flat rate 3.5%
        tax = (grundstueckswert * STANDARD_RATE).quantize(Decimal("0.01"))
        effective = STANDARD_RATE
        return GrEStResult(
            grundstueckswert=grundstueckswert,
            is_family_transfer=False,
            tax_amount=tax,
            effective_rate=effective,
            note=f"Standardsatz 3,5% auf EUR {grundstueckswert:,.2f}",
        )

    # Family transfer: stepped rates
    tiers = []
    tax = Decimal("0")

    # Tier 1: 0 - 250,000 at 0.5%
    tier1_base = min(grundstueckswert, FAMILY_TIER_1_LIMIT)
    tier1_tax = (tier1_base * FAMILY_TIER_1_RATE).quantize(Decimal("0.01"))
    tax += tier1_tax
    tiers.append({
        "range": f"0 - {FAMILY_TIER_1_LIMIT:,.0f}",
        "rate": "0.5%",
        "base": float(tier1_base),
        "tax": float(tier1_tax),
    })

    # Tier 2: 250,001 - 400,000 at 2.0%
    if grundstueckswert > FAMILY_TIER_1_LIMIT:
        tier2_base = min(grundstueckswert, FAMILY_TIER_2_LIMIT) - FAMILY_TIER_1_LIMIT
        tier2_tax = (tier2_base * FAMILY_TIER_2_RATE).quantize(Decimal("0.01"))
        tax += tier2_tax
        tiers.append({
            "range": f"{FAMILY_TIER_1_LIMIT:,.0f} - {FAMILY_TIER_2_LIMIT:,.0f}",
            "rate": "2.0%",
            "base": float(tier2_base),
            "tax": float(tier2_tax),
        })

    # Tier 3: above 400,000 at 3.5%
    if grundstueckswert > FAMILY_TIER_2_LIMIT:
        tier3_base = grundstueckswert - FAMILY_TIER_2_LIMIT
        tier3_tax = (tier3_base * FAMILY_TIER_3_RATE).quantize(Decimal("0.01"))
        tax += tier3_tax
        tiers.append({
            "range": f"ab {FAMILY_TIER_2_LIMIT:,.0f}",
            "rate": "3.5%",
            "base": float(tier3_base),
            "tax": float(tier3_tax),
        })

    effective = (tax / grundstueckswert).quantize(Decimal("0.0001")) if grundstueckswert > 0 else Decimal("0")

    return GrEStResult(
        grundstueckswert=grundstueckswert,
        is_family_transfer=True,
        tax_amount=tax,
        effective_rate=effective,
        tier_breakdown=tiers,
        note=(
            f"Familienuebergabe: Stufentarif auf EUR {grundstueckswert:,.2f}. "
            f"Effektiver Satz: {effective * 100:.2f}%"
        ),
    )
