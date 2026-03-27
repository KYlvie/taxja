from datetime import date
from decimal import Decimal

from app.services.field_normalization import (
    normalize_amount,
    normalize_boolean_flag,
    normalize_currency,
    normalize_date,
    normalize_quantity,
    normalize_semantic_flags,
    normalize_vat_rate,
)


def test_normalize_quantity_accepts_integer_text_variants():
    assert normalize_quantity("3 Stück") == 3
    assert normalize_quantity("x2") == 2
    assert normalize_quantity("1,0") == 1


def test_normalize_quantity_rejects_fractional_values():
    assert normalize_quantity("1,5 Std") is None
    assert normalize_quantity(Decimal("2.5")) is None


def test_normalize_currency_maps_symbols_and_codes():
    assert normalize_currency("EUR 96,00") == "EUR"
    assert normalize_currency("$96.00") == "USD"
    assert normalize_currency("CHF 10.00") == "CHF"


def test_normalize_boolean_flag_handles_multilingual_values():
    assert normalize_boolean_flag("ja") is True
    assert normalize_boolean_flag("bezahlt") is True
    assert normalize_boolean_flag("nein") is False
    assert normalize_boolean_flag("offen") is False


def test_normalize_semantic_flags_detects_commercial_markers():
    flags = normalize_semantic_flags(
        "Reverse Charge - tax to be accounted for by the recipient",
        "storniert",
    )
    assert "reverse_charge" in flags
    assert "cancelled" in flags


def test_existing_core_normalizers_remain_compatible():
    assert normalize_amount("1.234,56") == Decimal("1234.56")
    assert normalize_vat_rate("0,20") == Decimal("20")
    assert normalize_date("19. Dez. 2024") == date(2024, 12, 19)


def test_normalize_amount_accepts_structured_payloads():
    assert normalize_amount({"total": 545.5, "currency": "EUR"}) == Decimal("545.5")
    assert normalize_amount({"amount": "96,00", "currency": "EUR"}) == Decimal("96.00")
