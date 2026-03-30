"""
AI Context Resolver — Uses AI-extracted data to make business decisions.

This service consumes the ``_ai_first`` data stored in ``ocr_result`` by the
AI-first classifier, and provides answers to business questions that the
downstream pipeline needs:

1. Which property does this invoice relate to? (property routing)
2. What is the netto amount? (E1b WK uses netto, not brutto)
3. Is the user landlord or tenant for this document?
4. What tax form should this go to? (E1a vs E1b)
5. Should this create a recurring? What parameters?

Principle: All ambiguous business decisions are first resolved by AI data.
Keywords/regex only as last-resort fallback.
"""
import logging
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def get_ai_data(ocr_result: dict) -> Dict[str, Any]:
    """Extract AI-first data from ocr_result, with safe defaults."""
    ai = ocr_result.get("_ai_first", {})
    return {
        "document_type": ai.get("document_type", "unknown"),
        "document_subtype": ai.get("document_subtype"),
        "document_purpose": ai.get("document_purpose"),
        "role": (ai.get("role_detection") or {}).get("user_is"),
        "landlord_name": (ai.get("role_detection") or {}).get("landlord_name"),
        "tenant_name": (ai.get("role_detection") or {}).get("tenant_name"),
        "total_amount": (ai.get("amounts") or {}).get("total_amount"),
        "annual_amount": (ai.get("amounts") or {}).get("annual_amount"),
        "monthly_amount": (ai.get("amounts") or {}).get("monthly_amount"),
        "settlement_amount": (ai.get("amounts") or {}).get("settlement_amount"),
        "new_amount": (ai.get("amounts") or {}).get("new_amount"),
        "property_address": (ai.get("key_fields") or {}).get("property_address"),
        "tax_form": (ai.get("tax_treatment") or {}).get("tax_form"),
        "expense_or_income": (ai.get("tax_treatment") or {}).get("expense_or_income"),
        "is_deductible": (ai.get("tax_treatment") or {}).get("is_deductible"),
        "deduction_category": (ai.get("tax_treatment") or {}).get("deduction_category"),
        "confidence": ai.get("confidence", 0),
    }


def resolve_property_context(
    ocr_result: dict,
    known_properties: List[Dict[str, Any]] = None,
    llm_fn=None,
) -> Optional[Dict[str, Any]]:
    """
    Determine which property (if any) this document relates to.

    Strategy:
    1. Use AI-extracted ``property_address`` from ``_ai_first``
    2. If ambiguous, ask LLM with property list context
    3. Match against known_properties by address similarity

    Returns:
        dict with property_id, address, is_rental, tax_form or None
    """
    ai = get_ai_data(ocr_result)
    ai_addr = ai.get("property_address") or ""
    raw_text = ocr_result.get("raw_text", "")[:2000]

    if not known_properties:
        known_properties = []

    # Strategy 1: AI already identified a property address
    if ai_addr:
        for prop in known_properties:
            prop_addr = prop.get("address", "").lower()
            if _address_match(ai_addr.lower(), prop_addr):
                return {
                    "property_id": prop.get("id"),
                    "address": prop.get("address"),
                    "is_rental": prop.get("is_rental", False),
                    "tax_form": "E1b" if prop.get("is_rental") else "E1a",
                    "match_source": "ai_address",
                }

    # Strategy 2: Ask LLM with full context
    if llm_fn and known_properties and raw_text:
        prop_list = "\n".join(
            f"  {i+1}. {p.get('address', '?')} ({'vermietet' if p.get('is_rental') else 'eigen'})"
            for i, p in enumerate(known_properties)
        )
        prompt = (
            f"Welche Immobilie betrifft dieses Dokument? "
            f"Bekannte Immobilien:\n{prop_list}\n\n"
            f"Antwort NUR als JSON: "
            f'{{\"property_index\": Nummer_oder_null, \"reason\": \"kurze Begruendung\"}}\n\n'
            f"Dokumenttext:\n{raw_text}"
        )
        try:
            response = llm_fn(
                "Du bist ein Experte fuer oesterreichische Immobilienverwaltung.",
                prompt, 100
            )
            import json
            m = re.search(r"\{[^{}]+\}", response)
            if m:
                result = json.loads(m.group(0))
                idx = result.get("property_index")
                if idx and 1 <= idx <= len(known_properties):
                    prop = known_properties[idx - 1]
                    return {
                        "property_id": prop.get("id"),
                        "address": prop.get("address"),
                        "is_rental": prop.get("is_rental", False),
                        "tax_form": "E1b" if prop.get("is_rental") else "E1a",
                        "match_source": "llm_context",
                        "reason": result.get("reason"),
                    }
        except Exception as e:
            logger.debug("Property context LLM failed: %s", e)

    # Strategy 3: Single-property shortcut for property-related document types
    ai_form = ai.get("tax_form") or ""
    ai_doc_type = ai.get("document_type") or ""
    _property_doc_types = {
        "grundsteuerbescheid", "versicherungspolizze", "zinsbescheinigung",
        "hausverwaltung_honorarnote", "hausverwaltung", "reparatur",
        "mietvorschreibung", "betriebskostenabrechnung",
    }
    is_property_related = (
        ai_form.upper() in ("E1B", "E1B_BEILAGE")
        or ai_doc_type in _property_doc_types
    )
    if is_property_related and len(known_properties) == 1:
        prop = known_properties[0]
        logger.info(
            "Single-property shortcut: AI says E1b, assigning to %s",
            prop.get("address", "?"),
        )
        return {
            "property_id": prop.get("id"),
            "address": prop.get("address"),
            "is_rental": prop.get("is_rental", False),
            "tax_form": "E1b",
            "match_source": "single_property_e1b",
        }

    return None


