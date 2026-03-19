"""Lifecycle calculations for non-real-estate assets."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.asset_event import AssetEvent, AssetEventTriggerSource, AssetEventType
from app.models.property import Property, PropertyType


class AssetLifecycleService:
    """Central lifecycle calculations for movable/fixed business assets."""

    DEFAULT_DEGRESSIVE_RATE = Decimal("0.30")
    HALF_YEAR_THRESHOLD_MONTH = 7
    MIN_LINEAR_REMAINING_YEARS = Decimal("1")

    def __init__(self, db: Session):
        self.db = db

    def calculate_annual_depreciation(self, asset: Property, year: int) -> Decimal:
        """Calculate annual tax depreciation for one non-real-estate asset."""
        start_date = self._get_start_date(asset)
        if start_date is None:
            return Decimal("0")

        if asset.property_type == PropertyType.OWNER_OCCUPIED:
            return Decimal("0")
        if year < start_date.year:
            return Decimal("0")
        if asset.sale_date and year > asset.sale_date.year:
            return Decimal("0")

        depreciable_base = self.get_depreciable_base(asset)
        if depreciable_base <= Decimal("0"):
            return Decimal("0")

        accumulated_before = self.calculate_accumulated_depreciation(asset, year - 1)
        return self._calculate_annual_amount(
            asset,
            year,
            start_date=start_date,
            depreciable_base=depreciable_base,
            accumulated_before=accumulated_before,
        )

    def calculate_accumulated_depreciation(
        self,
        asset: Property,
        up_to_year: Optional[int] = None,
    ) -> Decimal:
        """Calculate accumulated depreciation for one asset up to a year."""
        start_date = self._get_start_date(asset)
        if start_date is None:
            return Decimal("0")

        end_year = up_to_year if up_to_year is not None else date.today().year
        if end_year < start_date.year:
            return Decimal("0")

        accumulated = Decimal("0")
        depreciable_base = self.get_depreciable_base(asset)

        for year in range(start_date.year, end_year + 1):
            if asset.sale_date and year > asset.sale_date.year:
                break
            annual_amount = self._calculate_annual_amount(
                asset,
                year,
                start_date=start_date,
                depreciable_base=depreciable_base,
                accumulated_before=accumulated,
            )
            accumulated += annual_amount

        return accumulated.quantize(Decimal("0.01"))

    def estimate_years_remaining(
        self,
        asset: Property,
        from_year: Optional[int] = None,
    ) -> Decimal | None:
        """Estimate remaining tax years until the asset is fully depreciated."""
        start_date = self._get_start_date(asset)
        if start_date is None:
            return None

        depreciable_base = self.get_depreciable_base(asset)
        if depreciable_base <= Decimal("0"):
            return None

        current_year = from_year if from_year is not None else date.today().year
        accumulated = self.calculate_accumulated_depreciation(asset, current_year - 1)
        if accumulated >= depreciable_base:
            return Decimal("0.0")

        years_remaining = Decimal("0")
        safety_limit = 200
        year = current_year
        while years_remaining < safety_limit and accumulated < depreciable_base:
            annual = self._calculate_annual_amount(
                asset,
                year,
                start_date=start_date,
                depreciable_base=depreciable_base,
                accumulated_before=accumulated,
            )
            if annual <= Decimal("0"):
                break
            accumulated += annual
            years_remaining += Decimal("1")
            year += 1

        return years_remaining.quantize(Decimal("0.1"))

    def should_switch_from_degressive_to_linear(self, asset: Property, year: int) -> bool:
        """Return True when linear depreciation is now better than degressive."""
        if self._normalize_method(asset.depreciation_method) != "degressive":
            return False
        existing_switch_year = self.get_degressive_switch_year(asset)
        if existing_switch_year is not None and existing_switch_year <= year:
            return False

        start_date = self._get_start_date(asset)
        if start_date is None or year < start_date.year:
            return False

        depreciable_base = self.get_depreciable_base(asset)
        accumulated_before = self.calculate_accumulated_depreciation(asset, year - 1)
        remaining = depreciable_base - accumulated_before
        if remaining <= Decimal("0"):
            return False

        degressive_amount = self._calculate_degressive_amount(
            asset,
            year,
            remaining_value=remaining,
            start_date=start_date,
        )
        linear_amount = self._calculate_linear_amount(
            asset,
            year,
            start_date=start_date,
            depreciable_base=depreciable_base,
            switch_year=year,
        )
        return linear_amount > degressive_amount

    def get_degressive_switch_year(self, asset: Property) -> int | None:
        """Return the effective tax year of a recorded degressive->linear switch."""
        event = (
            self.db.query(AssetEvent)
            .filter(
                AssetEvent.property_id == asset.id,
                AssetEvent.event_type == AssetEventType.DEGRESSIVE_TO_LINEAR_SWITCH,
            )
            .order_by(AssetEvent.event_date.asc(), AssetEvent.id.asc())
            .first()
        )
        return event.event_date.year if event else None

    def record_event(
        self,
        *,
        asset: Property,
        event_type: AssetEventType,
        event_date: date,
        trigger_source: AssetEventTriggerSource = AssetEventTriggerSource.SYSTEM,
        payload: Optional[dict] = None,
    ) -> AssetEvent:
        """Persist a lifecycle event for the asset."""
        event = AssetEvent(
            user_id=asset.user_id,
            property_id=asset.id,
            event_type=event_type,
            trigger_source=trigger_source,
            event_date=event_date,
            payload=payload or {},
        )
        self.db.add(event)
        self.db.flush()
        return event

    def record_degressive_to_linear_switch(
        self,
        *,
        asset: Property,
        switch_date: date,
        trigger_source: AssetEventTriggerSource = AssetEventTriggerSource.USER,
        payload: Optional[dict] = None,
    ) -> AssetEvent:
        """Persist an irreversible switch event from degressive to linear AfA."""
        existing_year = self.get_degressive_switch_year(asset)
        if existing_year is not None and existing_year == switch_date.year:
            existing_event = (
                self.db.query(AssetEvent)
                .filter(
                    AssetEvent.property_id == asset.id,
                    AssetEvent.event_type == AssetEventType.DEGRESSIVE_TO_LINEAR_SWITCH,
                    AssetEvent.event_date == switch_date,
                )
                .first()
            )
            if existing_event:
                return existing_event

        return self.record_event(
            asset=asset,
            event_type=AssetEventType.DEGRESSIVE_TO_LINEAR_SWITCH,
            event_date=switch_date,
            trigger_source=trigger_source,
            payload=payload,
        )

    def _calculate_annual_amount(
        self,
        asset: Property,
        year: int,
        *,
        start_date: date,
        depreciable_base: Decimal,
        accumulated_before: Decimal,
    ) -> Decimal:
        remaining_value = depreciable_base - accumulated_before
        if remaining_value <= Decimal("0"):
            return Decimal("0")

        if asset.gwg_elected:
            if year != start_date.year:
                return Decimal("0")
            return remaining_value.quantize(Decimal("0.01"))

        effective_method = self._get_effective_method(asset, year)
        if effective_method == "degressive":
            annual = self._calculate_degressive_amount(
                asset,
                year,
                remaining_value=remaining_value,
                start_date=start_date,
            )
        else:
            annual = self._calculate_linear_amount(
                asset,
                year,
                start_date=start_date,
                depreciable_base=depreciable_base,
                switch_year=self.get_degressive_switch_year(asset),
            )

        final_amount = min(annual, remaining_value)
        return final_amount.quantize(Decimal("0.01"))

    def _calculate_degressive_amount(
        self,
        asset: Property,
        year: int,
        *,
        remaining_value: Decimal,
        start_date: date,
    ) -> Decimal:
        rate = Decimal(str(asset.degressive_afa_rate or self.DEFAULT_DEGRESSIVE_RATE))
        annual = remaining_value * rate
        if year == start_date.year and self._is_half_year_start(start_date):
            annual = annual / Decimal("2")
        return annual

    def _calculate_linear_amount(
        self,
        asset: Property,
        year: int,
        *,
        start_date: date,
        depreciable_base: Decimal,
        switch_year: int | None,
    ) -> Decimal:
        effective_switch_year = (
            switch_year
            if switch_year is not None and self._normalize_method(asset.depreciation_method) == "degressive"
            else None
        )
        if effective_switch_year is not None and year >= effective_switch_year:
            remaining_at_switch = depreciable_base - self.calculate_accumulated_depreciation(asset, effective_switch_year - 1)
            remaining_years = self._remaining_linear_years_after_switch(
                asset,
                start_date=start_date,
                switch_year=effective_switch_year,
            )
            if remaining_years <= Decimal("0"):
                remaining_years = self.MIN_LINEAR_REMAINING_YEARS
            return remaining_at_switch / remaining_years

        annual = depreciable_base * Decimal(str(asset.depreciation_rate))
        if year == start_date.year and self._is_half_year_start(start_date):
            annual = annual / Decimal("2")
        return annual

    def _remaining_linear_years_after_switch(
        self,
        asset: Property,
        *,
        start_date: date,
        switch_year: int,
    ) -> Decimal:
        useful_life = Decimal(str(asset.useful_life_years or 1))
        years_before_switch = Decimal(max(switch_year - start_date.year, 0))
        if years_before_switch > Decimal("0") and self._is_half_year_start(start_date):
            years_before_switch -= Decimal("0.5")
        remaining = useful_life - years_before_switch
        return remaining if remaining > Decimal("0") else self.MIN_LINEAR_REMAINING_YEARS

    def get_depreciable_base(self, asset: Property) -> Decimal:
        base = Decimal(str(asset.income_tax_depreciable_base or asset.building_value or Decimal("0")))
        business_use = Decimal(str(asset.business_use_percentage or Decimal("100")))
        if business_use < Decimal("100"):
            base = base * (business_use / Decimal("100"))
        return base.quantize(Decimal("0.01"))

    def _get_start_date(self, asset: Property) -> date | None:
        return asset.put_into_use_date or asset.purchase_date

    def _is_half_year_start(self, start_date: date) -> bool:
        return start_date.month >= self.HALF_YEAR_THRESHOLD_MONTH

    def _get_effective_method(self, asset: Property, year: int) -> str:
        normalized = self._normalize_method(asset.depreciation_method)
        if normalized != "degressive":
            return "linear"
        switch_year = self.get_degressive_switch_year(asset)
        if switch_year is not None and year >= switch_year:
            return "linear"
        return "degressive"

    def _normalize_method(self, value: object) -> str:
        if value is None:
            return "linear"
        normalized = getattr(value, "value", value)
        return str(normalized).lower()
