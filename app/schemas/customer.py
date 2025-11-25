from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
import re

class CustomerCreate(BaseModel):
    code: str = Field(..., min_length=2)
    name: str = Field(..., min_length=2)
    type: str  # UUID of client type
    address: str = Field(..., min_length=10)
    email: EmailStr
    whatsapp: str = Field(..., min_length=10)
    phone: str = Field(..., min_length=10)
    contactPerson: str = Field(..., min_length=2)
    gstNumber: Optional[str] = Field(None, min_length=15, max_length=15)
    panNumber: Optional[str] = Field(None, min_length=10, max_length=10)
    paymentTerms: int
    accountManager: str  # UUID of account manager
    isActive: bool = True
    
    @validator('gstNumber')
    def validate_gst_number(cls, v):
        if v:
            # GST format: 29ABCDE1234F1Z5
            pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
            if not re.match(pattern, v):
                raise ValueError('Invalid GST number format')
        return v
    
    @validator('panNumber')
    def validate_pan_number(cls, v):
        if v:
            # PAN format: ABCDE1234F
            pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
            if not re.match(pattern, v):
                raise ValueError('Invalid PAN number format')
        return v
    
    @validator('paymentTerms')
    def validate_payment_terms(cls, v):
        if v < 0:
            raise ValueError('Payment terms must be 0 or greater')
        return v

class CustomerUpdate(CustomerCreate):
    pass

class CustomerResponse(BaseModel):
    id: str
    code: str
    name: str
    type: str
    typeId: str
    address: str
    email: str
    whatsapp: str
    phone: str
    contactPerson: str
    gstNumber: Optional[str] = None
    panNumber: Optional[str] = None
    paymentTerms: int
    accountManager: str
    accountManagerId: str
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
