"""
Step 3: Transaction Classification Rule Engine.

Deterministic rules that override AI judgment for known document types.
This is the FINAL authority on what gets created in the system.

Data flow:
  Step 1 (Vision) → perception: document_type, gross_amount, vat_amount, issuer, recipient
  Step 2 (LLM)    → judgment: direction, is_asset, asset_type, is_gwg, tax_form
  Step 3 (Rules)   → THIS FILE: transaction_type, corrected direction, corrected asset_type

Design principle: AI handles ambiguity, rules handle certainty.
  - Insurance is ALWAYS expense, NEVER asset → rule
  - SVS is ALWAYS expense → rule
  - GWG ≤ €1,000 netto → rule
  - PKW vs E-Auto distinction → AI (Step 2) with rule validation
"""
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Transaction types that the pipeline understands
TRANSACTION_TYPE_EXPENSE = "expense"
TRANSACTION_TYPE_INCOME = "income"
TRANSACTION_TYPE_ASSET_ACQUISITION = "asset_acquisition"
TRANSACTION_TYPE_GWG = "gwg"              # KZ 9130 — sofort absetzbar
TRANSACTION_TYPE_ARCHIVE_ONLY = "archive_only"
TRANSACTION_TYPE_RECURRING = "recurring"
TRANSACTION_TYPE_LOAN = "loan"
TRANSACTION_TYPE_PROPERTY = "property"


# Document types that are ALWAYS expense, no exceptions
_ALWAYS_EXPENSE_DOC_TYPES = {
    "versicherungspolizze",
    "svs_vorschreibung",
    "svs_nachbemessung",
    "grundsteuerbescheid",
    "kirchenbeitrag",
    "spendenbestaetigung",
}

# Document types that should never create transactions
_ARCHIVE_ONLY_DOC_TYPES = {
    "einkommensteuerbescheid",
    "e1_form",
    "bank_statement",
    "tilgungsplan",
    "fahrtenbuch",
    "homeoffice_nachweis",
}

# Document types that create special objects (not plain transactions)
_SPECIAL_DOC_TYPES = {
    "mietvertrag": TRANSACTION_TYPE_RECURRING,
    "loan_contract": TRANSACTION_TYPE_LOAN,
    "kaufvertrag": TRANSACTION_TYPE_PROPERTY,
}

# Asset types that are valid for asset creation
_VALID_ASSET_TYPES = {"pkw", "e_auto", "lkw", "fiskal_lkw", "maschine", "it_hardware", "moebel"}

# GWG threshold (§13 EStG)
GWG_NETTO_THRESHOLD = Decimal("1000")


