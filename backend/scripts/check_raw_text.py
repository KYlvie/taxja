"""Check raw OCR text for a Gehalt document"""
from app.models.chat_message import ChatMessage
from app.db.base import SessionLocal
from app.models.document import Document

db = SessionLocal()
d = db.query(Document).filter(Document.id == 27).first()
if d and d.raw_text:
    print(f"Doc {d.id}: {d.file_name}")
    print(f"Type: {d.document_type}")
    print(f"Raw text length: {len(d.raw_text)}")
    print("--- First 2000 chars ---")
    print(d.raw_text[:2000])
else:
    print(f"Doc 27: no raw text")
db.close()
