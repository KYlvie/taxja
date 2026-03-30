"""
AI-First Document Classifier & Extractor.

Two-round strategy:
  Round 1: Mega-prompt covers ALL document types → returns type + subtype + core fields
  Round 2: Type-specific deep extraction prompt (only if needed)

This replaces regex-first classification with LLM-first, using keywords only as fallback.
"""
import json
import logging
import re
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Round 1: Mega-prompt — one LLM call classifies + extracts core fields
# ──────────────────────────────────────────────────────────────────────

ROUND1_SYSTEM_PROMPT = """\
Du bist ein Experte für österreichische Steuer- und Finanzdokumente.
Analysiere das Dokument und gib die Ergebnisse als JSON zurück.

DOKUMENT-TYPEN (wähle GENAU einen):
- mietvertrag: Mietvertrag (Vermieter, Mieter, Mietzins, Mietdauer)
- mietvorschreibung: Monatliche Mietvorschreibung / Mietzahlungsbeleg
- indexanpassung: Mietzinserhöhung / Indexanpassung / Wertsicherung
- betriebskostenabrechnung: BK-Jahresabrechnung (Nachforderung oder Guthaben)
- kautionsbestaetigung: Kautionsbestätigung / Mietkaution
- uebergabeprotokoll: Wohnungsübergabeprotokoll
- versicherungspolizze: Versicherungspolizze / Versicherungsbestätigung
- versicherung_kuendigung: Kündigungsbestätigung einer Versicherung
- versicherung_praemienaenderung: Prämienänderung / Beitragsanpassung
- versicherung_jahresbestaetigung: Jahresbestätigung / Prämienübersicht
- sepa_lastschrift: SEPA-Lastschrift / Abbuchungsbeleg
- svs_vorschreibung: SVS Beitragsvorschreibung (Quartals-Vorschreibung, GSVG-Pflichtbeitraege)
- svs_nachbemessung: SVS Nachbemessung (Nachforderung oder Gutschrift nach ESt-Bescheid)
- svs_jahresbestaetigung: SVS Jahresbestaetigung (Jahresuebersicht der gezahlten Beitraege)
- invoice: Rechnung / Honorarnote (Handwerker, Hausverwaltung, Dienstleister)
- receipt: Kassenbon / Einkaufsbeleg (Supermarkt, Tankstelle)
- grundsteuerbescheid: Grundsteuerbescheid
- lohnzettel: Lohnzettel / Gehaltszettel / L16
- einkommensteuerbescheid: Einkommensteuerbescheid vom Finanzamt
- svs_notice: SVS-Beitragsmitteilung / Sozialversicherung
- bank_statement: Kontoauszug
- kaufvertrag: Immobilien-Kaufvertrag
- loan_contract: Kreditvertrag / Darlehensvertrag (NEUER Vertrag)
- zinsbescheinigung: Zinsbescheinigung / Zinsbestaetigung (Jahresbestaetigung der Bank ueber gezahlte Zinsen)
- tilgungsplan: Tilgungsplan / Amortisationsplan (Tabelle mit monatlichen Raten)
- loan_kontoauszug: Kreditkonto-Auszug / Kreditkontoauszug (Kontobewegungen eines Kredits)
- e1_form: Steuererklärung E1/E1a/E1b/L1/U1/U30
- spendenbestaetigung: Spendenbestätigung
- kirchenbeitrag: Kirchenbeitrag
- other: Keiner der obigen Typen

ANTWORT NUR als JSON (kein anderer Text):
{
  "document_type": "einer der obigen Typen",
  "confidence": 0.0 bis 1.0,
  "document_subtype": "REQUIRED subtype. For BK: nachzahlung or guthaben. For insurance: berufshaftpflicht/kfz/rechtsschutz/haushaltsversicherung/gebaeudeversicherung/private_krankenversicherung. For invoice: thermenwartung/hausverwaltung/reparatur. For rental: mietvertrag/mietvorschreibung/kaution/uebergabeprotokoll. null only if truly unknown.",
  "document_purpose": "Zweck: polizze, kuendigung, vorschreibung, abrechnung, bestaetigung, rechnung, etc.",
  "role_detection": {
    "landlord_name": "Name des Vermieters oder null",
    "tenant_name": "Name des Mieters oder null",
    "user_is": "landlord oder tenant oder null (wenn DI Maria Steiner im Dokument vorkommt)"
  },
  "amounts": {
    "total_amount": Hauptbetrag als Zahl oder null,
    "annual_amount": Jahresbetrag oder null,
    "monthly_amount": Monatsbetrag oder null,
    "settlement_amount": "NUR bei BK: Differenzbetrag (Nachforderung/Guthaben), NICHT Gesamt-BK",
    "new_amount": "Bei Indexanpassung/Prämienänderung: neuer Betrag oder null"
  },
  "key_fields": {
    "polizze_nr": "Polizzennummer oder null",
    "insurer_name": "Versicherungsgesellschaft oder null",
    "property_address": "Immobilienadresse oder null",
    "date": "YYYY-MM-DD",
    "month": Monat als Zahl 1-12 oder null,
    "year": Jahr als Zahl oder null,
    "invoice_number": "Rechnungsnummer oder null",
    "insured_object": "Versichertes Objekt / Fahrzeug / Kennzeichen oder null",
    "svs_nummer": "SVS-Nummer oder null",
    "beitragsjahr": "Beitragsjahr (bei SVS) oder null",
    "quarter": "Quartal Q1/Q2/Q3/Q4 (bei SVS) oder null",
    "beitragsgrundlage": "Beitragsgrundlage (bei SVS) oder null",
    "quarterly_amount": "Quartalsbeitrag (bei SVS) oder null",
    "nachforderung_amount": "Nachforderung Betrag (bei SVS/BK) oder null",
    "gutschrift_amount": "Gutschrift Betrag (bei SVS/BK) oder null",
    "contract_number": "Vertragsnummer / Kontonummer (bei Kredit) oder null",
    "interest_rate": "Zinssatz in Prozent (bei Kredit) oder null",
    "monthly_payment": "Monatliche Rate (bei Kredit) oder null",
    "loan_amount": "Kreditbetrag (bei Kredit) oder null",
    "lender_name": "Kreditgeber (bei Kredit) oder null"
  },
  "tax_treatment": {
    "is_deductible": true/false/null,
    "deduction_category": "Betriebsausgabe, Werbungskosten, Sonderausgaben, nicht absetzbar, oder null",
    "tax_form": "E1a, E1b, E1, oder null",
    "expense_or_income": "WICHTIG: Aus Sicht des Dokumentempfaengers/Benutzers: expense (Ausgabe) oder income (Einnahme) oder archive_only oder null. Beispiele: Mietvorschreibung fuer Vermieter=income, BK-Nachforderung fuer Vermieter=income (Mieter zahlt), BK-Guthaben fuer Mieter=income (Rueckzahlung), Lohnzettel=income"
  }
}

WICHTIG:
- Bei Betriebskostenabrechnung: settlement_amount ist die DIFFERENZ (Nachforderung oder Guthaben), NICHT die Gesamt-BK. document_subtype MUSS 'nachzahlung' oder 'guthaben' sein — Nachforderung wenn Mieter nachzahlen muss, Guthaben wenn Mieter Geld zurückbekommt.
- Bei Grundsteuerbescheid: annual_amount ist der JAHRESBETRAG, nicht der Quartalsbetrag.
- Bei Versicherungspolizzen: annual_amount ist die JAHRESPRÄMIE (bei Monatsbeträgen ×12, Quartal ×4, Halbjahr ×2).
- Bei Mietvertrag: Wenn DI Maria Steiner als Vermieter/in erscheint → user_is=landlord. Als Mieter/in → user_is=tenant.
- Ein Mietvertrag der das Wort "Übergabe" in einer Klausel erwähnt ist KEIN Übergabeprotokoll.
- Eine Polizze die "Kündigung" in den AGB erwähnt ist KEINE Kündigung.
- Eine Polizze mit SEPA-Zahlungsweg ist KEIN SEPA-Beleg.
- Eine Zinsbescheinigung ist KEIN Kreditvertrag — sie bescheinigt nur die im Jahr gezahlten Zinsen.
- Ein Tilgungsplan ist KEIN Kreditvertrag — er zeigt nur die geplanten Raten.
- Ein Kreditkonto-Auszug ist KEIN normaler Kontoauszug und KEIN Kreditvertrag.
- Beträge als Dezimalzahlen mit Punkt (1662.36 statt 1.662,36). Daten als YYYY-MM-DD.
- Bei Rechnungen: total_amount = BRUTTO, annual_amount = NETTO (ohne USt). Immer beide angeben wenn USt vorhanden.
- Bei Mietvorschreibungen für Vermieter: monthly_amount = Gesamt inkl. BK+USt, settlement_amount = nur Hauptmietzins (ohne BK, ohne USt).
- Bei Hausverwaltung-Rechnungen: Prüfen ob ein verwaltetes Objekt/Immobilie erwähnt wird (auch indirekt, z.B. über Immo-Treuhand, Hausverwaltung GmbH).
- RICHTUNG (expense_or_income) — Aus Sicht des BENUTZERS bestimmen:
  * **Ausgangsrechnung / Honorarnote / AR** (vom Benutzer AUSGESTELLT): **INCOME** (Benutzer stellt Rechnung = Einnahme)
  * Eingangsrechnung / Rechnung (an Benutzer GERICHTET): EXPENSE (Benutzer bezahlt = Ausgabe)
  * WICHTIG: Wenn der Benutzer-Name als Rechnungssteller/Aussteller/Lieferant erscheint → INCOME
  * WICHTIG: Wenn der Benutzer-Name als Empfänger/Kunde erscheint → EXPENSE
  * Mietvorschreibung, wenn Benutzer=Vermieter: INCOME (er bekommt Geld vom Mieter)
  * BK-Nachforderung, wenn Benutzer=Vermieter: INCOME (Mieter zahlt nach)
  * BK-Guthaben, wenn Benutzer=Mieter: INCOME (teilweise Rückerstattung = Betriebseinnahme)
  * BK-Guthaben, wenn Benutzer=Vermieter: EXPENSE (er zahlt dem Mieter zurück)
  * BK-Nachforderung, wenn Benutzer=Mieter: EXPENSE
  * Lohnzettel/Gehalt: INCOME
  * SVS-Gutschrift: INCOME
  * Kaution: archive_only (weder Einnahme noch Ausgabe)
- V+V-Dokumente (Vermietung) gehen auf E1b, NICHT E1a.
- BK bei Vermietung = durchlaufende Posten (is_deductible kann true sein, Kategorie=Werbungskosten)."""

