"""
Automated Austrian tax law scraper.
Fetches current tax law data from official sources (WKO, USP, BMF)
and uses LLM to structure it into trilingual knowledge base documents.

Usage:
    from app.services.tax_law_scraper import TaxLawScraper
    scraper = TaxLawScraper()
    results = await scraper.scrape_and_update()
"""
import logging
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# Official Austrian tax law sources
OFFICIAL_SOURCES = [
    {
        "id": "wko_income_tax",
        "url": "https://www.wko.at/en/current-values",
        "name": "WKO Income Tax / Corporation Tax",
        "category": "income_tax",
    },
    {
        "id": "wko_kleinunternehmer",
        "url": "https://www.wko.at/en/small-business-exemption-regulation-sales-tax",
        "name": "WKO Kleinunternehmerregelung (EN)",
        "category": "vat",
    },
    {
        "id": "wko_steuertarif_de",
        "url": "https://www.wko.at/steuern/aktuelle-werte-est-koest",
        "name": "WKO Steuertarif (DE)",
        "category": "income_tax",
    },
    {
        "id": "wko_kleinunternehmer_de",
        "url": "https://www.wko.at/kleinunternehmerregelung-umsatzsteuer",
        "name": "WKO Kleinunternehmerregelung (DE)",
        "category": "vat",
    },
]


# Directory to cache raw scraped HTML
SCRAPE_CACHE_DIR = Path("./data/tax_law_cache")

_EXTRACT_PROMPT = """\
You are an Austrian tax law expert. Extract ALL tax-relevant facts from the following
official government webpage text. Output a JSON array of knowledge documents.

Each document must have:
- "text_de": German text (precise legal language with § references)
- "text_en": English translation
- "text_zh": Chinese translation
- "category": one of: income_tax, vat, social_insurance, deductions, corporate_tax, other
- "subcategory": specific topic (e.g. "tax_brackets", "kleinunternehmerregelung")
- "legal_refs": array of § references (e.g. ["§6 Abs 1 Z 27 UStG"])
- "valid_from": year this rule is valid from (e.g. "2025")

RULES:
- Include EVERY number, threshold, rate, deadline, and condition
- Always include the § legal reference when available
- Be precise with EUR amounts — do not round
- If a rule changed (e.g. threshold raised from X to Y), mention BOTH old and new values
- Each document should cover ONE specific rule or topic
- Keep each text field under 500 characters
- Output ONLY a valid JSON array, no markdown fences, no explanation

SOURCE TEXT:
{text}
"""


