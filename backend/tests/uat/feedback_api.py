"""
API endpoints for UAT feedback collection.

Provides endpoints for:
- Submitting feedback
- Tracking usage metrics
- Viewing feedback summaries
- Monitoring UAT progress
"""

from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from .feedback_form import (
    UATFeedback,
    UATMetrics,
    FeedbackCreate,
    FeedbackResponse,
    MetricCreate,
    MetricResponse,
    FeedbackSummary,
    UATProgress,
    FeedbackCategory,
    FeedbackSeverity,
    TestScenario,
)


router = APIRouter(prefix="/api/v1/uat", tags=["UAT Feedback"])


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    feedback: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Submit UAT feedback.
    
    Can be submitted anonymously (no authentication required) or with user context.
    """
    db_feedback = UATFeedback(
        user_id=current_user.id if current_user else None,
        test_scenario=feedback.test_scenario,
        category=feedback.category,
        rating=feedback.rating,
        comment=feedback.comment,
        severity=feedback.severity,
        steps_to_reproduce=feedback.steps_to_reproduce,
        expected_result=feedback.expected_result,
        actual_result=feedback.actual_result,
        browser_info=feedback.browser_info,
    )
    
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    
    return db_feedback


@router.post("/metrics", response_model=MetricResponse, status_code=status.HTTP_201_CREATED)
def track_metric(
    metric: MetricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Track UAT usage metrics.
    
    Records user actions, completion times, and success rates.
    """
    db_metric = UATMetrics(
        user_id=current_user.id,
        test_scenario=metric.test_scenario,
        action=metric.action,
        duration_seconds=metric.duration_seconds,
        success=metric.success,
        error_message=metric.error_message,
    )
    
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    
    return db_metric


@router.get("/feedback", response_model=List[FeedbackResponse])
def list_feedback(
    test_scenario: Optional[TestScenario] = None,
    category: Optional[FeedbackCategory] = None,
    severity: Optional[FeedbackSeverity] = None,
    resolved: Optional[bool] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    List all UAT feedback with optional filters.
    
    Admin endpoint for reviewing feedback.
    """
    query = db.query(UATFeedback)
    
    if test_scenario:
        query = query.filter(UATFeedback.test_scenario == test_scenario)
    
    if category:
        query = query.filter(UATFeedback.category == category)
    
    if severity:
        query = query.filter(UATFeedback.severity == severity)
    
    if resolved is not None:
        query = query.filter(UATFeedback.resolved == resolved)
    
    query = query.order_by(UATFeedback.created_at.desc()).limit(limit)
    
    return query.all()


@router.get("/feedback/summary", response_model=FeedbackSummary)
def get_feedback_summary(
    db: Session = Depends(get_db),
):
    """
    Get aggregated feedback summary.
    
    Provides overview of all UAT feedback for analysis.
    """
    # Total feedback count
    total_feedback = db.query(func.count(UATFeedback.id)).scalar()
    
    # Average rating (excluding null ratings)
    avg_rating = db.query(func.avg(UATFeedback.rating)).filter(
        UATFeedback.rating.isnot(None)
    ).scalar() or 0.0
    
    # Feedback by category
    feedback_by_category = {}
    category_counts = db.query(
        UATFeedback.category,
        func.count(UATFeedback.id)
    ).group_by(UATFeedback.category).all()
    
    for category, count in category_counts:
        feedback_by_category[category.value] = count
    
    # Feedback by scenario
    feedback_by_scenario = {}
    scenario_counts = db.query(
        UATFeedback.test_scenario,
        func.count(UATFeedback.id)
    ).group_by(UATFeedback.test_scenario).all()
    
    for scenario, count in scenario_counts:
        feedback_by_scenario[scenario.value] = count
    
    # Bug count by severity
    bug_count_by_severity = {}
    bug_counts = db.query(
        UATFeedback.severity,
        func.count(UATFeedback.id)
    ).filter(
        UATFeedback.category == FeedbackCategory.BUG_REPORT
    ).group_by(UATFeedback.severity).all()
    
    for severity, count in bug_counts:
        if severity:
            bug_count_by_severity[severity.value] = count
    
    # Top issues (most common comments)
    top_issues = []
    bug_reports = db.query(UATFeedback.comment).filter(
        UATFeedback.category == FeedbackCategory.BUG_REPORT,
        UATFeedback.comment.isnot(None)
    ).limit(10).all()
    
    top_issues = [report[0][:100] for report in bug_reports if report[0]]
    
    return FeedbackSummary(
        total_feedback=total_feedback,
        average_rating=round(float(avg_rating), 2),
        feedback_by_category=feedback_by_category,
        feedback_by_scenario=feedback_by_scenario,
        bug_count_by_severity=bug_count_by_severity,
        top_issues=top_issues,
    )


@router.get("/progress", response_model=UATProgress)
def get_uat_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get UAT progress for current user.
    
    Shows which scenarios completed, time spent, and feedback submitted.
    """
    # Get completed scenarios
    completed_scenarios = db.query(UATMetrics.test_scenario).filter(
        UATMetrics.user_id == current_user.id,
        UATMetrics.success == True
    ).distinct().all()
    
    scenarios_completed = [scenario[0] for scenario in completed_scenarios]
    
    # Calculate completion percentage
    total_scenarios = len(TestScenario)
    completion_percentage = (len(scenarios_completed) / total_scenarios) * 100
    
    # Total time spent
    total_time = db.query(func.sum(UATMetrics.duration_seconds)).filter(
        UATMetrics.user_id == current_user.id
    ).scalar() or 0.0
    
    total_time_minutes = total_time / 60
    
    # Feedback submitted
    feedback_count = db.query(func.count(UATFeedback.id)).filter(
        UATFeedback.user_id == current_user.id
    ).scalar()
    
    # Bugs reported
    bug_count = db.query(func.count(UATFeedback.id)).filter(
        UATFeedback.user_id == current_user.id,
        UATFeedback.category == FeedbackCategory.BUG_REPORT
    ).scalar()
    
    return UATProgress(
        user_id=current_user.id,
        scenarios_completed=scenarios_completed,
        completion_percentage=round(completion_percentage, 1),
        total_time_spent_minutes=round(total_time_minutes, 1),
        feedback_submitted=feedback_count,
        bugs_reported=bug_count,
    )


@router.patch("/feedback/{feedback_id}/resolve")
def resolve_feedback(
    feedback_id: int,
    resolution_notes: str,
    db: Session = Depends(get_db),
):
    """
    Mark feedback as resolved.
    
    Admin endpoint for tracking feedback resolution.
    """
    feedback = db.query(UATFeedback).filter(UATFeedback.id == feedback_id).first()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found"
        )
    
    feedback.resolved = True
    feedback.resolution_notes = resolution_notes
    
    db.commit()
    db.refresh(feedback)
    
    return {"message": "Feedback marked as resolved", "feedback_id": feedback_id}


