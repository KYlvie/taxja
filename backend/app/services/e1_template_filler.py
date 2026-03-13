"""
Official BMF E1 Template Filler

Fills an official BMF E1 PDF template with user data.

Two modes:
1. AcroForm mode: If the template has fillable form fields, fill them by field name
2. Overlay mode: If the template is a flat PDF, overlay text at known KZ positions

The official E1 form can be downloaded from:
  https://service.bmf.gv.at/service/anwend/formulare/show_mast.asp?Ession=E1

Place the downloaded PDF as:
  backend/app/templates/E1_2024.pdf  (or E1_<year>.pdf)

Field name → KZ mapping is based on calibration of the official 2024/2025 E1 form.
"""
import io
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

# Directory for PDF templates
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _sanitize_latin1(text: str) -> str:
    """Replace non-Latin-1 characters with ASCII equivalents.

    PyMuPDF Base14 fonts (helv, hebo, cour) only support Latin-1 encoding.
    Characters outside Latin-1 cause garbled output.
    """
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "*",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u20ac": "EUR",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    result = []
    for ch in text:
        try:
            ch.encode("latin-1")
            result.append(ch)
        except UnicodeEncodeError:
            result.append("?")
    return "".join(result)

# ── AcroForm field name → KZ number mapping ─────────────────────────
# Discovered via calibrate_template() on E1_2024.pdf (Version 2025)
# The BMF PDF uses field names like "Zahl86a", "Zahl75", "Text06" etc.
# This maps each field name to the KZ number it represents.
#
# Page 0: Personal info fields
# Page 2: Betriebliche Einkünfte (Punkt 9-11)
# Page 3: Anzurechnende Steuer + Wartetastenregelungen
# Page 4: Werbungskosten (Punkt 15)
# Page 5: Einkünfte aus Vermietung (Punkt 17) + Grundstücksveräußerungen (Punkt 18)
# Page 6: Sonstige Einkünfte (Punkt 19-22)
# Page 7: Ausländische Einkünfte (Punkt 23) + Sonderausgaben (Punkt 24)
# Page 8: Freibetragsbescheid (Punkt 27)

