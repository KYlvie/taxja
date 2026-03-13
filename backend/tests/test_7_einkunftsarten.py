"""
Tests for the 7 Austrian Einkunftsarten (income types) implementation.

Validates:
1. IncomeCategory enum has exactly 7 values matching Austrian tax law
2. Rule-based classifier maps keywords to all 7 categories correctly
3. EA report service has income groups for all 7 categories
4. Bilanz report service has GuV income accounts for all 7 categories
5. Saldenliste service has account definitions for all 7 categories
6. No income category is orphaned (missing from reports)
7. Classifier income/expense path separation (booking.com edge case)
"""
import pytest
from decimal import Decimal
from enum import Enum
from types import SimpleNamespace

from app.models.transaction import IncomeCategory, ExpenseCategory, TransactionType
from app.services.rule_based_classifier import RuleBasedClassifier
from app.services.ea_report_service import INCOME_GROUPS
from app.services.bilanz_report_service import GUV_STRUCTURE
from app.services.saldenliste_service import KONTENPLAN_EA, KONTENPLAN_GMBH


# ── 1. Enum completeness ────────────────────────────────────────────────

EXPECTED_INCOME_CATEGORIES = {
    "agriculture",       # Nr.1 Land- und Forstwirtschaft
    "self_employment",   # Nr.2 Selbständige Arbeit
    "business",          # Nr.3 Gewerbebetrieb
    "employment",        # Nr.4 Nichtselbständige Arbeit
    "capital_gains",     # Nr.5 Kapitalvermögen
    "rental",            # Nr.6 Vermietung und Verpachtung
    "other_income",      # Nr.7 Sonstige Einkünfte
}


class TestIncomeCategoryEnum:
    def test_has_exactly_7_values(self):
        values = {c.value for c in IncomeCategory}
        assert len(values) == 7, f"Expected 7 income categories, got {len(values)}: {values}"

    def test_all_expected_values_present(self):
        values = {c.value for c in IncomeCategory}
        assert values == EXPECTED_INCOME_CATEGORIES, (
            f"Missing: {EXPECTED_INCOME_CATEGORIES - values}, "
            f"Extra: {values - EXPECTED_INCOME_CATEGORIES}"
        )

    def test_enum_is_str_enum(self):
        """IncomeCategory values must be usable as strings (for JSON serialization)."""
        for cat in IncomeCategory:
            assert isinstance(cat.value, str)
            assert cat == cat.value  # str Enum identity


# ── 2. Classifier keyword coverage ──────────────────────────────────────

class TestClassifierIncomeKeywords:
    """Every income category must have at least one keyword in INCOME_KEYWORDS."""

    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier()

    def test_all_7_categories_have_keywords(self, classifier):
        covered = set(classifier.INCOME_KEYWORDS.values())
        for cat in EXPECTED_INCOME_CATEGORIES:
            assert cat in covered, (
                f"Income category '{cat}' has no keywords in INCOME_KEYWORDS"
            )

    @pytest.mark.parametrize("description,expected_category", [
        # Nr.1 Agriculture
        ("Holzverkauf Waldgrundstück", "agriculture"),
        ("Ernte Obstbau 2026", "agriculture"),
        ("Imkerei Honigverkauf", "agriculture"),
        # Nr.2 Self-employment (Freiberufler)
        ("Honorar Beratung März", "self_employment"),
        ("Arzthonorar Ordination", "self_employment"),
        ("Gutachten Sachverständiger", "self_employment"),
        # Nr.3 Business (Gewerbebetrieb)
        ("Umsatz Tischlerei Q1", "business"),
        ("Provision Vermittlung", "business"),
        ("Erlös Warenverkauf", "business"),
        # Nr.4 Employment
        ("Gehalt März 2026", "employment"),
        ("Lohn Überstunden", "employment"),
        ("Pension Dezember", "employment"),
        ("Weihnachtsgeld 2026", "employment"),
        # Nr.5 Capital gains
        ("Dividende Erste Bank", "capital_gains"),
        ("Kursgewinn Aktien", "capital_gains"),
        ("Bitcoin Verkauf", "capital_gains"),
        ("Fondsausschüttung Q4", "capital_gains"),
        # Nr.6 Rental
        ("Mieteinnahme Wohnung Praterstraße", "rental"),
        ("Airbnb Auszahlung März", "rental"),
        ("Booking Auszahlung Februar", "rental"),
        ("Pachteinnahme Grundstück", "rental"),
        ("Ferienwohnung Einnahme", "rental"),
        # Nr.7 Other income
        ("Spekulationsgewinn Immobilie", "other_income"),
        ("Aufsichtsrat Vergütung", "other_income"),
        ("Veräußerungsgewinn Beteiligung", "other_income"),
    ])
    def test_income_classification(self, classifier, description, expected_category):
        txn = SimpleNamespace(
            type=TransactionType.INCOME,
            description=description,
        )
        result = classifier.classify(txn)
        assert result.category == expected_category, (
            f"'{description}' classified as '{result.category}', expected '{expected_category}'"
        )
        assert result.category_type == "income"
        assert result.confidence >= Decimal("0.5")

    def test_unknown_income_defaults_to_employment(self, classifier):
        """Unknown income descriptions should default to employment with low confidence."""
        txn = SimpleNamespace(
            type=TransactionType.INCOME,
            description="Sonstige Zahlung XYZ",
        )
        result = classifier.classify(txn)
        assert result.category == "employment"
        assert result.confidence <= Decimal("0.5")

    def test_empty_description_returns_none(self, classifier):
        txn = SimpleNamespace(type=TransactionType.INCOME, description="")
        result = classifier.classify(txn)
        assert result.category is None


