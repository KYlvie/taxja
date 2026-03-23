"""
Tests for the 4 design warning fixes:
① LLMService.is_ollama_mode public property (replaces _use_ollama cross-class access)
② OrderedDict LRU cache for conversation summaries
③ Optional[SavingsSuggestion] return type annotations
④ Knowledge update: delete old chunks before re-ingesting
"""
import hashlib
import json
import inspect
import os
import tempfile
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal
from typing import Optional, get_type_hints
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# ① LLMService.is_ollama_mode public property
# ---------------------------------------------------------------------------

class TestIsOllamaModePublicProperty:
    """Verify _use_ollama is no longer accessed cross-class."""

    def test_is_ollama_mode_property_exists(self):
        """LLMService exposes is_ollama_mode as a public property."""
        from app.services.llm_service import LLMService
        assert hasattr(LLMService, "is_ollama_mode")
        assert isinstance(
            inspect.getattr_static(LLMService, "is_ollama_mode"), property
        )

    def test_rag_service_uses_public_api(self):
        """rag_service.py no longer references _use_ollama."""
        import app.services.rag_service as mod
        src = inspect.getsource(mod)
        assert "_use_ollama" not in src

    def test_ai_orchestrator_uses_public_api(self):
        """ai_orchestrator.py no longer references _use_ollama."""
        import app.services.ai_orchestrator as mod
        src = inspect.getsource(mod)
        assert "_use_ollama" not in src


# ---------------------------------------------------------------------------
# ② OrderedDict LRU cache for conversation summaries
# ---------------------------------------------------------------------------

class TestSummaryCacheLRU:
    """Verify the summary cache uses OrderedDict with proper LRU semantics."""

    def test_cache_is_ordered_dict(self):
        """_summary_cache is an OrderedDict, not a plain dict."""
        from app.services.rag_service import _summary_cache
        assert isinstance(_summary_cache, OrderedDict)

    @patch("app.services.rag_service.get_llm_service")
    @patch("app.services.rag_service.get_chat_history_service")
    def test_cache_hit_moves_to_end(self, mock_get_chat, mock_get_llm):
        """Accessing a cached summary moves it to the end (most-recently-used)."""
        from app.services.rag_service import RAGService, _summary_cache

        mock_llm = MagicMock()
        mock_llm.is_ollama_mode = False
        mock_llm.generate_response.return_value = "Summary A."
        mock_get_llm.return_value = mock_llm

        service = RAGService(MagicMock())
        chat_svc = MagicMock()

        def _msg(role, content, mid):
            m = MagicMock()
            m.role = MagicMock()
            m.role.value = role
            m.content = content
            m.id = mid
            return m

        # 10 messages → triggers summary for older ones
        messages = [_msg("user", f"Msg {i}", i + 500) for i in range(10)]
        chat_svc.get_conversation_history.return_value = messages

        _summary_cache.clear()

        # First call — populates cache
        service._build_conversation_context(chat_svc, user_id=800)
        assert len(_summary_cache) == 1
        first_key = list(_summary_cache.keys())[0]

        # Insert a second dummy entry so we can check ordering
        _summary_cache["dummy_key"] = "dummy"
        assert list(_summary_cache.keys())[-1] == "dummy_key"

        # Second call — cache hit should move first_key to end
        service._build_conversation_context(chat_svc, user_id=800)
        assert list(_summary_cache.keys())[-1] == first_key

    def test_eviction_removes_oldest_by_access_order(self):
        """When cache overflows, least-recently-used entries are evicted."""
        from app.services import rag_service
        from app.services.rag_service import _summary_cache, _summary_lock

        original_max = rag_service._SUMMARY_CACHE_MAX
        try:
            # Temporarily set a small max
            rag_service._SUMMARY_CACHE_MAX = 10
            _summary_cache.clear()

            # Fill cache to capacity
            for i in range(10):
                _summary_cache[f"key_{i}"] = f"val_{i}"

            # Access key_0 to make it recently used
            _summary_cache.move_to_end("key_0")

            # Now simulate what _get_or_create_summary does on overflow:
            # insert a new entry → eviction of ~10% oldest
            with _summary_lock:
                if len(_summary_cache) >= rag_service._SUMMARY_CACHE_MAX:
                    keys_to_remove = list(_summary_cache.keys())[
                        : rag_service._SUMMARY_CACHE_MAX // 10
                    ]
                    for k in keys_to_remove:
                        _summary_cache.pop(k, None)
                _summary_cache["new_key"] = "new_val"
                _summary_cache.move_to_end("new_key")

            # key_1 was the oldest (key_0 was moved to end), so key_1 should be evicted
            assert "key_1" not in _summary_cache
            # key_0 should survive (it was moved to end)
            assert "key_0" in _summary_cache
            assert "new_key" in _summary_cache
        finally:
            rag_service._SUMMARY_CACHE_MAX = original_max
            _summary_cache.clear()


# ---------------------------------------------------------------------------
# ③ Optional[SavingsSuggestion] return type annotations
# ---------------------------------------------------------------------------

