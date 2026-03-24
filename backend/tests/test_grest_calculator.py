"""
Unit tests for GrESt (Grunderwerbsteuer) Calculator Service

Tests cover:
- Standard rate (3.5%) for non-family transfers
- Family transfer stepped rates (0.5% / 2.0% / 3.5%)
- Edge cases at thresholds (250k, 400k)
- Zero and negative values
- Tier breakdown verification
- Effective rate calculations
"""

import pytest
from decimal import Decimal

from app.services.grest_calculator import (
    calculate_grest,
    GrEStResult,
    STANDARD_RATE,
    FAMILY_TIER_1_LIMIT,
    FAMILY_TIER_1_RATE,
    FAMILY_TIER_2_LIMIT,
    FAMILY_TIER_2_RATE,
    FAMILY_TIER_3_RATE,
)


# ---------------------------------------------------------------------------
# Standard rate (non-family) transfers
# ---------------------------------------------------------------------------

class TestStandardRate:
    """Standard 3.5% flat rate for non-family property transfers."""

    def test_basic_standard_rate(self):
        result = calculate_grest(Decimal("100000"), is_family_transfer=False)
        assert result.tax_amount == Decimal("3500.00")
        assert result.effective_rate == STANDARD_RATE
        assert result.is_family_transfer is False
        assert result.tier_breakdown is None

    def test_standard_rate_large_value(self):
        result = calculate_grest(Decimal("1000000"), is_family_transfer=False)
        assert result.tax_amount == Decimal("35000.00")

    def test_standard_rate_small_value(self):
        result = calculate_grest(Decimal("1"), is_family_transfer=False)
        assert result.tax_amount == Decimal("0.04")

    def test_standard_rate_with_cents(self):
        result = calculate_grest(Decimal("123456.78"), is_family_transfer=False)
        expected = (Decimal("123456.78") * Decimal("0.035")).quantize(Decimal("0.01"))
        assert result.tax_amount == expected

    def test_standard_rate_defaults_to_non_family(self):
        """is_family_transfer defaults to False."""
        result = calculate_grest(Decimal("200000"))
        assert result.is_family_transfer is False
        assert result.tax_amount == Decimal("7000.00")

    def test_standard_rate_grundstueckswert_stored(self):
        result = calculate_grest(Decimal("350000"), is_family_transfer=False)
        assert result.grundstueckswert == Decimal("350000")

    def test_standard_rate_note_contains_value(self):
        result = calculate_grest(Decimal("500000"), is_family_transfer=False)
        assert "3,5%" in result.note or "3.5%" in result.note or "500" in result.note


# ---------------------------------------------------------------------------
# Family transfer stepped rates
# ---------------------------------------------------------------------------

class TestFamilyTransferTier1Only:
    """Values up to EUR 250,000 — tier 1 only at 0.5%."""

    def test_tier1_small_value(self):
        result = calculate_grest(Decimal("50000"), is_family_transfer=True)
        assert result.tax_amount == Decimal("250.00")
        assert result.is_family_transfer is True

    def test_tier1_100k(self):
        result = calculate_grest(Decimal("100000"), is_family_transfer=True)
        assert result.tax_amount == Decimal("500.00")

    def test_tier1_single_tier_breakdown(self):
        result = calculate_grest(Decimal("100000"), is_family_transfer=True)
        assert result.tier_breakdown is not None
        assert len(result.tier_breakdown) == 1
        assert result.tier_breakdown[0]["rate"] == "0.5%"
        assert result.tier_breakdown[0]["base"] == 100000.0
        assert result.tier_breakdown[0]["tax"] == 500.0


class TestFamilyTransferTier2:
    """Values between EUR 250,001 and EUR 400,000 — tiers 1 + 2."""

    def test_tier2_300k(self):
        result = calculate_grest(Decimal("300000"), is_family_transfer=True)
        # Tier 1: 250,000 * 0.5% = 1,250
        # Tier 2: 50,000 * 2.0% = 1,000
        expected = Decimal("1250.00") + Decimal("1000.00")
        assert result.tax_amount == expected

    def test_tier2_breakdown_has_two_tiers(self):
        result = calculate_grest(Decimal("300000"), is_family_transfer=True)
        assert result.tier_breakdown is not None
        assert len(result.tier_breakdown) == 2
        assert result.tier_breakdown[0]["rate"] == "0.5%"
        assert result.tier_breakdown[1]["rate"] == "2.0%"

    def test_tier2_350k(self):
        result = calculate_grest(Decimal("350000"), is_family_transfer=True)
        # Tier 1: 250,000 * 0.5% = 1,250
        # Tier 2: 100,000 * 2.0% = 2,000
        assert result.tax_amount == Decimal("3250.00")


