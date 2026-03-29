"""
Insurance suggestion logic for Phase 2-4.

Standalone service functions for:
- Phase 2: Auto-actions (Kuendigung, Praemienaenderung, SEPA, Jahresbestaetigung)
- Phase 3: Suggestion confirm with user input/override
- Phase 4: Arbeitszimmer + Property context auto-fill

These functions are pure logic — no DB access, no side-effects.
The pipeline orchestrator calls them and persists the results.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List
import re

from app.services.insurance_rules import (
    INSURANCE_NEEDS_USER_INPUT,
    INSURANCE_NO_INPUT_100_PCT,
    INSURANCE_NOT_DEDUCTIBLE_2021,
    INSURANCE_AUTO_ACTION_SUBTYPES,
    INSURANCE_ARCHIVE_ONLY_SUBTYPES,
)


# ══════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════

# German frequency name → payments per year
FREQUENCY_MAP: Dict[str, int] = {
    "monatlich": 12,
    "vierteljaehrlich": 4,
    "vierteljährlich": 4,
    "halbjaehrlich": 2,
    "halbjährlich": 2,
    "jaehrlich": 1,
    "jährlich": 1,
    # English aliases
    "monthly": 12,
    "quarterly": 4,
    "semi_annual": 2,
    "annually": 1,
}

# Frequency name → RecurrenceFrequency enum value
FREQUENCY_TO_ENUM: Dict[str, str] = {
    "monatlich": "monthly",
    "monthly": "monthly",
    "vierteljaehrlich": "quarterly",
    "vierteljährlich": "quarterly",
    "quarterly": "quarterly",
    "halbjaehrlich": "semi_annual",
    "halbjährlich": "semi_annual",
    "semi_annual": "semi_annual",
    "jaehrlich": "annually",
    "jährlich": "annually",
    "annually": "annually",
}


def _normalize_polizze_nr(nr: str) -> str:
    """Normalize polizze number for comparison: strip spaces/dashes, lowercase."""
    if not nr:
        return ""
    return re.sub(r"[\s\-/]", "", nr).lower()


def _amounts_match(a: float, b: float, tolerance_pct: float = 2.0) -> bool:
    """Check if two amounts match within a percentage tolerance."""
    if a == 0 and b == 0:
        return True
    if a == 0 or b == 0:
        return False
    diff_pct = abs(a - b) / max(abs(a), abs(b)) * 100
    return diff_pct <= tolerance_pct


# ══════════════════════════════════════════════
# Phase 4: Suggestion status resolution
# ══════════════════════════════════════════════

def resolve_insurance_suggestion_status(
    insurance_subtype: str,
    tax_year: int = 2024,
    user_az_m2: Optional[float] = None,
    user_nutzflaeche_m2: Optional[float] = None,
    linked_property_is_rented: bool = False,
) -> Dict[str, Any]:
    """
    Determine suggestion status and input requirements for an insurance document.

    Returns dict with:
      - status: "pending" | "needs_input" | "auto_applied" | "not_deductible"
      - is_deductible: bool
      - deductible_pct: Optional[float]  (1.0, 0.2308, or None if needs input)
      - input_fields: List[dict]  (empty if no input needed)
      - deduction_reason: str
      - tax_form: str  ("E1a" or "E1b")
    """
    result: Dict[str, Any] = {
        "status": "needs_input",
        "is_deductible": True,
        "deductible_pct": None,
        "input_fields": [],
        "deduction_reason": "",
        "tax_form": "E1a",
    }

    # ── Not deductible since 2021 ──
    if insurance_subtype in INSURANCE_NOT_DEDUCTIBLE_2021 and tax_year >= 2021:
        result["status"] = "not_deductible"
        result["is_deductible"] = False
        result["deductible_pct"] = 0.0
        result["deduction_reason"] = (
            f"Seit 2021 nicht mehr als Sonderausgaben absetzbar "
            f"(§ 18 Abs 1 Z 2 EStG Neufassung)"
        )
        return result

    # ── Action subtypes — no financial deduction ──
    if insurance_subtype in INSURANCE_AUTO_ACTION_SUBTYPES:
        result["status"] = "auto_applied"
        result["is_deductible"] = False
        result["deductible_pct"] = 0.0
        result["deduction_reason"] = "Verwaltungsdokument, keine Betriebsausgabe"
        return result

    # ── Archive only (SEPA) ──
    if insurance_subtype in INSURANCE_ARCHIVE_ONLY_SUBTYPES:
        result["status"] = "auto_applied"
        result["is_deductible"] = False
        result["deductible_pct"] = 0.0
        result["deduction_reason"] = "Zahlungsbeleg, Archivierung"
        return result

    # ── 100% deductible without input ──
    if insurance_subtype in INSURANCE_NO_INPUT_100_PCT:
        result["status"] = "auto_applied"
        result["deductible_pct"] = 1.0
        result["deduction_reason"] = "100% Betriebsausgabe (E1a)"
        return result

    # ── Gebäudeversicherung — property context ──
    if insurance_subtype == "gebaeudeversicherung":
        if linked_property_is_rented:
            result["status"] = "pending"
            result["deductible_pct"] = 1.0
            result["tax_form"] = "E1b"
            result["deduction_reason"] = (
                "100% Werbungskosten bei vermieteter Immobilie (E1b)"
            )
            return result
        else:
            result["status"] = "needs_input"
            result["deductible_pct"] = None
            result["input_fields"] = [
                {
                    "field": "property_link",
                    "type": "property_selector",
                    "label": "Zugehörige Immobilie auswählen",
                },
            ]
            result["deduction_reason"] = "Immobilie zuordnen für Absetzbarkeit"
            return result

    # ── Haushaltsversicherung — AZ context ──
    if insurance_subtype == "haushaltsversicherung":
        if user_az_m2 and user_nutzflaeche_m2 and user_nutzflaeche_m2 > 0:
            az_pct = Decimal(str(user_az_m2)) / Decimal(str(user_nutzflaeche_m2))
            az_pct_rounded = float(
                (az_pct * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )
            result["status"] = "pending"
            result["deductible_pct"] = float(
                az_pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            )
            result["deduction_reason"] = (
                f"Arbeitszimmer-Anteil: {az_pct_rounded}% "
                f"({user_az_m2}m² / {user_nutzflaeche_m2}m²)"
            )
            result["input_fields"] = [
                {
                    "field": "arbeitszimmer_anteil",
                    "type": "percentage",
                    "label": "Arbeitszimmer-Anteil (%)",
                    "auto_filled": True,
                    "auto_value": az_pct_rounded,
                },
            ]
            return result
        else:
            result["status"] = "needs_input"
            result["deductible_pct"] = None
            result["input_fields"] = INSURANCE_NEEDS_USER_INPUT.get(
                "haushaltsversicherung", []
            )
            result["deduction_reason"] = (
                "Arbeitszimmer-Daten erforderlich für anteilige Absetzung"
            )
            return result

    # ── Other needs_user_input subtypes (KFZ, Rechtsschutz) ──
    if insurance_subtype in INSURANCE_NEEDS_USER_INPUT:
        result["status"] = "needs_input"
        result["deductible_pct"] = None
        result["input_fields"] = INSURANCE_NEEDS_USER_INPUT[insurance_subtype]
        result["deduction_reason"] = (
            "Beruflicher/geschäftlicher Anteil muss angegeben werden"
        )
        return result

    # ── Fallback: unknown subtype, needs manual review ──
    result["status"] = "needs_input"
    result["deductible_pct"] = None
    result["deduction_reason"] = "Manuelle Prüfung erforderlich"
    return result


# ══════════════════════════════════════════════
# Phase 2: Auto-actions
# ══════════════════════════════════════════════

def resolve_kuendigung_action(
    polizze_nr: str,
    end_date: str,
    existing_recurrings: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Match Kuendigung to existing recurring and return end action.

    Returns dict with:
      - action: "end_recurring"
      - recurring_id: matched recurring ID
      - end_date: the termination date
      - polizze_nr: matched polizze number
    Or None if no match found.
    """
    if not polizze_nr:
        return None

    norm_nr = _normalize_polizze_nr(polizze_nr)

    for rec in existing_recurrings:
        rec_nr = _normalize_polizze_nr(rec.get("polizze_nr", ""))
        if rec_nr and rec_nr == norm_nr:
            return {
                "action": "end_recurring",
                "recurring_id": rec["id"],
                "end_date": end_date,
                "polizze_nr": polizze_nr,
            }

    return None


