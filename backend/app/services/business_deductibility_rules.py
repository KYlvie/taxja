"""Business-type-specific expense deductibility rules.

Austrian self-employed sub-types have significantly different deductibility rules:

- Freiberufler (§22 EStG): Liberal professions — doctors, lawyers, accountants,
  IT consultants, architects, artists, journalists.
  -> Groceries NOT deductible, Bewirtung 50%, consulting Pauschalierung 6%

- Gewerbetreibende (§23 EStG): Trade, crafts, restaurants, retail, e-commerce.
  -> Groceries = Wareneinsatz (fully deductible), vehicle fully if trade vehicle,
     standard Pauschalierung 12-15%

- Neue Selbständige: Trainers, coaches, content creators, freelance non-§22.
  -> Similar to Freiberufler, consulting Pauschalierung 6%

- Land- und Forstwirtschaft (§21 EStG): Agriculture and forestry.
  -> Special Pauschalierung rules, Wareneinsatz deductible

This module provides per-sub-type overrides that refine the base _SELF_EMPLOYED
rules in deductibility_checker.py.
"""
import logging
from typing import Optional, Dict, Tuple, Any
from app.models.user import SelfEmployedType

logger = logging.getLogger(__name__)

# Sentinel for "needs AI analysis"
_NEEDS_AI = "NEEDS_AI"


# ── Per-sub-type rule overrides ──
# Format: {ExpenseCategory_value: (is_deductible, reason, max_amount, deductible_pct)}
# deductible_pct: None = 100% if deductible, else a fraction (e.g., 0.5 for 50%)
# Only categories that DIFFER from the base _SELF_EMPLOYED rules need to be listed.

_FREIBERUFLER_OVERRIDES: Dict[str, Tuple[Any, str, Optional[float], Optional[float]]] = {
    "groceries": (
        False,
        "Private Lebensführung — Freiberufler haben keinen Wareneinsatz",
        None, None,
    ),
    "travel": (
        True,
        "Betriebsausgabe — Reisekosten für Mandantenbesuche / Fortbildung",
        None, None,
    ),
    "marketing": (
        True,
        "Repräsentationsaufwand — Bewirtung nur 50% absetzbar (§20 Abs 1 Z 3 EStG)",
        None, 0.5,
    ),
    "vehicle": (
        True,
        "KFZ-Aufwand — Fahrtenbuch oder km-Pauschale (amtliches km-Geld)",
        None, None,  # needs Fahrtenbuch or km-Geld calculation
    ),
    "rent": (
        True,
        "Betriebsausgabe — Praxis-/Kanzlei-/Büro-Miete",
        None, None,
    ),
}

_GEWERBETREIBENDE_OVERRIDES: Dict[str, Tuple[Any, str, Optional[float], Optional[float]]] = {
    "groceries": (
        True,
        "Wareneinsatz — Einkauf von Handelswaren / Rohstoffen ist voll absetzbar",
        None, None,
    ),
    "travel": (
        True,
        "Betriebsausgabe — Geschäftsreisen, Kundenbesuche, Messebesuche",
        None, None,
    ),
    "marketing": (
        True,
        "Betriebsausgabe — Werbung, Bewirtung von Geschäftspartnern (50%)",
        None, 0.5,  # Bewirtung portion still 50%
    ),
    "vehicle": (
        True,
        "Betriebsausgabe — Lieferfahrzeug / Handwerker-Fahrzeug voll absetzbar",
        None, None,
    ),
    "maintenance": (
        True,
        "Betriebsausgabe — Instandhaltung Geschäftslokal / Werkstatt",
        None, None,
    ),
}

_NEUE_SELBSTAENDIGE_OVERRIDES: Dict[str, Tuple[Any, str, Optional[float], Optional[float]]] = {
    "groceries": (
        _NEEDS_AI,
        "Depends on business context — AI will analyze (e.g., catering for seminars)",
        None, None,
    ),
    "travel": (
        True,
        "Betriebsausgabe — Reisekosten für Kundenbesuche / Seminare",
        None, None,
    ),
    "marketing": (
        True,
        "Betriebsausgabe — Online-Werbung, Social Media, Bewirtung 50%",
        None, 0.5,
    ),
    "vehicle": (
        True,
        "KFZ-Aufwand — km-Pauschale oder Fahrtenbuch",
        None, None,
    ),
}

