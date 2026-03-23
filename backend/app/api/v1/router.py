"""API v1 Router"""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    account,
    transactions,
    documents,
    dashboard,
    tax,
    auth,
    users,
    reports,
    properties,
    error_monitoring,
    historical_import,
    subscriptions,
    usage,
    webhooks,
    admin,
    health,
    employer,
    loans,
    liabilities,
)
from app.api.v1 import recurring_transactions
from app.api.v1.endpoints import recurring_suggestions

api_router = APIRouter()

# Health check routes (no prefix for standard paths)
api_router.include_router(health.router, tags=["health"])

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(employer.router, prefix="/employer", tags=["employer"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(loans.router, prefix="/loans", tags=["loans"])
api_router.include_router(liabilities.router, prefix="/liabilities", tags=["liabilities"])
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_router.include_router(recurring_transactions.router, prefix="/recurring-transactions", tags=["recurring-transactions"])
api_router.include_router(recurring_suggestions.router, prefix="/recurring-suggestions", tags=["recurring-suggestions"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(tax.router, tags=["tax"])
api_router.include_router(error_monitoring.router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(
    historical_import.router, prefix="/historical-import", tags=["historical-import"]
)

# Account management routes (cancellation, reactivation, data export)
api_router.include_router(account.router, prefix="/account", tags=["account"])

# Subscription and monetization routes
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# Tax configuration management (public supported-years + admin CRUD)
from app.api.v1.endpoints import tax_config_admin
api_router.include_router(
    tax_config_admin.router, prefix="/tax-configs", tags=["tax-configs"]
)

# User classification rules management
from app.api.v1.endpoints import classification_rules
api_router.include_router(
    classification_rules.router, prefix="/classification-rules", tags=["classification-rules"]
)

# Try to include optional routers
try:
    from app.api.v1.endpoints import ai_assistant
    api_router.include_router(ai_assistant.router, prefix="/ai", tags=["ai"])
except Exception:
    pass

# Tax filing summary
from app.api.v1.endpoints import tax_filing
api_router.include_router(tax_filing.router, tags=["tax-filing"])

# Credit-based billing
from app.api.v1.endpoints import credits
api_router.include_router(credits.router, prefix="/credits", tags=["credits"])

# Public contact form (no auth)
from app.api.v1.endpoints import contact
api_router.include_router(contact.router, tags=["contact"])
