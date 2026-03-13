"""Plan service for managing subscription plans"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging

from app.models.plan import Plan, PlanType
from app.schemas.subscription import PlanCreate, PlanUpdate, PlanResponse


logger = logging.getLogger(__name__)


class PlanService:
    """Service for managing subscription plans"""
    
    def __init__(self, db: Session):
        """
        Initialize plan service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def get_plan(self, plan_id: int) -> Optional[Plan]:
        """
        Get a plan by ID.
        
        Args:
            plan_id: ID of the plan to retrieve
            
        Returns:
            Plan instance if found, None otherwise
        """
        return self.db.query(Plan).filter(Plan.id == plan_id).first()
    
    def get_plan_by_type(self, plan_type: PlanType) -> Optional[Plan]:
        """
        Get a plan by plan type.
        
        Args:
            plan_type: Type of plan (FREE, PLUS, PRO)
            
        Returns:
            Plan instance if found, None otherwise
        """
        return self.db.query(Plan).filter(Plan.plan_type == plan_type).first()
    
    def list_plans(self) -> List[Plan]:
        """
        List all available plans.
        
        Returns:
            List of all Plan instances
        """
        return self.db.query(Plan).order_by(Plan.monthly_price).all()
    
    def create_plan(self, plan_data: PlanCreate) -> Plan:
        """
        Create a new subscription plan.
        
        Args:
            plan_data: Plan creation data
            
        Returns:
            Created Plan instance
            
        Raises:
            ValueError: If plan with same plan_type already exists
            ValueError: If features or quotas validation fails
        """
        # Check if plan with this type already exists
        existing_plan = self.get_plan_by_type(plan_data.plan_type)
        if existing_plan:
            raise ValueError(f"Plan with type {plan_data.plan_type} already exists")
        
        # Create new plan
        plan = Plan(
            plan_type=plan_data.plan_type,
            name=plan_data.name,
            monthly_price=plan_data.monthly_price,
            yearly_price=plan_data.yearly_price,
            features=plan_data.features,
            quotas=plan_data.quotas,
        )
        
        # Validate features and quotas
        if not plan.validate_features():
            raise ValueError("Invalid features: all values must be boolean")
        
        if not plan.validate_quotas():
            raise ValueError("Invalid quotas: all values must be integers >= -1")
        
        try:
            self.db.add(plan)
            self.db.commit()
            self.db.refresh(plan)
            logger.info(f"Created plan: {plan.plan_type} (ID: {plan.id})")
            return plan
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to create plan: {e}")
            raise ValueError(f"Failed to create plan: {e}")
    
    def update_plan(self, plan_id: int, plan_data: PlanUpdate) -> Plan:
        """
        Update an existing plan.
        
        Per Requirement 1.3: Plan updates only affect new subscriptions.
        Existing subscriptions maintain their original plan configuration
        until the next billing cycle.
        
        Args:
            plan_id: ID of the plan to update
            plan_data: Plan update data
            
        Returns:
            Updated Plan instance
            
        Raises:
            ValueError: If plan not found
            ValueError: If features or quotas validation fails
        """
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan with id {plan_id} not found")
        
        # Update fields if provided
        if plan_data.name is not None:
            plan.name = plan_data.name
        
        if plan_data.monthly_price is not None:
            plan.monthly_price = plan_data.monthly_price
        
        if plan_data.yearly_price is not None:
            plan.yearly_price = plan_data.yearly_price
        
        if plan_data.features is not None:
            plan.features = plan_data.features
        
        if plan_data.quotas is not None:
            plan.quotas = plan_data.quotas
        
        # Validate features and quotas after update
        if not plan.validate_features():
            self.db.rollback()
            raise ValueError("Invalid features: all values must be boolean")
        
        if not plan.validate_quotas():
            self.db.rollback()
            raise ValueError("Invalid quotas: all values must be integers >= -1")
        
        try:
            self.db.commit()
            self.db.refresh(plan)
            logger.info(
                f"Updated plan: {plan.plan_type} (ID: {plan.id}). "
                f"Changes will only affect new subscriptions."
            )
            return plan
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to update plan: {e}")
            raise ValueError(f"Failed to update plan: {e}")
    
    def get_plan_features(self, plan_id: int) -> Dict[str, bool]:
        """
        Get all features for a specific plan.
        
        Args:
            plan_id: ID of the plan
            
        Returns:
            Dictionary of feature names to boolean values
            
        Raises:
            ValueError: If plan not found
        """
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan with id {plan_id} not found")
        
        return plan.features or {}
    
    def get_plan_quotas(self, plan_id: int) -> Dict[str, int]:
        """
        Get all quotas for a specific plan.
        
        Args:
            plan_id: ID of the plan
            
        Returns:
            Dictionary of resource types to quota limits (-1 for unlimited)
            
        Raises:
            ValueError: If plan not found
        """
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan with id {plan_id} not found")
        
        return plan.quotas or {}
    
    def check_feature_access(self, plan_id: int, feature_name: str) -> bool:
        """
        Check if a plan has access to a specific feature.
        
        Args:
            plan_id: ID of the plan
            feature_name: Name of the feature to check
            
        Returns:
            True if plan has access to feature, False otherwise
            
        Raises:
            ValueError: If plan not found
        """
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan with id {plan_id} not found")
        
        return plan.has_feature(feature_name)
    
    def get_quota_limit(self, plan_id: int, resource_type: str) -> int:
        """
        Get quota limit for a specific resource type.
        
        Args:
            plan_id: ID of the plan
            resource_type: Type of resource (e.g., 'transactions', 'ocr_scans')
            
        Returns:
            Quota limit as integer, -1 for unlimited, 0 if not defined
            
        Raises:
            ValueError: If plan not found
        """
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan with id {plan_id} not found")
        
        return plan.get_quota(resource_type)