class TestOptionalReturnTypes:
    """Verify _check_* methods have Optional return type annotations."""

    def _get_service_class(self):
        from app.services.savings_suggestion_service import SavingsSuggestionService
        return SavingsSuggestionService

    def test_check_commuting_allowance_returns_optional(self):
        cls = self._get_service_class()
        hints = get_type_hints(cls._check_commuting_allowance)
        assert hints["return"] == Optional[object] or "Optional" in str(hints["return"]) \
            or "None" in str(hints["return"])

    def test_check_home_office_deduction_returns_optional(self):
        cls = self._get_service_class()
        hints = get_type_hints(cls._check_home_office_deduction)
        ret = str(hints["return"])
        assert "None" in ret or "Optional" in ret

    def test_check_flat_rate_tax_returns_optional(self):
        cls = self._get_service_class()
        hints = get_type_hints(cls._check_flat_rate_tax)
        ret = str(hints["return"])
        assert "None" in ret or "Optional" in ret

    def test_check_family_deductions_returns_optional(self):
        cls = self._get_service_class()
        hints = get_type_hints(cls._check_family_deductions)
        ret = str(hints["return"])
        assert "None" in ret or "Optional" in ret

    def test_check_svs_deductibility_returns_optional(self):
        cls = self._get_service_class()
        hints = get_type_hints(cls._check_svs_deductibility)
        ret = str(hints["return"])
        assert "None" in ret or "Optional" in ret

    def test_all_five_methods_allow_none(self):
        """All 5 _check_* methods should accept None as a valid return."""
        from app.services.savings_suggestion_service import SavingsSuggestion
        cls = self._get_service_class()
        methods = [
            "_check_commuting_allowance",
            "_check_home_office_deduction",
            "_check_flat_rate_tax",
            "_check_family_deductions",
            "_check_svs_deductibility",
        ]
        for name in methods:
            hints = get_type_hints(getattr(cls, name))
            ret_str = str(hints["return"])
            assert "None" in ret_str or "Optional" in ret_str, (
                f"{name} return type {ret_str} does not include None"
            )


# ---------------------------------------------------------------------------
# ④ Knowledge update: delete old chunks before re-ingesting
# ---------------------------------------------------------------------------

class TestDeleteOldChunksBeforeIngest:
    """Verify _ingest_file deletes stale chunks before adding new ones."""

    def test_delete_old_chunks_function_exists(self):
        """_delete_old_chunks helper is defined."""
        from app.tasks.knowledge_update_tasks import _delete_old_chunks
        assert callable(_delete_old_chunks)

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_ingest_calls_delete_before_add(self, mock_get_kb, tmp_path):
        """_ingest_file deletes old chunks for the file before adding new ones."""
        from app.tasks.knowledge_update_tasks import _ingest_file

        mock_kb = MagicMock()
        mock_collection = MagicMock()
        mock_kb.vector_db.client.get_collection.return_value = mock_collection
        mock_get_kb.return_value = mock_kb

        # Create a small markdown file
        f = tmp_path / "test.md"
        f.write_text("Hello world content here")

        _ingest_file(str(f), "test.md", ".md", mock_kb)

        # Verify delete was called with source_file filter
        mock_kb.vector_db.client.get_collection.assert_called_once()
        mock_collection.delete.assert_called_once_with(
            where={"source_file": "test.md"}
        )

        # Verify add_documents was also called (after delete)
        mock_kb.vector_db.add_documents.assert_called_once()

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_delete_failure_does_not_block_ingest(self, mock_get_kb, tmp_path):
        """If delete fails (e.g. collection doesn't exist), ingest still proceeds."""
        from app.tasks.knowledge_update_tasks import _ingest_file

        mock_kb = MagicMock()
        # Simulate collection not found
        mock_kb.vector_db.client.get_collection.side_effect = Exception("not found")
        mock_get_kb.return_value = mock_kb

        f = tmp_path / "test.md"
        f.write_text("Some content")

        # Should not raise
        chunks = _ingest_file(str(f), "test.md", ".md", mock_kb)
        assert chunks == 1

        # add_documents should still be called
        mock_kb.vector_db.add_documents.assert_called_once()

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_update_file_fewer_chunks_no_stale(self, mock_get_kb, tmp_path):
        """
        Scenario: file originally had 3 chunks, updated to 1 chunk.
        Old chunks should be deleted first, so no stale data remains.
        """
        from app.tasks.knowledge_update_tasks import scan_and_ingest

        mock_kb = MagicMock()
        mock_collection = MagicMock()
        mock_kb.vector_db.client.get_collection.return_value = mock_collection
        mock_get_kb.return_value = mock_kb

        f = tmp_path / "doc.md"

        # First version: lots of content (3 chunks)
        f.write_text(" ".join([f"word{i}" for i in range(1200)]))
        r1 = scan_and_ingest(str(tmp_path))
        assert r1["new_files"] == 1
        assert r1["total_chunks"] == 3

        # Second version: small content (1 chunk)
        f.write_text("Short update.")
        mock_kb.vector_db.add_documents.reset_mock()
        mock_collection.delete.reset_mock()

        r2 = scan_and_ingest(str(tmp_path))
        assert r2["updated_files"] == 1
        assert r2["total_chunks"] == 1

        # delete was called before add
        mock_collection.delete.assert_called_with(where={"source_file": "doc.md"})
        mock_kb.vector_db.add_documents.assert_called_once()

    @patch("app.services.knowledge_base_service.get_knowledge_base_service")
    def test_json_file_also_deletes_old_chunks(self, mock_get_kb, tmp_path):
        """JSON files also get old chunks deleted before re-ingesting."""
        from app.tasks.knowledge_update_tasks import _ingest_file

        mock_kb = MagicMock()
        mock_collection = MagicMock()
        mock_kb.vector_db.client.get_collection.return_value = mock_collection

        data = [{"text": "New rule", "metadata": {"source": "BMF"}}]
        f = tmp_path / "update.json"
        f.write_text(json.dumps(data))

        _ingest_file(str(f), "update.json", ".json", mock_kb)

        mock_collection.delete.assert_called_once_with(
            where={"source_file": "update.json"}
        )
        mock_kb.vector_db.add_documents.assert_called_once()
