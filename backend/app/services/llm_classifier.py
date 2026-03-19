"""
LLM-based transaction classifier with user-context-aware caching.

Called as a fallback when rule-based and ML classifiers both return
low confidence (< LLM_THRESHOLD). Results are cached by
(merchant_normalized, user_type, business_type, business_industry)
so the LLM is only called once per unique combination.

Cache entries also feed back into the ML training pipeline via
ClassificationCorrection records.
"""
import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Valid expense categories (must match ExpenseCategory enum values)
VALID_EXPENSE_CATEGORIES = {
    "groceries", "other", "commuting", "home_office", "office_supplies",
    "equipment", "travel", "marketing", "professional_services",
    "maintenance", "property_tax", "loan_interest", "insurance",
    "utilities", "vehicle", "telecom", "rent", "bank_fees",
    "svs_contributions", "depreciation", "cleaning", "clothing",
    "software", "shipping", "fuel", "education",
    "property_management_fees", "property_insurance", "depreciation_afa",
}

# Valid income categories
VALID_INCOME_CATEGORIES = {
    "employment", "self_employment", "business", "rental",
    "capital_gains", "agriculture", "other_income",
}


@dataclass
class LLMClassificationResult:
    """Result from LLM classification."""
    category: str
    confidence: Decimal
    category_type: str  # "income" or "expense"
    is_deductible: Optional[bool] = None
    deduction_reason: Optional[str] = None
    cached: bool = False


class _CacheEntry:
    """In-memory cache entry with TTL (fallback when Redis unavailable)."""
    __slots__ = ("value", "expires_at")

    def __init__(self, value: LLMClassificationResult, ttl: int):
        self.value = value
        self.expires_at = time.monotonic() + ttl


