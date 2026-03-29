"""Insurance-specific tax and recurring decision helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.property import Property, PropertyType
from app.models.user import User
FULLY_DEDUCTIBLE_SUBTYPES = {
    "berufshaftpflicht",
    "betriebsunterbrechung",
    "cyberversicherung",
    "betriebshaftpflicht",
    "d_and_o",
}

NON_DEDUCTIBLE_SUBTYPES = {
    "private_krankenversicherung",
    "private_unfallversicherung",
    "unfallversicherung",
    "lebensversicherung",
}


@dataclass
class DeductionResult:
    deductibility_status: str
    deductibility_hint: str
    deductible_category: Optional[str] = None
    kz_hint: Optional[str] = None
    deductible_pct: Optional[float] = None
    needs_user_input: bool = False
    input_fields: list[str] | None = None
    split_mode: str = "none"
    linked_property_candidate: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "deductibility_status": self.deductibility_status,
            "deductibility_hint": self.deductibility_hint,
            "deductible_category": self.deductible_category,
            "kz_hint": self.kz_hint,
            "deductible_pct": self.deductible_pct,
            "needs_user_input": self.needs_user_input,
            "input_fields": list(self.input_fields or []),
            "split_mode": self.split_mode,
            "linked_property_candidate": self.linked_property_candidate,
        }


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not value:
        return None
    token = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_pct(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return None
    if pct > 1:
        pct = pct / 100.0
    return max(0.0, min(1.0, pct))


def _home_office_ratio(user: User) -> Optional[float]:
    arbeitszimmer = getattr(user, "arbeitszimmer_m2", None)
    nutzflaeche = getattr(user, "nutzflaeche_m2", None)
    if arbeitszimmer in (None, "") or nutzflaeche in (None, "", 0):
        return None
    try:
        ratio = Decimal(str(arbeitszimmer)) / Decimal(str(nutzflaeche))
    except Exception:
        return None
    if ratio <= Decimal("0"):
        return None
    return max(0.0, min(1.0, float(ratio)))


def _property_context(
    db: Session,
    *,
    user_id: int,
    linked_property_id: Any = None,
) -> tuple[Optional[Property], Optional[float]]:
    if not linked_property_id:
        return None, None
    prop = (
        db.query(Property)
        .filter(Property.id == linked_property_id, Property.user_id == user_id)
        .first()
    )
    if not prop:
        return None, None

    rental_pct = getattr(prop, "rental_percentage", None)
    if rental_pct is None:
        return prop, None
    try:
        return prop, float(Decimal(str(rental_pct)) / Decimal("100"))
    except Exception:
        return prop, None


def _is_rechtsschutz_kombi(facts: dict[str, Any]) -> bool:
    text = " ".join(
        str(facts.get(key) or "")
        for key in (
            "insurance_type",
            "insurance_subtype",
            "document_subtype",
            "description",
            "raw_text",
        )
    ).lower()
    if "berufsrechtsschutz" in text and "privat" not in text and "kombi" not in text:
        return False
    return any(token in text for token in ("privat", "kombi", "plus", "kombi-produkt"))


def evaluate_insurance_deductibility(
    db: Session,
    *,
    user: User,
    facts: dict[str, Any],
) -> DeductionResult:
    subtype = str(facts.get("insurance_subtype") or "other").strip().lower()
    linked_property_id = facts.get("linked_property_id")

    if subtype in FULLY_DEDUCTIBLE_SUBTYPES:
        return DeductionResult(
            deductibility_status="deductible",
            deductible_pct=1.0,
            deductible_category="betriebsausgabe",
            kz_hint="E1a KZ 9230",
            deductibility_hint="100% deductible as business insurance.",
            split_mode="full",
        )

    if subtype == "kfz":
        return DeductionResult(
            deductibility_status="partially_deductible",
            deductible_category="betriebsausgabe",
            kz_hint="E1a KZ 9230 (anteilig)",
            deductibility_hint="Business-use percentage is required for KFZ insurance.",
            needs_user_input=True,
            input_fields=["business_use_percentage"],
            split_mode="business_use_split",
        )

    if subtype == "rechtsschutz":
        if _is_rechtsschutz_kombi(facts):
            return DeductionResult(
                deductibility_status="partially_deductible",
                deductible_category="betriebsausgabe",
                kz_hint="E1a KZ 9230 (anteilig)",
                deductibility_hint="Only the professional portion is deductible for combined legal-protection products.",
                needs_user_input=True,
                input_fields=["beruflicher_anteil_pct"],
                split_mode="beruflicher_anteil_split",
            )
        return DeductionResult(
            deductibility_status="deductible",
            deductible_pct=1.0,
            deductible_category="betriebsausgabe",
            kz_hint="E1a KZ 9230",
            deductibility_hint="Pure professional legal-protection insurance is deductible.",
            split_mode="full",
        )

    if subtype == "gebaeudeversicherung":
        prop, rental_ratio = _property_context(
            db,
            user_id=user.id,
            linked_property_id=linked_property_id,
        )
        if prop:
            property_type = getattr(prop, "property_type", None)
            property_type_value = getattr(property_type, "value", property_type)
            if property_type_value == PropertyType.OWNER_OCCUPIED.value:
                return DeductionResult(
                    deductibility_status="not_deductible",
                    deductibility_hint="Owner-occupied building insurance is not deductible.",
                    linked_property_candidate=str(prop.id),
                )
            if rental_ratio and rental_ratio > 0:
                pct = 1.0 if rental_ratio >= 0.999 else rental_ratio
                return DeductionResult(
                    deductibility_status=(
                        "deductible" if pct >= 0.999 else "partially_deductible"
                    ),
                    deductible_pct=pct,
                    deductible_category="werbungskosten_vv",
                    kz_hint="E1b KZ 9510",
                    deductibility_hint=(
                        "Building insurance linked to a rental property is deductible."
                        if pct >= 0.999
                        else "Building insurance is deductible in proportion to the rental share."
                    ),
                    split_mode="property_rental_split" if pct < 0.999 else "full",
                    linked_property_candidate=str(prop.id),
                )
        return DeductionResult(
            deductibility_status="unknown",
            deductibility_hint="Property rental status is required for building insurance.",
            needs_user_input=True,
            input_fields=["property_rental_status"],
            split_mode="property_rental_split",
        )

    if subtype == "haushaltsversicherung":
        ratio = _home_office_ratio(user)
        if ratio and ratio > 0:
            pct = _normalize_pct(ratio) or 0.0
            return DeductionResult(
                deductibility_status="partially_deductible" if pct < 0.999 else "deductible",
                deductible_pct=pct,
                deductible_category="betriebsausgabe",
                kz_hint="E1a KZ 9230 (anteilig)",
                deductibility_hint=(
                    f"Home-office portion can be deducted ({pct * 100:.1f}%)."
                ),
                split_mode="business_use_split" if pct < 0.999 else "full",
            )
        return DeductionResult(
            deductibility_status="partially_deductible",
            deductible_category="betriebsausgabe",
            kz_hint="E1a KZ 9230 (anteilig)",
            deductibility_hint="Only the home-office portion is deductible.",
            needs_user_input=True,
            input_fields=["business_use_percentage"],
            split_mode="business_use_split",
        )

    if subtype in NON_DEDUCTIBLE_SUBTYPES:
        start_date = _parse_date(facts.get("vertragsbeginn"))
        if start_date:
            if start_date < date(2016, 1, 1):
                hint = "Legacy contract detected, but private KV/UV/Leben is no longer deductible for 2021+ tax years."
            else:
                hint = (
                    f"Contract start {start_date.isoformat()}: private KV/UV/Leben is not deductible for 2021+ tax years."
                )
        else:
            hint = "Private KV/UV/Leben is not deductible for 2021+ tax years."
        return DeductionResult(
            deductibility_status="not_deductible",
            deductibility_hint=hint,
        )

    return DeductionResult(
        deductibility_status="unknown",
        deductibility_hint="Insurance type could not be classified reliably.",
        needs_user_input=True,
        input_fields=[],
    )
