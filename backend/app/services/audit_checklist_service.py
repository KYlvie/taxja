"""
Audit Checklist Service

Generates comprehensive audit readiness checklists for tax compliance.
Validates that all transactions have supporting documents, deductions are properly
documented, and VAT calculations are correct.

Requirements: 32.1, 32.2, 32.3, 32.4, 32.5, 32.6
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.transaction import Transaction, TransactionType
from app.models.document import Document
from app.models.user import User, UserType
from app.models.tax_report import TaxReport
from app.services.vat_calculator import VATCalculator
from app.services.deductibility_checker import DeductibilityChecker


class AuditIssue:
    """Represents an audit compliance issue"""
    
    def __init__(
        self,
        severity: str,  # 'critical', 'warning', 'info'
        category: str,
        title: str,
        description: str,
        affected_items: List[Dict] = None,
        recommendation: str = None
    ):
        self.severity = severity
        self.category = category
        self.title = title
        self.description = description
        self.affected_items = affected_items or []
        self.recommendation = recommendation


class AuditChecklistResult:
    """Result of audit checklist generation"""
    
    def __init__(self):
        self.issues: List[AuditIssue] = []
        self.summary: Dict = {}
        self.compliance_score: float = 0.0
        self.is_audit_ready: bool = False
    
    def add_issue(self, issue: AuditIssue):
        """Add an issue to the checklist"""
        self.issues.append(issue)
    
    def calculate_compliance_score(self):
        """Calculate overall compliance score (0-100)"""
        if not self.issues:
            self.compliance_score = 100.0
            self.is_audit_ready = True
            return
        
        # Weight issues by severity
        critical_count = sum(1 for i in self.issues if i.severity == 'critical')
        warning_count = sum(1 for i in self.issues if i.severity == 'warning')
        info_count = sum(1 for i in self.issues if i.severity == 'info')
        
        # Critical issues have highest impact
        total_penalty = (critical_count * 20) + (warning_count * 5) + (info_count * 1)
        self.compliance_score = max(0.0, 100.0 - total_penalty)
        
        # Audit ready if no critical issues and score > 80
        self.is_audit_ready = critical_count == 0 and self.compliance_score >= 80.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            'compliance_score': round(self.compliance_score, 2),
            'is_audit_ready': self.is_audit_ready,
            'summary': self.summary,
            'issues': [
                {
                    'severity': issue.severity,
                    'category': issue.category,
                    'title': issue.title,
                    'description': issue.description,
                    'affected_items': issue.affected_items,
                    'recommendation': issue.recommendation
                }
                for issue in self.issues
            ]
        }


class AuditChecklistService:
    """Service for generating audit readiness checklists"""
    
    def __init__(self, db: Session):
        self.db = db
        self.vat_calculator = VATCalculator()
        self.deductibility_checker = DeductibilityChecker()
    
    def generate_checklist(
        self,
        user_id: int,
        tax_year: int
    ) -> AuditChecklistResult:
        """
        Generate comprehensive audit checklist for a user and tax year
        
        Args:
            user_id: User ID
            tax_year: Tax year to audit
            
        Returns:
            AuditChecklistResult with all issues and compliance score
        """
        result = AuditChecklistResult()
        
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Get all transactions for the tax year
        transactions = self.db.query(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                func.extract('year', Transaction.date) == tax_year
            )
        ).all()
        
        # Run all checks
        self._check_missing_documents(result, transactions)
        self._check_deduction_documentation(result, transactions, user)
        self._check_vat_calculations(result, transactions, user, tax_year)
        self._check_transaction_completeness(result, transactions)
        self._check_duplicate_transactions(result, transactions)
        self._check_tax_report_exists(result, user_id, tax_year)
        
        # Calculate summary statistics
        result.summary = self._calculate_summary(transactions, user, tax_year)
        
        # Calculate compliance score
        result.calculate_compliance_score()
        
        return result
    
    def _check_missing_documents(
        self,
        result: AuditChecklistResult,
        transactions: List[Transaction]
    ):
        """Check that all transactions have supporting documents"""
        missing_docs = []
        
        for txn in transactions:
            # Check if transaction has a linked document
            if not txn.document_id:
                missing_docs.append({
                    'transaction_id': txn.id,
                    'date': txn.date.isoformat(),
                    'amount': float(txn.amount),
                    'description': txn.description,
                    'type': txn.type.value
                })
        
        if missing_docs:
            result.add_issue(AuditIssue(
                severity='critical' if len(missing_docs) > 10 else 'warning',
                category='documentation',
                title='Missing Supporting Documents',
                description=f'{len(missing_docs)} transaction(s) do not have supporting documents attached.',
                affected_items=missing_docs[:10],  # Limit to first 10
                recommendation='Upload receipts, invoices, or other proof for all transactions. '
                              'This is critical for tax audit compliance.'
            ))
    
    def _check_deduction_documentation(
        self,
        result: AuditChecklistResult,
        transactions: List[Transaction],
        user: User
    ):
        """Check that all deductions are properly documented"""
        undocumented_deductions = []
        
        for txn in transactions:
            if txn.type == TransactionType.EXPENSE and txn.is_deductible:
                # Check if deduction is valid for user type
                is_valid, reason = self.deductibility_checker.is_deductible(
                    txn.expense_category,
                    user.user_type
                )
                
                if not is_valid:
                    undocumented_deductions.append({
                        'transaction_id': txn.id,
                        'date': txn.date.isoformat(),
                        'amount': float(txn.amount),
                        'category': txn.expense_category.value if txn.expense_category else 'unknown',
                        'reason': reason
                    })
                
                # Check if high-value deduction has document
                if txn.amount > Decimal('500.00') and not txn.document_id:
                    undocumented_deductions.append({
                        'transaction_id': txn.id,
                        'date': txn.date.isoformat(),
                        'amount': float(txn.amount),
                        'category': txn.expense_category.value if txn.expense_category else 'unknown',
                        'reason': 'High-value deduction (>€500) requires supporting document'
                    })
        
        if undocumented_deductions:
            result.add_issue(AuditIssue(
                severity='critical',
                category='deductions',
                title='Improperly Documented Deductions',
                description=f'{len(undocumented_deductions)} deduction(s) may not be valid or lack proper documentation.',
                affected_items=undocumented_deductions[:10],
                recommendation='Ensure all deductions are valid for your taxpayer type and have supporting documents. '
                              'High-value deductions (>€500) must have receipts or invoices.'
            ))
    
    def _check_vat_calculations(
        self,
        result: AuditChecklistResult,
        transactions: List[Transaction],
        user: User,
        tax_year: int
    ):
        """Check that VAT calculations are correct"""
        vat_issues = []
        
        # Only check VAT for self-employed and business owners
        if user.user_type not in [UserType.SELF_EMPLOYED, UserType.LANDLORD]:
            return
        
        # Calculate gross turnover
        gross_turnover = sum(
            txn.amount for txn in transactions
            if txn.type == TransactionType.INCOME
        )
        
        # Check if VAT registration is required
        if gross_turnover > Decimal('55000.00'):
            # Check that VAT is being tracked
            income_with_vat = [
                txn for txn in transactions
                if txn.type == TransactionType.INCOME and txn.vat_amount is not None
            ]
            
            if len(income_with_vat) == 0:
                vat_issues.append({
                    'issue': 'vat_not_tracked',
                    'description': f'Gross turnover €{gross_turnover:,.2f} exceeds €55,000 threshold, '
                                  'but VAT is not being tracked on income transactions.',
                    'recommendation': 'Add VAT amounts to all income transactions.'
                })
            
            # Check for missing VAT on expenses
            expense_with_vat = [
                txn for txn in transactions
                if txn.type == TransactionType.EXPENSE and txn.vat_amount is not None
            ]
            
            if len(expense_with_vat) == 0:
                vat_issues.append({
                    'issue': 'input_vat_not_tracked',
                    'description': 'Input VAT is not being tracked on expense transactions.',
                    'recommendation': 'Track input VAT on all business expenses to maximize deductions.'
                })
        
        # Check for inconsistent VAT rates
        for txn in transactions:
            if txn.vat_amount and txn.vat_rate:
                # Calculate expected VAT
                expected_vat = txn.amount * txn.vat_rate / (Decimal('1') + txn.vat_rate)
                actual_vat = txn.vat_amount
                
                # Allow 1 cent tolerance
                if abs(expected_vat - actual_vat) > Decimal('0.01'):
                    vat_issues.append({
                        'transaction_id': txn.id,
                        'date': txn.date.isoformat(),
                        'amount': float(txn.amount),
                        'expected_vat': float(expected_vat),
                        'actual_vat': float(actual_vat),
                        'difference': float(abs(expected_vat - actual_vat))
                    })
        
        if vat_issues:
            result.add_issue(AuditIssue(
                severity='critical',
                category='vat',
                title='VAT Calculation Issues',
                description=f'{len(vat_issues)} VAT-related issue(s) detected.',
                affected_items=vat_issues[:10],
                recommendation='Review and correct VAT calculations. Ensure all income and expenses '
                              'have correct VAT rates and amounts.'
            ))
    
    def _check_transaction_completeness(
        self,
        result: AuditChecklistResult,
        transactions: List[Transaction]
    ):
        """Check that all transactions have complete information"""
        incomplete_transactions = []
        
        for txn in transactions:
            issues = []
            
            if not txn.description or len(txn.description.strip()) < 3:
                issues.append('Missing or insufficient description')
            
            if txn.type == TransactionType.INCOME and not txn.income_category:
                issues.append('Missing income category')
            
            if txn.type == TransactionType.EXPENSE and not txn.expense_category:
                issues.append('Missing expense category')
            
            if issues:
                incomplete_transactions.append({
                    'transaction_id': txn.id,
                    'date': txn.date.isoformat(),
                    'amount': float(txn.amount),
                    'issues': issues
                })
        
        if incomplete_transactions:
            result.add_issue(AuditIssue(
                severity='warning',
                category='data_quality',
                title='Incomplete Transaction Information',
                description=f'{len(incomplete_transactions)} transaction(s) have incomplete information.',
                affected_items=incomplete_transactions[:10],
                recommendation='Complete all transaction details including descriptions and categories.'
            ))
    
    def _check_duplicate_transactions(
        self,
        result: AuditChecklistResult,
        transactions: List[Transaction]
    ):
        """Check for potential duplicate transactions"""
        # Group by date and amount
        from collections import defaultdict
        groups = defaultdict(list)
        
        for txn in transactions:
            key = (txn.date, txn.amount, txn.type)
            groups[key].append(txn)
        
        duplicates = []
        for key, txns in groups.items():
            if len(txns) > 1:
                duplicates.append({
                    'date': key[0].isoformat(),
                    'amount': float(key[1]),
                    'type': key[2].value,
                    'count': len(txns),
                    'transaction_ids': [t.id for t in txns]
                })
        
        if duplicates:
            result.add_issue(AuditIssue(
                severity='warning',
                category='data_quality',
                title='Potential Duplicate Transactions',
                description=f'{len(duplicates)} group(s) of potential duplicate transactions detected.',
                affected_items=duplicates[:10],
                recommendation='Review and remove duplicate transactions to avoid double-counting.'
            ))
    
    def _check_tax_report_exists(
        self,
        result: AuditChecklistResult,
        user_id: int,
        tax_year: int
    ):
        """Check if tax report has been generated"""
        report = self.db.query(TaxReport).filter(
            and_(
                TaxReport.user_id == user_id,
                TaxReport.tax_year == tax_year
            )
        ).first()
        
        if not report:
            result.add_issue(AuditIssue(
                severity='info',
                category='reporting',
                title='Tax Report Not Generated',
                description=f'No tax report has been generated for {tax_year}.',
                recommendation='Generate a tax report to review your tax calculations and prepare for filing.'
            ))
    
    def _calculate_summary(
        self,
        transactions: List[Transaction],
        user: User,
        tax_year: int
    ) -> Dict:
        """Calculate summary statistics for the audit"""
        total_transactions = len(transactions)
        transactions_with_docs = sum(1 for t in transactions if t.document_id)
        
        total_income = sum(
            t.amount for t in transactions if t.type == TransactionType.INCOME
        )
        total_expenses = sum(
            t.amount for t in transactions if t.type == TransactionType.EXPENSE
        )
        deductible_expenses = sum(
            t.amount for t in transactions
            if t.type == TransactionType.EXPENSE and t.is_deductible
        )
        
        return {
            'tax_year': tax_year,
            'user_type': user.user_type.value,
            'total_transactions': total_transactions,
            'transactions_with_documents': transactions_with_docs,
            'documentation_rate': round(
                (transactions_with_docs / total_transactions * 100) if total_transactions > 0 else 0,
                2
            ),
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'deductible_expenses': float(deductible_expenses),
            'net_income': float(total_income - total_expenses)
        }
