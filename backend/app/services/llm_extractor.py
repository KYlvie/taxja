"""
LLM-based document field extractor.
Uses Ollama (or OpenAI) to extract structured data from OCR text.
Falls back to regex extractors if LLM is unavailable or fails.
"""
import json
import logging
import re
from typing import Dict, Any, Optional

from app.services.llm_service import get_llm_service
from app.services.document_classifier import DocumentType

logger = logging.getLogger(__name__)


# --- Extraction prompts per document type ---

INVOICE_EXTRACTION_PROMPT = """Du bist ein Experte für die Extraktion von Daten aus österreichischen Rechnungen und Belegen.
Extrahiere die folgenden Felder aus dem OCR-Text. Antworte NUR mit einem JSON-Objekt.
Wenn ein Feld nicht gefunden wird, setze den Wert auf null.

Felder:
- date: Rechnungsdatum (Format: YYYY-MM-DD)
- amount: Gesamtbetrag in EUR (Zahl, ohne Währungszeichen)
- merchant: Name des Händlers/Lieferanten
- tax_id: UID-Nummer oder Steuernummer
- vat_amount: Mehrwertsteuerbetrag (Zahl)
- vat_rate: Mehrwertsteuersatz (Zahl, z.B. 20)
- invoice_number: Rechnungsnummer
- description: Kurze Beschreibung der Leistung/Ware
- payment_method: Zahlungsmethode (bar, Karte, Überweisung)

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

# Map document types to prompts
EXTRACTION_PROMPTS = {
    DocumentType.INVOICE: INVOICE_EXTRACTION_PROMPT,
    DocumentType.RECEIPT: INVOICE_EXTRACTION_PROMPT,
    DocumentType.MIETVERTRAG: MIETVERTRAG_EXTRACTION_PROMPT,
    DocumentType.KAUFVERTRAG: KAUFVERTRAG_EXTRACTION_PROMPT,
    DocumentType.E1_FORM: E1_FORM_EXTRACTION_PROMPT,
    DocumentType.EINKOMMENSTEUERBESCHEID: BESCHEID_EXTRACTION_PROMPT,
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
                max_tokens=2000,
            )
            return self._parse_json_response(response)
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
            "Du klassifizierst Dokumente. Antworte NUR mit einem der folgenden Typen:\n"
            "invoice, receipt, mietvertrag, kaufvertrag, e1_form, "
            "einkommensteuerbescheid, bank_statement, unknown\n\n"
            "Keine Erklärungen, nur das eine Wort."
        )

        text = raw_text[:3000] if len(raw_text) > 3000 else raw_text

        try:
            response = self.llm.generate_simple(
                system_prompt=system_prompt,
                user_prompt=f"Dokument-Text:\n\n{text}",
                temperature=0.0,
                max_tokens=20,
            )
            return response.strip().lower().replace('"', "").replace("'", "")
        except Exception:
            return None

    @staticmethod
    def _parse_json_response(response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if not response:
            return None

        text = response.strip()

        # Remove markdown code block wrapper if present
        if text.startswith("```"):
            # Remove opening ```json or ```
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            # Remove closing ```
            text = re.sub(r"\n?```\s*$", "", text)

        # Try to find JSON object in the response
        # Sometimes LLM adds text before/after the JSON
        json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if json_match:
            text = json_match.group(0)

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON response: %s", text[:200])

        return None


# Singleton
_llm_extractor: Optional[LLMExtractor] = None


def get_llm_extractor() -> LLMExtractor:
    global _llm_extractor
    if _llm_extractor is None:
        _llm_extractor = LLMExtractor()
    return _llm_extractor