_LAND_FORSTWIRTSCHAFT_OVERRIDES: Dict[str, Tuple[Any, str, Optional[float], Optional[float]]] = {
    "groceries": (
        True,
        "Wareneinsatz — Saatgut, Futtermittel, landwirtschaftliche Betriebsmittel",
        None, None,
    ),
    "vehicle": (
        True,
        "Betriebsausgabe — landwirtschaftliche Fahrzeuge / Maschinen",
        None, None,
    ),
    "maintenance": (
        True,
        "Betriebsausgabe — Instandhaltung Hof / Stallungen / Maschinen",
        None, None,
    ),
    "insurance": (
        True,
        "Betriebsausgabe — Hagelversicherung, Tierversicherung",
        None, None,
    ),
    "marketing": (
        True,
        "Betriebsausgabe — Direktvermarktung, Hofladen-Werbung",
        None, None,  # no 50% limit for agriculture direct sales
    ),
}

_OVERRIDES = {
    SelfEmployedType.FREIBERUFLER: _FREIBERUFLER_OVERRIDES,
    SelfEmployedType.GEWERBETREIBENDE: _GEWERBETREIBENDE_OVERRIDES,
    SelfEmployedType.NEUE_SELBSTAENDIGE: _NEUE_SELBSTAENDIGE_OVERRIDES,
    SelfEmployedType.LAND_FORSTWIRTSCHAFT: _LAND_FORSTWIRTSCHAFT_OVERRIDES,
}


# ── Industry-specific overrides (second level, refines business_type) ──
# These take precedence over business_type rules when a specific industry is set.
# Key = industry slug, Value = dict of expense_category -> override tuple
# Priority: industry override > business_type override > base rules > AI

