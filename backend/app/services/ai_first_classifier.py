"""
AI-First Document Classifier & Extractor.

Two-step strategy:
  Step 1: Classify document type (lightweight, high accuracy)
  Step 2: Extract type-specific fields (targeted, comprehensive)

User context (name, roles, properties) is injected into both steps
so the AI can determine direction (income vs expense) and property routing.
"""
import json
import logging
import os
import re
from typing import Optional, Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Step 1: Classification prompt — ONLY asks for document type
# ──────────────────────────────────────────────────────────────────────

STEP1_SYSTEM = """\
Du bist ein Experte für österreichische Steuer- und Finanzdokumente.
Bestimme den Dokumenttyp und was im Steuersystem angelegt werden soll.
Antworte NUR als JSON.

Typen:
- mietvertrag: Mietvertrag
- mietvorschreibung: Monatliche Mietzinsvorschreibung
- betriebskostenabrechnung: BK-Jahresabrechnung (Nachforderung/Guthaben)
- versicherungspolizze: Versicherungspolizze / Prämienvorschreibung
- svs_vorschreibung: SVS Quartals-Beitragsvorschreibung
- svs_nachbemessung: SVS Nachbemessung / Differenzvorschreibung
- invoice: Rechnung / Honorarnote / Ausgangsrechnung
- receipt: Kassenbon / Einkaufsbeleg
- grundsteuerbescheid: Grundsteuerbescheid
- lohnzettel: Lohnzettel / L16 / Jahreslohnzettel
- einkommensteuerbescheid: Einkommensteuerbescheid / ESt-Bescheid
- bank_statement: Kontoauszug
- kaufvertrag: Immobilien-Kaufvertrag
- loan_contract: Kreditvertrag / Darlehensvertrag (neuer Vertrag)
- zinsbescheinigung: Zinsbescheinigung (Jahresübersicht gezahlter Zinsen)
- tilgungsplan: Tilgungsplan / Rückzahlungsplan
- e1_form: Steuerformular E1/E1a/E1b/L1/L1k/U1
- spendenbestaetigung: Spendenbestätigung
- kirchenbeitrag: Kirchenbeitrag / Kirchensteuer
- fahrtenbuch: Fahrtenbuch / Kilometeraufstellung
- homeoffice_nachweis: Homeoffice-Bestätigung / Telearbeit-Nachweis
- studienbescheinigung: Studienbescheinigung / Inskriptionsbestätigung
- pendlerrechner: Pendlerrechner-Ergebnis / Pendlerpauschale-Nachweis
- pensionsbescheid: Pensionsbescheid / Pensionsmitteilung
- crypto_report: Kryptowährungs-Report / Broker-Jahresbericht
- kest_bescheinigung: KESt-Bescheinigung / Kapitalertragsteuer
- asset_purchase: Anlagegut-Kauf (Fahrzeug, Maschine, IT-Hardware >1000 EUR netto)
- other: Keiner der obigen Typen

{
  "document_type": "typ",
  "confidence": 0.0-1.0,
  "creates": ["transaction", "asset", "recurring", "loan", "property", "archive_only"]
}

"creates" bestimmt, was in unserem Steuerverwaltungssystem angelegt werden soll:

- "transaction": Eine einmalige Buchung (Einnahme oder Ausgabe) in der Einnahmen-Ausgaben-Rechnung.
  Erscheint in E1a (§22/§23), E1b (§28 V+V) oder E1 (§25 AN). Beeinflusst Gewinn/Verlust direkt.
  Beispiele: Rechnung bezahlt, SVS-Beitrag, Kirchenbeitrag, Spende, Zinszahlung laut Bescheinigung.

- "asset": Ein Anlagegut wird im Anlageverzeichnis (AV) angelegt und über die Nutzungsdauer
  abgeschrieben (AfA). Erscheint in der Bilanz und als jährliche AfA in E1a.
  WICHTIG: Nur für Wirtschaftsgüter >EUR 1.000 netto mit Nutzungsdauer >1 Jahr.
  Beispiele: Fahrzeuge (PKW, E-Auto, LKW), Maschinen, IT-Hardware >1000 EUR.
  NICHT für GWG ≤1.000 EUR (die sind sofort absetzbar = nur "transaction").
  NICHT für Verbrauchsmaterial (Holz, Büromaterial = nur "transaction").

- "recurring": Eine wiederkehrende Buchung (monatlich/quartalsweise/jährlich) wird angelegt.
  Das System generiert automatisch Einzelbuchungen für jeden Zeitraum.
  Beispiele: Monatliche Miete (Vermieter=Einnahme, Mieter=Ausgabe),
  Versicherungsprämie (jährlich), Werkstattmiete (monatlich).

- "loan": Ein Kredit/Darlehen wird als Verbindlichkeit angelegt.
  Verwaltet Zinsen, Tilgung, Restschuld. Zinsen erscheinen als WK in E1b (Hypothek)
  oder BA in E1a (Betriebsmittelkredit).
  Beispiele: Hypothekarkredit, Betriebsmittelkredit, Familiendarlehen.

- "property": Eine Immobilie wird angelegt mit Kaufpreis, Gebäudewert, AfA-Satz.
  Generiert automatisch die Gebäude-AfA (1,5% p.a.) für E1b.
  Beispiele: Kaufvertrag einer Mietimmobilie, Mietvertrag als Vermieter.

- "archive_only": Dokument wird nur gespeichert, keine Buchung/Anlage.
  Beispiele: Kontoauszug (zur Abstimmung), Tilgungsplan, Übergabeprotokoll,
  Fahrtenbuch (korrigiert nur %), Halbjahresregel-Nachweis.

Mehrfach möglich: Fahrzeugkauf = ["asset", "transaction"]. Mietvertrag VM = ["property", "recurring"]."""

