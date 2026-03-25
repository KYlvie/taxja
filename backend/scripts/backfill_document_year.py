"""Backfill document year attribution for bank statements and tax-year documents."""
from __future__ import annotations

import argparse
from typing import Iterable

from sqlalchemy.orm.attributes import flag_modified

from app.db.base import SessionLocal
from app.models.document import Document, DocumentType
from app.services.document_year_attribution import materialize_document_temporal_metadata


SUPPORTED_TYPES = {
    DocumentType.BANK_STATEMENT,
    DocumentType.KONTOAUSZUG,
}


def _is_in_scope(document: Document) -> bool:
    if document.document_type in SUPPORTED_TYPES:
        return True
    ocr_result = document.ocr_result or {}
    return isinstance(ocr_result, dict) and ocr_result.get("tax_year") is not None


def _iter_candidates(db, batch_size: int) -> Iterable[list[Document]]:
    last_id = 0
    while True:
        batch = (
            db.query(Document)
            .filter(Document.document_year.is_(None))
            .filter(Document.id > last_id)
            .order_by(Document.id.asc())
            .limit(batch_size)
            .all()
        )
        if not batch:
            break
        yield batch
        last_id = batch[-1].id


def main():
    parser = argparse.ArgumentParser(description="Backfill document year attribution fields")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    processed = 0
    updated = 0
    try:
        for batch in _iter_candidates(db, args.batch_size):
            for document in batch:
                if args.limit is not None and processed >= args.limit:
                    break

                processed += 1
                if not _is_in_scope(document):
                    continue

                ocr_result = dict(document.ocr_result or {})
                before = (
                    document.document_date,
                    document.document_year,
                    document.year_basis,
                    document.year_confidence,
                    ocr_result.get("document_year"),
                    ocr_result.get("year_basis"),
                    ocr_result.get("year_confidence"),
                )

                materialize_document_temporal_metadata(document, ocr_result)
                after = (
                    document.document_date,
                    document.document_year,
                    document.year_basis,
                    document.year_confidence,
                    ocr_result.get("document_year"),
                    ocr_result.get("year_basis"),
                    ocr_result.get("year_confidence"),
                )

                if after != before:
                    updated += 1
                    if not args.dry_run:
                        document.ocr_result = ocr_result
                        flag_modified(document, "ocr_result")

            if args.dry_run:
                db.rollback()
            else:
                db.commit()

            if args.limit is not None and processed >= args.limit:
                break

        print(
            f"Document year backfill complete. processed={processed} updated={updated} dry_run={args.dry_run}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
