"""Tests for automatic property status transition when rental contracts expire."""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.property import Property, PropertyType, PropertyStatus
from app.models.recurring_transaction import (
    RecurringTransaction,
    RecurringTransactionType,
    RecurrenceFrequency,
)


class FakeQuery:
    """Minimal query mock that supports chaining."""

    def __init__(self, results=None):
        self._results = results or []

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._results

    def count(self):
        return len(self._results)

    def order_by(self, *args):
        return self


class TestRecalculateRentalPercentage:
    """Test that recalculate_rental_percentage correctly transitions property_type."""

    def _make_property(self, property_type=PropertyType.RENTAL, rental_pct=100):
        prop = MagicMock(spec=Property)
        prop.id = uuid4()
        prop.user_id = 1
        prop.property_type = property_type
        prop.rental_percentage = Decimal(str(rental_pct))
        prop.status = PropertyStatus.ACTIVE
        return prop

    def _make_contract(self, prop_id, is_active=True, end_date=None, unit_pct=100):
        rt = MagicMock(spec=RecurringTransaction)
        rt.id = 1
        rt.property_id = prop_id
        rt.user_id = 1
        rt.recurring_type = RecurringTransactionType.RENTAL_INCOME
        rt.is_active = is_active
        rt.end_date = end_date
        rt.unit_percentage = Decimal(str(unit_pct))
        return rt

    @patch("app.services.property_service.PropertyService._invalidate_metrics_cache")
    @patch("app.services.property_service.PropertyService._invalidate_portfolio_cache")
    @patch("app.services.property_service.PropertyService._invalidate_property_list_cache")
    def test_all_contracts_expired_sets_owner_occupied(self, *mocks):
        """When all rental contracts are expired, property_type → OWNER_OCCUPIED."""
        from app.services.property_service import PropertyService

        prop = self._make_property(PropertyType.RENTAL, 100)
        expired_contract = self._make_contract(
            prop.id, is_active=False, end_date=date.today() - timedelta(days=30)
        )

        db = MagicMock()
        # _validate_ownership returns the property
        db.query.return_value = FakeQuery()

        service = PropertyService.__new__(PropertyService)
        service.db = db
        service._redis_client = None
        service.afa_calculator = MagicMock()

        # Mock _validate_ownership
        service._validate_ownership = MagicMock(return_value=prop)

        # First query: active rentals → empty (all expired)
        # Second query: all rentals count → 1
        call_count = [0]
        original_query = db.query

        def side_effect_query(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Active rentals query
                return FakeQuery([])
            else:
                # All rentals count query
                return FakeQuery([expired_contract])

        db.query.side_effect = side_effect_query

        service.recalculate_rental_percentage(prop.id, prop.user_id)

        assert prop.property_type == PropertyType.OWNER_OCCUPIED
        assert prop.rental_percentage == Decimal("0.00")

    @patch("app.services.property_service.PropertyService._invalidate_metrics_cache")
    @patch("app.services.property_service.PropertyService._invalidate_portfolio_cache")
    @patch("app.services.property_service.PropertyService._invalidate_property_list_cache")
    def test_active_contract_keeps_rental(self, *mocks):
        """When active contracts exist, property_type stays RENTAL."""
        from app.services.property_service import PropertyService

        prop = self._make_property(PropertyType.RENTAL, 100)
        active_contract = self._make_contract(prop.id, is_active=True, unit_pct=100)

        db = MagicMock()
        service = PropertyService.__new__(PropertyService)
        service.db = db
        service._redis_client = None
        service.afa_calculator = MagicMock()
        service._validate_ownership = MagicMock(return_value=prop)

        call_count = [0]

        def side_effect_query(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeQuery([active_contract])
            else:
                return FakeQuery([active_contract])

        db.query.side_effect = side_effect_query

        service.recalculate_rental_percentage(prop.id, prop.user_id)

        assert prop.property_type == PropertyType.RENTAL
        assert prop.rental_percentage == Decimal("100.00")


class TestSyncExpiredRentalContracts:
    """Test the _sync_expired_rental_contracts method on get_property."""

    def test_expired_active_contracts_get_deactivated(self):
        """Contracts past end_date should be deactivated on property load."""
        from app.services.property_service import PropertyService

        prop_id = uuid4()
        prop = MagicMock(spec=Property)
        prop.id = prop_id
        prop.user_id = 1
        prop.status = PropertyStatus.ACTIVE

        rt = MagicMock(spec=RecurringTransaction)
        rt.is_active = True
        rt.end_date = date.today() - timedelta(days=60)
        rt.property_id = prop_id
        rt.recurring_type = RecurringTransactionType.RENTAL_INCOME

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [rt]

        service = PropertyService.__new__(PropertyService)
        service.db = db
        service._redis_client = None
        service.afa_calculator = MagicMock()
        service.recalculate_rental_percentage = MagicMock()

        service._sync_expired_rental_contracts(prop, 1)

        # Contract should be deactivated
        assert rt.is_active is False
        db.commit.assert_called_once()
        service.recalculate_rental_percentage.assert_called_once_with(prop_id, 1)

    def test_no_expired_contracts_no_action(self):
        """When no expired active contracts exist, nothing happens."""
        from app.services.property_service import PropertyService

        prop = MagicMock(spec=Property)
        prop.id = uuid4()

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        service = PropertyService.__new__(PropertyService)
        service.db = db
        service._redis_client = None
        service.afa_calculator = MagicMock()
        service.recalculate_rental_percentage = MagicMock()

        service._sync_expired_rental_contracts(prop, 1)

        db.commit.assert_not_called()
        service.recalculate_rental_percentage.assert_not_called()
