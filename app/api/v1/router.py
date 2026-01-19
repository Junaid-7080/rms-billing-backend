# app/api/v1/router.py
from fastapi import APIRouter



# Add your routes here
from app.api.v1.endpoints import (
    auth,
    tenants,
    dashboard,
    company,
    customers,
    service_types,
    client_types,
    account_managers,
    roles,
    invoices,
    receipts,
    credit_notes,
    gst_settings,
    helpers
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(dashboard.router)
api_router.include_router(company.router)
api_router.include_router(customers.router)
api_router.include_router(service_types.router)
api_router.include_router(client_types.router)
api_router.include_router(account_managers.router, prefix="/account-managers", tags=["Account Managers"])
api_router.include_router(roles.router)
api_router.include_router(invoices.router)
api_router.include_router(receipts.router)
api_router.include_router(credit_notes.router)
api_router.include_router(gst_settings.router)
api_router.include_router(helpers.router)
