"""Rule-based transaction classifier for Austrian merchants and patterns"""
import re
from decimal import Decimal
from typing import Optional

# Minimum keyword length for plain substring matching.
# Shorter keywords use word-boundary regex to avoid false positives
# (e.g. "drei" matching "dreieck", "a1" matching "ba1ance").
_MIN_SUBSTR_LEN = 5


def _keyword_matches(keyword: str, text: str) -> bool:
    """Check if *keyword* appears in *text* as a meaningful token.

    For short keywords (< _MIN_SUBSTR_LEN chars) we require word boundaries
    so that e.g. "drei" won't match "dreieck" and "a1" won't match "sa1do".
    Longer keywords are safe with plain ``in`` checks.
    """
    if len(keyword) >= _MIN_SUBSTR_LEN:
        return keyword in text
    return bool(re.search(r'(?<!\w)' + re.escape(keyword) + r'(?!\w)', text))


class ClassificationResult:
    def __init__(self, category, confidence, category_type=None):
        self.category = category
        self.confidence = confidence
        self.category_type = category_type

    def __repr__(self):
        return f"<ClassificationResult(category={self.category}, confidence={self.confidence})>"


# Online retailers / parcel services - skip merchant-name matching, use product keywords instead
ONLINE_RETAILERS = {"amazon", "gls", "dhl", "dpd", "post.at"}


