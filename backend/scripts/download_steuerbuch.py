#!/usr/bin/env python3
"""
Download Austrian Steuerbuch (Tax Book) PDFs from BMF website.

Usage:
    python scripts/download_steuerbuch.py

Downloads German and English versions for 2024, 2025, 2026 into data/steuerbuch/.
"""
import os
import sys
import urllib.request
import ssl
import re

BASE = "https://www.bmf.gv.at"
STEUERBUCH_PAGE = BASE + "/services/publikationen/das-steuerbuch.html"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "steuerbuch")

# Which years/languages we want
WANTED = {
    (2026, "de"), (2026, "en"),
    (2025, "de"), (2025, "en"),
    (2024, "de"), (2024, "en"),
}


def fetch_pdf_links() -> dict:
    """Parse the BMF page to extract real JCR PDF links."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(STEUERBUCH_PAGE, headers={"User-Agent": "Taxja/1.0"})
    html = urllib.request.urlopen(req, context=ctx, timeout=30).read().decode("utf-8")

    # Extract all PDF hrefs
    raw_links = re.findall(r'href=["\']([^"\']*?\.pdf)["\']', html, re.IGNORECASE)

    mapping = {}
    for link in raw_links:
        url = link if link.startswith("http") else BASE + link
        name_lower = link.lower()
        # Detect year
        for year in (2024, 2025, 2026):
            if str(year) in name_lower:
                lang = "en" if "_en" in name_lower or "-en" in name_lower else "de"
                mapping[(year, lang)] = url
                break
    return mapping


def download(url: str, dest: str) -> bool:
    """Download a file, return True on success."""
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "Taxja/1.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            data = resp.read()
            if len(data) < 10_000:
                return False
            with open(dest, "wb") as f:
                f.write(data)
        return True
    except Exception as exc:
        print(f"  Failed: {exc}")
        return False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching PDF links from BMF website...")
    links = fetch_pdf_links()
    print(f"Found {len(links)} PDF links\n")

    success = 0
    for (year, lang) in sorted(WANTED):
        filename = f"steuerbuch_{year}_{lang}.pdf"
        dest = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
            size_mb = os.path.getsize(dest) / (1024 * 1024)
            print(f"[SKIP] {filename} already exists ({size_mb:.1f} MB)")
            success += 1
            continue

        url = links.get((year, lang))
        if not url:
            print(f"[MISS] {filename} - no link found on BMF page")
            continue

        print(f"[DOWNLOAD] {filename}")
        print(f"  URL: {url}")
        if download(url, dest):
            size_mb = os.path.getsize(dest) / (1024 * 1024)
            print(f"  OK ({size_mb:.1f} MB)")
            success += 1
        else:
            print(f"  FAILED")

    print(f"\nDone: {success}/{len(WANTED)} files in {OUTPUT_DIR}")
    if success < len(WANTED):
        print(
            "\nFor missing files, download manually from:\n"
            f"  {STEUERBUCH_PAGE}\n"
            f"  Save to: {os.path.abspath(OUTPUT_DIR)}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
