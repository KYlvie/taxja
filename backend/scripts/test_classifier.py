"""Manual classifier smoke script for local debugging."""

from app.db.base import SessionLocal
from app.models.document import Document
from app.services.document_classifier import DocumentClassifier


def main() -> None:
    db = SessionLocal()
    classifier = DocumentClassifier()

    try:
        for doc_id in [27, 30, 36]:
            document = db.query(Document).filter(Document.id == doc_id).first()
            if document and document.raw_text:
                doc_type, confidence = classifier.classify(None, document.raw_text)
                print(
                    f"Doc {document.id} ({document.file_name}): "
                    f"classified as {doc_type} (conf={confidence:.3f})"
                )
            else:
                print(f"Doc {doc_id}: no raw text")
    finally:
        db.close()


if __name__ == "__main__":
    main()
