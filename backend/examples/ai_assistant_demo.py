#!/usr/bin/env python3
"""
AI Tax Assistant Demo Script

This script demonstrates the AI Tax Assistant functionality including:
- Basic tax questions
- OCR result explanation
- Tax optimization suggestions
- Multi-language support
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ai_assistant_service import get_ai_assistant_service
from app.services.knowledge_base_service import get_knowledge_base_service


def demo_basic_question():
    """Demo: Basic tax question"""
    print("\n" + "=" * 60)
    print("Demo 1: Basic Tax Question (German)")
    print("=" * 60)
    
    ai_service = get_ai_assistant_service()
    
    response = ai_service.generate_response(
        user_message="Wie berechne ich meine Einkommensteuer für 2026?",
        user_context={"user_type": "employee"},
        conversation_history=[],
        language="de"
    )
    
    print("\nQuestion: Wie berechne ich meine Einkommensteuer für 2026?")
    print("\nResponse:")
    print(response)


def demo_vat_question():
    """Demo: VAT question in English"""
    print("\n" + "=" * 60)
    print("Demo 2: VAT Question (English)")
    print("=" * 60)
    
    ai_service = get_ai_assistant_service()
    
    response = ai_service.generate_response(
        user_message="Do I need to pay VAT if my turnover is €50,000?",
        user_context={
            "user_type": "self_employed",
            "year_to_date_income": 50000.00
        },
        conversation_history=[],
        language="en"
    )
    
    print("\nQuestion: Do I need to pay VAT if my turnover is €50,000?")
    print("\nResponse:")
    print(response)


def demo_chinese_question():
    """Demo: Tax question in Chinese"""
    print("\n" + "=" * 60)
    print("Demo 3: Tax Question (Chinese)")
    print("=" * 60)
    
    ai_service = get_ai_assistant_service()
    
    response = ai_service.generate_response(
        user_message="我可以扣除哪些费用？",
        user_context={"user_type": "self_employed"},
        conversation_history=[],
        language="zh"
    )
    
    print("\nQuestion: 我可以扣除哪些费用？")
    print("\nResponse:")
    print(response)


def demo_ocr_explanation():
    """Demo: OCR result explanation"""
    print("\n" + "=" * 60)
    print("Demo 4: OCR Result Explanation")
    print("=" * 60)
    
    ai_service = get_ai_assistant_service()
    
    ocr_data = {
        "document_type": "receipt",
        "extracted_data": {
            "merchant": "BILLA",
            "date": "2026-03-01",
            "amount": 45.50,
            "items": [
                {"name": "Milch", "price": 1.50},
                {"name": "Brot", "price": 2.00},
                {"name": "Kugelschreiber", "price": 3.00},
                {"name": "Notizbuch", "price": 5.00}
            ],
            "vat_amounts": {
                "20%": 7.58
            }
        },
        "confidence_score": 0.85
    }
    
    explanation = ai_service.explain_ocr_result(ocr_data, language="de")
    
    print("\nOCR Data:")
    print(f"  Merchant: {ocr_data['extracted_data']['merchant']}")
    print(f"  Amount: €{ocr_data['extracted_data']['amount']}")
    print(f"  Items: {len(ocr_data['extracted_data']['items'])}")
    print(f"  Confidence: {ocr_data['confidence_score']}")
    
    print("\nAI Explanation:")
    print(explanation)


def demo_tax_optimization():
    """Demo: Tax optimization suggestions"""
    print("\n" + "=" * 60)
    print("Demo 5: Tax Optimization Suggestions")
    print("=" * 60)
    
    ai_service = get_ai_assistant_service()
    
    user_tax_data = {
        "year_to_date_income": 60000.00,
        "year_to_date_expenses": 5000.00,
        "estimated_tax": 12000.00,
        "user_type": "self_employed",
        "vat_liable": True,
        "commuting_distance_km": 0,  # Not claiming commuting allowance
        "home_office_claimed": False  # Not claiming home office
    }
    
    suggestions = ai_service.suggest_tax_optimization(user_tax_data, language="en")
    
    print("\nUser Tax Data:")
    print(f"  Income: €{user_tax_data['year_to_date_income']:,.2f}")
    print(f"  Expenses: €{user_tax_data['year_to_date_expenses']:,.2f}")
    print(f"  Estimated Tax: €{user_tax_data['estimated_tax']:,.2f}")
    print(f"  User Type: {user_tax_data['user_type']}")
    
    print("\nAI Optimization Suggestions:")
    print(suggestions)


def demo_conversation_context():
    """Demo: Multi-turn conversation with context"""
    print("\n" + "=" * 60)
    print("Demo 6: Multi-Turn Conversation")
    print("=" * 60)
    
    ai_service = get_ai_assistant_service()
    
    # First question
    print("\nUser: What is the income tax rate for €50,000?")
    response1 = ai_service.generate_response(
        user_message="What is the income tax rate for €50,000?",
        user_context={"user_type": "employee"},
        conversation_history=[],
        language="en"
    )
    print(f"\nAssistant: {response1[:200]}...")
    
    # Follow-up question with context
    conversation_history = [
        {"role": "user", "content": "What is the income tax rate for €50,000?"},
        {"role": "assistant", "content": response1}
    ]
    
    print("\n\nUser: What about €100,000?")
    response2 = ai_service.generate_response(
        user_message="What about €100,000?",
        user_context={"user_type": "employee"},
        conversation_history=conversation_history,
        language="en"
    )
    print(f"\nAssistant: {response2[:200]}...")


def demo_disclaimer_verification():
    """Demo: Verify disclaimer is always included"""
    print("\n" + "=" * 60)
    print("Demo 7: Disclaimer Verification")
    print("=" * 60)
    
    ai_service = get_ai_assistant_service()
    
    languages = ["de", "en", "zh"]
    
    for lang in languages:
        response = ai_service.generate_response(
            user_message="Test question",
            user_context={},
            conversation_history=[],
            language=lang
        )
        
        disclaimer = ai_service.DISCLAIMERS[lang]
        has_disclaimer = disclaimer in response
        
        print(f"\nLanguage: {lang}")
        print(f"Disclaimer included: {'✓' if has_disclaimer else '✗'}")
        print(f"Disclaimer text: {disclaimer[:100]}...")


def main():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("AI Tax Assistant Demo")
    print("=" * 60)
    print("\nThis demo showcases the AI Tax Assistant capabilities.")
    print("Make sure you have set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env")
    print()
    
    # Check if knowledge base is initialized
    try:
        kb_service = get_knowledge_base_service()
        print("✓ Knowledge base service initialized")
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nPlease run: python scripts/init_knowledge_base.py")
        sys.exit(1)
    
    # Run demos
    try:
        demo_basic_question()
        demo_vat_question()
        demo_chinese_question()
        demo_ocr_explanation()
        demo_tax_optimization()
        demo_conversation_context()
        demo_disclaimer_verification()
        
        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error running demo: {e}")
        print("\nMake sure you have:")
        print("  1. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env")
        print("  2. Initialized the knowledge base")
        print("  3. Installed all dependencies")
        sys.exit(1)


if __name__ == "__main__":
    main()
