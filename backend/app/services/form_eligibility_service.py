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
        "name_fr": "Déclaration d'impôt sur le revenu",
        "name_ru": "Декларация о подоходном налоге",
        "name_hu": "Jövedelemadó-bevallás",
        "name_pl": "Zeznanie podatkowe",
        "name_tr": "Gelir vergisi beyannamesi",
        "name_bs": "Prijava poreza na dohodak",
        "description_de": "Hauptformular für die jährliche Einkommensteuererklärung",
        "description_en": "Main form for the annual income tax return",
        "description_zh": "汇总全年收入，计算应缴或退税金额",
        "description_fr": "Formulaire principal pour la déclaration annuelle d'impôt sur le revenu",
        "description_ru": "Основная форма для ежегодной декларации о подоходном налоге",
        "description_hu": "Az éves jövedelemadó-bevallás fő nyomtatványa",
        "description_pl": "Główny formularz rocznego zeznania podatkowego",
        "description_tr": "Yillik gelir vergisi beyannamesi icin ana form",
        "description_bs": "Glavni obrazac za godisnju prijavu poreza na dohodak",
        "category": "income_tax",
    },
    TaxFormType.E1A: {
        "name_de": "Selbständige Einkünfte",
        "name_en": "Self-Employment Income",
        "name_zh": "自雇/个体经营收入",
        "name_fr": "Revenus d'activité indépendante",
        "name_ru": "Доходы от самозанятости",
        "name_hu": "Önálló tevékenységből származó jövedelem",
        "name_pl": "Dochody z działalności gospodarczej",
        "name_tr": "Serbest meslek geliri",
        "name_bs": "Prihodi od samostalne djelatnosti",
        "description_de": "Einnahmen-Ausgaben-Rechnung für Einzelunternehmer",
        "description_en": "Income-expense statement for sole proprietors",
        "description_zh": "申报自由职业或个体经营的收入和支出",
        "description_fr": "Relevé des recettes et dépenses pour les entrepreneurs individuels",
        "description_ru": "Отчёт о доходах и расходах для индивидуальных предпринимателей",
        "description_hu": "Bevétel-kiadás kimutatás egyéni vállalkozók számára",
        "description_pl": "Zestawienie przychodów i wydatków dla jednoosobowych działalności",
        "description_tr": "Serbest meslek erbaplari icin gelir-gider tablosu",
        "description_bs": "Pregled prihoda i rashoda za samostalne poduzetnike",
        "category": "income_tax",
    },
    TaxFormType.E1B: {
        "name_de": "Vermietung & Verpachtung",
        "name_en": "Rental Income",
        "name_zh": "租赁收入申报",
        "name_fr": "Revenus locatifs",
        "name_ru": "Доходы от аренды",
        "name_hu": "Bérbeadásból származó jövedelem",
        "name_pl": "Dochody z najmu",
        "name_tr": "Kira geliri",
        "name_bs": "Prihodi od najma",
        "description_de": "Einkünfte aus Vermietung und Verpachtung (pro Objekt)",
        "description_en": "Rental and leasing income (per property)",
        "description_zh": "按房产申报租金收入和相关支出",
        "description_fr": "Revenus de location et de bail (par bien immobilier)",
        "description_ru": "Доходы от аренды и лизинга (по каждому объекту)",
        "description_hu": "Bérbeadásból és haszonbérletből származó jövedelem (ingatlanonként)",
        "description_pl": "Dochody z najmu i dzierżawy (na nieruchomość)",
        "description_tr": "Kira ve kiralama geliri (mulk basina)",
        "description_bs": "Prihodi od iznajmljivanja i zakupa (po nekretnini)",
        "category": "income_tax",
    },
    TaxFormType.L1: {
        "name_de": "Arbeitnehmerveranlagung",
        "name_en": "Employee Tax Assessment",
        "name_zh": "雇员年度退税",
        "name_fr": "Régularisation fiscale des salariés",
        "name_ru": "Налоговая оценка работников",
        "name_hu": "Munkavállalói adóelszámolás",
        "name_pl": "Rozliczenie podatkowe pracownika",
        "name_tr": "Calisan vergi degerlendirmesi",
        "name_bs": "Porezno uskladjivanje zaposlenika",
        "description_de": "Lohnsteuerjahresausgleich für Arbeitnehmer",
        "description_en": "Annual wage tax adjustment for employees",
        "description_zh": "申请工资税年度结算，获取退税",
        "description_fr": "Régularisation annuelle de l'impôt sur les salaires pour les employés",
        "description_ru": "Ежегодная корректировка налога на заработную плату для работников",
        "description_hu": "Éves bérjövedelem-adó elszámolás munkavállalók számára",
        "description_pl": "Roczne rozliczenie podatku od wynagrodzeń dla pracowników",
        "description_tr": "Calisanlar icin yillik ucret vergisi duzeltmesi",
        "description_bs": "Godisnje uskladjivanje poreza na platu za zaposlenike",
        "category": "income_tax",
    },
    TaxFormType.L1K: {
        "name_de": "Kinder-Absetzbeträge",
        "name_en": "Child Tax Benefits",
        "name_zh": "子女税收优惠",
        "name_fr": "Avantages fiscaux pour enfants",
        "name_ru": "Налоговые льготы на детей",
        "name_hu": "Gyermekek utáni adókedvezmények",
        "name_pl": "Ulgi podatkowe na dzieci",
        "name_tr": "Cocuk vergi avantajlari",
        "name_bs": "Porezne olaksice za djecu",
        "description_de": "Familienbonus Plus, Kindermehrbetrag, Unterhaltsabsetzbetrag",
        "description_en": "Family Bonus Plus, child tax credit, maintenance deduction",
        "description_zh": "申请子女抵税额和家庭补贴",
        "description_fr": "Bonus familial Plus, crédit d'impôt pour enfants, déduction pour pension alimentaire",
        "description_ru": "Семейный бонус Плюс, детский налоговый вычет, вычет на содержание",
        "description_hu": "Családi bónusz Plusz, gyermek adójóváírás, tartásdíj-levonás",
        "description_pl": "Bonus rodzinny Plus, ulga podatkowa na dziecko, odliczenie alimentów",
        "description_tr": "Aile Bonusu Plus, cocuk vergi kredisi, nafaka indirimi",
        "description_bs": "Porodicni bonus Plus, djeciji porezni kredit, odbitak za izdrzavanje",
        "category": "income_tax",
    },
    TaxFormType.K1: {
        "name_de": "Körperschaftsteuer",
        "name_en": "Corporate Tax Return",
        "name_zh": "公司所得税申报",
        "name_fr": "Déclaration d'impôt sur les sociétés",
        "name_ru": "Декларация по корпоративному налогу",
        "name_hu": "Társasági adóbevallás",
        "name_pl": "Zeznanie z podatku dochodowego od osób prawnych",
        "name_tr": "Kurumlar vergisi beyannamesi",
        "name_bs": "Prijava poreza na dobit pravnih lica",
        "description_de": "Steuererklärung für Kapitalgesellschaften (GmbH)",
        "description_en": "Tax return for corporations (GmbH)",
        "description_zh": "有限责任公司(GmbH)年度税务申报",
        "description_fr": "Déclaration fiscale pour les sociétés de capitaux (GmbH)",
        "description_ru": "Налоговая декларация для юридических лиц (GmbH)",
        "description_hu": "Adóbevallás tőketársaságok (GmbH) számára",
        "description_pl": "Zeznanie podatkowe dla spółek kapitałowych (GmbH)",
        "description_tr": "Sermaye sirketleri (GmbH) icin vergi beyannamesi",
        "description_bs": "Porezna prijava za drustva kapitala (GmbH)",
        "category": "corporate_tax",
    },
    TaxFormType.U1: {
        "name_de": "Umsatzsteuer-Jahreserklärung",
        "name_en": "Annual VAT Return",
        "name_zh": "年度增值税结算",
        "name_fr": "Déclaration annuelle de TVA",
        "name_ru": "Годовая декларация по НДС",
        "name_hu": "Éves ÁFA bevallás",
        "name_pl": "Roczna deklaracja VAT",
        "name_tr": "Yillik KDV beyannamesi",
        "name_bs": "Godisnja prijava PDV-a",
        "description_de": "Jahreserklärung zur Umsatzsteuer",
        "description_en": "Annual value-added tax return",
        "description_zh": "汇总全年增值税，适用于需缴纳VAT的纳税人",
        "description_fr": "Déclaration annuelle de taxe sur la valeur ajoutée",
        "description_ru": "Ежегодная декларация по налогу на добавленную стоимость",
        "description_hu": "Éves általános forgalmi adó bevallás",
        "description_pl": "Roczna deklaracja podatku od towarów i usług",
        "description_tr": "Yillik katma deger vergisi beyannamesi",
        "description_bs": "Godisnja prijava poreza na dodanu vrijednost",
        "category": "vat",
    },
    TaxFormType.UVA: {
        "name_de": "USt-Voranmeldung",
        "name_en": "VAT Pre-Filing",
        "name_zh": "增值税月度/季度预申报",
        "name_fr": "Déclaration préalable de TVA",
        "name_ru": "Предварительная декларация по НДС",
        "name_hu": "ÁFA előleg bevallás",
        "name_pl": "Zaliczkowa deklaracja VAT",
        "name_tr": "KDV on bildirimi",
        "name_bs": "Prethodna prijava PDV-a",
        "description_de": "Monatliche/vierteljährliche USt-Voranmeldung",
        "description_en": "Monthly/quarterly VAT pre-filing",
        "description_zh": "按月或按季预缴增值税",
        "description_fr": "Déclaration préalable mensuelle/trimestrielle de TVA",
        "description_ru": "Ежемесячная/ежеквартальная предварительная декларация по НДС",
        "description_hu": "Havi/negyedéves ÁFA előleg bevallás",
        "description_pl": "Miesięczna/kwartalna zaliczkowa deklaracja VAT",
        "description_tr": "Aylik/uc aylik KDV on bildirimi",
        "description_bs": "Mjesecna/tromjesecna prethodna prijava PDV-a",
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
            "name_fr": meta.get("name_fr", ft.value),
            "name_ru": meta.get("name_ru", ft.value),
            "name_hu": meta.get("name_hu", ft.value),
            "name_pl": meta.get("name_pl", ft.value),
            "name_tr": meta.get("name_tr", ft.value),
            "name_bs": meta.get("name_bs", ft.value),
            "description_de": meta.get("description_de", ""),
            "description_en": meta.get("description_en", ""),
            "description_zh": meta.get("description_zh", ""),
            "description_fr": meta.get("description_fr", ""),
            "description_ru": meta.get("description_ru", ""),
            "description_hu": meta.get("description_hu", ""),
            "description_pl": meta.get("description_pl", ""),
            "description_tr": meta.get("description_tr", ""),
            "description_bs": meta.get("description_bs", ""),
            "category": meta.get("category", "other"),
        })

    return result


def get_eligible_form_types(user: User, db: Optional[Session] = None) -> List[str]:
    """Get just the form type strings for this user (simpler API)."""
    return [f["form_type"] for f in get_eligible_forms(user, db)]
