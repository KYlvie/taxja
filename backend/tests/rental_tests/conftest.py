"""
Shared fixtures for rental module tests.
All tests use DI Maria Steiner as tenant with Arbeitszimmer 18m²/78m².
"""
import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import MagicMock
from types import SimpleNamespace


# ──────────────────────────────────────────────
# Pytest markers
# ──────────────────────────────────────────────
def pytest_configure(config):
    config.addinivalue_line("markers", "p0: critical tests that must pass")
    config.addinivalue_line("markers", "p1: important tests")
    config.addinivalue_line("markers", "p2: nice-to-have tests")


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
AZ_M2 = Decimal("18.00")
NUTZFLAECHE_M2 = Decimal("78.00")
AZ_RATIO = Decimal("0.2308")  # 18/78 rounded to 4 decimal places
AZ_PCT = Decimal("23.08")

# Old rent (Jan-Mar 2024)
HM_OLD = Decimal("620.00")
BK_AKONTO = Decimal("185.00")
UST_OLD = Decimal("62.00")
MIETE_OLD = Decimal("867.00")  # 620 + 185 + 62

# New rent (Apr+ 2024, after Indexanpassung)
HM_NEW = Decimal("691.29")
UST_NEW = Decimal("69.13")
MIETE_NEW = Decimal("945.42")  # 691.29 + 185 + 69.13

# BK
BK_NACHZAHLUNG = Decimal("142.35")
BK_GUTHABEN = Decimal("87.60")
BK_GH_AZ_INCOME = (BK_GUTHABEN * AZ_RATIO).quantize(Decimal("0.01"))  # ~€20.23

# Thermenwartung
THERMEN_BRUTTO = Decimal("198.00")

# Kaution
KAUTION = Decimal("1860.00")

# Tolerance for decimal comparisons
TOLERANCE = Decimal("0.02")


# ──────────────────────────────────────────────
# Mock User (with Arbeitszimmer)
# ──────────────────────────────────────────────
@pytest.fixture
def user_with_az():
    """DI Maria Steiner — tenant with Arbeitszimmer, Mittelpunkt=True."""
    user = MagicMock()
    user.id = 1
    user.arbeitszimmer_m2 = AZ_M2
    user.nutzflaeche_m2 = NUTZFLAECHE_M2
    user.arbeitszimmer_mittelpunkt = True
    user.employer_telearbeit_tage = None
    user.employer_telearbeit_pauschale = None
    user.employment_type = "self_employed"
    return user


@pytest.fixture
def user_without_az():
    """User without Arbeitszimmer configured."""
    user = MagicMock()
    user.id = 2
    user.arbeitszimmer_m2 = None
    user.nutzflaeche_m2 = None
    user.arbeitszimmer_mittelpunkt = None
    user.employer_telearbeit_tage = 45
    user.employer_telearbeit_pauschale = Decimal("135.00")
    user.employment_type = "self_employed"
    return user


@pytest.fixture
def user_az_not_mittelpunkt():
    """User with Arbeitszimmer but NOT Mittelpunkt — €1,250 annual cap applies."""
    user = MagicMock()
    user.id = 3
    user.arbeitszimmer_m2 = AZ_M2
    user.nutzflaeche_m2 = NUTZFLAECHE_M2
    user.arbeitszimmer_mittelpunkt = False
    user.employer_telearbeit_tage = None
    user.employer_telearbeit_pauschale = None
    user.employment_type = "self_employed"
    return user


@pytest.fixture
def user_az_large_ratio():
    """User with AZ > 50% — should trigger soft warning but not block."""
    user = MagicMock()
    user.id = 4
    user.arbeitszimmer_m2 = Decimal("25.00")
    user.nutzflaeche_m2 = Decimal("40.00")  # 62.5%
    user.arbeitszimmer_mittelpunkt = True
    user.employment_type = "self_employed"
    return user


# ──────────────────────────────────────────────
# OCR Result Builders
# ──────────────────────────────────────────────
def build_ocr_result(
    doc_type: str = "INVOICE",
    rental_subtype: str = None,
    amount: Decimal = None,
    date_str: str = "2024-01-15",
    description: str = "",
    vendor: str = "",
    contract_metadata: dict = None,
    expense_category: str = None,
    abrechnungsjahr: int = None,
    property_address: str = "Landstrasser Hauptstrasse 98/3, 1030 Wien",
    month: int = None,
    year: int = None,
):
    """Build a mock ocr_result dict matching the system's expected format."""
    result = {
        "document_type": doc_type,
        "amount": str(amount) if amount else None,
        "date": date_str,
        "description": description,
        "vendor": vendor,
        "confidence": 0.92,
    }

    if rental_subtype:
        result["_rental_subtype"] = rental_subtype

    if contract_metadata:
        result["_contract_metadata"] = contract_metadata

    if expense_category:
        result["expense_category"] = expense_category

    if abrechnungsjahr:
        result["abrechnungsjahr"] = abrechnungsjahr

    if property_address:
        result["property_address"] = property_address

    if month:
        result["month"] = month

    if year:
        result["year"] = year

    return result


