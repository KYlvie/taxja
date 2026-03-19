"""Jahresabschluss (annual financial statement) extractor.

Extracts income/expense summary and profit/loss from E/A or Bilanz format.
"""
import re
import logging
from dataclasses import dataclass, field, asdict
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
class JahresabschlussData:
    tax_year: Optional[int] = None
    format_type: str = "ea"  # "ea" or "bilanz"
    einnahmen_gesamt: Optional[Decimal] = None
    ausgaben_gesamt: Optional[Decimal] = None
    gewinn_verlust: Optional[Decimal] = None
    afa_gesamt: Optional[Decimal] = None
    ausgaben_detail: Dict[str, float] = field(default_factory=dict)
    has_loss: bool = False
    confidence: float = 0.0


class JahresabschlussExtractor:
    KEYWORD_CONTEXT = {
        "einnahmen gesamt": "einnahmen_gesamt",
        "betriebseinnahmen": "einnahmen_gesamt",
        "gesamteinnahmen": "einnahmen_gesamt",
        "ausgaben gesamt": "ausgaben_gesamt",
        "betriebsausgaben": "ausgaben_gesamt",
        "gesamtausgaben": "ausgaben_gesamt",
        "gewinn": "gewinn_verlust",
        "verlust": "gewinn_verlust",
        "jahresergebnis": "gewinn_verlust",
        "betriebsergebnis": "gewinn_verlust",
        "abschreibung": "afa_gesamt",
        "afa": "afa_gesamt",
    }

    EXPENSE_CATEGORIES = [
        "wareneinkauf", "personalaufwand", "miete", "versicherung",
        "reisekosten", "werbung", "büromaterial", "bueromaterial",
        "telefon", "internet", "fortbildung", "beratung",
    ]

    def extract(self, text: str) -> JahresabschlussData:
        if not text or len(text.strip()) < 20:
            return JahresabschlussData(confidence=0.0)

        data = JahresabschlussData()
        text_lower = text.lower()

        # Detect format
        if "bilanz" in text_lower or "bilanzsumme" in text_lower:
            data.format_type = "bilanz"
        else:
            data.format_type = "ea"

        # Tax year
        for m in re.finditer(r"(?:Jahr|Geschäftsjahr|Geschaeftsjahr|Zeitraum)\s*[:.]?\s*(\d{4})",
                             text, re.I):
            year = int(m.group(1))
            if 2015 <= year <= 2030:
                data.tax_year = year
                break

        # Main fields via keyword context
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

        # Expense detail categories
        for cat in self.EXPENSE_CATEGORIES:
            if cat in text_lower:
                idx = text_lower.find(cat)
                window = text[idx:idx + 100]
                amounts = re.findall(amount_pat, window)
                if amounts:
                    val = _parse_decimal(amounts[-1])
                    if val is not None:
                        data.ausgaben_detail[cat] = float(val)

        # Detect loss
        if data.gewinn_verlust is not None and data.gewinn_verlust < 0:
            data.has_loss = True

        data.confidence = self._calculate_confidence(data)
        return data

    def _calculate_confidence(self, data: JahresabschlussData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.15
        if data.einnahmen_gesamt:
            score += 0.25
        if data.ausgaben_gesamt:
            score += 0.2
        if data.gewinn_verlust is not None:
            score += 0.2
        if data.ausgaben_detail:
            score += min(len(data.ausgaben_detail) * 0.05, 0.2)
        return min(score, 1.0)

    def to_dict(self, data: JahresabschlussData) -> Dict[str, Any]:
        result = {}
        for k, v in asdict(data).items():
            if isinstance(v, Decimal):
                result[k] = float(v)
            else:
                result[k] = v
        return result
