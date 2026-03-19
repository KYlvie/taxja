"""Form Eligibility Service — determines which tax forms a user needs.

Maps user_type (+ optional properties like has_children, has_properties)
to the set of relevant Austrian tax forms.

Austrian tax form assignment rules:
  - E1:  Everyone filing income tax (all personal types)
  - E1a: Self-employed sole proprietors (EA-Rechnung)
  - E1b: Landlords with rental income (per property)
  - L1:  Employees (Arbeitnehmerveranlagung)
  - L1k: Anyone with children (Familienbonus, Kindermehrbetrag)
  - K1:  GmbH / Körperschaftsteuer
  - U1:  Annual VAT return (self-employed, GmbH if VAT-registered)
  - UVA: Monthly/quarterly VAT pre-return (same as U1)
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.tax_form_template import TaxFormType


# ── Core mapping: user_type → applicable form types ──

_USER_TYPE_FORMS: Dict[str, List[TaxFormType]] = {
    UserType.EMPLOYEE.value: [
        TaxFormType.E1,
        TaxFormType.L1,
        TaxFormType.L1K,
    ],
    UserType.SELF_EMPLOYED.value: [
        TaxFormType.E1,
        TaxFormType.E1A,
        TaxFormType.L1K,
        TaxFormType.U1,
        TaxFormType.UVA,
    ],
    UserType.LANDLORD.value: [
        TaxFormType.E1,
        TaxFormType.E1B,
        TaxFormType.L1K,
    ],
    UserType.MIXED.value: [
        TaxFormType.E1,
        TaxFormType.E1A,
        TaxFormType.E1B,
        TaxFormType.L1,
        TaxFormType.L1K,
        TaxFormType.U1,
        TaxFormType.UVA,
    ],
    UserType.GMBH.value: [
        TaxFormType.K1,
        TaxFormType.U1,
        TaxFormType.UVA,
    ],
}

# Display metadata for each form
_FORM_META: Dict[TaxFormType, Dict[str, str]] = {
    TaxFormType.E1: {
        "name_de": "Einkommensteuererklärung",
        "name_en": "Income Tax Return",
        "name_zh": "年度所得税申报",
        "description_de": "Hauptformular für die jährliche Einkommensteuererklärung",
        "description_en": "Main form for the annual income tax return",
        "description_zh": "汇总全年收入，计算应缴或退税金额",
        "category": "income_tax",
    },
    TaxFormType.E1A: {
        "name_de": "Selbständige Einkünfte",
        "name_en": "Self-Employment Income",
        "name_zh": "自雇/个体经营收入",
        "description_de": "Einnahmen-Ausgaben-Rechnung für Einzelunternehmer",
        "description_en": "Income-expense statement for sole proprietors",
        "description_zh": "申报自由职业或个体经营的收入和支出",
        "category": "income_tax",
    },
    TaxFormType.E1B: {
        "name_de": "Vermietung & Verpachtung",
        "name_en": "Rental Income",
        "name_zh": "租赁收入申报",
        "description_de": "Einkünfte aus Vermietung und Verpachtung (pro Objekt)",
        "description_en": "Rental and leasing income (per property)",
        "description_zh": "按房产申报租金收入和相关支出",
        "category": "income_tax",
    },
    TaxFormType.L1: {
        "name_de": "Arbeitnehmerveranlagung",
        "name_en": "Employee Tax Assessment",
        "name_zh": "雇员年度退税",
        "description_de": "Lohnsteuerjahresausgleich für Arbeitnehmer",
        "description_en": "Annual wage tax adjustment for employees",
        "description_zh": "申请工资税年度结算，获取退税",
        "category": "income_tax",
    },
    TaxFormType.L1K: {
        "name_de": "Kinder-Absetzbeträge",
        "name_en": "Child Tax Benefits",
        "name_zh": "子女税收优惠",
        "description_de": "Familienbonus Plus, Kindermehrbetrag, Unterhaltsabsetzbetrag",
        "description_en": "Family Bonus Plus, child tax credit, maintenance deduction",
        "description_zh": "申请子女抵税额和家庭补贴",
        "category": "income_tax",
    },
    TaxFormType.K1: {
        "name_de": "Körperschaftsteuer",
        "name_en": "Corporate Tax Return",
        "name_zh": "公司所得税申报",
        "description_de": "Steuererklärung für Kapitalgesellschaften (GmbH)",
        "description_en": "Tax return for corporations (GmbH)",
        "description_zh": "有限责任公司(GmbH)年度税务申报",
        "category": "corporate_tax",
    },
    TaxFormType.U1: {
        "name_de": "Umsatzsteuer-Jahreserklärung",
        "name_en": "Annual VAT Return",
        "name_zh": "年度增值税结算",
        "description_de": "Jahreserklärung zur Umsatzsteuer",
        "description_en": "Annual value-added tax return",
        "description_zh": "汇总全年增值税，适用于需缴纳VAT的纳税人",
        "category": "vat",
    },
    TaxFormType.UVA: {
        "name_de": "USt-Voranmeldung",
        "name_en": "VAT Pre-Filing",
        "name_zh": "增值税月度/季度预申报",
        "description_de": "Monatliche/vierteljährliche USt-Voranmeldung",
        "description_en": "Monthly/quarterly VAT pre-filing",
        "description_zh": "按月或按季预缴增值税",
        "category": "vat",
    },
}


def get_eligible_forms(
    user: User,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Get the list of tax forms applicable to this user.

    Args:
        user: User model with user_type, family_info, etc.
        db: Optional DB session (for checking properties, etc.)

    Returns:
        List of form dicts with type, names, descriptions, availability flags
    """
    user_type = user.user_type
    if hasattr(user_type, 'value'):
        user_type = user_type.value

    base_forms = _USER_TYPE_FORMS.get(user_type, [TaxFormType.E1])

    # Conditional adjustments
    forms = list(base_forms)

    # L1k: only show if user has children
    has_children = False
    family_info = user.family_info or {}
    if family_info.get("children") or family_info.get("num_children", 0) > 0:
        has_children = True

    if not has_children and TaxFormType.L1K in forms:
        forms.remove(TaxFormType.L1K)

    # E1b: check if user actually has rental properties
    if TaxFormType.E1B in forms and db:
        try:
            from app.models.property import Property, PropertyStatus
            property_count = db.query(Property).filter(
                Property.user_id == user.id,
                Property.status.in_([PropertyStatus.ACTIVE, PropertyStatus.SOLD]),
            ).count()
            if property_count == 0:
                forms.remove(TaxFormType.E1B)
        except Exception:
            pass  # Keep E1b if we can't check

    # U1/UVA: check Kleinunternehmer status (below €55k → no VAT obligation)
    # For now, keep them if user_type qualifies; frontend can show a note

    # Build result with metadata
    result = []
    for ft in forms:
        meta = _FORM_META.get(ft, {})
        result.append({
            "form_type": ft.value,
            "name_de": meta.get("name_de", ft.value),
            "name_en": meta.get("name_en", ft.value),
            "name_zh": meta.get("name_zh", ft.value),
            "description_de": meta.get("description_de", ""),
            "description_en": meta.get("description_en", ""),
            "description_zh": meta.get("description_zh", ""),
            "category": meta.get("category", "other"),
        })

    return result


def get_eligible_form_types(user: User, db: Optional[Session] = None) -> List[str]:
    """Get just the form type strings for this user (simpler API)."""
    return [f["form_type"] for f in get_eligible_forms(user, db)]
