"""Document type classification for OCR"""
import re
from enum import Enum
from typing import Tuple, Dict, Optional
import numpy as np


class DocumentType(str, Enum):
    """Supported document types"""

    PAYSLIP = "payslip"  # Lohnzettel / Gehaltsabrechnung
    RECEIPT = "receipt"  # Supermarket receipt / Kassenbon
    INVOICE = "invoice"  # Rechnung
    RENTAL_CONTRACT = "rental_contract"  # Mietvertrag
    LOAN_CONTRACT = "loan_contract"  # Kreditvertrag / Darlehensvertrag
    KAUFVERTRAG = "kaufvertrag"  # Property purchase contract
    MIETVERTRAG = "mietvertrag"  # Rental contract (detailed)
    BANK_STATEMENT = "bank_statement"  # Kontoauszug
    PROPERTY_TAX = "property_tax"  # Grundsteuer
    SVS_NOTICE = "svs_notice"  # SVS Beitragsmitteilung
    LOHNZETTEL = "lohnzettel"  # Official tax wage slip
    EINKOMMENSTEUERBESCHEID = "einkommensteuerbescheid"  # Income tax assessment
    E1_FORM = "e1_form"  # E1 tax declaration form
    L1_FORM = "l1_form"  # L1 employee tax return
    L1K_BEILAGE = "l1k_beilage"  # L1k child supplement
    L1AB_BEILAGE = "l1ab_beilage"  # L1ab deductions supplement
    E1A_BEILAGE = "e1a_beilage"  # E1a self-employment supplement
    E1B_BEILAGE = "e1b_beilage"  # E1b rental income supplement
    E1KV_BEILAGE = "e1kv_beilage"  # E1kv capital gains supplement
    U1_FORM = "u1_form"  # U1 annual VAT declaration
    U30_FORM = "u30_form"  # U30 VAT advance return (UVA)
    JAHRESABSCHLUSS = "jahresabschluss"  # Annual financial statement
    SPENDENBESTAETIGUNG = "spendenbestaetigung"  # Donation confirmation
    VERSICHERUNGSBESTAETIGUNG = "versicherungsbestaetigung"  # Insurance confirmation
    KINDERBETREUUNGSKOSTEN = "kinderbetreuungskosten"  # Childcare cost receipt
    FORTBILDUNGSKOSTEN = "fortbildungskosten"  # Continuing education cost receipt
    PENDLERPAUSCHALE = "pendlerpauschale"  # Commuter allowance confirmation
    KIRCHENBEITRAG = "kirchenbeitrag"  # Church tax confirmation
    GRUNDBUCHAUSZUG = "grundbuchauszug"  # Land registry extract
    BETRIEBSKOSTENABRECHNUNG = "betriebskostenabrechnung"  # Operating cost statement
    GEWERBESCHEIN = "gewerbeschein"  # Trade license
    KONTOAUSZUG = "kontoauszug"  # Bank account statement
    UNKNOWN = "unknown"


def _normalize_umlauts(text: str) -> str:
    """Normalize German umlauts and sharp-s to ASCII equivalents.

    This ensures keyword matching works regardless of whether the OCR engine
    or PDF text layer uses proper Unicode umlauts (ä, ö, ü, ß) or their ASCII
    transliterations (ae, oe, ue, ss).  We match against BOTH forms.
    """
    return (
        text
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
    )


