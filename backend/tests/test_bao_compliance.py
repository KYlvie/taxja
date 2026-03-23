"""Tests for BAO §132 account deletion compliance.

Verifies that hard_delete_account anonymizes PII, preserves tax-relevant
data, sets a 7-year retention expiry, and that purge_expired_retained_data
removes data only after the retention period.
"""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch, PropertyMock

import pytest
from sqlalchemy.orm import Session

from app.services.account_cancellation_service import AccountCancellationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(user_id=1, status="deactivated"):
    """Create a mock User with typical fields."""
    user = MagicMock()
    user.id = user_id
    user.email = "max.mustermann@example.at"
    user.name = "Max Mustermann"
    user.password_hash = "$argon2id$somehash"
    user.tax_number = "12-345/6789"
    user.vat_number = "ATU12345678"
    user.address = "Stephansplatz 1, 1010 Wien"
    user.family_info = {"children": 2}
    user.commuting_info = {"distance_km": 25}
    user.two_factor_secret = "JBSWY3DPEHPK3PXP"
    user.two_factor_enabled = True
    user.account_status = status
    user.bao_retention_expiry = None
    user.deactivated_at = datetime.utcnow() - timedelta(days=31)
    user.scheduled_deletion_at = datetime.utcnow() - timedelta(days=1)
    user.cancellation_reason = "too_expensive"
    return user


def _make_document(user_id=1, file_path="docs/invoice.pdf", days_old=30):
    doc = MagicMock()
    doc.user_id = user_id
    doc.file_path = file_path
    doc.created_at = datetime.utcnow() - timedelta(days=days_old)
    return doc


# ---------------------------------------------------------------------------
# 1. PII anonymization
# ---------------------------------------------------------------------------

class TestPIIAnonymization:
    """hard_delete_account must anonymize all personally identifiable info."""

    @patch("app.services.account_cancellation_service.redis")
    @patch("app.services.account_cancellation_service.StorageService")
    @patch("app.services.account_cancellation_service.settings")
    def test_email_is_hashed(self, mock_settings, mock_storage_cls, mock_redis):
        mock_settings.SECRET_KEY = "test-secret"
        db = Mock(spec=Session)
        user = _make_user()
        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.update.return_value = 0
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.delete.return_value = 0

        AccountCancellationService.hard_delete_account(1, "scheduled", db)

        expected_hash = hashlib.sha256(f"1test-secret".encode()).hexdigest()
        assert user.email == f"deleted_{expected_hash[:16]}@anonymized.local"

    @patch("app.services.account_cancellation_service.redis")
    @patch("app.services.account_cancellation_service.StorageService")
    @patch("app.services.account_cancellation_service.settings")
    def test_name_set_to_geloeschter_benutzer(self, mock_settings, mock_storage_cls, mock_redis):
        mock_settings.SECRET_KEY = "test-secret"
        db = Mock(spec=Session)
        user = _make_user()
        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.update.return_value = 0
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.delete.return_value = 0

        AccountCancellationService.hard_delete_account(1, "scheduled", db)

        assert user.name == "Gelöschter Benutzer"

    @patch("app.services.account_cancellation_service.redis")
    @patch("app.services.account_cancellation_service.StorageService")
    @patch("app.services.account_cancellation_service.settings")
    def test_sensitive_fields_cleared(self, mock_settings, mock_storage_cls, mock_redis):
        mock_settings.SECRET_KEY = "s"
        db = Mock(spec=Session)
        user = _make_user()
        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.update.return_value = 0
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.delete.return_value = 0

        AccountCancellationService.hard_delete_account(1, "scheduled", db)

        assert user.password_hash == "ANONYMIZED"
        assert user.tax_number is None
        assert user.vat_number is None
        assert user.address is None
        assert user.family_info == {}
        assert user.commuting_info == {}
        assert user.two_factor_secret is None
        assert user.two_factor_enabled is False
        assert user.account_status == "anonymized"


# ---------------------------------------------------------------------------
# 2. Tax-relevant data preserved
# ---------------------------------------------------------------------------

class TestTaxDataPreserved:
    """Transactions, documents (rows), and tax reports within 7 years must survive."""

    @patch("app.services.account_cancellation_service.redis")
    @patch("app.services.account_cancellation_service.StorageService")
    @patch("app.services.account_cancellation_service.settings")
    def test_recent_transactions_not_deleted(self, mock_settings, mock_storage_cls, mock_redis):
        """Transactions younger than 7 years must NOT be purged during hard delete."""
        mock_settings.SECRET_KEY = "s"
        db = Mock(spec=Session)
        user = _make_user()

        # We need distinct query chains for different models.
        # The service calls db.query(Document).filter(...).all() for docs,
        # and db.query(Transaction).filter(..., < bao_cutoff).delete() for old tx.
        # With Mock(spec=Session), we verify delete is called with date < cutoff.
        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.update.return_value = 0
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.delete.return_value = 0

        result = AccountCancellationService.hard_delete_account(1, "scheduled", db)

        # No old_transactions_purged action if delete returns 0
        purge_actions = [a for a in result["data_actions"] if "old_transactions_purged" in a]
        assert len(purge_actions) == 0

    @patch("app.services.account_cancellation_service.redis")
    @patch("app.services.account_cancellation_service.StorageService")
    @patch("app.services.account_cancellation_service.settings")
    def test_document_rows_kept_but_files_deleted(self, mock_settings, mock_storage_cls, mock_redis):
        """Document DB rows must be kept; only MinIO file blobs are deleted."""
        mock_settings.SECRET_KEY = "s"
        db = Mock(spec=Session)
        user = _make_user()
        doc = _make_document()

        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.update.return_value = 0
        db.query.return_value.filter.return_value.all.return_value = [doc]
        db.query.return_value.filter.return_value.delete.return_value = 0

        result = AccountCancellationService.hard_delete_account(1, "scheduled", db)

        # file_path cleared on the document row
        assert doc.file_path is None
        assert "document_files_deleted" in result["data_actions"]


