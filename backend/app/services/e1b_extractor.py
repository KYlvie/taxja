"""E1b Beilage (rental income supplement) extractor.

Extracts per-property rental income/expense data from Austrian E1b tax form.
"""
import re
import logging
from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _parse_decimal(value: str) -> Optional[Decimal]:
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


@dataclass
class RentalPropertyDetail:
    address: Optional[str] = None
    einnahmen: Optional[Decimal] = None       # KZ9460 rental income
    afa: Optional[Decimal] = None             # KZ9500 depreciation
    fremdfinanzierung: Optional[Decimal] = None  # KZ9510 loan interest
    instandhaltung: Optional[Decimal] = None  # KZ9520 maintenance
    uebrige_werbungskosten: Optional[Decimal] = None  # KZ9530 other costs
    einkuenfte: Optional[Decimal] = None      # KZ9414 net rental income


@dataclass
class E1bData:
    tax_year: Optional[int] = None
    steuernummer: Optional[str] = None
    properties: List[RentalPropertyDetail] = field(default_factory=list)
    total_vv_income: Optional[Decimal] = None
    confidence: float = 0.0


class E1bExtractor:
    KZ_PROPERTY_MAP = {
        "9460": "einnahmen",
        "9500": "afa",
        "9510": "fremdfinanzierung",
        "9520": "instandhaltung",
        "9530": "uebrige_werbungskosten",
        "9414": "einkuenfte",
    }

    def extract(self, text: str) -> E1bData:
        if not text or len(text.strip()) < 20:
            return E1bData(confidence=0.0)

        data = E1bData()

        # Tax year
        for m in re.finditer(r"(?:Jahr|Veranlagung|Zeitraum)\s*[:.]?\s*(\d{4})", text, re.I):
            year = int(m.group(1))
            if 2015 <= year <= 2030:
                data.tax_year = year
                break

        # Steuernummer
        stn = re.search(r"(?:Steuernummer|St\.?Nr\.?)\s*[:.]?\s*([\d/\-]+)", text, re.I)
        if stn:
            data.steuernummer = stn.group(1).strip()

        # Try to split by property sections
        self._extract_properties(text, data)

        # If no properties found, try single-property extraction
        if not data.properties:
            prop = RentalPropertyDetail()
            self._extract_kz_into_property(text, prop)
            self._extract_address(text, prop)
            if prop.einnahmen is not None or prop.einkuenfte is not None:
                data.properties.append(prop)

        # Total V+V income
        text_lower = text.lower()
        if "gesamtbetrag" in text_lower or "summe" in text_lower:
            amount_pat = r"([\-]?[\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
            for kw in ["gesamtbetrag", "summe der einkünfte", "summe der einkuenfte"]:
                if kw in text_lower:
                    idx = text_lower.find(kw)
                    window = text[idx:idx + 100]
                    amounts = re.findall(amount_pat, window)
                    if amounts:
                        data.total_vv_income = _parse_decimal(amounts[-1])
                        break

        data.confidence = self._calculate_confidence(data)
        return data

    def _extract_properties(self, text: str, data: E1bData) -> None:
        """Try to split text into per-property sections."""
        # Look for property section markers
        sections = re.split(
            r"(?:Objekt|Liegenschaft|Grundstück|Grundstueck)\s*(?:\d+|[A-Z])\s*[:\-]",
            text, flags=re.IGNORECASE,
        )
        if len(sections) <= 1:
            return

        for section in sections[1:]:  # Skip header before first property
            prop = RentalPropertyDetail()
            self._extract_kz_into_property(section, prop)
            self._extract_address(section, prop)
            if prop.einnahmen is not None or prop.einkuenfte is not None or prop.address:
                data.properties.append(prop)

    def _extract_kz_into_property(self, text: str, prop: RentalPropertyDetail) -> None:
        for m in re.finditer(r"(?:KZ|Kz|kz)\s*(\d{4})\s*[:\s]+\s*([\d.,\-]+)", text):
            kz = m.group(1)
            val = _parse_decimal(m.group(2))
            field_name = self.KZ_PROPERTY_MAP.get(kz)
            if field_name and val is not None and getattr(prop, field_name) is None:
                setattr(prop, field_name, val)

        # Keyword fallback
        text_lower = text.lower()
        amount_pat = r"([\-]?[\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
        for kw, attr in [
            ("mieteinnahmen", "einnahmen"), ("einnahmen", "einnahmen"),
            ("afa", "afa"), ("abschreibung", "afa"),
            ("zinsen", "fremdfinanzierung"), ("fremdfinanzierung", "fremdfinanzierung"),
            ("instandhaltung", "instandhaltung"), ("reparatur", "instandhaltung"),
        ]:
            if kw in text_lower and getattr(prop, attr) is None:
                idx = text_lower.find(kw)
                window = text[idx:idx + 100]
                amounts = re.findall(amount_pat, window)
                if amounts:
                    val = _parse_decimal(amounts[-1])
                    if val:
                        setattr(prop, attr, val)

    def _extract_address(self, text: str, prop: RentalPropertyDetail) -> None:
        addr = re.search(
            r"(?:Adresse|Anschrift|Lage)\s*[:.]?\s*(.+?)(?:\n|$)", text, re.I
        )
        if addr:
            prop.address = addr.group(1).strip()[:200]

    def _calculate_confidence(self, data: E1bData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.15
        if data.properties:
            score += 0.2
            for prop in data.properties:
                if prop.einnahmen:
                    score += 0.15
                if prop.einkuenfte:
                    score += 0.1
                if prop.address:
                    score += 0.1
        if data.total_vv_income:
            score += 0.15
        return min(score, 1.0)

    def to_dict(self, data: E1bData) -> Dict[str, Any]:
        result = {
            "tax_year": data.tax_year,
            "steuernummer": data.steuernummer,
            "total_vv_income": float(data.total_vv_income) if data.total_vv_income else None,
            "confidence": data.confidence,
            "properties": [],
        }
        for prop in data.properties:
            p = {}
            for k, v in asdict(prop).items():
                p[k] = float(v) if isinstance(v, Decimal) else v
            result["properties"].append(p)
        return result