FIELD_TO_KZ: Dict[str, str] = {
    # ── Page 2: Betriebliche Einkünfte (Punkt 9-11) ──
    # Columns: Land-/Forstwirtschaft | Selbständige Arbeit | Gewerbebetrieb
    "Zahl50": "311",       # Einzelunternehmer - L&F
    "Zahl62": "321",       # Einzelunternehmer - Selbständig
    "Zahl76": "327",       # Einzelunternehmer - Gewerbe
    "Zahl54": "312",       # Beteiligter - L&F
    "Zahl66": "322",       # Beteiligter - Selbständig
    "Zahl80": "328",       # Beteiligter - Gewerbe
    "Zahl58a": "311",      # Davon auszuscheiden 3 Jahre - L&F
    "Zahl70a": "321",      # Davon auszuscheiden 3 Jahre - Selbständig
    "Zahl84a": "327",      # Davon auszuscheiden 3 Jahre - Gewerbe
    "Zahl58b": "312",      # Davon auszuscheiden 5 Jahre - L&F
    "Zahl70b": "322",      # Davon auszuscheiden 5 Jahre - Selbständig
    "Zahl84b": "328",      # Davon auszuscheiden 5 Jahre - Gewerbe
    "Zahl73": "325",       # Einkünfteverteilung § 37 Abs. 9
    "Zahl314KZ": "314",    # Teilbeträge Einkünfteverteilung - L&F
    "Zahl324KZ": "324",    # Teilbeträge Einkünfteverteilung - Selbständig
    "Zahl326KZ": "326",    # Teilbeträge Einkünfteverteilung - Gewerbe
    "Zahl314KZ_b1": "314", # Umwidmungszuschlag - L&F
    "Zahl324KZ_b1": "324", # Umwidmungszuschlag - Selbständig
    "Zahl326KZ_b1": "326", # Umwidmungszuschlag - Gewerbe
    "Zahl60": "780",       # Regelbesteuerung Kapitalerträge - L&F
    "Zahl74": "782",       # Regelbesteuerung Kapitalerträge - Selbständig
    "Zahl86": "784",       # Regelbesteuerung Kapitalerträge - Gewerbe
    "Zahl60a": "917",      # Regelbesteuerung Kapitalerträge (ausl. QSt) - L&F
    "Zahl74a": "918",      # Regelbesteuerung Kapitalerträge (ausl. QSt) - Selbständig
    "Zahl86_01": "919",    # Regelbesteuerung Kapitalerträge (ausl. QSt) - Gewerbe
    "Zahl60a_2": "500",    # Substanzgewinne Betriebsgrundstücke - L&F
    "Zahl74a_2": "501",    # Substanzgewinne Betriebsgrundstücke - Selbständig
    "Zahl86_01_2": "502",  # Substanzgewinne Betriebsgrundstücke - Gewerbe
    "Zahl60aa": "310_umw", # Umwidmungszuschlag in 500/501/502 (skip)
    "Zahl74aa": "320_umw",
    "Zahl86_01a": "330_umw",
    "Zahl61": "310",       # Summe 1-9 - L&F
    "Zahl75": "320",       # Summe 1-9 - Selbständig
    "Zahl86a": "330",      # Summe 1-9 - Gewerbe
    "Zahl151KZ": "151",    # Einkünfteverteilung L&F § 37 Abs. 4

    # ── Page 2 continued: Anzurechnende Steuer auf betriebliche Kapitalerträge ──
    "Zahl946KZ": "946",    # KESt 27,5% - L&F
    "Zahl947KZ": "947",    # KESt 27,5% - Selbständig
    "Zahl948KZ": "948",    # KESt 27,5% - Gewerbe
    "Zahl781KZ": "781",    # KESt 25% - L&F
    "Zahl783KZ": "783",    # KESt 25% - Selbständig
    "Zahl785KZ": "785",    # KESt 25% - Gewerbe
    "Zahl949KZ": "949",    # Ausl. QSt 27,5% - L&F
    "Zahl950KZ": "950",    # Ausl. QSt 27,5% - Selbständig
    "Zahl951KZ": "951",    # Ausl. QSt 27,5% - Gewerbe

    # ── Page 3: Anzurechnende Steuer (Fortsetzung) ──
    "Zahl920KZ": "920",    # Ausl. QSt 25% - L&F
    "Zahl921KZ": "921",    # Ausl. QSt 25% - Selbständig
    "Zahl922KZ": "922",    # Ausl. QSt 25% - Gewerbe
    "Zahl551KZ": "961",    # ImmoESt 30% betrieblich - L&F (NOTE: field name != KZ)
    "Zahl552KZ": "962",    # ImmoESt 30% betrieblich - Selbständig
    "Zahl553KZ": "963",    # ImmoESt 30% betrieblich - Gewerbe
    "Zahl551KZ_b1": "551", # ImmoESt 25% betrieblich - L&F
    "Zahl552KZ_b1": "552", # ImmoESt 25% betrieblich - Selbständig
    "Zahl553KZ_b1": "553", # ImmoESt 25% betrieblich - Gewerbe
    "Zahl961KZ": "551",    # (alternate mapping)
    "Zahl962KZ": "552",
    "Zahl963KZ": "553",
    "Zahl955KZ": "955",    # Bes. Vorauszahlung 30% - L&F
    "Zahl956KZ": "956",    # Bes. Vorauszahlung 30% - Selbständig
    "Zahl957KZ": "957",    # Bes. Vorauszahlung 30% - Gewerbe
    "Zahl580KZ": "580",    # Bes. Vorauszahlung 25% - L&F
    "Zahl581KZ": "581",    # Bes. Vorauszahlung 25% - Selbständig
    "Zahl582KZ": "582",    # Bes. Vorauszahlung 25% - Gewerbe
    "Zahl958KZ": "958",    # Ausl. Steuer Grundstücke 30% - L&F
    "Zahl959KZ": "959",    # Ausl. Steuer Grundstücke 30% - Selbständig
    "Zahl960KZ": "960",    # Ausl. Steuer Grundstücke 30% - Gewerbe
    "Zahl923KZ": "923",    # Ausl. Steuer Grundstücke 25% - L&F
    "Zahl924KZ": "924",    # Ausl. Steuer Grundstücke 25% - Selbständig
    "Zahl925KZ": "925",    # Ausl. Steuer Grundstücke 25% - Gewerbe
    "Zahl964KZ": "964",    # ImmoESt 30% Grundstücksveräußerung - L&F
    "Zahl965KZ": "965",    # ImmoESt 30% Grundstücksveräußerung - Selbständig
    "Zahl966KZ": "966",    # ImmoESt 30% Grundstücksveräußerung - Gewerbe
    "Zahl683KZ": "583",    # ImmoESt 25% Grundstücksveräußerung - L&F (field name != KZ!)
    "Zahl584KZ": "584",    # ImmoESt 25% Grundstücksveräußerung - Selbständig
    "Zahl585KZ": "585",    # ImmoESt 25% Grundstücksveräußerung - Gewerbe
    "Zahl967KZ": "967",    # Bes. Vorauszahlung 30% Grundstücke - L&F
    "Zahl968KZ": "968",    # Bes. Vorauszahlung 30% Grundstücke - Selbständig
    "Zahl969KZ": "969",    # Bes. Vorauszahlung 30% Grundstücke - Gewerbe
    "Zahl589KZ": "589",    # Bes. Vorauszahlung 25% Grundstücke - L&F
    "Zahl590KZ": "590",    # Bes. Vorauszahlung 25% Grundstücke - Selbständig
    "Zahl591KZ": "591",    # Bes. Vorauszahlung 25% Grundstücke - Gewerbe
    "Zahl970KZ": "970",    # Ausl. Steuer 30% Grundstücke - L&F
    "Zahl971KZ": "971",    # Ausl. Steuer 30% Grundstücke - Selbständig
    "Zahl972KZ": "972",    # Ausl. Steuer 30% Grundstücke - Gewerbe
    "Zahl586KZ": "586",    # Ausl. Steuer 25% Grundstücke - L&F
    "Zahl587KZ": "587",    # Ausl. Steuer 25% Grundstücke - Selbständig
    "Zahl588KZ": "588",    # Ausl. Steuer 25% Grundstücke - Gewerbe
    "Zahl286KZ": "286",    # Abzugsteuer § 107 - L&F
    "Zahl287KZ": "287",    # Abzugsteuer § 107 - Selbständig
    "Zahl288KZ": "288",    # Abzugsteuer § 107 - Gewerbe
    "Zahl491KZ": "491",    # In KZ 330 enthaltene beitragsbegründende Einkünfte
    "Zahl492KZ": "492",    # In KZ 330 enthaltene beitragserhöhende Einkünfte

    # ── Page 3 continued: Wartetastenregelungen (Punkt 12-13) ──
    "Zahl98": "341",       # Nicht ausgleichsfähige Verluste § 2 Abs. 2a - eigener Betrieb
    "Zahl100": "342",      # Nicht ausgleichsfähige Verluste - Beteiligungen
    "Zahl101": "332",      # Verrechenbare Verluste Vorjahre - eigener Betrieb
    "Zahl102": "346",      # Verrechenbare Verluste Vorjahre - Beteiligungen
    "Zahl102_00": "509",   # Ausgleichsfähiger Verlust § 23a
    "Zahl102_01": "371",   # Nicht ausgleichsfähige Verluste außerbetrieblich
    "Zahl102_02": "372",   # Verrechenbare Verluste außerbetrieblich

    # ── Page 4: Sonderausgaben + Werbungskosten (Punkt 14-15) ──
    "Zahl25": "245",       # Anzahl Kinder (Punkt 4.2) - actually on page 4 header
    "Zahl104_00": "725",   # Topfsonderausgaben
    "Zahl104_01": "718",   # Personenversicherungen, Wohnraumschaffung
    "Zahl104_01a": "916",  # Nachkauf Versicherungszeiten
    "Zahl104_02": "717",   # Gewerkschaftsbeiträge / Berufsverbände
    "Zahl104_02a": "158",  # Telearbeit Mobiliar
    "Zahl104_03": "274",   # Pflichtbeiträge geringfügige Beschäftigung
    "Text104_00b": "_beruf", # Genaue Bezeichnung berufliche Tätigkeit
    "Zahl104_04": "169",   # Digitale Arbeitsmittel
    "Zahl104_04a": "719",  # Andere Arbeitsmittel
    "Zahl104_05": "720",   # Fachliteratur
    "Zahl104_06": "721",   # Beruflich veranlasste Reisekosten
    "Zahl104_07": "722",   # Fortbildungs-/Ausbildungskosten
    "Zahl104_08": "300",   # Familienheimfahrten
    "Zahl104_09": "723",   # Doppelte Haushaltsführung
    "Zahl104_09a": "159",  # Arbeitszimmer
    "Zahl104_10": "724",   # Sonstige Werbungskosten

    # ── Page 5: Einkünfte aus Vermietung (Punkt 17) + Grundstücksveräußerungen ──
    "Zahl108": "370_sum",  # Summe 17.1-17.5 (auto-calculated in some versions)
    "Zahl123": "546",      # Veräußerung Miet-/Pachtzinsforderungen
    "Zahl127": "547",      # Leitungsrechte / Hochwasserschutz
    "Zahl127_01": "546",   # (alternate)
    "Zahl127_02": "547",   # (alternate)
    "Zahl130_01": "373",   # Sonstige Einkünfte V&V
    "Zahl131": "370",      # Summe Einkünfte V&V
    "Zahl973KZ": "973",    # Fünfzehntelbetrag Verlust Grundstücksveräußerung
    "Zahl974KZ": "974",    # 60% Verlustausgleich V&V
    "Zahl985KZ": "985",    # Pauschal Grundstücksveräußerung 14% - 30%
    "Zahl572KZ": "572",    # Pauschal Grundstücksveräußerung 14% - 25%
    "Zahl986KZ": "986",    # Grundstücksveräußerung Umwidmung 60% - 30%
    "Zahl573KZ": "573",    # Grundstücksveräußerung Umwidmung 60% - 25%
    "Zahl986KZ_b2": "986_umw",  # Umwidmungszuschlag in KZ 986
    "Zahl987KZ": "987",    # Nicht pauschal ermittelte Grundstücksveräußerung - 30%
    "Zahl574KZ": "574",    # Nicht pauschal ermittelte Grundstücksveräußerung - 25%
    "Zahl987KZ_b2": "987_umw",  # Umwidmungszuschlag in KZ 987
    "Zahl787KZSumme": "787_sum", # Saldo 985/986/987 - 30%
    "Zahl574KZSumme": "574_sum", # Saldo 572/573/574 - 25%

    # ── Page 6: Grundstücksveräußerungen (Forts.) + Sonstige Einkünfte (Punkt 19-22) ──
    "Zahl988KZ": "988",    # Anrechenbare ImmoESt privat - 30%
    "Zahl576KZ": "576",    # Anrechenbare ImmoESt privat - 25%
    "Zahl989KZ": "989",    # Bes. Vorauszahlung privat - 30%
    "Zahl579KZ": "579",    # Bes. Vorauszahlung privat - 25%
    "Zahl997KZ": "997",    # Ausl. Steuer privat - 30%
    "Zahl578KZ": "578",    # Ausl. Steuer privat - 25%
    "Zahl575KZ": "575",    # Grundstücksveräußerung gegen Rente
    "Zahl575KZ_b2": "575_umw",  # Umwidmungszuschlag in KZ 575
    "Zahl975KZ": "975",    # Ausl. Steuer Grundstücke Tarif
    "Zahl132a": "800",     # Wiederkehrende Bezüge § 29 Z 1
    "Zahl132a01": "801",   # Spekulationsgeschäfte § 31
    "Zahl132a01_503": "503", # Forderungswertpapiere/Derivate 27,5%
    "Zahl132a02": "803",   # Nicht betriebliche Leistungen § 29 Z 3
    "Zahl132a03": "804",   # Funktionsgebühren § 29 Z 4
    "Zahl134b": "792",     # Nachversteuerung ausl. Verluste
    "Zah140_21_4": "423_gesamtbetrag",  # Gesamtbetrag der Einkünfte (Punkt 21)
    "Zahl89a_001": "423",  # Hälftesteuersatz Einkünfte
    "Zahl89a_001x1": "167", # Waldnutzungen Hälftesteuersatz
    "Zahl144": "496",      # Quote Schuldnachlass %
    "Zahl89a_001a": "386", # Schuldnachlass § 36
    "Zahl89a_002": "978_text",  # (text field for Art)
    "Zahl89a_004": "978",  # Ratenzahlung § 6 Z 6
    "Zahl89a_006": "235",  # Anlagevermögen 5 Raten
    "Zahl89a_006x1": "991", # Umlaufvermögen 2 Raten
    "Zahl89a_009": "979",  # Ratenzahlung UmgrStG
    "Zahl89a_011": "559",  # Anlagevermögen UmgrStG 5 Raten
    "Zahl89a_011x1": "993", # Umlaufvermögen UmgrStG 2 Raten

    # ── Page 7: Tarifbegünstigungen (Forts.) + Ausländische Einkünfte + Sonderausgaben ──
    "Zahl89a_013a": "153", # Anteilstausch UmgrStG
    "Zahl89a_013": "806",  # Nichtfestsetzung § 27 Abs. 6
    "Zahl89a_014": "980",  # Ratenzahlung § 27 Abs. 6
    "Zahl89a_014a": "596", # Abzugsteuer Leitungsrechte
    "Zahl89a_015": "309",  # Abzugsteuer § 99
    "Zahl89a_016": "983",  # Steuerabzug § 107
    "Zahl89a_017": "375",  # Progressionsvorbehalt Auslandseinkünfte
    "Zahl151_01": "395",   # Ausländische Einkünfte mit Besteuerungsrecht
    "Zahl151_02": "396",   # Anrechenbare ausländische Steuer
    "Zahl151_03": "440",   # Steuerbefreite Auslandseinkünfte Progressionsvorbehalt
    "Zahl151_04": "746",   # Ausländische Verluste (Amtshilfe)
    "Zahl151_05": "944",   # Ausländische Verluste (keine Amtshilfe)
    "Zahl160": "462",      # Verlustabzug (Sonderausgaben Punkt 24)

    # ── Page 8: Freibetragsbescheid ──
    "Zahl181": "449",      # Freibetragsbescheid Höhe
}

