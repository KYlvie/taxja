"""
Tests for AI optimizations ④⑤⑦:
④ AI personalized savings suggestions (spending pattern analysis)
⑤ Conversation summary for extended memory (RAG service)
⑦ Knowledge base semi-automatic update system
"""
import json
import os
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# ⑤ Conversation summary tests
# ---------------------------------------------------------------------------

class TestConversationSummary:
    """Tests for RAG service conversation summary feature."""

    def _make_chat_message(self, role, content, msg_id=None):
        msg = MagicMock()
        msg.role = MagicMock()
        msg.role.value = role
        msg.content = content
        msg.id = msg_id or id(msg)
        return msg

    @patch("app.services.rag_service.get_llm_service")
    @patch("app.services.rag_service.get_chat_history_service")
    def test_short_conversation_no_summary(self, mock_get_chat, mock_get_llm):
        """When history <= RECENT_WINDOW, no summary is generated."""
        from app.services.rag_service import RAGService

        mock_db = MagicMock()
        mock_llm = MagicMock()
        mock_llm.is_ollama_mode = False
        mock_get_llm.return_value = mock_llm

        service = RAGService(mock_db)
        chat_svc = MagicMock()
        mock_get_chat.return_value = chat_svc

        # Only 4 messages — below RECENT_WINDOW (6)
        messages = [
            self._make_chat_message("user", "Hello", i)
            for i in range(4)
        ]
        chat_svc.get_conversation_history.return_value = messages

        result = service._build_conversation_context(chat_svc, user_id=1)

        assert len(result) == 4
        # No summary system message
        assert all(r["role"] != "system" for r in result)

    @patch("app.services.rag_service.get_llm_service")
    @patch("app.services.rag_service.get_chat_history_service")
    def test_long_conversation_generates_summary(self, mock_get_chat, mock_get_llm):
        """When history > RECENT_WINDOW, older messages get summarised."""
        from app.services.rag_service import RAGService, _summary_cache

        mock_db = MagicMock()
        mock_llm = MagicMock()
        mock_llm.is_ollama_mode = False
        mock_llm.generate_response.return_value = "Summary of tax discussion about deductions."
        mock_get_llm.return_value = mock_llm

        service = RAGService(mock_db)
        chat_svc = MagicMock()

        # 12 messages — 6 older + 6 recent
        messages = [
            self._make_chat_message(
                "user" if i % 2 == 0 else "assistant",
                f"Message {i} about taxes",
                msg_id=i + 100,
            )
            for i in range(12)
        ]
        chat_svc.get_conversation_history.return_value = messages

        # Clear cache to force generation
        _summary_cache.clear()

        result = service._build_conversation_context(chat_svc, user_id=99)

        # Should have summary + 6 recent = 7 entries
        assert len(result) == 7
        assert result[0]["role"] == "system"
        assert "Previous conversation summary" in result[0]["content"]

        # LLM was called to generate summary
        mock_llm.generate_response.assert_called_once()

    @patch("app.services.rag_service.get_llm_service")
    @patch("app.services.rag_service.get_chat_history_service")
    def test_summary_is_cached(self, mock_get_chat, mock_get_llm):
        """Second call with same messages uses cached summary."""
        from app.services.rag_service import RAGService, _summary_cache

        mock_db = MagicMock()
        mock_llm = MagicMock()
        mock_llm.is_ollama_mode = False
        mock_llm.generate_response.return_value = "Cached summary."
        mock_get_llm.return_value = mock_llm

        service = RAGService(mock_db)
        chat_svc = MagicMock()

        messages = [
            self._make_chat_message("user", f"Msg {i}", msg_id=i + 200)
            for i in range(10)
        ]
        chat_svc.get_conversation_history.return_value = messages

        _summary_cache.clear()

        # First call — generates summary
        service._build_conversation_context(chat_svc, user_id=50)
        assert mock_llm.generate_response.call_count == 1

        # Second call — should use cache
        service._build_conversation_context(chat_svc, user_id=50)
        assert mock_llm.generate_response.call_count == 1  # Still 1

    @patch("app.services.rag_service.get_llm_service")
    @patch("app.services.rag_service.get_chat_history_service")
    def test_summary_fallback_on_llm_error(self, mock_get_chat, mock_get_llm):
        """If LLM fails, a fallback topic-list summary is used."""
        from app.services.rag_service import RAGService, _summary_cache

        mock_db = MagicMock()
        mock_llm = MagicMock()
        mock_llm.is_ollama_mode = False
        mock_llm.generate_response.side_effect = RuntimeError("LLM down")
        mock_get_llm.return_value = mock_llm

        service = RAGService(mock_db)
        chat_svc = MagicMock()

        messages = [
            self._make_chat_message(
                "user" if i % 2 == 0 else "assistant",
                f"Topic {i}",
                msg_id=i + 300,
            )
            for i in range(10)
        ]
        chat_svc.get_conversation_history.return_value = messages

        _summary_cache.clear()

        result = service._build_conversation_context(chat_svc, user_id=77)

        # Should still have a summary (fallback)
        assert result[0]["role"] == "system"
        assert "Previous" in result[0]["content"] or "topics" in result[0]["content"].lower()