ROUND1_USER_TEMPLATE = "Analysiere dieses Dokument:\n\n{text}"

# ──────────────────────────────────────────────────────────────────────
# Round 2: Type-specific deep extraction prompts
# ──────────────────────────────────────────────────────────────────────

ROUND2_PROMPTS = {
    "versicherungspolizze": """\
Extrahiere ALLE Felder dieser Versicherungspolizze. NUR JSON:
{
  "insurer_name": "Versicherungsgesellschaft",
  "versicherungsnehmer": "Versicherungsnehmer",
  "polizze_nr": "Polizzennummer",
  "insurance_type": "Versicherungsart (z.B. Berufshaftpflicht, KFZ, Rechtsschutz)",
  "insurance_subtype": "berufshaftpflicht|kfz|rechtsschutz|haushaltsversicherung|gebaeudeversicherung|private_krankenversicherung|unfallversicherung|lebensversicherung|other",
  "document_purpose": "polizze|kuendigung|praemienaenderung|jahresbestaetigung|sepa_beleg",
  "praemie_jaehrlich": Jahresprämie_als_Zahl,
  "zahlungsfrequenz": "monatlich|vierteljaehrlich|halbjaehrlich|jaehrlich",
  "vertragsbeginn": "YYYY-MM-DD",
  "vertragsende": "YYYY-MM-DD oder null",
  "neue_praemie": "bei Prämienänderung: neuer Betrag, sonst null",
  "kuendigung_datum": "bei Kündigung: Enddatum, sonst null",
  "versichertes_objekt": "Adresse/Kennzeichen/Beschreibung oder null"
}
Beträge als Dezimalzahlen (1662.36). Daten YYYY-MM-DD. null wenn nicht gefunden.""",

    "mietvertrag": """\
Extrahiere ALLE Felder dieses Mietvertrags. NUR JSON:
{
  "landlord_name": "Vermieter",
  "tenant_name": "Mieter",
  "property_address": "Mietobjekt Adresse",
  "hauptmietzins": Zahl,
  "betriebskosten": Zahl,
  "umsatzsteuer": Zahl,
  "gesamtmiete": Zahl,
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD oder null (unbefristet)",
  "kaution": Zahl_oder_null,
  "nutzflaeche_m2": Zahl_oder_null,
  "contract_type": "befristet|unbefristet"
}""",

    "betriebskostenabrechnung": """\
Extrahiere die BK-Abrechnung. NUR JSON:
{
  "abrechnungsjahr": Zahl,
  "settlement_type": "nachforderung|guthaben",
  "settlement_amount": DIFFERENZ_als_Zahl,
  "total_actual_bk": Gesamte_tatsächliche_BK,
  "total_akonto_paid": Geleistete_Akontozahlungen,
  "property_address": "Objekt-Adresse",
  "tenant_name": "Mieter",
  "landlord_name": "Vermieter oder Hausverwaltung"
}
WICHTIG: settlement_amount = |total_actual_bk - total_akonto_paid| = die Differenz.""",

    "invoice": """\
Extrahiere diese Rechnung. NUR JSON:
{
  "invoice_type": "thermenwartung|reparatur|hausverwaltung|handwerker|dienstleistung|other",
  "issuer": "Rechnungssteller",
  "recipient": "Rechnungsempfänger",
  "invoice_number": "Rechnungsnummer",
  "amount_brutto": Bruttobetrag,
  "amount_netto": Nettobetrag_OHNE_USt,
  "vat_amount": USt_Betrag_oder_null,
  "vat_rate": USt_Satz_in_Prozent,
  "date": "YYYY-MM-DD",
  "description": "Kurze Beschreibung der Leistung",
  "property_address": "Leistungsort/Objekt falls angegeben",
  "related_property": "Adresse der verwalteten/reparierten Immobilie falls erkennbar (auch indirekt)"
}
WICHTIG: amount_netto MUSS der Betrag OHNE Umsatzsteuer sein.""",

    "grundsteuerbescheid": """\
Extrahiere den Grundsteuerbescheid. NUR JSON:
{
  "annual_tax": Jahresbetrag_Grundsteuer,
  "quarterly_payment": Vierteljährlicher_Betrag_oder_null,
  "property_address": "Liegenschaft Adresse",
  "owner_name": "Eigentümer",
  "steuernummer": "Steuernummer oder null",
  "assessment_year": Jahr
}
WICHTIG: annual_tax ist der JAHRESBETRAG.""",

    "svs_vorschreibung": """\
Extrahiere diese SVS-Beitragsvorschreibung. NUR JSON:
{
  "svs_nummer": "SVS-Nummer",
  "beitragsjahr": Jahr_als_Zahl,
  "quarter": "Q1|Q2|Q3|Q4",
  "beitragsgrundlage": Beitragsgrundlage_als_Zahl,
  "quarterly_total": Quartalsbeitrag_Gesamt,
  "pensionsversicherung": PV_Betrag,
  "krankenversicherung": KV_Betrag,
  "unfallversicherung": UV_Betrag,
  "selbstaendigenvorsorge": SV_Betrag_oder_null,
  "faellig_am": "YYYY-MM-DD"
}""",

    "svs_nachbemessung": """\
Extrahiere diese SVS-Nachbemessung. NUR JSON:
{
  "svs_nummer": "SVS-Nummer",
  "beitragsjahr": Jahr_als_Zahl,
  "settlement_type": "nachforderung|gutschrift",
  "settlement_amount": Differenz_Betrag_als_Zahl,
  "vorlaeufige_beitragsgrundlage": vorlaeufige_BG,
  "endgueltige_beitragsgrundlage": endgueltige_BG,
  "vorlaeufige_beitraege": vorlaeufig_gezahlte_Beitraege,
  "endgueltige_beitraege": endgueltige_Beitraege,
  "faellig_am": "YYYY-MM-DD"
}
WICHTIG: settlement_amount ist die DIFFERENZ (endgueltig - vorlaeufig).""",

    "svs_jahresbestaetigung": """\
Extrahiere diese SVS-Jahresbestaetigung. NUR JSON:
{
  "svs_nummer": "SVS-Nummer",
  "beitragsjahr": Jahr_als_Zahl,
  "total_annual": Gesamtbetrag_Jahresbeitraege,
  "pensionsversicherung": PV_Jahresbetrag,
  "krankenversicherung": KV_Jahresbetrag,
  "unfallversicherung": UV_Jahresbetrag,
  "selbstaendigenvorsorge": SV_Jahresbetrag_oder_null
}""",

    "loan_contract": """\
Extrahiere diesen Kreditvertrag. NUR JSON:
{
  "loan_type": "hypothekarkredit|betriebsmittelkredit|familiendarlehen|other",
  "lender_name": "Kreditgeber / Bank",
  "borrower_name": "Kreditnehmer",
  "contract_number": "Vertragsnummer / Kontonummer",
  "loan_amount": Kreditbetrag_als_Zahl,
  "interest_rate": Zinssatz_in_Prozent,
  "monthly_payment": Monatsrate,
  "term_months": Laufzeit_in_Monaten,
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD oder null",
  "property_address": "Sicherheit-Immobilie Adresse oder null",
  "is_tax_relevant": true_oder_false
}""",

    "zinsbescheinigung": """\
Extrahiere diese Zinsbescheinigung / Zinsbestätigung. NUR JSON:
{
  "contract_number": "Kreditnummer / Vertragsnummer / Kontonummer",
  "lender_name": "Bank / Kreditgeber",
  "borrower_name": "Kreditnehmer",
  "tax_year": Steuerjahr_als_Zahl,
  "annual_interest_paid": Gezahlte_Zinsen_im_Jahr_als_Zahl,
  "annual_principal_paid": Gezahlte_Tilgung_im_Jahr_als_Zahl,
  "remaining_balance": Kapitalstand_am_Jahresende_als_Zahl,
  "original_loan_amount": Urspruenglicher_Kreditbetrag_als_Zahl,
  "interest_rate": Zinssatz_in_Prozent,
  "monthly_payment": Monatsrate_als_Zahl,
  "loan_type": "hypothekarkredit|betriebsmittelkredit|familiendarlehen|other",
  "property_address": "Immobilie Adresse oder null",
  "tax_deductible_category": "E1b Finanzierungskosten|E1a Betriebsausgabe|Sonderausgabe|null"
}
Betraege als Dezimalzahlen (1029.03). null wenn nicht gefunden.""",
}


