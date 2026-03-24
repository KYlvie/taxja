"""Unit tests for persisted tax-profile completeness."""
from app.models.user import Gewinnermittlungsart, UserType, VatStatus
from app.services.tax_profile_service import TaxProfileService
from tests.fixtures.models import create_test_user


def test_tax_profile_completeness_requires_persisted_fields_for_self_employed(db):
    user = create_test_user(
        db,
        email="tax-profile-incomplete@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_status=None,
        gewinnermittlungsart=None,
    )

    completeness = TaxProfileService().get_asset_tax_profile_context(user).completeness

    assert completeness.is_complete_for_asset_automation is False
    assert completeness.missing_fields == ["vat_status", "gewinnermittlungsart"]
    assert completeness.source == "persisted_user_profile"
    assert completeness.contract_version == "v1"


def test_tax_profile_completeness_allows_non_asset_users_without_extra_fields(db):
    user = create_test_user(
        db,
        email="tax-profile-employee@example.com",
        user_type=UserType.EMPLOYEE,
        vat_status=None,
        gewinnermittlungsart=None,
    )

    context = TaxProfileService().get_asset_tax_profile_context(user)

    assert context.completeness.is_complete_for_asset_automation is True
    assert context.completeness.missing_fields == []
    assert context.resolved_vat_status == VatStatus.UNKNOWN
    assert context.resolved_gewinnermittlungsart == Gewinnermittlungsart.UNKNOWN