# ---------------------------------------------------------------------------
# ④ AI savings suggestions tests
# ---------------------------------------------------------------------------

class TestAISavingsSuggestions:
    """Tests for AI-powered spending pattern analysis."""

    def test_parse_ai_suggestions_valid_json(self):
        """Valid JSON array is parsed into SavingsSuggestion objects."""
        from app.services.savings_suggestion_service import SavingsSuggestionService

        raw = json.dumps([
            {
                "title": "Claim Fortbildungskosten",
                "description": "Your education expenses may be deductible.",
                "estimated_savings_eur": 450,
                "action_required": "Collect receipts",
            },
            {
                "title": "Sonderausgaben: Kirchenbeitrag",
                "description": "Church tax up to €400 is deductible.",
                "estimated_savings_eur": 120,
                "action_required": "Add Kirchenbeitrag receipts",
            },
        ])

        result = SavingsSuggestionService._parse_ai_suggestions(raw)

        assert len(result) == 2
        assert result[0].title == "Claim Fortbildungskosten"
        assert result[0].potential_savings == Decimal("450")
        assert result[0].category == "ai_suggestion"
        assert result[1].potential_savings == Decimal("120")

    def test_parse_ai_suggestions_markdown_fenced(self):
        """JSON wrapped in markdown fences is still parsed."""
        from app.services.savings_suggestion_service import SavingsSuggestionService

        raw = '```json\n[{"title":"Test","description":"Desc","estimated_savings_eur":50,"action_required":"Do it"}]\n```'

        result = SavingsSuggestionService._parse_ai_suggestions(raw)

        assert len(result) == 1
        assert result[0].title == "Test"

    def test_parse_ai_suggestions_invalid_json(self):
        """Invalid JSON returns empty list."""
        from app.services.savings_suggestion_service import SavingsSuggestionService

        result = SavingsSuggestionService._parse_ai_suggestions("not json at all")
        assert result == []

    def test_parse_ai_suggestions_max_three(self):
        """At most 3 suggestions are returned."""
        from app.services.savings_suggestion_service import SavingsSuggestionService

        raw = json.dumps([
            {"title": f"Tip {i}", "description": f"Desc {i}",
             "estimated_savings_eur": 10 * i, "action_required": ""}
            for i in range(5)
        ])

        result = SavingsSuggestionService._parse_ai_suggestions(raw)
        assert len(result) == 3

    def test_parse_ai_suggestions_missing_fields_skipped(self):
        """Items without title or description are skipped."""
        from app.services.savings_suggestion_service import SavingsSuggestionService

        raw = json.dumps([
            {"title": "", "description": "No title", "estimated_savings_eur": 10},
            {"title": "Valid", "description": "Good one", "estimated_savings_eur": 20},
        ])

        result = SavingsSuggestionService._parse_ai_suggestions(raw)
        assert len(result) == 1
        assert result[0].title == "Valid"

    @patch("app.services.llm_service.get_llm_service")
    def test_ai_spending_analysis_too_few_transactions(self, mock_get_llm):
        """With fewer than 5 transactions, AI analysis is skipped."""
        from app.services.savings_suggestion_service import SavingsSuggestionService

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        # Bypass __init__ dependencies by creating instance without calling __init__
        service = object.__new__(SavingsSuggestionService)
        service.db = mock_db

        user = MagicMock()
        user.id = 1
        user.user_type = MagicMock()
        user.user_type.value = "employee"

        result = service._ai_spending_analysis(user, 2026, "de")
        assert result == []


# ---------------------------------------------------------------------------
# ⑦ Knowledge base update tests
# ---------------------------------------------------------------------------

