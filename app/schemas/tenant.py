from pydantic import BaseModel, EmailStr
from typing import Optional

class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    email: Optional[str]
   
  
    subscriptionStatus: str
    trialStartDate: Optional[str]
    trialEndDate: Optional[str]
    trialDaysRemaining: int
    isTrialUsed: bool
    currentInvoiceCount: int
    currentCustomerCount: int
    currentUserCount: int
    createdAt: Optional[str]


class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class SubscriptionResponse(BaseModel):
    planType: str
    status: str
    isTrial: bool
    trialDaysRemaining: int
    trialEndDate: Optional[str]
    currentUsage: dict
    limits: dict
    features: dict


class UpgradeRequest(BaseModel):
    planType: str  # "basic", "professional", "enterprise"
    billingCycle: str  # "monthly", "yearly"


class UpgradeResponse(BaseModel):
    message: str
    planType: str
    status: str
    billingCycle: str
