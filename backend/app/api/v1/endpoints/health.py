"""Health check endpoints"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.base import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint for monitoring.
    
    Returns system health status including database connectivity.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        
        # Check if critical tables exist
        db.execute(text("SELECT COUNT(*) FROM plans"))
        db.execute(text("SELECT COUNT(*) FROM subscriptions"))
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": now,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": now,
        }


@router.get("/health/detailed")
def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check with component status.
    
    Returns detailed status of all system components.
    """
    health_status = {
        "status": "healthy",
        "components": {}
    }
    
    # Check database
    try:
        db.execute(text("SELECT 1"))
        health_status["components"]["database"] = {
            "status": "healthy",
            "message": "Connected"
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "message": str(e)
        }
    
    # Check plans table
    try:
        count = db.execute(text("SELECT COUNT(*) FROM plans")).scalar()
        health_status["components"]["plans"] = {
            "status": "healthy" if count > 0 else "warning",
            "count": count
        }
    except Exception as e:
        health_status["components"]["plans"] = {
            "status": "unhealthy",
            "message": str(e)
        }
    
    # Check subscriptions table
    try:
        count = db.execute(text("SELECT COUNT(*) FROM subscriptions")).scalar()
        health_status["components"]["subscriptions"] = {
            "status": "healthy",
            "count": count
        }
    except Exception as e:
        health_status["components"]["subscriptions"] = {
            "status": "unhealthy",
            "message": str(e)
        }
    
    # Check Redis connection
    try:
        import redis as redis_lib
        from app.core.config import settings as app_settings

        redis_client = redis_lib.Redis(
            host=getattr(app_settings, "REDIS_HOST", "localhost"),
            port=getattr(app_settings, "REDIS_PORT", 6379),
            db=getattr(app_settings, "REDIS_DB", 0),
            socket_connect_timeout=2,
        )
        redis_client.ping()
        health_status["components"]["redis"] = {
            "status": "healthy",
            "message": "Connected",
        }
        redis_client.close()
    except Exception as e:
        health_status["components"]["redis"] = {
            "status": "unhealthy",
            "message": str(e),
        }
    
    return health_status


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check for Kubernetes/load balancers.
    
    Returns 200 if service is ready to accept traffic.
    """
    try:
        # Check database
        db.execute(text("SELECT 1"))
        
        # Check if plans are seeded
        count = db.execute(text("SELECT COUNT(*) FROM plans")).scalar()
        if count == 0:
            return {
                "ready": False,
                "reason": "Plans not seeded"
            }
        
        return {
            "ready": True
        }
    except Exception as e:
        return {
            "ready": False,
            "reason": str(e)
        }