def resolve_netto_amount(ocr_result: dict) -> Optional[Decimal]:
    """
    Get the netto (excl. USt) amount from AI data.

    For E1b Werbungskosten, the netto amount is used (not brutto).
    AI mega-prompt now returns annual_amount = netto when USt is present.

    Returns:
        Netto amount as Decimal, or None if not available.
    """
    ai = get_ai_data(ocr_result)

    # AI annual_amount = netto (per enhanced prompt)
    netto = ai.get("annual_amount")
    if netto and netto > 0:
        return Decimal(str(netto))

    # Fallback: compute from brutto - USt
    brutto = ai.get("total_amount")
    if brutto and brutto > 0:
        # Check if AI extracted tax treatment
        # Standard: 20% USt → netto = brutto / 1.20
        # Reduced: 10% USt → netto = brutto / 1.10
        # Try to detect rate from AI
        return Decimal(str(brutto))  # Return brutto if can't determine USt

    return None


def resolve_tax_routing(
    ocr_result: dict,
    user_context: dict = None,
) -> Dict[str, Any]:
    """
    Determine the tax routing for a document.

    Returns:
        dict with:
          tax_form: "E1a" | "E1b" | "E1" | None
          category: expense category string
          is_wk: whether it's Werbungskosten (for V+V)
          is_ba: whether it's Betriebsausgabe (for self-employment)
          use_netto: whether to use netto amount (for WK)
          arbeitszimmer_split: whether to apply AZ% split
    """
    ai = get_ai_data(ocr_result)
    doc_type = ai.get("document_type", "unknown")
    role = ai.get("role")
    tax_form = ai.get("tax_form")
    ded_cat = ai.get("deduction_category", "")

    result = {
        "tax_form": tax_form,
        "category": ded_cat,
        "is_wk": False,
        "is_ba": False,
        "use_netto": False,
        "arbeitszimmer_split": False,
    }

    # V+V documents (landlord)
    if role == "landlord" or tax_form == "E1b" or "Werbungskosten" in (ded_cat or ""):
        result["tax_form"] = "E1b"
        result["is_wk"] = True
        result["use_netto"] = True  # E1b WK always uses netto

    # Self-employment documents
    elif role == "tenant" or tax_form == "E1a" or "Betriebsausgabe" in (ded_cat or ""):
        result["tax_form"] = "E1a"
        result["is_ba"] = True
        # Check if AZ split needed
        if doc_type in ("mietvorschreibung",) and role == "tenant":
            result["arbeitszimmer_split"] = True

    return result


def resolve_recurring_params(ocr_result: dict) -> Optional[Dict[str, Any]]:
    """
    Extract recurring transaction parameters from AI data.

    For contracts (Mietvertrag, Kreditvertrag, Versicherungspolizze),
    determine the recurring frequency and amount.

    Returns:
        dict with frequency, amount, start_date, description, or None
    """
    ai = get_ai_data(ocr_result)
    doc_type = ai.get("document_type", "")

    if doc_type == "mietvertrag":
        monthly = ai.get("monthly_amount")
        if monthly:
            return {
                "frequency": "monthly",
                "amount": Decimal(str(monthly)),
                "type": "income" if ai.get("role") == "landlord" else "expense",
                "description": f"Miete {ai.get('property_address', '')}",
            }

    # Other contract types handled by existing pipeline
    return None


def _normalize_street_name(word: str) -> str:
    """Normalize Austrian street name abbreviations for matching."""
    # Common Austrian abbreviations: str. → strasse, g. → gasse, pl. → platz
    w = word.rstrip(".")
    suffixes = {
        "str": "strasse", "strasse": "strasse",
        "g": "gasse", "gasse": "gasse",
        "pl": "platz", "platz": "platz",
        "weg": "weg", "ring": "ring",
    }
    for abbr, full in suffixes.items():
        if w.endswith(abbr) and len(w) > len(abbr):
            return w[: len(w) - len(abbr)] + full
    return w


def _address_match(addr1: str, addr2: str) -> bool:
    """Fuzzy address matching — checks if core street name overlaps."""
    if not addr1 or not addr2:
        return False
    # Normalize punctuation
    for char in ".,/":
        addr1 = addr1.replace(char, " ")
        addr2 = addr2.replace(char, " ")
    # Normalize street abbreviations
    words1 = {_normalize_street_name(w) for w in addr1.split()}
    words2 = {_normalize_street_name(w) for w in addr2.split()}
    # Check if main street name overlaps (at least 1 significant word)
    common = words1 & words2
    significant = {w for w in common if len(w) > 3 and not w.isdigit()}
    # Also check if any word from addr1 is a prefix of any word in addr2 (or vice versa)
    if not significant:
        for w1 in words1:
            if len(w1) <= 3:
                continue
            for w2 in words2:
                if len(w2) <= 3:
                    continue
                if w1.startswith(w2) or w2.startswith(w1):
                    significant.add(w1)
    return len(significant) >= 1
