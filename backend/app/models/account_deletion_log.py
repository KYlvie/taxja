"""Account deletion log model for GDPR compliance audit trail"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.db.base import Base


class AccountDeletionLog(Base):
    """Immutable audit record created after hard-deleting a user account.

    Stores only anonymised data (SHA-256 hash of user id + salt) so that
    the platform can prove deletion occurred without retaining PII.
    """
    __tablename__ = "account_deletion_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    anonymous_user_hash = Column(String(64), nullable=False)  # SHA-256(user_id + salt)
    deleted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_types_deleted = Column(JSON, nullable=True)  # e.g. ["transactions", "documents", ...]
    deletion_method = Column(String(20), nullable=True)  # "scheduled" | "admin_manual"
    initiated_by = Column(String(20), nullable=True)  # "user" | "admin" | "system"

    def __repr__(self):
        return (
            f"<AccountDeletionLog(id={self.id}, "
            f"hash={self.anonymous_user_hash[:8]}..., "
            f"deleted_at={self.deleted_at})>"
        )