class TestKnowledgeBaseUpdate:
    """Tests for the knowledge base semi-automatic update system."""

    def test_chunk_text_splits_correctly(self):
        """Text is split into chunks of max_words."""
        from app.tasks.knowledge_update_tasks import _chunk_text

        text = " ".join([f"word{i}" for i in range(120)])

        chunks = _chunk_text(text, max_words=50)
        assert len(chunks) == 3  # 120/50 = 2.4 → 3 chunks
        assert len(chunks[0].split()) == 50
        assert len(chunks[2].split()) == 20

    def test_chunk_text_small_input(self):
        """Short text returns a single chunk."""
        from app.tasks.knowledge_update_tasks import _chunk_text

        chunks = _chunk_text("Hello world", max_words=100)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_detect_language(self):
        """Language detection from filename."""
        from app.tasks.knowledge_update_tasks import _detect_language

        assert _detect_language("update_de.md") == "de"
        assert _detect_language("tax_en.md") == "en"
        assert _detect_language("info_zh.json") == "zh"
        assert _detect_language("something.txt") == "de"  # default

    def test_file_hash_deterministic(self, tmp_path):
        """Same content produces same hash."""
        from app.tasks.knowledge_update_tasks import _file_hash

        f = tmp_path / "test.txt"
        f.write_text("hello world")

        h1 = _file_hash(str(f))
        h2 = _file_hash(str(f))
        assert h1 == h2
        assert len(h1) == 32  # MD5 hex

    def test_manifest_load_save(self, tmp_path):
        """Manifest can be saved and loaded."""
        from app.tasks.knowledge_update_tasks import _load_manifest, _save_manifest

        updates_dir = str(tmp_path)

        # No manifest yet
        m = _load_manifest(updates_dir)
        assert m == {"ingested_files": {}}

        # Save and reload
        m["ingested_files"]["test.md"] = {"hash": "abc123", "chunks": 5}
        _save_manifest(updates_dir, m)

        m2 = _load_manifest(updates_dir)
        assert m2["ingested_files"]["test.md"]["hash"] == "abc123"

    def test_scan_empty_directory(self, tmp_path):
        """Scanning an empty directory returns zero counts."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest

        result = scan_and_ingest(str(tmp_path))
        assert result["new_files"] == 0
        assert result["total_chunks"] == 0
        assert result["errors"] == []

    def test_scan_nonexistent_directory(self):
        """Scanning a missing directory returns a message, no crash."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest

        result = scan_and_ingest("/nonexistent/path/12345")
        assert result["new_files"] == 0
        assert "not found" in result.get("message", "").lower()

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_scan_ingests_json_file(self, mock_get_kb, tmp_path):
        """A JSON knowledge file is ingested correctly."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest

        mock_kb = MagicMock()
        mock_get_kb.return_value = mock_kb

        # Create a JSON knowledge file
        data = [
            {
                "text": "New tax rule for 2026.",
                "metadata": {"source": "BMF", "category": "tax_update", "language": "de"},
            }
        ]
        (tmp_path / "update.json").write_text(json.dumps(data))

        result = scan_and_ingest(str(tmp_path))

        assert result["new_files"] == 1
        assert result["total_chunks"] == 1
        mock_kb.vector_db.add_documents.assert_called_once()

        # Verify the manifest was written
        manifest = json.loads((tmp_path / "manifest.json").read_text())
        assert "update.json" in manifest["ingested_files"]

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_scan_ingests_markdown_file(self, mock_get_kb, tmp_path):
        """A markdown knowledge file is chunked and ingested."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest

        mock_kb = MagicMock()
        mock_get_kb.return_value = mock_kb

        # Create a markdown file with enough content for multiple chunks
        words = " ".join([f"word{i}" for i in range(600)])
        (tmp_path / "big_update_en.md").write_text(words)

        result = scan_and_ingest(str(tmp_path))

        assert result["new_files"] == 1
        assert result["total_chunks"] == 2  # 600 / 500 = 1.2 → 2 chunks
        mock_kb.vector_db.add_documents.assert_called_once()

        # Check language detection from filename
        call_args = mock_kb.vector_db.add_documents.call_args
        metadatas = call_args.kwargs.get("metadatas") or call_args[1].get("metadatas")
        assert metadatas[0]["language"] == "en"

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_scan_skips_unchanged_files(self, mock_get_kb, tmp_path):
        """Already-ingested files are not re-processed."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest

        mock_kb = MagicMock()
        mock_get_kb.return_value = mock_kb

        (tmp_path / "data.json").write_text(json.dumps([{"text": "Test", "metadata": {}}]))

        # First scan
        r1 = scan_and_ingest(str(tmp_path))
        assert r1["new_files"] == 1

        # Second scan — same file, same content
        mock_kb.vector_db.add_documents.reset_mock()
        r2 = scan_and_ingest(str(tmp_path))
        assert r2["new_files"] == 0
        assert r2["updated_files"] == 0
        mock_kb.vector_db.add_documents.assert_not_called()

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_scan_detects_updated_files(self, mock_get_kb, tmp_path):
        """Modified files are re-ingested."""
        from app.tasks.knowledge_update_tasks import scan_and_ingest

        mock_kb = MagicMock()
        mock_get_kb.return_value = mock_kb

        f = tmp_path / "data.json"
        f.write_text(json.dumps([{"text": "Version 1", "metadata": {}}]))

        scan_and_ingest(str(tmp_path))

        # Modify the file
        f.write_text(json.dumps([{"text": "Version 2", "metadata": {}}]))
        mock_kb.vector_db.add_documents.reset_mock()

        r2 = scan_and_ingest(str(tmp_path))
        assert r2["updated_files"] == 1
        mock_kb.vector_db.add_documents.assert_called_once()
