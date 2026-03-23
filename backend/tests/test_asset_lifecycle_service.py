"""Tests for non-real-estate asset lifecycle calculations."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.asset_event import AssetEventTriggerSource, AssetEventType
from app.models.property import Property, PropertyStatus, PropertyType
from app.models.user import User
from app.services.afa_calculator import AfACalculator
from app.services.asset_lifecycle_service import AssetLifecycleService
from app.services.property_report_service import PropertyReportService


def _create_user(db, email: str = "asset@example.com") -> User:
    user = User(
        email=email,
        name="Asset User",
        password_hash="hashed-password",
        user_type="self_employed",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_asset(
    db,
    user: User,
    *,
    asset_type: str = "computer",
    name: str = "Business Laptop",
    purchase_date: date = date(2026, 1, 10),
    put_into_use_date: date | None = None,
    purchase_price: Decimal = Decimal("1500.00"),
    building_value: Decimal = Decimal("1500.00"),
    depreciation_rate: Decimal = Decimal("0.3333"),
    useful_life_years: int = 3,
    business_use_percentage: Decimal = Decimal("100.00"),
    depreciation_method: str = "linear",
    degressive_afa_rate: Decimal | None = None,
    gwg_elected: bool = False,
    gwg_eligible: bool = False,
) -> Property:
    asset = Property(
        user_id=user.id,
        asset_type=asset_type,
        name=name,
        property_type=PropertyType.RENTAL,
        rental_percentage=business_use_percentage,
        business_use_percentage=business_use_percentage,
        address=name,
        street=name,
        city="Wien",
        postal_code="1010",
        purchase_date=purchase_date,
        purchase_price=purchase_price,
        building_value=building_value,
        land_value=Decimal("0"),
        depreciation_rate=depreciation_rate,
        useful_life_years=useful_life_years,
        put_into_use_date=put_into_use_date,
        depreciation_method=depreciation_method,
        degressive_afa_rate=degressive_afa_rate,
        gwg_elected=gwg_elected,
        gwg_eligible=gwg_eligible,
        status=PropertyStatus.ACTIVE,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


class TestAssetLifecycleService:
    def test_linear_asset_uses_half_year_rule_from_put_into_use_date(self, db):
        user = _create_user(db, "linear@example.com")
        asset = _create_asset(
            db,
            user,
            put_into_use_date=date(2026, 8, 15),
            purchase_price=Decimal("1500.00"),
            building_value=Decimal("1500.00"),
            depreciation_rate=Decimal("0.3333"),
            useful_life_years=3,
        )

        service = AssetLifecycleService(db)

        assert service.calculate_annual_depreciation(asset, 2025) == Decimal("0")
        assert service.calculate_annual_depreciation(asset, 2026) == Decimal("249.98")
        assert service.calculate_annual_depreciation(asset, 2027) == Decimal("499.95")
        assert service.calculate_accumulated_depreciation(asset, 2027) == Decimal("749.93")

    def test_gwg_elected_expenses_once_in_first_tax_year(self, db):
        user = _create_user(db, "gwg@example.com")
        asset = _create_asset(
            db,
            user,
            name="Office Printer",
            purchase_price=Decimal("900.00"),
            building_value=Decimal("900.00"),
            depreciation_rate=Decimal("1.0000"),
            useful_life_years=1,
            gwg_eligible=True,
            gwg_elected=True,
            put_into_use_date=date(2026, 9, 1),
        )

        service = AssetLifecycleService(db)

        assert service.calculate_annual_depreciation(asset, 2026) == Decimal("900.00")
        assert service.calculate_annual_depreciation(asset, 2027) == Decimal("0")
        assert service.calculate_accumulated_depreciation(asset, 2027) == Decimal("900.00")

    def test_degressive_asset_switches_to_linear_after_event(self, db):
        user = _create_user(db, "degressive@example.com")
        asset = _create_asset(
            db,
            user,
            asset_type="machinery",
            name="Workshop Machine",
            purchase_price=Decimal("1200.00"),
            building_value=Decimal("1200.00"),
            depreciation_rate=Decimal("0.3333"),
            useful_life_years=3,
            depreciation_method="degressive",
            degressive_afa_rate=Decimal("0.30"),
            put_into_use_date=date(2026, 3, 1),
        )

        service = AssetLifecycleService(db)

        assert service.calculate_annual_depreciation(asset, 2026) == Decimal("360.00")
        assert service.calculate_annual_depreciation(asset, 2027) == Decimal("252.00")
        assert service.should_switch_from_degressive_to_linear(asset, 2028) is True

        service.record_degressive_to_linear_switch(
            asset=asset,
            switch_date=date(2028, 1, 1),
            trigger_source=AssetEventTriggerSource.POLICY_RECOMPUTE,
            payload={"reason": "linear_better_than_degressive"},
        )
        db.commit()

        assert service.calculate_annual_depreciation(asset, 2028) == Decimal("588.00")
        assert service.get_degressive_switch_year(asset) == 2028

    def test_afa_calculator_delegates_non_real_estate_assets(self, db):
        user = _create_user(db, "delegate@example.com")
        asset = _create_asset(
            db,
            user,
            business_use_percentage=Decimal("50.00"),
            purchase_price=Decimal("1000.00"),
            building_value=Decimal("1000.00"),
            depreciation_rate=Decimal("0.2000"),
            useful_life_years=5,
            put_into_use_date=date(2026, 8, 1),
        )

        calculator = AfACalculator(db)
        depreciation = calculator.calculate_annual_depreciation(asset, 2026)

        assert depreciation == Decimal("50.00")
        assert calculator.get_accumulated_depreciation(asset.id, 2026) == Decimal("50.00")

    def test_property_report_schedule_for_asset_starts_at_put_into_use_year(self, db):
        user = _create_user(db, "report@example.com")
        asset = _create_asset(
            db,
            user,
            purchase_date=date(2025, 12, 15),
            put_into_use_date=date(2026, 8, 1),
            purchase_price=Decimal("1000.00"),
            building_value=Decimal("1000.00"),
            depreciation_rate=Decimal("0.2000"),
            useful_life_years=5,
            business_use_percentage=Decimal("50.00"),
        )

        report_service = PropertyReportService(db)
        report = report_service.generate_depreciation_schedule(str(asset.id), include_future=False)

        assert report["property"]["id"] == str(asset.id)
        assert report["property"]["building_value"] == 500.0
        assert [row["year"] for row in report["schedule"]] == [2026]
        assert report["schedule"][0]["annual_depreciation"] == 50.0
        assert report["summary"]["total_depreciation"] == 500.0
        assert report["summary"]["remaining_value"] == 450.0
