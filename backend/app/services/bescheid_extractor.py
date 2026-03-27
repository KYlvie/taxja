"""
Einkommensteuerbescheid (Annual Income Tax Assessment) Extractor

Parses OCR text from Austrian Steuerberechnung documents and extracts
structured tax data including income, deductions, tax amounts, and refund info.

Reference document structure:
- Header: Name, Finanzamt, Steuernummer, tax year
- Voraussichtlicher Einkommensteuerbescheid section
- Berechnung der Einkommensteuer section
- Steuer vor/nach Abzug der Absetzbetraege
- Abgabengutschrift / Abgabennachforderung
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class BescheidData:
    """Structured data from an Einkommensteuerbescheid"""
    # Header
    tax_year: Optional[int] = None
    taxpayer_name: Optional[str] = None
    finanzamt: Optional[str] = None
    steuernummer: Optional[str] = None
    aktenzahl: Optional[str] = None
    bescheid_datum: Optional[str] = None
    faellig_am: Optional[str] = None

    # Family info from header
    anzahl_kinder: Optional[int] = None
    verkehrsabsetzbetrag: Optional[bool] = None
    alleinverdiener: Optional[bool] = None
    alleinerzieher: Optional[bool] = None
    pendlerpauschale: Optional[bool] = None

    # Festgesetzte Einkommensteuer (final assessed tax)
    festgesetzte_einkommensteuer: Optional[Decimal] = None

    # Abgabengutschrift (tax refund) or Abgabennachforderung (tax due)
    abgabengutschrift: Optional[Decimal] = None
    abgabennachforderung: Optional[Decimal] = None

    # Einkommen (total income)
    einkommen: Optional[Decimal] = None
    gesamtbetrag_einkuenfte: Optional[Decimal] = None

    # Income by type (Einkunftsarten)
    einkuenfte_nichtselbstaendig: Optional[Decimal] = None  # KZ 245
    einkuenfte_selbstaendig: Optional[Decimal] = None
    einkuenfte_gewerbebetrieb: Optional[Decimal] = None
    einkuenfte_vermietung: Optional[Decimal] = None  # V+V
    einkuenfte_kapital: Optional[Decimal] = None
    sonstige_einkuenfte: Optional[Decimal] = None

    # Employment details
    employer_name: Optional[str] = None
    stpfl_bezuege: Optional[Decimal] = None  # steuerpflichtige Bezuege (KZ 245)

    # Deductions
    werbungskosten_pauschale: Optional[Decimal] = None
    pendlerpauschale_betrag: Optional[Decimal] = None
    telearbeitspauschale: Optional[Decimal] = None
    sonderausgaben: Optional[Decimal] = None

    # Tax calculation
    steuer_vor_absetzbetraege: Optional[Decimal] = None
    verkehrsabsetzbetrag_betrag: Optional[Decimal] = None
    steuer_nach_absetzbetraege: Optional[Decimal] = None
    anrechenbare_lohnsteuer: Optional[Decimal] = None
    erstattung_sv_beitraege: Optional[Decimal] = None
    negativsteuer: Optional[Decimal] = None

    # V+V details (Vermietung und Verpachtung)
    vermietung_details: List[Dict[str, Any]] = field(default_factory=list)

    # Raw confidence
    confidence: float = 0.0


class BescheidExtractor:
    """Extract structured data from Einkommensteuerbescheid OCR text"""

    def extract(self, text: str) -> BescheidData:
        """Main extraction method"""
        data = BescheidData()

        data.tax_year = self._extract_tax_year(text)
        data.taxpayer_name = self._extract_taxpayer_name(text)
        data.finanzamt = self._extract_finanzamt(text)
        data.steuernummer = self._extract_steuernummer(text)
        data.aktenzahl = self._extract_aktenzahl(text)
        data.bescheid_datum = self._extract_bescheid_datum(text)
        data.faellig_am = self._extract_faellig_am(text)

        self._extract_header_flags(text, data)
        self._extract_festgesetzte_steuer(text, data)
        self._extract_gutschrift_nachforderung(text, data)
        self._extract_einkommen(text, data)
        self._extract_employment_details(text, data)
        self._extract_vermietung(text, data)
        self._extract_deductions(text, data)
        self._extract_tax_calculation(text, data)
        self._extract_modern_bescheid_layout(text, data)

        data.confidence = self._calculate_confidence(data)
        return data

    def to_dict(self, data: BescheidData) -> Dict[str, Any]:
        """Convert BescheidData to dictionary for storage"""
        result = {}
        for key, value in data.__dict__.items():
            if value is None:
                result[key] = None
            elif isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, list):
                result[key] = [
                    {k: float(v) if isinstance(v, Decimal) else v for k, v in item.items()}
                    for item in value
                ]
            else:
                result[key] = value
        return result

    # --- Header extraction ---

    def _extract_tax_year(self, text: str) -> Optional[int]:
        # "Steuerberechnung fuer 2023" or "Steuerberechnung für 2023"
        m = re.search(r"steuerberechnung\s+f.{1,2}r\s+(\d{4})", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        # "EINKOMMENSTEUERBESCHEID 2023"
        m = re.search(r"einkommensteuerbescheid\s+(\d{4})", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        # "Das Einkommen im Jahr 2023"
        m = re.search(r"einkommen\s+im\s+jahr\s+(\d{4})", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return None

    def _extract_taxpayer_name(self, text: str) -> Optional[str]:
        # Name is typically at the top, before "FA:" line
        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Look for a name-like line before FA: or St.Nr.
            if i < 10 and stripped and not stripped.startswith(("FA", "St.", "Steuer", "Einkom")):
                # Check next lines for FA: pattern
                for j in range(i + 1, min(i + 4, len(lines))):
                    if re.search(r"FA[:\s]", lines[j]):
                        return stripped
        return None

    def _extract_finanzamt(self, text: str) -> Optional[str]:
        m = re.search(r"FA[:\s]+(.+?)(?:\n|$)", text)
        if m:
            return m.group(1).strip()
        return None

    def _extract_steuernummer(self, text: str) -> Optional[str]:
        m = re.search(r"St\.?\s*Nr\.?[:\s]*(\d[\d\s/]+\d)", text)
        if m:
            return m.group(1).strip()
        return None

    def _extract_aktenzahl(self, text: str) -> Optional[str]:
        m = re.search(
            r"Aktenzahl[:\s]+([A-Z]{1,4}-\d{2,9}/\d{4})",
            text,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()
        return None

    def _extract_bescheid_datum(self, text: str) -> Optional[str]:
        m = re.search(
            r"bescheid[\s-]*datum[:\s]+(\d{1,2}\.\d{1,2}\.\d{4})",
            text,
            re.IGNORECASE,
        )
        if m:
            return m.group(1)
        return None

    def _extract_faellig_am(self, text: str) -> Optional[str]:
        m = re.search(
            r"f.{1,2}llig\s+am[:\s]+(\d{1,2}\.\d{1,2}\.\d{4})",
            text,
            re.IGNORECASE,
        )
        if m:
            return m.group(1)
        return None

    def _extract_header_flags(self, text: str, data: BescheidData) -> None:
        """Extract Ja/Nein flags from header table"""
        text_lower = text.lower()

        # Verkehrsabsetzbetrag
        m = re.search(r"verkehrsabsetzbetrag\s+(ja|nein)", text_lower)
        if m:
            data.verkehrsabsetzbetrag = m.group(1) == "ja"

        # Alleinverdienerabsetzbetrag
        m = re.search(r"alleinverdienerabsetzbetrag\s+(ja|nein)", text_lower)
        if m:
            data.alleinverdiener = m.group(1) == "ja"

        # Alleinerzieherabsetzbetrag
        m = re.search(r"alleinerzieherabsetzbetrag\s+(ja|nein)", text_lower)
        if m:
            data.alleinerzieher = m.group(1) == "ja"

        # Anzahl der Kinder
        m = re.search(r"anzahl\s+der\s+kinder\s+(\d+)", text_lower)
        if m:
            data.anzahl_kinder = int(m.group(1))

    # --- Tax amounts ---

    def _extract_festgesetzte_steuer(self, text: str, data: BescheidData) -> None:
        """Extract the final assessed income tax"""
        # "Festgesetzte Einkommensteuer - gerundet gem. § 39 (3)   -3.794,00"
        m = re.search(
            r"festgesetzte\s+einkommensteuer[^\n]*?(-?\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            data.festgesetzte_einkommensteuer = self._parse_amount(m.group(1))


    def _extract_gutschrift_nachforderung(self, text: str, data: BescheidData) -> None:
        """Extract refund or additional payment"""
        # Abgabengutschrift (refund) - amount at end of line
        m = re.search(
            r"abgabengutschrift[^\n]*?(\d{1,3}(?:\.\d{3})*,\d{2})\s*$",
            text, re.IGNORECASE | re.MULTILINE,
        )
        if m:
            data.abgabengutschrift = self._parse_amount(m.group(1))

        # Abgabennachforderung (additional payment due)
        m = re.search(
            r"abgabennachforderung[^\n]*?(\d{1,3}(?:\.\d{3})*,\d{2})\s*$",
            text, re.IGNORECASE | re.MULTILINE,
        )
        if m:
            data.abgabennachforderung = self._parse_amount(m.group(1))

    # --- Income extraction ---

    def _extract_einkommen(self, text: str, data: BescheidData) -> None:
        """Extract total income and Gesamtbetrag der Einkuenfte"""
        # "Das Einkommen im Jahr 2023 betraegt 10.513,51"
        m = re.search(
            r"einkommen\s+im\s+jahr\s+\d{4}\s+betr.{1,2}gt\s+(\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            data.einkommen = self._parse_amount(m.group(1))

        # "Gesamtbetrag der Einkuenfte" line
        m = re.search(
            r"gesamtbetrag\s+der\s+eink.{1,2}nfte\s+(\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            data.gesamtbetrag_einkuenfte = self._parse_amount(m.group(1))

    def _extract_employment_details(self, text: str, data: BescheidData) -> None:
        """Extract employment income details"""
        # "stpfl.Bezuege (245)" or "stpfl. Bezüge (245)"
        m = re.search(r"stpfl\.?\s*bez.{1,2}ge\s*\(245\)", text, re.IGNORECASE)
        if m:
            data.einkuenfte_nichtselbstaendig = self._find_amount_after(text, m.end())

        # Employer name: look for all-caps line after "Bezugsauszahlende Stelle"
        # e.g. "MAGISTRAT DER STADT WIEN"
        employer_match = re.search(
            r"bezugsauszahlende\s+stelle[^\n]*\n\s*\n?\s*([A-Z][A-Z\s]+?)(?:\s{2,}|\n)",
            text, re.IGNORECASE | re.DOTALL,
        )
        if employer_match:
            employer_line = employer_match.group(1).strip()
            # Remove any trailing numbers (amounts)
            employer_line = re.sub(r"\s+\d[\d.,]*$", "", employer_line).strip()
            if len(employer_line) > 3:
                data.employer_name = employer_line

        # stpfl. Bezuege amount (the gross employment income before deductions)
        m = re.search(
            r"(?:magistrat|arbeitgeber|bezugsauszahlende).*?(\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            data.stpfl_bezuege = self._parse_amount(m.group(1))

    def _extract_vermietung(self, text: str, data: BescheidData) -> None:
        """Extract rental income (Vermietung und Verpachtung) details"""
        # Look for "Einkuenfte aus Vermietung und Verpachtung" section
        vv_match = re.search(
            r"eink.{1,2}nfte\s+aus\s+vermietung\s+und\s+verpachtung",
            text, re.IGNORECASE,
        )
        if not vv_match:
            return

        # Extract individual property lines like:
        # "E1b, Thenneberg 51, 2571 Altenmarkt an der Triesting      -869,82"
        # "E1b, Angeligasse 86 14, 1100 Wien                            0,00      -869,82"
        # We want the first amount (property result), not the subtotal at end
        e1b_pattern = r"E1b,\s*(.+?)\s{2,}(-?\d{1,3}(?:\.\d{3})*,\d{2})"
        vv_text = text[vv_match.start():]
        for line in vv_text.split("\n"):
            m = re.search(e1b_pattern, line.strip(), re.IGNORECASE)
            if m:
                address = m.group(1).strip()
                amount = self._parse_amount(m.group(2))
                if amount is not None:
                    data.vermietung_details.append({
                        "address": address,
                        "amount": amount,
                    })

        # Total V+V income
        total = Decimal("0")
        for detail in data.vermietung_details:
            total += detail["amount"]
        if data.vermietung_details:
            data.einkuenfte_vermietung = total

    def _extract_deductions(self, text: str, data: BescheidData) -> None:
        """Extract deduction amounts"""
        # Pauschbetrag fuer Werbungskosten: "-132,00"
        m = re.search(
            r"pauschbetrag\s+f.{1,2}r\s+werbungskosten\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            val = self._parse_amount(m.group(1))
            data.werbungskosten_pauschale = abs(val) if val is not None else None

        # Telearbeitspauschale: the deduction amount (first amount after EUR))
        # "Telearbeitspauschale lt. Lohnzettel (26 Tage x 3,00 EUR)  -78,00     11.383,33"
        # We want -78,00 (the deduction), not 11.383,33 (the subtotal)
        m = re.search(
            r"telearbeitspauschale[^\n]*?EUR\)\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if not m:
            # Fallback: first amount on a line starting with telearbeitspauschale
            m = re.search(
                r"telearbeitspauschale\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})",
                text, re.IGNORECASE,
            )
        if m:
            val = self._parse_amount(m.group(1))
            data.telearbeitspauschale = abs(val) if val is not None else None

        # Pendlerpauschale
        m = re.search(
            r"pendlerpauschale[^\n]*?(-?\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            val = self._parse_amount(m.group(1))
            data.pendlerpauschale_betrag = abs(val) if val is not None else None

    def _extract_tax_calculation(self, text: str, data: BescheidData) -> None:
        """Extract tax calculation details"""
        # Steuer vor Abzug der Absetzbetraege
        m = re.search(
            r"steuer\s+vor\s+abzug\s+der\s+absetzbetr.{1,2}ge\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            data.steuer_vor_absetzbetraege = self._parse_amount(m.group(1))

        # Verkehrsabsetzbetrag amount - must be on its own line with an amount
        # "Verkehrsabsetzbetrag                    -1.105,00"
        # Skip the header line that has "Ja/Nein"
        m = re.search(
            r"^\s*verkehrsabsetzbetrag\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})\s*$",
            text, re.IGNORECASE | re.MULTILINE,
        )
        if m:
            val = self._parse_amount(m.group(1))
            if val is not None:
                data.verkehrsabsetzbetrag_betrag = abs(val)

        # Steuer nach Abzug der Absetzbetraege
        m = re.search(
            r"steuer\s+nach\s+abzug\s+der\s+absetzbetr.{1,2}ge\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            data.steuer_nach_absetzbetraege = self._parse_amount(m.group(1))

        # Anrechenbare Lohnsteuer (260) - match the amount at end of line
        # "Anrechenbare Lohnsteuer (260)    -2.689,42"
        m = re.search(
            r"anrechenbare\s+lohnsteuer[^\n]*?(-?\d{1,3}(?:\.\d{3})*,\d{2})\s*$",
            text, re.IGNORECASE | re.MULTILINE,
        )
        if m:
            data.anrechenbare_lohnsteuer = self._parse_amount(m.group(1))

        # Erstattung SV-Beitraege
        m = re.search(
            r"erstattung.*?sv.?beitr.{1,2}ge\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            data.erstattung_sv_beitraege = self._parse_amount(m.group(1))

        # Negativsteuer
        m = re.search(
            r"negativsteuer\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            data.negativsteuer = self._parse_amount(m.group(1))

    def _extract_modern_bescheid_layout(self, text: str, data: BescheidData) -> None:
        """Recover fields from the newer Einkommensteuerbescheid layout used by FinanzOnline."""
        if not data.tax_year:
            m = re.search(
                r"einkommensteuerbescheid\s*(?:\n|\s)+f.{1,3}r\s+das\s+jahr\s+(\d{4})",
                text,
                re.IGNORECASE,
            )
            if m:
                data.tax_year = int(m.group(1))

        if not data.finanzamt:
            m = re.search(r"^(Finanzamt[^\n]+)$", text, re.IGNORECASE | re.MULTILINE)
            if m:
                data.finanzamt = m.group(1).strip()

        if not data.taxpayer_name:
            lines = text.splitlines()
            title_idx = next(
                (idx for idx, line in enumerate(lines) if re.search(r"einkommensteuerbescheid", line, re.IGNORECASE)),
                None,
            )
            if title_idx is not None:
                for i in range(max(0, title_idx - 6), title_idx):
                    stripped = lines[i].strip()
                    if not stripped:
                        continue
                    if re.search(
                        r"^(republik|bundesministerium|finanzamt|dienststelle|marxergasse|\d{4}\b)",
                        stripped,
                        re.IGNORECASE,
                    ):
                        continue
                    next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    next_next_line = lines[i + 2].strip() if i + 2 < len(lines) else ""
                    if re.search(r"\d", next_line) and re.search(r"^\d{4}\b", next_next_line):
                        data.taxpayer_name = stripped
                        break

        if not data.steuernummer:
            m = re.search(r"steuernummer\s+(\d[\d/\-]+\d)", text, re.IGNORECASE)
            if m:
                data.steuernummer = m.group(1).strip()

        if data.abgabennachforderung is None:
            m = re.search(
                r"nachzahlung[:\s]+(?:EUR\s*)?(\d{1,3}(?:\.\d{3})*,\d{2})",
                text,
                re.IGNORECASE,
            )
            if m:
                data.abgabennachforderung = self._parse_amount(m.group(1))

        if data.abgabengutschrift is None:
            m = re.search(
                r"gutschrift[:\s]+(?:EUR\s*)?(\d{1,3}(?:\.\d{3})*,\d{2})",
                text,
                re.IGNORECASE,
            )
            if m:
                data.abgabengutschrift = self._parse_amount(m.group(1))
        if data.faellig_am is None:
            data.faellig_am = self._extract_faellig_am(text)
        if data.bescheid_datum is None:
            data.bescheid_datum = self._extract_bescheid_datum(text)

    # --- Helpers ---

    @staticmethod
    def _parse_amount(text: str) -> Optional[Decimal]:
        """Parse Austrian number format: 1.234,56 -> 1234.56"""
        if not text:
            return None
        try:
            cleaned = text.strip().replace(".", "").replace(",", ".")
            # Handle negative with dash prefix
            cleaned = cleaned.lstrip("-")
            val = Decimal(cleaned)
            if "-" in text:
                val = -val
            return val
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _find_amount_after(text: str, pos: int) -> Optional[Decimal]:
        """Find the first European-format amount after a position in text"""
        remaining = text[pos:pos + 200]
        m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2})", remaining)
        if m:
            amount_str = m.group(1).replace(".", "").replace(",", ".")
            try:
                return Decimal(amount_str)
            except (InvalidOperation, ValueError):
                return None
        return None

    @staticmethod
    def _calculate_confidence(data: BescheidData) -> float:
        """Calculate overall extraction confidence"""
        score = 0.0
        total_fields = 0

        checks = [
            data.tax_year is not None,
            data.taxpayer_name is not None,
            data.steuernummer is not None,
            data.einkommen is not None,
            data.festgesetzte_einkommensteuer is not None,
            data.abgabengutschrift is not None or data.abgabennachforderung is not None,
            data.einkuenfte_nichtselbstaendig is not None or data.einkuenfte_vermietung is not None,
        ]

        for check in checks:
            total_fields += 1
            if check:
                score += 1

        return round(score / total_fields, 2) if total_fields > 0 else 0.0
