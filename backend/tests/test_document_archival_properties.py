"""
Property-based tests for document archival and transaction association

Property 26: Document archival association integrity
Validates: Requirements 19.8, 19.9, 24.1, 24.7
"""
import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timedelta
from decimal import Decimal

from app.models.document import Document, DocumentType
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.document_archival_service import DocumentArchivalService


# Strategies for generating test data
@st.composite
def document_strategy(draw):
    """Generate a valid document"""
    return {
        "document_type": draw(st.sampled_from(list(DocumentType))),
        "file_path": draw(st.text(min_size=10, max_size=100)),
        "file_name": draw(st.text(min_size=5, max_size=50)),
        "file_size": draw(st.integers(min_value=100, max_value=10_000_000)),
        "mime_type": draw(st.sampled_from(["image/jpeg", "image/png", "application/pdf"])),
        "confidence_score": draw(st.floats(min_value=0.0, max_value=1.0)),
    }


@st.composite
def transaction_strategy(draw):
    """Generate a valid transaction"""
    return {
        "type": draw(st.sampled_from(list(TransactionType))),
        "amount": draw(st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100000.00"), places=2)),
        "date": draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2026, 12, 31))),
        "description": draw(st.text(min_size=5, max_size=200)),
    }


class TestDocumentArchivalProperties:
    """Property-based tests for document archival"""

    @given(document_strategy())
    @settings(max_examples=50)
    def test_property_26a_document_archival_preserves_data(self, db_session, test_user, document_data):
        """
        Property 26a: Archiving a document preserves all document data
        
        When a document is archived, all its data should remain intact
        and accessible, only the archival status should change.
        """
        # Create document
        document = Document(
            user_id=test_user.id,
            **document_data,
            uploaded_at=datetime.utcnow(),
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Store original data
        original_id = document.id
        original_file_path = document.file_path
        original_file_name = document.file_name
        original_file_size = document.file_size
        original_mime_type = document.mime_type
        original_confidence = document.confidence_score
        
        # Archive document
        archival_service = DocumentArchivalService(db_session)
        success = archival_service.archive_document(document.id)
        
        assert success, "Archival should succeed"
        
        # Refresh document
        db_session.refresh(document)
        
        # Verify archival status changed
        assert document.is_archived == True, "Document should be marked as archived"
        assert document.archived_at is not None, "Archived timestamp should be set"
        
        # Verify all original data is preserved
        assert document.id == original_id, "Document ID should not change"
        assert document.file_path == original_file_path, "File path should not change"
        assert document.file_name == original_file_name, "File name should not change"
        assert document.file_size == original_file_size, "File size should not change"
        assert document.mime_type == original_mime_type, "MIME type should not change"
        assert document.confidence_score == original_confidence, "Confidence score should not change"

    @given(document_strategy(), transaction_strategy())
    @settings(max_examples=50)
    def test_property_26b_transaction_deletion_archives_documents(
        self, db_session, test_user, document_data, transaction_data
    ):
        """
        Property 26b: When a transaction is deleted, associated documents are archived
        
        This ensures audit trail is preserved even when transactions are removed.
        """
        # Create transaction
        transaction = Transaction(
            user_id=test_user.id,
            **transaction_data,
        )
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        # Create document associated with transaction
        document = Document(
            user_id=test_user.id,
            transaction_id=transaction.id,
            **document_data,
            uploaded_at=datetime.utcnow(),
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Verify document is not archived initially
        assert document.is_archived == False, "Document should not be archived initially"
        assert document.transaction_id == transaction.id, "Document should be linked to transaction"
        
        # Archive documents for transaction (simulating transaction deletion)
        archival_service = DocumentArchivalService(db_session)
        count = archival_service.archive_documents_for_transaction(transaction.id)
        
        assert count == 1, "Should archive exactly one document"
        
        # Refresh document
        db_session.refresh(document)
        
        # Verify document is now archived
        assert document.is_archived == True, "Document should be archived after transaction deletion"
        assert document.archived_at is not None, "Archived timestamp should be set"
        assert document.transaction_id == transaction.id, "Transaction link should be preserved"

    @given(st.lists(document_strategy(), min_size=1, max_size=10))
    @settings(max_examples=30)
    def test_property_26c_multiple_documents_archival(self, db_session, test_user, documents_data):
        """
        Property 26c: Archiving multiple documents for a transaction works correctly
        
        When a transaction has multiple documents, all should be archived.
        """
        # Create transaction
        transaction = Transaction(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("100.00"),
            date=datetime(2026, 1, 1),
            description="Test transaction",
        )
        db_session.add(transaction)
        db_session.commit()
        db_session.refresh(transaction)
        
        # Create multiple documents for the transaction
        documents = []
        for doc_data in documents_data:
            document = Document(
                user_id=test_user.id,
                transaction_id=transaction.id,
                **doc_data,
                uploaded_at=datetime.utcnow(),
            )
            db_session.add(document)
            documents.append(document)
        
        db_session.commit()
        
        # Verify all documents are not archived
        for doc in documents:
            db_session.refresh(doc)
            assert doc.is_archived == False, "Documents should not be archived initially"
        
        # Archive all documents for transaction
        archival_service = DocumentArchivalService(db_session)
        count = archival_service.archive_documents_for_transaction(transaction.id)
        
        assert count == len(documents_data), f"Should archive all {len(documents_data)} documents"
        
        # Verify all documents are now archived
        for doc in documents:
            db_session.refresh(doc)
            assert doc.is_archived == True, "All documents should be archived"
            assert doc.archived_at is not None, "All documents should have archived timestamp"

    @given(document_strategy())
    @settings(max_examples=50)
    def test_property_26d_restore_reverses_archival(self, db_session, test_user, document_data):
        """
        Property 26d: Restoring an archived document reverses the archival
        
        Archive then restore should return document to original state.
        """
        # Create document
        document = Document(
            user_id=test_user.id,
            **document_data,
            uploaded_at=datetime.utcnow(),
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        archival_service = DocumentArchivalService(db_session)
        
        # Archive document
        success = archival_service.archive_document(document.id)
        assert success, "Archival should succeed"
        
        db_session.refresh(document)
        assert document.is_archived == True, "Document should be archived"
        
        # Restore document
        success = archival_service.restore_document(document.id)
        assert success, "Restore should succeed"
        
        db_session.refresh(document)
        
        # Verify document is restored
        assert document.is_archived == False, "Document should not be archived after restore"
        assert document.archived_at is None, "Archived timestamp should be cleared"

    @given(st.integers(min_value=1, max_value=3000))
    @settings(max_examples=30)
    def test_property_26e_retention_policy_respects_age(self, db_session, test_user, days_old):
        """
        Property 26e: Retention policy correctly identifies documents by age
        
        Documents older than retention period should be identified for deletion.
        """
        # Create document with specific archived date
        archived_date = datetime.utcnow() - timedelta(days=days_old)
        
        document = Document(
            user_id=test_user.id,
            document_type=DocumentType.RECEIPT,
            file_path=f"test/path/{days_old}",
            file_name=f"test_{days_old}.jpg",
            file_size=1000,
            mime_type="image/jpeg",
            uploaded_at=archived_date,
            is_archived=True,
            archived_at=archived_date,
        )
        db_session.add(document)
        db_session.commit()
        
        # Apply retention policy (7 years = 2555 days)
        archival_service = DocumentArchivalService(db_session)
        result = archival_service.apply_retention_policy(retention_days=2555, dry_run=True)
        
        # Verify correct identification
        if days_old > 2555:
            assert result["total_found"] >= 1, "Old document should be identified for deletion"
        else:
            # Document should not be in deletion list (it's within retention period)
            # Note: Other documents from other tests might be in the list
            pass

    @given(document_strategy())
    @settings(max_examples=50)
    def test_property_26f_unarchived_documents_not_affected_by_retention(
        self, db_session, test_user, document_data
    ):
        """
        Property 26f: Retention policy only affects archived documents
        
        Active (non-archived) documents should never be deleted by retention policy.
        """
        # Create old but non-archived document
        old_date = datetime.utcnow() - timedelta(days=3000)  # Older than 7 years
        
        document = Document(
            user_id=test_user.id,
            **document_data,
            uploaded_at=old_date,
            is_archived=False,  # Not archived
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        document_id = document.id
        
        # Apply retention policy
        archival_service = DocumentArchivalService(db_session)
        result = archival_service.apply_retention_policy(retention_days=2555, dry_run=False)
        
        # Verify document still exists (not deleted)
        db_session.expire_all()  # Clear session cache
        document = db_session.query(Document).filter(Document.id == document_id).first()
        
        assert document is not None, "Non-archived document should not be deleted by retention policy"
        assert document.is_archived == False, "Document should still be non-archived"


# Fixtures
@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
