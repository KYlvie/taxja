"""Address matching service for property linking during imports"""
from typing import List, Dict, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.property import Property, PropertyStatus


@dataclass
class AddressMatch:
    """Represents a property match with confidence score"""
    property: Property
    confidence: float
    matched_components: Dict[str, bool]


class AddressMatcher:
    """
    Matches property addresses using fuzzy string matching.
    
    Used when importing E1/Bescheid with rental income to suggest
    linking to existing properties.
    
    Confidence levels:
    - > 0.9: High confidence (auto-suggest)
    - 0.7-0.9: Medium confidence (show as option)
    - < 0.7: Low confidence (don't suggest)
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def match_address(
        self, 
        address_string: str, 
        user_id: int
    ) -> List[AddressMatch]:
        """
        Find properties matching the given address string.
        
        Args:
            address_string: Address to match (can be full or partial)
            user_id: User ID to filter properties
        
        Returns:
            List of AddressMatch objects sorted by confidence (highest first)
            Only returns matches with confidence >= 0.7
        """
        # Get user's active properties
        properties = self.db.query(Property).filter(
            Property.user_id == user_id,
            Property.status == PropertyStatus.ACTIVE
        ).all()
        
        if not properties:
            return []
        
        # Normalize input address
        normalized_input = self._normalize_address(address_string)
        
        matches = []
        for property in properties:
            # Calculate similarity scores for different components
            full_address = f"{property.street}, {property.postal_code} {property.city}"
            normalized_property = self._normalize_address(full_address)
            
            # Overall similarity
            overall_score = self._calculate_similarity(normalized_input, normalized_property)
            
            # Component-wise matching for better accuracy
            street_score = self._calculate_similarity(
                self._normalize_address(address_string),
                self._normalize_address(property.street)
            )
            
            # Postal code exact match bonus
            postal_bonus = 0.2 if property.postal_code in address_string else 0
            
            # City match check
            city_match = property.city.lower() in address_string.lower()
            
            # Final confidence score (weighted combination)
            confidence = min(
                (overall_score * 0.6 + street_score * 0.3 + postal_bonus),
                1.0
            )
            
            # Only include matches with confidence >= 0.7
            if confidence >= 0.7:
                matches.append(AddressMatch(
                    property=property,
                    confidence=confidence,
                    matched_components={
                        "street": street_score > 0.8,
                        "postal_code": postal_bonus > 0,
                        "city": city_match
                    }
                ))
        
        # Sort by confidence descending
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
    
    def _normalize_address(self, address: str) -> str:
        """
        Normalize address for comparison.
        
        Handles Austrian address conventions:
        - Standardizes street type abbreviations (Str., Straße, etc.)
        - Converts to lowercase
        - Removes extra whitespace
        """
        # Convert to lowercase
        normalized = address.lower()
        
        # Remove common abbreviations and standardize
        # Austrian street types
        replacements = {
            "str.": "strasse",
            "straße": "strasse",
            "gasse": "gasse",
            "platz": "platz",
            "weg": "weg",
            "allee": "allee",
            "ring": "ring",
            "hof": "hof",
            "gürtel": "guertel",
            "kai": "kai",
        }
        
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        
        return normalized
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate string similarity using Levenshtein distance ratio.
        
        Returns value between 0.0 (no match) and 1.0 (exact match).
        
        Uses a simple implementation based on edit distance if
        python-Levenshtein is not available.
        """
        try:
            # Try to use python-Levenshtein for better performance
            from Levenshtein import ratio
            return ratio(str1, str2)
        except ImportError:
            # Fallback to simple similarity calculation
            return self._simple_similarity(str1, str2)
    
    def _simple_similarity(self, str1: str, str2: str) -> float:
        """
        Simple similarity calculation based on common tokens.
        
        Fallback when Levenshtein library is not available.
        """
        if not str1 or not str2:
            return 0.0
        
        # Exact match
        if str1 == str2:
            return 1.0
        
        # Token-based similarity
        tokens1 = set(str1.split())
        tokens2 = set(str2.split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        
        return intersection / union if union > 0 else 0.0
