"""L1ab Beilage (deductions supplement) extractor.

Extracts Pendlerpauschale, Alleinverdiener/Alleinerzieher, and other deductions.
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
class L1abData:
    tax_year: Optional[int] = None
    alleinverdiener: Optional[bool] = None
    alleinerzieher: Optional[bool] = None
    pendlerpauschale_km: Optional[int] = None
    pendlerpauschale_betrag: Optional[Decimal] = None
    pendlereuro: Optional[Decimal] = None
    unterhaltsabsetzbetrag: Optional[Decimal] = None
    confidence: float = 0.0


class L1abExtractor:
    def extract(self, text: str) -> L1abData:
        if not text or len(text.strip()) < 20:
            return L1abData(confidence=0.0)

        data = L1abData()
        text_lower = text.lower()

        # Tax year
        for m in re.finditer(r"(?:Jahr|Veranlagung)\s*[:.]?\s*(\d{4})", text, re.I):
            year = int(m.group(1))
            if 2015 <= year <= 2030:
                data.tax_year = year
                break

        # Alleinverdiener / Alleinerzieher
        if "alleinverdiener" in text_lower:
            data.alleinverdiener = True
            # Check for "ja" / "x" nearby
            idx = text_lower.find("alleinverdiener")
            window = text_lower[idx:idx + 50]
            if "nein" in window or "0" in window:
                data.alleinverdiener = False

        if "alleinerzieher" in text_lower:
            data.alleinerzieher = True
            idx = text_lower.find("alleinerzieher")
            window = text_lower[idx:idx + 50]
            if "nein" in window or "0" in window:
                data.alleinerzieher = False

        # Pendlerpauschale km
        km_match = re.search(r"(?:km|kilometer)\s*[:.]?\s*(\d+)", text, re.I)
        if km_match:
            data.pendlerpauschale_km = int(km_match.group(1))

        # Pendlerpauschale amount
        amount_pat = r"([\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
        for keyword, attr in [
            ("pendlerpauschale", "pendlerpauschale_betrag"),
            ("pendlereuro", "pendlereuro"),
            ("unterhaltsabsetzbetrag", "unterhaltsabsetzbetrag"),
        ]:
            if keyword in text_lower:
                idx = text_lower.find(keyword)
                window = text[idx:idx + 100]
                amounts = re.findall(amount_pat, window)
                if amounts:
                    val = _parse_decimal(amounts[-1])
                    if val:
                        setattr(data, attr, val)

        # KZ regex
        for m in re.finditer(r"(?:KZ|Kz|kz)\s*(\d{3})\s*[:\s]+\s*([\d.,]+)", text):
            kz = m.group(1)
            val = _parse_decimal(m.group(2))
            if kz == "718" and val and data.pendlerpauschale_betrag is None:
                data.pendlerpauschale_betrag = val
            elif kz == "719" and val and data.pendlereuro is None:
                data.pendlereuro = val

        data.confidence = self._calculate_confidence(data)
        return data

    def _calculate_confidence(self, data: L1abData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.2
        if data.alleinverdiener is not None or data.alleinerzieher is not None:
            score += 0.25
        if data.pendlerpauschale_betrag:
            score += 0.25
        if data.pendlereuro:
            score += 0.15
        if data.unterhaltsabsetzbetrag:
            score += 0.15
        return min(score, 1.0)

    def to_dict(self, data: L1abData) -> Dict[str, Any]:
        result = {}
        for k, v in asdict(data).items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