class TestFamilyTransferTier3:
    """Values above EUR 400,000 — all three tiers."""

    def test_tier3_500k(self):
        result = calculate_grest(Decimal("500000"), is_family_transfer=True)
        # Tier 1: 250,000 * 0.5% = 1,250
        # Tier 2: 150,000 * 2.0% = 3,000
        # Tier 3: 100,000 * 3.5% = 3,500
        expected = Decimal("1250.00") + Decimal("3000.00") + Decimal("3500.00")
        assert result.tax_amount == expected

    def test_tier3_1m(self):
        result = calculate_grest(Decimal("1000000"), is_family_transfer=True)
        # Tier 1: 250,000 * 0.5% = 1,250.00
        # Tier 2: 150,000 * 2.0% = 3,000.00
        # Tier 3: 600,000 * 3.5% = 21,000.00
        expected = Decimal("1250.00") + Decimal("3000.00") + Decimal("21000.00")
        assert result.tax_amount == expected

    def test_tier3_breakdown_has_three_tiers(self):
        result = calculate_grest(Decimal("500000"), is_family_transfer=True)
        assert result.tier_breakdown is not None
        assert len(result.tier_breakdown) == 3
        assert result.tier_breakdown[0]["rate"] == "0.5%"
        assert result.tier_breakdown[1]["rate"] == "2.0%"
        assert result.tier_breakdown[2]["rate"] == "3.5%"

    def test_tier3_breakdown_bases(self):
        result = calculate_grest(Decimal("500000"), is_family_transfer=True)
        assert result.tier_breakdown[0]["base"] == 250000.0
        assert result.tier_breakdown[1]["base"] == 150000.0
        assert result.tier_breakdown[2]["base"] == 100000.0

    def test_tier3_breakdown_taxes(self):
        result = calculate_grest(Decimal("500000"), is_family_transfer=True)
        assert result.tier_breakdown[0]["tax"] == 1250.0
        assert result.tier_breakdown[1]["tax"] == 3000.0
        assert result.tier_breakdown[2]["tax"] == 3500.0


# ---------------------------------------------------------------------------
# Edge cases: exactly at thresholds
# ---------------------------------------------------------------------------

class TestThresholdEdgeCases:
    """Values exactly at tier boundaries (250,000 and 400,000)."""

    def test_exactly_250k(self):
        """At exactly 250,000, only tier 1 applies."""
        result = calculate_grest(Decimal("250000"), is_family_transfer=True)
        assert result.tax_amount == Decimal("1250.00")
        assert len(result.tier_breakdown) == 1

    def test_one_cent_above_250k(self):
        """At 250,000.01 tier 2 kicks in."""
        result = calculate_grest(Decimal("250000.01"), is_family_transfer=True)
        assert len(result.tier_breakdown) == 2
        # Tier 1: 250,000 * 0.5% = 1,250.00
        # Tier 2: 0.01 * 2.0% = 0.00 (rounded)
        tier2_tax = (Decimal("0.01") * Decimal("0.02")).quantize(Decimal("0.01"))
        expected = Decimal("1250.00") + tier2_tax
        assert result.tax_amount == expected

    def test_exactly_400k(self):
        """At exactly 400,000, tiers 1 and 2 apply, but not tier 3."""
        result = calculate_grest(Decimal("400000"), is_family_transfer=True)
        # Tier 1: 250,000 * 0.5% = 1,250
        # Tier 2: 150,000 * 2.0% = 3,000
        assert result.tax_amount == Decimal("4250.00")
        assert len(result.tier_breakdown) == 2

    def test_one_cent_above_400k(self):
        """At 400,000.01 tier 3 kicks in."""
        result = calculate_grest(Decimal("400000.01"), is_family_transfer=True)
        assert len(result.tier_breakdown) == 3
        tier3_tax = (Decimal("0.01") * Decimal("0.035")).quantize(Decimal("0.01"))
        expected = Decimal("1250.00") + Decimal("3000.00") + tier3_tax
        assert result.tax_amount == expected


# ---------------------------------------------------------------------------
# Edge cases: zero and negative values
# ---------------------------------------------------------------------------

class TestZeroAndNegativeValues:
    """Zero and negative grundstueckswert should return an error note."""

    def test_zero_value(self):
        result = calculate_grest(Decimal("0"))
        assert result.tax_amount == Decimal("0.00")
        assert "positive" in result.note.lower() or "must be" in result.note.lower()

    def test_negative_value(self):
        result = calculate_grest(Decimal("-100000"))
        assert result.tax_amount == Decimal("0.00")
        assert "positive" in result.note.lower() or "must be" in result.note.lower()

    def test_zero_family_transfer(self):
        result = calculate_grest(Decimal("0"), is_family_transfer=True)
        assert result.tax_amount == Decimal("0.00")

    def test_negative_family_transfer(self):
        result = calculate_grest(Decimal("-50000"), is_family_transfer=True)
        assert result.tax_amount == Decimal("0.00")