_INDUSTRY_OVERRIDES: Dict[str, Dict[str, Tuple[Any, str, Optional[float], Optional[float]]]] = {
    # ── Gastronomie (Restaurant / Café / Bar) ──
    "gastronomie": {
        "groceries": (True, "Wareneinsatz — Lebensmitteleinkauf für Gastronomie voll absetzbar", None, None),
        "cleaning": (True, "Betriebsausgabe — Reinigungsmittel, Küchenreinigung, Hygienebedarf", None, None),
        "equipment": (True, "Betriebsausgabe — Küchengeräte, Geschirr, Möbel (AfA bei > €1.000)", None, None),
        "utilities": (True, "Betriebsausgabe — Gas, Strom, Wasser für Gastronomiebetrieb", None, None),
        "clothing": (True, "Betriebsausgabe — Kochuniform, Schürzen, Servicekleidung", None, None),
    },
    # ── Hotel / Beherbergung ──
    "hotel": {
        "groceries": (True, "Wareneinsatz — Frühstück, Minibar, Verpflegung für Gäste", None, None),
        "cleaning": (True, "Betriebsausgabe — Reinigung, Wäscherei, Zimmerpflege", None, None),
        "utilities": (True, "Betriebsausgabe — Heizung, Strom, Wasser, Internet für Gäste", None, None),
        "maintenance": (True, "Betriebsausgabe — Zimmerrenovierung, Gebäudeinstandhaltung", None, None),
        "marketing": (True, "Betriebsausgabe — Booking.com-Gebühren, Werbung (voll absetzbar)", None, None),
        "insurance": (True, "Betriebsausgabe — Betriebshaftpflicht, Gebäudeversicherung", None, None),
    },
    # ── Kosmetik / Friseur / Beauty ──
    "kosmetik": {
        "groceries": (True, "Wareneinsatz — Kosmetikprodukte, Behandlungsmaterialien, Pflegeprodukte", None, None),
        "equipment": (True, "Betriebsausgabe — Behandlungsgeräte, Friseurstuhl (AfA bei > €1.000)", None, None),
        "clothing": (True, "Betriebsausgabe — Arbeitskleidung, Schutzkittel", None, None),
        "cleaning": (True, "Betriebsausgabe — Hygienemittel, Desinfektion, Handtücher", None, None),
        "education": (True, "Betriebsausgabe — Fortbildung, Zertifizierungen, Produktschulungen", None, None),
    },
    # ── Handel / Einzelhandel ──
    "handel": {
        "groceries": (True, "Wareneinsatz — Einkauf von Handelswaren voll absetzbar", None, None),
        "shipping": (True, "Betriebsausgabe — Versandkosten, Verpackungsmaterial", None, None),
        "equipment": (True, "Betriebsausgabe — Ladeneinrichtung, Kassensystem (AfA bei > €1.000)", None, None),
        "insurance": (True, "Betriebsausgabe — Warenlagerversicherung, Betriebshaftpflicht", None, None),
    },
    # ── E-Commerce / Online-Handel ──
    "ecommerce": {
        "groceries": (True, "Wareneinsatz — Handelswaren, Dropshipping-Kosten", None, None),
        "shipping": (True, "Betriebsausgabe — Versand, Verpackung, Fulfillment-Gebühren", None, None),
        "software": (True, "Betriebsausgabe — Shop-System, Buchhaltungssoftware", None, None),
        "marketing": (True, "Betriebsausgabe — Google Ads, Facebook Ads, SEO (voll absetzbar)", None, None),
    },
    # ── Handwerk / Bau ──
    "handwerk": {
        "groceries": (True, "Wareneinsatz — Baumaterial, Rohstoffe", None, None),
        "vehicle": (True, "Betriebsausgabe — Firmenfahrzeug / Transporter voll absetzbar", None, None),
        "equipment": (True, "Betriebsausgabe — Werkzeuge, Maschinen, Sicherheitsausrüstung (AfA bei > €1.000)", None, None),
        "clothing": (True, "Betriebsausgabe — Sicherheitskleidung, Arbeitsschuhe, Helme", None, None),
        "insurance": (True, "Betriebsausgabe — Betriebshaftpflicht, Bauwesenversicherung", None, None),
    },
    # ── IT-Dienstleistung / Webdesign ──
    "it_dienstleistung": {
        "software": (True, "Betriebsausgabe — Softwarelizenzen, Cloud-Dienste, Hosting", None, None),
        "equipment": (True, "Betriebsausgabe — Computer, Monitor, Peripherie (GWG bis €1.000, AfA darüber)", None, None),
        "education": (True, "Betriebsausgabe — Zertifizierungen, Konferenzen, Online-Kurse", None, None),
        "groceries": (False, "Private Lebensführung — kein Wareneinsatz bei IT-Dienstleistung", None, None),
    },
    # ── Transport / Logistik ──
    "transport": {
        "vehicle": (True, "Betriebsausgabe — Lieferfahrzeug/LKW voll absetzbar", None, None),
        "fuel": (True, "Betriebsausgabe — Treibstoff, Maut, Vignette", None, None),
        "insurance": (True, "Betriebsausgabe — KFZ-Versicherung, Transportversicherung", None, None),
        "maintenance": (True, "Betriebsausgabe — Fahrzeugreparatur, Service, §57a", None, None),
    },
    # ── Reinigung / Gebäudeservice ──
    "reinigung": {
        "cleaning": (True, "Wareneinsatz — Reinigungsmittel, Desinfektionsmittel", None, None),
        "equipment": (True, "Betriebsausgabe — Reinigungsmaschinen, Staubsauger (AfA bei > €1.000)", None, None),
        "vehicle": (True, "Betriebsausgabe — Firmenfahrzeug für Kundenfahrten", None, None),
        "clothing": (True, "Betriebsausgabe — Arbeitskleidung, Schutzhandschuhe", None, None),
    },
    # ── Arzt / Zahnarzt ──
    "arzt": {
        "equipment": (True, "Betriebsausgabe — Medizinische Geräte, Praxisausstattung (AfA)", None, None),
        "education": (True, "Betriebsausgabe — Fortbildung (DFP-Punkte), Kongresse, Fachliteratur", None, None),
        "insurance": (True, "Betriebsausgabe — Berufshaftpflicht, Praxisversicherung", None, None),
        "clothing": (True, "Betriebsausgabe — Arztkittel, medizinische Schutzkleidung", None, None),
        "cleaning": (True, "Betriebsausgabe — Praxisreinigung, Desinfektion, Hygienematerial", None, None),
        "groceries": (False, "Private Lebensführung — kein Wareneinsatz in der Arztpraxis", None, None),
    },
    # ── Rechtsanwalt / Notar ──
    "rechtsanwalt": {
        "education": (True, "Betriebsausgabe — Fachliteratur, juristische Datenbanken (RIS, RDB)", None, None),
        "insurance": (True, "Betriebsausgabe — Berufshaftpflichtversicherung (Pflicht)", None, None),
        "groceries": (False, "Private Lebensführung — kein Wareneinsatz bei Rechtsanwälten", None, None),
    },
    # ── Steuerberater / Wirtschaftsprüfer ──
    "steuerberater": {
        "education": (True, "Betriebsausgabe — Fachliteratur, Fortbildung, ARGE-Tagungen", None, None),
        "software": (True, "Betriebsausgabe — BMD, RZL, DATEV, Buchhaltungssoftware", None, None),
        "insurance": (True, "Betriebsausgabe — Berufshaftpflicht (Pflicht), Kammer-Beitrag", None, None),
        "groceries": (False, "Private Lebensführung — kein Wareneinsatz", None, None),
    },
    # ── Trainer / Coach ──
    "trainer": {
        "education": (True, "Betriebsausgabe — Coaching-Ausbildung, Zertifizierungen, Supervision", None, None),
        "rent": (True, "Betriebsausgabe — Seminarraum-Miete, Co-Working-Space", None, None),
        "groceries": (_NEEDS_AI, "Kommt drauf an — Verpflegung für Seminarteilnehmer ja, privat nein", None, None),
        "marketing": (True, "Betriebsausgabe — Website, Online-Werbung (voll absetzbar)", None, None),
    },
    # ── Content Creator / Influencer ──
    "content_creator": {
        "equipment": (True, "Betriebsausgabe — Kamera, Mikrofon, Beleuchtung (AfA bei > €1.000)", None, None),
        "software": (True, "Betriebsausgabe — Adobe, Final Cut, Canva, Hosting", None, None),
        "marketing": (True, "Betriebsausgabe — Social Media Ads, Promotion (voll absetzbar)", None, None),
        "clothing": (_NEEDS_AI, "Kommt drauf an — Kostüme für Content evtl., normale Kleidung nicht", None, None),
        "groceries": (_NEEDS_AI, "Kommt drauf an — Food-Content ja, privater Einkauf nein", None, None),
    },
    # ── Weinbau / Winzer ──
    "weinbau": {
        "groceries": (True, "Wareneinsatz — Pflanzenschutz, Dünger, Flaschen, Korken, Etiketten", None, None),
        "equipment": (True, "Betriebsausgabe — Weinpresse, Tanks, Abfüllanlage (AfA)", None, None),
        "marketing": (True, "Betriebsausgabe — Verkostungen, Messestand, Direktvermarktung", None, None),
    },
    # ── Architekt / Ingenieur ──
    "architekt": {
        "software": (True, "Betriebsausgabe — CAD-Software, AutoCAD, ArchiCAD, BIM-Tools", None, None),
        "education": (True, "Betriebsausgabe — Fortbildung, Ziviltechnikerprüfung, Fachliteratur", None, None),
        "insurance": (True, "Betriebsausgabe — Berufshaftpflicht (Pflicht für Ziviltechniker)", None, None),
        "groceries": (False, "Private Lebensführung — kein Wareneinsatz", None, None),
    },
    # ── Künstler / Designer ──
    "kuenstler": {
        "equipment": (True, "Betriebsausgabe — Atelierbedarf, Materialien, Software (AfA bei > €1.000)", None, None),
        "groceries": (_NEEDS_AI, "Kommt drauf an — Kunstmaterialien ja, Lebensmittel nein", None, None),
        "rent": (True, "Betriebsausgabe — Atelier-/Studio-Miete", None, None),
        "education": (True, "Betriebsausgabe — Workshops, Kurse, Ausstellungsgebühren", None, None),
    },
}

