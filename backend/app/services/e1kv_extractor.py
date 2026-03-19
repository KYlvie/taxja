"""E1kv Beilage (capital gains supplement) extractor.

Extracts capital income and KESt data from Austrian E1kv tax form.
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
class E1kvData:
    tax_year: Optional[int] = None
    aktien_gewinne: Optional[Decimal] = None
    fonds_gewinne: Optional[Decimal] = None
    krypto_gewinne: Optional[Decimal] = None
    zinsen: Optional[Decimal] = None
    dividenden: Optional[Decimal] = None
    kest_einbehalten: Optional[Decimal] = None
    nachversteuerung: Optional[Decimal] = None
    confidence: float = 0.0


class E1kvExtractor:
    KEYWORD_CONTEXT = {
        "aktien": "aktien_gewinne",
        "wertpapier": "aktien_gewinne",
        "fonds": "fonds_gewinne",
        "investmentfonds": "fonds_gewinne",
        "kryptowährung": "krypto_gewinne",
        "kryptowaehrung": "krypto_gewinne",
        "krypto": "krypto_gewinne",
        "zinsen": "zinsen",
        "zinserträge": "zinsen",
        "zinsertraege": "zinsen",
        "dividenden": "dividenden",
        "kapitalertragsteuer": "kest_einbehalten",
        "kest": "kest_einbehalten",
        "nachversteuerung": "nachversteuerung",
    }

    def extract(self, text: str) -> E1kvData:
        if not text or len(text.strip()) < 20:
            return E1kvData(confidence=0.0)

        data = E1kvData()
        text_lower = text.lower()

        # Tax year
        for m in re.finditer(r"(?:Jahr|Veranlagung)\s*[:.]?\s*(\d{4})", text, re.I):
            year = int(m.group(1))
            if 2015 <= year <= 2030:
                data.tax_year = year
                break

        # KZ regex
        for m in re.finditer(r"(?:KZ|Kz|kz)\s*(\d{3,4})\s*[:\s]+\s*([\d.,\-]+)", text):
            val = _parse_decimal(m.group(2))
            if val is None:
                continue
            kz = m.group(1)
            if kz == "981" and data.aktien_gewinne is None:
                data.aktien_gewinne = val
            elif kz == "994" and data.kest_einbehalten is None:
                data.kest_einbehalten = val

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

    def _calculate_confidence(self, data: E1kvData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.15
        income_fields = [data.aktien_gewinne, data.fonds_gewinne, data.krypto_gewinne,
                         data.zinsen, data.dividenden]
        count = sum(1 for f in income_fields if f is not None)
        score += min(count * 0.15, 0.45)
        if data.kest_einbehalten:
            score += 0.25
        if data.nachversteuerung:
            score += 0.15
        return min(score, 1.0)

    def to_dict(self, data: E1kvData) -> Dict[str, Any]:
        result = {}
        for k, v in asdict(data).items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
