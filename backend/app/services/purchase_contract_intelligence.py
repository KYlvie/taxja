"""Helpers for distinguishing property vs asset purchase contracts."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, Optional

from app.services.document_classifier import DocumentClassifier, _normalize_umlauts


class PurchaseContractKind(str, Enum):
    """Supported purchase-contract subtypes."""

    PROPERTY = "property"
    ASSET = "asset"


PROPERTY_MARKERS = [
    "grundstuck",
    "grundstueck",
    "liegenschaft",
    "grundbuch",
    "einlagezahl",
    "katastralgemeinde",
    "grunderwerbsteuer",
    "wohnungseigentum",
    "immobilie",
    "objektadresse",
    "nutzflache",
    "nutzflaeche",
]


ASSET_MARKERS = [
    "fahrgestellnummer",
    "kraftfahrzeug",
    "fahrzeugart",
    "pkw",
    "lkw",
    "erstzulassung",
    "kilometerstand",
    "typenschein",
    "kennzeichen",
    "marke / modell",
    "marke/modell",
    "fahrzeug",
]


def _count_hits(text: str, markers: list[str]) -> int:
    text_lower = text.lower()
    text_norm = _normalize_umlauts(text_lower)
    return sum(1 for marker in markers if _normalize_umlauts(marker) in text_norm)


def detect_purchase_contract_kind(
    raw_text: str,
    extracted_data: Optional[Dict[str, Any]] = None,
    classifier: Optional[DocumentClassifier] = None,
) -> PurchaseContractKind:
    """Classify a Kaufvertrag as either property- or asset-oriented."""

    extracted_data = extracted_data or {}
    explicit_kind = extracted_data.get("purchase_contract_kind")
    if explicit_kind in (PurchaseContractKind.PROPERTY.value, PurchaseContractKind.ASSET.value):
        return PurchaseContractKind(explicit_kind)

    classifier = classifier or DocumentClassifier()
    asset_type = classifier.detect_asset_type(raw_text or "")

    property_field_hits = sum(
        1
        for key in (
            "property_address",
            "building_value",
            "land_value",
            "grunderwerbsteuer",
            "notary_name",
            "registry_fees",
        )
        if extracted_data.get(key)
    )
    asset_field_hits = sum(
        1
        for key in (
            "asset_type",
            "asset_name",
            "vehicle_identification_number",
            "first_registration_date",
            "license_plate",
            "mileage_km",
        )
        if extracted_data.get(key)
    )

    property_hits = _count_hits(raw_text or "", PROPERTY_MARKERS)
    asset_hits = _count_hits(raw_text or "", ASSET_MARKERS)

    if asset_type or asset_hits >= 2 or asset_field_hits >= 2:
        if property_hits >= 3 and asset_field_hits == 0 and asset_type is None:
            return PurchaseContractKind.PROPERTY
        return PurchaseContractKind.ASSET

    if property_hits >= 2 or property_field_hits >= 2:
        return PurchaseContractKind.PROPERTY

    return PurchaseContractKind.PROPERTY


def _parse_amount(raw_value: Optional[str]) -> Optional[float]:
    if not raw_value:
        return None
    value = re.sub(r"[^\d,.\-]", "", raw_value)
    value = re.sub(r"[.,]+$", "", value)
    if not value:
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif value.count(",") == 1 and value.count(".") == 0:
        value = value.replace(",", ".")
    else:
        value = value.replace(",", "")
    try:
        return float(value)
    except ValueError:
        return None


def _extract_labeled_value(raw_text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def _extract_date(raw_text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()

    all_dates = re.findall(r"(\d{1,2}\.\d{1,2}\.\d{4})", raw_text)
    if all_dates:
        return all_dates[-1]
    return None


def _extract_party_name(raw_text: str, role_patterns: list[str]) -> Optional[str]:
    for role in role_patterns:
        for pattern in (
            rf"(?:^|\n)\s*{role}\b\s*(?:\r?\n)+\s*name\s*[:\-]?\s*([^\r\n]+)",
            rf"(?:^|\n)\s*{role}\b[^\r\n]{{0,80}}?\bname\s*[:\-]?\s*([^\r\n]+)",
            rf"\b{role}\b\s*[:\-]?\s*([^\r\n]+)",
        ):
            match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
    return None


def _parse_whole_number(raw_value: Optional[str]) -> Optional[int]:
    if not raw_value:
        return None
    digits = re.sub(r"[^\d]", "", raw_value)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def extract_asset_purchase_contract_fields(
    raw_text: str,
    classifier: Optional[DocumentClassifier] = None,
) -> Dict[str, Any]:
    """Extract minimal asset-oriented fields from a Kaufvertrag."""

    classifier = classifier or DocumentClassifier()
    asset_type = classifier.detect_asset_type(raw_text or "") or "other_equipment"

    normalized_text = _normalize_umlauts(raw_text or "")
    purchase_price_raw = None
    price_block_match = re.search(
        r"kaufpreis(.{0,120})",
        normalized_text,
        re.IGNORECASE | re.DOTALL,
    )
    if price_block_match:
        purchase_price_raw = _extract_labeled_value(
            price_block_match.group(1),
            [
                r"(?:eur|euro)\s*([0-9][0-9.,\s]*)",
                r"([0-9][0-9.,\s]{3,})",
            ],
        )
    if not purchase_price_raw:
        purchase_price_raw = _extract_labeled_value(
            normalized_text,
            [
                r"gesamtpreis\s*[:\-]?\s*(?:eur|euro)?\s*([0-9][0-9.,\s]*)",
            ],
        )
    purchase_price = _parse_amount(purchase_price_raw)

    asset_name = _extract_labeled_value(
        raw_text,
        [
            r"marke\s*/\s*modell\s*[:\-]?\s*([^\r\n]+)",
            r"kaufgegenstand\s*[:\-]?\s*([^\r\n]+)",
            r"fahrzeug\s*[:\-]?\s*([^\r\n]+)",
        ],
    )
    if not asset_name and asset_type in ("vehicle", "electric_vehicle"):
        asset_name = "Vehicle Purchase"

    purchase_date = _extract_date(
        raw_text,
        [
            r"(?:vertragsdatum|abschlussdatum)\s*[:\-]?\s*(\d{1,2}\.\d{1,2}\.\d{4})",
            r"(?:wien|linz|graz|salzburg)[,\s]+am\s+(\d{1,2}\.\d{1,2}\.\d{4})",
            r"ubergabe(?:datum)?\s*[:\-]?\s*(\d{1,2}\.\d{1,2}\.\d{4})",
            r"Ã¼bergabe(?:datum)?\s*[:\-]?\s*(\d{1,2}\.\d{1,2}\.\d{4})",
        ],
    )

    first_registration_date = _extract_date(
        raw_text,
        [r"erstzulassung\s*[:\-]?\s*(\d{1,2}\.\d{1,2}\.\d{4})"],
    )

    seller_name = _extract_party_name(
        raw_text,
        [r"verkäufer", r"verkaufer", r"verkÃ¤ufer"],
    )
    buyer_name = _extract_party_name(
        raw_text,
        [r"käufer", r"kaufer", r"kÃ¤ufer"],
    )

    vin = _extract_labeled_value(
        raw_text,
        [
            r"fin\s*/\s*fahrgestellnummer\s*[:\-]?\s*([A-Z0-9\-]{6,})",
            r"fahrgestellnummer\s*[:\-]?\s*([A-Z0-9\-]{6,})",
            r"\bvin\s*[:\-]?\s*([A-Z0-9\-]{6,})",
        ],
    )
    license_plate = _extract_labeled_value(
        raw_text,
        [
            r"kennzeichen(?:\s+zuletzt)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\- ]{2,})",
            r"amtl\.?\s*kennzeichen\s*[:\-]?\s*([A-Z0-9][A-Z0-9\- ]{2,})",
        ],
    )

    mileage_raw = _extract_labeled_value(
        raw_text,
        [r"kilometerstand\s*[:\-]?\s*([0-9][0-9.,\s]*)\s*km"],
    )
    mileage_km = _parse_whole_number(mileage_raw)

    previous_owners_raw = _extract_labeled_value(
        raw_text,
        [r"anzahl\s+vorbesitzer\s*[:\-]?\s*([0-9]+)"],
    )
    previous_owners = None
    if previous_owners_raw and previous_owners_raw.isdigit():
        previous_owners = int(previous_owners_raw)

    is_used_asset = bool(
        re.search(r"\bgebraucht\w*\b", _normalize_umlauts(raw_text.lower()))
        or first_registration_date
        or (previous_owners is not None and previous_owners > 0)
    )

    confidence = 0.45
    if purchase_price:
        confidence += 0.20
    if asset_name:
        confidence += 0.15
    if asset_type != "other_equipment":
        confidence += 0.10
    if first_registration_date or vin:
        confidence += 0.10
    confidence = min(confidence, 0.92)

    field_confidence = {
        "purchase_contract_kind": 0.95,
        "asset_type": 0.80 if asset_type != "other_equipment" else 0.55,
    }
    if asset_name:
        field_confidence["asset_name"] = 0.75
    if purchase_price:
        field_confidence["purchase_price"] = 0.85
    if purchase_date:
        field_confidence["purchase_date"] = 0.70
    if seller_name:
        field_confidence["seller_name"] = 0.65
    if buyer_name:
        field_confidence["buyer_name"] = 0.65
    if first_registration_date:
        field_confidence["first_registration_date"] = 0.80
    if vin:
        field_confidence["vehicle_identification_number"] = 0.85
    if license_plate:
        field_confidence["license_plate"] = 0.75
    if mileage_km is not None:
        field_confidence["mileage_km"] = 0.75

    return {
        "purchase_contract_kind": PurchaseContractKind.ASSET.value,
        "asset_type": asset_type,
        "asset_name": asset_name,
        "purchase_price": purchase_price,
        "purchase_date": purchase_date,
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "first_registration_date": first_registration_date,
        "vehicle_identification_number": vin,
        "license_plate": license_plate.strip() if license_plate else None,
        "mileage_km": mileage_km,
        "is_used_asset": is_used_asset,
        "previous_owners": previous_owners,
        "field_confidence": field_confidence,
        "confidence": confidence,
    }
