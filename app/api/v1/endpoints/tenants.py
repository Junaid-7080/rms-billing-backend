from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.tenant import Tenant, Subscription
from app.schemas.tenant import (
    TenantResponse,
    TenantUpdateRequest,
    SubscriptionResponse,
    UpgradeRequest,
    UpgradeResponse
)

router = APIRouter(prefix="/api/v1/tenants", tags=["Tenants"])


@router.get("/me", response_model=TenantResponse)
def get_current_tenant(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current tenant details"""
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Calculate trial days remaining
    trial_days_remaining = 0
    if tenant.subscription_status == 'trial' and tenant.trial_end_date:
        days_left = (tenant.trial_end_date - datetime.utcnow()).days
        trial_days_remaining = max(0, days_left)
    
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "email": tenant.email,
        
    
        "subscriptionStatus": tenant.subscription_status,
        "trialStartDate": tenant.trial_start_date.isoformat() if tenant.trial_start_date else None,
        "trialEndDate": tenant.trial_end_date.isoformat() if tenant.trial_end_date else None,
        "trialDaysRemaining": trial_days_remaining,
        "isTrialUsed": tenant.is_trial_used,
        "currentInvoiceCount": tenant.current_invoice_count or 0,
        "currentCustomerCount": tenant.current_customer_count or 0,
        "currentUserCount": tenant.current_user_count or 0,
        "createdAt": tenant.created_at.isoformat() if tenant.created_at else None
    }


@router.put("/me", response_model=TenantResponse)
def update_current_tenant(
    payload: TenantUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update current tenant settings (admin only)"""
    # Check if user is admin
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update tenant settings"
        )
    
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Update fields
    if payload.name:
        tenant.name = payload.name
    if payload.email:
        tenant.email = payload.email
    if payload.phone:
        tenant.phone = payload.phone
    if payload.address:
        tenant.address = payload.address
    
    tenant.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(tenant)
    
    # Calculate trial days remaining
    trial_days_remaining = 0
    if tenant.subscription_status == 'trial' and tenant.trial_end_date:
        days_left = (tenant.trial_end_date - datetime.utcnow()).days
        trial_days_remaining = max(0, days_left)
    
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "email": tenant.email,
        "phone": tenant.phone,
        "address": tenant.address,
        "subscriptionStatus": tenant.subscription_status,
        "trialStartDate": tenant.trial_start_date.isoformat() if tenant.trial_start_date else None,
        "trialEndDate": tenant.trial_end_date.isoformat() if tenant.trial_end_date else None,
        "trialDaysRemaining": trial_days_remaining,
        "isTrialUsed": tenant.is_trial_used,
        "currentInvoiceCount": tenant.current_invoice_count or 0,
        "currentCustomerCount": tenant.current_customer_count or 0,
        "currentUserCount": tenant.current_user_count or 0,
        "createdAt": tenant.created_at.isoformat() if tenant.created_at else None
    }


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get subscription status and limits"""
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == current_user.tenant_id
    ).first()
    
    # Calculate trial days remaining
    trial_days_remaining = 0
    if tenant.subscription_status == 'trial' and tenant.trial_end_date:
        days_left = (tenant.trial_end_date - datetime.utcnow()).days
        trial_days_remaining = max(0, days_left)
    
    # Determine limits based on plan
    from app.core.config import settings
    
    if tenant.subscription_status == 'trial':
        limits = {
            "invoiceLimit": None,  # Unlimited during trial
            "customerLimit": None,
            "userLimit": None
        }
    elif tenant.subscription_status == 'free':
        limits = {
            "invoiceLimit": settings.FREE_TIER_INVOICE_LIMIT,
            "customerLimit": settings.FREE_TIER_CUSTOMER_LIMIT,
            "userLimit": settings.FREE_TIER_USER_LIMIT
        }
    else:  # paid
        limits = {
            "invoiceLimit": None,  # Unlimited
            "customerLimit": None,
            "userLimit": None
        }
    
    return {
        "planType": subscription.plan_type if subscription else "free",
        "status": tenant.subscription_status,
        "isTrial": subscription.is_trial if subscription else False,
        "trialDaysRemaining": trial_days_remaining,
        "trialEndDate": tenant.trial_end_date.isoformat() if tenant.trial_end_date else None,
        "currentUsage": {
            "invoices": tenant.current_invoice_count or 0,
            "customers": tenant.current_customer_count or 0,
            "users": tenant.current_user_count or 0
        },
        "limits": limits,
        "features": {
            "unlimitedInvoices": tenant.subscription_status in ['trial', 'paid'],
            "unlimitedCustomers": tenant.subscription_status in ['trial', 'paid'],
            "multipleUsers": tenant.subscription_status in ['trial', 'paid'],
            "pdfGeneration": True,
            "emailNotifications": True,
            "apiAccess": tenant.subscription_status == 'paid'
        }
    }


@router.post("/upgrade", response_model=UpgradeResponse)
def upgrade_subscription(
    payload: UpgradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upgrade to paid plan (admin only)"""
    # Check if user is admin
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can upgrade subscription"
        )
    
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check if already on paid plan
    if tenant.subscription_status == 'paid':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already on paid plan"
        )
    
    # Update tenant
    tenant.subscription_status = 'paid'
    tenant.updated_at = datetime.utcnow()
    
    # Update subscription
    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == current_user.tenant_id
    ).first()
    
    if subscription:
        subscription.plan_type = payload.planType
        subscription.is_trial = False
        subscription.billing_cycle = payload.billingCycle
        subscription.updated_at = datetime.utcnow()
    else:
        # Create new subscription
        subscription = Subscription(
            tenant_id=str(current_user.tenant_id),
            plan_type=payload.planType,
            is_trial=False,
            billing_cycle=payload.billingCycle
        )
        db.add(subscription)
    
    db.commit()
    
    return {
        "message": "Subscription upgraded successfully",
        "planType": payload.planType,
        "status": "paid",
        "billingCycle": payload.billingCycle
    }