# ── Reverse mapping: KZ number → field name(s) ──────────────────────
# Built from FIELD_TO_KZ. For KZ numbers that map to multiple fields,
# we prefer the "main" field (e.g. Summe fields for totals).
KZ_TO_FIELD: Dict[str, str] = {}
# Priority: fields without suffixes like _b1, _b2, _umw, _sum
for field_name, kz in FIELD_TO_KZ.items():
    if "_umw" in kz or "_sum" in kz or "_text" in kz or kz.endswith("_gesamtbetrag"):
        continue
    if kz not in KZ_TO_FIELD:
        KZ_TO_FIELD[kz] = field_name

# ── Personal info field mapping ──────────────────────────────────────
# Page 0 fields for personal data
PERSONAL_FIELDS = {
    # Steuernummer: split into 3 parts (FA-Nr / Steuernummer part 1 / part 2)
    "_stnr_fa": "Zahl03",        # Finanzamt-Nummer (2-3 digits)
    "_stnr_p1": "Zahl02_1",      # Steuernummer part 1
    "_stnr_p2": "Zahl02_2",      # Steuernummer part 2
    "_name": "Zahl07_01",        # Familienname
    "_geburtsdatum": "Zahl07_03", # Geburtsdatum
    "_strasse": "Text17",        # Straße (Punkt 2.1)
    "_hausnr": "Text17_01",      # Hausnummer
    "_stiege": "Text17_02",      # Stiege
    "_tuernr": "Text17_03",      # Türnummer
    "_land": "Text17_05",        # Land
    "_ort": "Text17_07",         # Ort
    "_plz": "Text17_06_plz",     # Postleitzahl
    "_telefon": "Text17_04",     # Telefonnummer
    # Partner fields (Page 1)
    "_partner_name": "Text20",   # Partner Familienname
    "_partner_vorname": "Text20a", # Partner Vorname
    "_partner_titel": "Text20b", # Partner Titel
}


