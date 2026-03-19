"""Address matching service for property linking during imports."""

from dataclasses import dataclass
import re
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.property import Property, PropertyStatus


@dataclass
class AddressMatch:
    """Represents a property match with confidence score."""

    property: Property
    confidence: float
    matched_components: Dict[str, bool]


class AddressMatcher:
    """
    Match user properties against a free-form address string.

    Confidence levels:
    - > 0.9: High confidence (auto-suggest)
    - 0.7-0.9: Medium confidence (show as option)
    - < 0.7: Low confidence (don't suggest)
    """

    def __init__(self, db: Session):
        self.db = db

    def match_address(self, address_string: str, user_id: int) -> List[AddressMatch]:
        """Find properties matching the given address string."""
        properties = (
            self.db.query(Property)
            .filter(
                Property.user_id == user_id,
                Property.status == PropertyStatus.ACTIVE,
            )
            .all()
        )

        if not properties:
            return []

        normalized_input = self._normalize_address(address_string)
        input_components = self._extract_address_components(address_string)

        matches: List[AddressMatch] = []
        for property_ in properties:
            full_address = f"{property_.street}, {property_.postal_code} {property_.city}"
            normalized_property = self._normalize_address(full_address)

            overall_score = self._calculate_similarity(
                normalized_input,
                normalized_property,
            )
            street_score = self._calculate_similarity(
                input_components["street"],
                self._normalize_address(property_.street),
            )

            postal_bonus = 0.2 if property_.postal_code in normalized_input else 0.0
            city_match = property_.city.lower() in address_string.lower()

            confidence = min(
                overall_score * 0.6 + street_score * 0.3 + postal_bonus,
                1.0,
            )

            # Street-only inputs should still surface strong matches even without
            # postal code or city hints.
            if not input_components["postal_code"] and not input_components["city"]:
                confidence = max(confidence, street_score * 0.85)

            if confidence >= 0.7:
                matches.append(
                    AddressMatch(
                        property=property_,
                        confidence=confidence,
                        matched_components={
                            "street": street_score > 0.8,
                            "postal_code": postal_bonus > 0,
                            "city": city_match,
                        },
                    )
                )

        matches.sort(key=lambda match: match.confidence, reverse=True)
        return matches

    def _extract_address_components(self, address: str) -> Dict[str, str]:
        """Extract normalized street/postal/city fragments from a free-form address."""
        normalized = self._normalize_address(address)
        street_part = normalized
        remainder = ""

        if "," in normalized:
            street_part, remainder = [part.strip() for part in normalized.split(",", 1)]

        postal_code = ""
        city_part = remainder
        postal_match = re.search(r"\b(\d{4})\b", remainder)
        if postal_match:
            postal_code = postal_match.group(1)
            city_part = remainder.replace(postal_code, "", 1).strip()

        return {
            "street": street_part,
            "postal_code": postal_code,
            "city": city_part,
        }

    def _normalize_address(self, address: str) -> str:
        """Normalize Austrian-style address strings for fuzzy comparison."""
        normalized = address.lower()

        replacements = {
            "str.": "strasse",
            "straße": "strasse",
            "straÃŸe": "strasse",
            "gürtel": "guertel",
            "gÃ¼rtel": "guertel",
        }

        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        normalized = " ".join(normalized.split())
        return normalized

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity using Levenshtein when available."""
        try:
            from Levenshtein import ratio

            return ratio(str1, str2)
        except ImportError:
            return self._simple_similarity(str1, str2)

    def _simple_similarity(self, str1: str, str2: str) -> float:
        """Fallback similarity calculation based on token overlap."""
        if not str1 or not str2:
            return 0.0

        if str1 == str2:
            return 1.0

        tokens1 = set(str1.split())
        tokens2 = set(str2.split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        return intersection / union if union > 0 else 0.0
