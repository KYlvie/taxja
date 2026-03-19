"""Grundsteuerbescheid (property tax notice) extractor.

Extracts property tax amount, address, and Einheitswert.
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
class GrundsteuerData:
    tax_year: Optional[int] = None
    property_address: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    grundsteuer_betrag: Optional[Decimal] = None
    einheitswert: Optional[Decimal] = None
    steuermessbetrag: Optional[Decimal] = None
    hebesatz: Optional[int] = None
    confidence: float = 0.0


class GrundsteuerExtractor:
    def extract(self, text: str) -> GrundsteuerData:
        if not text or len(text.strip()) < 20:
            return GrundsteuerData(confidence=0.0)

        data = GrundsteuerData()
        text_lower = text.lower()

        # Tax year
        for m in re.finditer(r"(?:Jahr|Zeitraum|Vorschreibung)\s*[:.]?\s*(\d{4})", text, re.I):
            year = int(m.group(1))
            if 2015 <= year <= 2030:
                data.tax_year = year
                break

        # Address
        addr = re.search(
            r"(?:Liegenschaft|Grundstück|Grundstueck|Objekt|Adresse)\s*[:.]?\s*(.+?)(?:\n|$)",
            text, re.I,
        )
        if addr:
            data.property_address = addr.group(1).strip()[:200]

        # Postal code + city
        plz = re.search(r"\b(\d{4})\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)", text)
        if plz:
            data.postal_code = plz.group(1)
            data.city = plz.group(2)

        # Amounts
        amount_pat = r"([\-]?[\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
        for kw, attr in [
            ("grundsteuer", "grundsteuer_betrag"),
            ("einheitswert", "einheitswert"),
            ("steuermessbetrag", "steuermessbetrag"),
        ]:
            if kw in text_lower:
                idx = text_lower.find(kw)
                window = text[idx:idx + 120]
                amounts = re.findall(amount_pat, window)
                if amounts:
                    val = _parse_decimal(amounts[-1])
                    if val:
                        setattr(data, attr, val)

        # Hebesatz (multiplier, typically 500%)
        hs = re.search(r"(?:Hebesatz|Zuschlag)\s*[:.]?\s*(\d+)\s*%", text, re.I)
        if hs:
            data.hebesatz = int(hs.group(1))

        data.confidence = self._calculate_confidence(data)
        return data

    def _calculate_confidence(self, data: GrundsteuerData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.15
        if data.property_address:
            score += 0.2
        if data.grundsteuer_betrag:
            score += 0.3
        if data.einheitswert:
            score += 0.2
        if data.steuermessbetrag:
            score += 0.15
        return min(score, 1.0)

    def to_dict(self, data: GrundsteuerData) -> Dict[str, Any]:
        result = {}
        for k, v in asdict(data).items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
