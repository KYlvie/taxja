"""L16 Lohnzettel (annual wage tax card) extractor.

Extracts structured data from Austrian L16 wage tax certificates.
Supports AcroForm PDF fields, KZ-code regex matching, and keyword context matching.
"""
import re
import logging
from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class L16Data:
    """Structured data from an L16 Lohnzettel."""

    tax_year: Optional[int] = None
    employer_name: Optional[str] = None
    employee_name: Optional[str] = None
    sv_nummer: Optional[str] = None
    # KZ fields (Kennzahlen)
    kz_210: Optional[Decimal] = None  # Bruttobezüge (gross income)
    kz_215: Optional[Decimal] = None  # Steuerfreie Zuschläge (tax-free overtime)
    kz_220: Optional[Decimal] = None  # Sonstige steuerfreie Bezüge
    kz_230: Optional[Decimal] = None  # SV-Beiträge (social insurance deducted)
    kz_245: Optional[Decimal] = None  # Steuerpflichtige Bezüge (taxable income)
    kz_260: Optional[Decimal] = None  # Einbehaltene Lohnsteuer (wage tax withheld)
    kz_718: Optional[Decimal] = None  # Pendlerpauschale
    kz_719: Optional[Decimal] = None  # Pendlereuro
    familienbonus: Optional[Decimal] = None
    telearbeitspauschale: Optional[Decimal] = None
    confidence: float = 0.0


def _parse_decimal(value: str) -> Optional[Decimal]:
    """Parse a German-format decimal string."""
    if not value:
        return None
    try:
        cleaned = value.strip().replace(".", "").replace(",", ".")
        cleaned = re.sub(r"[^\d.\-]", "", cleaned)
        if not cleaned or cleaned in (".", "-"):
            return None
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


