"""
Year Archival Service

Handles end-of-year archival processes including:
- Generating final reports for all users
- Moving old documents to archive storage
- Marking transactions as archived
"""

from decimal import Decimal
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user import User
from app.models.transaction import Transaction
from app.models.document import Document, DocumentStatus
from app.models.tax_report import TaxReport, ReportType
from app.services.tax_calculation_engine import TaxCalculationEngine
from app.services.pdf_generator import PDFGenerator
from app.services.finanzonline_xml_generator import FinanzOnlineXMLGenerator
from app.services.document_archival_service import DocumentArchivalService


class YearArchivalService:
    """Service for archiving completed tax years"""
    
    def __init__(self, db: Session):
        self.db = db
        self.tax_engine = TaxCalculationEngine(db)
        self.pdf_generator = PDFGenerator()
        self.xml_generator = FinanzOnlineXMLGenerator()
        self.doc_archival = DocumentArchivalService(db)
    
    def archive_year(
        self,
        tax_year: int,
        generate_reports: bool = True,
        archive_documents: bool = True,
        mark_transactions: bool = True
    ) -> Dict[str, Any]:
        """
        Archive a completed tax year.
        
        Args:
            tax_year: Year to archive
            generate_reports: Whether to generate final reports
            archive_documents: Whether to move documents to archive storage
            mark_transactions: Whether to mark transactions as archived
            
        Returns:
            Summary of archival process
        """
        summary = {
            'tax_year': tax_year,
            'started_at': datetime.utcnow().isoformat(),
            'users_processed': 0,
            'reports_generated': 0,
            'documents_archived': 0,
            'transactions_marked': 0,
            'errors': []
        }
        
        # Get all active users
        users = self.db.query(User).filter(User.is_active == True).all()
        
        for user in users:
            try:
                # Generate final reports
                if generate_reports:
                    self._generate_final_reports(user, tax_year)
                    summary['reports_generated'] += 1
                
                # Archive documents
                if archive_documents:
                    archived_count = self._archive_user_documents(user.id, tax_year)
                    summary['documents_archived'] += archived_count
                
                # Mark transactions as archived
                if mark_transactions:
                    marked_count = self._mark_transactions_archived(user.id, tax_year)
                    summary['transactions_marked'] += marked_count
                
                summary['users_processed'] += 1
                
            except Exception as e:
                summary['errors'].append({
                    'user_id': user.id,
                    'user_email': user.email,
                    'error': str(e)
                })
        
        summary['completed_at'] = datetime.utcnow().isoformat()
        
        return summary
    
    def _generate_final_reports(self, user: User, tax_year: int):
        """Generate final tax reports for a user"""
        # Check if report already exists
        existing_report = self.db.query(TaxReport).filter(
            and_(
                TaxReport.user_id == user.id,
                TaxReport.tax_year == tax_year,
                TaxReport.report_type == ReportType.ANNUAL
            )
        ).first()
        
        if existing_report:
            # Report already exists, skip
            return
        
        # Calculate taxes
        tax_result = self.tax_engine.calculate_all_taxes(
            user_id=user.id,
            tax_year=tax_year
        )
        
        # Get all transactions for the year
        transactions = self.db.query(Transaction).filter(
            and_(
                Transaction.user_id == user.id,
                Transaction.tax_year == tax_year
            )
        ).all()
        
        # Generate PDF report
        pdf_content = self.pdf_generator.generate_annual_report(
            user=user,
            tax_year=tax_year,
            tax_result=tax_result,
            transactions=transactions
        )
        
        # Generate XML for FinanzOnline
        xml_content = self.xml_generator.generate_xml(
            user=user,
            tax_year=tax_year,
            tax_result=tax_result,
            transactions=transactions
        )
        
        # Create tax report record
        report = TaxReport(
            user_id=user.id,
            tax_year=tax_year,
            report_type=ReportType.ANNUAL,
            total_income=tax_result.total_income,
            total_expenses=tax_result.total_expenses,
            total_deductions=tax_result.total_deductions,
            taxable_income=tax_result.taxable_income,
            income_tax=tax_result.income_tax,
            vat_liability=tax_result.vat_liability,
            svs_contributions=tax_result.svs_contributions,
            total_tax=tax_result.total_tax,
            net_income=tax_result.net_income,
            pdf_path=f"reports/{user.id}/{tax_year}/annual_report.pdf",
            xml_path=f"reports/{user.id}/{tax_year}/finanzonline.xml",
            generated_at=datetime.utcnow(),
            is_final=True
        )
        
        self.db.add(report)
        self.db.commit()
        
        # Store PDF and XML files (implementation depends on storage backend)
        # This would typically upload to MinIO/S3
        self._store_report_files(
            user_id=user.id,
            tax_year=tax_year,
            pdf_content=pdf_content,
            xml_content=xml_content
        )
    
    def _archive_user_documents(self, user_id: int, tax_year: int) -> int:
        """
        Move user's documents for a year to archive storage.
        
        Returns:
            Number of documents archived
        """
        # Get all documents for the year
        documents = self.db.query(Document).join(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.tax_year == tax_year,
                Document.status != DocumentStatus.ARCHIVED
            )
        ).all()
        
        archived_count = 0
        
        for document in documents:
            try:
                # Move to archive storage
                self.doc_archival.archive_document(document.id)
                archived_count += 1
            except Exception as e:
                # Log error but continue with other documents
                print(f"Error archiving document {document.id}: {e}")
        
        return archived_count
    
    def _mark_transactions_archived(self, user_id: int, tax_year: int) -> int:
        """
        Mark transactions as archived for a year.
        
        Returns:
            Number of transactions marked
        """
        result = self.db.query(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.tax_year == tax_year,
                Transaction.is_archived == False
            )
        ).update({
            'is_archived': True,
            'archived_at': datetime.utcnow()
        })
        
        self.db.commit()
        
        return result
    
    def _store_report_files(
        self,
        user_id: int,
        tax_year: int,
        pdf_content: bytes,
        xml_content: str
    ):
        """
        Store report files to storage backend.
        
        This is a placeholder - actual implementation would use MinIO/S3.
        """
        # TODO: Implement actual file storage
        # Example:
        # minio_client.put_object(
        #     bucket_name='tax-reports',
        #     object_name=f'{user_id}/{tax_year}/annual_report.pdf',
        #     data=io.BytesIO(pdf_content),
        #     length=len(pdf_content)
        # )
        pass
    
    def get_archival_status(self, tax_year: int) -> Dict[str, Any]:
        """
        Get archival status for a year.
        
        Returns:
            Summary of archival status
        """
        total_users = self.db.query(User).filter(User.is_active == True).count()
        
        # Count users with final reports
        users_with_reports = self.db.query(TaxReport).filter(
            and_(
                TaxReport.tax_year == tax_year,
                TaxReport.is_final == True
            )
        ).count()
        
        # Count archived transactions
        archived_transactions = self.db.query(Transaction).filter(
            and_(
                Transaction.tax_year == tax_year,
                Transaction.is_archived == True
            )
        ).count()
        
        # Count archived documents
        archived_documents = self.db.query(Document).join(Transaction).filter(
            and_(
                Transaction.tax_year == tax_year,
                Document.status == DocumentStatus.ARCHIVED
            )
        ).count()
        
        return {
            'tax_year': tax_year,
            'total_users': total_users,
            'users_with_final_reports': users_with_reports,
            'archived_transactions': archived_transactions,
            'archived_documents': archived_documents,
            'completion_percentage': (users_with_reports / total_users * 100) if total_users > 0 else 0
        }
    
    def unarchive_year(self, tax_year: int) -> Dict[str, Any]:
        """
        Unarchive a year (reverse archival process).
        
        This might be needed if corrections are required after archival.
        """
        # Unmark transactions
        transactions_updated = self.db.query(Transaction).filter(
            and_(
                Transaction.tax_year == tax_year,
                Transaction.is_archived == True
            )
        ).update({
            'is_archived': False,
            'archived_at': None
        })
        
        # Unarchive documents
        documents = self.db.query(Document).join(Transaction).filter(
            and_(
                Transaction.tax_year == tax_year,
                Document.status == DocumentStatus.ARCHIVED
            )
        ).all()
        
        documents_updated = 0
        for document in documents:
            document.status = DocumentStatus.PROCESSED
            documents_updated += 1
        
        self.db.commit()
        
        return {
            'tax_year': tax_year,
            'transactions_unarchived': transactions_updated,
            'documents_unarchived': documents_updated
        }
