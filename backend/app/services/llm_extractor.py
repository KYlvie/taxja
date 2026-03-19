"""
LLM-based document field extractor.
Uses Ollama (or OpenAI) to extract structured data from OCR text.
Falls back to regex extractors if LLM is unavailable or fails.
"""
import json
import logging
import re
from typing import Dict, Any, Optional, List

from app.services.llm_service import get_llm_service
from app.services.document_classifier import DocumentType

logger = logging.getLogger(__name__)


# --- Extraction prompts per document type ---

INVOICE_EXTRACTION_PROMPT = """Du bist ein Experte für die Extraktion von Daten aus österreichischen Rechnungen und Belegen.
Extrahiere die folgenden Felder aus dem OCR-Text. Antworte NUR mit JSON.

WICHTIG: Wenn der Text MEHRERE separate Rechnungen/Belege/Quittungen enthält (z.B. mehrere Kassenbons,
mehrere Rechnungen in einem Dokument, oder verschiedene Einkäufe), gib ein JSON-ARRAY zurück mit einem
Objekt pro Beleg. Wenn nur EIN Beleg vorhanden ist, gib ein einzelnes JSON-Objekt zurück.

Erkennungsmerkmale für mehrere Belege:
- Mehrere "Summe"/"Total"/"Gesamt"-Zeilen
- Verschiedene Händlernamen/Adressen
- Verschiedene Daten
- Wiederholte Kopfzeilen (z.B. "Rechnung", "Kassenbon", "Beleg")
- Verschiedene Rechnungsnummern

Felder pro Beleg:
- date: Rechnungsdatum (Format: YYYY-MM-DD)
- amount: Gesamtbetrag in EUR (Zahl, ohne Währungszeichen). Bei Kassenbon: SUMME/TOTAL/GESAMT. Bei Rechnung: Rechnungsbetrag/Zahlbetrag. Trenne Tausender korrekt: "1.500,00" = 1500.00, "15,00" = 15.00
- merchant: Name des Händlers/Lieferanten. Bei Kassenbon: steht ganz oben (z.B. "BILLA", "SPAR", "HOFER"). Bei Rechnung: Absender/Lieferant
- tax_id: UID-Nummer (ATU...) oder Steuernummer
- vat_amount: Mehrwertsteuerbetrag in EUR (Zahl)
- vat_rate: Mehrwertsteuersatz (Zahl, z.B. 20 oder 10). Bei gemischten Sätzen den höchsten angeben
- invoice_number: Rechnungsnummer / Belegnummer / BON-NR
- description: Kurze Beschreibung der Leistung/Ware (max 100 Zeichen, fasse die wichtigsten Positionen zusammen)
- payment_method: Zahlungsmethode ("bar", "karte", "ueberweisung", null wenn unklar)
- line_items: Array von Einzelpositionen, jede mit {"name": "Artikelname", "quantity": Menge, "price": Einzelpreis, "total": Gesamtpreis}. Extrahiere ALLE lesbaren Positionen. Bei unlesbaren OCR-Fragmenten überspringen.

Beispiel EIN Beleg:
{"date": "2026-03-15", "amount": 23.45, "merchant": "BILLA", "tax_id": null, "vat_amount": 3.91, "vat_rate": 20, "invoice_number": "BON-4521", "description": "Lebensmittel: Milch, Brot, Kaffee", "payment_method": "karte", "line_items": [{"name": "Milch 1L", "quantity": 1, "price": 1.49, "total": 1.49}]}

Beispiel MEHRERE Belege:
[{"date": "2026-03-15", "amount": 23.45, "merchant": "BILLA", "description": "Lebensmittel", "line_items": [...]}, {"date": "2026-03-15", "amount": 89.90, "merchant": "Mediamarkt", "description": "USB-Kabel", "line_items": [...]}]

Antworte NUR mit validem JSON, keine Erklärungen."""

MIETVERTRAG_EXTRACTION_PROMPT = """Du bist ein Experte für die Extraktion von Daten aus österreichischen Mietverträgen.
Extrahiere die folgenden Felder aus dem OCR-Text. Antworte NUR mit einem JSON-Objekt.
Wenn ein Feld nicht gefunden wird, setze den Wert auf null.

Felder:
- property_address: Vollständige Adresse des Mietobjekts
- street: Straße und Hausnummer
- city: Stadt/Ort
- postal_code: Postleitzahl (4-stellig)
- monthly_rent: Monatliche Miete/Hauptmietzins in EUR (Zahl)
- start_date: Mietbeginn (Format: YYYY-MM-DD)
- end_date: Mietende (Format: YYYY-MM-DD, null bei unbefristet)
- betriebskosten: Betriebskosten in EUR (Zahl)
- heating_costs: Heizkosten in EUR (Zahl)
- deposit_amount: Kaution in EUR (Zahl)
- tenant_name: Name des Mieters
- landlord_name: Name des Vermieters
- contract_type: "Befristet" oder "Unbefristet"

Antworte NUR mit validem JSON, keine Erklärungen."""