def _fmt_eur(value) -> str:
    """Format number as Austrian EUR: 1.234,56"""
    if value is None:
        return ""
    try:
        v = float(value)
        if v == 0:
            return ""
        sign = "" if v >= 0 else "-"
        v = abs(v)
        parts = f"{v:,.2f}".split(".")
        integer_part = parts[0].replace(",", ".")
        decimal_part = parts[1]
        return f"{sign}{integer_part},{decimal_part}"
    except (ValueError, TypeError):
        return str(value)


# KZ numbers that represent counts (not EUR amounts)
# These should be formatted as plain integers, not as currency
COUNT_KZ = {"245", "220", "40", "144"}


def _fmt_value(kz: str, value) -> str:
    """Format a value for a KZ field. Uses integer format for count fields."""
    if kz in COUNT_KZ:
        try:
            return str(int(float(value)))
        except (ValueError, TypeError):
            return str(value)
    return _fmt_eur(value)


def find_template(form_type: str, tax_year: int) -> Optional[Path]:
    """Find the official PDF template for the given form type and year."""
    if not TEMPLATE_DIR.exists():
        return None

    # Try exact year match first, then fall back to closest available
    candidates = [
        TEMPLATE_DIR / f"{form_type}_{tax_year}.pdf",
        TEMPLATE_DIR / f"{form_type.lower()}_{tax_year}.pdf",
        TEMPLATE_DIR / f"{form_type}.pdf",
        TEMPLATE_DIR / f"{form_type.lower()}.pdf",
    ]

    for path in candidates:
        if path.exists():
            return path

    # Try to find the closest year template
    import glob
    pattern = str(TEMPLATE_DIR / f"{form_type}_*.pdf")
    matches = glob.glob(pattern) + glob.glob(pattern.replace(form_type, form_type.lower()))
    if matches:
        # Sort by year descending, pick the most recent
        matches.sort(reverse=True)
        return Path(matches[0])

    return None



