"""
Shared transaction query for report services.

Fetches transactions for a given tax year using BOTH:
1. Transaction date within the tax year (legacy/default)
2. Linked document's document_year matching the tax year
   (for docs like L16, Zinsbescheinigung issued in Jan/Feb of next year)

This ensures annual summaries (L16, interest certificates) that are
dated in the next year are still included in the correct tax year report.
"""
from sqlalchemy.orm import Session
from sqlalchemy import extract, or_

from app.models.transaction import Transaction
from app.models.document import Document


def get_transactions_for_tax_year(
    db: Session,
    user_id: int,
    tax_year: int,
) -> list:
    """Fetch all transactions belonging to a tax year.

    Includes transactions where:
    - transaction_date falls within tax_year, OR
    - linked document has document_year = tax_year
    """
    return (
        db.query(Transaction)
        .outerjoin(Document, Transaction.document_id == Document.id)
        .filter(
            Transaction.user_id == user_id,
            or_(
                extract("year", Transaction.transaction_date) == tax_year,
                Document.document_year == tax_year,
            ),
        )
        .order_by(Transaction.transaction_date)
        .all()
    )
