"""Tax profile source-of-truth helpers for asset automation."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.user import Gewinnermittlungsart, User, UserType, VatStatus
from app.schemas.user import TaxProfileCompleteness


@dataclass(frozen=True)
class AssetTaxProfileContext:
    """Resolved and raw profile inputs used by asset automation."""

    vat_status: VatStatus | None
    gewinnermittlungsart: Gewinnermittlungsart | None
    resolved_vat_status: VatStatus
    resolved_gewinnermittlungsart: Gewinnermittlungsart
    completeness: TaxProfileCompleteness


class TaxProfileService:
    """Centralize persisted tax-profile completeness and asset inputs."""

    ASSET_AUTOMATION_USER_TYPES = {
        UserType.SELF_EMPLOYED,
        UserType.MIXED,
        UserType.GMBH,
    }

    def requires_asset_automation_profile(self, user: User) -> bool:
        user_type = self._coerce_user_type(getattr(user, "user_type", None))
        return user_type in self.ASSET_AUTOMATION_USER_TYPES

    def get_asset_tax_profile_context(self, user: User) -> AssetTaxProfileContext:
        raw_vat_status = self._coerce_optional_enum(
            getattr(user, "vat_status", None),
            VatStatus,
        )
        raw_gewinnermittlungsart = self._coerce_optional_enum(
            getattr(user, "gewinnermittlungsart", None),
            Gewinnermittlungsart,
        )

        missing_fields: list[str] = []
        if self.requires_asset_automation_profile(user):
            if raw_vat_status in (None, VatStatus.UNKNOWN):
                missing_fields.append("vat_status")
            if raw_gewinnermittlungsart in (None, Gewinnermittlungsart.UNKNOWN):
                missing_fields.append("gewinnermittlungsart")

        completeness = TaxProfileCompleteness(
            is_complete_for_asset_automation=not missing_fields,
            missing_fields=missing_fields,
        )

        return AssetTaxProfileContext(
            vat_status=raw_vat_status,
            gewinnermittlungsart=raw_gewinnermittlungsart,
            resolved_vat_status=raw_vat_status or VatStatus.UNKNOWN,
            resolved_gewinnermittlungsart=raw_gewinnermittlungsart or Gewinnermittlungsart.UNKNOWN,
            completeness=completeness,
        )

    def require_complete_asset_profile(self, user: User) -> AssetTaxProfileContext:
        context = self.get_asset_tax_profile_context(user)
        if context.completeness.is_complete_for_asset_automation:
            return context

        missing = ", ".join(context.completeness.missing_fields)
        raise ValueError(
            f"Tax profile incomplete for asset automation. Missing: {missing}"
        )

    def _coerce_user_type(self, value: UserType | str | None) -> UserType | None:
        if value is None:
            return None
        if isinstance(value, UserType):
            return value
        try:
            return UserType(value)
        except ValueError:
            return None

    def _coerce_optional_enum(self, value, enum_cls):
        if value is None:
            return None
        if isinstance(value, enum_cls):
            return value
        try:
            return enum_cls(value)
        except ValueError:
            return None