KAUFVERTRAG_EXTRACTION_PROMPT = """Du bist ein Experte für die Extraktion von Daten aus österreichischen Kaufverträgen (Immobilien).
Extrahiere die folgenden Felder aus dem OCR-Text. Antworte NUR mit einem JSON-Objekt.
Wenn ein Feld nicht gefunden wird, setze den Wert auf null.

Felder:
- property_address: Vollständige Adresse der Liegenschaft
- street: Straße und Hausnummer
- city: Stadt/Ort
- postal_code: Postleitzahl (4-stellig)
- purchase_price: Kaufpreis in EUR (Zahl)
- purchase_date: Kaufdatum (Format: YYYY-MM-DD)
- building_value: Gebäudewert in EUR (Zahl)
- land_value: Grundwert in EUR (Zahl)
- grunderwerbsteuer: Grunderwerbsteuer in EUR (Zahl)
- notary_fees: Notarkosten in EUR (Zahl)
- registry_fees: Eintragungsgebühr in EUR (Zahl)
- buyer_name: Name des Käufers
- seller_name: Name des Verkäufers
- notary_name: Name des Notars
- construction_year: Baujahr (Zahl)
- property_type: "Wohnung", "Haus" oder "Grundstück"

Antworte NUR mit validem JSON, keine Erklärungen."""


E1_FORM_EXTRACTION_PROMPT = """Du bist ein Experte für die Extraktion von Daten aus österreichischen E1 Einkommensteuererklärungen.
Extrahiere die folgenden Felder aus dem OCR-Text. Antworte NUR mit einem JSON-Objekt.
Wenn ein Feld nicht gefunden wird, setze den Wert auf null.

Felder:
- taxpayer_name: Name des Steuerpflichtigen
- steuernummer: Steuernummer
- tax_year: Steuerjahr (Zahl)
- total_income: Gesamtbetrag der Einkünfte in EUR (Zahl)
- rental_income: Einkünfte aus Vermietung und Verpachtung KZ 350 (Zahl)
- self_employment_income: Einkünfte aus selbständiger Arbeit (Zahl)
- employment_income: Einkünfte aus nichtselbständiger Arbeit (Zahl)
- sonderausgaben: Sonderausgaben (Zahl)
- werbungskosten: Werbungskosten (Zahl)
- loss_carryforward: Verlustvortrag (Zahl)

Antworte NUR mit validem JSON, keine Erklärungen."""

BESCHEID_EXTRACTION_PROMPT = """Du bist ein Experte für die Extraktion von Daten aus österreichischen Einkommensteuerbescheiden.
Extrahiere die folgenden Felder aus dem OCR-Text. Antworte NUR mit einem JSON-Objekt.
Wenn ein Feld nicht gefunden wird, setze den Wert auf null.

Felder:
- taxpayer_name: Name des Steuerpflichtigen
- steuernummer: Steuernummer
- tax_year: Veranlagungsjahr (Zahl)
- total_income: Einkommen (Zahl)
- tax_amount: Festgesetzte Einkommensteuer (Zahl)
- prepayments: Vorauszahlungen (Zahl)
- refund_amount: Gutschrift/Nachzahlung (Zahl, positiv=Gutschrift, negativ=Nachzahlung)
- effective_tax_rate: Durchschnittssteuersatz (Zahl in Prozent)

Antworte NUR mit validem JSON, keine Erklärungen."""

PAYSLIP_EXTRACTION_PROMPT = """Du bist ein Experte für die Extraktion von Daten aus österreichischen Gehaltsabrechnungen / Lohnzetteln.
Extrahiere die folgenden Felder aus dem OCR-Text. Antworte NUR mit einem JSON-Objekt.
Wenn ein Feld nicht gefunden wird, setze den Wert auf null.

Felder:
- gross_income: Bruttobezug / Summe Bezüge in EUR (Zahl). Der GESAMTE Bruttobetrag VOR Abzügen.
- net_income: Nettobezug / Auszahlungsbetrag in EUR (Zahl). Der Betrag NACH allen Abzügen.
- withheld_tax: Lohnsteuer in EUR (Zahl). Auch "LSt" oder "Lohnsteuer" genannt.
- social_insurance: Sozialversicherungsbeiträge in EUR (Zahl). Summe aller SV-Beiträge (KV, PV, AV, UV).
- employer: Name des Arbeitgebers / Dienstgebers
- date: Abrechnungsmonat oder Auszahlungsdatum (Format: YYYY-MM-DD). Bei "Auszahlungsmonat: 01.2024" -> "2024-01-01". Bei "Jänner 2024" -> "2024-01-01".
- employee_name: Name des Arbeitnehmers / Dienstnehmers
- personnel_number: Personalnummer

Beispiel:
{"gross_income": 5136.55, "net_income": 3332.02, "withheld_tax": 972.27, "social_insurance": 880.91, "employer": "Stadt Wien", "date": "2024-01-01", "employee_name": null, "personnel_number": "12345"}

Antworte NUR mit validem JSON, keine Erklärungen."""