def fill_template_acroform(template_path: Path, form_data: Dict[str, Any]) -> Optional[bytes]:
    """
    Fill an official E1 PDF template that has AcroForm fields.

    Uses the calibrated FIELD_TO_KZ mapping to match form field names
    to KZ numbers from form_data.
    Returns None if the template has no fillable fields.
    """
    doc = fitz.open(str(template_path))

    # First pass: check if there are any form fields at all
    has_fields = False
    total_fields = 0
    for page in doc:
        for _ in page.widgets():
            has_fields = True
            total_fields += 1

    if not has_fields:
        doc.close()
        return None

    logger.info(f"Template has {total_fields} form fields")

    # Build KZ -> formatted value mapping from form_data
    kz_values: Dict[str, str] = {}
    for field in form_data.get("fields", []):
        kz = field.get("kz", "")
        value = field.get("value", 0)
        if kz and value:
            kz_values[kz] = _fmt_value(kz, value)

    # Personal info
    tax_number = form_data.get("tax_number", "")
    user_name = form_data.get("user_name", "")
    stnr_parts = _split_tax_number(tax_number) if tax_number else ("", "", "")

    # Build a lookup: field_name -> value to set
    values_to_set: Dict[str, str] = {}

    # Map KZ fields
    for field_name, kz in FIELD_TO_KZ.items():
        val = kz_values.get(kz)
        if val:
            values_to_set[field_name] = val

    # Map personal info fields
    if user_name:
        values_to_set["Zahl07_01"] = user_name
    if tax_number:
        values_to_set["Zahl03"] = stnr_parts[0]
        values_to_set["Zahl02_1"] = stnr_parts[1]
        values_to_set["Zahl02_2"] = stnr_parts[2]
        values_to_set["SteuernummerInfo"] = tax_number

    # ── Fix: Set NeedAppearances flag ──
    # BMF PDFs have JavaScript-driven appearance streams that many viewers
    # (browsers, Preview, etc.) do not execute, causing filled fields to
    # appear blank. Setting NeedAppearances tells the viewer to rebuild them.
    import re as _re
    try:
        acroform_xref = 0
        for i in range(1, min(doc.xref_length(), 50)):
            obj_str = doc.xref_object(i)
            if "/AcroForm" in obj_str and "/Type /Catalog" in obj_str:
                m = _re.search(r"/AcroForm\s+(\d+)\s+0\s+R", obj_str)
                if m:
                    acroform_xref = int(m.group(1))
                break

        if acroform_xref:
            af_obj = doc.xref_object(acroform_xref)
            if "/NeedAppearances" not in af_obj:
                new_af = af_obj.rstrip().rstrip(">")
                new_af += "\n  /NeedAppearances true\n>>"
                doc.update_object(acroform_xref, new_af)
                logger.info("Set NeedAppearances=true on AcroForm")
    except Exception as e:
        logger.warning(f"Could not set NeedAppearances: {e}")

    # ── Pass 1: Remove stale appearance streams from fields we will fill ──
    # BMF fields have pre-built /AP entries showing empty boxes. If we don't
    # remove them, PDF viewers display the old (empty) appearance instead of
    # the new value, even after widget.update().
    for page in doc:
        for widget in page.widgets():
            fn = widget.field_name or ""
            if fn in values_to_set:
                try:
                    xref = widget.xref
                    if xref:
                        obj_str = doc.xref_object(xref)
                        if "/AP" in obj_str:
                            cleaned = _re.sub(r"/AP\s*<<[^>]*>>", "", obj_str)
                            doc.update_object(xref, cleaned)
                except Exception:
                    pass  # Non-critical; widget.update() will still try

    # ── Pass 2: Fill widgets and generate fresh appearance streams ──
    filled = 0
    for page in doc:
        for widget in page.widgets():
            fn = widget.field_name or ""
            if fn in values_to_set:
                try:
                    widget.field_value = values_to_set[fn]
                    widget.update()
                    filled += 1
                except Exception as e:
                    logger.warning(f"Failed to fill field '{fn}': {e}")

    logger.info(f"Filled {filled} form field instances")

    buf = io.BytesIO()
    doc.save(buf, garbage=3, deflate=True)
    doc.close()
    return buf.getvalue()




