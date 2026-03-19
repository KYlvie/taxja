"""L1 Form (Arbeitnehmerveranlagung) extractor.

Extracts structured data from Austrian L1 employee tax return forms.
"""
import re
import logging
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

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
class L1FormData:
    tax_year: Optional[int] = None
    taxpayer_name: Optional[str] = None
    steuernummer: Optional[str] = None
    # Werbungskosten
    kz_717: Optional[Decimal] = None  # Gewerkschaftsbeiträge
    kz_719: Optional[Decimal] = None  # Arbeitsmittel
    kz_720: Optional[Decimal] = None  # Fachliteratur
    kz_721: Optional[Decimal] = None  # Reisekosten
    kz_722: Optional[Decimal] = None  # Fortbildung
    kz_723: Optional[Decimal] = None  # Doppelte Haushaltsführung
    kz_724: Optional[Decimal] = None  # Sonstige Werbungskosten
    # Sonderausgaben
    kz_450: Optional[Decimal] = None  # Topf-Sonderausgaben
    kz_458: Optional[Decimal] = None  # Kirchenbeitrag
    kz_459: Optional[Decimal] = None  # Spenden
    # Außergewöhnliche Belastungen
    kz_730: Optional[Decimal] = None  # mit Selbstbehalt
    kz_740: Optional[Decimal] = None  # ohne Selbstbehalt
    confidence: float = 0.0


class L1FormExtractor:
    KZ_FIELD_MAP = {
        "717": "kz_717", "719": "kz_719", "720": "kz_720", "721": "kz_721",
        "722": "kz_722", "723": "kz_723", "724": "kz_724",
        "450": "kz_450", "458": "kz_458", "459": "kz_459",
        "730": "kz_730", "740": "kz_740",
    }

    KEYWORD_CONTEXT = {
        "gewerkschaftsbeiträge": "kz_717",
        "gewerkschaftsbeitraege": "kz_717",
        "arbeitsmittel": "kz_719",
        "fachliteratur": "kz_720",
        "reisekosten": "kz_721",
        "fortbildung": "kz_722",
        "doppelte haushaltsführung": "kz_723",
        "doppelte haushaltsfuehrung": "kz_723",
        "sonstige werbungskosten": "kz_724",
        "topf-sonderausgaben": "kz_450",
        "kirchenbeitrag": "kz_458",
        "spenden": "kz_459",
        "außergewöhnliche belastungen mit": "kz_730",
        "aussergewoehnliche belastungen mit": "kz_730",
        "außergewöhnliche belastungen ohne": "kz_740",
        "aussergewoehnliche belastungen ohne": "kz_740",
    }

    def extract(self, text: str) -> L1FormData:
        if not text or len(text.strip()) < 20:
            return L1FormData(confidence=0.0)

        data = L1FormData()
        self._extract_kz_regex(text, data)
        self._extract_keyword_context(text, data)
        self._extract_metadata(text, data)
        data.confidence = self._calculate_confidence(data)
        return data

    def _extract_kz_regex(self, text: str, data: L1FormData) -> None:
        for match in re.finditer(r"(?:KZ|Kz|kz)\s*(\d{3})\s*[:\s]+\s*([\d.,]+)", text):
            kz_num = match.group(1)
            value = _parse_decimal(match.group(2))
            field_name = self.KZ_FIELD_MAP.get(kz_num)
            if field_name and value is not None and getattr(data, field_name) is None:
                setattr(data, field_name, value)

    def _extract_keyword_context(self, text: str, data: L1FormData) -> None:
        text_lower = text.lower()
        amount_pattern = r"([\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
        for keyword, field_name in self.KEYWORD_CONTEXT.items():
            if keyword not in text_lower:
                continue
            if getattr(data, field_name) is not None:
                continue
            idx = text_lower.find(keyword)
            window = text[idx:idx + 120]
            amounts = re.findall(amount_pattern, window)
            if amounts:
                value = _parse_decimal(amounts[-1])
                if value is not None:
                    setattr(data, field_name, value)

    def _extract_metadata(self, text: str, data: L1FormData) -> None:
        for match in re.finditer(r"(?:Jahr|Veranlagung|Zeitraum)\s*[:.]?\s*(\d{4})", text, re.I):
            year = int(match.group(1))
            if 2015 <= year <= 2030:
                data.tax_year = year
                break
        stn = re.search(r"(?:Steuernummer|St\.?Nr\.?)\s*[:.]?\s*([\d/\-]+)", text, re.I)
        if stn:
            data.steuernummer = stn.group(1).strip()

    def _calculate_confidence(self, data: L1FormData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.2
        wk_fields = [data.kz_717, data.kz_719, data.kz_720, data.kz_721,
                      data.kz_722, data.kz_723, data.kz_724]
        wk_count = sum(1 for f in wk_fields if f is not None)
        score += min(wk_count * 0.1, 0.3)
        sa_fields = [data.kz_450, data.kz_458, data.kz_459]
        sa_count = sum(1 for f in sa_fields if f is not None)
        score += min(sa_count * 0.1, 0.2)
        if data.kz_730 is not None or data.kz_740 is not None:
            score += 0.15
        if data.steuernummer:
            score += 0.1
        return min(score, 1.0)

    def to_dict(self, data: L1FormData) -> Dict[str, Any]:
        result = {}
        for k, v in asdict(data).items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
