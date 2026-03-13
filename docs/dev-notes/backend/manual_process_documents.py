#!/usr/bin/env python3
"""Manually process uploaded documents that haven't been OCR'd yet"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.document import Document
from app.services.ocr_engine import OCREngine
from app.services.storage_service import StorageService

# Create sync engine
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Get unprocessed documents
documents = db.query(Document).filter(
    Document.processed_at == None,
    Document.user_id == 11
).all()

print(f"Found {len(documents)} unprocessed documents")

storage = StorageService()
ocr = OCREngine()

for doc in documents:
    print(f"\nProcessing: {doc.file_name} (ID: {doc.id})")
    
    # Download file from storage
    file_bytes = storage.download_file(doc.file_path)
    if not file_bytes:
        print(f"  ERROR: Could not download file")
        continue
    
    # Process with OCR
    try:
        result = ocr.process_document(file_bytes)
        
        # Update document
        from datetime import datetime
        doc.document_type = result.document_type
        doc.raw_text = result.raw_text
        doc.extracted_data = result.extracted_data
        doc.processed_at = datetime.utcnow()
        
        db.commit()
        
        print(f"  SUCCESS: Type={result.document_type.value}, Confidence={result.confidence_score:.2f}")
        if result.extracted_data:
            print(f"  Extracted {len(result.extracted_data)} fields")
            for key, value in list(result.extracted_data.items())[:5]:
                print(f"    - {key}: {value}")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()

db.close()
print("\nDone!")
