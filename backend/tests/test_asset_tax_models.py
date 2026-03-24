from datetime import date
from decimal import Decimal

from app.models.asset_event import AssetEvent, AssetEventTriggerSource, AssetEventType
from app.models.asset_policy_snapshot import AssetPolicySnapshot
from app.models.user import UserType
from tests.fixtures.models import create_test_property, create_test_user


def test_asset_policy_snapshot_and_event_persist_with_property(db):
    user = create_test_user(
        db,
        email="asset-model@example.com",
        user_type=UserType.SELF_EMPLOYED,
    )
    property_record = create_test_property(
        db,
        user=user,
        street="Asset Street 1",
        city="Wien",
        postal_code="1010",
        asset_type="computer",
        sub_category="computer",
        name="MacBook Pro",
        useful_life_years=3,
        supplier="Example Supplier GmbH",
        purchase_date=date(2026, 3, 10),
        purchase_price=Decimal("1499.00"),
        building_value=Decimal("1199.20"),
    )

    snapshot = AssetPolicySnapshot(
        user_id=user.id,
        property_id=property_record.id,
        effective_anchor_date=date(2026, 3, 20),
        snapshot_payload={"decision": "create_asset_suggestion"},
        rule_ids=["VAT-001", "GWG-003"],
    )
    event = AssetEvent(
        user_id=user.id,
        property_id=property_record.id,
        event_type=AssetEventType.PUT_INTO_USE,
        trigger_source=AssetEventTriggerSource.USER,
        event_date=date(2026, 3, 20),
        payload={"put_into_use_date": "2026-03-20"},
    )

    db.add(snapshot)
    db.add(event)
    db.commit()
    db.refresh(snapshot)
    db.refresh(event)
    db.refresh(property_record)

    assert snapshot.property_id == property_record.id
    assert event.property_id == property_record.id
    assert property_record.policy_snapshots[0].id == snapshot.id
    assert property_record.asset_events[0].id == event.id
    assert user.asset_policy_snapshots[0].id == snapshot.id
    assert user.asset_events[0].id == event.id
