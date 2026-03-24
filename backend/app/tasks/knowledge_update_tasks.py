"""
⑦ Knowledge base semi-automatic update system.

Celery tasks that:
1. Scan a configurable directory for new / updated knowledge documents
   (Markdown, JSON, or plain-text files).
2. Chunk, embed, and upsert them into the ChromaDB vector store.
3. Track which files have already been ingested (via a JSON manifest)
   so only deltas are processed.

Directory layout expected::

    knowledge_updates/
        ├── manifest.json          ← auto-generated tracking file
        ├── tax_law_update_2026.md
        ├── new_deductions.json
        └── ...

JSON files should contain a list of objects::

    [
        {
            "text": "...",
            "metadata": {"source": "BMF 2026", "category": "...", "language": "de"}
        }
    ]

Markdown / text files are auto-chunked (≤500 words per chunk) and
assigned ``language=de`` unless the filename contains ``_en`` or ``_zh``.
"""
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from celery import Task

from app.celery_app import celery_app

logger = logging.getLogger(__name__)

# Default directory where admins drop knowledge update files
_DEFAULT_UPDATES_DIR = os.environ.get(
    "KNOWLEDGE_UPDATES_DIR", "knowledge_updates"
)

# ChromaDB collection for admin-supplied updates
_UPDATE_COLLECTION = "admin_knowledge_updates"

# Maximum words per chunk when splitting plain-text / markdown
_MAX_CHUNK_WORDS = 500


class _DBTask(Task):
    """Task base with lazy DB session."""
    _db = None

    @property
    def db(self):
        if self._db is None:
            from app.db.session import SessionLocal
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _file_hash(path: str) -> str:
    """Return SHA-256 hex of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_language(filename: str) -> str:
    """Infer language from filename convention."""
    name = filename.lower()
    if "_en" in name or ".en." in name:
        return "en"
    if "_zh" in name or ".zh." in name:
        return "zh"
    return "de"


def _chunk_text(text: str, max_words: int = _MAX_CHUNK_WORDS) -> List[str]:
    """Split text into chunks of approximately *max_words* words."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i : i + max_words])
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks or [text.strip()]


def _load_manifest(updates_dir: str) -> Dict:
    """Load the manifest tracking already-ingested files."""
    path = os.path.join(updates_dir, "manifest.json")
    if not os.path.exists(path):
        return {"ingested_files": {}}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {"ingested_files": {}}


