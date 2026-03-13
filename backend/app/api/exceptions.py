"""Custom exception handlers for subscription system"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.services.usage_tracker_service import QuotaExceededError
import logging

logger = logging.getLogger(__name__)


class SubscriptionNotFoundError(Exception):
    """Raised when subscription is not found"""
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"Subscription not found for user {user_id}")


class FeatureNotAvailableError(Exception):
    """Raised when feature is not available in current plan"""
    def __init__(self, feature: str, required_plan: str):
        self.feature = feature
        self.required_plan = required_plan
        super().__init__(
            f"Feature '{feature}' requires {required_plan} plan or higher"
        )


class PaymentFailedError(Exception):
    """Raised when payment processing fails"""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class StripeAPIError(Exception):
    """Raised when Stripe API call fails"""
    def __init__(self, message: str, stripe_error: Exception = None):
        self.message = message
        self.stripe_error = stripe_error
        super().__init__(message)


async def subscription_not_found_handler(
    request: Request,
    exc: SubscriptionNotFoundError
) -> JSONResponse:
    """Handle SubscriptionNotFoundError (404)"""
    logger.warning(f"Subscription not found: user_id={exc.user_id}")
    
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "subscription_not_found",
            "message": "No active subscription found",
            "user_id": exc.user_id
        }
    )


async def quota_exceeded_handler(
    request: Request,
    exc: QuotaExceededError
) -> JSONResponse:
    """Handle QuotaExceededError (429) with usage details"""
    logger.warning(
        f"Quota exceeded: resource={exc.resource_type}, "
        f"current={exc.current}, limit={exc.limit}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "quota_exceeded",
            "message": str(exc),
            "resource_type": exc.resource_type,
            "current": exc.current,
            "limit": exc.limit,
            "reset_date": exc.reset_date.isoformat(),
            "upgrade_url": "/pricing"
        },
        headers={
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": exc.reset_date.isoformat()
        }
    )


async def feature_not_available_handler(
    request: Request,
    exc: FeatureNotAvailableError
) -> JSONResponse:
    """Handle FeatureNotAvailableError (403) with upgrade prompt"""
    logger.info(
        f"Feature access denied: feature={exc.feature}, "
        f"required_plan={exc.required_plan}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "feature_not_available",
            "message": str(exc),
            "feature": exc.feature,
            "required_plan": exc.required_plan,
            "upgrade_url": "/pricing"
        }
    )


async def payment_failed_handler(
    request: Request,
    exc: PaymentFailedError
) -> JSONResponse:
    """Handle PaymentFailedError (402)"""
    logger.error(f"Payment failed: {exc.message}, details={exc.details}")
    
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={
            "error": "payment_failed",
            "message": exc.message,
            "details": exc.details
        }
    )


async def stripe_api_error_handler(
    request: Request,
    exc: StripeAPIError
) -> JSONResponse:
    """Handle StripeAPIError (500)"""
    logger.error(
        f"Stripe API error: {exc.message}",
        extra={"stripe_error": str(exc.stripe_error) if exc.stripe_error else None}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "payment_processing_error",
            "message": "An error occurred while processing your payment. Please try again later.",
            "support_message": "If the problem persists, please contact support."
        }
    )


def register_exception_handlers(app):
    """
    Register custom exception handlers with FastAPI app.
    
    Per Requirement 2.2, 3.2, 4.8: Custom error responses.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(SubscriptionNotFoundError, subscription_not_found_handler)
    app.add_exception_handler(QuotaExceededError, quota_exceeded_handler)
    app.add_exception_handler(FeatureNotAvailableError, feature_not_available_handler)
    app.add_exception_handler(PaymentFailedError, payment_failed_handler)
    app.add_exception_handler(StripeAPIError, stripe_api_error_handler)
    
    logger.info("Registered custom exception handlers for subscription system")
