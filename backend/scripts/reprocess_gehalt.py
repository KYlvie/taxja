"""Reprocess all Gehalt documents that were incorrectly classified"""
from app.models.chat_message import ChatMessage
from app.db.base import SessionLocal
from app.models.document import Document, DocumentType
from app.models.transaction import Transaction
from datetime import datetime

db = SessionLocal()

# Find all Gehalt docs (id 27-38) that need reprocessing
gehalt_ids = list(range(27, 39))
docs = db.query(Document).filter(Document.id.in_(gehalt_ids)).all()

for d in docs:
    print(f"Resetting doc {d.id}: {d.file_name} (was type={d.document_type})")
    
    # Delete linked transaction if any
    if d.transaction_id:
        txn = db.query(Transaction).filter(Transaction.id == d.transaction_id).first()
        if txn:
            print(f"  Deleting linked transaction {txn.id}")
            db.delete(txn)
        d.transaction_id = None
    
    # Reset OCR data so it gets reprocessed
    d.ocr_result = None
    d.raw_text = None
    d.confidence_score = None
    d.processed_at = None
    d.document_type = DocumentType.OTHER  # Will be re-classified by OCR

db.commit()
print(f"\nReset {len(docs)} documents. Now triggering reprocessing...")

# Trigger OCR reprocessing via Celery
from app.tasks.ocr_tasks import process_document_ocr
queued = 0
for d in docs:
    try:
        process_document_ocr.delay(d.id)
        queued += 1
        print(f"  Queued doc {d.id} for OCR")
    except Exception as e:
        print(f"  Failed to queue doc {d.id}: {e}")

print(f"\nQueued {queued} documents for reprocessing")
db.close()