class _RedisClassificationCache:
    """
    Redis-backed classification cache with in-memory fallback.

    Keys are stored under the prefix ``llm_cls:`` with a 7-day TTL.
    If Redis is not available at connect time, all operations silently
    fall back to the in-memory ``_CacheEntry`` dict so the classifier
    keeps working without any external dependency.
    """

    PREFIX = "llm_cls:"

    def __init__(self, ttl: int, max_memory_size: int = 10_000):
        self._ttl = ttl
        self._max_memory_size = max_memory_size
        self._redis = None  # type: ignore[assignment]
        self._memory: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._connect()

    # -- connection --------------------------------------------------------

    def _connect(self) -> None:
        """Try to connect to Redis synchronously. Fail silently."""
        try:
            import redis as sync_redis
            from app.core.config import settings

            self._redis = sync_redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._redis.ping()
            logger.info("LLM classification cache: using Redis")
        except Exception as e:
            self._redis = None
            logger.info("LLM classification cache: Redis unavailable (%s), using in-memory", e)

    @property
    def _use_redis(self) -> bool:
        return self._redis is not None

    # -- public API --------------------------------------------------------

    def get(self, key: str) -> Optional[LLMClassificationResult]:
        if self._use_redis:
            return self._redis_get(key)
        return self._memory_get(key)

    def set(self, key: str, value: LLMClassificationResult) -> None:
        if self._use_redis:
            self._redis_set(key, value)
        else:
            self._memory_set(key, value)

    def stats(self) -> Dict[str, Any]:
        if self._use_redis:
            try:
                keys = list(self._redis.scan_iter(match=f"{self.PREFIX}*", count=500))
                return {"backend": "redis", "total": len(keys)}
            except Exception:
                return {"backend": "redis", "total": -1}
        with self._lock:
            now = time.monotonic()
            active = sum(1 for v in self._memory.values() if now <= v.expires_at)
            return {"backend": "memory", "total": len(self._memory), "active": active}

    # -- Redis implementation ----------------------------------------------

    def _redis_get(self, key: str) -> Optional[LLMClassificationResult]:
        try:
            raw = self._redis.get(f"{self.PREFIX}{key}")
            if raw is None:
                return None
            data = json.loads(raw)
            return LLMClassificationResult(
                category=data["category"],
                confidence=Decimal(str(data["confidence"])),
                category_type=data["category_type"],
                is_deductible=data.get("is_deductible"),
                deduction_reason=data.get("deduction_reason"),
                cached=True,
            )
        except Exception as e:
            logger.debug("Redis cache get error: %s", e)
            return None

    def _redis_set(self, key: str, value: LLMClassificationResult) -> None:
        try:
            data = {
                "category": value.category,
                "confidence": str(value.confidence),
                "category_type": value.category_type,
                "is_deductible": value.is_deductible,
                "deduction_reason": value.deduction_reason,
            }
            self._redis.setex(f"{self.PREFIX}{key}", self._ttl, json.dumps(data))
        except Exception as e:
            logger.debug("Redis cache set error: %s", e)

    # -- In-memory fallback ------------------------------------------------

    def _memory_get(self, key: str) -> Optional[LLMClassificationResult]:
        with self._lock:
            entry = self._memory.get(key)
            if entry is None:
                return None
            if time.monotonic() > entry.expires_at:
                del self._memory[key]
                return None
            return entry.value

    def _memory_set(self, key: str, value: LLMClassificationResult) -> None:
        with self._lock:
            if len(self._memory) >= self._max_memory_size:
                self._evict_expired()
            self._memory[key] = _CacheEntry(value, self._ttl)

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._memory.items() if now > v.expires_at]
        for k in expired:
            del self._memory[k]
        if len(self._memory) >= self._max_memory_size:
            to_remove = sorted(
                self._memory.items(), key=lambda kv: kv[1].expires_at
            )[: self._max_memory_size // 4]
            for k, _ in to_remove:
                del self._memory[k]


class LLMTransactionClassifier:
    """
    LLM fallback classifier with user-context-aware caching.

    Cache key = hash(merchant_norm, user_type, business_type, business_industry)
    Cache TTL = 7 days (classification of a merchant for a given user profile
    doesn't change often).

    Cache is persisted in Redis so it survives service restarts and is
    shared across multiple worker instances. Falls back to in-memory
    if Redis is unavailable.
    """

    CACHE_TTL = 7 * 86400  # 7 days
    MAX_CACHE_SIZE = 10_000

    # Confidence thresholds for quality gating
    MIN_CACHEABLE_CONFIDENCE = Decimal("0.60")   # Below this → don't cache / don't store correction
    DEFAULT_CONFIDENCE = Decimal("0.75")          # Fallback when LLM doesn't return confidence
    MIN_LLM_CONFIDENCE = Decimal("0.50")          # Floor clamp
    MAX_LLM_CONFIDENCE = Decimal("0.95")          # Ceiling clamp

    # LLM prompt for classification (now requests confidence score)
    CLASSIFICATION_PROMPT = (
        "Du bist ein österreichischer Steuerexperte. Klassifiziere diese Transaktion.\n\n"
        "BENUTZER-PROFIL:\n"
        "- Typ: {user_type}\n"
        "- Berufstyp: {business_type}\n"
        "- Branche: {business_industry}\n\n"
        "TRANSAKTION:\n"
        "- Beschreibung: {description}\n"
        "- Betrag: €{amount}\n"
        "- Art: {txn_type}\n\n"
        "AUFGABE: Bestimme die Kategorie, deine Konfidenz (0.0-1.0), und ob die Ausgabe "
        "steuerlich absetzbar ist.\n\n"
        "KATEGORIEN für Ausgaben: groceries, commuting, home_office, office_supplies, "
        "equipment, travel, marketing, professional_services, maintenance, property_tax, "
        "loan_interest, insurance, utilities, vehicle, telecom, rent, bank_fees, "
        "svs_contributions, depreciation, cleaning, clothing, software, shipping, fuel, "
        "education, other\n\n"
        "KATEGORIEN für Einnahmen: employment, self_employment, business, rental, "
        "capital_gains, agriculture, other_income\n\n"
        "REGELN für Absetzbarkeit:\n"
        "- Arbeitnehmer: Nur Pendlerpauschale, Home-Office (max €300), Fortbildung\n"
        "- Freiberufler/Gewerbetreibende: Betriebsausgaben je nach Branche\n"
        "- Vermieter: Nur vermietungsbezogene Kosten\n"
        "- Branche ist entscheidend: Gastro darf Lebensmittel absetzen, IT nicht\n\n"
        "KONFIDENZ-REGELN:\n"
        "- 0.9-1.0: Du bist dir sehr sicher (bekannter Händler, eindeutige Kategorie)\n"
        "- 0.7-0.9: Wahrscheinlich richtig, aber es gibt Alternativen\n"
        "- 0.5-0.7: Unsicher, mehrere Kategorien möglich\n\n"
        "Antworte NUR mit JSON:\n"
        '{{"category": "...", "confidence": 0.85, "is_deductible": true/false, '
        '"reason": "kurze Begründung auf Deutsch"}}'
    )

    def __init__(self):
        self._cache = _RedisClassificationCache(
            ttl=self.CACHE_TTL, max_memory_size=self.MAX_CACHE_SIZE
        )
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            from app.services.llm_service import get_llm_service
            self._llm = get_llm_service()
        return self._llm

    @property
    def is_available(self) -> bool:
        try:
            return self.llm.is_available
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self,
        description: str,
        amount: float,
        txn_type: str,
        user_type: str = "employee",
        business_type: str = "",
        business_industry: str = "",
    ) -> Optional[LLMClassificationResult]:
        """
        Classify a transaction using LLM with user-context-aware caching.

        Args:
            description: Transaction description (e.g. "BILLA Filiale 1234")
            amount: Transaction amount
            txn_type: "income" or "expense"
            user_type: User type (employee, self_employed, landlord, mixed, gmbh)
            business_type: Self-employed sub-type (freiberufler, gewerbetreibende, ...)
            business_industry: Specific industry (gastronomie, IT, fotografie, ...)

        Returns:
            LLMClassificationResult or None if LLM unavailable/failed
        """
        if not self.is_available:
            logger.debug("LLM not available for transaction classification")
            return None

        merchant = self._normalize_merchant(description)
        cache_key = self._build_cache_key(
            merchant, txn_type, user_type, business_type, business_industry
        )

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(
                "LLM classification cache hit: %s → %s (deductible=%s)",
                merchant, cached.category, cached.is_deductible,
            )
            cached.cached = True
            return cached

        # Call LLM
        result = self._call_llm(
            description, amount, txn_type,
            user_type, business_type, business_industry,
        )
        if result is None:
            return None

        # Only cache results with sufficient confidence to prevent
        # low-quality classifications from polluting the cache and
        # downstream ML training data.
        if result.confidence >= self.MIN_CACHEABLE_CONFIDENCE:
            self._cache.set(cache_key, result)
            logger.info(
                "LLM classified & cached: %s → %s (confidence=%s, deductible=%s)",
                merchant, result.category, result.confidence, result.is_deductible,
            )
        else:
            logger.info(
                "LLM classified but NOT cached (low confidence): %s → %s (confidence=%s)",
                merchant, result.category, result.confidence,
            )
        return result

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        description: str,
        amount: float,
        txn_type: str,
        user_type: str,
        business_type: str,
        business_industry: str,
    ) -> Optional[LLMClassificationResult]:
        """Call LLM to classify a transaction."""
        prompt = self.CLASSIFICATION_PROMPT.format(
            user_type=user_type or "employee",
            business_type=business_type or "N/A",
            business_industry=business_industry or "N/A",
            description=description,
            amount=f"{amount:.2f}",
            txn_type="Ausgabe" if "expense" in txn_type.lower() else "Einnahme",
        )

        try:
            response = self.llm.generate_simple(
                system_prompt=prompt,
                user_prompt="Klassifiziere diese Transaktion.",
                temperature=0.1,
                max_tokens=300,
            )
            return self._parse_response(response, txn_type)
        except Exception as e:
            logger.warning("LLM transaction classification failed: %s", e)
            return None

    def _parse_response(
        self, response: str, txn_type: str
    ) -> Optional[LLMClassificationResult]:
        """Parse LLM JSON response into a classification result."""
        if not response:
            return None

        text = response.strip()
        # Strip markdown code fences
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
            text = text.strip()

        # Extract JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            logger.warning("LLM classification: no JSON found in response")
            return None

        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            logger.warning("LLM classification: JSON parse failed: %s", e)
            return None

        category = (data.get("category") or "").lower().strip()
        is_expense = "expense" in txn_type.lower()

        # Validate category
        valid = VALID_EXPENSE_CATEGORIES if is_expense else VALID_INCOME_CATEGORIES
        if category not in valid:
            logger.warning(
                "LLM returned invalid category '%s' for %s", category, txn_type
            )
            category = "other" if is_expense else "other_income"

        is_deductible = data.get("is_deductible")
        if not isinstance(is_deductible, bool):
            is_deductible = None

        reason = data.get("reason") or data.get("deduction_reason") or ""

        # ① Dynamic confidence extraction
        confidence = self._extract_confidence(data)

        return LLMClassificationResult(
            category=category,
            confidence=confidence,
            category_type="expense" if is_expense else "income",
            is_deductible=is_deductible,
            deduction_reason=str(reason)[:200] if reason else None,
        )

    def _extract_confidence(self, data: dict) -> Decimal:
        """
        Extract and validate confidence from LLM JSON response.

        Falls back to DEFAULT_CONFIDENCE if the LLM didn't return a valid
        number, and clamps to [MIN_LLM_CONFIDENCE, MAX_LLM_CONFIDENCE].
        """
        raw = data.get("confidence")
        if raw is None:
            return self.DEFAULT_CONFIDENCE
        try:
            val = Decimal(str(raw))
        except Exception:
            return self.DEFAULT_CONFIDENCE
        # Clamp to valid range
        val = max(self.MIN_LLM_CONFIDENCE, min(self.MAX_LLM_CONFIDENCE, val))
        return val

    # ------------------------------------------------------------------
    # Merchant normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_merchant(description: str) -> str:
        """
        Normalize merchant name for cache key stability.

        "BILLA FILIALE 1234 WIEN" → "billa"
        "Zahlung an Müller GmbH" → "müller gmbh"
        """
        text = description.lower().strip()
        # Remove common prefixes
        for prefix in ("zahlung an ", "überweisung an ", "lastschrift ", "gutschrift "):
            if text.startswith(prefix):
                text = text[len(prefix):]
        # Remove branch/filiale numbers and addresses
        text = re.sub(r"\b(filiale|fil\.?|nr\.?|kasse)\s*\d+", "", text)
        # Remove postal codes and city names after numbers
        text = re.sub(r"\b\d{4}\s+\w+$", "", text)
        # Remove trailing numbers (receipt numbers, etc.)
        text = re.sub(r"\s+\d+\s*$", "", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    @staticmethod
    def _build_cache_key(
        merchant: str,
        txn_type: str,
        user_type: str,
        business_type: str,
        business_industry: str,
    ) -> str:
        raw = f"{merchant}|{txn_type}|{user_type}|{business_type}|{business_industry}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics for monitoring."""
        return self._cache.stats()


# Singleton
_llm_classifier: Optional[LLMTransactionClassifier] = None


def get_llm_classifier() -> LLMTransactionClassifier:
    global _llm_classifier
    if _llm_classifier is None:
        _llm_classifier = LLMTransactionClassifier()
    return _llm_classifier
