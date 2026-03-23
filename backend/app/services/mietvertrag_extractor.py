"""
Mietvertrag (Rental Contract) Extractor

Parses OCR text from Austrian rental contracts (Mietverträge) and extracts
structured data including property address, monthly rent, tenant/landlord information,
and contract terms.

This extractor is used for Phase 3 of the property asset management feature to
automatically populate property and tenant information from uploaded rental contracts.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MietvertragData:
    """Structured data from a Mietvertrag (rental contract)"""
    # Property information
    property_address: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    
    # Rental terms
    monthly_rent: Optional[Decimal] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None  # None for unlimited contracts
    
    # Additional costs
    betriebskosten: Optional[Decimal] = None  # Operating costs
    heating_costs: Optional[Decimal] = None  # Heizkosten
    deposit_amount: Optional[Decimal] = None  # Kaution
    
    # Utilities
    utilities_included: Optional[bool] = None  # Are utilities included in rent?
    
    # Parties
    tenant_name: Optional[str] = None
    landlord_name: Optional[str] = None
    
    # Contract type
    contract_type: Optional[str] = None  # Unbefristet, Befristet
    
    # Confidence scores per field
    field_confidence: Dict[str, float] = field(default_factory=dict)
    
    # Overall confidence
    confidence: float = 0.0


class MietvertragExtractor:
    """Extract structured data from Mietvertrag OCR text"""
    MIN_REASONABLE_MONTHLY_RENT = Decimal("100.00")
    MAX_REASONABLE_MONTHLY_RENT = Decimal("10000.00")
    
    def extract(self, text: str) -> MietvertragData:
        """Main extraction method"""
        data = MietvertragData()
        
        # Extract property information
        self._extract_property_address(text, data)
        
        # Extract rental terms
        self._extract_monthly_rent(text, data)
        self._extract_contract_dates(text, data)
        
        # Extract additional costs
        self._extract_additional_costs(text, data)
        
        # Extract utilities information
        self._extract_utilities_info(text, data)
        
        # Extract parties
        self._extract_tenant_landlord(text, data)
        
        # Extract contract type
        self._extract_contract_type(text, data)
        
        # Calculate overall confidence
        data.confidence = self._calculate_confidence(data)
        
        return data
    
    def to_dict(self, data: MietvertragData) -> Dict[str, Any]:
        """Convert MietvertragData to dictionary for storage"""
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
    
    def _extract_property_address(self, text: str, data: MietvertragData) -> None:
        """Extract property address from rental contract"""
        lines = text.split("\n")
        cleaned_lines = [line.strip() for line in lines]

        # Strategy 0: Look for "Objekt:" section, then "Adresse:" line right after
        # This handles the pattern: "Objekt: LAGER\nAdresse: Thenneberg 51, ..."
        for i, line in enumerate(cleaned_lines):
            if re.search(r"^(?:[^a-zA-Z]*)?objekt[:\s]", line, re.IGNORECASE):
                for j in range(i + 1, min(i + 3, len(cleaned_lines))):
                    addr_match = re.search(
                        r"adresse[:\s]+(.+)", cleaned_lines[j], re.IGNORECASE
                    )
                    if addr_match:
                        addr = addr_match.group(1).strip()
                        if len(addr) > 5:
                            data.property_address = addr
                            data.field_confidence["property_address"] = 0.9
                            self._parse_address_components(addr, data)
                            break
                if data.property_address:
                    break

        # Strategy 1: Look for MIETGEGENSTAND section and find address nearby
        if not data.property_address:
            for i, line in enumerate(cleaned_lines):
                if re.search(r"mietgegenstand", line, re.IGNORECASE):
                    # Look in the next few lines for address-like content
                    for j in range(i + 1, min(i + 8, len(cleaned_lines))):
                        # Look for "Thenneberg 51" style address or street patterns
                        addr_match = re.search(
                            r"([A-ZÄÖÜ][a-zäöüß]+(?:stra[sß]e|gasse|weg|platz|berg)\s+\d+[a-zA-Z/]*)",
                            cleaned_lines[j], re.IGNORECASE,
                        )
                        if addr_match:
                            data.property_address = addr_match.group(1).strip()
                            data.field_confidence["property_address"] = 0.85
                            self._parse_address_components(data.property_address, data)
                            break
                    if data.property_address:
                        break

        # Strategy 2: Standard labeled formats
        if not data.property_address:
            address_patterns = [
                r"(?:mietobjekt|bestandobjekt|wohnung|objekt)[:\s]+(.+?)(?:\n|$)",
                r"(?:gelegen|befindlich)\s+(?:in|zu)\s+(.+?)(?:\n|$)",
                r"(?:adresse|anschrift)[:\s]+(.+?)(?:\n|$)",
                r"(?:top|wohnung)\s+(?:nr\.?|nummer)?\s*\d+[,\s]+(.+?)(?:\n|$)",
                r"im\s+hause\s+(.+?)(?:\n|$)",
                r"lage[:\s]+(.+?)(?:\n|$)",
            ]

            for pattern in address_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    address_text = match.group(1).strip()
                    address_text = re.sub(
                        r",?\s+(?:bestehend|umfassend|mit).*$", "", address_text, flags=re.IGNORECASE
                    )
                    data.property_address = address_text
                    data.field_confidence["property_address"] = 0.85
                    self._parse_address_components(address_text, data)
                    break

        # Strategy 3: Find "Adresse:" lines in Vermieter section for property address
        if not data.property_address:
            for i, line in enumerate(cleaned_lines):
                if re.search(r"vermieter", line, re.IGNORECASE):
                    for j in range(i + 1, min(i + 6, len(cleaned_lines))):
                        addr_match = re.search(
                            r"adresse[:\s]+(.+)", cleaned_lines[j], re.IGNORECASE
                        )
                        if addr_match:
                            data.property_address = addr_match.group(1).strip()
                            data.field_confidence["property_address"] = 0.75
                            self._parse_address_components(data.property_address, data)
                            break
                    break

        # If no full address found, try to find components separately
        if not data.property_address:
            self._extract_address_components_separately(text, data)
    
    def _parse_address_components(self, address_text: str, data: MietvertragData) -> None:
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
    
    def _extract_address_components_separately(self, text: str, data: MietvertragData) -> None:
        """Extract address components when full address pattern doesn't match"""
        # Look for PLZ/Ort pattern (handles OCR noise like "PL2/ Ort", "PLZ/Ort")
        plz_patterns = [
            r"PL[ZZ2]/?\s*(?:Ort)?[:\s]+(\d{4})\s+([A-ZÄÖÜa-zäöüß]+(?:\s+[a-zäöüß]+)*)",
            r"\b(\d{4})\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[a-zäöüß]+)*)\b",
        ]
        for pattern in plz_patterns:
            postal_match = re.search(pattern, text, re.IGNORECASE)
            if postal_match:
                data.postal_code = postal_match.group(1)
                data.city = postal_match.group(2).strip()
                data.field_confidence["postal_code"] = 0.8
                data.field_confidence["city"] = 0.75
                break
    
    # --- Monthly rent extraction ---
    
    def _extract_monthly_rent(self, text: str, data: MietvertragData) -> None:
        """Extract monthly rent (Mietzins, Hauptmietzins)"""
        # Amount pattern: "320,00" or "640 00" (OCR: space instead of comma) or "320"
        amt = r"(\d{1,3}(?:\.\d{3})*(?:[,\s]\d{2})?)"

        rent_patterns = [
            # "Miete pro Monat beträgt € 320,00"
            rf"miete\s+pro\s+monat\s+betr.{{0,2}}gt\s+(?:EUR|€)\s*{amt}",
            # Standard: "Mietzins: EUR 640,00" (also matches OCR "Meetzins")
            rf"(?:haupt)?m[ie]{{1,2}}[tz]zins[:\s]+(?:EUR|€)?\s*{amt}",
            rf"monatliche\s+miete[:\s]+(?:EUR|€)?\s*{amt}",
            rf"nettomiete[:\s]+(?:EUR|€)?\s*{amt}",
            rf"grundmiete[:\s]+(?:EUR|€)?\s*{amt}",
            rf"miete[:\s]+(?:EUR|€)?\s*{amt}",
            # "Mietzins beträgt/lautet EUR 640,00"
            rf"m[ie]{{1,2}}[tz]zins\s+(?:betr.{{0,2}}gt|lautet)[:\s]+(?:EUR|€)?\s*{amt}",
            # "Betrag von EUR 640 00"
            rf"betrag\s+von\s+(?:EUR|€)\s*{amt}",
            # "Mietzins von EUR 640,00"
            rf"m[ie]{{1,2}}[tz]zins\s+von[:\s]+(?:EUR|€)?\s*{amt}",
            # "pro Monat" format
            rf"(?:EUR|€)\s*{amt}\s+pro\s+monat",
        ]

        for pattern in rent_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                # Handle "640 00" -> "640,00" (OCR space instead of comma)
                raw = re.sub(r"(\d)\s(\d{2})$", r"\1,\2", raw)
                amount = self._parse_amount(raw)
                if amount and self.MIN_REASONABLE_MONTHLY_RENT <= amount <= self.MAX_REASONABLE_MONTHLY_RENT:
                    data.monthly_rent = amount
                    data.field_confidence["monthly_rent"] = 0.9
                    break
    
    # --- Contract dates extraction ---
    
    def _extract_contract_dates(self, text: str, data: MietvertragData) -> None:
        """Extract contract start and end dates"""
        # Date token: allows "01.10.2021" or "01 10.2021" (OCR noise: space instead of dot)
        d = r"(\d{1,2})[.\s]+(\d{1,2})[.\s]+(\d{4})"

        # Start date patterns - including fuzzy OCR patterns
        start_patterns = [
            rf"(?:mietbeginn|vertragsbeginn|beginn)[:\s]+{d}",
            rf"(?:ab|vom)\s+{d}",
            rf"(?:gültig|gilt)\s+ab[:\s]+{d}",
            rf"(?:mietverhältnis|vertrag)\s+beginnt?\s+(?:am|mt|mit)[:\s]+{d}",
            rf"mit\s+wirkung\s+vom[:\s]+{d}",
            # OCR-fuzzy: "begnet mt 01.01.2024" or similar
            rf"beg\w+\s+(?:mt|mit|am)[:\s]+{d}",
            # Generic: any date after "Mietdauer" section
            rf"mietdauer.*?{d}",
        ]

        for pattern in start_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    day = int(match.group(1))
                    month = int(match.group(2))
                    year = int(match.group(3))
                    date = datetime(year, month, day)

                    if datetime(1950, 1, 1) <= date <= datetime(2050, 12, 31):
                        data.start_date = date
                        data.field_confidence["start_date"] = 0.85
                        break
                except (ValueError, IndexError):
                    continue

        # End date patterns
        end_patterns = [
            rf"(?:mietende|vertragsende|ende)[:\s]+{d}",
            rf"(?:bis|bis\s+zum)[:\s]+{d}",
            rf"(?:befristet|gültig)\s+bis[:\s]+{d}",
            rf"(?:mietverhältnis|vertrag)\s+endet\s+(?:am|sotin\s+am)[:\s]+{d}",
            # OCR-fuzzy: "endet sotin am 01 10 2024"
            rf"endet\s+\w+\s+am\s+{d}",
        ]

        for pattern in end_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    day = int(match.group(1))
                    month = int(match.group(2))
                    year = int(match.group(3))
                    date = datetime(year, month, day)

                    if datetime(1950, 1, 1) <= date <= datetime(2050, 12, 31):
                        if data.start_date is None or date > data.start_date:
                            data.end_date = date
                            data.field_confidence["end_date"] = 0.85
                            break
                except (ValueError, IndexError):
                    continue
    
    # --- Additional costs extraction ---
    
    def _extract_additional_costs(self, text: str, data: MietvertragData) -> None:
        """Extract additional costs (Betriebskosten, Heizkosten, Kaution)"""
        # Betriebskosten (operating costs)
        betriebskosten_patterns = [
            r"betriebskosten[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
            r"bk[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
            r"nebenkosten[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
        ]
        
        for pattern in betriebskosten_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = self._parse_amount(match.group(1))
                if amount and amount > Decimal("0"):
                    data.betriebskosten = amount
                    data.field_confidence["betriebskosten"] = 0.85
                    break
        
        # Heizkosten (heating costs)
        heating_patterns = [
            r"heizkosten[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
            r"hk[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
            r"heizung[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
        ]
        
        for pattern in heating_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = self._parse_amount(match.group(1))
                if amount and amount > Decimal("0"):
                    data.heating_costs = amount
                    data.field_confidence["heating_costs"] = 0.8
                    break
        
        # Kaution (deposit)
        deposit_patterns = [
            r"kaution[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
            r"sicherheitsleistung[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
            r"barkaution[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
            # Format with "in Höhe von"
            r"kaution\s+in\s+h.{1,2}he\s+von[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
            r"sicherheitsleistung\s+in\s+h.{1,2}he\s+von[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
            # Formats without decimal separator
            r"kaution[:\s]+(?:EUR|€)?\s*(\d{1,3}(?:\.\d{3})+)(?!\d)",
        ]
        
        for pattern in deposit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = self._parse_amount(match.group(1))
                if amount and amount > Decimal("0"):
                    data.deposit_amount = amount
                    data.field_confidence["deposit_amount"] = 0.85
                    break
    
    # --- Utilities information extraction ---
    
    def _extract_utilities_info(self, text: str, data: MietvertragData) -> None:
        """Extract information about utilities inclusion"""
        text_lower = text.lower()
        
        # Check for utilities excluded first (more specific patterns)
        excluded_patterns = [
            "betriebskosten exkludiert",
            "exkl. betriebskosten",
            "exklusive betriebskosten",
            "zuzüglich betriebskosten",
            "zzgl. betriebskosten",
            "kaltmiete",
            "nicht inkludiert",
            "nicht inbegriffen",
            "nicht enthalten",
        ]
        
        for pattern in excluded_patterns:
            if pattern in text_lower:
                data.utilities_included = False
                data.field_confidence["utilities_included"] = 0.8
                return
        
        # Check for utilities included
        included_patterns = [
            "betriebskosten inkludiert",
            "betriebskosten inbegriffen",
            "inkl. betriebskosten",
            "inklusive betriebskosten",
            "inkl. bk",
            "warmmiete",
        ]
        
        for pattern in included_patterns:
            if pattern in text_lower:
                data.utilities_included = True
                data.field_confidence["utilities_included"] = 0.8
                return
    
    # --- Parties extraction ---
    
    def _extract_tenant_landlord(self, text: str, data: MietvertragData) -> None:
        """Extract tenant and landlord names"""
        lines = text.split("\n")
        cleaned_lines = [line.strip() for line in lines]

        # --- Landlord (Vermieter) ---
        # Strategy: find "Vermieter" line, then look for "Name" in nearby lines
        for i, line in enumerate(cleaned_lines):
            if re.search(r"vermieter", line, re.IGNORECASE):
                # Check if name is on the same line after colon
                name_on_line = re.search(
                    r"vermieter(?:in)?[:\s]+(?!\()([\w\s\-äöüÄÖÜß]+)",
                    line, re.IGNORECASE,
                )
                if name_on_line:
                    name = self._normalize_party_name(name_on_line.group(1))
                    if len(name) > 3:
                        data.landlord_name = name
                        data.field_confidence["landlord_name"] = 0.8
                        break

                # Look for "Name ..." in the next few lines
                for j in range(i + 1, min(i + 5, len(cleaned_lines))):
                    if re.search(r"mieter", cleaned_lines[j], re.IGNORECASE) and not re.search(
                        r"vermieter", cleaned_lines[j], re.IGNORECASE
                    ):
                        break  # Hit the Mieter section, stop
                    # Match "Name:" with optional OCR noise prefix (single chars, punctuation)
                    name_match = re.match(
                        r"^(?:[^a-zA-Z]*|.{0,2}\s+)Name[:\s]+(.+)",
                        cleaned_lines[j], re.IGNORECASE
                    )
                    if name_match:
                        name = self._normalize_party_name(name_match.group(1))
                        if len(name) > 3:
                            data.landlord_name = name
                            data.field_confidence["landlord_name"] = 0.8
                            break
                break

        # --- Tenant (Mieter) ---
        for i, line in enumerate(cleaned_lines):
            # Match "Mieter:" but NOT "Vermieter:"
            if re.search(r"(?<!ver)mieter", line, re.IGNORECASE) and not re.search(
                r"vermieter", line, re.IGNORECASE
            ):
                # Check if name is on the same line
                name_on_line = re.search(
                    r"(?<!ver)mieter(?:in)?[:\s]+([\w\s\-äöüÄÖÜß]+)",
                    line, re.IGNORECASE,
                )
                if name_on_line:
                    name = self._normalize_party_name(name_on_line.group(1))
                    if len(name) > 3:
                        data.tenant_name = name
                        data.field_confidence["tenant_name"] = 0.8
                        break

                # Look for "Name ..." in the next few lines
                for j in range(i + 1, min(i + 5, len(cleaned_lines))):
                    # Match "Name:" with optional OCR noise prefix (single chars, punctuation)
                    name_match = re.match(
                        r"^(?:[^a-zA-Z]*|.{0,2}\s+)Name[:\s]+(.+)",
                        cleaned_lines[j], re.IGNORECASE
                    )
                    if name_match:
                        name = self._normalize_party_name(name_match.group(1))
                        if len(name) > 3:
                            data.tenant_name = name
                            data.field_confidence["tenant_name"] = 0.8
                            break
                break

        # Fallback: original regex patterns if line-based approach didn't work
        if not data.tenant_name:
            tenant_patterns = [
                r"(?<!Ver)mieter(?:in)?[:\s]+(.+?)(?:\n|,\s+geboren)",
                r"bestandnehmer(?:in)?[:\s]+(.+?)(?:\n|,\s+geboren)",
            ]
            for pattern in tenant_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    name = self._normalize_party_name(match.group(1))
                    if len(name) > 3:
                        data.tenant_name = name
                        data.field_confidence["tenant_name"] = 0.7
                        break

        if not data.landlord_name:
            landlord_patterns = [
                r"vermieter(?:in)?[:\s]+(.+?)(?:\n|,\s+geboren)",
                r"bestandgeber(?:in)?[:\s]+(.+?)(?:\n|,\s+geboren)",
            ]
            for pattern in landlord_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    name = self._normalize_party_name(match.group(1))
                    if len(name) > 3:
                        data.landlord_name = name
                        data.field_confidence["landlord_name"] = 0.7
                        break
    
    # --- Contract type extraction ---
    
    def _extract_contract_type(self, text: str, data: MietvertragData) -> None:
        """Extract contract type (Unbefristet vs Befristet)"""
        text_lower = text.lower()
        
        # Check for unlimited contract (Unbefristet)
        if "unbefristet" in text_lower or "auf unbestimmte zeit" in text_lower:
            data.contract_type = "Unbefristet"
            data.field_confidence["contract_type"] = 0.9
        # Check for fixed-term contract (Befristet)
        elif "befristet" in text_lower or "auf bestimmte zeit" in text_lower:
            data.contract_type = "Befristet"
            data.field_confidence["contract_type"] = 0.9
        # Infer from end_date presence
        elif data.end_date is not None:
            data.contract_type = "Befristet"
            data.field_confidence["contract_type"] = 0.7
        else:
            data.contract_type = "Unbefristet"
            data.field_confidence["contract_type"] = 0.6
    
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
    def _normalize_party_name(raw_name: str) -> str:
        """Remove titles and trailing residence/birth details from extracted names."""
        name = raw_name.strip()
        name = re.sub(r"^\(.*?\)\s*", "", name)
        name = re.sub(r"^(?:Herr|Frau|Di|DI|Mag|Dr)\.?\s+", "", name, flags=re.IGNORECASE)
        name = re.sub(r"^[:\s]+", "", name)
        name = re.split(r",\s*(?:wohnhaft|geboren)\b", name, maxsplit=1, flags=re.IGNORECASE)[0]
        return name.strip().rstrip(",")
    
    @staticmethod
    def _calculate_confidence(data: MietvertragData) -> float:
        """Calculate overall extraction confidence based on extracted fields"""
        # Critical fields for rental contract
        critical_fields = [
            "property_address",
            "monthly_rent",
            "start_date",
        ]
        
        # Important but not critical fields
        important_fields = [
            "street",
            "city",
            "postal_code",
            "tenant_name",
            "landlord_name",
            "deposit_amount",
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
