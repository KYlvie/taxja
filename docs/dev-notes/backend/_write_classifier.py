"""Script to write the rule_based_classifier.py file cleanly."""
import os

filepath = os.path.join('app', 'services', 'rule_based_classifier.py')

content = r'''"""Rule-based transaction classifier for Austrian merchants and patterns"""
from decimal import Decimal
from typing import Optional


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
        u"waldgrundst\u00fcck": "agriculture",
        # Nr.2 Selbstaendige Arbeit (self_employment)
        "honorar": "self_employment", "freiberuf": "self_employment",
        "gutachten": "self_employment", u"sachverst\u00e4ndig": "self_employment",
        "ordination": "self_employment",
        # Nr.3 Gewerbebetrieb (business)
        "umsatz": "business", "provision": "business", u"erl\u00f6s": "business",
        "tischlerei": "business", "warenverkauf": "business",
        "vermittlung": "business", "gewerbe": "business",
        "einzelhandel": "business", "gastronomie": "business",
        # Nr.4 Nichtselbstaendige Arbeit (employment)
        "gehalt": "employment", "lohn": "employment", "salary": "employment",
        "pension": "employment", "weihnachtsgeld": "employment",
        "urlaubsgeld": "employment", u"\u00fcberstunden": "employment",
        "abfertigung": "employment", u"pr\u00e4mie": "employment",
        # Nr.5 Kapitalvermoegen (capital_gains)
        "dividende": "capital_gains", "kursgewinn": "capital_gains",
        "zinsen": "capital_gains", "bitcoin": "capital_gains",
        "krypto": "capital_gains", "aktien": "capital_gains",
        u"fondsaussch\u00fcttung": "capital_gains", "fonds": "capital_gains",
        "kest": "capital_gains",
        # Nr.6 Vermietung und Verpachtung (rental)
        "miete": "rental", "mieteinnahme": "rental", "rent": "rental",
        "pacht": "rental", "airbnb": "rental", "booking": "rental",
        "ferienwohnung": "rental", "homestay": "rental",
        "vermietung": "rental",
        # Nr.7 Sonstige Einkuenfte (other_income)
        "spekulationsgewinn": "other_income", "aufsichtsrat": "other_income",
        u"ver\u00e4u\u00dferungsgewinn": "other_income", "immoest": "other_income",
        u"sonstige eink\u00fcnfte": "other_income",
    }
'''

content += r'''    PRODUCT_KEYWORDS = {
        # maintenance / cleaning / household supplies for rental property
        "schneeschaufel": "maintenance", u"schneer\u00e4umer": "maintenance",
        "auftausalz": "maintenance", "streusalz": "maintenance",
        "reinig": "maintenance", "reiniger": "maintenance",
        "schwamm": "maintenance", "scheuerschwamm": "maintenance",
        "mikrofaser": "maintenance", "sagrotan": "maintenance",
        "desinfekt": "maintenance", "biff": "maintenance",
        "viss": "maintenance", "fleckenentferner": "maintenance",
        "reparatur": "maintenance", "wartung": "maintenance",
        u"putzt\u00fc": "maintenance", "duschvorhang": "maintenance",
        "duschgel": "maintenance", "palmolive": "maintenance",
        "badreiniger": "maintenance", "seife": "maintenance",
        "toilettenpapier": "maintenance", u"k\u00fcchenrolle": "maintenance",
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
        "druckerpatrone": "office_supplies", u"b\u00fcro": "office_supplies",
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
        # utilities
        "strom": "utilities",
        # vehicle (KFZ)
        "kfz": "vehicle", "autowerkstatt": "vehicle",
        "werkstatt": "vehicle", u"parkgeb\u00fchr": "vehicle",
        "parken": "vehicle",
        # telecom (Nachrichtenaufwand)
        "internet": "telecom", "telefon": "telecom", "handy": "telecom",
        "mobilfunk": "telecom", "a1": "telecom", "magenta": "telecom",
        "drei": "telecom",
        # rent (business premises)
        u"b\u00fcromiete": "rent", "geschaeftsmiete": "rent",
        # bank fees
        u"kontof\u00fchrung": "bank_fees", "bankspesen": "bank_fees",
        u"bankgeb\u00fchr": "bank_fees",
        # SVS contributions
        "svs": "svs_contributions", "sva": "svs_contributions",
        "sozialversicherung": "svs_contributions",
        # commuting
        "pendlerpauschale": "commuting", "fahrtkosten": "commuting",
        "vignette": "commuting", "maut": "commuting",
        # home office
        "home office": "home_office", "homeoffice": "home_office",
        "schreibtisch": "home_office",
        # groceries
        "lebensmittel": "groceries", "nahrung": "groceries",
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
            if kw in description:
                return ClassificationResult(cat, Decimal("0.85"), "income")
        return ClassificationResult("employment", Decimal("0.3"), "income")

    def _classify_expense(self, description):
        is_online = any(r in description for r in ONLINE_RETAILERS)
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
                    if merchant in description:
                        return ClassificationResult(category, conf, "expense")
        for kw, cat in self.PRODUCT_KEYWORDS.items():
            if kw in description:
                return ClassificationResult(cat, Decimal("0.80"), "expense")
        return ClassificationResult("other", Decimal("0.3"), "expense")

    def get_confidence_score(self, transaction):
        return self.classify(transaction).confidence
'''

# Write with explicit flush and fsync
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
    f.flush()
    os.fsync(f.fileno())

# Verify immediately
with open(filepath, 'r', encoding='utf-8') as f:
    written = f.read()

print(f"Written {len(written)} chars")
print(f"agriculture count: {written.count('agriculture')}")
print(f"business count: {written.count('business')}")
print(f"other_income count: {written.count('other_income')}")
