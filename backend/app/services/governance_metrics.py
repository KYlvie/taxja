"""Unified governance metrics service.

Provides observability into the classification governance framework:
- Rule hit rates (soft vs strict)
- Soft→strict upgrade rate
- Training data source distribution
- requires_review rate from deductibility checks
- LLM unverified exclusion counts
"""
import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.classification_correction import ClassificationCorrection
from app.models.user_classification_rule import UserClassificationRule

logger = logging.getLogger(__name__)


class GovernanceMetricsService:
    """Computes governance and observability metrics from DB state."""

    def __init__(self, db: Session):
        self.db = db

    def get_rule_metrics(self, user_id: Optional[int] = None) -> dict:
        """Rule system metrics: soft/strict counts, hit rates, upgrades.

        Args:
            user_id: If provided, scope to a single user. Otherwise system-wide.
        """
        q = self.db.query(UserClassificationRule)
        if user_id:
            q = q.filter(UserClassificationRule.user_id == user_id)

        total = q.count()
        if total == 0:
            return {
                "total_rules": 0,
                "strict_rules": 0,
                "soft_rules": 0,
                "frozen_rules": 0,
                "strict_rule_ratio": 0.0,
                "soft_rule_ratio": 0.0,
                "total_hits": 0,
                "strict_hits": 0,
                "soft_hits": 0,
                "strict_hit_rate": 0.0,
                "soft_hit_rate": 0.0,
                "avg_soft_confidence": 0.0,
                "avg_strict_confidence": 0.0,
            }

        strict_count = q.filter(UserClassificationRule.rule_type == "strict").count()
        soft_count = q.filter(UserClassificationRule.rule_type == "soft").count()
        frozen_count = q.filter(UserClassificationRule.frozen == True).count()

        # Hit counts by type
        strict_hits = (
            self.db.query(func.coalesce(func.sum(UserClassificationRule.hit_count), 0))
            .filter(UserClassificationRule.rule_type == "strict")
        )
        soft_hits = (
            self.db.query(func.coalesce(func.sum(UserClassificationRule.hit_count), 0))
            .filter(UserClassificationRule.rule_type == "soft")
        )
        if user_id:
            strict_hits = strict_hits.filter(UserClassificationRule.user_id == user_id)
            soft_hits = soft_hits.filter(UserClassificationRule.user_id == user_id)

        strict_hits_val = int(strict_hits.scalar() or 0)
        soft_hits_val = int(soft_hits.scalar() or 0)
        total_hits = strict_hits_val + soft_hits_val

        # Average confidence by type
        avg_soft = (
            self.db.query(func.avg(UserClassificationRule.confidence))
            .filter(UserClassificationRule.rule_type == "soft")
        )
        avg_strict = (
            self.db.query(func.avg(UserClassificationRule.confidence))
            .filter(UserClassificationRule.rule_type == "strict")
        )
        if user_id:
            avg_soft = avg_soft.filter(UserClassificationRule.user_id == user_id)
            avg_strict = avg_strict.filter(UserClassificationRule.user_id == user_id)

        return {
            "total_rules": total,
            "strict_rules": strict_count,
            "soft_rules": soft_count,
            "frozen_rules": frozen_count,
            "strict_rule_ratio": round(strict_count / total, 4) if total else 0.0,
            "soft_rule_ratio": round(soft_count / total, 4) if total else 0.0,
            "total_hits": total_hits,
            "strict_hits": strict_hits_val,
            "soft_hits": soft_hits_val,
            "strict_hit_rate": round(strict_hits_val / total_hits, 4) if total_hits else 0.0,
            "soft_hit_rate": round(soft_hits_val / total_hits, 4) if total_hits else 0.0,
            "avg_soft_confidence": round(float(avg_soft.scalar() or 0), 4),
            "avg_strict_confidence": round(float(avg_strict.scalar() or 0), 4),
        }

    def get_correction_source_metrics(self) -> dict:
        """Training data source distribution and exclusion counts."""
        rows = (
            self.db.query(
                ClassificationCorrection.source,
                func.count(ClassificationCorrection.id),
            )
            .group_by(ClassificationCorrection.source)
            .all()
        )

        by_source = {src or "legacy_null": cnt for src, cnt in rows}
        total = sum(by_source.values())

        # Trainable = human_verified + llm_consensus + legacy_null
        trainable = (
            by_source.get("human_verified", 0)
            + by_source.get("llm_consensus", 0)
            + by_source.get("legacy_null", 0)
        )
        excluded = total - trainable

        return {
            "total_corrections": total,
            "by_source": by_source,
            "trainable_count": trainable,
            "excluded_count": excluded,
            "human_verified_count": by_source.get("human_verified", 0),
            "llm_verified_count": by_source.get("llm_verified", 0),
            "llm_unverified_count": by_source.get("llm_unverified", 0),
            "llm_consensus_count": by_source.get("llm_consensus", 0),
            "system_default_count": by_source.get("system_default", 0),
            "legacy_null_count": by_source.get("legacy_null", 0),
            "human_verified_ratio": (
                round(by_source.get("human_verified", 0) / total, 4) if total else 0.0
            ),
            "llm_unverified_exclusion_rate": (
                round(by_source.get("llm_unverified", 0) / total, 4) if total else 0.0
            ),
        }

    def get_soft_to_strict_upgrade_count(self) -> int:
        """Count rules that were upgraded from soft to strict.

        Heuristic: strict rules with hit_count > 1 were likely upgraded
        (created as soft by LLM, then confirmed by human).
        A more precise approach would need an audit log, but this is a
        reasonable proxy for now.
        """
        return (
            self.db.query(UserClassificationRule)
            .filter(
                UserClassificationRule.rule_type == "strict",
                UserClassificationRule.hit_count > 1,
            )
            .count()
        )

    def get_full_report(self, user_id: Optional[int] = None) -> dict:
        """Combined governance metrics report."""
        rule_metrics = self.get_rule_metrics(user_id)
        correction_metrics = self.get_correction_source_metrics()
        upgrade_count = self.get_soft_to_strict_upgrade_count()

        return {
            "rules": rule_metrics,
            "corrections": correction_metrics,
            "soft_to_strict_upgrades": upgrade_count,
        }