def _split_tax_number(tax_number: str) -> Tuple[str, str, str]:
    """Split Austrian tax number into (FA-Nr, Part1, Part2).

    Formats: "12-345/6789", "12 345/6789", "123456789"
    Returns 3 parts for the 3 Steuernummer fields on the E1 form.
    """
    import re
    # Remove common separators
    clean = tax_number.replace("-", "").replace("/", "").replace(" ", "")

    if len(clean) >= 9:
        return (clean[:2], clean[2:5], clean[5:])
    elif len(clean) >= 6:
        return (clean[:2], clean[2:5], clean[5:])
    else:
        return (tax_number, "", "")


def _fill_hybrid(template_path: Path, form_data: Dict[str, Any]) -> Optional[bytes]:
    """
    Hybrid fill: set AcroForm field values AND draw overlay text on widget rects.

    This reads the actual widget rectangles from the PDF, fills the AcroForm
    values (for data integrity), then draws visible text directly on the page
    at each widget's position (for universal viewer compatibility).
    """
    import re as _re

    doc = fitz.open(str(template_path))

    # Check for form fields
    has_fields = False
    for page in doc:
        for _ in page.widgets():
            has_fields = True
            break
        if has_fields:
            break

    if not has_fields:
        doc.close()
        return None

    # Build KZ -> formatted value mapping
    kz_values: Dict[str, str] = {}
    for field in form_data.get("fields", []):
        kz = field.get("kz", "")
        value = field.get("value", 0)
        if kz and value:
            kz_values[kz] = _fmt_value(kz, value)

    # Personal info
    tax_number = form_data.get("tax_number", "")
    user_name = form_data.get("user_name", "")
    stnr_parts = _split_tax_number(tax_number) if tax_number else ("", "", "")

    # Build field_name -> value lookup
    values_to_set: Dict[str, str] = {}
    for field_name, kz in FIELD_TO_KZ.items():
        val = kz_values.get(kz)
        if val:
            values_to_set[field_name] = val

    if user_name:
        values_to_set["Zahl07_01"] = user_name
    if tax_number:
        values_to_set["Zahl03"] = stnr_parts[0]
        values_to_set["Zahl02_1"] = stnr_parts[1]
        values_to_set["Zahl02_2"] = stnr_parts[2]

    if not values_to_set:
        doc.close()
        return None

    # Set NeedAppearances
    try:
        for i in range(1, min(doc.xref_length(), 50)):
            obj_str = doc.xref_object(i)
            if "/AcroForm" in obj_str and "/Type /Catalog" in obj_str:
                m = _re.search(r"/AcroForm\s+(\d+)\s+0\s+R", obj_str)
                if m:
                    af_xref = int(m.group(1))
                    af_obj = doc.xref_object(af_xref)
                    if "/NeedAppearances" not in af_obj:
                        new_af = af_obj.rstrip().rstrip(">")
                        new_af += "\n  /NeedAppearances true\n>>"
                        doc.update_object(af_xref, new_af)
                break
    except Exception:
        pass

    # Fill AcroForm values AND collect widget rects for overlay
    widget_rects: List[Tuple[int, str, str, Any]] = []  # (page_idx, field_name, value, rect)
    filled = 0

    for page_idx, page in enumerate(doc):
        for widget in page.widgets():
            fn = widget.field_name or ""
            if fn in values_to_set:
                val = values_to_set[fn]
                try:
                    widget.field_value = val
                    widget.update()
                    filled += 1
                except Exception:
                    pass
                # Collect rect for overlay regardless of AcroForm success
                widget_rects.append((page_idx, fn, val, widget.rect))

    logger.info(f"AcroForm: filled {filled} fields, overlay: {len(widget_rects)} rects")

    # Check if we actually filled any meaningful KZ value fields (not just personal info).
    # Personal info fields are Zahl07_01, Zahl03, Zahl02_1, Zahl02_2.
    personal_fields = {"Zahl07_01", "Zahl03", "Zahl02_1", "Zahl02_2"}
    kz_fields_filled = sum(
        1 for (_, fn, _, _) in widget_rects if fn not in personal_fields
    )
    if kz_fields_filled == 0:
        logger.info("No KZ value fields were matched – template fill not useful")
        doc.close()
        return None

    # Draw overlay text at each widget rect position
    fontname = "helv"
    fontsize = 8
    for page_idx, fn, val, rect in widget_rects:
        page = doc[page_idx]
        # Sanitize value for Latin-1 font compatibility
        safe_val = _sanitize_latin1(val)
        # Right-align numeric values, left-align text
        is_numeric = any(c.isdigit() for c in safe_val)
        if is_numeric:
            tw = fitz.get_text_length(safe_val, fontname=fontname, fontsize=fontsize)
            x = rect.x1 - tw - 2
        else:
            x = rect.x0 + 2
        # Vertically center in the widget rect
        y = rect.y0 + (rect.height + fontsize) / 2 - 1
        try:
            page.insert_text(
                fitz.Point(x, y),
                safe_val,
                fontsize=fontsize,
                fontname=fontname,
                color=(0, 0, 0.6),  # Dark blue to distinguish from printed form text
            )
        except Exception as e:
            logger.debug(f"Overlay failed for {fn}: {e}")

    buf = io.BytesIO()
    doc.save(buf, garbage=3, deflate=True)
    doc.close()
    return buf.getvalue()