class TaxLawScraper:
    """Scrapes official Austrian tax law sources and structures them via LLM."""

    def __init__(self):
        SCRAPE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._http = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; TaxjaBot/1.0; "
                    "+https://github.com/KYlvie/taxja)"
                ),
                "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
            },
        )

    async def close(self):
        await self._http.aclose()

    # ------------------------------------------------------------------
    # 1. Fetch raw HTML from official sources
    # ------------------------------------------------------------------
    async def fetch_source(self, source: Dict[str, str]) -> Optional[str]:
        """Fetch and extract text content from an official source URL."""
        url = source["url"]
        source_id = source["id"]
        try:
            resp = await self._http.get(url)
            resp.raise_for_status()
            html = resp.text

            # Cache raw HTML
            cache_path = SCRAPE_CACHE_DIR / f"{source_id}.html"
            cache_path.write_text(html, encoding="utf-8")

            # Extract text from HTML
            soup = BeautifulSoup(html, "html.parser")
            # Remove script/style
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            # Collapse whitespace
            text = re.sub(r"\n{3,}", "\n\n", text)
            # Limit to ~15k chars to fit LLM context
            if len(text) > 15000:
                text = text[:15000] + "\n\n[... truncated ...]"

            logger.info(f"Fetched {source_id}: {len(text)} chars from {url}")
            return text

        except Exception as e:
            logger.error(f"Failed to fetch {source_id} from {url}: {e}")
            return None

    # ------------------------------------------------------------------
    # 2. Use LLM to extract structured knowledge documents
    # ------------------------------------------------------------------
    def extract_knowledge(
        self, raw_text: str, source: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Use LLM to extract structured trilingual knowledge from raw text."""
        llm = get_llm_service()

        system = (
            "You are an Austrian tax law expert. "
            "Extract tax facts and output ONLY a JSON array. No markdown."
        )
        user_prompt = _EXTRACT_PROMPT.format(text=raw_text)

        try:
            content = llm.generate_simple(
                system_prompt=system,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=8000,
            )
            if not content:
                logger.warning(f"Empty LLM response for {source['id']}")
                return []

            # Parse JSON from response
            content = content.strip()
            # Remove <think>...</think> blocks
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            # Remove markdown fences
            if "```" in content:
                match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
                if match:
                    content = match.group(1).strip()
            # Find the JSON array
            start = content.find("[")
            end = content.rfind("]")
            if start != -1 and end != -1 and end > start:
                content = content[start : end + 1]

            docs = json.loads(content)
            if not isinstance(docs, list):
                docs = [docs]

            # Attach source metadata
            for doc in docs:
                doc["source_id"] = source["id"]
                doc["source_url"] = source["url"]
                doc["source_name"] = source["name"]
                doc["scraped_at"] = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"Extracted {len(docs)} knowledge docs from {source['id']}"
            )
            return docs

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON for {source['id']}: {e}")
            logger.debug(f"Raw content: {content[:500]}")
            return []
        except Exception as e:
            logger.error(f"LLM extraction failed for {source['id']}: {e}")
            return []

    # ------------------------------------------------------------------
    # 3. Store extracted knowledge into vector DB
    # ------------------------------------------------------------------
    def update_knowledge_base(
        self, all_docs: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Store extracted documents into the vector DB (trilingual)."""
        from app.services.vector_db_service import get_vector_db_service

        vdb = get_vector_db_service()

        # Reset the scraped collection (separate from hand-written docs)
        vdb.reset_collection("scraped_tax_law")

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []

        for i, doc in enumerate(all_docs):
            # Create one entry per language
            for lang, key in [("de", "text_de"), ("en", "text_en"), ("zh", "text_zh")]:
                text = doc.get(key, "")
                if not text:
                    continue
                doc_id = f"scraped_{doc.get('source_id', 'unknown')}_{i}_{lang}"
                meta = {
                    "source": doc.get("source_name", ""),
                    "source_url": doc.get("source_url", ""),
                    "category": doc.get("category", "other"),
                    "subcategory": doc.get("subcategory", ""),
                    "language": lang,
                    "legal_refs": ", ".join(doc.get("legal_refs", [])),
                    "valid_from": doc.get("valid_from", ""),
                    "scraped_at": doc.get("scraped_at", ""),
                }
                documents.append(text)
                metadatas.append(meta)
                ids.append(doc_id)

        if documents:
            vdb.add_documents(
                collection_name="scraped_tax_law",
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

        stats = {
            "total_source_docs": len(all_docs),
            "total_vector_entries": len(documents),
            "languages": {"de": 0, "en": 0, "zh": 0},
        }
        for m in metadatas:
            lang = m.get("language", "")
            if lang in stats["languages"]:
                stats["languages"][lang] += 1

        logger.info(f"Knowledge base updated: {stats}")
        return stats

    # ------------------------------------------------------------------
    # 4. Save extracted docs as JSON for audit trail
    # ------------------------------------------------------------------
    def save_audit_trail(self, all_docs: List[Dict[str, Any]]):
        """Save extracted knowledge to JSON file for traceability."""
        audit_dir = SCRAPE_CACHE_DIR / "extracted"
        audit_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = audit_dir / f"knowledge_{ts}.json"
        path.write_text(
            json.dumps(all_docs, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"Audit trail saved: {path}")
        return str(path)

    # ------------------------------------------------------------------
    # 5. Main entry point: scrape all sources and update KB
    # ------------------------------------------------------------------
    async def scrape_and_update(
        self, source_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Scrape official sources, extract knowledge via LLM, update vector DB.

        Args:
            source_ids: Optional list of source IDs to scrape.
                        If None, scrapes all OFFICIAL_SOURCES.

        Returns:
            Summary dict with stats and any errors.
        """
        sources = OFFICIAL_SOURCES
        if source_ids:
            sources = [s for s in sources if s["id"] in source_ids]

        all_docs: List[Dict[str, Any]] = []
        errors: List[str] = []
        fetched = 0

        for source in sources:
            raw_text = await self.fetch_source(source)
            if not raw_text:
                errors.append(f"Failed to fetch {source['id']}")
                continue
            fetched += 1

            docs = self.extract_knowledge(raw_text, source)
            if not docs:
                errors.append(f"No docs extracted from {source['id']}")
                continue
            all_docs.extend(docs)

        # Store in vector DB
        stats = {}
        if all_docs:
            stats = self.update_knowledge_base(all_docs)
            self.save_audit_trail(all_docs)

        await self.close()

        return {
            "sources_attempted": len(sources),
            "sources_fetched": fetched,
            "documents_extracted": len(all_docs),
            "vector_db_stats": stats,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
_scraper: Optional[TaxLawScraper] = None


def get_tax_law_scraper() -> TaxLawScraper:
    global _scraper
    if _scraper is None:
        _scraper = TaxLawScraper()
    return _scraper