def resolve_praemienaenderung_action(
    polizze_nr: str,
    new_amount: float,
    effective_date: str,
    existing_recurrings: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Match Praemienaenderung to existing recurring and return update action.

    Returns dict with:
      - action: "update_recurring"
      - recurring_id: matched recurring ID
      - new_amount: the new premium amount
      - effective_date: when the change takes effect
      - polizze_nr: matched polizze number
      - old_amount: previous amount from the recurring
    Or None if no match found.
    """
    if not polizze_nr:
        return None

    norm_nr = _normalize_polizze_nr(polizze_nr)

    for rec in existing_recurrings:
        rec_nr = _normalize_polizze_nr(rec.get("polizze_nr", ""))
        if rec_nr and rec_nr == norm_nr:
            return {
                "action": "update_recurring",
                "recurring_id": rec["id"],
                "new_amount": new_amount,
                "effective_date": effective_date,
                "polizze_nr": polizze_nr,
                "old_amount": rec.get("amount"),
            }

    return None


def resolve_sepa_action(
    insurer_name: str,
    amount: float,
    polizze_nr: Optional[str],
    existing_recurrings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Determine SEPA action: link to existing recurring or create single expense.

    Returns dict with:
      - should_auto_link: bool (True if matched to existing recurring)
      - should_create_single_expense: bool (True if no match found)
      - recurring_id: Optional[int] (matched recurring ID)
      - match_reason: str (why it matched or didn't)
    """
    result: Dict[str, Any] = {
        "should_auto_link": False,
        "should_create_single_expense": False,
        "recurring_id": None,
        "match_reason": "",
    }

    # Try polizze_nr match first (strongest signal)
    if polizze_nr:
        norm_nr = _normalize_polizze_nr(polizze_nr)
        for rec in existing_recurrings:
            rec_nr = _normalize_polizze_nr(rec.get("polizze_nr", ""))
            if rec_nr and rec_nr == norm_nr:
                result["should_auto_link"] = True
                result["recurring_id"] = rec["id"]
                result["match_reason"] = f"Polizze-Nr. Übereinstimmung: {polizze_nr}"
                return result

    # Try insurer_name + amount fuzzy match
    if insurer_name and amount:
        insurer_lower = insurer_name.lower()
        for rec in existing_recurrings:
            rec_desc = (rec.get("description", "") or "").lower()
            rec_vendor = (rec.get("vendor", "") or "").lower()
            rec_amount = rec.get("amount", 0)

            # Fuzzy name match: insurer name appears in description or vendor
            name_match = (
                insurer_lower in rec_desc
                or insurer_lower in rec_vendor
                or rec_vendor in insurer_lower
            )
            amount_match = _amounts_match(amount, float(rec_amount))

            if name_match and amount_match:
                result["should_auto_link"] = True
                result["recurring_id"] = rec["id"]
                result["match_reason"] = (
                    f"Versicherer + Betrag Übereinstimmung: "
                    f"{insurer_name}, EUR {amount}"
                )
                return result

    # No match — create single expense
    result["should_create_single_expense"] = True
    result["match_reason"] = "Kein zugehöriger Dauerauftrag gefunden"
    return result


def resolve_jahresbestaetigung(
    annual_premium: float,
    frequency: Optional[str],
) -> Dict[str, Any]:
    """
    Derive payment_amount from annual premium and frequency.

    Returns dict with:
      - annual_premium: float
      - frequency: Optional[str] (normalized)
      - frequency_enum: Optional[str] (RecurrenceFrequency value)
      - payments_per_year: Optional[int]
      - payment_amount: Optional[float] (per-period amount, or None if no frequency)
    """
    result: Dict[str, Any] = {
        "annual_premium": annual_premium,
        "frequency": frequency,
        "frequency_enum": None,
        "payments_per_year": None,
        "payment_amount": None,
    }

    if not frequency:
        return result

    freq_lower = frequency.lower().strip()
    payments_per_year = FREQUENCY_MAP.get(freq_lower)

    if payments_per_year is None:
        return result

    result["payments_per_year"] = payments_per_year
    result["frequency_enum"] = FREQUENCY_TO_ENUM.get(freq_lower)

    # Compute per-period amount with proper rounding
    payment = Decimal(str(annual_premium)) / Decimal(str(payments_per_year))
    result["payment_amount"] = float(
        payment.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    return result


# ══════════════════════════════════════════════
# Phase 3: User input / overrides
# ══════════════════════════════════════════════

def apply_user_overrides(
    suggestion_data: Dict[str, Any],
    business_use_percentage: Optional[float] = None,
    beruflicher_anteil: Optional[float] = None,
    arbeitszimmer_anteil: Optional[float] = None,
    override_amount: Optional[float] = None,
    override_frequency: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply user input/overrides to suggestion data and compute final deductible_pct.

    Override precedence: user override > AZ auto-fill > OCR extracted > default

    Returns updated suggestion_data with:
      - deductible_pct: float (0.0-1.0)
      - override_applied: bool
      - override_details: dict of what was overridden
    """
    result = dict(suggestion_data)
    result["override_applied"] = False
    result["override_details"] = {}

    # ── Percentage overrides (convert from % to ratio 0-1) ──
    if business_use_percentage is not None:
        pct = Decimal(str(business_use_percentage)) / Decimal("100")
        result["deductible_pct"] = float(
            pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        )
        result["override_applied"] = True
        result["override_details"]["business_use_percentage"] = business_use_percentage

    elif beruflicher_anteil is not None:
        pct = Decimal(str(beruflicher_anteil)) / Decimal("100")
        result["deductible_pct"] = float(
            pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        )
        result["override_applied"] = True
        result["override_details"]["beruflicher_anteil"] = beruflicher_anteil

    elif arbeitszimmer_anteil is not None:
        pct = Decimal(str(arbeitszimmer_anteil)) / Decimal("100")
        result["deductible_pct"] = float(
            pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        )
        result["override_applied"] = True
        result["override_details"]["arbeitszimmer_anteil"] = arbeitszimmer_anteil

    # ── Amount / frequency overrides ──
    if override_amount is not None:
        result["payment_amount"] = override_amount
        result["override_applied"] = True
        result["override_details"]["override_amount"] = override_amount

    if override_frequency is not None:
        freq_lower = override_frequency.lower().strip()
        result["frequency"] = override_frequency
        result["frequency_enum"] = FREQUENCY_TO_ENUM.get(freq_lower)
        result["override_applied"] = True
        result["override_details"]["override_frequency"] = override_frequency

    # Update status from needs_input to pending if we got the input
    if result.get("status") == "needs_input" and result.get("deductible_pct") is not None:
        result["status"] = "pending"

    return result


def check_polizze_dedup(
    polizze_nr: str,
    existing_recurrings: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Check if a recurring already exists for this polizze_nr.

    Returns the existing recurring dict if found, None otherwise.
    """
    if not polizze_nr:
        return None

    norm_nr = _normalize_polizze_nr(polizze_nr)

    for rec in existing_recurrings:
        rec_nr = _normalize_polizze_nr(rec.get("polizze_nr", ""))
        if rec_nr and rec_nr == norm_nr:
            return rec

    return None
