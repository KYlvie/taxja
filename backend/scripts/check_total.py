"""Check total docs"""
from app.models.chat_message import ChatMessage
from app.db.base import SessionLocal
from app.models.document import Document

db = SessionLocal()
total = db.query(Document).filter(Document.user_id == 4, Document.is_archived == False).count()
archived = db.query(Document).filter(Document.user_id == 4, Document.is_archived == True).count()
print(f"Active docs: {total}, Archived: {archived}")
db.close()