@pytest.fixture
def ocr_mietvertrag():
    """Mietvertrag — rental contract, user is tenant."""
    return build_ocr_result(
        doc_type="RENTAL_CONTRACT",
        rental_subtype="mietvertrag",
        description="Mietvertrag Landstrasser Hauptstrasse 98/3",
        contract_metadata={
            "monthly_rent": str(MIETE_OLD),
            "hauptmietzins": str(HM_OLD),
            "betriebskosten": str(BK_AKONTO),
            "ust": str(UST_OLD),
            "kaution": str(KAUTION),
            "tenant_name": "DI Maria Steiner",
            "landlord_name": "Ing. Thomas Gruber",
            "property_address": "Landstrasser Hauptstrasse 98/3, 1030 Wien",
            "mietbeginn": "2021-04-01",
            "arbeitszimmer_m2": str(AZ_M2),
            "nutzflaeche_m2": str(NUTZFLAECHE_M2),
        },
    )


@pytest.fixture
def ocr_kaution():
    """Kautionsbestätigung — must NOT create transaction."""
    return build_ocr_result(
        doc_type="RENTAL_CONTRACT",
        rental_subtype="kaution",
        amount=KAUTION,
        description="Kautionsbestaetigung EUR 1.860,00",
        date_str="2021-03-25",
    )


@pytest.fixture
def ocr_uebergabeprotokoll():
    """Übergabeprotokoll — must NOT create transaction."""
    return build_ocr_result(
        doc_type="RENTAL_CONTRACT",
        rental_subtype="uebergabeprotokoll",
        description="Uebergabeprotokoll Einzug 01.04.2021",
        date_str="2021-04-01",
    )


@pytest.fixture
def ocr_miete_jan():
    """Monthly rent invoice — January 2024 (old amount)."""
    return build_ocr_result(
        doc_type="INVOICE",
        rental_subtype="miete",
        amount=MIETE_OLD,
        date_str="2024-01-01",
        description="Mietzinsvorschreibung Jaenner 2024",
        vendor="Immobilien Treuhand GmbH",
        expense_category="RENT",
        month=1,
        year=2024,
    )


@pytest.fixture
def ocr_miete_apr():
    """Monthly rent invoice — April 2024 (new amount after Indexanpassung)."""
    return build_ocr_result(
        doc_type="INVOICE",
        rental_subtype="miete",
        amount=MIETE_NEW,
        date_str="2024-04-01",
        description="Mietzinsvorschreibung April 2024",
        vendor="Immobilien Treuhand GmbH",
        expense_category="RENT",
        month=4,
        year=2024,
    )


@pytest.fixture
def ocr_bk_nachzahlung():
    """BK-Abrechnung 2023 — Nachzahlung €142.35."""
    return build_ocr_result(
        doc_type="BETRIEBSKOSTENABRECHNUNG",
        rental_subtype="nachzahlung",
        amount=BK_NACHZAHLUNG,
        date_str="2024-04-30",
        description="Betriebskostenabrechnung 2023 Nachzahlung",
        vendor="Immobilien Treuhand GmbH",
        expense_category="RENT",
        abrechnungsjahr=2023,
    )


@pytest.fixture
def ocr_bk_guthaben():
    """BK-Abrechnung 2022 — Guthaben €87.60."""
    return build_ocr_result(
        doc_type="BETRIEBSKOSTENABRECHNUNG",
        rental_subtype="guthaben",
        amount=BK_GUTHABEN,
        date_str="2024-04-30",
        description="Betriebskostenabrechnung 2022 Guthaben",
        vendor="Immobilien Treuhand GmbH",
        abrechnungsjahr=2022,
    )


@pytest.fixture
def ocr_thermenwartung():
    """Thermenwartung invoice — €198.00 brutto."""
    return build_ocr_result(
        doc_type="INVOICE",
        amount=THERMEN_BRUTTO,
        date_str="2024-10-15",
        description="Gastherme Jahreswartung und Abgasmessung",
        vendor="Installationen Hofer GmbH",
        expense_category="MAINTENANCE",
    )


@pytest.fixture
def ocr_indexanpassung():
    """Rent increase notice — not a transaction, triggers recurring update."""
    return build_ocr_result(
        doc_type="RENTAL_CONTRACT",
        rental_subtype="indexanpassung",
        description="Anpassung des Hauptmietzinses gemaess VPI 2020",
        date_str="2024-02-01",
        contract_metadata={
            "old_hauptmietzins": str(HM_OLD),
            "new_hauptmietzins": str(HM_NEW),
            "old_gesamtmiete": str(MIETE_OLD),
            "new_gesamtmiete": str(MIETE_NEW),
            "effective_date": "2024-04-01",
        },
    )


# ──────────────────────────────────────────────
# Helper assertions
# ──────────────────────────────────────────────
def assert_amount_close(actual, expected, msg=""):
    """Assert two Decimal amounts are within TOLERANCE."""
    actual = Decimal(str(actual))
    expected = Decimal(str(expected))
    diff = abs(actual - expected)
    assert diff <= TOLERANCE, (
        f"Amount mismatch{' (' + msg + ')' if msg else ''}: "
        f"actual={actual}, expected={expected}, diff={diff}, tolerance={TOLERANCE}"
    )


def assert_split_correct(deductible, private, total, ratio, msg=""):
    """Assert line item split is correct: deductible + private = total, deductible ≈ total × ratio."""
    deductible = Decimal(str(deductible))
    private = Decimal(str(private))
    total = Decimal(str(total))

    # Sum must equal total
    assert_amount_close(deductible + private, total, f"sum check - {msg}")

    # Deductible must be close to total × ratio
    expected_deductible = (total * ratio).quantize(Decimal("0.01"))
    assert_amount_close(deductible, expected_deductible, f"ratio check - {msg}")