@router.get("/metrics/summary")
def get_metrics_summary(
    db: Session = Depends(get_db),
):
    """
    Get aggregated usage metrics summary.
    
    Provides insights into task completion rates, average times, and error rates.
    """
    # Task completion rate
    total_actions = db.query(func.count(UATMetrics.id)).scalar()
    successful_actions = db.query(func.count(UATMetrics.id)).filter(
        UATMetrics.success == True
    ).scalar()
    
    completion_rate = (successful_actions / total_actions * 100) if total_actions > 0 else 0
    
    # Average time by scenario
    avg_time_by_scenario = {}
    scenario_times = db.query(
        UATMetrics.test_scenario,
        func.avg(UATMetrics.duration_seconds)
    ).filter(
        UATMetrics.duration_seconds.isnot(None)
    ).group_by(UATMetrics.test_scenario).all()
    
    for scenario, avg_time in scenario_times:
        avg_time_by_scenario[scenario.value] = round(float(avg_time or 0), 2)
    
    # Error rate by scenario
    error_rate_by_scenario = {}
    scenario_errors = db.query(
        UATMetrics.test_scenario,
        func.count(UATMetrics.id).filter(UATMetrics.success == False),
        func.count(UATMetrics.id)
    ).group_by(UATMetrics.test_scenario).all()
    
    for scenario, error_count, total_count in scenario_errors:
        error_rate = (error_count / total_count * 100) if total_count > 0 else 0
        error_rate_by_scenario[scenario.value] = round(error_rate, 2)
    
    # Unique users
    unique_users = db.query(func.count(func.distinct(UATMetrics.user_id))).scalar()
    
    return {
        "total_actions": total_actions,
        "completion_rate": round(completion_rate, 2),
        "unique_users": unique_users,
        "avg_time_by_scenario_seconds": avg_time_by_scenario,
        "error_rate_by_scenario_percent": error_rate_by_scenario,
    }
