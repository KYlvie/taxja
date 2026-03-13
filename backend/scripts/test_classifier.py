"""Test the updated classifier against actual payslip text"""
from app.models.chat_message import ChatMessage
from app.db.base import SessionLocal
from app.models.document import Document
from app.services.document_classifier import DocumentClassifier

db = SessionLocal()
classifier = DocumentClassifier()

for doc_id in [27, 30, 36]:
    d = db.query(Document).filter(Document.id == doc_id).first()
    if d and d.raw_text:
        doc_type, conf = classifier.classify(None, d.raw_text)
        print(f"Doc {d.id} ({d.file_name}): classified as {doc_type} (conf={conf:.3f})")
    else:
        print(f"Doc {doc_id}: no raw text")

db.close()
