"""
Script to download official Austrian tax documents.
Run with: python -m backend.scripts.download_tax_docs
"""
import requests
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Official document URLs (update these with actual URLs)
TAX_DOCUMENTS = {
    "2023": {
        "EStR": "https://www.bmf.gv.at/dam/jcr:..../EStR_2023.pdf",
        "UStR": "https://www.bmf.gv.at/dam/jcr:..../UStR_2023.pdf",
    },
    "2024": {
        "EStR": "https://www.bmf.gv.at/dam/jcr:..../EStR_2024.pdf",
        "UStR": "https://www.bmf.gv.at/dam/jcr:..../UStR_2024.pdf",
    },
    "2025": {
        "EStR": "https://www.bmf.gv.at/dam/jcr:..../EStR_2025.pdf",
        "UStR": "https://www.bmf.gv.at/dam/jcr:..../UStR_2025.pdf",
    },
    "2026": {
        "EStR": "https://www.bmf.gv.at/dam/jcr:..../EStR_2026.pdf",
        "UStR": "https://www.bmf.gv.at/dam/jcr:..../UStR_2026.pdf",
    },
}


def download_document(url: str, output_path: Path) -> bool:
    """Download a document from URL to output path."""
    try:
        logger.info(f"Downloading: {url}")
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        
        logger.info(f"✅ Saved: {output_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to download {url}: {e}")
        return False


def main():
    """Download all configured tax documents."""
    docs_dir = Path(__file__).parent.parent / "docs" / "austrian_tax"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Output directory: {docs_dir}")
    logger.info("=" * 80)
    
    success_count = 0
    total_count = 0
    
    for year, documents in TAX_DOCUMENTS.items():
        logger.info(f"\nYear: {year}")
        logger.info("-" * 80)
        
        for doc_type, url in documents.items():
            total_count += 1
            output_path = docs_dir / f"{doc_type}_{year}.pdf"
            
            if output_path.exists():
                logger.info(f"⏭️  Skipping (already exists): {output_path.name}")
                success_count += 1
                continue
            
            if download_document(url, output_path):
                success_count += 1
    
    logger.info("=" * 80)
    logger.info(f"Download complete: {success_count}/{total_count} successful")
    
    if success_count < total_count:
        logger.warning(
            "\n⚠️  Some downloads failed. "
            "Please check URLs in TAX_DOCUMENTS dictionary."
        )


if __name__ == "__main__":
    main()
