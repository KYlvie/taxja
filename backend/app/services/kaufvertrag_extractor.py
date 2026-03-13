"""
Kaufvertrag (Property Purchase Contract) Extractor

Parses OCR text from Austrian property purchase contracts (Kaufverträge) and extracts
structured data including property address, purchase price, buyer/seller information,
and notary details.

This extractor is used for Phase 3 of the property asset management feature to
automatically populate property registration forms from uploaded contract documents.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class KaufvertragData:
    """Structured data from a Kaufvertrag (property purchase contract)"""
    # Property information
    property_address: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    
    # Purchase details
    purchase_price: Optional[Decimal] = None
    purchase_date: Optional[datetime] = None
    
    # Value breakdown (if available)
    building_value: Optional[Decimal] = None
    land_value: Optional[Decimal] = None
    
    # Purchase costs
    grunderwerbsteuer: Optional[Decimal] = None  # Property transfer tax
    notary_fees: Optional[Decimal] = None
    registry_fees: Optional[Decimal] = None  # Eintragungsgebühr
    
    # Parties
    buyer_name: Optional[str] = None
    seller_name: Optional[str] = None
    
    # Notary information
    notary_name: Optional[str] = None
    notary_location: Optional[str] = None
    
    # Building details (if available)
    construction_year: Optional[int] = None
    property_type: Optional[str] = None  # Wohnung, Haus, Grundstück
    
    # Confidence scores per field
    field_confidence: Dict[str, float] = field(default_factory=dict)
    
    # Overall confidence
    confidence: float = 0.0


class KaufvertragExtractor:
    """Extract structured data from Kaufvertrag OCR text"""
    
    def extract(self, text: str) -> KaufvertragData:
        """Main extraction method"""
        data = KaufvertragData()
        
        # Extract property information
        self._extract_property_address(text, data)
        
        # Extract purchase details
        self._extract_purchase_price(text, data)
        self._extract_purchase_date(text, data)
        
        # Extract value breakdown
        self._extract_value_breakdown(text, data)
        
        # Extract purchase costs
        self._extract_purchase_costs(text, data)
        
        # Extract parties
        self._extract_buyer_seller(text, data)
        
        # Extract notary information
        self._extract_notary_info(text, data)
        
        # Extract building details
        self._extract_building_details(text, data)
        
        # Calculate overall confidence
        data.confidence = self._calculate_confidence(data)
        
        return data
    
    def to_dict(self, data: KaufvertragData) -> Dict[str, Any]:
        """Convert KaufvertragData to dictionary for storage"""
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
    
    def _extract_property_address(self, text: str, data: KaufvertragData) -> None:
        """Extract property address from contract"""
        address_patterns = [
            # "postalischen Adresse Thenneberg 51, 2571 Altenmarkt"
            r"postalisch\w*\s+adresse\s+(.+?)(?:\.\s|$)",
            # Standard labeled formats
            r"(?:liegenschaft|grundst.{1,2}ck|objekt|wohnung)[:\s]+(.+?)(?:\n|$)",
            r"(?:gelegen|befindlich)\s+(?:in|zu)\s+(.+?)(?:\n|$)",
            r"(?:adresse|anschrift)[:\s]+(.+?)(?:\n|$)",
            # Land registry format: "EZ 123 ... KG Thenneberg"
            r"EZ\s+\d+\s+.*?KG\s+\d*\s*(.+?)(?:\n|,)",
            # Top/apartment number format
            r"(?:top|wohnung)\s+\d+[,\s]+(.+?)(?:\n|$)",
            r"im\s+hause\s+(.+?)(?:\n|$)",
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                address_text = match.group(1).strip()
                address_text = re.sub(
                    r",?\s+(?:bestehend|umfassend|mit\s+einer).*$", "",
                    address_text, flags=re.IGNORECASE,
                )
                # Clean trailing punctuation
                address_text = address_text.rstrip(".,;")
                if len(address_text) > 5:
                    data.property_address = address_text
                    data.field_confidence["property_address"] = 0.85
                    self._parse_address_components(address_text, data)
                    break
        
        if not data.property_address:
            self._extract_address_components_separately(text, data)
    
    def _parse_address_components(self, address_text: str, data: KaufvertragData) -> None:
        """Parse address into street, postal code, and city"""
        # Austrian address format variations:
        # 1. "Hauptstraße 123, 1010 Wien"
        # 2. "Hauptstraße 123/4, 1010 Wien" (with apartment number)
        # 3. "Hauptstraße 123 Top 5, 1010 Wien" (with Top number)
        # 4. "1010 Wien, Hauptstraße 123" (reversed format)
        # 5. "Hauptstraße 123-125, 1010 Wien" (range)
        
        # Pattern 1: Standard format - Street Number, PostalCode City
        pattern1 = r"^(.+?)\s+(\d+(?:[/-]\d+)?(?:\s+Top\s+\d+)?),?\s+(\d{4})\s+(.+)$"
        match = re.match(pattern1, address_text.strip(), re.IGNORECASE)
        
        if match:
            data.street = f"{match.group(1)} {match.group(2)}".strip()
            data.postal_code = match.group(3)
            data.city = match.group(4).strip()
            data.field_confidence["street"] = 0.9
            data.field_confidence["postal_code"] = 0.95
            data.field_confidence["city"] = 0.9
            return
        
        # Pattern 2: Reversed format - PostalCode City, Street Number
        pattern2 = r"^(\d{4})\s+(.+?),\s+(.+?)\s+(\d+(?:[/-]\d+)?)$"
        match = re.match(pattern2, address_text.strip())
        
        if match:
            data.postal_code = match.group(1)
            data.city = match.group(2).strip()
            data.street = f"{match.group(3)} {match.group(4)}".strip()
            data.field_confidence["street"] = 0.85
            data.field_confidence["postal_code"] = 0.95
            data.field_confidence["city"] = 0.85
            return
        
        # Pattern 3: Just postal code and city (street might be elsewhere)
        postal_city_pattern = r"(\d{4})\s+(.+)$"
        postal_match = re.search(postal_city_pattern, address_text)
        if postal_match:
            data.postal_code = postal_match.group(1)
            data.city = postal_match.group(2).strip()
            data.field_confidence["postal_code"] = 0.9
            data.field_confidence["city"] = 0.85
            
            # Street is everything before postal code
            street_part = address_text[:postal_match.start()].strip().rstrip(",")
            if street_part:
                data.street = street_part
                data.field_confidence["street"] = 0.8
    
    def _extract_address_components_separately(self, text: str, data: KaufvertragData) -> None:
        """Extract address components when full address pattern doesn't match"""
        # Look for postal code (4 digits)
        postal_pattern = r"\b(\d{4})\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[a-zäöüß]+)*)\b"
        postal_match = re.search(postal_pattern, text)
        if postal_match:
            data.postal_code = postal_match.group(1)
            data.city = postal_match.group(2)
            data.field_confidence["postal_code"] = 0.8
            data.field_confidence["city"] = 0.75
    
    # --- Purchase price extraction ---
    
    def _extract_purchase_price(self, text: str, data: KaufvertragData) -> None:
        """Extract purchase price (Kaufpreis)"""
        # Austrian amount pattern: 273.000,- or 273.000,00 or 273.000,-- or 273000
        amt = r"(\d{1,3}(?:\.\d{3})*(?:,[\d-]+)?)"

        price_patterns = [
            # "betragt EUR 273.000,-" (OCR: beträgt → betragt)
            # Allow text between "kaufpreis" and "betr" (sentence gap)
            rf"kaufpreis.{{0,200}}?betr.{{0,2}}gt\s+(?:EUR|€)\s*{amt}",
            # Standard: "Kaufpreis: EUR 273.000,00"
            rf"kaufpreis[:\s]+(?:EUR|€)?\s*{amt}",
            rf"gesamtkaufpreis[:\s]+(?:EUR|€)?\s*{amt}",
            rf"kaufsumme[:\s]+(?:EUR|€)?\s*{amt}",
            rf"verkaufspreis[:\s]+(?:EUR|€)?\s*{amt}",
            # "Kaufpreis von EUR 273.000,-"
            rf"kaufpreis\s+von\s+(?:EUR|€)\s*{amt}",
            # "Kaufpreis in Höhe von EUR 273.000,-"
            rf"kaufpreis\s+in\s+h.{{1,2}}he\s+von\s+(?:EUR|€)\s*{amt}",
            # Fallback: "EUR 273.000" near "Kaufpreis" context (within 300 chars)
            rf"kaufpreis.{{0,300}}?(?:EUR|€)\s*{amt}",
        ]

        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                raw = match.group(1)
                # Clean trailing dashes: "273.000,-" or "273.000,--" → "273.000"
                raw = re.sub(r",-+$", "", raw)
                amount = self._parse_amount(raw)
                if amount and amount > Decimal("1000"):  # Sanity check
                    data.purchase_price = amount
                    data.field_confidence["purchase_price"] = 0.9
                    break
    
    def _extract_purchase_date(self, text: str, data: KaufvertragData) -> None:
        """Extract purchase/contract date"""
        # Date token allowing optional spaces after dots: "29. 9. 1958" or "29.9.1958"
        d = r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})"

        # Prioritised patterns — most specific first
        date_patterns = [
            # Explicit contract-date labels
            rf"(?:vertragsdatum|datum|abgeschlossen\s+am)[:\s]+{d}",
            rf"(?:unterzeichnet|unterschrieben)\s+am[:\s]+{d}",
            rf"geschlossen\s+am[:\s]+{d}",
            # City + date on signature line
            rf"M.dling,?\s+(?:am\s+)?{d}",
            rf"Wien,?\s+(?:am\s+)?{d}",
            rf"Baden,?\s+(?:am\s+)?{d}",
            rf"Graz,?\s+(?:am\s+)?{d}",
            rf"Linz,?\s+(?:am\s+)?{d}",
            rf"Salzburg,?\s+(?:am\s+)?{d}",
            rf"Innsbruck,?\s+(?:am\s+)?{d}",
            # Generic city + date (but NOT "vom DD.MM.YYYY" which is often a reference)
            rf"[A-ZÄÖÜ][a-zäöüß]{{2,}},?\s+(?:am\s+)?{d}",
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    day = int(match.group(1))
                    month = int(match.group(2))
                    year = int(match.group(3))
                    date = datetime(year, month, day)

                    # Sanity check: date should be reasonable (not too old)
                    if datetime(2000, 1, 1) <= date <= datetime.now():
                        data.purchase_date = date
                        data.field_confidence["purchase_date"] = 0.85
                        break
                except (ValueError, IndexError):
                    continue

        # NOTE: We intentionally do NOT fall back to "vom DD.MM.YYYY" patterns
        # because in Kaufverträge those are almost always references to other
        # documents (Einantwortungsurkunde, Pfandurkunde, etc.), not the
        # contract signing date. Better to leave purchase_date as None than
        # to extract a wrong date.
    
    # --- Value breakdown extraction ---
    
    def _extract_value_breakdown(self, text: str, data: KaufvertragData) -> None:
        """Extract building value and land value if specified"""
        # Building value (Gebäudewert)
        building_patterns = [
            r"geb[aä].{0,2}udewert[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
            r"wert\s+des\s+geb[aä].{0,2}udes[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
        ]
        
        for pattern in building_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = self._parse_amount(match.group(1))
                if amount and amount > Decimal("0"):
                    data.building_value = amount
                    data.field_confidence["building_value"] = 0.85
                    break
        
        # Land value (Grundwert, Bodenwert)
        land_patterns = [
            r"(?:grundwert|bodenwert)[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
            r"wert\s+des\s+grundst.{1,2}cks[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)",
        ]
        
        for pattern in land_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = self._parse_amount(match.group(1))
                if amount and amount > Decimal("0"):
                    data.land_value = amount
                    data.field_confidence["land_value"] = 0.85
                    break
        
        # If we have purchase price but not building/land split, estimate
        if data.purchase_price and not data.building_value:
            # Austrian convention: ~80% building, ~20% land
            data.building_value = (data.purchase_price * Decimal("0.8")).quantize(Decimal("0.01"))
            data.land_value = (data.purchase_price * Decimal("0.2")).quantize(Decimal("0.01"))
            data.field_confidence["building_value"] = 0.5  # Lower confidence for estimate
            data.field_confidence["land_value"] = 0.5
    
    # --- Purchase costs extraction ---
    
    def _extract_purchase_costs(self, text: str, data: KaufvertragData) -> None:
        """Extract purchase-related costs"""
        # Amount pattern: handles "12.558,—" "12.558,00" "12.558,-" "12558"
        # NOTE: \u2014 is em-dash, must use Unicode escape in character class
        amt = r"(\d{1,3}(?:\.\d{3})*(?:,[0-9\u2014\-]+)?)"

        # Grunderwerbsteuer (property transfer tax)
        # Text often says: "Grunderwerbsteuer von 3,5% ... ausgehend von EUR 273.000,-- EUR 12.558,—"
        # We want the LAST EUR amount in the Grunderwerbsteuer context (the actual tax, not the base)
        grunderwerb_patterns = [
            # Direct label: "Grunderwerbsteuer: EUR 12.558"
            rf"grunderwerbs?steuer[:\s]+(?:EUR|€)\s*{amt}",
        ]

        # First try direct patterns
        found_grest = False
        for pattern in grunderwerb_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = re.sub(r"[,][\u2014\-]+$", "", match.group(1))
                amount = self._parse_amount(raw)
                if amount and Decimal("0") < amount < (data.purchase_price or Decimal("999999999")):
                    data.grunderwerbsteuer = amount
                    data.field_confidence["grunderwerbsteuer"] = 0.85
                    found_grest = True
                    break

        # Fallback: scan ALL "Grunderwerbsteuer" occurrences, find EUR amounts nearby
        if not found_grest:
            amounts = []
            for gm in re.finditer(
                r"grunderwerbs?steuer", text, re.IGNORECASE
            ):
                section = text[gm.end():gm.end() + 400]
                for m in re.finditer(rf"(?:EUR|€)\s*{amt}", section):
                    raw = re.sub(r"[,][\u2014\-]+$", "", m.group(1))
                    a = self._parse_amount(raw)
                    if a and a > Decimal("0"):
                        amounts.append(a)
            # Pick the smallest amount that's < 10% of purchase price (the tax, not the base)
            if amounts:
                candidates = [a for a in amounts
                              if data.purchase_price is None
                              or a < data.purchase_price * Decimal("0.1")]
                if candidates:
                    data.grunderwerbsteuer = min(candidates)
                    data.field_confidence["grunderwerbsteuer"] = 0.75

        # Notary fees (Notarkosten, Notargebühren)
        notary_fee_patterns = [
            rf"notarkosten[:\s]+(?:EUR|€)?\s*{amt}",
            rf"notargeb.{{1,2}}hren[:\s]+(?:EUR|€)?\s*{amt}",
            rf"geb.{{1,2}}hren\s+des\s+notars[:\s]+(?:EUR|€)?\s*{amt}",
        ]

        for pattern in notary_fee_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = re.sub(r"[,][\u2014\-]+$", "", match.group(1))
                amount = self._parse_amount(raw)
                if amount and amount > Decimal("0"):
                    data.notary_fees = amount
                    data.field_confidence["notary_fees"] = 0.8
                    break

        # Registry fees (Eintragungsgebühr, Grundbuchgebühr)
        registry_patterns = [
            rf"eintragungsgeb.{{1,2}}hr[:\s]+(?:EUR|€)?\s*{amt}",
            rf"grundbuchgeb.{{1,2}}hr[:\s]+(?:EUR|€)?\s*{amt}",
        ]

        for pattern in registry_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = re.sub(r"[,][\u2014\-]+$", "", match.group(1))
                amount = self._parse_amount(raw)
                if amount and amount > Decimal("0"):
                    data.registry_fees = amount
                    data.field_confidence["registry_fees"] = 0.8
                    break
    
    # --- Parties extraction ---
    
    def _extract_buyer_seller(self, text: str, data: KaufvertragData) -> None:
        """Extract buyer and seller names"""
        # Strategy 1: Line-based search for "als Käufer/Verkäufer" pattern
        # OCR text often has noise chars at line start, and name may span multiple lines
        lines = text.split("\n")
        cleaned_lines = [line.strip() for line in lines]

        # Find seller: look for "als Verkaufer" line, then scan backwards for name
        for i, line in enumerate(cleaned_lines):
            if re.search(r"als\s+verk.{0,2}ufer", line, re.IGNORECASE):
                # Scan backwards to find name (usually "Herrn/Frau Name, geb. ...")
                for j in range(i - 1, max(i - 5, -1), -1):
                    name_match = re.search(
                        r"(?:Herrn?|Frau)\s+(.+?)(?:,\s*geb|$)",
                        cleaned_lines[j], re.IGNORECASE,
                    )
                    if name_match:
                        name = name_match.group(1).strip().rstrip(",")
                        if len(name) > 3:
                            data.seller_name = name
                            data.field_confidence["seller_name"] = 0.85
                            break
                # Also check same line
                if not data.seller_name:
                    name_match = re.search(
                        r"(?:Herrn?|Frau)\s+(.+?)(?:,\s*geb|$)",
                        line, re.IGNORECASE,
                    )
                    if name_match:
                        name = name_match.group(1).strip().rstrip(",")
                        if len(name) > 3:
                            data.seller_name = name
                            data.field_confidence["seller_name"] = 0.85
                break

        # Find buyer: look for "als Käufer/Kaufer" line
        for i, line in enumerate(cleaned_lines):
            if re.search(r"als\s+k.{0,2}ufer", line, re.IGNORECASE):
                for j in range(i - 1, max(i - 5, -1), -1):
                    name_match = re.search(
                        r"(?:Herrn?|Frau)\s+(.+?)(?:,\s*geb|$)",
                        cleaned_lines[j], re.IGNORECASE,
                    )
                    if name_match:
                        name = name_match.group(1).strip().rstrip(",")
                        if len(name) > 3:
                            data.buyer_name = name
                            data.field_confidence["buyer_name"] = 0.85
                            break
                if not data.buyer_name:
                    name_match = re.search(
                        r"(?:Herrn?|Frau)\s+(.+?)(?:,\s*geb|$)",
                        line, re.IGNORECASE,
                    )
                    if name_match:
                        name = name_match.group(1).strip().rstrip(",")
                        if len(name) > 3:
                            data.buyer_name = name
                            data.field_confidence["buyer_name"] = 0.85
                break

        # Strategy 2: Fallback to original regex patterns
        if not data.buyer_name:
            buyer_patterns = [
                r"k.{1,2}ufer(?:in)?[:\s]+(.+?)(?:\n|,\s+geboren)",
                r"erwerber(?:in)?[:\s]+(.+?)(?:\n|,\s+geboren)",
            ]
            for pattern in buyer_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    name = match.group(1).strip().rstrip(",")
                    name = re.sub(r"^(?:Herr|Frau|Dr\.|Mag\.)\s+", "", name, flags=re.IGNORECASE)
                    if len(name) > 3:
                        data.buyer_name = name
                        data.field_confidence["buyer_name"] = 0.7
                        break

        if not data.seller_name:
            seller_patterns = [
                r"verk.{1,2}ufer(?:in)?[:\s]+(.+?)(?:\n|,\s+geboren)",
                r"ver.{1,2}u.{1,2}erer(?:in)?[:\s]+(.+?)(?:\n|,\s+geboren)",
            ]
            for pattern in seller_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    name = match.group(1).strip().rstrip(",")
                    name = re.sub(r"^(?:Herr|Frau|Dr\.|Mag\.)\s+", "", name, flags=re.IGNORECASE)
                    if len(name) > 3:
                        data.seller_name = name
                        data.field_confidence["seller_name"] = 0.7
                        break
    
    # --- Notary information extraction ---
    
    def _extract_notary_info(self, text: str, data: KaufvertragData) -> None:
        """Extract notary name and location"""
        # Notary name
        notary_patterns = [
            r"notar[:\s]+(.+?)(?:\n|,)",
            r"notarin[:\s]+(.+?)(?:\n|,)",
            r"(?:Dr\.|Mag\.)\s+([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+),?\s+(?:Notar|Notarin)",
        ]
        
        for pattern in notary_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3 and not name.lower().startswith("in"):
                    data.notary_name = name
                    data.field_confidence["notary_name"] = 0.75
                    break
        
        # Notary location (usually Wien or other Austrian cities)
        location_pattern = r"Notar(?:in)?\s+in\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[a-zäöüß]+)*)"
        location_match = re.search(location_pattern, text, re.IGNORECASE)
        if location_match:
            data.notary_location = location_match.group(1).strip()
            data.field_confidence["notary_location"] = 0.8
    
    # --- Building details extraction ---
    
    def _extract_building_details(self, text: str, data: KaufvertragData) -> None:
        """Extract building construction year and property type"""
        # Construction year (Baujahr, Errichtungsjahr)
        year_patterns = [
            r"baujahr[:\s]+(\d{4})",
            r"errichtungsjahr[:\s]+(\d{4})",
            r"erbaut\s+(?:im\s+Jahr\s+)?(\d{4})",
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                year = int(match.group(1))
                # Sanity check: year should be reasonable
                if 1800 <= year <= datetime.now().year:
                    data.construction_year = year
                    data.field_confidence["construction_year"] = 0.85
                    break
        
        # Property type
        text_lower = text.lower()
        if "wohnung" in text_lower or "eigentumswohnung" in text_lower:
            data.property_type = "Wohnung"
            data.field_confidence["property_type"] = 0.8
        elif "einfamilienhaus" in text_lower or "haus" in text_lower:
            data.property_type = "Haus"
            data.field_confidence["property_type"] = 0.75
        elif "grundstück" in text_lower or "baugrund" in text_lower:
            data.property_type = "Grundstück"
            data.field_confidence["property_type"] = 0.8
    
    # --- Helper methods ---
    
    @staticmethod
    def _parse_amount(text: str) -> Optional[Decimal]:
        """Parse Austrian/German number format: 1.234,56 or 1234,56 -> 1234.56"""
        if not text:
            return None
        try:
            # Remove spaces
            cleaned = text.strip().replace(" ", "")
            
            # Handle both . and , as thousand separator, and , or . as decimal
            # Austrian format: 1.234,56
            # Also accept: 1234.56 (international)
            
            # Check if it has both . and ,
            if "." in cleaned and "," in cleaned:
                # Austrian format: . is thousand, , is decimal
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "," in cleaned:
                # Only comma: assume it's decimal separator
                cleaned = cleaned.replace(",", ".")
            elif "." in cleaned:
                # Only dots: check if it's thousand separator or decimal
                # If dots appear in groups of 3 from the right, it's thousand separator
                # e.g., "200.000" or "1.234.567" -> thousand separator
                # e.g., "200.5" -> decimal separator
                parts = cleaned.split(".")
                if len(parts) == 2 and len(parts[1]) == 3:
                    # Could be either 200.000 (thousand) or 200.500 (decimal)
                    # In Austrian contracts, amounts are typically whole numbers or have 2 decimals
                    # So 3 digits after dot is likely thousand separator
                    cleaned = cleaned.replace(".", "")
                elif len(parts) > 2:
                    # Multiple dots: definitely thousand separator (e.g., 1.234.567)
                    cleaned = cleaned.replace(".", "")
                # else: single dot with !=3 digits after: keep as decimal
            
            # Handle negative
            is_negative = cleaned.startswith("-")
            cleaned = cleaned.lstrip("-")
            
            val = Decimal(cleaned)
            if is_negative:
                val = -val
            return val
        except (InvalidOperation, ValueError):
            return None
    
    @staticmethod
    def _calculate_confidence(data: KaufvertragData) -> float:
        """Calculate overall extraction confidence based on extracted fields"""
        # Critical fields for property registration
        critical_fields = [
            "property_address",
            "purchase_price",
            "purchase_date",
        ]
        
        # Important but not critical fields
        important_fields = [
            "street",
            "city",
            "postal_code",
            "building_value",
            "buyer_name",
            "seller_name",
        ]
        
        # Calculate weighted score
        score = 0.0
        total_weight = 0.0
        
        # Critical fields: weight 2.0
        for field in critical_fields:
            total_weight += 2.0
            if getattr(data, field) is not None:
                confidence = data.field_confidence.get(field, 0.5)
                score += confidence * 2.0
        
        # Important fields: weight 1.0
        for field in important_fields:
            total_weight += 1.0
            if getattr(data, field) is not None:
                confidence = data.field_confidence.get(field, 0.5)
                score += confidence * 1.0
        
        return round(score / total_weight, 2) if total_weight > 0 else 0.0
