from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import date

# Credit Note Schemas
class CreditNoteCreate(BaseModel):
    creditNoteId: Optional[str] = None  # Auto-generated if not provided
    creditNoteDate: date
    customerId: str  # UUID
    invoiceId: Optional[str] = None  # UUID, optional
    reason: str
    amount: float
    gstRate: float
    notes: Optional[str] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v < 1:
            raise ValueError('Amount must be at least 1')
        return v
    
    @validator('gstRate')
    def validate_gst_rate(cls, v):
        if v < 0 or v > 100:
            raise ValueError('GST rate must be between 0 and 100')
        return v
    
    @validator('reason')
    def validate_reason(cls, v):
        if not v or len(v) < 2:
            raise ValueError('Reason is required and must be at least 2 characters')
        return v
    
    @validator('notes')
    def validate_notes(cls, v):
        if v and len(v) > 1000:
            raise ValueError('Notes must be 1000 characters or less')
        return v

class CreditNoteResponse(BaseModel):
    id: str
    creditNoteId: str
    creditNoteDate: str
    customerId: str
    customerName: str
    invoiceId: Optional[str] = None
    invoiceNumber: Optional[str] = None
    reason: str
    amount: float
    gstRate: float
    gstAmount: float
    totalCredit: float
    status: str
    notes: Optional[str] = None
    createdAt: str

class Pagination(BaseModel):
    total: int
    page: int
    limit: int
    totalPages: int
    hasMore: bool

class CreditNoteListResponse(BaseModel):
    data: List[CreditNoteResponse]
    pagination: Pagination
