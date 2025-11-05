from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import date
from decimal import Decimal

# Receipt Allocation Schemas
class ReceiptAllocationCreate(BaseModel):
    invoiceId: str  # UUID
    amountAllocated: float
    
    @validator('amountAllocated')
    def validate_amount_allocated(cls, v):
        if v < 0.01:
            raise ValueError('Amount allocated must be at least 0.01')
        return v

class ReceiptAllocationResponse(BaseModel):
    invoiceId: str
    invoiceNumber: str
    amountAllocated: float

# Receipt Schemas
class ReceiptCreate(BaseModel):
    receiptId: Optional[str] = None  # Auto-generated if not provided
    receiptDate: date
    customerId: str  # UUID
    paymentMethod: str
    amountReceived: float
    allocations: List[ReceiptAllocationCreate]
    notes: Optional[str] = None
    
    @validator('receiptDate')
    def validate_receipt_date(cls, v):
        if v > date.today():
            raise ValueError('Receipt date cannot be in the future')
        return v
    
    @validator('paymentMethod')
    def validate_payment_method(cls, v):
        valid_methods = ['bank_transfer', 'cheque', 'cash', 'upi', 'card']
        if v.lower() not in valid_methods:
            raise ValueError(f'Payment method must be one of: {", ".join(valid_methods)}')
        return v.lower()
    
    @validator('amountReceived')
    def validate_amount_received(cls, v):
        if v < 1:
            raise ValueError('Amount received must be at least 1')
        return v
    
    @validator('allocations')
    def validate_allocations(cls, v):
        if len(v) < 1:
            raise ValueError('At least one allocation is required')
        return v
    
    @validator('notes')
    def validate_notes(cls, v):
        if v and len(v) > 1000:
            raise ValueError('Notes must be 1000 characters or less')
        return v

class ReceiptResponse(BaseModel):
    id: str
    receiptId: str
    receiptDate: str
    customerId: str
    customerName: str
    paymentMethod: str
    amountReceived: float
    allocations: List[ReceiptAllocationResponse]
    totalAllocated: float
    unappliedAmount: float
    notes: Optional[str] = None
    status: str
    createdAt: str

class ReceiptCreateResponse(ReceiptResponse):
    invoicesUpdated: List[str]

class Pagination(BaseModel):
    total: int
    page: int
    limit: int
    totalPages: int
    hasMore: bool

class ReceiptListResponse(BaseModel):
    data: List[ReceiptResponse]
    pagination: Pagination