def fill_template_overlay(template_path: Path, form_data: Dict[str, Any]) -> bytes:
    """
    Fill an official E1 PDF template by overlaying text at known positions.

    This is the fallback for flat (non-fillable) PDFs. It draws text directly
    on top of the form at the KZ field positions discovered during calibration.
    """
    doc = fitz.open(str(template_path))

    # Build KZ -> value mapping
    kz_values: Dict[str, str] = {}
    for field in form_data.get("fields", []):
        kz = field.get("kz", "")
        value = field.get("value", 0)
        if kz and value:
            kz_values[kz] = _fmt_eur(value)

    # For overlay mode, use KZ_TO_FIELD reverse mapping to find positions
    # from the calibration data. We draw at the field rect positions.
    # Since we don't have the actual widget rects in a flat PDF,
    # we use approximate positions based on the 2024 template layout.

    # Key KZ positions: (page_idx, x_right, y_baseline)
    # These are the right edge of the value field and the text baseline
    OVERLAY_POSITIONS: Dict[str, Tuple[int, float, float]] = {
        # Page 2: Summe betriebliche Einkünfte
        "310": (2, 355, 418),   # Summe L&F
        "320": (2, 460, 418),   # Summe Selbständig
        "330": (2, 565, 418),   # Summe Gewerbe
        # Page 4: Werbungskosten
        "717": (4, 564, 388),   # Gewerkschaftsbeiträge
        "718": (4, 564, 273),   # Personenversicherungen
        "724": (4, 564, 774),   # Sonstige Werbungskosten
        "725": (4, 564, 171),   # Topfsonderausgaben
        "169": (4, 564, 572),   # Digitale Arbeitsmittel
        "719": (4, 564, 595),   # Andere Arbeitsmittel
        "720": (4, 564, 617),   # Fachliteratur
        "721": (4, 564, 640),   # Reisekosten
        "722": (4, 564, 663),   # Fortbildung
        "723": (4, 564, 708),   # Doppelte Haushaltsführung
        # Page 5: Vermietung
        "370": (5, 562, 442),   # Summe V&V
        "373": (5, 562, 419),   # Sonstige V&V
        # Page 7: Sonderausgaben
        "462": (7, 557, 642),   # Verlustabzug
    }

    for kz, (page_idx, x_right, y) in OVERLAY_POSITIONS.items():
        if page_idx >= len(doc):
            continue
        value = kz_values.get(kz, "")
        if not value:
            continue

        page = doc[page_idx]
        tw = fitz.get_text_length(value, fontname="cour", fontsize=9)
        page.insert_text(
            fitz.Point(x_right - tw - 2, y),
            value,
            fontsize=9,
            fontname="cour",
            color=(0, 0, 0),
        )

    # Personal info overlay on page 0
    user_name = form_data.get("user_name", "")
    tax_number = form_data.get("tax_number", "")
    if user_name:
        safe_name = _sanitize_latin1(user_name)
        doc[0].insert_text(fitz.Point(240, 178), safe_name, fontsize=9, fontname="helv")
    if tax_number:
        doc[0].insert_text(fitz.Point(69, 178), tax_number, fontsize=9, fontname="helv")

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def calibrate_template(template_path: str):
    """
    Utility: Print all form fields and their positions in a PDF template.
    Also attempts to match field names to nearby KZ number labels.

    Usage:
        python -c "from app.services.e1_template_filler import calibrate_template; calibrate_template('app/templates/E1_2024.pdf')"
    """
    import re

    doc = fitz.open(template_path)
    print(f"Pages: {len(doc)}")
    print(f"Page size: {doc[0].rect.width} x {doc[0].rect.height}")
    print()

    for page_idx, page in enumerate(doc):
        print(f"=== Page {page_idx} ===")

        # List form fields (widgets)
        widgets = list(page.widgets())
        if widgets:
            print(f"  Form fields ({len(widgets)}):")
            for w in widgets:
                print(f"    {w.field_name}: type={w.field_type}, "
                      f"rect={w.rect}, value='{w.field_value}'")
        else:
            print("  No form fields on this page")

        # Extract KZ number labels
        blocks = page.get_text("dict")["blocks"]
        kz_blocks = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if re.match(r"^\d{3}$", text):
                        bbox = span["bbox"]
                        kz_blocks.append((text, bbox))

        if kz_blocks:
            print(f"  KZ labels ({len(kz_blocks)}):")
            for text, bbox in sorted(kz_blocks, key=lambda x: (x[1][1], x[1][0])):
                print(f"    KZ {text} at ({bbox[0]:.0f}, {bbox[1]:.0f}, "
                      f"{bbox[2]:.0f}, {bbox[3]:.0f})")

    doc.close()