# ── 3. Booking.com edge case: income vs expense ─────────────────────────

class TestBookingEdgeCase:
    """booking.com payout = rental income, booking.com charge = travel expense."""

    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier()

    def test_booking_income_is_rental(self, classifier):
        txn = SimpleNamespace(
            type=TransactionType.INCOME,
            description="Booking Auszahlung Ferienwohnung",
        )
        result = classifier.classify(txn)
        assert result.category == "rental"
        assert result.category_type == "income"

    def test_booking_expense_is_travel(self, classifier):
        txn = SimpleNamespace(
            type=TransactionType.EXPENSE,
            description="Booking.com Hotel Wien",
        )
        result = classifier.classify(txn)
        assert result.category == "travel"
        assert result.category_type == "expense"


# ── 4. Report service coverage ───────────────────────────────────────────

class TestEAReportIncomeGroups:
    """EA report INCOME_GROUPS must cover all 7 income categories."""

    def test_all_categories_covered(self):
        covered = set()
        for group in INCOME_GROUPS.values():
            for cat in group["categories"]:
                covered.add(cat.value)
        assert covered == EXPECTED_INCOME_CATEGORIES, (
            f"EA INCOME_GROUPS missing: {EXPECTED_INCOME_CATEGORIES - covered}"
        )

    def test_no_duplicate_categories(self):
        """Each income category should appear in exactly one group."""
        seen = []
        for key, group in INCOME_GROUPS.items():
            for cat in group["categories"]:
                assert cat.value not in seen, (
                    f"Category '{cat.value}' appears in multiple groups"
                )
                seen.append(cat.value)

    def test_all_groups_have_trilingual_labels(self):
        for key, group in INCOME_GROUPS.items():
            assert "label_de" in group, f"Group '{key}' missing label_de"
            assert "label_en" in group, f"Group '{key}' missing label_en"
            assert "label_zh" in group, f"Group '{key}' missing label_zh"


class TestBilanzReportIncomeAccounts:
    """Bilanz GuV income accounts must cover all 7 income categories."""

    def test_all_categories_covered(self):
        covered = set()
        for section in GUV_STRUCTURE:
            if section["type"] == "income":
                for cat in section["categories"]:
                    covered.add(cat.value)
        assert covered == EXPECTED_INCOME_CATEGORIES, (
            f"GuV GUV_STRUCTURE income missing: {EXPECTED_INCOME_CATEGORIES - covered}"
        )

    def test_all_income_sections_have_nr(self):
        for section in GUV_STRUCTURE:
            if section["type"] == "income":
                assert "nr" in section and section["nr"], (
                    f"Section '{section['key']}' missing nr"
                )


class TestSaldenlisteIncomeAccounts:
    """Saldenliste account plans must cover all 7 income categories."""

    def _get_covered_income_categories(self, plan):
        covered = set()
        for acct in plan:
            for cat in acct.income_categories:
                covered.add(cat.value)
        return covered

    def test_ea_plan_covers_all_categories(self):
        covered = self._get_covered_income_categories(KONTENPLAN_EA)
        assert covered == EXPECTED_INCOME_CATEGORIES, (
            f"EA Kontenplan missing: {EXPECTED_INCOME_CATEGORIES - covered}"
        )

    def test_gmbh_plan_covers_all_categories(self):
        covered = self._get_covered_income_categories(KONTENPLAN_GMBH)
        assert covered == EXPECTED_INCOME_CATEGORIES, (
            f"GmbH Kontenplan missing: {EXPECTED_INCOME_CATEGORIES - covered}"
        )

    def test_ea_income_accounts_are_kontenklasse_4(self):
        """All income accounts in EA plan must be Kontenklasse 4."""
        for acct in KONTENPLAN_EA:
            if acct.income_categories:
                assert acct.kontenklasse == 4, (
                    f"Income account {acct.konto} has kontenklasse {acct.kontenklasse}, expected 4"
                )

    def test_gmbh_income_accounts_are_kontenklasse_4(self):
        for acct in KONTENPLAN_GMBH:
            if acct.income_categories:
                assert acct.kontenklasse == 4, (
                    f"Income account {acct.konto} has kontenklasse {acct.kontenklasse}, expected 4"
                )


# ── 5. Cross-consistency ────────────────────────────────────────────────

class TestCrossConsistency:
    """Classifier output categories must be valid IncomeCategory values."""

    def test_classifier_keywords_are_valid_categories(self):
        classifier = RuleBasedClassifier()
        valid = {c.value for c in IncomeCategory}
        for kw, cat in classifier.INCOME_KEYWORDS.items():
            assert cat in valid, (
                f"Keyword '{kw}' maps to '{cat}' which is not a valid IncomeCategory"
            )

    def test_classifier_expense_keywords_are_valid_categories(self):
        classifier = RuleBasedClassifier()
        valid = {c.value for c in ExpenseCategory}
        for kw, cat in classifier.PRODUCT_KEYWORDS.items():
            assert cat in valid, (
                f"Product keyword '{kw}' maps to '{cat}' which is not a valid ExpenseCategory"
            )
