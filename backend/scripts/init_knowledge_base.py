#!/usr/bin/env python3
"""
Initialize AI Tax Assistant knowledge base.

This script initializes the vector database with Austrian tax law documents,
2026 USP tax tables, and common tax FAQs.

Usage:
    python scripts/init_knowledge_base.py
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.knowledge_base_service import get_knowledge_base_service


def main():
    """Initialize knowledge base"""
    print("=" * 60)
    print("AI Tax Assistant Knowledge Base Initialization")
    print("=" * 60)
    print()
    
    kb_service = get_knowledge_base_service()
    
    try:
        kb_service.initialize_all()
        print()
        print("=" * 60)
        print("✓ Knowledge base initialized successfully!")
        print("=" * 60)
        print()
        print("Collections created:")
        print("  - austrian_tax_law (Austrian tax law documents)")
        print("  - usp_2026_tax_tables (2026 USP tax tables)")
        print("  - tax_faq (Common tax questions and answers)")
        print()
        print("The AI Tax Assistant is now ready to use.")
        
    except Exception as e:
        print()
        print("=" * 60)
        print("✗ Error initializing knowledge base:")
        print(f"  {str(e)}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
