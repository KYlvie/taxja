"""L1k Beilage (child supplement) extractor.

Extracts Familienbonus Plus and child-related deduction data.
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
class ChildInfo:
    name: Optional[str] = None
    birth_date: Optional[str] = None
    familienbonus_amount: Optional[Decimal] = None  # KZ770
    kindermehrbetrag: Optional[Decimal] = None
    unterhaltsabsetzbetrag: Optional[Decimal] = None


@dataclass
class L1kData:
    tax_year: Optional[int] = None
    children: List[ChildInfo] = field(default_factory=list)
    total_familienbonus: Optional[Decimal] = None
    total_kindermehrbetrag: Optional[Decimal] = None
    confidence: float = 0.0


class L1kExtractor:
    def extract(self, text: str) -> L1kData:
        if not text or len(text.strip()) < 20:
            return L1kData(confidence=0.0)

        data = L1kData()
        self._extract_year(text, data)
        self._extract_children(text, data)
        self._extract_totals(text, data)
        data.confidence = self._calculate_confidence(data)
        return data

    def _extract_year(self, text: str, data: L1kData) -> None:
        for m in re.finditer(r"(?:Jahr|Veranlagung)\s*[:.]?\s*(\d{4})", text, re.I):
            year = int(m.group(1))
            if 2015 <= year <= 2030:
                data.tax_year = year
                break

    def _extract_children(self, text: str, data: L1kData) -> None:
        # Try to find child blocks: name + birth date + amounts
        child_pattern = re.compile(
            r"(?:Kind|Name)\s*[:.]?\s*(.+?)[\n\r]"
            r".*?(?:Geburtsdatum|geb\.?)\s*[:.]?\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
            re.IGNORECASE | re.DOTALL,
        )
        for m in child_pattern.finditer(text):
            child = ChildInfo(name=m.group(1).strip()[:100], birth_date=m.group(2).strip())
            data.children.append(child)

        # Extract KZ770 amounts for Familienbonus
        for m in re.finditer(r"(?:KZ|Kz|kz)\s*770\s*[:\s]+\s*([\d.,]+)", text):
            val = _parse_decimal(m.group(1))
            if val and data.children:
                # Assign to first child without amount
                for child in data.children:
                    if child.familienbonus_amount is None:
                        child.familienbonus_amount = val
                        break

    def _extract_totals(self, text: str, data: L1kData) -> None:
        text_lower = text.lower()
        amount_pat = r"([\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"

        for keyword, attr in [
            ("familienbonus", "total_familienbonus"),
            ("kindermehrbetrag", "total_kindermehrbetrag"),
        ]:
            if keyword in text_lower:
                idx = text_lower.find(keyword)
                window = text[idx:idx + 100]
                amounts = re.findall(amount_pat, window)
                if amounts:
                    val = _parse_decimal(amounts[-1])
                    if val:
                        setattr(data, attr, val)

    def _calculate_confidence(self, data: L1kData) -> float:
        score = 0.0
        if data.tax_year:
            score += 0.2
        if data.children:
            score += min(len(data.children) * 0.2, 0.4)
        if data.total_familienbonus:
            score += 0.25
        if data.total_kindermehrbetrag:
            score += 0.15
        return min(score, 1.0)

    def to_dict(self, data: L1kData) -> Dict[str, Any]:
        result = asdict(data)
        # Convert Decimals
        for child in result.get("children", []):
            for k, v in child.items():
                if isinstance(v, Decimal):
                    child[k] = float(v)
        for k in ("total_familienbonus", "total_kindermehrbetrag"):
            if isinstance(result.get(k), Decimal):
                result[k] = float(result[k])
        return result