def _save_manifest(updates_dir: str, manifest: Dict) -> None:
    """Persist the manifest."""
    path = os.path.join(updates_dir, "manifest.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


# ------------------------------------------------------------------
# Core ingestion logic (importable for testing without Celery)
# ------------------------------------------------------------------

def scan_and_ingest(updates_dir: Optional[str] = None) -> Dict:
    """
    Scan *updates_dir* for new/changed files and ingest them.

    Returns a summary dict with ``new_files``, ``updated_files``,
    ``total_chunks``, ``errors``.
    """
    updates_dir = updates_dir or _DEFAULT_UPDATES_DIR
    if not os.path.isdir(updates_dir):
        return {
            "new_files": 0,
            "updated_files": 0,
            "total_chunks": 0,
            "errors": [],
            "message": f"Directory not found: {updates_dir}",
        }

    manifest = _load_manifest(updates_dir)
    ingested = manifest.get("ingested_files", {})

    new_files = 0
    updated_files = 0
    total_chunks = 0
    errors: List[str] = []

    # Lazy-load heavy services only when we actually have work
    kb_service = None

    for entry in sorted(os.listdir(updates_dir)):
        if entry == "manifest.json":
            continue
        filepath = os.path.join(updates_dir, entry)
        if not os.path.isfile(filepath):
            continue

        ext = Path(entry).suffix.lower()
        if ext not in (".md", ".txt", ".json"):
            continue

        current_hash = _file_hash(filepath)
        prev_hash = ingested.get(entry, {}).get("hash")

        if current_hash == prev_hash:
            continue  # Already ingested, unchanged

        is_update = entry in ingested
        try:
            if kb_service is None:
                # First file — initialise the KB service now
                from app.services.knowledge_base_service import get_knowledge_base_service
                kb_service = get_knowledge_base_service()

            chunks_added = _ingest_file(filepath, entry, ext, kb_service)
            total_chunks += chunks_added
            if is_update:
                updated_files += 1
            else:
                new_files += 1

            ingested[entry] = {
                "hash": current_hash,
                "ingested_at": datetime.utcnow().isoformat(),
                "chunks": chunks_added,
            }
        except Exception as exc:
            logger.error("Failed to ingest %s: %s", entry, exc, exc_info=True)
            errors.append(f"{entry}: {exc}")

    manifest["ingested_files"] = ingested
    manifest["last_scan"] = datetime.utcnow().isoformat()
    _save_manifest(updates_dir, manifest)

    return {
        "new_files": new_files,
        "updated_files": updated_files,
        "total_chunks": total_chunks,
        "errors": errors,
    }


def _delete_old_chunks(filename: str, kb_service) -> None:
    """Delete all existing chunks for *filename* before re-ingesting."""
    try:
        collection = kb_service.vector_db.client.get_collection(
            name=_UPDATE_COLLECTION
        )
        collection.delete(where={"source_file": filename})
        logger.info("Deleted old chunks for %s from %s", filename, _UPDATE_COLLECTION)
    except Exception as exc:
        # Collection may not exist yet on first run — that's fine
        logger.debug("Could not delete old chunks for %s: %s", filename, exc)


def _ingest_file(filepath: str, filename: str, ext: str, kb_service) -> int:
    """Parse and ingest a single file, returning the number of chunks added."""
    if kb_service is None:
        raise RuntimeError("kb_service not initialised")

    # ④ Delete stale chunks BEFORE re-ingesting so that if the new version
    # has fewer chunks, the old high-index ones don't linger in ChromaDB.
    _delete_old_chunks(filename, kb_service)

    language = _detect_language(filename)

    if ext == ".json":
        with open(filepath, "r", encoding="utf-8") as f:
            items = json.load(f)
        if not isinstance(items, list):
            items = [items]
        documents = []
        metadatas = []
        for item in items:
            text = item.get("text", "")
            meta = item.get("metadata", {})
            if not text:
                continue
            meta.setdefault("language", language)
            meta["source_file"] = filename
            documents.append(text)
            metadatas.append(meta)
    else:
        # Markdown / plain text
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
        chunks = _chunk_text(raw)
        documents = chunks
        metadatas = [
            {
                "language": language,
                "source_file": filename,
                "chunk_index": i,
                "source": f"admin_update:{filename}",
            }
            for i in range(len(chunks))
        ]

    if not documents:
        return 0

    ids = [
        f"ku_{hashlib.sha256(f'{filename}:{i}'.encode()).hexdigest()[:16]}"
        for i in range(len(documents))
    ]

    kb_service.vector_db.add_documents(
        collection_name=_UPDATE_COLLECTION,
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )

    logger.info("Ingested %s: %d chunks into %s", filename, len(documents), _UPDATE_COLLECTION)
    return len(documents)


# ------------------------------------------------------------------
# Celery task
# ------------------------------------------------------------------

@celery_app.task(
    bind=True,
    base=_DBTask,
    name="knowledge.scan_and_ingest",
    max_retries=1,
    default_retry_delay=600,
)
def scan_and_ingest_task(self) -> Dict:
    """
    Periodic task: scan knowledge_updates/ for new files and ingest them.

    Schedule via Celery Beat (e.g. weekly or on-demand via admin endpoint).
    """
    try:
        logger.info("Knowledge update scan started")
        result = scan_and_ingest()
        logger.info(
            "Knowledge update scan finished: %d new, %d updated, %d chunks",
            result["new_files"], result["updated_files"], result["total_chunks"],
        )
        result["task_id"] = self.request.id
        result["scanned_at"] = datetime.utcnow().isoformat()
        return result
    except Exception as exc:
        logger.error("Knowledge update task failed: %s", exc, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"error": str(exc), "task_id": self.request.id}
