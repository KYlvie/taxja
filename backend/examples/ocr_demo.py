"""
OCR Engine Demo

This script demonstrates how to use the OCR engine to process documents.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ocr_engine import OCREngine
from app.services.document_classifier import DocumentType
import json


def demo_single_document():
    """Demo: Process a single document"""
    print("=" * 60)
    print("Demo: Single Document Processing")
    print("=" * 60)

    # Initialize OCR engine
    ocr_engine = OCREngine()

    # Load sample image (you need to provide your own)
    sample_image_path = "sample_receipt.jpg"

    if not os.path.exists(sample_image_path):
        print(f"\nError: Sample image not found at {sample_image_path}")
        print("Please provide a sample receipt image to test OCR.")
        return

    with open(sample_image_path, "rb") as f:
        image_bytes = f.read()

    # Process document
    print(f"\nProcessing: {sample_image_path}")
    result = ocr_engine.process_document(image_bytes)

    # Display results
    print(f"\nDocument Type: {result.document_type.value}")
    print(f"Confidence Score: {result.confidence_score:.2%}")
    print(f"Needs Review: {result.needs_review}")
    print(f"Processing Time: {result.processing_time_ms:.2f}ms")

    print("\nExtracted Data:")
    print(json.dumps(result.extracted_data, indent=2, default=str))

    if result.suggestions:
        print("\nSuggestions:")
        for suggestion in result.suggestions:
            print(f"  - {suggestion}")

    print("\nRaw Text (first 200 chars):")
    print(result.raw_text[:200])


def demo_batch_processing():
    """Demo: Batch process multiple documents"""
    print("\n" + "=" * 60)
    print("Demo: Batch Document Processing")
    print("=" * 60)

    # Initialize OCR engine
    ocr_engine = OCREngine()

    # Load multiple sample images
    sample_images = ["sample_receipt1.jpg", "sample_receipt2.jpg", "sample_invoice.jpg"]

    image_bytes_list = []
    for image_path in sample_images:
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                image_bytes_list.append(f.read())
        else:
            print(f"Warning: {image_path} not found, skipping...")

    if not image_bytes_list:
        print("\nNo sample images found for batch processing.")
        print("Please provide sample images to test batch OCR.")
        return

    # Process batch
    print(f"\nProcessing {len(image_bytes_list)} documents...")
    batch_result = ocr_engine.process_batch(image_bytes_list)

    # Display results
    print(f"\nTotal Processing Time: {batch_result.total_processing_time_ms:.2f}ms")
    print(f"Success Count: {batch_result.success_count}")
    print(f"Failure Count: {batch_result.failure_count}")

    print("\nGrouped Results:")
    for group_key, results in batch_result.grouped_results.items():
        print(f"  {group_key}: {len(results)} documents")

    if batch_result.suggestions:
        print("\nBatch Suggestions:")
        for suggestion in batch_result.suggestions:
            print(f"  - {suggestion}")


def demo_field_extraction():
    """Demo: Field extraction from text"""
    print("\n" + "=" * 60)
    print("Demo: Field Extraction")
    print("=" * 60)

    from app.services.field_extractor import FieldExtractor

    extractor = FieldExtractor()

    # Sample receipt text
    receipt_text = """
    BILLA AG
    Filiale 1234
    Musterstraße 1, 1010 Wien
    
    Datum: 15.01.2024
    
    Milch                    2,49 A
    Brot                     1,99 A
    Käse                     3,99 A
    
    Summe EUR               8,47
    
    20% USt                 1,41
    
    Vielen Dank für Ihren Einkauf!
    """

    print("\nSample Receipt Text:")
    print(receipt_text)

    # Extract fields
    fields = extractor.extract_fields(receipt_text, DocumentType.RECEIPT)

    print("\nExtracted Fields:")
    print(json.dumps(fields, indent=2, default=str))


def demo_merchant_database():
    """Demo: Merchant database lookup"""
    print("\n" + "=" * 60)
    print("Demo: Merchant Database")
    print("=" * 60)

    from app.services.merchant_database import MerchantDatabase

    merchant_db = MerchantDatabase()

    # Test merchant lookups
    test_merchants = ["billa", "spar", "hofer", "obi", "dm"]

    print("\nMerchant Lookups:")
    for merchant_name in test_merchants:
        merchant_info = merchant_db.lookup_merchant(merchant_name)
        if merchant_info:
            print(f"\n{merchant_name}:")
            print(f"  Official Name: {merchant_info.official_name}")
            print(f"  Category: {merchant_info.category.value}")
            print(f"  VAT Rate: {merchant_info.vat_rate * 100}%")
            print(f"  Austrian: {merchant_info.is_austrian}")

    # Get all merchants
    print("\n\nAll Known Merchants:")
    all_merchants = merchant_db.get_all_merchants()
    for i, merchant in enumerate(all_merchants, 1):
        print(f"  {i}. {merchant}")


def demo_document_classification():
    """Demo: Document classification"""
    print("\n" + "=" * 60)
    print("Demo: Document Classification")
    print("=" * 60)

    from app.services.document_classifier import DocumentClassifier
    import numpy as np

    classifier = DocumentClassifier()

    # Test texts
    test_cases = [
        (
            "BILLA AG\nDatum: 15.01.2024\nSumme EUR 12,34\n20% USt 2,06",
            "Receipt",
        ),
        (
            "Lohnzettel\nBrutto: 3000,00\nNetto: 2100,00\nLohnsteuer: 450,00",
            "Payslip",
        ),
        (
            "Rechnung Nr. 12345\nDatum: 15.01.2024\nBetrag: 500,00\nUSt-ID: ATU12345678",
            "Invoice",
        ),
        (
            "SVS Beitragsmitteilung\nPensionsversicherung: 200,00\nKrankenversicherung: 100,00",
            "SVS Notice",
        ),
    ]

    print("\nClassification Results:")
    for text, expected in test_cases:
        # Create dummy image
        dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)

        doc_type, confidence = classifier.classify(dummy_image, text)

        print(f"\nExpected: {expected}")
        print(f"Classified as: {doc_type.value}")
        print(f"Confidence: {confidence:.2%}")
        print(f"Text preview: {text[:50]}...")


def main():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("OCR Engine Demo")
    print("=" * 60)

    # Check if Tesseract is installed
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        print("\n✓ Tesseract is installed")
    except Exception as e:
        print(f"\n✗ Tesseract not found: {e}")
        print("Please install Tesseract OCR to use this demo.")
        print("See backend/docs/TESSERACT_SETUP.md for installation instructions.")
        return

    # Run demos
    try:
        demo_field_extraction()
        demo_merchant_database()
        demo_document_classification()

        # These require actual image files
        # demo_single_document()
        # demo_batch_processing()

        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

