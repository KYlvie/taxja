"""Tests for L1k form service — Arbeitnehmerveranlagung mit Kindern."""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from datetime import date

from sqlalchemy.orm import Session

from app.services.l1k_form_service import (
    generate_l1k_form_data,
    FAMILIENBONUS_HALF_FACTOR,
)
from app.models.user import User

# Test constants matching 2026 fallback config
FAMILIENBONUS_UNDER_18 = Decimal("2000.16")
FAMILIENBONUS_18_PLUS = Decimal("700.08")
KINDERMEHRBETRAG_MAX = Decimal("700")
UNTERHALTSAB_FIRST_CHILD_ANNUAL = Decimal("456")  # 38 * 12

_TEST_DEDUCTION_CONFIG = {
    "familienbonus_under_18": 2000.16,
    "familienbonus_18_24": 700.08,
    "kindermehrbetrag": 700.00,
    "unterhaltsabsetzbetrag": {
        "first_child_monthly": 38.00,
        "second_child_monthly": 56.00,
        "third_plus_child_monthly": 75.00,
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_user(family_info=None, name="Test User", tax_number="12-345/6789"):
    user = Mock(spec=User)
    user.family_info = family_info
    user.name = name
    user.tax_number = tax_number
    return user


def _make_db():
    db = Mock(spec=Session)
    # TaxConfiguration query returns None → uses fallback
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def _field_by_kz(result, kz):
    """Return the field dict matching the given Kennzahl."""
    for f in result["fields"]:
        if f["kz"] == kz:
            return f
    raise KeyError(f"No field with kz={kz}")


# ── 1. Familienbonus Plus for children under 18 (EUR 2000/child) ────────────

class TestFamilienbonusUnder18:
    def test_single_child_under_18(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Anna", "birth_date": "2015-06-15", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["summary"]["children_under_18"] == 1
        assert result["summary"]["children_18_plus"] == 0
        # Full familienbonus = EUR 2000.16 (from DB config)
        kz220 = _field_by_kz(result, "220")
        assert kz220["value"] == 2000.16

    def test_two_children_under_18(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Anna", "birth_date": "2015-03-01", "shared_custody_pct": 100},
                {"name": "Ben", "birth_date": "2018-11-20", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["summary"]["children_under_18"] == 2
        kz220 = _field_by_kz(result, "220")
        assert kz220["value"] == 4000.32  # 2 * 2000.16

    def test_child_turns_18_on_dec_31_is_still_under_18(self):
        """A child born on 2008-01-01 turns 17 on 2025-01-01, is 17 at end of 2025."""
        user = _make_user(family_info={
            "children": [
                {"name": "Clara", "birth_date": "2008-01-01", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        assert result["summary"]["children_under_18"] == 1
        assert result["child_details"][0]["age"] == 17


# ── 2. Familienbonus Plus for children 18+ (EUR 650/child) ──────────────────

class TestFamilienbonus18Plus:
    def test_single_child_18_plus(self):
        user = _make_user(family_info={
            "children": [
                {"name": "David", "birth_date": "2005-03-15", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["summary"]["children_18_plus"] == 1
        assert result["summary"]["children_under_18"] == 0
        kz220 = _field_by_kz(result, "220")
        assert kz220["value"] == 700.08  # 18+ rate from DB config

    def test_child_exactly_18(self):
        """Child born 2007-12-31 is exactly 18 at end of 2025."""
        user = _make_user(family_info={
            "children": [
                {"name": "Eva", "birth_date": "2007-12-31", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        assert result["summary"]["children_18_plus"] == 1
        assert result["child_details"][0]["age"] == 18
        kz220 = _field_by_kz(result, "220")
        assert kz220["value"] == 700.08  # 18+ rate from DB config


# ── 3. Half Familienbonus for shared custody (50%) ──────────────────────────

class TestHalfFamilienbonus:
    def test_shared_custody_under_18(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Felix", "birth_date": "2015-05-10", "shared_custody_pct": 50},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        # Full amount field (kz 220) should be 0
        kz220 = _field_by_kz(result, "220")
        assert kz220["value"] == 0.0
        # Half amount field (kz 221) should be 1000.08 (2000.16 * 0.5)
        kz221 = _field_by_kz(result, "221")
        assert kz221["value"] == 1000.08

    def test_shared_custody_18_plus(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Greta", "birth_date": "2004-08-20", "shared_custody_pct": 50},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        kz220 = _field_by_kz(result, "220")
        assert kz220["value"] == 0.0
        kz221 = _field_by_kz(result, "221")
        assert kz221["value"] == 350.04  # 700.08 * 0.5

    def test_total_familienbonus_summary_includes_half(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Hans", "birth_date": "2015-01-01", "shared_custody_pct": 50},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        # summary total_familienbonus = full + half
        assert result["summary"]["total_familienbonus"] == 1000.08


# ── 4. Kindermehrbetrag (max EUR 550/child) ─────────────────────────────────

class TestKindermehrbetrag:
    def test_one_child_kindermehrbetrag(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Ida", "birth_date": "2016-04-01", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        kz222 = _field_by_kz(result, "222")
        assert kz222["value"] == 700.0
        assert result["summary"]["total_kindermehrbetrag"] == 700.0

    def test_three_children_kindermehrbetrag(self):
        user = _make_user(family_info={
            "children": [
                {"name": "A", "birth_date": "2010-01-01", "shared_custody_pct": 100},
                {"name": "B", "birth_date": "2012-01-01", "shared_custody_pct": 100},
                {"name": "C", "birth_date": "2014-01-01", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        kz222 = _field_by_kz(result, "222")
        assert kz222["value"] == 2100.0  # 3 * 700
        assert result["summary"]["total_kindermehrbetrag"] == 2100.0

    def test_per_child_kindermehrbetrag_in_details(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Jan", "birth_date": "2016-01-01", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        assert result["child_details"][0]["kindermehrbetrag"] == 700.0


# ── 5. Unterhaltsabsetzbetrag ───────────────────────────────────────────────

class TestUnterhaltsabsetzbetrag:
    def test_child_not_in_household(self):
        user = _make_user(family_info={
            "children": [
                {
                    "name": "Karl",
                    "birth_date": "2012-07-01",
                    "shared_custody_pct": 100,
                    "in_household": False,
                },
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        kz243 = _field_by_kz(result, "243")
        assert kz243["value"] == 456.0  # 38 * 12 (1st child)
        kz244 = _field_by_kz(result, "244")
        assert kz244["value"] == 1
        assert result["summary"]["total_unterhaltsabsetzbetrag"] == 456.0

    def test_child_in_household_no_unterhaltsab(self):
        user = _make_user(family_info={
            "children": [
                {
                    "name": "Lisa",
                    "birth_date": "2014-03-15",
                    "shared_custody_pct": 100,
                    "in_household": True,
                },
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        kz243 = _field_by_kz(result, "243")
        assert kz243["value"] == 0.0
        kz244 = _field_by_kz(result, "244")
        assert kz244["value"] == 0

    def test_default_in_household_is_true(self):
        """When in_household is not specified, it defaults to True (no Unterhaltsab)."""
        user = _make_user(family_info={
            "children": [
                {"name": "Max", "birth_date": "2013-09-01", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        kz243 = _field_by_kz(result, "243")
        assert kz243["value"] == 0.0

    def test_multiple_children_mixed_household(self):
        user = _make_user(family_info={
            "children": [
                {"name": "A", "birth_date": "2012-01-01", "shared_custody_pct": 100, "in_household": True},
                {"name": "B", "birth_date": "2014-01-01", "shared_custody_pct": 100, "in_household": False},
                {"name": "C", "birth_date": "2016-01-01", "shared_custody_pct": 100, "in_household": False},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        kz243 = _field_by_kz(result, "243")
        assert kz243["value"] == 1128.0  # 1st: 38*12=456 + 2nd: 56*12=672
        kz244 = _field_by_kz(result, "244")
        assert kz244["value"] == 2
        assert result["summary"]["total_unterhaltsabsetzbetrag"] == 1128.0


# ── 6. No children scenario ────────────────────────────────────────────────

class TestNoChildren:
    def test_no_family_info(self):
        user = _make_user(family_info=None)
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["summary"]["total_children"] == 0
        assert result["summary"]["children_under_18"] == 0
        assert result["summary"]["children_18_plus"] == 0
        assert result["summary"]["total_familienbonus"] == 0.0
        assert result["summary"]["total_kindermehrbetrag"] == 0.0
        assert result["summary"]["total_unterhaltsabsetzbetrag"] == 0.0
        assert result["child_details"] == []

    def test_empty_family_info(self):
        user = _make_user(family_info={})
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        assert result["summary"]["total_children"] == 0

    def test_empty_children_list(self):
        user = _make_user(family_info={"children": []})
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        assert result["summary"]["total_children"] == 0

    def test_all_fields_zero_when_no_children(self):
        user = _make_user(family_info={})
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        for f in result["fields"]:
            assert f["value"] == 0 or f["value"] == 0.0


# ── 7. Mixed ages (some under 18, some over) ───────────────────────────────

class TestMixedAges:
    def test_two_under_18_one_over(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Young1", "birth_date": "2015-01-15", "shared_custody_pct": 100},
                {"name": "Young2", "birth_date": "2017-06-20", "shared_custody_pct": 100},
                {"name": "Adult1", "birth_date": "2003-02-10", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["summary"]["children_under_18"] == 2
        assert result["summary"]["children_18_plus"] == 1
        assert result["summary"]["total_children"] == 3
        # Full bonus: 2*2000.16 + 1*700.08 = 4700.40
        kz220 = _field_by_kz(result, "220")
        assert kz220["value"] == 4700.4

    def test_mixed_ages_with_shared_custody(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Under18Full", "birth_date": "2015-03-01", "shared_custody_pct": 100},
                {"name": "Under18Half", "birth_date": "2016-07-01", "shared_custody_pct": 50},
                {"name": "Over18Full", "birth_date": "2004-11-01", "shared_custody_pct": 100},
                {"name": "Over18Half", "birth_date": "2005-05-01", "shared_custody_pct": 50},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["summary"]["children_under_18"] == 2
        assert result["summary"]["children_18_plus"] == 2
        # Full: 2000.16 (under18full) + 700.08 (over18full) = 2700.24
        kz220 = _field_by_kz(result, "220")
        assert kz220["value"] == 2700.24
        # Half: 1000.08 (under18half) + 350.04 (over18half) = 1350.12
        kz221 = _field_by_kz(result, "221")
        assert kz221["value"] == 1350.12
        # Total in summary = 2700.24 + 1350.12 = 4050.36
        assert result["summary"]["total_familienbonus"] == 4050.36

    def test_child_details_have_correct_ages(self):
        user = _make_user(family_info={
            "children": [
                {"name": "Young", "birth_date": "2020-06-15", "shared_custody_pct": 100},
                {"name": "Old", "birth_date": "2000-01-01", "shared_custody_pct": 100},
            ]
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        details = {d["name"]: d for d in result["child_details"]}
        assert details["Young"]["age"] == 5
        assert details["Old"]["age"] == 25


# ── 8. Fallback to num_children when no per-child data ─────────────────────

class TestFallbackNumChildren:
    def test_num_children_fallback_creates_entries(self):
        user = _make_user(family_info={"num_children": 3})
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["summary"]["total_children"] == 3
        assert len(result["child_details"]) == 3

    def test_fallback_children_have_no_age(self):
        user = _make_user(family_info={"num_children": 2})
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        for detail in result["child_details"]:
            assert detail["age"] is None

    def test_fallback_uses_18_plus_rate(self):
        """Without birth_date, age is None so children count as 18+ (EUR 700.08)."""
        user = _make_user(family_info={"num_children": 2})
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["summary"]["children_18_plus"] == 2
        assert result["summary"]["children_under_18"] == 0
        kz220 = _field_by_kz(result, "220")
        assert kz220["value"] == 1400.16  # 2 * 700.08

    def test_fallback_names_are_generated(self):
        user = _make_user(family_info={"num_children": 2})
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        names = [d["name"] for d in result["child_details"]]
        assert names == ["Kind 1", "Kind 2"]

    def test_fallback_full_custody(self):
        user = _make_user(family_info={"num_children": 1})
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["child_details"][0]["shared_custody_pct"] == 100
        kz221 = _field_by_kz(result, "221")
        assert kz221["value"] == 0.0  # no half amounts

    def test_num_children_zero_produces_no_children(self):
        user = _make_user(family_info={"num_children": 0})
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)

        assert result["summary"]["total_children"] == 0

    def test_existing_children_list_overrides_num_children(self):
        """If both children list and num_children exist, the list takes precedence."""
        user = _make_user(family_info={
            "num_children": 5,
            "children": [
                {"name": "Only", "birth_date": "2015-01-01", "shared_custody_pct": 100},
            ],
        })
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        assert result["summary"]["total_children"] == 1


# ── Metadata and structure ──────────────────────────────────────────────────

class TestFormMetadata:
    def test_form_type(self):
        user = _make_user(family_info=None)
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        assert result["form_type"] == "L1k"

    def test_tax_year_passed_through(self):
        user = _make_user(family_info=None)
        result = generate_l1k_form_data(_make_db(), user, tax_year=2024)
        assert result["tax_year"] == 2024

    def test_user_name_and_tax_number(self):
        user = _make_user(family_info=None, name="Maria Huber", tax_number="99-999/0000")
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        assert result["user_name"] == "Maria Huber"
        assert result["tax_number"] == "99-999/0000"

    def test_has_disclaimers(self):
        user = _make_user(family_info=None)
        result = generate_l1k_form_data(_make_db(), user, tax_year=2025)
        assert "disclaimer_de" in result
        assert "disclaimer_en" in result
