"""Check all documents for user 4 to find problematic ones"""
from app.models.chat_message import ChatMessage
from app.db.base import SessionLocal
from app.models.document import Document

db = SessionLocal()
docs = db.query(Document).filter(Document.user_id == 4, Document.is_archived == False).order_by(Document.id).all()
for d in docs:
    ocr_ok = "yes" if d.ocr_result else "no"
    print(f"id={d.id} name={d.file_name:<30} type={str(d.document_type):<30} conf={d.confidence_score} txn={d.transaction_id} ocr={ocr_ok}")
print(f"\nTotal: {len(docs)} documents")
db.close()
