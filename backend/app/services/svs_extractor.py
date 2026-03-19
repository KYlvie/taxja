"""SVS (Sozialversicherung der Selbständigen) notice extractor.

Extracts social insurance contribution data for self-employed persons.
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
class SvsData:
    tax_year: Optional[int] = None
    versicherungsnummer: Optional[str] = None
    beitragsgrundlage: Optional[Decimal] = None
    pensionsversicherung: Optional[Decimal] = None
    krankenversicherung: Optional[Decimal] = None
    unfallversicherung: Optional[Decimal] = None
    beitrag_gesamt: Optional[Decimal] = None
    nachzahlung: Optional[Decimal] = None
    gutschrift: Optional[Decimal] = None
    confidence: float = 0.0


class SvsExtractor:
    KEYWORD_CONTEXT = {
        "beitragsgrundlage": "beitragsgrundlage",
        "pensionsversicherung": "pensionsversicherung",
        "krankenversicherung": "krankenversicherung",
        "unfallversicherung": "unfallversicherung",
        "beitrag gesamt": "beitrag_gesamt",
        "gesamtbeitrag": "beitrag_gesamt",
        "nachzahlung": "nachzahlung",
        "gutschrift": "gutschrift",
    }

    def extract(self, text: str) -> SvsData:
        if not text or len(text.strip()) < 20:
            return SvsData(confidence=0.0)

        data = SvsData()
        text_lower = text.lower()

        # Tax year
        for m in re.finditer(r"(?:Jahr|Beitragsjahr|Zeitraum)\s*[:.]?\s*(\d{4})", text, re.I):
            year = int(m.group(1))
            if 2015 <= year <= 2030:
                data.tax_year = year
                break

        # Versicherungsnummer
        vn = re.search(r"(?:Versicherungsnummer|VNr\.?)\s*[:.]?\s*([\d\s]+)", text, re.I)
        if vn:
            data.versicherungsnummer = vn.group(1).strip()[:20]

        # Keyword context
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

        data.confidence = self._calculate_confidence(data)
        return data

    def _calculate_confidence(self, data: SvsData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.15
        if data.beitragsgrundlage:
            score += 0.2
        ins_fields = [data.pensionsversicherung, data.krankenversicherung,
                      data.unfallversicherung]
        count = sum(1 for f in ins_fields if f is not None)
        score += min(count * 0.15, 0.35)
        if data.beitrag_gesamt:
            score += 0.2
        return min(score, 1.0)

    def to_dict(self, data: SvsData) -> Dict[str, Any]:
        result = {}
        for k, v in asdict(data).items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
