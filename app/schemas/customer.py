from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
import re
from uuid import UUID


def _strip_or_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


class CustomerCreate(BaseModel):
    code: str = Field(..., min_length=2)
    name: str = Field(..., min_length=2)
    typeId: Optional[UUID] = None  # UUID of client type (optional)
    addressLine1: str = Field(..., min_length=2)
    addressLine2: Optional[str] = Field(None, min_length=2)
    addressLine3: Optional[str] = Field(None, min_length=2)
    state: str = Field(..., min_length=2)
    country: str = Field(..., min_length=2)
    email: EmailStr
    whatsapp: str = Field(..., min_length=10)
    phone: str = Field(..., min_length=10)
    contactPerson: str = Field(..., min_length=2)
    customerNote: Optional[str] = None
    gstNumber: Optional[str] = Field(None, min_length=15, max_length=15)
    panNumber: Optional[str] = Field(None, min_length=10, max_length=10)
    gstExempted: bool = False
    gstExemptionReason: Optional[str] = None
    paymentTerms: int
    isActive: bool = True
    
    @validator('gstNumber')
    def validate_gst_number(cls, v):
        if v:
            pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
            if not re.match(pattern, v):
                raise ValueError('Invalid GST number format')
        return v
    
    @validator('panNumber')
    def validate_pan_number(cls, v):
        if v:
            pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
            if not re.match(pattern, v):
                raise ValueError('Invalid PAN number format')
        return v
    
    @validator('paymentTerms')
    def validate_payment_terms(cls, v):
        if v < 0:
            raise ValueError('Payment terms must be 0 or greater')
        return v
    
    @validator('contactPerson')
    def validate_contact_person(cls, v):
        cleaned = _strip_or_none(v)
        if not cleaned:
            raise ValueError('Contact person cannot be empty')
        return cleaned
    
    @validator('gstExemptionReason', always=True)
    def validate_gst_exemption_reason(cls, v, values):
        cleaned = _strip_or_none(v)
        if values.get('gstExempted'):
            if not cleaned:
                raise ValueError('GST exemption reason is required when GST is exempted')
            return cleaned
        return cleaned


class CustomerUpdate(CustomerCreate):
    code: Optional[str] = Field(None, min_length=2)
    name: Optional[str] = Field(None, min_length=2)
    typeId: Optional[UUID] = None
    addressLine1: Optional[str] = Field(None, min_length=2)
    addressLine2: Optional[str] = Field(None, min_length=2)
    addressLine3: Optional[str] = Field(None, min_length=2)
    state: Optional[str] = Field(None, min_length=2)
    country: Optional[str] = Field(None, min_length=2)
    email: Optional[EmailStr] = None
    whatsapp: Optional[str] = Field(None, min_length=10)
    phone: Optional[str] = Field(None, min_length=10)
    contactPerson: Optional[str] = Field(None, min_length=2)
    customerNote: Optional[str] = None
    gstNumber: Optional[str] = Field(None, min_length=15, max_length=15)
    panNumber: Optional[str] = Field(None, min_length=10, max_length=10)
    gstExempted: Optional[bool] = None
    gstExemptionReason: Optional[str] = None
    paymentTerms: Optional[int] = None
    isActive: Optional[bool] = None
    
    @validator('gstNumber')
    def validate_gst_number(cls, v):
        if v:
            pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
            if not re.match(pattern, v):
                raise ValueError('Invalid GST number format')
        return v
    
    @validator('panNumber')
    def validate_pan_number(cls, v):
        if v:
            pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
            if not re.match(pattern, v):
                raise ValueError('Invalid PAN number format')
        return v
    
    @validator('paymentTerms')
    def validate_payment_terms(cls, v):
        if v is not None and v < 0:
            raise ValueError('Payment terms must be 0 or greater')
        return v
    
    @validator('contactPerson')
    def validate_contact_person(cls, v):
        if v is None:
            return v
        cleaned = _strip_or_none(v)
        if not cleaned:
            raise ValueError('Contact person cannot be empty')
        return cleaned
    
    @validator('gstExemptionReason', always=True)
    def validate_gst_exemption_reason(cls, v, values):
        cleaned = _strip_or_none(v)
        if values.get('gstExempted'):
            if not cleaned:
                raise ValueError('GST exemption reason is required when GST is exempted')
            return cleaned
        return cleaned


class CustomerResponse(BaseModel):
    id: str
    code: str
    name: str
    type: Optional[str] = None  # Display name
    typeId: Optional[str] = None  # UUID
    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    addressLine3: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    phone: Optional[str] = None
    contactPerson: Optional[str] = None
    customerNote: Optional[str] = None
    gstNumber: Optional[str] = None
    panNumber: Optional[str] = None
    gstExempted: bool
    gstExemptionReason: Optional[str] = None
    paymentTerms: int
    isActive: bool
    createdAt: str
    updatedAt: str


class Pagination(BaseModel):
    total: int
    page: int
    limit: int
    totalPages: int
    hasMore: bool

class CustomerListResponse(BaseModel):
    data: List[CustomerResponse]
    pagination: Pagination