class DocumentClassifier:
    """Classify document types based on content and patterns"""

    def __init__(self):
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> Dict[DocumentType, Dict]:
        """Load classification patterns for each document type"""
        return {
            DocumentType.LOHNZETTEL: {
                "keywords": [
                    "lohnzettel",
                    "gehaltszettel",
                    "gehaltsabrechnung",
                    "brutto",
                    "netto",
                    "lohnsteuer",
                    "sozialversicherung",
                    "arbeitgeber",
                    "arbeitnehmer",
                    "gehalt",
                    "auszahlungsbetrag",
                    "auszahlungsmonat",
                    "personalnummer",
                    "sv/kfa",
                    "summe abz",
                    "summe bez",
                    "pendlereuro",
                    "familienbonus",
                    "lst-basis",
                    "sv-basis",
                    "l16",
                    "finanzamt",
                    "steuernummer",
                    "versicherungsnummer",
                ],
                "required_keywords": [],
                "required_any": ["gehalt", "lohnsteuer", "auszahlungsbetrag",
                                 "gehaltszettel", "lohnzettel", "gehaltsabrechnung",
                                 "auszahlungsmonat", "personalnummer", "l16"],
                "weight": 1.3,
            },
            DocumentType.RECEIPT: {
                "keywords": [
                    "billa",
                    "spar",
                    "hofer",
                    "lidl",
                    "merkur",
                    "penny",
                    "kassenbon",
                    "bon-nr",
                    "kasse",
                    "summe",
                    "bar",
                    "karte",
                ],
                "required_keywords": [],
                "weight": 0.9,
            },
            DocumentType.INVOICE: {
                "keywords": [
                    "rechnung",
                    "rechnungsnummer",
                    "invoice",
                    "ust-id",
                    "uid",
                    "zahlbar",
                    "lieferant",
                    "kunde",
                    "gesamtpreis",
                    "zahlbetrag",
                    "rechnungsbetrag",
                    "total amount due",
                    "payment due",
                    "commission",
                ],
                "required_keywords": [],
                "weight": 1.0,
            },
            DocumentType.SVS_NOTICE: {
                "keywords": [
                    "svs",
                    "sozialversicherung",
                    "beitrag",
                    "versicherungsnummer",
                    "beitragsgrundlage",
                    "pensionsversicherung",
                    "krankenversicherung",
                    "unfallversicherung",
                ],
                "required_keywords": ["svs", "beitrag"],
                "weight": 1.0,
            },
            DocumentType.RENTAL_CONTRACT: {
                "keywords": [
                    "mietvertrag",
                    "miete",
                    "vermieter",
                    "mieter",
                    "wohnung",
                    "kaution",
                    "mietbeginn",
                    "mietdauer",
                    "lager",
                    "kontoeingang",
                    "pacht",
                ],
                "required_keywords": [],
                "required_any": ["mietvertrag", "miete", "vermieter", "pacht"],
                "weight": 1.0,
            },
            DocumentType.LOAN_CONTRACT: {
                "keywords": [
                    "kreditvertrag",
                    "darlehensvertrag",
                    "kreditnehmer",
                    "darlehensnehmer",
                    "kreditgeber",
                    "darlehensgeber",
                    "kreditbetrag",
                    "darlehensbetrag",
                    "vertragsnummer",
                    "zinssatz",
                    "aktueller zinssatz",
                    "laufzeit",
                    "vertragsbeginn",
                    "vertragsende",
                    "monatliche rate",
                    "annuitaet",
                    "sondertilgung",
                    "vorfaelligkeitsentschaedigung",
                    "wohnbaukredit",
                    "hypothekarkredit",
                    "rueckzahlung",
                    "tilgungsform",
                ],
                "required_keywords": [],
                "required_any": [
                    "kreditvertrag",
                    "darlehensvertrag",
                    "kreditbetrag",
                    "darlehensbetrag",
                    "kreditnehmer",
                    "darlehensnehmer",
                ],
                "weight": 1.2,
            },
            DocumentType.KAUFVERTRAG: {
                "keywords": [
                    "kaufvertrag",
                    "kaufpreis",
                    "käufer",
                    "kaufer",
                    "verkäufer",
                    "verkaufer",
                    "grundstück",
                    "grundstuck",
                    "liegenschaft",
                    "eigentum",
                    "notar",
                    "grundbuch",
                    "einlagezahl",
                    "katastralgemeinde",
                    "grunderwerbsteuer",
                    "übergabe",
                    "ubergabe",
                    "übernahme",
                    "ubernahme",
                    "immobilie",
                    "wohnungseigentum",
                    "kaufgegenstand",
                    "kaufobjekt",
                    "gebäude",
                    "gebaude",
                    "baujahr",
                    "nutzfläche",
                    "nutzflache",
                    "als kauferin",
                    "als käuferin",
                    "fahrgestellnummer",
                    "fahrzeug",
                    "kfz",
                    "pkw",
                    "zulassung",
                    "marke",
                    "modell",
                    "kilometerstand",
                    "erstzulassung",
                    "typenschein",
                    "motorleistung",
                    "hubraum",
                    "seriennummer",
                    "garantie",
                    "gewährleistung",
                    "gewaehrleistung",
                    "lieferschein",
                    "anschaffung",
                ],
                "required_keywords": [],
                "required_any": ["kaufvertrag", "kaufpreis", "käufer", "kaufer",
                                 "verkäufer", "verkaufer", "grundstück", "grundstuck",
                                 "fahrgestellnummer", "fahrzeug", "kfz", "pkw",
                                 "zulassung", "typenschein"],
                "weight": 1.2,
            },
            DocumentType.MIETVERTRAG: {
                "keywords": [
                    "mietvertrag",
                    "mietzins",
                    "hauptmietzins",
                    "betriebskosten",
                    "vermieter",
                    "mieter",
                    "mietobjekt",
                    "mietgegenstand",
                    "wohnung",
                    "kaution",
                    "mietbeginn",
                    "mietdauer",
                    "kündigungsfrist",
                    "kundigungsfrist",
                    "befristung",
                    "unbefristet",
                    "indexanpassung",
                    "heizkosten",
                    "warmwasser",
                    "strom",
                    "gas",
                    "mietrechtsgesetz",
                    "kategorie",
                ],
                "required_keywords": [],
                "required_any": ["mietvertrag", "mietzins", "hauptmietzins", "mietobjekt", "mietgegenstand"],
                "weight": 1.2,
            },
            DocumentType.BANK_STATEMENT: {
                "keywords": [
                    "kontoauszug",
                    "iban",
                    "bic",
                    "saldo",
                    "buchung",
                    "lastschrift",
                    "gutschrift",
                    "kontoeingang",
                    "kontostand",
                ],
                "required_keywords": [],
                "required_any": ["kontoauszug", "saldo", "buchung", "kontostand"],
                "weight": 0.9,
            },
            DocumentType.PROPERTY_TAX: {
                "keywords": [
                    "grundsteuer",
                    "immobiliensteuer",
                    "liegenschaft",
                    "einheitswert",
                    "steuernummer",
                ],
                "required_keywords": ["grundsteuer"],
                "weight": 1.0,
            },
            DocumentType.EINKOMMENSTEUERBESCHEID: {
                "keywords": [
                    "einkommensteuerbescheid",
                    "steuerberechnung",
                    "einkommensteuer",
                    "abgabengutschrift",
                    "abgabennachforderung",
                    "festgesetzte einkommensteuer",
                    "gesamtbetrag der einkuenfte",
                    "gesamtbetrag der einkünfte",
                    "steuer vor abzug",
                    "steuer nach abzug",
                    "absetzbetraege",
                    "absetzbeträge",
                    "verkehrsabsetzbetrag",
                    "anrechenbare lohnsteuer",
                    "negativsteuer",
                    "finanzamt",
                    "einkommen im jahr",
                ],
                "required_keywords": [],
                "required_any": [
                    "einkommensteuerbescheid",
                    "steuerberechnung",
                    "festgesetzte einkommensteuer",
                    "abgabengutschrift",
                    "abgabennachforderung",
                ],
                "weight": 1.5,
            },
            DocumentType.E1_FORM: {
                "keywords": [
                    "einkommensteuererklärung",
                    "einkommensteuererklaerung",
                    "e 1-edv",
                    "e 1-pdf",
                    "e 1, seite",
                    "e1-pdf",
                    "formular e1",
                    "steuererklärung",
                    "steuererklaerung",
                    "veranlagung",
                    "kennzahl",
                    "kz 245",
                    "kz 350",
                    "nichtselbständiger arbeit",
                    "nichtselbstaendiger arbeit",
                    "vermietung und verpachtung",
                    "sonderausgaben",
                    "werbungskosten",
                    "außergewöhnliche belastungen",
                    "aussergewoehnliche belastungen",
                    "verlustvortrag",
                    "familienbonus",
                    "einkünfte aus selbständiger arbeit",
                    "einkuenfte aus selbstaendiger arbeit",
                    "einnahmen-ausgaben-rechnung",
                    "einnahmen ausgaben rechnung",
                    "gewinnfreibetrag",
                    "bundesministerium für finanzen",
                    "bundesministerium fuer finanzen",
                    "finanzamt",
                    "formular e 1",
                    "erklaerung",
                    "erklärung",
                    "einkuenfte aus vermietung",
                    "einkünfte aus vermietung",
                ],
                "required_keywords": [],
                "required_any": [
                    "einkommensteuererklärung",
                    "einkommensteuererklaerung",
                    "e 1-edv",
                    "e 1-pdf",
                    "e1-pdf",
                    "e 1, seite",
                    "steuererklärung für",
                    "steuererklaerung fuer",
                    "steuererklaerung fur",
                    "formular e 1",
                    "formular e1",
                    "finanzamt",
                    "bundesministerium für finanzen",
                    "bundesministerium fuer finanzen",
                ],
                "weight": 1.8,
            },
            DocumentType.L1_FORM: {
                "keywords": [
                    "arbeitnehmerveranlagung",
                    "arbeitnehmerinnenveranlagung",
                    "l 1", "l1",
                    "werbungskosten",
                    "sonderausgaben",
                    "außergewöhnliche belastungen",
                    "aussergewoehnliche belastungen",
                    "pendlerpauschale",
                    "kirchenbeitrag",
                    "spenden",
                    "fortbildungskosten",
                    "arbeitsmittel",
                    "fachliteratur",
                    "reisekosten",
                    "kz 717", "kz 719", "kz 720", "kz 721",
                    "kz 722", "kz 723", "kz 724",
                    "kz 450", "kz 458", "kz 459",
                    "kz 730", "kz 740",
                ],
                "required_keywords": [],
                "required_any": [
                    "arbeitnehmerveranlagung", "arbeitnehmerinnenveranlagung",
                    "l 1-pdf", "l1-pdf", "formular l 1", "formular l1",
                ],
                "weight": 1.7,
            },
            DocumentType.L1K_BEILAGE: {
                "keywords": [
                    "l1k", "l 1k",
                    "beilage für kinder",
                    "beilage fuer kinder",
                    "familienbonus plus",
                    "familienbonus",
                    "kindermehrbetrag",
                    "unterhaltsabsetzbetrag",
                    "kz 770", "kz 771", "kz 772",
                    "kind", "kinder",
                    "geburtsdatum",
                ],
                "required_keywords": [],
                "required_any": [
                    "l1k", "l 1k", "beilage für kinder", "beilage fuer kinder",
                    "familienbonus plus", "kindermehrbetrag",
                ],
                "weight": 1.6,
            },
            DocumentType.L1AB_BEILAGE: {
                "keywords": [
                    "l1ab", "l 1ab",
                    "absetzbeträge", "absetzbetraege",
                    "alleinverdienerabsetzbetrag",
                    "alleinerzieherabsetzbetrag",
                    "alleinverdiener",
                    "alleinerzieher",
                    "pendlerpauschale",
                    "pendlereuro",
                    "unterhaltsabsetzbetrag",
                    "km entfernung",
                    "öffentliches verkehrsmittel",
                    "oeffentliches verkehrsmittel",
                ],
                "required_keywords": [],
                "required_any": [
                    "l1ab", "l 1ab",
                    "alleinverdienerabsetzbetrag", "alleinerzieherabsetzbetrag",
                ],
                "weight": 1.6,
            },
            DocumentType.E1A_BEILAGE: {
                "keywords": [
                    "e1a", "e 1a",
                    "beilage zur einkommensteuererklärung",
                    "beilage zur einkommensteuererklaerung",
                    "selbständige arbeit",
                    "selbstaendige arbeit",
                    "einnahmen-ausgaben-rechnung",
                    "einnahmen ausgaben rechnung",
                    "betriebseinnahmen",
                    "betriebsausgaben",
                    "gewinnfreibetrag",
                    "betriebsausgabenpauschale",
                    "wareneinkauf",
                    "personalaufwand",
                    "abschreibung",
                ],
                "required_keywords": [],
                "required_any": [
                    "e1a", "e 1a", "e 1a-pdf", "e1a-pdf",
                    "betriebseinnahmen", "betriebsausgaben",
                    "selbständige arbeit", "selbstaendige arbeit",
                ],
                "weight": 1.7,
            },
            DocumentType.E1B_BEILAGE: {
                "keywords": [
                    "e1b", "e 1b",
                    "vermietung und verpachtung",
                    "mieteinnahmen",
                    "kz 9460", "kz 9500", "kz 9510", "kz 9520", "kz 9530",
                    "kz 9414",
                    "afa", "absetzung für abnutzung",
                    "absetzung fuer abnutzung",
                    "fremdfinanzierung",
                    "instandhaltung",
                    "werbungskosten vermietung",
                ],
                "required_keywords": [],
                "required_any": [
                    "e1b", "e 1b", "e 1b-pdf", "e1b-pdf",
                    "vermietung und verpachtung",
                    "kz 9460", "kz 9414",
                ],
                "weight": 1.7,
            },
            DocumentType.E1KV_BEILAGE: {
                "keywords": [
                    "e1kv", "e 1kv",
                    "kapitalvermögen", "kapitalvermoegen",
                    "kapitalertragsteuer", "kest",
                    "kryptowährung", "kryptowaehrung",
                    "aktiengewinne",
                    "dividenden",
                    "zinserträge", "zinsertraege",
                    "fondsgewinne",
                    "27,5%",
                    "endbesteuerung",
                ],
                "required_keywords": [],
                "required_any": [
                    "e1kv", "e 1kv", "e 1kv-pdf", "e1kv-pdf",
                    "kapitalvermögen", "kapitalvermoegen",
                    "kapitalertragsteuer",
                ],
                "weight": 1.7,
            },
            DocumentType.U1_FORM: {
                "keywords": [
                    "umsatzsteuererklärung", "umsatzsteuererklaerung",
                    "u 1", "u1",
                    "jahresumsatzsteuer",
                    "umsatzsteuer",
                    "vorsteuer",
                    "lieferungen und leistungen",
                    "steuerbarer umsatz",
                    "steuerpflichtiger umsatz",
                    "20%", "13%", "10%",
                    "innergemeinschaftliche",
                    "zahllast",
                ],
                "required_keywords": [],
                "required_any": [
                    "umsatzsteuererklärung", "umsatzsteuererklaerung",
                    "u 1-pdf", "u1-pdf", "formular u 1", "formular u1",
                    "jahresumsatzsteuer",
                ],
                "weight": 1.5,
            },
            DocumentType.U30_FORM: {
                "keywords": [
                    "umsatzsteuervoranmeldung",
                    "u 30", "u30",
                    "uva",
                    "voranmeldung",
                    "voranmeldungszeitraum",
                    "umsatzsteuer",
                    "vorsteuer",
                    "zahllast",
                    "monat", "quartal",
                ],
                "required_keywords": [],
                "required_any": [
                    "umsatzsteuervoranmeldung",
                    "u 30-pdf", "u30-pdf", "formular u 30", "formular u30",
                    "voranmeldung",
                ],
                "weight": 1.5,
            },
            DocumentType.JAHRESABSCHLUSS: {
                "keywords": [
                    "jahresabschluss",
                    "einnahmen-ausgaben-rechnung",
                    "einnahmen ausgaben rechnung",
                    "bilanz",
                    "gewinn- und verlustrechnung",
                    "gewinn und verlustrechnung",
                    "betriebsergebnis",
                    "bilanzsumme",
                    "eigenkapital",
                    "fremdkapital",
                    "anlagevermögen", "anlagevermoegen",
                    "umlaufvermögen", "umlaufvermoegen",
                    "rückstellungen", "rueckstellungen",
                    "abschreibungen",
                ],
                "required_keywords": [],
                "required_any": [
                    "jahresabschluss",
                    "bilanz",
                    "gewinn- und verlustrechnung",
                    "gewinn und verlustrechnung",
                ],
                "weight": 1.3,
            },
            DocumentType.SPENDENBESTAETIGUNG: {
                "keywords": [
                    "spendenbestätigung", "spendenbestaetigung",
                    "spendenbescheinigung",
                    "spende", "spenden",
                    "zuwendungsbestätigung", "zuwendungsbestaetigung",
                    "gemeinnützig", "gemeinnuetzig",
                    "absetzbar", "sonderausgaben",
                    "§ 4a", "§4a",
                    "spendenorganisation",
                    "registrierungsnummer",
                ],
                "required_keywords": [],
                "required_any": [
                    "spendenbestätigung", "spendenbestaetigung",
                    "spendenbescheinigung",
                    "zuwendungsbestätigung", "zuwendungsbestaetigung",
                ],
                "weight": 1.2,
            },
            DocumentType.VERSICHERUNGSBESTAETIGUNG: {
                "keywords": [
                    "versicherungsbestätigung", "versicherungsbestaetigung",
                    "versicherungspolizze", "polizze",
                    "versicherungsnehmer",
                    "prämie", "praemie",
                    "versicherungssumme",
                    "deckung",
                    "haftpflicht", "haushaltsversicherung",
                    "rechtsschutz", "unfallversicherung",
                    "lebensversicherung", "krankenversicherung",
                    "zusatzversicherung",
                    "versicherungsvertrag",
                    "versicherungsschein",
                ],
                "required_keywords": [],
                "required_any": [
                    "versicherungsbestätigung", "versicherungsbestaetigung",
                    "versicherungspolizze", "polizze",
                    "versicherungsschein", "versicherungsvertrag",
                ],
                "weight": 1.0,
            },
            DocumentType.KINDERBETREUUNGSKOSTEN: {
                "keywords": [
                    "kinderbetreuung", "kinderbetreuungskosten",
                    "kindergarten", "kindertagesstätte", "kindertagesstaette",
                    "hort", "tagesmutter",
                    "betreuungskosten",
                    "betreuungseinrichtung",
                    "pädagogisch", "paedagogisch",
                    "kind", "kinder",
                    "betreuungsgeld",
                    "nachmittagsbetreuung",
                ],
                "required_keywords": [],
                "required_any": [
                    "kinderbetreuung", "kinderbetreuungskosten",
                    "betreuungskosten", "kindergarten",
                    "tagesmutter",
                ],
                "weight": 1.1,
            },
            DocumentType.FORTBILDUNGSKOSTEN: {
                "keywords": [
                    "fortbildung", "fortbildungskosten",
                    "weiterbildung", "weiterbildungskosten",
                    "kursbestätigung", "kursbestaetigung",
                    "seminar", "schulung", "lehrgang",
                    "teilnahmebestätigung", "teilnahmebestaetigung",
                    "zertifikat", "diplom",
                    "bildungseinrichtung",
                    "studiengebühr", "studiengebuehr",
                    "umschulung",
                ],
                "required_keywords": [],
                "required_any": [
                    "fortbildung", "fortbildungskosten",
                    "weiterbildung", "weiterbildungskosten",
                    "kursbestätigung", "kursbestaetigung",
                    "teilnahmebestätigung", "teilnahmebestaetigung",
                ],
                "weight": 1.1,
            },
            DocumentType.PENDLERPAUSCHALE: {
                "keywords": [
                    "pendlerpauschale",
                    "pendlerrechner",
                    "pendlereuro",
                    "fahrtstrecke", "arbeitsweg",
                    "entfernung", "kilometer",
                    "öffentliches verkehrsmittel", "oeffentliches verkehrsmittel",
                    "zumutbarkeit",
                    "pendlerförderung", "pendlerfoerderung",
                    "arbeitsstätte", "arbeitsstaette",
                ],
                "required_keywords": [],
                "required_any": [
                    "pendlerpauschale", "pendlerrechner", "pendlereuro",
                ],
                "weight": 1.2,
            },
            DocumentType.KIRCHENBEITRAG: {
                "keywords": [
                    "kirchenbeitrag", "kirchensteuer",
                    "kirchenbeitragsbestätigung", "kirchenbeitragsbestaetigung",
                    "diözese", "dioezese",
                    "pfarrgemeinde", "pfarramt",
                    "kirchgeld",
                    "beitragsjahr",
                    "mitgliedsbeitrag",
                    "seelsorge",
                    "religionsgemeinschaft",
                ],
                "required_keywords": [],
                "required_any": [
                    "kirchenbeitrag", "kirchensteuer",
                    "kirchenbeitragsbestätigung", "kirchenbeitragsbestaetigung",
                ],
                "weight": 1.2,
            },
            DocumentType.GRUNDBUCHAUSZUG: {
                "keywords": [
                    "grundbuchauszug", "grundbuch",
                    "einlagezahl", "katastralgemeinde",
                    "bezirksgericht",
                    "eigentumsrecht", "eigentümer", "eigentuemer",
                    "grundstücksnummer", "grundstuecksnummer",
                    "lastenblatt", "eigentumsblatt",
                    "pfandrecht", "hypothek",
                    "dienstbarkeit",
                    "liegenschaft",
                ],
                "required_keywords": [],
                "required_any": [
                    "grundbuchauszug", "grundbuch",
                    "einlagezahl", "katastralgemeinde",
                ],
                "weight": 1.2,
            },
            DocumentType.BETRIEBSKOSTENABRECHNUNG: {
                "keywords": [
                    "betriebskostenabrechnung", "betriebskosten",
                    "hausverwaltung",
                    "abrechnungszeitraum", "abrechnungsperiode",
                    "nachzahlung", "guthaben",
                    "heizkosten", "warmwasser",
                    "müllabfuhr", "muellabfuhr",
                    "kanalgebühr", "kanalgebuehr",
                    "versicherung", "verwaltungshonorar",
                    "aufzug", "lift",
                    "allgemeinbeleuchtung",
                    "rücklage", "ruecklage",
                ],
                "required_keywords": [],
                "required_any": [
                    "betriebskostenabrechnung", "betriebskosten",
                    "hausverwaltung",
                ],
                "weight": 1.1,
            },
            DocumentType.GEWERBESCHEIN: {
                "keywords": [
                    "gewerbeschein", "gewerbeberechtigung",
                    "gewerbeanmeldung",
                    "gewerbeordnung",
                    "bezirkshauptmannschaft", "magistrat",
                    "gewerbetreibende", "gewerbetreibender",
                    "standort", "betriebsstandort",
                    "gewerbe", "handelsgewerbe",
                    "gisa", "gewerbeinformationssystem",
                ],
                "required_keywords": [],
                "required_any": [
                    "gewerbeschein", "gewerbeberechtigung",
                    "gewerbeanmeldung",
                ],
                "weight": 1.3,
            },
            DocumentType.KONTOAUSZUG: {
                "keywords": [
                    "kontoauszug", "kontobewegungen",
                    "buchungsdetails", "buchungstext",
                    "valuta", "wertstellung",
                    "iban", "bic",
                    "saldo", "anfangssaldo", "endsaldo",
                    "haben", "soll",
                    "überweisung", "ueberweisung",
                    "lastschrift", "gutschrift",
                    "kontonummer", "bankleitzahl",
                    "auszugsnummer",
                ],
                "required_keywords": [],
                "required_any": [
                    "kontoauszug", "kontobewegungen",
                    "auszugsnummer", "buchungsdetails",
                ],
                "weight": 1.0,
            },
        }

    def classify(self, image: np.ndarray, text: str) -> Tuple[DocumentType, float]:
        """
        Classify document type based on extracted text

        Args:
            image: Document image (for future ML-based classification)
            text: Extracted text from OCR

        Returns:
            Tuple of (document_type, confidence_score)
        """
        # Method 1: Pattern-based classification
        pattern_result = self._classify_by_patterns(text)

        # Method 2: ML-based classification (placeholder for future enhancement)
        # ml_result = self._classify_by_ml(image, text)

        # For now, use pattern-based classification
        return pattern_result["type"], pattern_result["confidence"]

    def _classify_by_patterns(self, text: str) -> Dict:
        """
        Classify document using keyword pattern matching.

        Matches against both the original text and an umlaut-normalized version
        so that OCR output using ä/ö/ü or ae/oe/ue is handled equally well.

        Args:
            text: Extracted text from OCR

        Returns:
            Dictionary with type and confidence
        """
        text_lower = text.lower()
        # Also create umlaut-normalized version for fallback matching
        text_normalized = _normalize_umlauts(text_lower)

        def _contains(haystack: str, haystack_norm: str, needle: str) -> bool:
            """Check if needle is in haystack OR its umlaut-normalized form."""
            if needle in haystack:
                return True
            # Also try the normalized form of the needle against normalized text
            return _normalize_umlauts(needle) in haystack_norm

        # ================================================================
        # EARLY DETECTION: Multi-candidate scoring with exclusion rules
        # ================================================================
        # Instead of sequential if/else that returns on first match,
        # we score ALL early detection candidates and pick the best.
        # Exclusion rules prevent false positives (e.g., Dienstzettel ≠ Lohnzettel).
        #
        # Architecture: Each detector returns (type, confidence) or None.
        # Exclusion rules can veto a detection.
        # The highest-confidence non-vetoed candidate wins.

        import re as _re

        first_page = text_lower[:2000]
        first_page_norm = text_normalized[:2000]

        # --- Exclusion rules: if ANY of these appear, VETO the candidate ---
        EXCLUSION_RULES = {
            DocumentType.LOHNZETTEL: [
                "dienstzettel", "arbeitsvertrag", "dienstvertrag",
                "arbeitgeberkündigung", "arbeitgeberkuendigung",
                "arbeitszeugnis", "pflichten aus dem arbeitsvertrag",
            ],
            DocumentType.RENTAL_CONTRACT: [
                "übergabeprotokoll", "uebergabeprotokoll", "ubergabeprotokoll",
                "wohnungsübergabe", "wohnungsuebergabe", "wohnungsubergabe",
                "rückgabeprotokoll", "rueckgabeprotokoll", "ruckgabeprotokoll",
                "abnahmeprotokoll", "zustandsbericht",
            ],
        }

        def _is_excluded(doc_type, page, page_norm):
            """Check if any exclusion pattern vetoes this type."""
            excl = EXCLUSION_RULES.get(doc_type, [])
            return any(_contains(page, page_norm, e) for e in excl)

        # --- Priority 0: Detect UNSUPPORTED / non-tax documents FIRST ---
        # These must be checked before anything else to prevent false positives

        # Dienstzettel / Arbeitsvertrag → NOT a payslip
        dienstzettel_markers = ["dienstzettel", "dienstvertrag",
                                "pflichten aus dem arbeitsvertrag",
                                "wesentlichen rechte und pflichten"]
        if any(_contains(first_page, first_page_norm, m) for m in dienstzettel_markers):
            return {"type": DocumentType.UNKNOWN, "confidence": 0.85,
                    "_unsupported_type": "dienstzettel",
                    "_message": "Employment record (Dienstzettel) — not a payslip"}

        # Übergabeprotokoll → NOT a rental contract
        # Include OCR variants where ü→u (not ue) due to poor OCR
        handover_markers = ["übergabeprotokoll", "uebergabeprotokoll", "ubergabeprotokoll",
                            "wohnungsübergabe", "wohnungsuebergabe", "wohnungsubergabe",
                            "rückgabeprotokoll", "rueckgabeprotokoll", "ruckgabeprotokoll"]
        if any(_contains(first_page, first_page_norm, m) for m in handover_markers):
            return {"type": DocumentType.UNKNOWN, "confidence": 0.85,
                    "_unsupported_type": "handover_protocol",
                    "_message": "Handover protocol — not a rental contract"}

        # K1 Körperschaftsteuererklärung → unsupported corporate form
        k1_markers = ["körperschaftsteuer", "koerperschaftsteuer",
                      "k 1-pdf", "k1-pdf", "formular k 1", "formular k1",
                      "k 1-edv", "k1-edv",
                      "körperschaftsteuererklärung", "koerperschaftsteuererklaerung"]
        if any(_contains(first_page, first_page_norm, m) for m in k1_markers):
            return {"type": DocumentType.UNKNOWN, "confidence": 0.85,
                    "_unsupported_type": "k1_form",
                    "_message": "K1 (Körperschaftsteuererklärung) — corporate tax not supported"}

        # --- Priority 1: Payslips (with exclusion check) ---
        payslip_markers = [
            "auszahlungsmonat",
            "personalnummer",
            "summe bezüge", "summe bezuege",
            "summe abzüge", "summe abzuege",
            "gehaltszettel",
            "gehaltsabrechnung",
            "lohnabrechnung",
            "gehalt/entsch",
            "jahreslohnzettel",
        ]
        payslip_hits = sum(
            1 for m in payslip_markers
            if _contains(first_page, first_page_norm, m)
        )
        if payslip_hits >= 2 and not _is_excluded(DocumentType.LOHNZETTEL, first_page, first_page_norm):
            return {"type": DocumentType.LOHNZETTEL, "confidence": 0.92}

        # --- Priority 2: L1 employee tax return ---
        l1_markers = [
            "l 1-pdf", "l1-pdf", "l 1-edv", "l1-edv",
            "formular l 1", "formular l1",
            "erklärung zur arbeitnehmerveranlagung",
            "erklaerung zur arbeitnehmerveranlagung",
        ]
        if any(_contains(first_page, first_page_norm, m) for m in l1_markers):
            l1k_markers = ["l 1k", "l1k", "beilage für kinder", "beilage fuer kinder",
                           "familienbonus plus", "kindermehrbetrag"]
            if any(_contains(first_page, first_page_norm, m) for m in l1k_markers):
                return {"type": DocumentType.L1K_BEILAGE, "confidence": 0.90}
            l1ab_markers = ["l 1ab", "l1ab", "absetzbeträge", "absetzbetraege",
                            "alleinverdienerabsetzbetrag", "alleinerzieherabsetzbetrag",
                            "pendlerpauschale"]
            if any(_contains(first_page, first_page_norm, m) for m in l1ab_markers):
                return {"type": DocumentType.L1AB_BEILAGE, "confidence": 0.90}
            return {"type": DocumentType.L1_FORM, "confidence": 0.90}

        # L1k / L1ab standalone
        l1k_standalone = ["l 1k-pdf", "l1k-pdf", "l 1k,", "l1k,",
                          "beilage für kinder", "beilage fuer kinder"]
        if any(_contains(first_page, first_page_norm, m) for m in l1k_standalone):
            return {"type": DocumentType.L1K_BEILAGE, "confidence": 0.88}
        l1ab_standalone = ["l 1ab-pdf", "l1ab-pdf", "l 1ab,", "l1ab,"]
        if any(_contains(first_page, first_page_norm, m) for m in l1ab_standalone):
            return {"type": DocumentType.L1AB_BEILAGE, "confidence": 0.88}

        # --- Priority 3: E1 sub-forms (BEFORE E1 main) ---
        # Use case-insensitive regex to handle OCR variants: "E1a", "E1A", "Ela", "e 1a"
        e1a_patterns_re = [
            r"e\s*1\s*a[\s\-–]*(?:beilage|pdf|edv)",
            r"beilage\s+(?:zur\s+)?e\s*1\s*a",
            r"formular\s+e\s*1\s*a",
            r"eink[uü]nfte\s+aus\s+selbst[aä]ndiger\s+arbeit",
        ]
        if any(_re.search(p, first_page, _re.IGNORECASE) for p in e1a_patterns_re):
            return {"type": DocumentType.E1A_BEILAGE, "confidence": 0.90}

        e1b_patterns_re = [
            r"e\s*1\s*b[\s\-–]*(?:beilage|pdf|edv)",
            r"beilage\s+(?:zur\s+)?e\s*1\s*b",
            r"formular\s+e\s*1\s*b",
            r"eink[uü]nfte\s+aus\s+vermietung\s+und\s+verpachtung",
        ]
        if any(_re.search(p, first_page, _re.IGNORECASE) for p in e1b_patterns_re):
            return {"type": DocumentType.E1B_BEILAGE, "confidence": 0.90}

        e1kv_patterns_re = [
            r"e\s*1\s*kv[\s\-–]*(?:beilage|pdf|edv)",
            r"formular\s+e\s*1\s*kv",
            r"eink[uü]nfte\s+aus\s+kapitalverm[oö]gen",
        ]
        if any(_re.search(p, first_page, _re.IGNORECASE) for p in e1kv_patterns_re):
            return {"type": DocumentType.E1KV_BEILAGE, "confidence": 0.90}

        # --- Priority 4: U1 / U30 ---
        u1_markers = ["umsatzsteuererklärung", "umsatzsteuererklaerung",
                      "formular u 1", "formular u1", "u 1-pdf", "u1-pdf"]
        if any(_contains(first_page, first_page_norm, m) for m in u1_markers):
            return {"type": DocumentType.U1_FORM, "confidence": 0.90}

        u30_markers = ["umsatzsteuervoranmeldung", "u 30-pdf", "u30-pdf",
                       "formular u 30", "formular u30"]
        if any(_contains(first_page, first_page_norm, m) for m in u30_markers):
            return {"type": DocumentType.U30_FORM, "confidence": 0.90}

        # --- Priority 5: E1 main form (AFTER all sub-forms checked) ---
        e1_markers = [
            "e 1-pdf", "e 1-edv", "e1-pdf",
            "e 1, seite",
            "einkommensteuererklärung für",
            "einkommensteuererklaerung fuer",
            "einkommensteuererklaerung fur",
            "formular e 1", "formular e1",
        ]
        # Also check with regex for OCR variants
        e1_re = [
            r"e\s*1[\s,\-–]+(?:seite|pdf|edv)",
            r"einkommensteuererkl[aä]rung\s+f[uü]r",
            r"bundesministerium\s+f[uü]r\s+finanzen",
        ]
        if (any(_contains(first_page, first_page_norm, m) for m in e1_markers) or
                any(_re.search(p, first_page, _re.IGNORECASE) for p in e1_re)):
            return {"type": DocumentType.E1_FORM, "confidence": 0.90}

        # --- Priority 6: Arbeitnehmerveranlagung fallback ---
        anv_markers = ["arbeitnehmerinnenveranlagung", "arbeitnehmerveranlagung"]
        if any(_contains(first_page, first_page_norm, m) for m in anv_markers):
            return {"type": DocumentType.L1_FORM, "confidence": 0.85}

        # ================================================================
        # KEYWORD SCORING (for types not caught by early detection)
        # ================================================================

        scores = {}

        for doc_type, pattern_info in self.patterns.items():
            score = 0.0
            keyword_matches = 0

            # Check required keywords first (ALL must match)
            required_keywords = pattern_info.get("required_keywords", [])
            if required_keywords:
                required_found = all(
                    _contains(text_lower, text_normalized, keyword)
                    for keyword in required_keywords
                )
                if not required_found:
                    scores[doc_type] = 0.0
                    continue

            # Check required_any keywords (at least ONE must match)
            required_any = pattern_info.get("required_any", [])
            if required_any:
                any_found = any(
                    _contains(text_lower, text_normalized, keyword)
                    for keyword in required_any
                )
                if not any_found:
                    scores[doc_type] = 0.0
                    continue

            # Count keyword matches
            for keyword in pattern_info["keywords"]:
                if _contains(text_lower, text_normalized, keyword):
                    keyword_matches += 1

            # Calculate score
            if keyword_matches > 0:
                match_ratio = keyword_matches / len(pattern_info["keywords"])
                score = match_ratio * pattern_info["weight"]

                # Boost score if required keywords are present
                if required_keywords and all(
                    _contains(text_lower, text_normalized, keyword)
                    for keyword in required_keywords
                ):
                    score *= 1.2

                # Boost score for required_any matches
                if required_any:
                    any_count = sum(
                        1 for k in required_any
                        if _contains(text_lower, text_normalized, k)
                    )
                    score *= (1.0 + 0.1 * any_count)

            scores[doc_type] = min(score, 1.0)

        # --- INVOICE vs RECEIPT disambiguation ---
        # If both scored, use stronger signals to decide
        if DocumentType.RECEIPT in scores and DocumentType.INVOICE in scores:
            invoice_strong = ["rechnungsnummer", "re-nr", "uid", "ust-id",
                              "firmenbuchnummer", "reverse charge", "faktura"]
            receipt_strong = ["kassenbon", "quittung", "kassa", "bar bezahlt",
                              "wechselgeld"]
            inv_hits = sum(1 for m in invoice_strong if _contains(text_lower, text_normalized, m))
            rec_hits = sum(1 for m in receipt_strong if _contains(text_lower, text_normalized, m))
            if inv_hits > rec_hits:
                scores[DocumentType.RECEIPT] *= 0.5  # Penalize RECEIPT
            elif rec_hits > inv_hits:
                scores[DocumentType.INVOICE] *= 0.5  # Penalize INVOICE

        # Find best match
        if not scores or max(scores.values()) == 0:
            return {"type": DocumentType.UNKNOWN, "confidence": 0.3}

        best_type = max(scores, key=scores.get)
        confidence = scores[best_type]

        return {"type": best_type, "confidence": confidence}

    def classify_austrian_merchant(self, text: str) -> Optional[str]:
        """
        Identify Austrian merchant from text

        Args:
            text: Extracted text

        Returns:
            Merchant name if found, None otherwise
        """
        text_lower = text.lower()

        # Common Austrian merchants
        merchants = {
            "billa": "BILLA AG",
            "spar": "SPAR ?sterreich",
            "hofer": "HOFER KG",
            "lidl": "Lidl ?sterreich",
            "merkur": "MERKUR",
            "penny": "PENNY",
            "obi": "OBI Bau- und Heimwerkerm?rkte",
            "baumax": "bauMax",
            "hornbach": "HORNBACH",
            "dm": "dm drogerie markt",
            "m?ller": "M?ller Drogerie",
            "interspar": "INTERSPAR",
        }

        for key, official_name in merchants.items():
            if key in text_lower:
                return official_name

        return None

    def get_document_characteristics(self, text: str) -> Dict:
        """
        Extract document characteristics for classification

        Args:
            text: Extracted text

        Returns:
            Dictionary of characteristics
        """
        text_lower = text.lower()

        characteristics = {
            "has_date": bool(re.search(r"\d{2}\.\d{2}\.\d{4}", text)),
            "has_amount": bool(re.search(r"?\s*\d+[,\.]\d{2}", text)),
            "has_vat": "ust" in text_lower or "mwst" in text_lower,
            "has_iban": bool(re.search(r"AT\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}", text)),
            "has_tax_number": "steuernummer" in text_lower or "stnr" in text_lower,
            "has_merchant": self.classify_austrian_merchant(text) is not None,
            "language": self._detect_language(text),
            "line_count": len(text.split("\n")),
            "word_count": len(text.split()),
        }

        return characteristics

    def _detect_language(self, text: str) -> str:
        """
        Detect primary language of text

        Args:
            text: Input text

        Returns:
            Language code ('de' or 'en')
        """
        text_lower = text.lower()

        # German indicators
        german_words = ["und", "der", "die", "das", "mit", "f?r", "von", "zu", "auf"]
        german_count = sum(1 for word in german_words if word in text_lower)

        # English indicators
        english_words = ["and", "the", "with", "for", "from", "to", "on", "at"]
        english_count = sum(1 for word in english_words if word in text_lower)

        return "de" if german_count > english_count else "en"

    def detect_asset_type(self, text: str) -> Optional[str]:
        """
        Detect if a Kaufvertrag is for a vehicle, equipment, or real estate.

        Returns asset_type string (e.g. 'vehicle', 'computer') or None for real estate.
        """
        text_lower = text.lower()
        text_norm = _normalize_umlauts(text_lower)

        vehicle_keywords = [
            "fahrgestellnummer", "fahrzeug", "kfz", "pkw", "lkw",
            "zulassung", "erstzulassung", "typenschein", "kilometerstand",
            "motorleistung", "hubraum", "kennzeichen", "auto",
            "kraftfahrzeug", "personenkraftwagen",
        ]
        ev_keywords = ["elektro", "e-auto", "elektrofahrzeug", "batterie", "kwh", "ladekabel"]
        computer_keywords = [
            "laptop", "notebook", "computer", "pc", "macbook", "imac",
            "tablet", "ipad", "server", "workstation",
        ]
        phone_keywords = ["smartphone", "iphone", "handy", "mobiltelefon", "samsung galaxy"]
        furniture_keywords = ["schreibtisch", "bürostuhl", "buerostuhl", "büromöbel", "bueromoebel", "regal"]
        machinery_keywords = ["maschine", "anlage", "cnc", "fräse", "fraese", "drehbank", "presse"]
        software_keywords = [
            "software",
            "lizenz",
            "dauerlizenz",
            "perpetual",
            "einmallizenz",
            "einmal-lizenz",
        ]
        tools_keywords = ["werkzeug", "bohrmaschine", "säge", "saege", "schrauber"]

        def _hits(keywords):
            return sum(1 for kw in keywords if kw in text_lower or _normalize_umlauts(kw) in text_norm)

        scores = {
            "vehicle": _hits(vehicle_keywords),
            "electric_vehicle": _hits(ev_keywords),
            "computer": _hits(computer_keywords),
            "phone": _hits(phone_keywords),
            "office_furniture": _hits(furniture_keywords),
            "machinery": _hits(machinery_keywords),
            "software": _hits(software_keywords),
            "tools": _hits(tools_keywords),
        }

        # EV is a sub-type of vehicle — combine
        if scores["electric_vehicle"] >= 2:
            return "electric_vehicle"
        if scores["vehicle"] >= 2:
            return "vehicle"

        # Find best non-vehicle match
        best = max(scores, key=scores.get)
        if scores[best] >= 2 and best not in ("vehicle", "electric_vehicle"):
            return best

        return None  # real estate or unknown

    def suggest_document_type(self, characteristics: Dict) -> DocumentType:
        """
        Suggest document type based on characteristics

        Args:
            characteristics: Document characteristics

        Returns:
            Suggested document type
        """
        # Receipt indicators
        if characteristics["has_merchant"] and characteristics["has_amount"]:
            return DocumentType.RECEIPT

        # Invoice indicators
        if characteristics["has_vat"] and characteristics["has_amount"]:
            return DocumentType.INVOICE

        # Bank statement indicators
        if characteristics["has_iban"]:
            return DocumentType.BANK_STATEMENT

        # Payslip indicators
        if characteristics["has_tax_number"] and characteristics["has_amount"]:
            return DocumentType.PAYSLIP

        return DocumentType.UNKNOWN







