"""
Feedback collection system for Property Management UAT.

This module provides API endpoints and database models for collecting
user feedback during User Acceptance Testing.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.db.base import Base


class FeedbackCategory(str, Enum):
    """Feedback category types"""
    USABILITY = "usability"
    FUNCTIONALITY = "functionality"
    VALUE = "value"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"


class FeedbackSeverity(str, Enum):
    """Bug severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestScenario(str, Enum):
    """UAT test scenarios"""
    PROPERTY_REGISTRATION = "property_registration"
    HISTORICAL_BACKFILL = "historical_backfill"
    TRANSACTION_LINKING = "transaction_linking"
    PROPERTY_METRICS = "property_metrics"
    REPORT_GENERATION = "report_generation"
    MULTI_PROPERTY = "multi_property"
    PROPERTY_ARCHIVAL = "property_archival"
    GENERAL = "general"


# Database Models

class UATFeedback(Base):
    """User feedback collected during UAT"""
    __tablename__ = "uat_feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)  # Optional for anonymous feedback
    test_scenario = Column(SQLEnum(TestScenario), nullable=False)
    category = Column(SQLEnum(FeedbackCategory), nullable=False)
    rating = Column(Integer, nullable=True)  # 1-5 scale
    comment = Column(Text, nullable=True)
    severity = Column(SQLEnum(FeedbackSeverity), nullable=True)  # For bug reports
    
    # Bug report specific fields
    steps_to_reproduce = Column(Text, nullable=True)
    expected_result = Column(Text, nullable=True)
    actual_result = Column(Text, nullable=True)
    browser_info = Column(String(200), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Integer, default=False)
    resolution_notes = Column(Text, nullable=True)


class UATMetrics(Base):
    """Track UAT usage metrics"""
    __tablename__ = "uat_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    test_scenario = Column(SQLEnum(TestScenario), nullable=False)
    action = Column(String(100), nullable=False)
    
    # Performance metrics
    duration_seconds = Column(Float, nullable=True)
    success = Column(Integer, default=True)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic Schemas

class FeedbackCreate(BaseModel):
    """Schema for creating feedback"""
    test_scenario: TestScenario
    category: FeedbackCategory
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None
    severity: Optional[FeedbackSeverity] = None
    
    # Bug report fields
    steps_to_reproduce: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    browser_info: Optional[str] = None
    
    @validator('rating')
    def validate_rating(cls, v, values):
        """Ensure rating is provided for usability/functionality/value feedback"""
        category = values.get('category')
        if category in [FeedbackCategory.USABILITY, FeedbackCategory.FUNCTIONALITY, FeedbackCategory.VALUE]:
            if v is None:
                raise ValueError(f"Rating is required for {category} feedback")
        return v
    
    @validator('severity')
    def validate_severity(cls, v, values):
        """Ensure severity is provided for bug reports"""
        if values.get('category') == FeedbackCategory.BUG_REPORT and v is None:
            raise ValueError("Severity is required for bug reports")
        return v


class FeedbackResponse(BaseModel):
    """Schema for feedback response"""
    id: int
    test_scenario: TestScenario
    category: FeedbackCategory
    rating: Optional[int]
    comment: Optional[str]
    severity: Optional[FeedbackSeverity]
    created_at: datetime
    resolved: bool
    
    class Config:
        from_attributes = True


class MetricCreate(BaseModel):
    """Schema for creating usage metrics"""
    test_scenario: TestScenario
    action: str
    duration_seconds: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None


class MetricResponse(BaseModel):
    """Schema for metric response"""
    id: int
    user_id: int
    test_scenario: TestScenario
    action: str
    duration_seconds: Optional[float]
    success: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class FeedbackSummary(BaseModel):
    """Aggregated feedback summary"""
    total_feedback: int
    average_rating: float
    feedback_by_category: dict
    feedback_by_scenario: dict
    bug_count_by_severity: dict
    top_issues: List[str]


class UATProgress(BaseModel):
    """UAT progress tracking"""
    user_id: int
    scenarios_completed: List[TestScenario]
    completion_percentage: float
    total_time_spent_minutes: float
    feedback_submitted: int
    bugs_reported: int
