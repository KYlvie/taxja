"""
RAG (Retrieval-Augmented Generation) service for AI Tax Assistant.
Combines knowledge base retrieval + user financial data + LLM generation.

⑤ Conversation summary: when history exceeds RECENT_WINDOW messages,
older messages are compressed into a one-paragraph summary so the LLM
retains long-term context without blowing the token budget.
"""
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from collections import OrderedDict
import hashlib
import threading

from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.document import Document
from app.models.user import User
from app.services.llm_service import get_llm_service
from app.services.chat_history_service import get_chat_history_service
from app.models.chat_message import MessageRole

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ⑤ In-memory conversation-summary cache (per user)
# ---------------------------------------------------------------------------
_summary_cache: OrderedDict[str, str] = OrderedDict()
_summary_lock = threading.Lock()
_SUMMARY_CACHE_MAX = 500

_SUMMARY_PROMPT = (
    "You are a concise summariser. Condense the following conversation into "
    "ONE paragraph (max 120 words). Preserve key tax topics, numbers, "
    "user decisions, and any advice given. Output ONLY the summary paragraph, "
    "nothing else.\n\n{conversation}"
)


class RAGService:
    """Orchestrates retrieval + generation for the AI assistant."""

    def __init__(self, db: Session):
        self.db = db
        self.llm = get_llm_service()
        self._kb = None

    @property
    def kb(self):
        """Lazy-load knowledge base service (expensive: loads SentenceTransformer model)."""
        if self._kb is None:
            from app.services.knowledge_base_service import get_knowledge_base_service
            self._kb = get_knowledge_base_service()
        return self._kb

    def answer(
        self,
        user: User,
        message: str,
        language: str = "de",
        tax_year: Optional[int] = None,
    ) -> str:
        """
        Generate a RAG-powered answer.

        1. Retrieve relevant tax knowledge chunks
        2. Build user financial summary from DB
        3. Fetch recent conversation history
        4. Call LLM with all context

        Returns the response text (without disclaimer).
        """
        if tax_year is None:
            tax_year = datetime.now().year

        # Step 1 – knowledge retrieval (skip for Ollama — too slow with SentenceTransformer)
        if self.llm.is_ollama_mode:
            context_chunks = []
            logger.info("Skipping RAG retrieval for Ollama (CPU-only, using system prompt knowledge)")
        else:
            context_chunks = self._retrieve_knowledge(message, language)

        # Step 2 – user financial summary
        financial_summary = self._build_financial_summary(user, tax_year, language)

        # Step 3 – conversation history (with summary for long conversations)
        chat_service = get_chat_history_service(self.db)
        conversation_history = self._build_conversation_context(
            chat_service, user.id
        )

        # Step 4 – LLM generation
        return self.llm.generate_response(
            user_message=message,
            language=language,
            context_chunks=context_chunks,
            user_financial_summary=financial_summary,
            conversation_history=conversation_history,
        )

    # ------------------------------------------------------------------
    # Knowledge retrieval
    # ------------------------------------------------------------------

    def _retrieve_knowledge(self, query: str, language: str) -> List[str]:
        """Retrieve relevant chunks from all knowledge base collections."""
        chunks: List[str] = []
        lang_filter = {"language": language}

        # Original hand-written knowledge base collections
        for collection in ("austrian_tax_law", "usp_2026_tax_tables", "tax_faq"):
            try:
                results = self.kb.vector_db.query_documents(
                    collection_name=collection,
                    query_text=query,
                    n_results=3,
                    where=lang_filter,
                )
                docs = results.get("documents", [[]])[0]
                chunks.extend(docs)
            except Exception:
                pass

        # Steuerbuch PDF chunks (ingested from BMF tax guides)
        try:
            results = self.kb.vector_db.query_documents(
                collection_name="steuerbuch_guides",
                query_text=query,
                n_results=5,
                where=lang_filter,
            )
            docs = results.get("documents", [[]])[0]
            chunks.extend(docs)
        except Exception:
            pass

        # ⑦ Admin-supplied knowledge updates
        try:
            results = self.kb.vector_db.query_documents(
                collection_name="admin_knowledge_updates",
                query_text=query,
                n_results=3,
                where=lang_filter,
            )
            docs = results.get("documents", [[]])[0]
            chunks.extend(docs)
        except Exception:
            pass

        return chunks

    # ------------------------------------------------------------------
    # Financial summary builder
    # ------------------------------------------------------------------

    def _build_financial_summary(
        self, user: User, tax_year: int, language: str
    ) -> str:
        """Build a concise text summary of the user's financial situation."""
        transactions = (
            self.db.query(Transaction)
            .filter(
                Transaction.user_id == user.id,
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .all()
        )

        if not transactions:
            return self._no_data_message(user, language)

        total_income = sum(
            (t.amount for t in transactions if t.type == TransactionType.INCOME),
            Decimal("0"),
        )
        total_expenses = sum(
            (t.amount for t in transactions if t.type == TransactionType.EXPENSE),
            Decimal("0"),
        )
        deductible = sum(
            (
                t.amount
                for t in transactions
                if t.type == TransactionType.EXPENSE and t.is_deductible
            ),
            Decimal("0"),
        )

        # Income breakdown
        income_cats: Dict[str, Decimal] = {}
        for t in transactions:
            if t.type == TransactionType.INCOME and t.income_category:
                cat = t.income_category.value
                income_cats[cat] = income_cats.get(cat, Decimal("0")) + t.amount

        # Expense breakdown
        expense_cats: Dict[str, Decimal] = {}
        for t in transactions:
            if t.type == TransactionType.EXPENSE and t.expense_category:
                cat = t.expense_category.value
                expense_cats[cat] = expense_cats.get(cat, Decimal("0")) + t.amount

        # Document count
        doc_count = (
            self.db.query(Document)
            .filter(Document.user_id == user.id)
            .count()
        )

        lines = [
            f"Tax year: {tax_year}",
            f"User type: {user.user_type.value if user.user_type else 'unknown'}",
            f"Total income: €{total_income:,.2f}",
            f"Total expenses: €{total_expenses:,.2f}",
            f"Deductible expenses: €{deductible:,.2f}",
            f"Net income: €{total_income - total_expenses:,.2f}",
            f"Transactions: {len(transactions)}, Documents: {doc_count}",
        ]

        if income_cats:
            lines.append("Income breakdown: " + ", ".join(
                f"{k}: €{v:,.2f}" for k, v in income_cats.items()
            ))
        if expense_cats:
            lines.append("Expense breakdown: " + ", ".join(
                f"{k}: €{v:,.2f}" for k, v in expense_cats.items()
            ))

        # Family info
        family = user.family_info or {}
        if family.get("num_children"):
            lines.append(
                f"Children: {family['num_children']}, "
                f"Single parent: {family.get('is_single_parent', False)}"
            )

        # Commuting
        commuting = user.commuting_info or {}
        if commuting.get("distance_km"):
            lines.append(
                f"Commute: {commuting['distance_km']} km, "
                f"Public transport: {commuting.get('public_transport_available', 'unknown')}"
            )

        if user.home_office_eligible:
            lines.append("Home office eligible: yes")

        # --- Enhanced context: properties, loans, thresholds, gaps ---

        # Property portfolio
        try:
            from app.models.property import Property, PropertyStatus
            from app.models.property_loan import PropertyLoan

            properties = (
                self.db.query(Property)
                .filter(Property.user_id == user.id, Property.status == PropertyStatus.ACTIVE)
                .all()
            )
            if properties:
                lines.append(f"Active properties: {len(properties)}")
                for p in properties:
                    dep_rate_pct = float(p.depreciation_rate or 0) * 100
                    annual_dep = float(p.building_value or 0) * float(p.depreciation_rate or 0)
                    lines.append(
                        f"  Property: purchase €{p.purchase_price:,.0f}, "
                        f"building €{p.building_value:,.0f}, "
                        f"depreciation {dep_rate_pct:.1f}%/yr (€{annual_dep:,.0f}/yr), "
                        f"accumulated depreciation €{p.accumulated_depreciation:,.0f}"
                    )

            loans = (
                self.db.query(PropertyLoan)
                .filter(PropertyLoan.user_id == user.id)
                .all()
            )
            if loans:
                total_loan_interest = sum(
                    float(lo.calculate_annual_interest(tax_year)) for lo in loans
                )
                lines.append(
                    f"Property loans: {len(loans)}, "
                    f"estimated annual interest: €{total_loan_interest:,.0f}"
                )
        except Exception:
            self.db.rollback()  # Prevent poisoned transaction from breaking subsequent queries

        # Recurring transactions
        recurring = [t for t in transactions if t.is_recurring and t.recurring_is_active]
        if recurring:
            lines.append(f"Active recurring transactions: {len(recurring)}")

        # Kleinunternehmerregelung threshold check (€55,000 since 2025)
        # Only relevant for self-employed / business / mixed users
        user_type_val = user.user_type.value if user.user_type else ""
        if user_type_val in ("self_employed", "mixed", "small_business"):
            business_income = sum(
                v for k, v in income_cats.items()
                if k in ("business", "self_employment")
            )
            if business_income > 0:
                threshold = Decimal("55000")
                pct_of_threshold = (business_income / threshold * 100).quantize(Decimal("1"))
                lines.append(
                    f"Kleinunternehmerregelung: business income €{business_income:,.0f} "
                    f"= {pct_of_threshold}% of €55,000 threshold"
                )
                if business_income > Decimal("45000"):
                    lines.append("WARNING: Approaching Kleinunternehmerregelung threshold!")

        # Missing deduction detection
        missing = []
        has_employment = "employment" in income_cats
        has_commuting_expense = "commuting" in expense_cats
        has_home_office_expense = "home_office" in expense_cats
        has_children = bool(family.get("num_children"))
        has_childcare_expense = "kinderbetreuung" in expense_cats or any(
            "kinderbetreuung" in (t.description or "").lower()
            for t in transactions
            if t.type == TransactionType.EXPENSE
        )

        if has_employment and commuting.get("distance_km") and not has_commuting_expense:
            missing.append("Commuting allowance (Pendlerpauschale) not claimed")
        if has_employment and user.home_office_eligible and not has_home_office_expense:
            missing.append("Home office deduction not claimed")
        if has_children and not has_childcare_expense:
            missing.append("Childcare costs (Kinderbetreuungskosten) not recorded")

        if missing:
            lines.append("Potentially missing deductions: " + "; ".join(missing))

        # Confirmed tax filing data (from OCR-imported tax forms)
        try:
            from app.models.tax_filing_data import TaxFilingData

            filing_records = (
                self.db.query(TaxFilingData)
                .filter(
                    TaxFilingData.user_id == user.id,
                    TaxFilingData.tax_year == tax_year,
                    TaxFilingData.status == "confirmed",
                )
                .all()
            )
            if filing_records:
                lines.append(f"Confirmed tax filing records: {len(filing_records)}")
                for rec in filing_records:
                    data = rec.data or {}
                    summary_parts = [f"  {rec.data_type}"]
                    # Extract key amounts from common fields
                    for key in (
                        "kz_245", "kz_260", "betriebseinnahmen", "betriebsausgaben",
                        "gewinn_verlust", "gesamtumsatz", "zahllast", "total_amount",
                        "annual_tax", "kapitalertraege",
                    ):
                        val = data.get(key)
                        if val is not None:
                            summary_parts.append(f"{key}: €{float(val):,.2f}")
                    lines.append(", ".join(summary_parts))
        except Exception:
            self.db.rollback()

        # Year-over-year comparison
        try:
            prev_transactions = (
                self.db.query(Transaction)
                .filter(
                    Transaction.user_id == user.id,
                    extract("year", Transaction.transaction_date) == tax_year - 1,
                )
                .all()
            )
            if prev_transactions:
                prev_income = sum(
                    (t.amount for t in prev_transactions if t.type == TransactionType.INCOME),
                    Decimal("0"),
                )
                prev_expenses = sum(
                    (t.amount for t in prev_transactions if t.type == TransactionType.EXPENSE),
                    Decimal("0"),
                )
                if prev_income > 0:
                    income_change = ((total_income - prev_income) / prev_income * 100).quantize(
                        Decimal("1")
                    )
                    lines.append(
                        f"Year-over-year: income {'+' if income_change > 0 else ''}"
                        f"{income_change}%, "
                        f"prev year income €{prev_income:,.0f}, expenses €{prev_expenses:,.0f}"
                    )
        except Exception:
            self.db.rollback()

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # ⑤ Conversation summary for extended memory
    # ------------------------------------------------------------------

    # Recent messages sent verbatim to the LLM
    RECENT_WINDOW = 6
    # Older messages to summarise (beyond the recent window)
    SUMMARY_WINDOW = 20

    def _build_conversation_context(
        self, chat_service, user_id: int
    ) -> List[Dict[str, str]]:
        """
        Build conversation history with optional summary of older messages.

        - Fetch the last (RECENT_WINDOW + SUMMARY_WINDOW) messages.
        - The most recent RECENT_WINDOW go verbatim.
        - If there are older messages beyond that, summarise them into one
          system-role message prepended to the list.
        """
        total_fetch = self.RECENT_WINDOW + self.SUMMARY_WINDOW
        all_msgs = chat_service.get_conversation_history(
            user_id=user_id, limit=total_fetch, offset=0
        )

        if len(all_msgs) <= self.RECENT_WINDOW:
            # Short conversation — no summary needed
            return [
                {"role": msg.role.value, "content": msg.content}
                for msg in all_msgs
            ]

        # Split into older (to summarise) and recent (verbatim)
        older = all_msgs[: -self.RECENT_WINDOW]
        recent = all_msgs[-self.RECENT_WINDOW:]

        conversation_history: List[Dict[str, str]] = []

        # Summarise older part
        summary = self._get_or_create_summary(user_id, older)
        if summary:
            conversation_history.append({
                "role": "system",
                "content": f"[Previous conversation summary]: {summary}",
            })

        # Add recent verbatim
        for msg in recent:
            conversation_history.append({
                "role": msg.role.value, "content": msg.content
            })

        return conversation_history

    def _get_or_create_summary(
        self, user_id: int, messages
    ) -> Optional[str]:
        """Return a cached or freshly-generated summary for *messages*."""
        # Build a deterministic cache key from message IDs/content
        content_hash = hashlib.md5(
            "|".join(
                f"{m.id}:{m.content[:60]}" for m in messages
            ).encode()
        ).hexdigest()[:16]
        cache_key = f"{user_id}:{content_hash}"

        with _summary_lock:
            if cache_key in _summary_cache:
                _summary_cache.move_to_end(cache_key)  # Mark as recently used
                return _summary_cache[cache_key]

        # Generate summary via LLM
        conversation_text = "\n".join(
            f"{m.role.value}: {m.content}" for m in messages
        )
        prompt = _SUMMARY_PROMPT.format(conversation=conversation_text)

        try:
            summary = self.llm.generate_response(
                user_message=prompt,
                language="en",
                context_chunks=[],
                user_financial_summary="",
                conversation_history=[],
            )
            # Trim to max 200 words as safety net
            words = summary.split()
            if len(words) > 200:
                summary = " ".join(words[:200]) + "…"
        except Exception as exc:
            logger.warning("Conversation summary generation failed: %s", exc)
            # Fallback: just list topics
            summary = "Previous topics: " + ", ".join(
                m.content[:40] for m in messages if m.role.value == "user"
            )

        with _summary_lock:
            # Evict least-recently-used entries if cache is full
            if len(_summary_cache) >= _SUMMARY_CACHE_MAX:
                # Remove ~10% oldest by access order
                keys_to_remove = list(_summary_cache.keys())[: _SUMMARY_CACHE_MAX // 10]
                for k in keys_to_remove:
                    _summary_cache.pop(k, None)
            _summary_cache[cache_key] = summary
            # Move to end (most-recently-used) so LRU eviction works correctly
            _summary_cache.move_to_end(cache_key)

        return summary

    @staticmethod
    def _no_data_message(user: User, language: str) -> str:
        user_type = user.user_type.value if user.user_type else "unknown"
        msgs = {
            "de": f"Benutzertyp: {user_type}. Noch keine Transaktionen für dieses Steuerjahr erfasst.",
            "en": f"User type: {user_type}. No transactions recorded for this tax year yet.",
            "zh": f"用户类型：{user_type}。本税务年度尚无交易记录。",
        }
        return msgs.get(language, msgs["de"])