def fill_e1_from_template(form_data: Dict[str, Any]) -> Optional[bytes]:
    """
    Try to fill an official E1 template PDF with user data.

    Returns filled PDF bytes, or None if no template is available.

    Strategy:
    1. Look for template file in app/templates/
    2. Use AcroForm filling (sets field values in PDF data layer)
    3. ALSO overlay visible text on top (ensures values display in all viewers)

    BMF PDFs have JavaScript-controlled field rendering that many PDF viewers
    (browsers, macOS Preview, VS Code) do not execute. The overlay ensures
    values are always visible regardless of viewer capabilities.
    """
    form_type = form_data.get("form_type", "E1")
    tax_year = form_data.get("tax_year", 2024)

    template_path = find_template(form_type, tax_year)
    if not template_path:
        logger.info(f"No template found for {form_type} {tax_year}")
        return None

    logger.info(f"Using template: {template_path}")

    # Count how many fields have non-zero values
    non_zero_fields = sum(
        1 for f in form_data.get("fields", [])
        if f.get("kz") and f.get("value") and float(f.get("value", 0)) != 0
    )

    # Use hybrid approach: AcroForm + overlay for maximum compatibility
    result = _fill_hybrid(template_path, form_data)
    if result:
        logger.info("Filled template using hybrid (AcroForm + overlay) mode")
        return result

    # Pure overlay fallback – only if we have data to fill
    if non_zero_fields > 0:
        logger.info("Falling back to pure overlay mode")
        return fill_template_overlay(template_path, form_data)

    # No data to fill – let caller fall back to generated replica
    logger.info("No non-zero fields to fill in template, skipping template mode")
    return None
