from decimal import Decimal

from app.models.document import DocumentType
from app.services.proactive_reminder_service import ProactiveReminderService
from tests.fixtures.models import (
    create_test_document,
    create_test_property,
    create_test_user,
)


def test_property_health_reminder_links_directly_to_asset_detail(db_session):
    user = create_test_user(db_session, email="asset-reminder@example.com")
    prop = create_test_property(
        db_session,
        user=user,
        street="Wiedner Hauptstr. 63/2/14",
        city="Wien",
        postal_code="1040",
        name="macbook",
    )

    reminders = ProactiveReminderService(db_session).get_reminders(user, 2024)

    kaufvertrag_reminder = next(
        reminder
        for reminder in reminders
        if reminder.get("body_key") == "healthCheck.propertyNoKaufvertrag"
        and reminder.get("params", {}).get("address") == (prop.address or str(prop.id))
    )

    assert kaufvertrag_reminder["link"] == f"/properties/{prop.id}"
    detail_items = kaufvertrag_reminder["action_data"]["detail_items"]
    assert len(detail_items) == 1
    assert detail_items[0]["kind"] == "asset"
    assert detail_items[0]["href"] == f"/properties/{prop.id}"
    assert detail_items[0]["label"] == "macbook"


def test_multi_asset_and_document_health_reminders_include_detail_targets(db_session):
    user = create_test_user(db_session, email="multi-reminder@example.com")
    prop_a = create_test_property(
        db_session,
        user=user,
        street="Alpha 1",
        city="Wien",
        postal_code="1010",
        name="Alpha Asset",
    )
    prop_b = create_test_property(
        db_session,
        user=user,
        street="Beta 2",
        city="Wien",
        postal_code="1020",
        name="Beta Asset",
    )
    doc_a = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.RECEIPT,
        file_name="uncertain-a.pdf",
        confidence_score=Decimal("0.50"),
    )
    doc_b = create_test_document(
        db_session,
        user=user,
        document_type=DocumentType.INVOICE,
        file_name="uncertain-b.pdf",
        confidence_score=Decimal("0.55"),
    )

    reminders = ProactiveReminderService(db_session).get_reminders(user, 2024)

    afa_reminder = next(
        reminder
        for reminder in reminders
        if reminder.get("body_key") == "healthCheck.missingAfaSetup"
    )
    assert afa_reminder["link"] is None
    afa_targets = afa_reminder["action_data"]["detail_items"]
    assert {item["href"] for item in afa_targets} == {
        f"/properties/{prop_a.id}",
        f"/properties/{prop_b.id}",
    }

    low_conf_reminder = next(
        reminder
        for reminder in reminders
        if reminder.get("body_key") == "healthCheck.lowConfidenceDocuments"
    )
    assert low_conf_reminder["link"] is None
    low_conf_targets = low_conf_reminder["action_data"]["detail_items"]
    assert {item["href"] for item in low_conf_targets} == {
        f"/documents/{doc_a.id}",
        f"/documents/{doc_b.id}",
    }
    assert {item["kind"] for item in low_conf_targets} == {"document"}
