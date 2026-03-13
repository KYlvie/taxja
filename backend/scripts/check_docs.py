"""Check recent documents for user 4"""
from app.models.chat_message import ChatMessage
from app.db.base import SessionLocal
from app.models.document import Document

db = SessionLocal()
docs = db.query(Document).filter(Document.user_id == 4).order_by(Document.id.desc()).limit(10).all()
for d in docs:
    print(f"id={d.id} name={d.file_name} type={d.document_type} archived={d.is_archived} ocr={bool(d.ocr_result)} conf={d.confidence_score} txn={d.transaction_id}")
db.close()