def classify_transaction(
    step1: Dict[str, Any],
    step2: Dict[str, Any],
    user_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Step 3 rule engine: classify what the pipeline should create.

    Args:
        step1: Vision perception data (document_type, gross_amount, vat_amount, issuer, recipient)
        step2: LLM judgment data (direction, is_asset, asset_type, is_gwg, etc.)
        user_context: User tax profile (name, vat_number, etc.)

    Returns:
        {
            "transaction_type": one of the TRANSACTION_TYPE_* constants,
            "direction": "income" | "expense",
            "asset_type": "pkw" | "e_auto" | "lkw" | ... | None,
            "is_gwg": bool,
            "creates": ["transaction"] | ["asset"] | ["recurring"] | ["loan"] | ["property"] | ["archive_only"],
            "rule_applied": str (for audit logging),
        }
    """
    doc_type = (step1.get("document_type") or step2.get("document_type") or "other").lower()

    # ── Rule 1: Archive-only documents ──────────────────────────────
    if doc_type in _ARCHIVE_ONLY_DOC_TYPES:
        return {
            "transaction_type": TRANSACTION_TYPE_ARCHIVE_ONLY,
            "direction": None,
            "asset_type": None,
            "is_gwg": False,
            "creates": ["archive_only"],
            "rule_applied": f"archive_only:{doc_type}",
        }

    # ── Rule 1.5: Kaufvertrag override — vehicle/equipment purchases ─
    # AI may classify vehicle purchase contracts as "kaufvertrag" (real estate).
    # If Step 2 detected a vehicle/equipment asset_type, it's an asset purchase.
    ai_asset_type_early = (step2.get("asset_type") or "").lower() if step2.get("asset_type") else None
    _VEHICLE_ASSET_TYPES = {"pkw", "e_auto", "lkw", "fiskal_lkw", "maschine", "it_hardware", "moebel"}
    if doc_type == "kaufvertrag" and ai_asset_type_early in _VEHICLE_ASSET_TYPES:
        gross = _to_decimal(step1.get("gross_amount") or step2.get("gross_amount"))
        vat = _to_decimal(step1.get("vat_amount") or step2.get("vat_amount"))
        netto = gross - vat if gross and vat else gross
        if netto and netto > GWG_NETTO_THRESHOLD:
            return {
                "transaction_type": TRANSACTION_TYPE_ASSET_ACQUISITION,
                "direction": "expense",
                "asset_type": ai_asset_type_early,
                "is_gwg": False,
                "creates": ["asset"],
                "rule_applied": f"kaufvertrag_override:{ai_asset_type_early},netto={netto}",
            }

    # ── Rule 2: Special document types (contracts) ──────────────────
    if doc_type in _SPECIAL_DOC_TYPES:
        special_type = _SPECIAL_DOC_TYPES[doc_type]
        creates = [special_type]
        # Mietvertrag also needs a recurring transaction
        if special_type == TRANSACTION_TYPE_RECURRING:
            creates = ["recurring"]
        elif special_type == TRANSACTION_TYPE_LOAN:
            creates = ["loan"]
        elif special_type == TRANSACTION_TYPE_PROPERTY:
            creates = ["property"]
        return {
            "transaction_type": special_type,
            "direction": _resolve_direction(step1, step2, user_context, doc_type),
            "asset_type": None,
            "is_gwg": False,
            "creates": creates,
            "rule_applied": f"special:{doc_type}→{special_type}",
        }

    # ── Rule 3: Always-expense documents ────────────────────────────
    if doc_type in _ALWAYS_EXPENSE_DOC_TYPES:
        creates = ["transaction"]
        # Insurance and SVS also create recurring
        if doc_type == "versicherungspolizze":
            creates = ["recurring", "transaction"]
        return {
            "transaction_type": TRANSACTION_TYPE_EXPENSE,
            "direction": "expense",
            "asset_type": None,
            "is_gwg": False,
            "creates": creates,
            "rule_applied": f"always_expense:{doc_type}",
        }

    # ── Rule 4: Lohnzettel = always income ──────────────────────────
    if doc_type == "lohnzettel":
        return {
            "transaction_type": TRANSACTION_TYPE_INCOME,
            "direction": "income",
            "asset_type": None,
            "is_gwg": False,
            "creates": ["transaction"],
            "rule_applied": "always_income:lohnzettel",
        }

    # ── Rule 5: Zinsbescheinigung = always expense ──────────────────
    if doc_type == "zinsbescheinigung":
        return {
            "transaction_type": TRANSACTION_TYPE_EXPENSE,
            "direction": "expense",
            "asset_type": None,
            "is_gwg": False,
            "creates": ["transaction"],
            "rule_applied": "always_expense:zinsbescheinigung",
        }

    # ── Rule 6: Mietvorschreibung / BK-Abrechnung ──────────────────
    if doc_type in ("mietvorschreibung", "betriebskostenabrechnung"):
        direction = _resolve_direction(step1, step2, user_context, doc_type)
        # Safety: if AI is unsure about direction, check user context
        # Selbständige (self-employed) receiving a Mietvorschreibung are tenants (expense)
        # Only landlords (Vermieter) have rental income
        if direction == "income" and user_context:
            user_roles = user_context.get("role_hints", [])
            # If user is self-employed and NOT explicitly a landlord for this address,
            # Mietvorschreibung is most likely their office/workshop rent (expense)
            is_selbstaendig = any("selbst" in r.lower() or "gewerbe" in r.lower()
                                  or "freiberuf" in r.lower() for r in user_roles)
            is_vermieter = any("vermieter" in r.lower() or "landlord" in r.lower()
                               for r in user_roles)
            if is_selbstaendig and not is_vermieter:
                direction = "expense"
        return {
            "transaction_type": TRANSACTION_TYPE_INCOME if direction == "income" else TRANSACTION_TYPE_EXPENSE,
            "direction": direction,
            "asset_type": None,
            "is_gwg": False,
            "creates": ["transaction"],
            "rule_applied": f"rental:{doc_type}→{direction}",
        }

    # ── Now handle invoices / receipts / asset_purchase ─────────────

    # Get amounts
    gross = _to_decimal(step1.get("gross_amount") or step2.get("gross_amount"))
    vat = _to_decimal(step1.get("vat_amount") or step2.get("vat_amount"))
    netto = gross - vat if gross and vat else gross

    # Get AI judgment on asset
    ai_is_asset = step2.get("is_asset_purchase") or step2.get("is_asset") or False
    ai_is_gwg = step2.get("is_gwg") or False
    ai_asset_type = (step2.get("asset_type") or "").lower() if step2.get("asset_type") else None

    # Direction
    direction = _resolve_direction(step1, step2, user_context, doc_type)

    # ── Rule 6.5: Income direction → NEVER asset ──────────────────
    # An outgoing invoice (Ausgangsrechnung) is income — user is selling, not buying.
    # AI sometimes wrongly sets is_asset_purchase on AR invoices. Override.
    if direction == "income":
        ai_is_asset = False

    # ── Rule 7: GWG check (§13 EStG) ───────────────────────────────
    # If netto ≤ €1,000 AND AI thinks it's an asset → GWG (sofort absetzbar)
    if ai_is_asset and netto and netto <= GWG_NETTO_THRESHOLD:
        return {
            "transaction_type": TRANSACTION_TYPE_GWG,
            "direction": "expense",
            "asset_type": ai_asset_type,
            "is_gwg": True,
            "creates": ["transaction"],  # GWG = expense transaction, NOT asset
            "rule_applied": f"gwg:netto={netto}≤{GWG_NETTO_THRESHOLD}",
        }

    # ── Rule 8: Asset purchase (netto > €1,000 + valid asset_type) ──
    if (ai_is_asset or doc_type == "asset_purchase") and netto and netto > GWG_NETTO_THRESHOLD:
        if ai_asset_type in _VALID_ASSET_TYPES:
            return {
                "transaction_type": TRANSACTION_TYPE_ASSET_ACQUISITION,
                "direction": "expense",
                "asset_type": ai_asset_type,
                "is_gwg": False,
                "creates": ["asset"],
                "rule_applied": f"asset:{ai_asset_type},netto={netto}",
            }
        # AI says asset but no valid type → treat as expense
        logger.warning("AI says asset but invalid type '%s' for doc, treating as expense", ai_asset_type)

    # ── Rule 9: Default — normal transaction ────────────────────────
    return {
        "transaction_type": TRANSACTION_TYPE_INCOME if direction == "income" else TRANSACTION_TYPE_EXPENSE,
        "direction": direction,
        "asset_type": None,
        "is_gwg": False,
        "creates": ["transaction"],
        "rule_applied": f"default:{doc_type}→{direction}",
    }


def _resolve_direction(
    step1: Dict[str, Any],
    step2: Dict[str, Any],
    user_context: Optional[Dict[str, Any]],
    doc_type: str,
) -> str:
    """Determine income vs expense from AI + user context."""
    # Step 2 AI judgment takes priority
    ai_direction = step2.get("expense_or_income")
    if ai_direction in ("income", "expense"):
        return ai_direction

    # Fallback: check issuer/recipient vs user name
    if user_context and user_context.get("name"):
        user_name = user_context["name"].lower()
        tokens = [t for t in user_name.split() if len(t) > 2]
        if tokens:
            issuer = (step1.get("issuer") or step2.get("issuer") or "").lower()
            recipient = (step1.get("recipient") or step2.get("recipient") or "").lower()
            if issuer and any(t in issuer for t in tokens):
                return "income"
            if recipient and any(t in recipient for t in tokens):
                return "expense"

    # Default: expense (safer assumption for tax deduction)
    return "expense"


def _to_decimal(value) -> Optional[Decimal]:
    """Safely convert to Decimal."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
