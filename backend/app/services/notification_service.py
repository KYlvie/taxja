"""
Notification Service

Handles user notifications for tax rate updates and other events.
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user import User
from app.models.notification import Notification, NotificationType


class NotificationService:
    """Service for managing user notifications"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def notify_tax_rate_update(
        self,
        tax_year: int,
        admin_user: User
    ):
        """
        Notify all users about tax rate update.
        
        Args:
            tax_year: Year that was updated
            admin_user: Admin who made the update
        """
        # Get all active users
        users = self.db.query(User).filter(
            User.is_active == True
        ).all()
        
        # Create notification for each user
        for user in users:
            notification = Notification(
                user_id=user.id,
                type=NotificationType.TAX_RATE_UPDATE,
                title=f"Steuerrate-Update für {tax_year}",
                message=f"Die Steuerkonfiguration für das Jahr {tax_year} wurde aktualisiert. "
                        f"Bitte überprüfen Sie Ihre Berechnungen.",
                message_en=f"Tax configuration for year {tax_year} has been updated. "
                          f"Please review your calculations.",
                message_zh=f"{tax_year} 年税率配置已更新。请检查您的计算。",
                data={
                    'tax_year': tax_year,
                    'updated_by': admin_user.email,
                    'updated_at': datetime.utcnow().isoformat()
                },
                is_read=False,
                created_at=datetime.utcnow()
            )
            self.db.add(notification)
        
        self.db.commit()
    
    def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """Get notifications for a user"""
        query = self.db.query(Notification).filter(
            Notification.user_id == user_id
        )
        
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        return query.order_by(
            Notification.created_at.desc()
        ).limit(limit).all()
    
    def mark_as_read(self, notification_id: int, user_id: int):
        """Mark notification as read"""
        notification = self.db.query(Notification).filter(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        ).first()
        
        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            self.db.commit()
    
    def mark_all_as_read(self, user_id: int):
        """Mark all notifications as read for a user"""
        self.db.query(Notification).filter(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        ).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        self.db.commit()