class RuleBasedClassifier:
    SUPERMARKETS = {
        "billa": "groceries", "spar": "groceries", "hofer": "groceries",
        "lidl": "groceries", "merkur": "groceries", "penny": "groceries",
        "interspar": "groceries", "eurospar": "groceries",
        "unimarkt": "groceries", "mpreis": "groceries", "adeg": "groceries",
        "asia market": "groceries", "asia shop": "groceries",
    }
    HARDWARE_STORES = {
        "obi": "maintenance", "baumax": "maintenance", "bauhaus": "maintenance",
        "hornbach": "maintenance", "hagebau": "maintenance",
        "lagerhaus": "maintenance",
    }
    OFFICE_STORES = {
        "libro": "office_supplies", "pagro": "office_supplies",
        "staples": "office_supplies",
    }
    ELECTRONICS_STORES = {
        "mediamarkt": "equipment", "saturn": "equipment", "conrad": "equipment",
    }
    INSURANCE_COMPANIES = {
        "uniqa": "insurance", "generali": "insurance", "allianz": "insurance",
    }
    UTILITY_COMPANIES = {
        "wien energie": "utilities", "evn": "utilities", "verbund": "utilities",
    }
    TRAVEL_MERCHANTS = {
        "booking.com": "travel", "airbnb": "travel", "expedia": "travel",
        "flixbus": "travel", "ryanair": "travel", "wizz air": "travel",
    }
    GAS_STATIONS = {
        "omv": "vehicle", "shell": "vehicle", "avanti": "vehicle",
        "diesel": "vehicle", "benzin": "vehicle", "tankstelle": "vehicle",
    }
    INCOME_KEYWORDS = {
        # Nr.1 Land- und Forstwirtschaft (agriculture)
        "holzverkauf": "agriculture", "ernte": "agriculture",
        "obstbau": "agriculture", "imkerei": "agriculture",
        "honig": "agriculture", "forstwirtschaft": "agriculture",
        "landwirtschaft": "agriculture", "gartenbau": "agriculture",
        "waldgrundstück": "agriculture",
        # Nr.2 Selbstaendige Arbeit (self_employment)
        "honorar": "self_employment", "freiberuf": "self_employment",
        "gutachten": "self_employment", "sachverständig": "self_employment",
        "ordination": "self_employment",
        # Nr.3 Gewerbebetrieb (business)
        "umsatz": "business", "provision": "business", "erlös": "business",
        "tischlerei": "business", "warenverkauf": "business",
        "vermittlung": "business", "gewerbe": "business",
        "einzelhandel": "business", "gastronomie": "business",
        # Nr.4 Nichtselbstaendige Arbeit (employment)
        "gehalt": "employment", "lohn": "employment", "salary": "employment",
        "pension": "employment", "weihnachtsgeld": "employment",
        "urlaubsgeld": "employment", "überstunden": "employment",
        "abfertigung": "employment", "prämie": "employment",
        # Nr.5 Kapitalvermoegen (capital_gains)
        "dividende": "capital_gains", "kursgewinn": "capital_gains",
        "zinsen": "capital_gains", "bitcoin": "capital_gains",
        "krypto": "capital_gains", "aktien": "capital_gains",
        "fondsausschüttung": "capital_gains", "fonds": "capital_gains",
        "kest": "capital_gains",
        # Nr.6 Vermietung und Verpachtung (rental)
        "miete": "rental", "mieteinnahme": "rental", "rent": "rental",
        "pacht": "rental", "airbnb": "rental", "booking": "rental",
        "ferienwohnung": "rental", "homestay": "rental",
        "vermietung": "rental",
        # Nr.7 Sonstige Einkuenfte (other_income)
        "spekulationsgewinn": "other_income", "aufsichtsrat": "other_income",
        "veräußerungsgewinn": "other_income", "immoest": "other_income",
        "sonstige einkünfte": "other_income",
    }
    PRODUCT_KEYWORDS = {
        # maintenance / cleaning / household supplies for rental property
        "schneeschaufel": "maintenance", "schneeräumer": "maintenance",
        "auftausalz": "maintenance", "streusalz": "maintenance",
        "reinig": "maintenance", "reiniger": "maintenance",
        "schwamm": "maintenance", "scheuerschwamm": "maintenance",
        "mikrofaser": "maintenance", "sagrotan": "maintenance",
        "desinfekt": "maintenance", "biff": "maintenance",
        "viss": "maintenance", "fleckenentferner": "maintenance",
        "reparatur": "maintenance", "wartung": "maintenance",
        "putztü": "maintenance", "duschvorhang": "maintenance",
        "duschgel": "maintenance", "palmolive": "maintenance",
        "badreiniger": "maintenance", "seife": "maintenance",
        "toilettenpapier": "maintenance", "küchenrolle": "maintenance",
        # equipment / kitchen / appliances
        "heizung": "equipment", "infrarotheizung": "equipment",
        "heidenfeld": "equipment", "bratpfanne": "equipment",
        "pfanne": "equipment", "tefal": "equipment",
        "topf": "equipment", "besteck": "equipment",
        "geschirr": "equipment", "staubsauger": "equipment",
        "waschmaschine": "equipment", "drucker": "equipment",
        "laptop": "equipment", "computer": "equipment",
        "monitor": "equipment", "headset": "equipment",
        "kamera": "equipment",
        # office supplies
        "papier": "office_supplies", "toner": "office_supplies",
        "druckerpatrone": "office_supplies", "büro": "office_supplies",
        "porto": "office_supplies", "versand": "office_supplies",
        "paket": "office_supplies",
        # travel
        "reise": "travel", "hotel": "travel", "flug": "travel",
        "unterkunft": "travel", "commission": "travel",
        # marketing
        "marketing": "marketing", "werbung": "marketing",
        # professional services
        "steuerberater": "professional_services",
        "rechtsanwalt": "professional_services",
        "notar": "professional_services", "beratung": "professional_services",
        # insurance
        "versicherung": "insurance", "insurance": "insurance",
        # property tax
        "grundsteuer": "property_tax",
        # loan interest
        "kredit": "loan_interest", "darlehen": "loan_interest",
        "zinsen": "loan_interest", "hypothek": "loan_interest",
        # utilities
        "strom": "utilities", "gas": "utilities", "wasser": "utilities",
        "heizkosten": "utilities", "energie": "utilities",
        # vehicle (KFZ)
        "kfz": "vehicle", "autowerkstatt": "vehicle",
        "werkstatt": "vehicle", "parkgebühr": "vehicle",
        "parken": "vehicle",
        # telecom (Nachrichtenaufwand)
        "internet": "telecom", "telefon": "telecom", "handy": "telecom",
        "mobilfunk": "telecom", "a1": "telecom", "magenta": "telecom",
        "drei": "telecom",
        # rent (business premises)
        "büromiete": "rent", "geschaeftsmiete": "rent",
        # bank fees
        "kontoführung": "bank_fees", "bankspesen": "bank_fees",
        "bankgebühr": "bank_fees",
        # SVS contributions
        "svs": "svs_contributions", "sva": "svs_contributions",
        "sozialversicherung": "svs_contributions",
        # commuting
        "pendlerpauschale": "commuting", "fahrtkosten": "commuting",
        "vignette": "commuting", "maut": "commuting",
        # home office
        "home office": "home_office", "homeoffice": "home_office",
        "schreibtisch": "home_office",
        # cleaning
        "reinigungsmittel": "cleaning", "spülmittel": "cleaning",
        "desinfektionsmittel": "cleaning", "hygienemittel": "cleaning",
        # clothing (work clothing)
        "arbeitskleidung": "clothing", "schürze": "clothing",
        "arbeitsschuhe": "clothing", "schutzkleidung": "clothing",
        "sicherheitsschuhe": "clothing", "kochuniform": "clothing",
        # software
        "lizenz": "software", "software": "software",
        "adobe": "software", "microsoft": "software",
        "hosting": "software", "cloud": "software",
        "saas": "software", "abonnement": "software",
        # shipping
        "versandkosten": "shipping", "verpackungsmaterial": "shipping",
        "fulfillment": "shipping", "frankierung": "shipping",
        # fuel
        "diesel": "fuel", "benzin": "fuel",
        "tankstelle": "fuel", "treibstoff": "fuel",
        # education
        "fortbildung": "education", "weiterbildung": "education",
        "seminar": "education", "kurs": "education",
        "zertifizierung": "education", "schulung": "education",
        "fachliteratur": "education", "fachbuch": "education",
        "konferenz": "education", "kongress": "education",
        # groceries
        "lebensmittel": "groceries", "nahrung": "groceries",
        # property management fees
        "hausverwaltung": "property_management_fees",
        "immobilienverwaltung": "property_management_fees",
        "verwaltungskosten": "property_management_fees",
        "hausmeister": "property_management_fees",
        # property insurance
        "gebäudeversicherung": "property_insurance",
        "immobilienversicherung": "property_insurance",
        "eigenheimversicherung": "property_insurance",
        "wohnungsversicherung": "property_insurance",
        # depreciation (AfA)
        "afa": "depreciation_afa",
        "abschreibung": "depreciation_afa",
        "absetzung": "depreciation_afa",
    }

    def classify(self, transaction):
        if not transaction.description:
            return ClassificationResult(None, Decimal("0.0"))
        description_lower = transaction.description.lower()
        txn_type = str(transaction.type.value) if hasattr(transaction.type, "value") else str(transaction.type)
        if "income" in txn_type.lower():
            return self._classify_income(description_lower)
        return self._classify_expense(description_lower)

    def _classify_income(self, description):
        for kw, cat in self.INCOME_KEYWORDS.items():
            if _keyword_matches(kw, description):
                return ClassificationResult(cat, Decimal("0.85"), "income")
        return ClassificationResult("employment", Decimal("0.3"), "income")

    def _classify_expense(self, description):
        # Check for specific property-related keywords first (higher priority)
        # These need to be checked before generic merchant matching
        property_specific_keywords = {
            "gebäudeversicherung": "property_insurance",
            "immobilienversicherung": "property_insurance",
            "eigenheimversicherung": "property_insurance",
            "wohnungsversicherung": "property_insurance",
            "hausverwaltung": "property_management_fees",
            "immobilienverwaltung": "property_management_fees",
            "verwaltungskosten": "property_management_fees",
            # Chimney sweep / building maintenance
            "rauchfangkehrer": "maintenance",
            "kaminkehrer": "maintenance",
            "schornsteinfeger": "maintenance",
            "kaminfeger": "maintenance",
            # Property taxes and municipal fees
            "nachtigungstaxe": "property_tax",
            "nächtigungstaxe": "property_tax",
            "ortstaxe": "property_tax",
            "kurtaxe": "property_tax",
            "kommunalsteuer": "property_tax",
            # Municipal utility fees
            "kanalbenutzungsgebühr": "utilities",
            "kanalgebühr": "utilities",
            "wasserbezugsgebühr": "utilities",
            "wassergebühr": "utilities",
            "müllabfuhr": "utilities",
            "abfallgebühr": "utilities",
        }
        
        for kw, cat in property_specific_keywords.items():
            if _keyword_matches(kw, description):
                return ClassificationResult(cat, Decimal("0.85"), "expense")
        
        is_online = any(_keyword_matches(r, description) for r in ONLINE_RETAILERS)
        if not is_online:
            for db, conf in [
                (self.SUPERMARKETS, Decimal("0.90")),
                (self.HARDWARE_STORES, Decimal("0.85")),
                (self.OFFICE_STORES, Decimal("0.85")),
                (self.ELECTRONICS_STORES, Decimal("0.85")),
                (self.INSURANCE_COMPANIES, Decimal("0.90")),
                (self.UTILITY_COMPANIES, Decimal("0.90")),
                (self.TRAVEL_MERCHANTS, Decimal("0.90")),
                (self.GAS_STATIONS, Decimal("0.85")),
            ]:
                for merchant, category in db.items():
                    if _keyword_matches(merchant, description):
                        return ClassificationResult(category, conf, "expense")
        for kw, cat in self.PRODUCT_KEYWORDS.items():
            if _keyword_matches(kw, description):
                return ClassificationResult(cat, Decimal("0.80"), "expense")
        return ClassificationResult("other", Decimal("0.3"), "expense")

    def get_confidence_score(self, transaction):
        return self.classify(transaction).confidence
