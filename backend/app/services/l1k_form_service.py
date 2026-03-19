"""
L1k Form Service — Arbeitnehmerveranlagung mit Kindern

Generates L1k supplement form data for employees claiming child-related
tax benefits: Familienbonus Plus, Kindermehrbetrag, Unterhaltsabsetzbetrag.
All amounts loaded from DB TaxConfiguration per year.

Reference: BMF FinanzOnline L1k form
"""
import logging
from decimal import Decimal
from datetime import date
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

# Fallback defaults (2026 values) — used only when DB config unavailable
_FALLBACK_DEDUCTION = {
    "familienbonus_under_18": 2000.16,
    "familienbonus_18_24": 700.08,
    "kindermehrbetrag": 700.00,
    "unterhaltsabsetzbetrag": {
        "first_child_monthly": 38.00,
        "second_child_monthly": 56.00,
        "third_plus_child_monthly": 75.00,
    },
}

FAMILIENBONUS_HALF_FACTOR = Decimal("0.5")  # 50% for shared custody


def _load_deduction_config(db: Session, tax_year: int) -> dict:
    """Load deduction config from DB for the given tax year."""
    try:
        from app.models.tax_configuration import TaxConfiguration
        config_row = db.query(TaxConfiguration).filter(
            TaxConfiguration.tax_year == tax_year
        ).first()
        if config_row and config_row.deduction_config:
            return config_row.deduction_config
    except Exception as e:
        logger.warning("Failed to load deduction config for %d: %s", tax_year, e)
    return _FALLBACK_DEDUCTION


def _get_unterhaltsab(deduction_config: dict, child_index: int) -> Decimal:
    """Get annual Unterhaltsabsetzbetrag based on child position (0-indexed)."""
    uab = deduction_config.get("unterhaltsabsetzbetrag", {})
    if isinstance(uab, dict):
        if child_index == 0:
            monthly = Decimal(str(uab.get("first_child_monthly", 38.00)))
        elif child_index == 1:
            monthly = Decimal(str(uab.get("second_child_monthly", 56.00)))
        else:
            monthly = Decimal(str(uab.get("third_plus_child_monthly", 75.00)))
        return (monthly * 12).quantize(Decimal("0.01"))
    # Legacy: single flat value
    return Decimal(str(uab)) if uab else Decimal("456")


