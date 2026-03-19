"""Tax policy snapshots for asset creation and lifecycle explainability."""
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class AssetPolicySnapshot(Base):
    """Frozen tax policy context anchored to put-into-use date."""

    __tablename__ = "asset_policy_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_version = Column(String(50), nullable=False, default="asset_tax_engine_v1")
    jurisdiction = Column(String(10), nullable=False, default="AT")
    effective_anchor_date = Column(Date, nullable=False, index=True)
    snapshot_payload = Column(JSON, nullable=False)
    rule_ids = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="asset_policy_snapshots")
    property = relationship("Property", back_populates="policy_snapshots")


__all__ = ["AssetPolicySnapshot"]
