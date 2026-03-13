"""Reprocess all Gehalt documents with updated classifier"""
from app.models.chat_message import ChatMessage
from app.db.base import SessionLocal
from app.models.document import Document, DocumentType
from app.models.transaction import Transaction

db = SessionLocal()

gehalt_ids = list(range(27, 39))
docs = db.query(Document).filter(Document.id.in_(gehalt_ids)).all()

for d in docs:
    # Delete linked transaction if any
    if d.transaction_id:
        txn = db.query(Transaction).filter(Transaction.id == d.transaction_id).first()
        if txn:
            db.delete(txn)
        d.transaction_id = None
    
    # Reset OCR data
    d.ocr_result = None
    d.raw_text = None
    d.confidence_score = None
    d.processed_at = None
    d.document_type = DocumentType.OTHER

db.commit()
print(f"Reset {len(docs)} documents")

# Queue for reprocessing
from app.tasks.ocr_tasks import process_document_ocr
for d in docs:
    try:
        process_document_ocr.delay(d.id)
        print(f"Queued doc {d.id}: {d.file_name}")
    except Exception as e:
        print(f"Failed doc {d.id}: {e}")

db.close()