def generate_l1k_form_data(
    db: Session,
    user: User,
    tax_year: int,
) -> Dict[str, Any]:
    """Generate L1k form data for employee with children.

    Expects user.family_info to contain:
    {
        "children": [
            {"name": "...", "birth_date": "YYYY-MM-DD", "shared_custody_pct": 100},
            ...
        ]
    }
    Falls back to simple num_children if per-child data not available.
    Amounts loaded from DB TaxConfiguration for the given tax_year.
    """
    # Load year-specific config
    deduction_config = _load_deduction_config(db, tax_year)

    familienbonus_under_18 = Decimal(str(deduction_config.get("familienbonus_under_18", 2000.16)))
    familienbonus_18_plus = Decimal(str(deduction_config.get("familienbonus_18_24", 700.08)))
    kindermehrbetrag_max = Decimal(str(deduction_config.get("kindermehrbetrag", 700.00)))

    family_info = user.family_info or {}
    children = family_info.get("children", [])

    # Fallback: if no per-child data, build from num_children
    if not children and family_info.get("num_children", 0) > 0:
        num = family_info["num_children"]
        children = [
            {"name": f"Kind {i+1}", "birth_date": None, "shared_custody_pct": 100}
            for i in range(num)
        ]

    tax_year_end = date(tax_year, 12, 31)

    # Per-child calculations
    child_details: List[Dict[str, Any]] = []
    total_familienbonus = Decimal("0")
    total_familienbonus_half = Decimal("0")
    total_kindermehrbetrag = Decimal("0")
    total_unterhaltsab = Decimal("0")
    children_under_18 = 0
    children_18_plus = 0
    unterhaltsab_child_index = 0  # Track position for graduated rates

    for child in children:
        name = child.get("name", "Kind")
        birth_str = child.get("birth_date")
        shared_pct = child.get("shared_custody_pct", 100)

        # Calculate age
        age = None
        if birth_str:
            try:
                birth = date.fromisoformat(str(birth_str))
                age = tax_year_end.year - birth.year
                if (tax_year_end.month, tax_year_end.day) < (birth.month, birth.day):
                    age -= 1
            except (ValueError, TypeError):
                pass

        is_under_18 = age is not None and age < 18
        if is_under_18:
            children_under_18 += 1
            base_bonus = familienbonus_under_18
        else:
            children_18_plus += 1
            base_bonus = familienbonus_18_plus

        # Shared custody: 50% split
        if shared_pct == 50:
            bonus = (base_bonus * FAMILIENBONUS_HALF_FACTOR).quantize(Decimal("0.01"))
            total_familienbonus_half += bonus
        else:
            bonus = base_bonus
            total_familienbonus += bonus

        # Kindermehrbetrag (simplified: available if low income)
        kindermehr = kindermehrbetrag_max  # placeholder; real calc depends on tax liability

        # Unterhaltsabsetzbetrag (only if child not in household)
        in_household = child.get("in_household", True)
        unterhaltsab = Decimal("0")
        if not in_household:
            unterhaltsab = _get_unterhaltsab(deduction_config, unterhaltsab_child_index)
            unterhaltsab_child_index += 1
            total_unterhaltsab += unterhaltsab

        child_details.append({
            "name": name,
            "birth_date": birth_str,
            "age": age,
            "shared_custody_pct": shared_pct,
            "familienbonus": float(bonus),
            "kindermehrbetrag": float(kindermehr),
            "unterhaltsabsetzbetrag": float(unterhaltsab),
        })

    total_kindermehrbetrag = kindermehrbetrag_max * len(children)

    # Format labels with year-specific amounts
    fb_u18_label = f"{float(familienbonus_under_18):,.0f}"
    fb_18p_label = f"{float(familienbonus_18_plus):,.0f}"
    kmb_label = f"{float(kindermehrbetrag_max):,.0f}"

    fields = [
        {
            "kz": "220",
            "label_de": "Familienbonus Plus (voller Betrag, je Kind)",
            "label_en": "Family Bonus Plus (full amount, per child)",
            "label_zh": "家庭奖金Plus（全额，每子女）",
            "value": float(total_familienbonus),
            "section": "familienbonus",
            "editable": True,
            "note_de": f"Unter 18: EUR {fb_u18_label}/Jahr, ab 18: EUR {fb_18p_label}/Jahr",
        },
        {
            "kz": "221",
            "label_de": "Familienbonus Plus (halber Betrag, gemeinsame Obsorge)",
            "label_en": "Family Bonus Plus (half amount, shared custody)",
            "label_zh": "家庭奖金Plus（半额，共同抚养）",
            "value": float(total_familienbonus_half),
            "section": "familienbonus",
            "editable": True,
            "note_de": "50% bei geteilter Obsorge",
        },
        {
            "kz": "222",
            "label_de": f"Kindermehrbetrag (bei geringer Steuer, max. EUR {kmb_label}/Kind)",
            "label_en": f"Child tax credit (low income, max EUR {kmb_label}/child)",
            "label_zh": f"儿童额外抵免（低收入，最高{kmb_label}欧元/子女）",
            "value": float(total_kindermehrbetrag),
            "section": "kindermehrbetrag",
            "editable": True,
            "note_de": "Steht zu, wenn die Einkommensteuer unter dem Familienbonus liegt",
        },
        {
            "kz": "243",
            "label_de": "Unterhaltsabsetzbetrag (Kind nicht im Haushalt)",
            "label_en": "Maintenance deduction (child not in household)",
            "label_zh": "抚养费抵扣（子女不在同一户籍）",
            "value": float(total_unterhaltsab),
            "section": "unterhaltsabsetzbetrag",
            "editable": True,
            "note_de": "Fuer Kinder, die nicht im gemeinsamen Haushalt leben",
        },
        {
            "kz": "244",
            "label_de": "Anzahl Kinder mit Unterhaltsabsetzbetrag",
            "label_en": "Number of children with maintenance deduction",
            "label_zh": "享受抚养费抵扣的子女数量",
            "value": sum(1 for c in children if not c.get("in_household", True)),
            "section": "unterhaltsabsetzbetrag",
            "editable": True,
        },
    ]

    return {
        "form_type": "L1k",
        "form_name_de": "Beilage zur Arbeitnehmerveranlagung (Kinder)",
        "form_name_en": "Supplement to Employee Tax Assessment (Children)",
        "form_name_zh": "雇员申报附表（子女）",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "tax_number": user.tax_number or "",
        "generated_at": date.today().isoformat(),
        "fields": fields,
        "child_details": child_details,
        "summary": {
            "total_children": len(children),
            "children_under_18": children_under_18,
            "children_18_plus": children_18_plus,
            "total_familienbonus": float(total_familienbonus + total_familienbonus_half),
            "total_kindermehrbetrag": float(total_kindermehrbetrag),
            "total_unterhaltsabsetzbetrag": float(total_unterhaltsab),
        },
        "disclaimer_de": (
            "Diese Daten dienen als Ausfuellhilfe fuer das Formular L1k. "
            "Bitte pruefen Sie alle Werte vor der Einreichung. Keine Steuerberatung."
        ),
        "disclaimer_en": (
            "This data is a filling aid for the L1k form. "
            "Please verify all values before submitting. Not tax advice."
        ),
    }
