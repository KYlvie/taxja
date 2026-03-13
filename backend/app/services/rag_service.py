"""
RAG (Retrieval-Augmented Generation) service for AI Tax Assistant.
Combines knowledge base retrieval + user financial data + LLM generation.
"""
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
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
        if self.llm._use_ollama:
            context_chunks = []
            logger.info("Skipping RAG retrieval for Ollama (CPU-only, using system prompt knowledge)")
        else:
            context_chunks = self._retrieve_knowledge(message, language)

        # Step 2 – user financial summary
        financial_summary = self._build_financial_summary(user, tax_year, language)

        # Step 3 – conversation history
        chat_service = get_chat_history_service(self.db)
        recent_msgs = chat_service.get_conversation_history(
            user_id=user.id, limit=6, offset=0
        )
        conversation_history = [
            {"role": msg.role.value, "content": msg.content}
            for msg in reversed(recent_msgs)  # oldest first
        ]

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

        return "\n".join(lines)

    @staticmethod
    def _no_data_message(user: User, language: str) -> str:
        user_type = user.user_type.value if user.user_type else "unknown"
        msgs = {
            "de": f"Benutzertyp: {user_type}. Noch keine Transaktionen für dieses Steuerjahr erfasst.",
            "en": f"User type: {user_type}. No transactions recorded for this tax year yet.",
            "zh": f"用户类型：{user_type}。本税务年度尚无交易记录。",
        }
        return msgs.get(language, msgs["de"])