# Generic tax form extraction prompt — used for all KZ-based Austrian tax forms
TAX_FORM_GENERIC_PROMPT = """Du bist ein Experte für österreichische Steuerformulare.
Extrahiere ALLE Kennzahlen (KZ) und deren Werte aus dem OCR-Text. Antworte NUR mit JSON.
Wenn ein Feld nicht gefunden wird, setze den Wert auf null.

Allgemeine Felder:
- tax_year: Steuerjahr (Zahl)
- taxpayer_name: Name des Steuerpflichtigen
- steuernummer: Steuernummer
- employer_name: Arbeitgeber (falls vorhanden)

Kennzahlen als kz_XXX (z.B. kz_210, kz_245, kz_260):
Extrahiere JEDE Kennzahl die im Text vorkommt im Format "kz_XXX": Wert.
Beträge als Zahlen (nicht als String), z.B. "kz_245": 35000.00

Zusätzliche Felder je nach Formulartyp:
- gewinn_verlust: Gewinn/Verlust (E1a, Jahresabschluss)
- betriebseinnahmen, betriebsausgaben: Einnahmen/Ausgaben (E1a)
- monthly_rent, property_address: Mietdaten (E1b)
- total_capital_gains: Kapitalerträge (E1kv)
- umsatz_20, umsatz_10, vorsteuer, zahllast: USt-Daten (U1/U30)
- pension_insurance, health_insurance, accident_insurance: SVS-Beiträge
- grundsteuer_amount, einheitswert: Grundsteuer
- familienbonus_total: Familienbonus (L1k)
- alleinverdiener, pendlerpauschale: Absetzbeträge (L1ab)
- confidence: Deine Einschätzung der Extraktionsqualität (0.0-1.0)

Antworte NUR mit validem JSON, keine Erklärungen."""

# Map document types to prompts
EXTRACTION_PROMPTS = {
    DocumentType.INVOICE: INVOICE_EXTRACTION_PROMPT,
    DocumentType.RECEIPT: INVOICE_EXTRACTION_PROMPT,
    DocumentType.LOHNZETTEL: PAYSLIP_EXTRACTION_PROMPT,
    DocumentType.PAYSLIP: PAYSLIP_EXTRACTION_PROMPT,
    DocumentType.MIETVERTRAG: MIETVERTRAG_EXTRACTION_PROMPT,
    DocumentType.KAUFVERTRAG: KAUFVERTRAG_EXTRACTION_PROMPT,
    DocumentType.E1_FORM: E1_FORM_EXTRACTION_PROMPT,
    DocumentType.EINKOMMENSTEUERBESCHEID: BESCHEID_EXTRACTION_PROMPT,
    # Tax form types — all use the generic KZ extraction prompt
    DocumentType.L1_FORM: TAX_FORM_GENERIC_PROMPT,
    DocumentType.L1K_BEILAGE: TAX_FORM_GENERIC_PROMPT,
    DocumentType.L1AB_BEILAGE: TAX_FORM_GENERIC_PROMPT,
    DocumentType.E1A_BEILAGE: TAX_FORM_GENERIC_PROMPT,
    DocumentType.E1B_BEILAGE: TAX_FORM_GENERIC_PROMPT,
    DocumentType.E1KV_BEILAGE: TAX_FORM_GENERIC_PROMPT,
    DocumentType.U1_FORM: TAX_FORM_GENERIC_PROMPT,
    DocumentType.U30_FORM: TAX_FORM_GENERIC_PROMPT,
    DocumentType.JAHRESABSCHLUSS: TAX_FORM_GENERIC_PROMPT,
    DocumentType.SVS_NOTICE: TAX_FORM_GENERIC_PROMPT,
    DocumentType.PROPERTY_TAX: TAX_FORM_GENERIC_PROMPT,
    DocumentType.BANK_STATEMENT: TAX_FORM_GENERIC_PROMPT,
}


