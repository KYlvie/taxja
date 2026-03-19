"""VAT form extractor for U1 (annual) and U30 (advance) declarations.

Extracts turnover by tax rate, input/output VAT, and payment amounts.
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
class VatFormData:
    form_type: str = "u1"  # "u1" or "u30"
    tax_year: Optional[int] = None
    period: Optional[str] = None  # "2025" for U1, "Q1 2025" / "01/2025" for U30
    umsatz_20: Optional[Decimal] = None
    umsatz_13: Optional[Decimal] = None
    umsatz_10: Optional[Decimal] = None
    umsatz_0: Optional[Decimal] = None
    umsatz_gesamt: Optional[Decimal] = None
    ust_gesamt: Optional[Decimal] = None  # Output VAT total
    vorsteuer: Optional[Decimal] = None   # Input VAT total
    zahllast: Optional[Decimal] = None    # Net VAT payable (positive) or refund (negative)
    confidence: float = 0.0


class VatFormExtractor:
    KEYWORD_CONTEXT = {
        "20%": "umsatz_20", "20 %": "umsatz_20",
        "13%": "umsatz_13", "13 %": "umsatz_13",
        "10%": "umsatz_10", "10 %": "umsatz_10",
        "steuerfrei": "umsatz_0",
        "gesamtumsatz": "umsatz_gesamt",
        "gesamtbetrag der umsatzsteuer": "ust_gesamt",
        "vorsteuer": "vorsteuer",
        "zahllast": "zahllast",
        "gutschrift": "zahllast",
    }

    def extract(self, text: str) -> VatFormData:
        """Extract U1 annual VAT declaration."""
        return self._extract_common(text, "u1")

    def extract_u30(self, text: str) -> VatFormData:
        """Extract U30 VAT advance return."""
        return self._extract_common(text, "u30")

    def _extract_common(self, text: str, form_type: str) -> VatFormData:
        if not text or len(text.strip()) < 20:
            return VatFormData(form_type=form_type, confidence=0.0)

        data = VatFormData(form_type=form_type)
        text_lower = text.lower()

        # Tax year
        for m in re.finditer(r"(?:Jahr|Zeitraum|Veranlagung)\s*[:.]?\s*(\d{4})", text, re.I):
            year = int(m.group(1))
            if 2015 <= year <= 2030:
                data.tax_year = year
                break

        # Period for U30
        if form_type == "u30":
            period_m = re.search(
                r"(?:Zeitraum|Monat|Quartal)\s*[:.]?\s*(.+?)(?:\n|$)", text, re.I
            )
            if period_m:
                data.period = period_m.group(1).strip()[:50]
        else:
            if data.tax_year:
                data.period = str(data.tax_year)

        # KZ regex
        for m in re.finditer(r"(?:KZ|Kz|kz)\s*(\d{3})\s*[:\s]+\s*([\d.,\-]+)", text):
            val = _parse_decimal(m.group(2))
            if val is None:
                continue
            kz = m.group(1)
            if kz == "000" and data.umsatz_gesamt is None:
                data.umsatz_gesamt = val
            elif kz == "022" and data.umsatz_20 is None:
                data.umsatz_20 = val
            elif kz == "029" and data.umsatz_10 is None:
                data.umsatz_10 = val
            elif kz == "060" and data.vorsteuer is None:
                data.vorsteuer = val
            elif kz == "095" and data.zahllast is None:
                data.zahllast = val

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

    def _calculate_confidence(self, data: VatFormData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.15
        turnover_fields = [data.umsatz_20, data.umsatz_13, data.umsatz_10, data.umsatz_0]
        count = sum(1 for f in turnover_fields if f is not None)
        score += min(count * 0.1, 0.3)
        if data.umsatz_gesamt:
            score += 0.15
        if data.vorsteuer:
            score += 0.2
        if data.zahllast:
            score += 0.2
        return min(score, 1.0)

    def to_dict(self, data: VatFormData) -> Dict[str, Any]:
        result = {}
        for k, v in asdict(data).items():
            result[k] = float(v) if isinstance(v, Decimal) else v
        return result