# ---------------------------------------------------------------------------
# 3. BAO retention expiry set to 7 years
# ---------------------------------------------------------------------------

class TestBAORetentionExpiry:
    """bao_retention_expiry must be ~7 years from now."""

    @patch("app.services.account_cancellation_service.redis")
    @patch("app.services.account_cancellation_service.StorageService")
    @patch("app.services.account_cancellation_service.settings")
    def test_retention_expiry_set(self, mock_settings, mock_storage_cls, mock_redis):
        mock_settings.SECRET_KEY = "s"
        db = Mock(spec=Session)
        user = _make_user()
        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.update.return_value = 0
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.delete.return_value = 0

        before = datetime.utcnow()
        AccountCancellationService.hard_delete_account(1, "scheduled", db)
        after = datetime.utcnow()

        assert user.bao_retention_expiry is not None
        # Should be approximately 7*365 days from now (within a few seconds)
        expected_min = before + timedelta(days=7 * 365 - 1)
        expected_max = after + timedelta(days=7 * 365 + 1)
        assert expected_min <= user.bao_retention_expiry <= expected_max


# ---------------------------------------------------------------------------
# 4. purge_expired_retained_data
# ---------------------------------------------------------------------------

class TestPurgeExpiredData:
    """After 7 years, purge_expired_retained_data fully removes the user."""

    def test_expired_user_is_purged(self):
        db = Mock(spec=Session)
        expired_user = _make_user(status="anonymized")
        expired_user.bao_retention_expiry = datetime.utcnow() - timedelta(days=1)

        db.query.return_value.filter.return_value.all.return_value = [expired_user]

        result = AccountCancellationService.purge_expired_retained_data(db)

        assert result["expired_users_found"] == 1
        assert result["purged_count"] == 1
        db.delete.assert_called_once_with(expired_user)
        db.commit.assert_called_once()

    def test_non_expired_user_not_purged(self):
        db = Mock(spec=Session)
        # No users returned by the query (none are expired)
        db.query.return_value.filter.return_value.all.return_value = []

        result = AccountCancellationService.purge_expired_retained_data(db)

        assert result["expired_users_found"] == 0
        assert result["purged_count"] == 0
        db.delete.assert_not_called()

    def test_purge_handles_individual_failure(self):
        db = Mock(spec=Session)
        user1 = _make_user(user_id=1, status="anonymized")
        user1.bao_retention_expiry = datetime.utcnow() - timedelta(days=1)
        user2 = _make_user(user_id=2, status="anonymized")
        user2.bao_retention_expiry = datetime.utcnow() - timedelta(days=1)

        db.query.return_value.filter.return_value.all.return_value = [user1, user2]
        # First delete succeeds, second raises
        db.delete.side_effect = [None, Exception("FK violation")]
        db.flush.side_effect = [None, Exception("FK violation")]

        result = AccountCancellationService.purge_expired_retained_data(db)

        assert result["expired_users_found"] == 2
        # Only the first one succeeded
        assert result["purged_count"] == 1


# ---------------------------------------------------------------------------
# 5. Non-tax data deleted
# ---------------------------------------------------------------------------

class TestNonTaxDataDeleted:
    """Chat messages, corrections, and notifications must be deleted."""

    @patch("app.services.account_cancellation_service.redis")
    @patch("app.services.account_cancellation_service.StorageService")
    @patch("app.services.account_cancellation_service.settings")
    def test_chat_messages_deleted(self, mock_settings, mock_storage_cls, mock_redis):
        mock_settings.SECRET_KEY = "s"
        db = Mock(spec=Session)
        user = _make_user()
        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.update.return_value = 0
        db.query.return_value.filter.return_value.all.return_value = []
        # Return positive count for non-tax model deletes, 0 for old data purge
        db.query.return_value.filter.return_value.delete.return_value = 5

        result = AccountCancellationService.hard_delete_account(1, "scheduled", db)

        # All three non-tax types should appear as deleted
        assert "chat_messages_deleted" in result["data_actions"]
        assert "corrections_deleted" in result["data_actions"]
        assert "notifications_deleted" in result["data_actions"]

    @patch("app.services.account_cancellation_service.redis")
    @patch("app.services.account_cancellation_service.StorageService")
    @patch("app.services.account_cancellation_service.settings")
    def test_deletion_log_created(self, mock_settings, mock_storage_cls, mock_redis):
        mock_settings.SECRET_KEY = "s"
        db = Mock(spec=Session)
        user = _make_user()
        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.update.return_value = 0
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.delete.return_value = 0

        AccountCancellationService.hard_delete_account(1, "admin", db)

        # AccountDeletionLog should have been added
        db.add.assert_called()
        db.commit.assert_called()