# Which industries belong to which business_type (for UI cascading dropdown)
INDUSTRIES_BY_TYPE = {
    SelfEmployedType.FREIBERUFLER: [
        "arzt", "rechtsanwalt", "steuerberater", "it_dienstleistung",
        "architekt", "kuenstler",
    ],
    SelfEmployedType.GEWERBETREIBENDE: [
        "gastronomie", "hotel", "kosmetik", "handel", "ecommerce",
        "handwerk", "transport", "reinigung",
    ],
    SelfEmployedType.NEUE_SELBSTAENDIGE: [
        "trainer", "content_creator",
    ],
    SelfEmployedType.LAND_FORSTWIRTSCHAFT: [
        "weinbau",
    ],
}


def get_business_type_override(
    business_type: Optional[str],
    expense_category: str,
    business_industry: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get deductibility override for an expense category.

    Resolution order: industry override > business_type override > None (use base rules).

    Args:
        business_type: SelfEmployedType value string, or None
        expense_category: ExpenseCategory value string (lowercase)
        business_industry: Specific industry slug (e.g., "gastronomie"), or None

    Returns:
        Dict with keys: is_deductible, reason, max_amount, deductible_pct
        or None if no override exists (use base rules).
    """
    cat = expense_category.lower()

    # 1. Check industry-specific override first (highest priority)
    if business_industry:
        industry_rules = _INDUSTRY_OVERRIDES.get(business_industry.lower(), {})
        override = industry_rules.get(cat)
        if override:
            is_deductible, reason, max_amount, deductible_pct = override
            return {
                "is_deductible": is_deductible,
                "reason": reason,
                "max_amount": max_amount,
                "deductible_pct": deductible_pct,
            }

    # 2. Fall back to business_type override
    if not business_type:
        return None

    try:
        bt = SelfEmployedType(business_type)
    except ValueError:
        return None

    overrides = _OVERRIDES.get(bt, {})
    override = overrides.get(cat)
    if not override:
        return None

    is_deductible, reason, max_amount, deductible_pct = override
    return {
        "is_deductible": is_deductible,
        "reason": reason,
        "max_amount": max_amount,
        "deductible_pct": deductible_pct,
    }


def get_pauschalierung_type(business_type: Optional[str]) -> str:
    """Determine which Basispauschalierung rate to use.

    Returns:
        'consulting' for Freiberufler/Neue Selbständige (6%),
        'general' for Gewerbetreibende (12-15%),
        'agriculture' for Land- und Forstwirtschaft (special rules),
        'general' as default.
    """
    if not business_type:
        return "general"

    try:
        bt = SelfEmployedType(business_type)
    except ValueError:
        return "general"

    if bt in (SelfEmployedType.FREIBERUFLER, SelfEmployedType.NEUE_SELBSTAENDIGE):
        return "consulting"
    elif bt == SelfEmployedType.LAND_FORSTWIRTSCHAFT:
        return "agriculture"
    else:
        return "general"


# ── Typical expense categories per business type (for AI context) ──
# Used when sending OCR data to AI for better classification

# ── Industry-specific AI context for better OCR classification ──
INDUSTRY_CONTEXTS = {
    "gastronomie": {
        "typical_expenses": ["Lebensmittel", "Getränke", "Reinigungsmittel", "Küchengeräte", "Gas/Strom", "Arbeitskleidung"],
        "description_de": "Gastronomie (Restaurant, Café, Bar)",
        "description_en": "Gastronomy (restaurant, café, bar)",
        "description_zh": "餐饮业（餐厅、咖啡馆、酒吧）",
    },
    "hotel": {
        "typical_expenses": ["Bettwäsche", "Reinigung", "Frühstück", "Booking-Gebühren", "Heizung", "Internet"],
        "description_de": "Hotel / Pension / Beherbergung",
        "description_en": "Hotel / B&B / accommodation",
        "description_zh": "酒店/民宿/住宿业",
    },
    "kosmetik": {
        "typical_expenses": ["Kosmetikprodukte", "Behandlungsmaterial", "Hygienemittel", "Friseurbedarf", "Handtücher"],
        "description_de": "Kosmetik / Friseur / Beauty-Salon",
        "description_en": "Beauty / hairdresser / cosmetics salon",
        "description_zh": "美容/美发/美容院",
    },
    "handel": {
        "typical_expenses": ["Handelswaren", "Verpackung", "Ladeneinrichtung", "Kassensystem", "Warenversicherung"],
        "description_de": "Einzelhandel / Großhandel",
        "description_en": "Retail / wholesale",
        "description_zh": "零售/批发",
    },
    "ecommerce": {
        "typical_expenses": ["Handelswaren", "Versandkosten", "Shop-Software", "Online-Werbung", "Fulfillment"],
        "description_de": "E-Commerce / Online-Handel",
        "description_en": "E-commerce / online retail",
        "description_zh": "电商/网上零售",
    },
    "handwerk": {
        "typical_expenses": ["Baumaterial", "Werkzeuge", "Sicherheitskleidung", "Firmenfahrzeug", "Maschinenreparatur"],
        "description_de": "Handwerk / Baugewerbe",
        "description_en": "Crafts / construction",
        "description_zh": "手工业/建筑业",
    },
    "it_dienstleistung": {
        "typical_expenses": ["Softwarelizenzen", "Cloud-Hosting", "Computer", "Monitor", "Konferenztickets"],
        "description_de": "IT-Dienstleistung / Softwareentwicklung / Webdesign",
        "description_en": "IT services / software development / web design",
        "description_zh": "IT服务/软件开发/网页设计",
    },
    "transport": {
        "typical_expenses": ["Treibstoff", "Maut", "KFZ-Versicherung", "Fahrzeugreparatur", "Vignette"],
        "description_de": "Transport / Logistik / Lieferdienst",
        "description_en": "Transport / logistics / delivery",
        "description_zh": "运输/物流/快递",
    },
    "reinigung": {
        "typical_expenses": ["Reinigungsmittel", "Desinfektionsmittel", "Reinigungsmaschinen", "Arbeitskleidung"],
        "description_de": "Reinigung / Gebäudeservice",
        "description_en": "Cleaning / building services",
        "description_zh": "清洁/物业服务",
    },
    "arzt": {
        "typical_expenses": ["Medizingeräte", "Praxisbedarf", "Fortbildung", "Berufshaftpflicht", "Hygienematerial"],
        "description_de": "Arzt / Zahnarzt / Therapeut",
        "description_en": "Doctor / dentist / therapist",
        "description_zh": "医生/牙医/治疗师",
    },
    "rechtsanwalt": {
        "typical_expenses": ["Fachliteratur", "Juristische Datenbanken", "Kammerbeitrag", "Berufshaftpflicht"],
        "description_de": "Rechtsanwalt / Notar",
        "description_en": "Lawyer / notary",
        "description_zh": "律师/公证人",
    },
    "steuerberater": {
        "typical_expenses": ["BMD/RZL-Software", "Fachliteratur", "Kammerbeitrag", "Berufshaftpflicht", "Fortbildung"],
        "description_de": "Steuerberater / Wirtschaftsprüfer",
        "description_en": "Tax advisor / auditor",
        "description_zh": "税务顾问/审计师",
    },
    "trainer": {
        "typical_expenses": ["Seminarraum", "Coaching-Ausbildung", "Lehrmaterial", "Webhosting", "Online-Tools"],
        "description_de": "Trainer / Coach / Berater",
        "description_en": "Trainer / coach / consultant",
        "description_zh": "培训师/教练/顾问",
    },
    "content_creator": {
        "typical_expenses": ["Kamera", "Mikrofon", "Beleuchtung", "Adobe-Abo", "Social-Media-Werbung"],
        "description_de": "Content Creator / Influencer",
        "description_en": "Content creator / influencer",
        "description_zh": "内容创作者/网红",
    },
    "weinbau": {
        "typical_expenses": ["Pflanzenschutz", "Dünger", "Flaschen", "Korken", "Weinpresse", "Verkostung"],
        "description_de": "Weinbau / Winzer",
        "description_en": "Viticulture / winemaker",
        "description_zh": "葡萄酒种植/酒庄",
    },
    "architekt": {
        "typical_expenses": ["CAD-Software", "Plotterkosten", "Fachliteratur", "Ziviltechniker-Beitrag"],
        "description_de": "Architekt / Ingenieur / Ziviltechniker",
        "description_en": "Architect / engineer",
        "description_zh": "建筑师/工程师",
    },
    "kuenstler": {
        "typical_expenses": ["Atelierbedarf", "Kunstmaterialien", "Ausstellungsgebühren", "Atelier-Miete"],
        "description_de": "Künstler / Designer / Grafiker",
        "description_en": "Artist / designer / graphic designer",
        "description_zh": "艺术家/设计师/平面设计师",
    },
}

BUSINESS_TYPE_CONTEXTS = {
    SelfEmployedType.FREIBERUFLER: {
        "typical_expenses": [
            "Fachliteratur", "Fortbildung", "Kanzlei-/Praxis-Miete",
            "Berufshaftpflichtversicherung", "Berufskleidung",
            "Fachdatenbanken", "Standesbeiträge (Kammer)",
        ],
        "description_de": "Freiberufler (§22 EStG): Arzt, Anwalt, Steuerberater, IT-Berater, Architekt, Künstler",
        "description_en": "Liberal professional (§22 EStG): doctor, lawyer, accountant, IT consultant, architect, artist",
        "description_zh": "自由职业者 (§22 EStG)：医生、律师、会计师、IT顾问、建筑师、艺术家",
    },
    SelfEmployedType.GEWERBETREIBENDE: {
        "typical_expenses": [
            "Wareneinsatz", "Geschäftslokal-Miete", "Lieferfahrzeug",
            "Warenlager", "Verpackungsmaterial", "Handwerker-Werkzeug",
            "Gewerbeschein-Gebühren", "Betriebshaftpflicht",
        ],
        "description_de": "Gewerbetreibende (§23 EStG): Handel, Handwerk, Gastronomie, E-Commerce, Lieferdienste",
        "description_en": "Trade/business (§23 EStG): retail, crafts, restaurants, e-commerce, delivery",
        "description_zh": "工商经营者 (§23 EStG)：零售、手工业、餐饮、电商、配送",
    },
    SelfEmployedType.NEUE_SELBSTAENDIGE: {
        "typical_expenses": [
            "Seminarraum-Miete", "Online-Plattform-Gebühren",
            "Kamera/Mikrofon (Content)", "Coaching-Ausbildung",
            "Webhosting", "Software-Lizenzen",
        ],
        "description_de": "Neue Selbständige: Trainer, Coaches, Content Creators, Vortragende",
        "description_en": "New self-employed: trainers, coaches, content creators, lecturers",
        "description_zh": "新型自由职业者：培训师、教练、内容创作者、讲师",
    },
    SelfEmployedType.LAND_FORSTWIRTSCHAFT: {
        "typical_expenses": [
            "Saatgut", "Düngemittel", "Futtermittel", "Tierarzt",
            "Landmaschinen-Reparatur", "Hagelversicherung",
            "Direktvermarktung-Kosten",
        ],
        "description_de": "Land- und Forstwirtschaft (§21 EStG): Bauern, Winzer, Forstwirte",
        "description_en": "Agriculture & forestry (§21 EStG): farmers, vintners, foresters",
        "description_zh": "农林业 (§21 EStG)：农民、酒庄经营者、林业工作者",
    },
}
