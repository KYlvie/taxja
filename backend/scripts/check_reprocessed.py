"""Check reprocessed Gehalt documents"""
import json
from app.models.chat_message import ChatMessage
from app.db.base import SessionLocal
from app.models.document import Document

db = SessionLocal()
gehalt_ids = list(range(27, 39))
docs = db.query(Document).filter(Document.id.in_(gehalt_ids)).order_by(Document.id).all()
for d in docs:
    ocr = d.ocr_result
    if ocr:
        gross = ocr.get("gross_income")
        net = ocr.get("net_income")
        tax = ocr.get("withheld_tax")
        emp = ocr.get("employer", ocr.get("supplier", ""))
        dt = ocr.get("date", "")
        print(f"id={d.id} {d.file_name:<25} type={str(d.document_type):<30} conf={d.confidence_score} txn={d.transaction_id} gross={gross} net={net} tax={tax} emp={str(emp)[:30]}")
    else:
        print(f"id={d.id} {d.file_name:<25} type={str(d.document_type):<30} conf={d.confidence_score} txn={d.transaction_id} OCR=PENDING")
db.close()