# ---------------------------------------------------------------------------
# Effective rate calculations
# ---------------------------------------------------------------------------

class TestEffectiveRate:
    """Effective rate should reflect the blended stepped rate for family transfers."""

    def test_effective_rate_standard_is_flat(self):
        result = calculate_grest(Decimal("200000"), is_family_transfer=False)
        assert result.effective_rate == Decimal("0.035")

    def test_effective_rate_tier1_only(self):
        result = calculate_grest(Decimal("200000"), is_family_transfer=True)
        # All in tier 1 at 0.5% -> effective = 0.5%
        assert result.effective_rate == Decimal("0.0050")

    def test_effective_rate_two_tiers(self):
        result = calculate_grest(Decimal("300000"), is_family_transfer=True)
        # Tax = 2,250; effective = 2250 / 300000 = 0.0075
        assert result.effective_rate == Decimal("0.0075")

    def test_effective_rate_three_tiers(self):
        result = calculate_grest(Decimal("500000"), is_family_transfer=True)
        # Tax = 7,750; effective = 7750 / 500000 = 0.0155
        assert result.effective_rate == Decimal("0.0155")

    def test_effective_rate_at_exactly_250k(self):
        result = calculate_grest(Decimal("250000"), is_family_transfer=True)
        assert result.effective_rate == Decimal("0.0050")

    def test_effective_rate_at_exactly_400k(self):
        result = calculate_grest(Decimal("400000"), is_family_transfer=True)
        # Tax = 4,250; effective = 4250 / 400000 = 0.010625 -> quantize to 0.0106
        expected = (Decimal("4250") / Decimal("400000")).quantize(Decimal("0.0001"))
        assert result.effective_rate == expected

    def test_effective_rate_increases_with_value(self):
        """Higher values should have a higher effective rate for family transfers."""
        r100k = calculate_grest(Decimal("100000"), is_family_transfer=True)
        r300k = calculate_grest(Decimal("300000"), is_family_transfer=True)
        r500k = calculate_grest(Decimal("500000"), is_family_transfer=True)
        r1m = calculate_grest(Decimal("1000000"), is_family_transfer=True)

        assert r100k.effective_rate < r300k.effective_rate
        assert r300k.effective_rate < r500k.effective_rate
        assert r500k.effective_rate < r1m.effective_rate

    def test_effective_rate_never_exceeds_standard(self):
        """Family effective rate should never exceed the standard 3.5% rate."""
        for value in [100000, 250000, 400000, 500000, 1000000, 10000000]:
            result = calculate_grest(Decimal(str(value)), is_family_transfer=True)
            assert result.effective_rate <= STANDARD_RATE


# ---------------------------------------------------------------------------
# Family transfer is always cheaper or equal to standard
# ---------------------------------------------------------------------------

class TestFamilyVsStandard:
    """Family transfer tax should always be <= standard rate tax."""

    @pytest.mark.parametrize("value", [
        "1", "1000", "50000", "100000", "250000",
        "300000", "400000", "500000", "1000000", "5000000",
    ])
    def test_family_leq_standard(self, value):
        standard = calculate_grest(Decimal(value), is_family_transfer=False)
        family = calculate_grest(Decimal(value), is_family_transfer=True)
        assert family.tax_amount <= standard.tax_amount


# ---------------------------------------------------------------------------
# GrEStResult dataclass defaults
# ---------------------------------------------------------------------------

class TestGrEStResultDefaults:
    """Verify GrEStResult default values."""

    def test_defaults(self):
        result = GrEStResult()
        assert result.grundstueckswert == Decimal("0.00")
        assert result.is_family_transfer is False
        assert result.tax_amount == Decimal("0.00")
        assert result.effective_rate == Decimal("0.00")
        assert result.tier_breakdown is None
        assert result.note == ""


# ---------------------------------------------------------------------------
# Input coercion (int / float / str passed as grundstueckswert)
# ---------------------------------------------------------------------------

class TestInputCoercion:
    """The calculator converts inputs to Decimal via str()."""

    def test_int_input(self):
        result = calculate_grest(100000, is_family_transfer=False)
        assert result.tax_amount == Decimal("3500.00")

    def test_float_input(self):
        result = calculate_grest(100000.0, is_family_transfer=False)
        assert result.tax_amount == Decimal("3500.00")

    def test_string_input(self):
        result = calculate_grest("100000", is_family_transfer=False)
        assert result.tax_amount == Decimal("3500.00")