STEP1_USER = "Dokumenttyp bestimmen:\n\n{text}"

# ──────────────────────────────────────────────────────────────────────
# Step 2: Type-specific extraction prompts — comprehensive per type
# ──────────────────────────────────────────────────────────────────────

STEP2_PROMPTS = {
    "invoice": """\
Analysiere diese Rechnung. Antworte NUR als JSON.

ZAHLENFORMAT: Europäisch! "10.800,00" = 10800.00, "1.234,56" = 1234.56.
Gib Beträge mit Punkt als Dezimaltrenner aus.

WICHTIG — Prüfe den BENUTZER-KONTEXT am Ende dieser Nachricht!
Wenn der Benutzer-Name im Dokument als Rechnungssteller/Aussteller/Absender erscheint
→ Das ist eine AUSGANGSRECHNUNG → expense_or_income = "income" (Benutzer bekommt Geld)
Wenn der Benutzer-Name als Empfänger/Kunde/Auftraggeber erscheint
→ Das ist eine EINGANGSRECHNUNG → expense_or_income = "expense" (Benutzer zahlt)
Hinweise: "AR", "Ausgangsrechnung", "Honorarnote" im Titel → immer income.

{
  "expense_or_income": "income wenn Benutzer = Aussteller, expense wenn Benutzer = Empfänger",
  "issuer": "Rechnungssteller / Lieferant",
  "recipient": "Rechnungsempfänger / Kunde",
  "invoice_number": "Rechnungsnummer oder null",
  "amount_brutto": Bruttobetrag als Zahl,
  "amount_netto": Nettobetrag ohne USt als Zahl,
  "vat_amount": USt-Betrag oder null,
  "vat_rate": USt-Satz in Prozent oder null,
  "date": "YYYY-MM-DD",
  "description": "Kurzbeschreibung der Leistung/Ware",
  "property_address": "Immobilienadresse falls erwähnt, sonst null",
  "is_asset_purchase": true wenn Anlagegut (Fahrzeug/Maschine/IT >EUR 1000) gekauft wurde,
  "asset_type": "pkw|e_auto|lkw|maschine|it_hardware|moebel|null",
  "is_deductible": true/false,
  "deduction_category": "Betriebsausgabe|Werbungskosten|Sonderausgaben|null",
  "tax_form": "E1a|E1b|E1|null"
}""",

    "mietvertrag": """\
Analysiere diesen Mietvertrag. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

Bestimme: Ist der BENUTZER Vermieter oder Mieter?

{
  "user_is": "landlord oder tenant",
  "landlord_name": "Vermieter",
  "tenant_name": "Mieter",
  "property_address": "Mietobjekt Adresse",
  "hauptmietzins": Hauptmietzins als Zahl,
  "betriebskosten": BK-Akonto als Zahl,
  "umsatzsteuer": USt-Betrag oder null,
  "gesamtmiete": Gesamtmiete als Zahl,
  "nutzflaeche_m2": Nutzfläche in m² oder null,
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD oder null",
  "kaution": Kaution als Zahl oder null,
  "purchase_price": Kaufpreis falls im Vertrag erwähnt oder null,
  "building_percentage": Gebäudeanteil in % (oft 70%) oder null
}""",

    "mietvorschreibung": """\
Analysiere diese Mietvorschreibung. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "expense_or_income": "income wenn Benutzer=Vermieter, expense wenn Benutzer=Mieter",
  "user_is": "landlord oder tenant",
  "property_address": "Objekt-Adresse",
  "month": Monat 1-12,
  "year": Jahr,
  "hauptmietzins": HM als Zahl oder null,
  "betriebskosten": BK als Zahl oder null,
  "gesamtbetrag": Gesamtbetrag als Zahl,
  "date": "YYYY-MM-DD"
}""",

    "betriebskostenabrechnung": """\
Analysiere diese BK-Abrechnung. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

Bestimme: Ist es eine Nachforderung (Mieter zahlt nach) oder Guthaben (Mieter bekommt zurück)?
Aus Sicht des BENUTZERS: Wenn Benutzer=Vermieter, dann Nachforderung=income, Guthaben=expense.

{
  "settlement_type": "nachforderung oder guthaben",
  "expense_or_income": "income oder expense (aus Sicht des Benutzers)",
  "settlement_amount": Differenzbetrag als Zahl (NUR die Differenz!),
  "abrechnungsjahr": Jahr,
  "property_address": "Objekt-Adresse",
  "date": "YYYY-MM-DD"
}""",

    "versicherungspolizze": """\
Analysiere diese Versicherungspolizze. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "insurer_name": "Versicherungsgesellschaft",
  "polizze_nr": "Polizzennummer oder null",
  "insurance_subtype": "berufshaftpflicht|kfz|rechtsschutz|haushaltsversicherung|gebaeudeversicherung|private_krankenversicherung|unfallversicherung|other",
  "praemie_jaehrlich": Jahresprämie als Zahl,
  "zahlungsfrequenz": "monatlich|vierteljaehrlich|halbjaehrlich|jaehrlich",
  "vertragsbeginn": "YYYY-MM-DD",
  "versichertes_objekt": "Adresse/Kennzeichen/Beschreibung oder null",
  "property_address": "Immobilienadresse falls Gebäudeversicherung, sonst null",
  "expense_or_income": "expense",
  "is_deductible": true/false,
  "deduction_category": "Betriebsausgabe|Werbungskosten|null",
  "tax_form": "E1a|E1b|null",
  "deductible_percentage": 100 oder Teilbetrag in Prozent falls nur teilweise absetzbar
}""",

    "svs_vorschreibung": """\
Analysiere diese SVS-Beitragsvorschreibung. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "svs_nummer": "SVS-Nummer",
  "beitragsjahr": Jahr als Zahl,
  "quarter": "Q1|Q2|Q3|Q4",
  "beitragsgrundlage": Beitragsgrundlage als Zahl,
  "quarterly_amount": Quartalsbeitrag GESAMT als Zahl,
  "annual_amount": Jahresbeitrag als Zahl oder null,
  "pensionsversicherung": PV-Betrag oder null,
  "krankenversicherung": KV-Betrag oder null,
  "unfallversicherung": UV-Betrag oder null,
  "date": "YYYY-MM-DD",
  "expense_or_income": "expense",
  "tax_form": "E1a"
}""",

    "svs_nachbemessung": """\
Analysiere diese SVS-Nachbemessung. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "svs_nummer": "SVS-Nummer",
  "beitragsjahr": Jahr als Zahl,
  "settlement_type": "nachforderung|gutschrift",
  "settlement_amount": Differenzbetrag als Zahl,
  "date": "YYYY-MM-DD",
  "expense_or_income": "expense bei Nachforderung, income bei Gutschrift",
  "tax_form": "E1a"
}""",

    "grundsteuerbescheid": """\
Analysiere diesen Grundsteuerbescheid. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "annual_tax": Jahresbetrag als Zahl,
  "property_address": "Liegenschaft-Adresse",
  "owner_name": "Eigentümer",
  "date": "YYYY-MM-DD",
  "expense_or_income": "expense",
  "tax_form": "E1b"
}""",

    "lohnzettel": """\
Analysiere diesen Lohnzettel / L16. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "employer_name": "Arbeitgeber",
  "employee_name": "Arbeitnehmer",
  "brutto_jahresgehalt": Brutto-Jahresgehalt als Zahl,
  "lohnsteuer": Einbehaltene Lohnsteuer als Zahl,
  "sozialversicherung": SV-Beiträge als Zahl oder null,
  "tax_year": Steuerjahr als Zahl,
  "date": "YYYY-MM-DD",
  "expense_or_income": "income",
  "tax_form": "E1"
}""",

    "zinsbescheinigung": """\
Analysiere diese Zinsbescheinigung. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

Eine Zinsbescheinigung bescheinigt die vom Kreditnehmer im Jahr GEZAHLTEN Zinsen.
Das ist eine AUSGABE des Benutzers (expense), keine Einnahme!

{
  "lender_name": "Bank / Kreditgeber",
  "contract_number": "Kreditnummer / Kontonummer",
  "tax_year": Steuerjahr als Zahl,
  "annual_interest_paid": Gezahlte Zinsen im Jahr als Zahl,
  "remaining_balance": Restschuld am Jahresende oder null,
  "loan_type": "hypothekarkredit|betriebsmittelkredit|familiendarlehen|other",
  "property_address": "Immobilienadresse falls Hypothek, sonst null",
  "date": "YYYY-MM-DD",
  "expense_or_income": "expense",
  "is_deductible": true,
  "tax_form": "E1b bei Hypothek, E1a bei Betriebsmittelkredit"
}""",

    "loan_contract": """\
Analysiere diesen Kreditvertrag. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "lender_name": "Kreditgeber / Bank",
  "borrower_name": "Kreditnehmer",
  "contract_number": "Vertragsnummer",
  "loan_amount": Kreditbetrag als Zahl,
  "interest_rate": Zinssatz in Prozent,
  "monthly_payment": Monatsrate oder null,
  "loan_type": "hypothekarkredit|betriebsmittelkredit|familiendarlehen|other",
  "property_address": "Sicherheiten-Immobilie oder null",
  "start_date": "YYYY-MM-DD",
  "expense_or_income": "archive_only"
}""",

    "einkommensteuerbescheid": """\
Analysiere diesen Einkommensteuerbescheid. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "tax_year": Steuerjahr als Zahl,
  "festgesetzte_est": Festgesetzte ESt als Zahl,
  "verlustvortrag": Verlustvortrag als Zahl oder null,
  "nachzahlung": Nachzahlung als Zahl oder null,
  "gutschrift": Gutschrift als Zahl oder null,
  "date": "YYYY-MM-DD",
  "expense_or_income": "archive_only"
}""",

    "spendenbestaetigung": """\
Analysiere diese Spendenbestätigung. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "recipient_org": "Spendenempfänger-Organisation",
  "amount": Spendenbetrag als Zahl,
  "date": "YYYY-MM-DD",
  "tax_year": Steuerjahr oder null,
  "expense_or_income": "expense",
  "is_deductible": true,
  "deduction_category": "Sonderausgaben",
  "tax_form": "E1"
}""",

    "kirchenbeitrag": """\
Analysiere diesen Kirchenbeitrag. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "parish": "Pfarrgemeinde / Diözese",
  "amount": Jahresbeitrag als Zahl,
  "tax_year": Steuerjahr als Zahl,
  "date": "YYYY-MM-DD",
  "expense_or_income": "expense",
  "is_deductible": true,
  "deduction_category": "Sonderausgaben",
  "tax_form": "E1"
}""",

    "asset_purchase": """\
Analysiere diesen Anlagegut-Kauf. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "asset_type": "pkw|e_auto|lkw|fiskal_lkw|maschine|it_hardware|moebel|other",
  "description": "Beschreibung des Wirtschaftsguts",
  "purchase_price_brutto": Bruttokaufpreis als Zahl,
  "purchase_price_netto": Nettokaufpreis als Zahl,
  "vat_amount": USt-Betrag oder null,
  "vat_rate": USt-Satz oder null,
  "purchase_date": "YYYY-MM-DD",
  "supplier": "Verkäufer / Händler",
  "is_gwg": true wenn Nettobetrag <= 1000 EUR,
  "useful_life_years": Geschätzte Nutzungsdauer in Jahren oder null,
  "business_use_percentage": Betriebliche Nutzung in % oder 100,
  "expense_or_income": "expense",
  "tax_form": "E1a"
}""",

    "e1_form": """\
Analysiere dieses Steuerformular. Antworte NUR als JSON.

{
  "form_type": "E1|E1a|E1b|L1|L1k|U1|U30",
  "tax_year": Steuerjahr als Zahl,
  "key_values": {},
  "expense_or_income": "archive_only"
}""",

    "other": """\
Analysiere dieses Dokument. Antworte NUR als JSON.
ZAHLENFORMAT: "1.234,56" = 1234.56.

{
  "description": "Kurzbeschreibung des Dokuments",
  "amount": Hauptbetrag als Zahl oder null,
  "date": "YYYY-MM-DD oder null",
  "expense_or_income": "expense|income|archive_only|null"
}""",
}