class LLMExtractor:
    """Extract structured data from OCR text using LLM."""

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm_service()
        return self._llm

    @property
    def is_available(self) -> bool:
        try:
            return self.llm.is_available
        except Exception:
            return False

    def extract(
        self, raw_text: str, doc_type: DocumentType
    ) -> Optional[Dict[str, Any]]:
        """
        Extract fields from OCR text using LLM.

        For invoices/receipts, the LLM may return a JSON array when multiple
        receipts are detected. In that case, the first receipt becomes the
        primary result and the rest are stored in ``_additional_receipts``.

        Args:
            raw_text: OCR-extracted text
            doc_type: Detected document type

        Returns:
            Dict of extracted fields, or None if LLM unavailable/failed
        """
        if not self.is_available:
            logger.debug("LLM not available, skipping LLM extraction")
            return None

        prompt = EXTRACTION_PROMPTS.get(doc_type)
        if not prompt:
            logger.debug("No LLM extraction prompt for doc type: %s", doc_type)
            return None

        # Truncate very long texts to avoid token limits
        text = raw_text[:8000] if len(raw_text) > 8000 else raw_text

        try:
            response = self.llm.generate_simple(
                system_prompt=prompt,
                user_prompt=f"OCR-Text:\n\n{text}",
                temperature=0.1,
                max_tokens=4000,
            )
            parsed = self._parse_json_response(response)
            if parsed is None:
                return None

            # Handle multi-receipt array response from LLM
            if isinstance(parsed, list):
                valid = [r for r in parsed if isinstance(r, dict) and r.get("amount") is not None]
                if not valid:
                    return None
                if len(valid) == 1:
                    return valid[0]
                # Multiple receipts — pack into _additional_receipts format
                primary = valid[0]
                primary["_additional_receipts"] = valid[1:]
                primary["_receipt_count"] = len(valid)
                logger.info("LLM detected %d receipts in document text", len(valid))
                return primary

            return parsed
        except Exception as e:
            logger.warning("LLM extraction failed: %s", e)
            return None

    def classify_document(self, raw_text: str) -> Optional[str]:
        """
        Use LLM to classify document type.

        Returns document type string or None if failed.
        """
        if not self.is_available:
            return None

        system_prompt = (
            "Du bist ein Experte fuer oesterreichische Finanzdokumente. "
            "Klassifiziere das Dokument in GENAU einen der folgenden Typen. "
            "Antworte NUR mit dem Typ-Wort, nichts anderes.\n\n"
            "Typen:\n"
            "- receipt: Kassenbon, Einkaufsbeleg (BILLA, SPAR, HOFER, Tankstelle, Restaurant). "
            "Erkennbar an: BON-NR, KASSE, SUMME, BAR/KARTE, kurzes Format\n"
            "- invoice: Rechnung, Honorarnote (hat Rechnungsnummer, UID/ATU-Nummer, Zahlungsziel). "
            "Erkennbar an: RECHNUNG, RE-NR, Rechnungsbetrag, Zahlbar bis\n"
            "- lohnzettel: Lohn-/Gehaltszettel, L16 (hat Brutto/Netto, Lohnsteuer, SV-Beitraege, Arbeitgeber). "
            "Erkennbar an: GEHALT, LOHNSTEUER, SV-BASIS, AUSZAHLUNGSBETRAG\n"
            "- mietvertrag: Mietvertrag (hat Mietzins, Vermieter/Mieter, Mietobjekt, Betriebskosten)\n"
            "- kaufvertrag: Kaufvertrag fuer Immobilien (hat Kaufpreis, Kaeufer/Verkaeufer, Grundbuch, Notar)\n"
            "- e1_form: Steuererklaerung E1/E1a/E1b/L1k (hat Kennzahlen KZ, Einkommensteuererklaerung, Finanzamt)\n"
            "- einkommensteuerbescheid: Steuerbescheid vom Finanzamt (hat festgesetzte Steuer, Gutschrift/Nachzahlung)\n"
            "- svs_notice: SVS-Beitragsmitteilung (hat SVS, Beitragsgrundlage, Pensionsversicherung)\n"
            "- bank_statement: Kontoauszug (hat IBAN, Saldo, Buchungen, Kontostand)\n"
            "- unknown: Nur wenn keiner der obigen Typen passt\n\n"
            "Beispiele:\n"
            "Text mit 'BILLA...Kassenbon...SUMME EUR 23,45...BAR' -> receipt\n"
            "Text mit 'Rechnung Nr. RE-2026-001...UID ATU12345...Zahlbar bis' -> invoice\n"
            "Text mit 'Gehaltsabrechnung...Brutto 3.500,00...Lohnsteuer 450,00...Netto' -> lohnzettel\n"
            "Text mit 'E 1-PDF...Einkommensteuererklaerung...KZ 245' -> e1_form\n"
            "Text mit 'Einkommensteuerbescheid...festgesetzte Steuer...Gutschrift' -> einkommensteuerbescheid"
        )

        text = raw_text[:4000] if len(raw_text) > 4000 else raw_text

        try:
            response = self.llm.generate_simple(
                system_prompt=system_prompt,
                user_prompt=f"Klassifiziere dieses Dokument:\n\n{text}",
                temperature=0.0,
                max_tokens=500,  # gpt-oss-120b is a reasoning model; needs ~50+ reasoning tokens before output
            )
            result = response.strip().lower().replace('"', "").replace("'", "")
            # Validate response is a known type
            valid_types = {
                "receipt", "invoice", "lohnzettel", "mietvertrag", "kaufvertrag",
                "e1_form", "einkommensteuerbescheid", "svs_notice", "bank_statement",
                "unknown",
            }
            # Handle partial matches (LLM might say "receipt." or "type: receipt")
            for vt in valid_types:
                if vt in result:
                    return vt
            logger.warning("LLM classify returned unexpected type: %s", result)
            return None
        except Exception as e:
            logger.warning("LLM classification failed: %s", e)
            return None

    @staticmethod
    def _parse_json_response(response: str) -> Optional[Any]:
        """
        Parse JSON from LLM response with multi-layer fallback.

        Returns a dict (single receipt) or list (multiple receipts).

        Strategy:
          1. Strip markdown code fences
          2. Try json.loads on full text
          3. Extract outermost { ... } or [ ... ] block (supports nested objects/arrays)
          4. Light repair: trailing commas, unquoted keys
          5. On failure: log the raw response and reason, never silently swallow

        Tracks parse path: parsed_direct / parsed_outer_block / parsed_repaired / parsed_failed
        for monitoring prompt output format stability.
        """
        if not response:
            logger.warning("JSON parse: empty response [parse_path=empty_input]")
            return None

        text = response.strip()
        parse_attempts = []

        # Step 1: Strip markdown code fences
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
            text = text.strip()

        # Step 2: Try direct parse (fast path)
        try:
            data = json.loads(text)
            if isinstance(data, (dict, list)):
                logger.debug("JSON parse OK [parse_path=parsed_direct]")
                return data
        except json.JSONDecodeError as e:
            parse_attempts.append(f"direct: {e}")

        # Step 3: Extract outermost JSON block — try [ ... ] first (array), then { ... }
        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        first_brace = text.find("{")
        last_brace = text.rfind("}")

        # Determine which outer delimiter comes first
        candidates = []
        if first_bracket != -1 and last_bracket > first_bracket:
            candidates.append((first_bracket, last_bracket, "["))
        if first_brace != -1 and last_brace > first_brace:
            candidates.append((first_brace, last_brace, "{"))
        # Sort by position — try the one that appears first
        candidates.sort(key=lambda c: c[0])

        for start_pos, end_pos, _delim in candidates:
            json_block = text[start_pos:end_pos + 1]
            try:
                data = json.loads(json_block)
                if isinstance(data, (dict, list)):
                    logger.info("JSON parse OK [parse_path=parsed_outer_block]")
                    return data
            except json.JSONDecodeError as e:
                parse_attempts.append(f"outermost_block({_delim}): {e}")

            # Step 4: Light repair on extracted block
            repaired = json_block
            repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
            repaired = repaired.replace("True", "true").replace("False", "false").replace("None", "null")

            if repaired != json_block:
                try:
                    data = json.loads(repaired)
                    if isinstance(data, (dict, list)):
                        logger.warning(
                            "JSON parse OK after repair [parse_path=parsed_repaired] — "
                            "indicates prompt output format instability"
                        )
                        return data
                except json.JSONDecodeError as e:
                    parse_attempts.append(f"repaired({_delim}): {e}")

        # All attempts failed — log for debugging, don't silently return None
        logger.warning(
            "JSON parse FAILED [parse_path=parsed_failed] after %d attempts: %s | "
            "raw_response (first 500 chars): %s",
            len(parse_attempts),
            "; ".join(parse_attempts),
            response[:500],
        )
        return None


# Singleton
_llm_extractor: Optional[LLMExtractor] = None


def get_llm_extractor() -> LLMExtractor:
    global _llm_extractor
    if _llm_extractor is None:
        _llm_extractor = LLMExtractor()
    return _llm_extractor
