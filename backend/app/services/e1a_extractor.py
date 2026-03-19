"""E1a Beilage (self-employment income supplement) extractor.

Extracts business income/expense data from Austrian E1a tax form supplement.
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
class E1aData:
    tax_year: Optional[int] = None
    steuernummer: Optional[str] = None
    betriebseinnahmen: Optional[Decimal] = None
    wareneinkauf: Optional[Decimal] = None
    personalaufwand: Optional[Decimal] = None
    afa: Optional[Decimal] = None
    mietaufwand: Optional[Decimal] = None
    reisekosten: Optional[Decimal] = None
    versicherungen: Optional[Decimal] = None
    sonstige_ausgaben: Optional[Decimal] = None
    betriebsausgaben_gesamt: Optional[Decimal] = None
    gewinn_verlust: Optional[Decimal] = None
    betriebsausgabenpauschale: Optional[bool] = None
    pauschale_prozent: Optional[int] = None
    has_loss: bool = False
    confidence: float = 0.0


class E1aExtractor:
    KEYWORD_CONTEXT = {
        "betriebseinnahmen": "betriebseinnahmen",
        "wareneinkauf": "wareneinkauf",
        "personalaufwand": "personalaufwand",
        "abschreibung": "afa",
        "afa": "afa",
        "mietaufwand": "mietaufwand",
        "reisekosten": "reisekosten",
        "versicherungen": "versicherungen",
        "sonstige betriebsausgaben": "sonstige_ausgaben",
        "betriebsausgaben gesamt": "betriebsausgaben_gesamt",
        "betriebsausgaben insgesamt": "betriebsausgaben_gesamt",
        "gewinn": "gewinn_verlust",
        "verlust": "gewinn_verlust",
    }

    def extract(self, text: str) -> E1aData:
        if not text or len(text.strip()) < 20:
            return E1aData(confidence=0.0)

        data = E1aData()
        text_lower = text.lower()

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

        # Betriebsausgabenpauschale
        if "betriebsausgabenpauschale" in text_lower or "pauschale" in text_lower:
            data.betriebsausgabenpauschale = True
            pct = re.search(r"(\d+)\s*%", text[text_lower.find("pauschale"):])
            if pct:
                data.pauschale_prozent = int(pct.group(1))

        # KZ regex extraction
        for m in re.finditer(r"(?:KZ|Kz|kz)\s*(\d{3,4})\s*[:\s]+\s*([\d.,\-]+)", text):
            val = _parse_decimal(m.group(2))
            if val is None:
                continue
            # Map common E1a KZ codes
            kz = m.group(1)
            if kz in ("9040", "9050"):
                data.betriebseinnahmen = data.betriebseinnahmen or val
            elif kz == "9230":
                data.betriebsausgaben_gesamt = data.betriebsausgaben_gesamt or val

        # Keyword context extraction
        amount_pat = r"([\-]?[\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
        for keyword, field_name in self.KEYWORD_CONTEXT.items():
            if keyword not in text_lower:
                continue
            if getattr(data, field_name) is not None:
                continue
            idx = text_lower.find(keyword)
            window = text[idx:idx + 120]
            amounts = re.findall(amount_pat, window)
            if amounts:
                val = _parse_decimal(amounts[-1])
                if val is not None:
                    setattr(data, field_name, val)

        # Detect loss
        if data.gewinn_verlust is not None and data.gewinn_verlust < 0:
            data.has_loss = True

        data.confidence = self._calculate_confidence(data)
        return data

    def _calculate_confidence(self, data: E1aData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.15
        if data.betriebseinnahmen:
            score += 0.25
        if data.betriebsausgaben_gesamt:
            score += 0.2
        if data.gewinn_verlust is not None:
            score += 0.2
        expense_fields = [data.wareneinkauf, data.personalaufwand, data.afa,
                          data.mietaufwand, data.reisekosten, data.versicherungen]
        count = sum(1 for f in expense_fields if f is not None)
        score += min(count * 0.05, 0.2)
        return min(score, 1.0)

    def to_dict(self, data: E1aData) -> Dict[str, Any]:
        result = {}
        for k, v in asdict(data).items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
