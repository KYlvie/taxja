"""
Audit and Compliance API Endpoints

Provides endpoints for audit readiness checks, GDPR data export/deletion,
and audit logging.

Requirements: 17.6, 17.7, 17.8, 17.9, 32.1-32.6
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict

from app.api import deps
from app.models.user import User
from app.services.audit_checklist_service import AuditChecklistService
from app.services.gdpr_service import GDPRService
from app.services.audit_log_service import AuditLogService
from app.services.disclaimer_service import DisclaimerService
from app.schemas.audit import (
    AuditChecklistResponse,
    GDPRExportResponse,
    GDPRDeleteResponse,
    AuditLogQuery,
    AuditLogResponse,
    DisclaimerResponse,
    DisclaimerAcceptanceRequest,
    DisclaimerAcceptanceResponse,
    DisclaimerStatusResponse
)

router = APIRouter()


@router.get("/checklist/{tax_year}", response_model=AuditChecklistResponse)
def get_audit_checklist(
    tax_year: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Generate audit readiness checklist for a specific tax year
    
    Checks:
    - All transactions have supporting documents
    - All deductions are properly documented
    - VAT calculations are correct
    - Transaction data is complete
    - No duplicate transactions
    
    Requirements: 32.1, 32.2, 32.3, 32.4, 32.5, 32.6
    """
    service = AuditChecklistService(db)
    
    try:
        result = service.generate_checklist(current_user.id, tax_year)
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate audit checklist: {str(e)}")


@router.post("/gdpr/export", response_model=GDPRExportResponse)
def export_user_data(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Export all user data (GDPR compliance)
    
    Exports:
    - User profile
    - All transactions
    - All documents
    - All tax reports
    - Audit logs
    
    Creates a ZIP archive with all data in JSON format plus original documents.
    
    Requirements: 17.6, 17.7
    """
    service = GDPRService(db)
    
    try:
        # Start export in background
        export_id = service.initiate_export(current_user.id)
        background_tasks.add_task(service.execute_export, export_id)
        
        return {
            'export_id': export_id,
            'status': 'processing',
            'message': 'Data export initiated. You will receive a download link when ready.'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate data export: {str(e)}")


@router.get("/gdpr/export/{export_id}/status")
def get_export_status(
    export_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Check status of GDPR data export
    
    Requirements: 17.6, 17.7
    """
    service = GDPRService(db)
    
    try:
        status = service.get_export_status(export_id, current_user.id)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get export status: {str(e)}")


@router.delete("/gdpr/delete", response_model=GDPRDeleteResponse)
def delete_user_data(
    confirmation: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Permanently delete all user data (GDPR compliance)
    
    This action is IRREVERSIBLE. All data will be permanently deleted:
    - User account
    - All transactions
    - All documents
    - All tax reports
    - All audit logs
    
    Requires confirmation string: "DELETE_MY_DATA"
    
    Requirements: 17.8
    """
    if confirmation != "DELETE_MY_DATA":
        raise HTTPException(
            status_code=400,
            detail='Confirmation string must be "DELETE_MY_DATA"'
        )
    
    service = GDPRService(db)
    
    try:
        result = service.delete_user_data(current_user.id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user data: {str(e)}")


@router.get("/logs", response_model=AuditLogResponse)
def get_audit_logs(
    query: AuditLogQuery = Depends(),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Query audit logs for current user
    
    Logs include:
    - Login/logout events
    - Transaction create/update/delete
    - Document upload/delete
    - Report generation
    - Settings changes
    
    Requirements: 17.9
    """
    service = AuditLogService(db)
    
    try:
        logs = service.query_logs(
            user_id=current_user.id,
            action_type=query.action_type,
            start_date=query.start_date,
            end_date=query.end_date,
            limit=query.limit,
            offset=query.offset
        )
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query audit logs: {str(e)}")



@router.get("/disclaimer", response_model=DisclaimerResponse)
def get_disclaimer(
    language: str = 'de',
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Get disclaimer text in specified language
    
    Languages: de (German), en (English), zh (Chinese)
    
    Requirements: 17.11
    """
    service = DisclaimerService(db)
    disclaimer = service.get_disclaimer(language)
    disclaimer['language'] = language
    return disclaimer


@router.get("/disclaimer/status", response_model=DisclaimerStatusResponse)
def get_disclaimer_status(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Check if user has accepted current disclaimer
    
    Requirements: 17.11
    """
    service = DisclaimerService(db)
    
    has_accepted = service.has_accepted_disclaimer(current_user.id)
    history = service.get_acceptance_history(current_user.id)
    
    return {
        'has_accepted': has_accepted,
        'current_version': service.DISCLAIMERS['de']['version'],
        'acceptance_history': history
    }


@router.post("/disclaimer/accept", response_model=DisclaimerAcceptanceResponse)
def accept_disclaimer(
    request: DisclaimerAcceptanceRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Record user acceptance of disclaimer
    
    Requirements: 17.11
    """
    service = DisclaimerService(db)
    
    try:
        acceptance = service.record_acceptance(
            user_id=current_user.id,
            language=request.language
        )
        
        return {
            'success': True,
            'message': 'Disclaimer accepted successfully',
            'accepted_at': acceptance.accepted_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record acceptance: {str(e)}")


@router.get("/disclaimer/short")
def get_short_disclaimer(
    language: str = 'de',
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Get short disclaimer text for page footer
    
    Requirements: 17.11
    """
    service = DisclaimerService(db)
    return {
        'text': service.get_short_disclaimer(language),
        'language': language
    }


@router.get("/disclaimer/ai")
def get_ai_disclaimer(
    language: str = 'de',
    db: Session = Depends(deps.get_db)
) -> Dict:
    """
    Get disclaimer text for AI assistant responses
    
    Requirements: 17.11, 38.4
    """
    service = DisclaimerService(db)
    return {
        'text': service.get_ai_disclaimer(language),
        'language': language
    }
