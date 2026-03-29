"""
Rent Adjustment (Indexanpassungsschreiben / Mietzinserhöhung) Extractor

Parses OCR text from Austrian rent adjustment notices and extracts structured data
including current rent, new rent, effective date, property address, and adjustment reason.

Triggered when a user uploads a rent increase letter. The extracted data is used to
find the matching rental recurring transaction and propose an update.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RentAdjustmentData:
    """Structured data from a rent adjustment notice"""
    # Property information
    property_address: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None

    # Rent amounts
    current_monthly_rent: Optional[Decimal] = None  # bisheriger Mietzins
    new_monthly_rent: Optional[Decimal] = None  # neuer Mietzins
    adjustment_amount: Optional[Decimal] = None  # Erhöhungsbetrag
    adjustment_percentage: Optional[Decimal] = None  # Erhöhungsprozentsatz

    # Dates
    notice_date: Optional[datetime] = None  # Datum des Schreibens
    effective_date: Optional[datetime] = None  # Wirksam ab / Gültig ab

    # Parties
    tenant_name: Optional[str] = None
    landlord_name: Optional[str] = None

    # Adjustment reason
    adjustment_reason: Optional[str] = None  # Indexanpassung, Inflationsausgleich, etc.

    # Betriebskosten adjustments (if present)
    current_betriebskosten: Optional[Decimal] = None
    new_betriebskosten: Optional[Decimal] = None

    # Confidence scores per field
    field_confidence: Dict[str, float] = field(default_factory=dict)

    # Overall confidence
    confidence: float = 0.0


class RentAdjustmentExtractor:
    """Extract structured data from rent adjustment notice OCR text"""
    MIN_REASONABLE_RENT = Decimal("100.00")
    MAX_REASONABLE_RENT = Decimal("10000.00")

    def extract(self, text: str) -> RentAdjustmentData:
        """Main extraction method"""
        data = RentAdjustmentData()

        self._extract_property_address(text, data)
        self._extract_rent_amounts(text, data)
        self._extract_dates(text, data)
        self._extract_parties(text, data)
        self._extract_adjustment_reason(text, data)
        self._extract_betriebskosten(text, data)
        self._derive_calculated_fields(data)

        data.confidence = self._calculate_confidence(data)
        return data

    def to_dict(self, data: RentAdjustmentData) -> Dict[str, Any]:
        """Convert RentAdjustmentData to dictionary for storage"""
        result = {}
        for key, value in data.__dict__.items():
            if value is None:
                result[key] = None
            elif isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = {
                    k: float(v) if isinstance(v, Decimal) else v
                    for k, v in value.items()
                }
            else:
                result[key] = value
        return result

    # --- Property address extraction ---

    def _extract_property_address(self, text: str, data: RentAdjustmentData) -> None:
        """Extract property address from rent adjustment notice"""
        lines = text.split("\n")

        # Strategy 1: labeled patterns (Mietobjekt, Objekt, betreffend, Wohnung)
        address_labels = [
            r"(?:mietobjekt|objekt|mietgegenstand|betreffend|wohnung|liegenschaft)[:\s]+(.+)",
            r"(?:mietobjekt|objekt|betreffend)\s*[:\-]\s*(.+)",
        ]
        for pattern in address_labels:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                addr = match.group(1).strip().rstrip(",;.")
                if len(addr) > 5:
                    data.property_address = addr
                    data.field_confidence["property_address"] = 0.85
                    break

        # Strategy 2: postal code + city pattern (Austrian: 4-digit PLZ)
        if not data.property_address:
            for line in lines:
                postal_match = re.search(r"(\d{4})\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)", line)
                if postal_match:
                    # Look for street in same or previous line
                    street_match = re.search(r"([A-ZÄÖÜ][a-zäöüß]+(?:straße|gasse|weg|platz|ring)\s+\d+[a-z]?(?:/\d+)?)", line, re.IGNORECASE)
                    if street_match:
                        data.street = street_match.group(1).strip()
                        data.field_confidence["street"] = 0.75
                    data.postal_code = postal_match.group(1)
                    data.city = postal_match.group(2).strip()
                    data.property_address = line.strip()
                    data.field_confidence["property_address"] = 0.7
                    data.field_confidence["postal_code"] = 0.8
                    data.field_confidence["city"] = 0.75
                    break

        # Extract street from address if not yet found
        if data.property_address and not data.street:
            street_match = re.search(
                r"([A-ZÄÖÜ][a-zäöüß]+(?:straße|gasse|weg|platz|ring)\s+\d+[a-z]?(?:/\d+)?)",
                data.property_address, re.IGNORECASE,
            )
            if street_match:
                data.street = street_match.group(1).strip()
                data.field_confidence["street"] = 0.7

        # Extract postal code + city from address if not yet found
        if data.property_address and not data.postal_code:
            for pattern in [
                r"(\d{4})\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)",
                r"(\d{4})\s+(\w+)",
            ]:
                match = re.search(pattern, data.property_address)
                if match:
                    data.postal_code = match.group(1)
                    data.city = match.group(2).strip()
                    data.field_confidence["postal_code"] = 0.7
                    data.field_confidence["city"] = 0.65
                    break

    # --- Rent amounts extraction ---

    def _extract_rent_amounts(self, text: str, data: RentAdjustmentData) -> None:
        """Extract current (old) and new rent amounts"""
        # Amount pattern: "640,00" or "1.234,56" or "640 00" (OCR noise)
        amt = r"(\d{1,3}(?:\.\d{3})*(?:[,\s]\d{2})?)"

        # --- New rent (most important) ---
        new_rent_patterns = [
            # "neuer Mietzins: EUR 680,00"
            rf"neuer?\s+(?:haupt)?m[ie]{{1,2}}[tz]zins[:\s]+(?:EUR|€)?\s*{amt}",
            # "neue Miete: EUR 680,00"
            rf"neue\s+miete[:\s]+(?:EUR|€)?\s*{amt}",
            # "erhöhter Mietzins: EUR 680,00"
            rf"erh.{{0,2}}hter?\s+(?:haupt)?m[ie]{{1,2}}[tz]zins[:\s]+(?:EUR|€)?\s*{amt}",
            # "Mietzins ab ... EUR 680,00" or "Mietzins ab 01.05.2024: EUR 680,00"
            rf"m[ie]{{1,2}}[tz]zins\s+ab\s+[\d.]+[:\s]+(?:EUR|€)?\s*{amt}",
            # "beträgt ab ... EUR 680,00"
            rf"betr.{{0,2}}gt\s+ab\s+[\d.\s]+(?:EUR|€)\s*{amt}",
            # "auf EUR 680,00 erhöht" / "auf € 680,00 angepasst"
            rf"auf\s+(?:EUR|€)\s*{amt}\s+(?:erh.{{0,2}}ht|angepasst|valorisiert)",
            # "angepasst auf EUR 680,00"
            rf"(?:angepasst|erh.{{0,2}}ht|valorisiert)\s+auf\s+(?:EUR|€)\s*{amt}",
            # "neu: EUR 680,00"
            rf"neu[:\s]+(?:EUR|€)\s*{amt}",
        ]

        for pattern in new_rent_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                raw = re.sub(r"(\d)\s(\d{2})$", r"\1,\2", raw)
                amount = self._parse_amount(raw)
                if amount and self.MIN_REASONABLE_RENT <= amount <= self.MAX_REASONABLE_RENT:
                    data.new_monthly_rent = amount
                    data.field_confidence["new_monthly_rent"] = 0.9
                    break

        # --- Current (old) rent ---
        old_rent_patterns = [
            # "bisheriger Mietzins: EUR 640,00"
            rf"bisher(?:iger?)?\s+(?:haupt)?m[ie]{{1,2}}[tz]zins[:\s]+(?:EUR|€)?\s*{amt}",
            # "alter Mietzins: EUR 640,00"
            rf"alter?\s+(?:haupt)?m[ie]{{1,2}}[tz]zins[:\s]+(?:EUR|€)?\s*{amt}",
            # "derzeitiger/aktueller Mietzins: EUR 640,00"
            rf"(?:derzeitig|aktuell)(?:er?)?\s+(?:haupt)?m[ie]{{1,2}}[tz]zins[:\s]+(?:EUR|€)?\s*{amt}",
            # "bisherige Miete: EUR 640,00"
            rf"bisher(?:ige?)?\s+miete[:\s]+(?:EUR|€)?\s*{amt}",
            # "Mietzins von EUR 640,00 auf EUR 680,00"
            rf"m[ie]{{1,2}}[tz]zins\s+von\s+(?:EUR|€)?\s*{amt}\s+auf",
            # "von EUR 640,00 auf"
            rf"von\s+(?:EUR|€)\s*{amt}\s+auf\s+(?:EUR|€)",
            # "bisher: EUR 640,00"
            rf"bisher[:\s]+(?:EUR|€)\s*{amt}",
            # "alt: EUR 640,00"
            rf"alt[:\s]+(?:EUR|€)\s*{amt}",
        ]

        for pattern in old_rent_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                raw = re.sub(r"(\d)\s(\d{2})$", r"\1,\2", raw)
                amount = self._parse_amount(raw)
                if amount and self.MIN_REASONABLE_RENT <= amount <= self.MAX_REASONABLE_RENT:
                    data.current_monthly_rent = amount
                    data.field_confidence["current_monthly_rent"] = 0.85
                    break

        # --- Adjustment percentage ---
        pct_patterns = [
            # "Erhöhung um 3,5%" or "Anpassung um 2,8%"
            r"(?:erh.{0,2}hung|anpassung|steigerung|valorisierung)\s+(?:um|von)\s+(\d{1,2}[.,]\d{1,2})\s*%",
            # "um 3,5 % erhöht" or "um 2,8 % angepasst"
            r"um\s+(\d{1,2}[.,]\d{1,2})\s*%\s+(?:erh.{0,2}ht|angepasst|valorisiert)",
            # "3,5 %" standalone near index/anpassung context
            r"(?:index|vpi|verbraucherpreis)\w*\s+(?:von\s+)?(\d{1,2}[.,]\d{1,2})\s*%",
        ]

        for pattern in pct_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).replace(",", ".")
                try:
                    pct = Decimal(raw)
                    if Decimal("0.1") <= pct <= Decimal("30.0"):
                        data.adjustment_percentage = pct
                        data.field_confidence["adjustment_percentage"] = 0.8
                        break
                except (InvalidOperation, ValueError):
                    continue

        # --- Adjustment amount (absolute EUR difference) ---
        diff_patterns = [
            # "Erhöhung um EUR 40,00" or "Anpassung um € 40,00"
            rf"(?:erh.{{0,2}}hung|anpassung|differenz|mehrmiete)\s+(?:um|von|betr.{{0,2}}gt)\s+(?:EUR|€)\s*{amt}",
            # "um EUR 40,00 erhöht"
            rf"um\s+(?:EUR|€)\s*{amt}\s+(?:erh.{{0,2}}ht|angepasst)",
        ]

        for pattern in diff_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                raw = re.sub(r"(\d)\s(\d{2})$", r"\1,\2", raw)
                amount = self._parse_amount(raw)
                if amount and Decimal("1.00") <= amount <= Decimal("2000.00"):
                    data.adjustment_amount = amount
                    data.field_confidence["adjustment_amount"] = 0.8
                    break

    # --- Date extraction ---

    def _extract_dates(self, text: str, data: RentAdjustmentData) -> None:
        """Extract effective date and notice date"""
        d = r"(\d{1,2})[.\s]+(\d{1,2})[.\s]+(\d{4})"

        # Effective date (when new rent takes effect)
        effective_patterns = [
            rf"(?:wirksam|wirkung|gültig|gueltig|gilt)\s+(?:ab|vom|per)[:\s]+{d}",
            rf"(?:ab|per)\s+(?:dem\s+)?{d}\s+(?:beträgt|gilt|wird)",
            rf"(?:ab|per)\s+{d}",
            rf"(?:mit\s+wirkung\s+(?:vom|ab))[:\s]+{d}",
            rf"(?:neue|angepasste)\s+miete\s+ab[:\s]+{d}",
            rf"(?:neuer|angepasster)\s+mietzins\s+ab[:\s]+{d}",
            # "Stichtag: 01.05.2024"
            rf"stichtag[:\s]+{d}",
        ]

        for pattern in effective_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    day = int(match.group(1))
                    month = int(match.group(2))
                    year = int(match.group(3))
                    date = datetime(year, month, day)
                    if datetime(2000, 1, 1) <= date <= datetime(2050, 12, 31):
                        data.effective_date = date
                        data.field_confidence["effective_date"] = 0.9
                        break
                except (ValueError, IndexError):
                    continue

        # Notice date (date of the letter itself)
        notice_patterns = [
            rf"(?:datum|wien|graz|linz|salzburg|innsbruck|klagenfurt),?\s+(?:am\s+|den\s+)?{d}",
            rf"(?:vom|am)\s+{d}",
        ]

        for pattern in notice_patterns:
            match = re.search(pattern, text[:1000], re.IGNORECASE)
            if match:
                try:
                    day = int(match.group(1))
                    month = int(match.group(2))
                    year = int(match.group(3))
                    date = datetime(year, month, day)
                    if datetime(2000, 1, 1) <= date <= datetime(2050, 12, 31):
                        # Don't use effective_date as notice_date
                        if data.effective_date is None or date != data.effective_date:
                            data.notice_date = date
                            data.field_confidence["notice_date"] = 0.7
                            break
                except (ValueError, IndexError):
                    continue

    # --- Parties extraction ---

    def _extract_parties(self, text: str, data: RentAdjustmentData) -> None:
        """Extract tenant and landlord names"""
        # Tenant
        tenant_patterns = [
            r"(?:mieter(?:in)?|mietpartei)[:\s]+([^\n,;]+)",
            r"(?:an|gerichtet\s+an)[:\s]+(?:Herr|Frau|Herrn)?\s*([^\n,;]+)",
            r"(?:sehr\s+geehrte[r]?)\s+(?:Herr|Frau)\s+([^\n,;!]+)",
        ]
        for pattern in tenant_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = self._normalize_party_name(match.group(1))
                if 2 < len(name) < 60:
                    data.tenant_name = name
                    data.field_confidence["tenant_name"] = 0.75
                    break

        # Landlord
        landlord_patterns = [
            r"(?:vermieter(?:in)?|hausverwaltung|verwaltung)[:\s]+([^\n,;]+)",
            r"(?:mit\s+freundlichen\s+grüßen|mfg|hochachtungsvoll)[\s\n]+([^\n,;]+)",
        ]
        for pattern in landlord_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = self._normalize_party_name(match.group(1))
                if 2 < len(name) < 60:
                    data.landlord_name = name
                    data.field_confidence["landlord_name"] = 0.7
                    break

    # --- Adjustment reason extraction ---

    def _extract_adjustment_reason(self, text: str, data: RentAdjustmentData) -> None:
        """Extract the reason for the rent adjustment"""
        text_lower = text.lower()

        reason_checks = [
            ("Indexanpassung (VPI)", [
                "verbraucherpreisindex", "vpi", "indexanpassung",
                "index-anpassung", "inflationsanpassung",
            ]),
            ("Wertsicherung", [
                "wertsicherung", "wertsicherungsklausel", "valorisierung",
            ]),
            ("Mietzinserhöhung §12 MRG", [
                "§12", "§ 12", "par 12", "paragraph 12",
            ]),
            ("Mietzinserhöhung §45 MRG", [
                "§45", "§ 45", "par 45", "paragraph 45",
            ]),
            ("Betriebskostenanpassung", [
                "betriebskostenanpassung", "betriebskostenerhöhung",
                "betriebskostenerhoehung", "bk-anpassung",
            ]),
            ("Mietzinserhöhung", [
                "mietzinserhöhung", "mietzinserhoehung",
                "mieterhöhung", "mieterhoehung",
                "mietanpassung", "mietzinsanpassung",
            ]),
        ]

        for reason, keywords in reason_checks:
            for kw in keywords:
                if kw in text_lower:
                    data.adjustment_reason = reason
                    data.field_confidence["adjustment_reason"] = 0.85
                    return

    # --- Betriebskosten adjustment extraction ---

    def _extract_betriebskosten(self, text: str, data: RentAdjustmentData) -> None:
        """Extract operating cost adjustments if present"""
        amt = r"(\d{1,3}(?:\.\d{3})*(?:[,\s]\d{2})?)"

        # New BK
        new_bk_patterns = [
            rf"neue\s+betriebskosten[:\s]+(?:EUR|€)?\s*{amt}",
            rf"betriebskosten\s+(?:neu|ab)[:\s]+(?:EUR|€)?\s*{amt}",
            rf"bk\s+neu[:\s]+(?:EUR|€)?\s*{amt}",
        ]
        for pattern in new_bk_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                raw = re.sub(r"(\d)\s(\d{2})$", r"\1,\2", raw)
                amount = self._parse_amount(raw)
                if amount and Decimal("10.00") <= amount <= Decimal("2000.00"):
                    data.new_betriebskosten = amount
                    data.field_confidence["new_betriebskosten"] = 0.8
                    break

        # Old BK
        old_bk_patterns = [
            rf"bisher(?:ige?)?\s+betriebskosten[:\s]+(?:EUR|€)?\s*{amt}",
            rf"betriebskosten\s+(?:bisher|alt)[:\s]+(?:EUR|€)?\s*{amt}",
            rf"bk\s+(?:bisher|alt)[:\s]+(?:EUR|€)?\s*{amt}",
        ]
        for pattern in old_bk_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                raw = re.sub(r"(\d)\s(\d{2})$", r"\1,\2", raw)
                amount = self._parse_amount(raw)
                if amount and Decimal("10.00") <= amount <= Decimal("2000.00"):
                    data.current_betriebskosten = amount
                    data.field_confidence["current_betriebskosten"] = 0.75
                    break

    # --- Derived fields ---

    def _derive_calculated_fields(self, data: RentAdjustmentData) -> None:
        """Calculate missing fields from available data"""
        # Calculate adjustment_amount if we have both rents
        if data.new_monthly_rent and data.current_monthly_rent and not data.adjustment_amount:
            data.adjustment_amount = data.new_monthly_rent - data.current_monthly_rent
            data.field_confidence["adjustment_amount"] = 0.95

        # Calculate adjustment_percentage if we have both rents
        if data.new_monthly_rent and data.current_monthly_rent and not data.adjustment_percentage:
            if data.current_monthly_rent > 0:
                pct = ((data.new_monthly_rent - data.current_monthly_rent) / data.current_monthly_rent) * 100
                data.adjustment_percentage = round(pct, 2)
                data.field_confidence["adjustment_percentage"] = 0.9

        # Calculate new_monthly_rent from current + amount
        if not data.new_monthly_rent and data.current_monthly_rent and data.adjustment_amount:
            data.new_monthly_rent = data.current_monthly_rent + data.adjustment_amount
            data.field_confidence["new_monthly_rent"] = 0.85

        # Calculate current_monthly_rent from new - amount
        if not data.current_monthly_rent and data.new_monthly_rent and data.adjustment_amount:
            data.current_monthly_rent = data.new_monthly_rent - data.adjustment_amount
            data.field_confidence["current_monthly_rent"] = 0.85

    # --- Helper methods ---

    @staticmethod
    def _parse_amount(text: str) -> Optional[Decimal]:
        """Parse Austrian/German number format: 1.234,56 or 1234,56 -> 1234.56"""
        if not text:
            return None
        try:
            cleaned = text.strip().replace(" ", "")
            if "." in cleaned and "," in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            elif "." in cleaned:
                parts = cleaned.split(".")
                if len(parts) == 2 and len(parts[1]) == 3:
                    cleaned = cleaned.replace(".", "")
                elif len(parts) > 2:
                    cleaned = cleaned.replace(".", "")

            is_negative = cleaned.startswith("-")
            cleaned = cleaned.lstrip("-")
            val = Decimal(cleaned)
            if is_negative:
                val = -val
            return val
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _normalize_party_name(raw_name: str) -> str:
        """Remove titles and trailing residence/birth details from extracted names."""
        name = raw_name.strip()
        name = re.sub(r"^\(.*?\)\s*", "", name)
        name = re.sub(r"^(?:Herr|Frau|Herrn|Di|DI|Mag|Dr)\.?\s+", "", name, flags=re.IGNORECASE)
        name = re.sub(r"^[:\s]+", "", name)
        name = re.split(r",\s*(?:wohnhaft|geboren)\b", name, maxsplit=1, flags=re.IGNORECASE)[0]
        return name.strip().rstrip(",")

    @staticmethod
    def _calculate_confidence(data: RentAdjustmentData) -> float:
        """Calculate overall extraction confidence"""
        # Critical fields for rent adjustment
        critical_fields = [
            "new_monthly_rent",
            "effective_date",
        ]

        # Important fields
        important_fields = [
            "current_monthly_rent",
            "property_address",
            "adjustment_reason",
            "adjustment_percentage",
            "tenant_name",
            "landlord_name",
        ]

        score = 0.0
        total_weight = 0.0

        for f in critical_fields:
            total_weight += 2.0
            if getattr(data, f) is not None:
                confidence = data.field_confidence.get(f, 0.5)
                score += confidence * 2.0

        for f in important_fields:
            total_weight += 1.0
            if getattr(data, f) is not None:
                confidence = data.field_confidence.get(f, 0.5)
                score += confidence * 1.0

        return round(score / total_weight, 2) if total_weight > 0 else 0.0
