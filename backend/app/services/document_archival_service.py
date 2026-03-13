"""Document archival and retention service"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.models.document import Document
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)


class DocumentArchivalService:
    """Service for managing document archival and retention policies"""

    def __init__(self, db: Session):
        self.db = db

    def archive_document(self, document_id: int) -> bool:
        """
        Mark a document as archived
        
        Args:
            document_id: ID of document to archive
            
        Returns:
            True if successful, False otherwise
        """
        try:
            document = self.db.query(Document).filter(Document.id == document_id).first()
            
            if not document:
                logger.warning(f"Document {document_id} not found")
                return False
            
            document.is_archived = True
            document.archived_at = datetime.utcnow()
            
            self.db.commit()
            logger.info(f"Archived document {document_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to archive document {document_id}: {e}")
            return False

    def archive_documents_for_transaction(self, transaction_id: int) -> int:
        """
        Archive all documents associated with a transaction
        
        This is called when a transaction is deleted to preserve
        the document trail for audit purposes.
        
        Args:
            transaction_id: ID of transaction
            
        Returns:
            Number of documents archived
        """
        try:
            documents = (
                self.db.query(Document)
                .filter(Document.transaction_id == transaction_id)
                .filter(Document.is_archived == False)
                .all()
            )
            
            count = 0
            for document in documents:
                document.is_archived = True
                document.archived_at = datetime.utcnow()
                count += 1
            
            self.db.commit()
            logger.info(f"Archived {count} documents for transaction {transaction_id}")
            return count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to archive documents for transaction {transaction_id}: {e}")
            return 0

    def get_archived_documents(
        self, user_id: int, limit: Optional[int] = None
    ) -> List[Document]:
        """
        Get all archived documents for a user
        
        Args:
            user_id: User ID
            limit: Optional limit on number of results
            
        Returns:
            List of archived documents
        """
        query = (
            self.db.query(Document)
            .filter(Document.user_id == user_id)
            .filter(Document.is_archived == True)
            .order_by(Document.archived_at.desc())
        )
        
        if limit:
            query = query.limit(limit)
        
        return query.all()

    def apply_retention_policy(
        self, retention_days: int = 2555, dry_run: bool = True
    ) -> dict:
        """
        Apply retention policy to old archived documents
        
        Austrian tax law requires keeping documents for 7 years (2555 days).
        This method identifies documents that can be permanently deleted.
        
        Args:
            retention_days: Number of days to retain documents (default 7 years)
            dry_run: If True, only report what would be deleted without deleting
            
        Returns:
            Dictionary with deletion statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Find old archived documents
        old_documents = (
            self.db.query(Document)
            .filter(Document.is_archived == True)
            .filter(Document.archived_at < cutoff_date)
            .all()
        )
        
        result = {
            "total_found": len(old_documents),
            "deleted": 0,
            "dry_run": dry_run,
            "cutoff_date": cutoff_date.isoformat(),
        }
        
        if not dry_run:
            # Actually delete the documents
            from app.services.storage_service import StorageService
            storage = StorageService()
            
            for document in old_documents:
                try:
                    # Delete from storage
                    storage.delete_file(document.file_path)
                    
                    # Delete from database
                    self.db.delete(document)
                    result["deleted"] += 1
                    
                except Exception as e:
                    logger.error(f"Failed to delete document {document.id}: {e}")
            
            self.db.commit()
            logger.info(f"Deleted {result['deleted']} old documents")
        else:
            logger.info(
                f"Dry run: Would delete {result['total_found']} documents "
                f"older than {cutoff_date}"
            )
        
        return result

    def restore_document(self, document_id: int) -> bool:
        """
        Restore an archived document
        
        Args:
            document_id: ID of document to restore
            
        Returns:
            True if successful, False otherwise
        """
        try:
            document = self.db.query(Document).filter(Document.id == document_id).first()
            
            if not document:
                logger.warning(f"Document {document_id} not found")
                return False
            
            document.is_archived = False
            document.archived_at = None
            
            self.db.commit()
            logger.info(f"Restored document {document_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to restore document {document_id}: {e}")
            return False

    def get_retention_statistics(self, user_id: Optional[int] = None) -> dict:
        """
        Get statistics about document retention
        
        Args:
            user_id: Optional user ID to filter by
            
        Returns:
            Dictionary with retention statistics
        """
        query = self.db.query(Document)
        
        if user_id:
            query = query.filter(Document.user_id == user_id)
        
        total_documents = query.count()
        archived_documents = query.filter(Document.is_archived == True).count()
        active_documents = total_documents - archived_documents
        
        # Documents older than 7 years
        cutoff_date = datetime.utcnow() - timedelta(days=2555)
        old_archived = (
            query.filter(Document.is_archived == True)
            .filter(Document.archived_at < cutoff_date)
            .count()
        )
        
        return {
            "total_documents": total_documents,
            "active_documents": active_documents,
            "archived_documents": archived_documents,
            "old_archived_documents": old_archived,
            "retention_period_days": 2555,
        }
