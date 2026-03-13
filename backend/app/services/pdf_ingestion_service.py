"""
PDF ingestion service for loading Steuerbuch PDFs into the knowledge base.

Reads PDF files, splits them into chunks, and stores them in ChromaDB
for RAG retrieval.
"""
import os
import re
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path

import fitz  # PyMuPDF

from app.services.vector_db_service import get_vector_db_service


# Collection name for ingested PDF documents
STEUERBUCH_COLLECTION = "steuerbuch_guides"

# Chunk configuration
CHUNK_SIZE = 1500  # characters per chunk (roughly ~300-400 tokens)
CHUNK_OVERLAP = 200  # overlap between consecutive chunks


class PDFIngestionService:
    """Ingests PDF tax guides into the vector database."""

    def __init__(self, pdf_dir: Optional[str] = None):
        self.pdf_dir = pdf_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "steuerbuch"
        )
        self.vector_db = get_vector_db_service()

    def ingest_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Ingest all PDF files found in the steuerbuch directory.

        Args:
            force: If True, re-ingest even if already present.

        Returns:
            Summary dict with counts.
        """
        pdf_dir = Path(self.pdf_dir)
        if not pdf_dir.exists():
            return {"error": f"Directory not found: {pdf_dir}", "ingested": 0}

        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            return {"error": f"No PDF files in {pdf_dir}", "ingested": 0}

        # Ensure collection exists
        self._ensure_collection()

        total_chunks = 0
        results = []

        for pdf_path in pdf_files:
            meta = self._parse_filename(pdf_path.name)
            file_hash = self._file_hash(pdf_path)

            if not force and self._already_ingested(file_hash):
                results.append({"file": pdf_path.name, "status": "skipped", "chunks": 0})
                continue

            # Extract text
            text = self._extract_text(pdf_path)
            if not text.strip():
                results.append({"file": pdf_path.name, "status": "empty", "chunks": 0})
                continue

            # Clean and chunk
            text = self._clean_text(text)
            chunks = self._split_into_chunks(text)

            # Build metadata for each chunk
            documents = []
            metadatas = []
            ids = []
            for i, chunk in enumerate(chunks):
                doc_id = f"sb_{meta['year']}_{meta['language']}_{i:04d}"
                documents.append(chunk)
                metadatas.append({
                    "source": f"BMF Steuerbuch {meta['year']}",
                    "year": meta["year"],
                    "language": meta["language"],
                    "file": pdf_path.name,
                    "file_hash": file_hash,
                    "chunk_index": i,
                    "category": "steuerbuch",
                })
                ids.append(doc_id)

            # Store in vector DB
            self.vector_db.add_documents(
                collection_name=STEUERBUCH_COLLECTION,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

            total_chunks += len(chunks)
            results.append({
                "file": pdf_path.name,
                "status": "ingested",
                "chunks": len(chunks),
                "pages": self._page_count(pdf_path),
            })

        return {
            "ingested": sum(1 for r in results if r["status"] == "ingested"),
            "skipped": sum(1 for r in results if r["status"] == "skipped"),
            "total_chunks": total_chunks,
            "files": results,
        }

    def ingest_single(self, pdf_path: str, year: int, language: str) -> Dict[str, Any]:
        """Ingest a single PDF file with explicit metadata."""
        path = Path(pdf_path)
        if not path.exists():
            return {"error": f"File not found: {pdf_path}"}

        self._ensure_collection()

        text = self._extract_text(path)
        if not text.strip():
            return {"error": "No text extracted from PDF"}

        text = self._clean_text(text)
        chunks = self._split_into_chunks(text)
        file_hash = self._file_hash(path)

        documents = []
        metadatas = []
        ids = []
        for i, chunk in enumerate(chunks):
            doc_id = f"sb_{year}_{language}_{i:04d}"
            documents.append(chunk)
            metadatas.append({
                "source": f"BMF Steuerbuch {year}",
                "year": year,
                "language": language,
                "file": path.name,
                "file_hash": file_hash,
                "chunk_index": i,
                "category": "steuerbuch",
            })
            ids.append(doc_id)

        self.vector_db.add_documents(
            collection_name=STEUERBUCH_COLLECTION,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

        return {"file": path.name, "chunks": len(chunks), "status": "ingested"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_collection(self):
        """Make sure the steuerbuch collection exists."""
        try:
            self.vector_db.client.get_collection(STEUERBUCH_COLLECTION)
        except Exception:
            self.vector_db.client.create_collection(
                name=STEUERBUCH_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )

    def _extract_text(self, pdf_path: Path) -> str:
        """Extract all text from a PDF using PyMuPDF."""
        doc = fitz.open(str(pdf_path))
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()
        return "\n".join(pages)

    def _page_count(self, pdf_path: Path) -> int:
        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean extracted PDF text."""
        # Collapse multiple whitespace / newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove page numbers like "  12  " on their own line
        text = re.sub(r"^\s*\d{1,3}\s*$", "", text, flags=re.MULTILINE)
        # Remove excessive spaces
        text = re.sub(r"[ \t]{3,}", "  ", text)
        return text.strip()

    @staticmethod
    def _split_into_chunks(
        text: str,
        chunk_size: int = CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
    ) -> List[str]:
        """Split text into overlapping chunks, preferring paragraph boundaries."""
        # Split on double newlines (paragraphs) first
        paragraphs = re.split(r"\n\n+", text)

        chunks: List[str] = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) + 2 <= chunk_size:
                current = (current + "\n\n" + para).strip() if current else para
            else:
                if current:
                    chunks.append(current)
                # If a single paragraph exceeds chunk_size, split it further
                if len(para) > chunk_size:
                    words = para.split()
                    current = ""
                    for word in words:
                        if len(current) + len(word) + 1 <= chunk_size:
                            current = (current + " " + word).strip() if current else word
                        else:
                            if current:
                                chunks.append(current)
                            current = word
                else:
                    current = para

        if current:
            chunks.append(current)

        # Add overlap: prepend tail of previous chunk to next chunk
        if overlap > 0 and len(chunks) > 1:
            overlapped: List[str] = [chunks[0]]
            for i in range(1, len(chunks)):
                prev_tail = chunks[i - 1][-overlap:]
                overlapped.append(prev_tail + "\n" + chunks[i])
            chunks = overlapped

        # Filter out tiny chunks
        chunks = [c for c in chunks if len(c) > 50]

        return chunks

    @staticmethod
    def _parse_filename(filename: str) -> Dict[str, Any]:
        """Extract year and language from filename like steuerbuch_2026_de.pdf."""
        match = re.match(r"steuerbuch_(\d{4})_(de|en)\.pdf", filename, re.IGNORECASE)
        if match:
            return {"year": int(match.group(1)), "language": match.group(2)}
        # Fallback
        year = 2026
        lang = "de"
        if "2025" in filename:
            year = 2025
        elif "2024" in filename:
            year = 2024
        if "en" in filename.lower():
            lang = "en"
        return {"year": year, "language": lang}

    @staticmethod
    def _file_hash(path: Path) -> str:
        """Compute SHA-256 hash of a file (first 64KB for speed)."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read(65536))
        return h.hexdigest()[:16]

    def _already_ingested(self, file_hash: str) -> bool:
        """Check if a file with this hash is already in the collection."""
        try:
            coll = self.vector_db.client.get_collection(STEUERBUCH_COLLECTION)
            results = coll.get(where={"file_hash": file_hash}, limit=1)
            return bool(results and results.get("ids") and len(results["ids"]) > 0)
        except Exception:
            return False


# Convenience function
def get_pdf_ingestion_service(pdf_dir: Optional[str] = None) -> PDFIngestionService:
    return PDFIngestionService(pdf_dir=pdf_dir)
