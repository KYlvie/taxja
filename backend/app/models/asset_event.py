"""Asset lifecycle event log for recomputation and auditability."""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Date, DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class AssetEventType(str, Enum):
    ACQUIRED = "acquired"
    PUT_INTO_USE = "put_into_use"
    RECLASSIFIED = "reclassified"
    BUSINESS_USE_CHANGED = "business_use_changed"
    DEGRESSIVE_TO_LINEAR_SWITCH = "degressive_to_linear_switch"
    IFB_FLAGGED = "ifb_flagged"
    IFB_CLAIMED = "ifb_claimed"
    SOLD = "sold"
    SCRAPPED = "scrapped"
    PRIVATE_WITHDRAWAL = "private_withdrawal"


class AssetEventTriggerSource(str, Enum):
    SYSTEM = "system"
    USER = "user"
    POLICY_RECOMPUTE = "policy_recompute"
    IMPORT = "import"


class AssetEvent(Base):
    """Immutable event record for asset tax lifecycle changes."""

    __tablename__ = "asset_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(
        SQLEnum(AssetEventType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    trigger_source = Column(
        SQLEnum(AssetEventTriggerSource, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AssetEventTriggerSource.SYSTEM,
    )
    event_date = Column(Date, nullable=False, index=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="asset_events")
    property = relationship("Property", back_populates="asset_events")


__all__ = ["AssetEvent", "AssetEventType", "AssetEventTriggerSource"]