class AIFirstClassifier:
    """
    AI-first document classification and extraction.

    Usage:
        classifier = AIFirstClassifier(llm_client)
        result = classifier.classify_and_extract(raw_text)
        # result = {"document_type": ..., "confidence": ..., ...}

        # Optional round 2 for deeper extraction:
        deep = classifier.deep_extract(raw_text, result["document_type"])
    """

    def __init__(self, llm_generate_fn=None):
        """
        Args:
            llm_generate_fn: callable(system_prompt, user_prompt, max_tokens) -> str
                If None, uses Groq via environment variable.
        """
        self._generate = llm_generate_fn or self._default_groq_generate
        self._groq_client = None

    def _default_groq_generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
        """Default LLM backend — tries Groq first, falls back to OpenAI."""
        import os
        from dotenv import load_dotenv
        load_dotenv()

        # Try Groq first (faster, cheaper) — with key rotation for rate limits
        groq_keys = [k for k in [
            os.getenv("GROQ_API_KEY"),
            os.getenv("GROQ_API_KEY_2"),
        ] if k]
        if not hasattr(self, "_groq_key_index"):
            self._groq_key_index = 0

        for _key_attempt in range(len(groq_keys) or 1):
            if not groq_keys:
                break
            key_idx = (self._groq_key_index + _key_attempt) % len(groq_keys)
            groq_key = groq_keys[key_idx]
            try:
                from groq import Groq
                client = Groq(api_key=groq_key, timeout=60.0)
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0,
                )
                # Rotate key for next call to spread load
                self._groq_key_index = (key_idx + 1) % len(groq_keys)
                return resp.choices[0].message.content
            except ImportError:
                break
            except Exception as e:
                logger.info("Groq key %d failed (%s), trying next key", key_idx, e)
                continue

        # All Groq keys failed or none available

        # Fallback to OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import openai
                client = openai.OpenAI(api_key=openai_key)
                logger.info("Falling back to OpenAI (gpt-4o-mini) after Groq failure")
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0,
                )
                return resp.choices[0].message.content
            except Exception as openai_err:
                logger.error("OpenAI fallback also failed: %s", openai_err)

        # Fallback to Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=anthropic_key)
                logger.info("Falling back to Anthropic (claude-sonnet) after Groq+OpenAI failure")
                resp = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return resp.content[0].text
            except Exception as anthropic_err:
                logger.error("Anthropic fallback also failed: %s", anthropic_err)

        raise RuntimeError("No LLM API available (all Groq keys + OpenAI + Anthropic failed)")

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        if not text:
            return {}
        # Try markdown code block first
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # Try direct JSON
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    # ── Round 1: Classify + extract core fields ──────────────────────

    def classify_and_extract(
        self, raw_text: str, max_chars: int = 4000,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Round 1: Single LLM call to classify document type AND extract core fields.

        Args:
            raw_text: OCR-extracted text from the document.
            max_chars: Maximum characters to send to LLM.
            user_context: Optional dict with user info to help AI make correct
                tax decisions. Keys: name, role_hints (list of known roles like
                "tenant at Landstrasse", "landlord at Praterstrasse"),
                known_properties (list of property addresses with is_rental flag).

        Returns dict with document_type, confidence, subtype, amounts, role, etc.
        """
        if not raw_text or len(raw_text.strip()) < 20:
            return {"document_type": "unknown", "confidence": 0.0}

        text = raw_text[:max_chars]

        # Build user context string for the prompt
        context_str = ""
        if user_context:
            parts = []
            if user_context.get("name"):
                parts.append(f"Benutzer: {user_context['name']}")
            if user_context.get("role_hints"):
                parts.append("Bekannte Rollen: " + ", ".join(user_context["role_hints"]))
            if user_context.get("known_properties"):
                props = user_context["known_properties"]
                parts.append("Immobilien: " + ", ".join(
                    f"{p['address']} ({'vermietet' if p.get('is_rental') else 'eigen'})"
                    for p in props
                ))
            if parts:
                context_str = "\n\nBENUTZER-KONTEXT:\n" + "\n".join(parts) + "\n"

        try:
            response = self._generate(
                ROUND1_SYSTEM_PROMPT,
                ROUND1_USER_TEMPLATE.format(text=text) + context_str,
                max_tokens=800,
            )
            result = self._parse_json(response)
            if not result.get("document_type"):
                result["document_type"] = "unknown"
            return result
        except Exception as e:
            logger.warning("AI-first classify failed: %s", e)
            return {"document_type": "unknown", "confidence": 0.0, "error": str(e)}

    # ── Round 2: Type-specific deep extraction ───────────────────────

    def deep_extract(self, raw_text: str, document_type: str, max_chars: int = 4000) -> Dict[str, Any]:
        """
        Round 2: Type-specific extraction for detailed fields.

        Only called when Round 1 identified a type that needs deeper extraction.
        """
        prompt = ROUND2_PROMPTS.get(document_type)
        if not prompt:
            return {}

        text = raw_text[:max_chars]
        try:
            response = self._generate(
                "Du bist ein Experte für österreichische Dokumente. Extrahiere die Felder exakt.",
                f"{prompt}\n\nDokument:\n{text}",
                max_tokens=600,
            )
            return self._parse_json(response)
        except Exception as e:
            logger.warning("AI-first deep extract failed for %s: %s", document_type, e)
            return {}

    # ── Convenience: full two-round pipeline ─────────────────────────

    def full_pipeline(self, raw_text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Run both rounds. Returns (round1_result, round2_result).

        Round 2 is only triggered for types that have a deep extraction prompt.
        """
        r1 = self.classify_and_extract(raw_text)
        doc_type = r1.get("document_type", "unknown")

        # Determine if Round 2 is needed
        r2 = {}
        if doc_type in ROUND2_PROMPTS:
            r2 = self.deep_extract(raw_text, doc_type)
        elif doc_type in (
            "versicherung_kuendigung", "versicherung_praemienaenderung",
            "versicherung_jahresbestaetigung",
        ):
            r2 = self.deep_extract(raw_text, "versicherungspolizze")
        elif doc_type in ("sepa_lastschrift",) and "SVS" in raw_text[:500]:
            r2 = self.deep_extract(raw_text, "svs_vorschreibung")

        return r1, r2