class L16Extractor:
    """Extracts structured data from L16 Lohnzettel documents."""

    # KZ code to field name mapping
    KZ_FIELD_MAP = {
        "210": "kz_210",
        "215": "kz_215",
        "220": "kz_220",
        "230": "kz_230",
        "245": "kz_245",
        "260": "kz_260",
        "718": "kz_718",
        "719": "kz_719",
    }

    # Keyword context patterns: keyword → field name
    KEYWORD_CONTEXT = {
        "bruttobezüge": "kz_210",
        "bruttobezuege": "kz_210",
        "brutto": "kz_210",
        "steuerfreie zuschläge": "kz_215",
        "steuerfreie zuschlaege": "kz_215",
        "sv-beiträge": "kz_230",
        "sv-beitraege": "kz_230",
        "sozialversicherung": "kz_230",
        "sv-dnbeitrag": "kz_230",
        "steuerpflichtige bezüge": "kz_245",
        "steuerpflichtige bezuege": "kz_245",
        "bemessungsgrundlage": "kz_245",
        "lohnsteuer": "kz_260",
        "einbehaltene lohnsteuer": "kz_260",
        "lst": "kz_260",
        "pendlerpauschale": "kz_718",
        "pendlereuro": "kz_719",
        "familienbonus": "familienbonus",
        "fabo plus": "familienbonus",
        "telearbeitspauschale": "telearbeitspauschale",
        "homeoffice": "telearbeitspauschale",
    }

    def extract(self, text: str) -> L16Data:
        """Extract L16 data from OCR text."""
        if not text or len(text.strip()) < 20:
            return L16Data(confidence=0.0)

        data = L16Data()

        # Strategy 1: AcroForm fields (--- FORM FIELDS --- section)
        self._extract_acroform(text, data)

        # Strategy 2: KZ code + amount regex
        self._extract_kz_regex(text, data)

        # Strategy 3: Keyword context matching
        self._extract_keyword_context(text, data)

        # Extract metadata
        self._extract_metadata(text, data)

        # Calculate confidence
        data.confidence = self._calculate_confidence(data)

        return data

    def _extract_acroform(self, text: str, data: L16Data) -> None:
        """Extract from AcroForm PDF fields."""
        form_section = ""
        in_form = False
        for line in text.split("\n"):
            if "--- FORM FIELDS ---" in line or "FORM FIELDS" in line.upper():
                in_form = True
                continue
            if in_form:
                if line.startswith("---"):
                    break
                form_section += line + "\n"

        if not form_section:
            return

        # Match Kz{number}: value patterns
        for match in re.finditer(r"Kz\s*(\d{3})\s*[:=]\s*([\d.,\-]+)", form_section, re.IGNORECASE):
            kz_num = match.group(1)
            value = _parse_decimal(match.group(2))
            if kz_num in self.KZ_FIELD_MAP and value is not None:
                setattr(data, self.KZ_FIELD_MAP[kz_num], value)

    def _extract_kz_regex(self, text: str, data: L16Data) -> None:
        """Extract KZ codes with amounts using regex."""
        # Pattern: KZ 245 ... 42500.00 or Kz245: 42.500,00
        patterns = [
            r"(?:KZ|Kz|kz)\s*(\d{3})\s*[:\s]+\s*([\d.,]+(?:\s*[\d.,]+)?)",
            r"(\d{3})\s*[|]\s*([\d.,]+)",  # Table format: 245 | 42.500,00
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                kz_num = match.group(1)
                value = _parse_decimal(match.group(2))
                field_name = self.KZ_FIELD_MAP.get(kz_num)
                if field_name and value is not None and getattr(data, field_name) is None:
                    setattr(data, field_name, value)

    def _extract_keyword_context(self, text: str, data: L16Data) -> None:
        """Extract amounts near known keywords."""
        text_lower = text.lower()
        amount_pattern = r"([\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"

        for keyword, field_name in self.KEYWORD_CONTEXT.items():
            if keyword not in text_lower:
                continue
            if getattr(data, field_name) is not None:
                continue

            # Find keyword position and look for amount nearby
            idx = text_lower.find(keyword)
            # Search in a window after the keyword
            window = text[idx:idx + 120]
            amounts = re.findall(amount_pattern, window)
            if amounts:
                value = _parse_decimal(amounts[-1])  # Take last (usually the value)
                if value is not None:
                    setattr(data, field_name, value)

    def _extract_metadata(self, text: str, data: L16Data) -> None:
        """Extract tax year, employer name, employee name, SV number."""
        # Tax year
        year_patterns = [
            r"(?:Kalenderjahr|Jahr|Zeitraum|Lohnzettel)\s*[:.]?\s*(\d{4})",
            r"(\d{4})\s*(?:Lohnzettel|L\s*16)",
            r"L\s*16\s*(?:für|fuer|fur)?\s*(\d{4})",
            r"01\.01\.(\d{4})\s*[-–]\s*31\.12\.\d{4}",
        ]
        for pattern in year_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and data.tax_year is None:
                year = int(match.group(1))
                if 2015 <= year <= 2030:
                    data.tax_year = year
                    break

        # SV number (format: 1234 DDMMYY or 1234DDMMYY)
        sv_match = re.search(r"\b(\d{4})\s*(\d{6})\b", text)
        if sv_match and data.sv_nummer is None:
            data.sv_nummer = f"{sv_match.group(1)} {sv_match.group(2)}"

        # Employer name: look after "Arbeitgeber" keyword
        emp_match = re.search(
            r"(?:Arbeitgeber|Dienstgeber)\s*[:.]?\s*(.+?)(?:\n|$)", text, re.IGNORECASE
        )
        if emp_match and data.employer_name is None:
            name = emp_match.group(1).strip()
            if len(name) > 2:
                data.employer_name = name[:200]

    def _calculate_confidence(self, data: L16Data) -> float:
        """Calculate confidence score based on extracted fields."""
        score = 0.0
        # Critical fields
        if data.tax_year:
            score += 0.2
        if data.kz_245:
            score += 0.25
        if data.kz_260:
            score += 0.25
        # Important fields
        if data.kz_210:
            score += 0.1
        if data.kz_230:
            score += 0.1
        # Nice-to-have
        if data.employer_name:
            score += 0.05
        if data.kz_718 or data.kz_719:
            score += 0.05
        return min(score, 1.0)

    def to_dict(self, data: L16Data) -> Dict[str, Any]:
        """Convert L16Data to JSON-serializable dict."""
        result = {}
        for k, v in asdict(data).items():
            if v is None:
                result[k] = None
            elif isinstance(v, Decimal):
                result[k] = float(v)
            else:
                result[k] = v
        return result
