"""Per-user classification override service.

Manages user-specific description→category rules that take priority over
the global rule-based / ML / LLM classification pipeline.

Key design: rules are keyed on the FULL normalized description, not just
the merchant name. "amazon druckerpatrone" and "amazon kleidung" produce
different rules because the same merchant can sell items in different
tax categories.

Rules are auto-generated from user corrections and LLM results.
"""
import logging
import re
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user_classification_rule import UserClassificationRule

logger = logging.getLogger(__name__)

# Patterns to strip: noise that varies between identical purchases
# but NOT product/item keywords
_STRIP_PATTERNS = [
    r"\b\d{4,}\b",                        # long numbers (card refs, store IDs)
    r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b",    # dates like 15.03.2026
    r"\bAT\d+\b",                          # Austrian IBAN fragments
    r"\b[A-Z]{2}\d{2}\b",                  # IBAN country prefix
    r"\b(filiale|fil\.?|kasse)\s*\d*\b",   # branch/register numbers
    r"\s{2,}",                             # collapse whitespace
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _STRIP_PATTERNS]


def normalize_description(description: str) -> str:
    """Normalize a transaction description into a stable lookup key.

    Strips noise (dates, card numbers, branch IDs) but preserves product
    keywords so that different items from the same merchant produce
    different keys.

    Examples:
        "AMAZON EU S.A.R.L. Druckerpatrone 12345" → "amazon eu s.a.r.l. druckerpatrone"
        "AMAZON EU S.A.R.L. Kleidung 67890"       → "amazon eu s.a.r.l. kleidung"
        "BILLA Filiale 1234 WIEN"                  → "billa wien"
    """
    text = description.lower().strip()
    for pat in _COMPILED:
        text = pat.sub(" ", text)
    return " ".join(text.split())


class UserClassificationService:
    """Manages per-user classification override rules."""

    def __init__(self, db: Session):
        self.db = db

    def lookup(
        self,
        user_id: int,
        description: str,
        txn_type: str,
    ) -> Optional[UserClassificationRule]:
        """
        Look up a per-user rule for the given transaction description.

        Returns the matching rule or None if no user override exists.
        """
        norm = normalize_description(description)
        if not norm:
            return None

        return (
            self.db.query(UserClassificationRule)
            .filter(
                UserClassificationRule.user_id == user_id,
                UserClassificationRule.normalized_description == norm,
                UserClassificationRule.txn_type == txn_type,
            )
            .first()
        )

    def upsert_rule(
        self,
        user_id: int,
        description: str,
        txn_type: str,
        category: str,
        rule_type: str = "strict",
    ) -> UserClassificationRule:
        """
        Create or update a per-user classification rule.

        If a rule already exists for (user, normalized_description, type),
        update it. Otherwise create a new one.

        Args:
            rule_type: "strict" for human-confirmed, "soft" for LLM-inferred.
        """
        norm = normalize_description(description)

        existing = (
            self.db.query(UserClassificationRule)
            .filter(
                UserClassificationRule.user_id == user_id,
                UserClassificationRule.normalized_description == norm,
                UserClassificationRule.txn_type == txn_type,
            )
            .first()
        )

        if existing:
            existing.category = category
            existing.hit_count += 1
            existing.original_description = description
            # Upgrade soft → strict if a human confirms, but never downgrade
            if rule_type == "strict" and existing.rule_type != "strict":
                existing.rule_type = "strict"
                existing.confidence = Decimal("1.00")
            self.db.flush()
            logger.info(
                "Updated user rule: user=%s desc=%r → %s (hits=%d, type=%s)",
                user_id, norm, category, existing.hit_count, existing.rule_type,
            )
            return existing

        # Soft rules start with lower confidence
        confidence = Decimal("1.00") if rule_type == "strict" else Decimal("0.80")

        rule = UserClassificationRule(
            user_id=user_id,
            normalized_description=norm,
            original_description=description,
            txn_type=txn_type,
            category=category,
            confidence=confidence,
            hit_count=1,
            rule_type=rule_type,
        )
        self.db.add(rule)
        self.db.flush()
        logger.info(
            "Created user rule: user=%s desc=%r → %s (type=%s)",
            user_id, norm, category, rule_type,
        )
        return rule

    def delete_rule(self, user_id: int, rule_id: int) -> bool:
        """Delete a specific user rule."""
        deleted = (
            self.db.query(UserClassificationRule)
            .filter(
                UserClassificationRule.id == rule_id,
                UserClassificationRule.user_id == user_id,
            )
            .delete()
        )
        self.db.flush()
        return deleted > 0

    def list_rules(self, user_id: int) -> list:
        """List all classification rules for a user."""
        return (
            self.db.query(UserClassificationRule)
            .filter(UserClassificationRule.user_id == user_id)
            .order_by(UserClassificationRule.hit_count.desc())
            .all()
        )

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    def record_hit(self, rule: UserClassificationRule) -> None:
        """Record a rule hit — updates last_hit_at timestamp."""
        from datetime import datetime
        rule.last_hit_at = datetime.utcnow()
        self.db.flush()

    def record_conflict(self, rule: UserClassificationRule) -> None:
        """Record a conflict (human corrected away from this rule's category).

        Soft rules with >= 3 conflicts are automatically frozen.
        """
        rule.conflict_count += 1
        if rule.rule_type == "soft" and rule.conflict_count >= 3:
            rule.frozen = True
            logger.warning(
                "Soft rule frozen due to conflicts: user=%s desc=%r conflicts=%d",
                rule.user_id, rule.normalized_description, rule.conflict_count,
            )
        self.db.flush()

    def decay_stale_soft_rules(self, user_id: int, stale_days: int = 90) -> int:
        """Reduce confidence of soft rules not hit in `stale_days`.

        Returns the number of rules decayed.
        """
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=stale_days)

        stale = (
            self.db.query(UserClassificationRule)
            .filter(
                UserClassificationRule.user_id == user_id,
                UserClassificationRule.rule_type == "soft",
                UserClassificationRule.frozen == False,
                (
                    (UserClassificationRule.last_hit_at < cutoff)
                    | (UserClassificationRule.last_hit_at.is_(None))
                ),
            )
            .all()
        )

        decayed = 0
        for rule in stale:
            new_conf = max(Decimal("0.50"), rule.confidence - Decimal("0.10"))
            if new_conf != rule.confidence:
                rule.confidence = new_conf
                decayed += 1
                logger.info(
                    "Decayed soft rule: user=%s desc=%r conf=%s",
                    rule.user_id, rule.normalized_description, new_conf,
                )

        if decayed:
            self.db.flush()
        return decayed

    def archive_low_hit_rules(self, user_id: int, min_hits: int = 1, stale_days: int = 180) -> int:
        """Delete rules with <= min_hits that haven't been hit in stale_days.

        Returns the number of rules archived (deleted).
        """
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=stale_days)

        deleted = (
            self.db.query(UserClassificationRule)
            .filter(
                UserClassificationRule.user_id == user_id,
                UserClassificationRule.hit_count <= min_hits,
                (
                    (UserClassificationRule.last_hit_at < cutoff)
                    | (UserClassificationRule.last_hit_at.is_(None))
                ),
            )
            .delete(synchronize_session="fetch")
        )

        if deleted:
            self.db.flush()
            logger.info("Archived %d low-hit rules for user=%s", deleted, user_id)
        return deleted
