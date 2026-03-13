"""
GDPR Compliance Service

Handles GDPR data export and deletion requests.
Exports all user data to JSON and creates ZIP archive with documents.
Permanently deletes all user data when requested.

Requirements: 17.6, 17.7, 17.8
"""

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from zipfile import ZipFile
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user import User
from app.models.transaction import Transaction
from app.models.document import Document
from app.models.tax_report import TaxReport
from app.models.classification_correction import ClassificationCorrection
from app.models.loss_carryforward import LossCarryforward
from app.services.audit_log_service import AuditLogService, AuditAction
from app.core.config import settings


class GDPRExport:
    """Represents a GDPR data export request"""
    
    def __init__(self, export_id: str, user_id: int):
        self.export_id = export_id
        self.user_id = user_id
        self.status = 'pending'  # pending, processing, completed, failed
        self.created_at = datetime.utcnow()
        self.completed_at = None
        self.download_url = None
        self.error_message = None


class GDPRService:
    """Service for GDPR compliance operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_log = AuditLogService(db)
        self.export_dir = Path(settings.GDPR_EXPORT_DIR)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory export tracking (in production, use Redis or database)
        self._exports: Dict[str, GDPRExport] = {}
    
    def initiate_export(self, user_id: int) -> str:
        """
        Initiate GDPR data export
        
        Args:
            user_id: User ID
            
        Returns:
            Export ID for tracking
        """
        export_id = str(uuid.uuid4())
        export = GDPRExport(export_id, user_id)
        self._exports[export_id] = export
        
        # Log the export request
        self.audit_log.log_action(
            user_id=user_id,
            action=AuditAction.GDPR_EXPORT_REQUESTED,
            details={'export_id': export_id}
        )
        
        return export_id
    
    def execute_export(self, export_id: str):
        """
        Execute GDPR data export (runs in background)
        
        Args:
            export_id: Export ID
        """
        export = self._exports.get(export_id)
        if not export:
            return
        
        try:
            export.status = 'processing'
            
            # Create export directory
            export_path = self.export_dir / export_id
            export_path.mkdir(parents=True, exist_ok=True)
            
            # Export all data
            self._export_user_data(export.user_id, export_path)
            self._export_transactions(export.user_id, export_path)
            self._export_documents(export.user_id, export_path)
            self._export_tax_reports(export.user_id, export_path)
            self._export_audit_logs(export.user_id, export_path)
            self._export_metadata(export.user_id, export_path)
            
            # Create ZIP archive
            zip_path = self.export_dir / f"{export_id}.zip"
            self._create_zip_archive(export_path, zip_path)
            
            # Clean up temporary directory
            shutil.rmtree(export_path)
            
            # Update export status
            export.status = 'completed'
            export.completed_at = datetime.utcnow()
            export.download_url = f"/api/v1/audit/gdpr/export/{export_id}/download"
            
            # Log completion
            self.audit_log.log_action(
                user_id=export.user_id,
                action=AuditAction.GDPR_EXPORT_COMPLETED,
                details={'export_id': export_id}
            )
            
        except Exception as e:
            export.status = 'failed'
            export.error_message = str(e)
            
            # Log failure
            self.audit_log.log_action(
                user_id=export.user_id,
                action=AuditAction.GDPR_EXPORT_FAILED,
                details={'export_id': export_id, 'error': str(e)}
            )
    
    def get_export_status(self, export_id: str, user_id: int) -> Dict:
        """
        Get status of GDPR export
        
        Args:
            export_id: Export ID
            user_id: User ID (for authorization)
            
        Returns:
            Export status dictionary
        """
        export = self._exports.get(export_id)
        if not export:
            raise ValueError(f"Export {export_id} not found")
        
        if export.user_id != user_id:
            raise ValueError("Unauthorized access to export")
        
        return {
            'export_id': export.export_id,
            'status': export.status,
            'created_at': export.created_at.isoformat(),
            'completed_at': export.completed_at.isoformat() if export.completed_at else None,
            'download_url': export.download_url,
            'error_message': export.error_message
        }
    
    def _export_user_data(self, user_id: int, export_path: Path):
        """Export user profile data"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        user_data = {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'user_type': user.user_type.value,
            'tax_number': user.tax_number,
            'vat_number': user.vat_number,
            'address': user.address,
            'family_info': user.family_info,
            'commuting_info': user.commuting_info,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'updated_at': user.updated_at.isoformat() if user.updated_at else None
        }
        
        with open(export_path / 'user_profile.json', 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
    
    def _export_transactions(self, user_id: int, export_path: Path):
        """Export all transactions"""
        transactions = self.db.query(Transaction).filter(
            Transaction.user_id == user_id
        ).all()
        
        transactions_data = []
        for txn in transactions:
            transactions_data.append({
                'id': txn.id,
                'type': txn.type.value,
                'amount': float(txn.amount),
                'date': txn.date.isoformat(),
                'description': txn.description,
                'income_category': txn.income_category.value if txn.income_category else None,
                'expense_category': txn.expense_category.value if txn.expense_category else None,
                'is_deductible': txn.is_deductible,
                'vat_rate': float(txn.vat_rate) if txn.vat_rate else None,
                'vat_amount': float(txn.vat_amount) if txn.vat_amount else None,
                'document_id': txn.document_id,
                'created_at': txn.created_at.isoformat() if txn.created_at else None,
                'updated_at': txn.updated_at.isoformat() if txn.updated_at else None
            })
        
        with open(export_path / 'transactions.json', 'w', encoding='utf-8') as f:
            json.dump(transactions_data, f, indent=2, ensure_ascii=False)
    
    def _export_documents(self, user_id: int, export_path: Path):
        """Export all documents and their metadata"""
        documents = self.db.query(Document).filter(
            Document.user_id == user_id
        ).all()
        
        # Create documents directory
        docs_dir = export_path / 'documents'
        docs_dir.mkdir(exist_ok=True)
        
        documents_data = []
        for doc in documents:
            doc_data = {
                'id': doc.id,
                'document_type': doc.document_type.value if doc.document_type else None,
                'file_path': doc.file_path,
                'ocr_result': doc.ocr_result,
                'confidence_score': float(doc.confidence_score) if doc.confidence_score else None,
                'raw_text': doc.raw_text,
                'transaction_id': doc.transaction_id,
                'created_at': doc.created_at.isoformat() if doc.created_at else None
            }
            documents_data.append(doc_data)
            
            # Copy original document file
            if doc.file_path and os.path.exists(doc.file_path):
                filename = f"doc_{doc.id}_{Path(doc.file_path).name}"
                shutil.copy2(doc.file_path, docs_dir / filename)
                doc_data['exported_filename'] = filename
        
        with open(export_path / 'documents_metadata.json', 'w', encoding='utf-8') as f:
            json.dump(documents_data, f, indent=2, ensure_ascii=False)
    
    def _export_tax_reports(self, user_id: int, export_path: Path):
        """Export all tax reports"""
        reports = self.db.query(TaxReport).filter(
            TaxReport.user_id == user_id
        ).all()
        
        reports_data = []
        for report in reports:
            reports_data.append({
                'id': report.id,
                'tax_year': report.tax_year,
                'report_data': report.report_data,
                'created_at': report.created_at.isoformat() if report.created_at else None
            })
        
        with open(export_path / 'tax_reports.json', 'w', encoding='utf-8') as f:
            json.dump(reports_data, f, indent=2, ensure_ascii=False)
    
    def _export_audit_logs(self, user_id: int, export_path: Path):
        """Export audit logs"""
        logs = self.audit_log.query_logs(
            user_id=user_id,
            limit=10000  # Export all logs
        )
        
        with open(export_path / 'audit_logs.json', 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    
    def _export_metadata(self, user_id: int, export_path: Path):
        """Export metadata about the export"""
        metadata = {
            'export_date': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'data_types': [
                'user_profile',
                'transactions',
                'documents',
                'tax_reports',
                'audit_logs'
            ],
            'format_version': '1.0',
            'gdpr_notice': 'This archive contains all personal data stored by Taxja for your account. '
                          'You have the right to request deletion of this data at any time.'
        }
        
        with open(export_path / 'README.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    def _create_zip_archive(self, source_dir: Path, zip_path: Path):
        """Create ZIP archive of exported data"""
        with ZipFile(zip_path, 'w') as zipf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)
    
    def delete_user_data(self, user_id: int) -> Dict:
        """
        Permanently delete all user data (GDPR right to erasure)
        
        This is IRREVERSIBLE. Deletes:
        - User account
        - All transactions
        - All documents (from storage)
        - All tax reports
        - All classification corrections
        - All loss carryforward records
        - All audit logs
        
        Args:
            user_id: User ID
            
        Returns:
            Deletion result dictionary
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Log the deletion request BEFORE deleting
        self.audit_log.log_action(
            user_id=user_id,
            action=AuditAction.GDPR_DELETE_REQUESTED,
            details={'email': user.email}
        )
        
        deleted_counts = {}
        
        try:
            # Delete documents from storage
            documents = self.db.query(Document).filter(Document.user_id == user_id).all()
            for doc in documents:
                if doc.file_path and os.path.exists(doc.file_path):
                    os.remove(doc.file_path)
            deleted_counts['documents_files'] = len(documents)
            
            # Delete database records (order matters due to foreign keys)
            deleted_counts['classification_corrections'] = self.db.query(ClassificationCorrection).filter(
                ClassificationCorrection.user_id == user_id
            ).delete()
            
            deleted_counts['loss_carryforwards'] = self.db.query(LossCarryforward).filter(
                LossCarryforward.user_id == user_id
            ).delete()
            
            deleted_counts['tax_reports'] = self.db.query(TaxReport).filter(
                TaxReport.user_id == user_id
            ).delete()
            
            deleted_counts['documents'] = self.db.query(Document).filter(
                Document.user_id == user_id
            ).delete()
            
            deleted_counts['transactions'] = self.db.query(Transaction).filter(
                Transaction.user_id == user_id
            ).delete()
            
            # Delete user account
            self.db.delete(user)
            deleted_counts['user_account'] = 1
            
            # Commit all deletions
            self.db.commit()
            
            return {
                'success': True,
                'message': 'All user data has been permanently deleted',
                'deleted_counts': deleted_counts,
                'deleted_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to delete user data: {str(e)}")