# Fallback for types without specific prompt
for _t in ["fahrtenbuch", "homeoffice_nachweis", "studienbescheinigung",
           "pendlerrechner", "pensionsbescheid", "crypto_report",
           "kest_bescheinigung", "bank_statement", "tilgungsplan", "receipt"]:
    if _t not in STEP2_PROMPTS:
        STEP2_PROMPTS[_t] = STEP2_PROMPTS["other"]


class AIFirstClassifier:
    """
    Two-step AI document classifier:
      Step 1: classify_type() — determine document type
      Step 2: extract_fields() — extract type-specific fields
    """

    def __init__(self, llm_generate_fn=None):
        self._generate = llm_generate_fn or self._default_groq_generate
        self._groq_client = None

    def _default_groq_generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
        """LLM backend — Groq (gpt-oss-120b) → OpenAI fallback → Anthropic fallback."""
        load_dotenv()

        # Try Groq with key rotation
        groq_keys = [k for k in [
            os.getenv("GROQ_API_KEY"),
            os.getenv("GROQ_API_KEY_2"),
        ] if k]
        if not hasattr(self, "_groq_key_index"):
            self._groq_key_index = 0

        import time as _time
        # Retry with backoff — Groq rate limits cause empty responses under concurrency
        for _retry in range(3):
            for _key_attempt in range(len(groq_keys) or 1):
                if not groq_keys:
                    break
                key_idx = (self._groq_key_index + _key_attempt) % len(groq_keys)
                groq_key = groq_keys[key_idx]
                try:
                    from groq import Groq
                    client = Groq(api_key=groq_key, timeout=60.0)
                    resp = client.chat.completions.create(
                        model="openai/gpt-oss-20b",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=max_tokens,
                        temperature=0,
                    )
                    self._groq_key_index = (key_idx + 1) % len(groq_keys)
                    content = resp.choices[0].message.content
                    if content and content.strip():
                        return content
                    # Log the full response for debugging
                    finish = resp.choices[0].finish_reason if resp.choices else "no_choices"
                    usage = getattr(resp, "usage", None)
                    logger.warning(
                        "Groq gpt-oss-120b empty response: finish=%s, usage=%s, content=%r",
                        finish, usage, content,
                    )
                except ImportError:
                    break
                except Exception as e:
                    logger.info("Groq key %d failed (%s)", key_idx, e)
            # Wait before retry (rate limit backoff)
            if _retry < 2:
                _time.sleep(2 * (_retry + 1))

        # Fallback to OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import openai
                client = openai.OpenAI(api_key=openai_key)
                logger.info("Falling back to OpenAI gpt-4o-mini")
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
            except Exception as e:
                logger.error("OpenAI fallback failed: %s", e)

        # Fallback to Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=anthropic_key)
                logger.info("Falling back to Anthropic claude-sonnet")
                resp = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return resp.content[0].text
            except Exception as e:
                logger.error("Anthropic fallback failed: %s", e)

        return ""

    def _parse_json(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    def _build_context_str(self, user_context: Optional[Dict[str, Any]]) -> str:
        if not user_context:
            return ""
        parts = []
        if user_context.get("name"):
            parts.append(f"Benutzer: {user_context['name']}")
        if user_context.get("role_hints"):
            parts.append("Rollen: " + ", ".join(user_context["role_hints"]))
        if user_context.get("known_properties"):
            props = user_context["known_properties"]
            parts.append("Immobilien: " + ", ".join(
                f"{p['address']} ({'vermietet' if p.get('is_rental') else 'eigen'})"
                for p in props
            ))
        if parts:
            return "\n\nBENUTZER-KONTEXT:\n" + "\n".join(parts) + "\n"
        return ""

    # ── Step 1: Classify type ──────────────────────────────────────

    def classify_type(self, raw_text: str, max_chars: int = 3000,
                      user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Step 1: Determine document type. Fast, lightweight."""
        if not raw_text or len(raw_text.strip()) < 20:
            return {"document_type": "unknown", "confidence": 0.0}

        text = raw_text[:max_chars]
        context_str = self._build_context_str(user_context)

        try:
            response = self._generate(
                STEP1_SYSTEM,
                STEP1_USER.format(text=text) + context_str,
                max_tokens=1024,
            )
            result = self._parse_json(response)
            if not result.get("document_type"):
                result["document_type"] = "unknown"
            return result
        except Exception as e:
            logger.warning("Step 1 classify failed: %s", e)
            return {"document_type": "unknown", "confidence": 0.0}

    # ── Step 2: Extract fields ─────────────────────────────────────

    def extract_fields(self, raw_text: str, document_type: str,
                       max_chars: int = 6000,
                       user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Step 2: Extract type-specific fields. Comprehensive."""
        prompt = STEP2_PROMPTS.get(document_type, STEP2_PROMPTS.get("other", ""))
        if not prompt:
            return {}

        text = raw_text[:max_chars]
        context_str = self._build_context_str(user_context)

        try:
            step2_system = (
                "Du bist ein Experte für österreichische Steuer- und Finanzdokumente. "
                "Extrahiere die Felder exakt aus dem Dokument.\n\n"
                "ZAHLENFORMAT: Europäisch! '10.800,00' = 10800.00, '1.234,56' = 1234.56. "
                "Gib Beträge mit Punkt als Dezimaltrenner aus.\n\n"
                "STEUERLICHE EINORDNUNG anhand des BENUTZER-KONTEXT:\n"
                "- Selbständig (§22/§23): Ausgaben sind 'Betriebsausgabe', tax_form='E1a'\n"
                "- Arbeitnehmer (§25): Ausgaben sind 'Werbungskosten', tax_form='E1'\n"
                "- Vermieter (§28): Immobilien-bezogene Ausgaben sind 'Werbungskosten', tax_form='E1b'\n"
                "- expense_or_income: Bestimme aus Sicht des BENUTZERS "
                "(Ausgangsrechnung = income, Eingangsrechnung = expense, "
                "Zinsbescheinigung = expense, Versicherung = expense)\n"
                "- Wenn der Benutzer-Name als Aussteller/Lieferant im Dokument steht → income\n"
                "- Wenn der Benutzer-Name als Empfänger/Kunde steht → expense"
            )
            response = self._generate(
                step2_system,
                prompt + "\n\nDokument:\n" + text + context_str,
                max_tokens=800,
            )
            return self._parse_json(response)
        except Exception as e:
            logger.warning("Step 2 extract failed for %s: %s", document_type, e)
            return {}

    # ── Combined: classify + extract (replaces old classify_and_extract) ──

    def classify_and_extract(
        self, raw_text: str, max_chars: int = 6000,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Two-step: classify type, then extract fields.
        Returns merged result compatible with old format.
        """
        # Step 1: classify
        step1 = self.classify_type(raw_text, max_chars=min(max_chars, 3000),
                                   user_context=user_context)
        doc_type = step1.get("document_type", "unknown")
        confidence = step1.get("confidence", 0.0)

        if doc_type == "unknown":
            return {"document_type": "unknown", "confidence": 0.0}

        # Step 2: extract
        step2 = self.extract_fields(raw_text, doc_type, max_chars=max_chars,
                                    user_context=user_context)

        # Merge into unified format (backward compatible with old _ai_first)
        creates = step1.get("creates", [])
        if isinstance(creates, str):
            creates = [creates]

        result = {
            "document_type": doc_type,
            "confidence": confidence,
            "creates": creates,
            "document_subtype": step2.get("insurance_subtype") or step2.get("settlement_type")
                               or step2.get("loan_type") or step2.get("asset_type"),
            "document_purpose": step2.get("document_purpose"),
            "role_detection": {
                "landlord_name": step2.get("landlord_name"),
                "tenant_name": step2.get("tenant_name"),
                "user_is": step2.get("user_is"),
            },
            "amounts": {
                "total_amount": step2.get("amount_brutto") or step2.get("purchase_price_brutto")
                               or step2.get("gesamtbetrag") or step2.get("amount")
                               or step2.get("brutto_jahresgehalt") or step2.get("settlement_amount"),
                "annual_amount": step2.get("amount_netto") or step2.get("praemie_jaehrlich")
                                or step2.get("annual_tax") or step2.get("annual_interest_paid")
                                or step2.get("annual_amount") or step2.get("purchase_price_netto"),
                "monthly_amount": step2.get("monthly_amount") or step2.get("gesamtmiete"),
                "settlement_amount": step2.get("settlement_amount"),
                "new_amount": step2.get("new_amount"),
            },
            "key_fields": {
                "polizze_nr": step2.get("polizze_nr"),
                "insurer_name": step2.get("insurer_name"),
                "property_address": step2.get("property_address") or step2.get("related_property"),
                "date": step2.get("date") or step2.get("purchase_date"),
                "month": step2.get("month"),
                "year": step2.get("year") or step2.get("tax_year") or step2.get("beitragsjahr")
                        or step2.get("abrechnungsjahr"),
                "invoice_number": step2.get("invoice_number"),
                "insured_object": step2.get("versichertes_objekt"),
                "svs_nummer": step2.get("svs_nummer"),
                "beitragsjahr": step2.get("beitragsjahr"),
                "quarter": step2.get("quarter"),
                "beitragsgrundlage": step2.get("beitragsgrundlage"),
                "quarterly_amount": step2.get("quarterly_amount"),
                "nachforderung_amount": step2.get("nachforderung_amount"),
                "gutschrift_amount": step2.get("gutschrift_amount"),
                "contract_number": step2.get("contract_number"),
                "interest_rate": step2.get("interest_rate"),
                "monthly_payment": step2.get("monthly_payment"),
                "loan_amount": step2.get("loan_amount"),
                "lender_name": step2.get("lender_name"),
                # New fields from step 2
                "employer_name": step2.get("employer_name"),
                "brutto_jahresgehalt": step2.get("brutto_jahresgehalt"),
                "lohnsteuer": step2.get("lohnsteuer"),
                "verlustvortrag": step2.get("verlustvortrag"),
                "is_asset_purchase": step2.get("is_asset_purchase"),
                "asset_type": step2.get("asset_type"),
                "is_gwg": step2.get("is_gwg"),
                "useful_life_years": step2.get("useful_life_years"),
                "business_use_percentage": step2.get("business_use_percentage"),
                "deductible_percentage": step2.get("deductible_percentage"),
            },
            "tax_treatment": {
                "is_deductible": step2.get("is_deductible"),
                "deduction_category": step2.get("deduction_category"),
                "tax_form": step2.get("tax_form"),
                "expense_or_income": step2.get("expense_or_income"),
            },
        }

        return result

    # ── Backward compatibility ─────────────────────────────────────

    def deep_extract(self, raw_text: str, document_type: str,
                     max_chars: int = 6000) -> Dict[str, Any]:
        """Backward compatible: calls extract_fields."""
        return self.extract_fields(raw_text, document_type, max_chars=max_chars)
