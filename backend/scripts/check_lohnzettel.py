"""Check Lohnzettel OCR data"""
import json
from app.models.chat_message import ChatMessage
from app.db.base import SessionLocal
from app.models.document import Document

db = SessionLocal()
# Check docs 36 and 37 (Lohnzettel with no transaction)
for doc_id in [36, 37, 38]:
    d = db.query(Document).filter(Document.id == doc_id).first()
    if d:
        print(f"\n=== Doc {d.id}: {d.file_name} type={d.document_type} txn={d.transaction_id} ===")
        if d.ocr_result:
            print(json.dumps(d.ocr_result, indent=2, default=str)[:800])
        else:
            print("No OCR result")
db.close()
