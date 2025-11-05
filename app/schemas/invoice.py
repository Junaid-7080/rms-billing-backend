from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import date
from decimal import Decimal

# Line Item Schemas
class InvoiceLineItemCreate(BaseModel):
    serviceType: str  # UUID
    description: Optional[str] = None
    quantity: float
    rate: float
    taxRate: float
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v < 1:
            raise ValueError('Quantity must be at least 1')
        return v
    
    @validator('rate')
    def validate_rate(cls, v):
        if v < 0:
            raise ValueError('Rate must be 0 or greater')
        return v
    
    @validator('taxRate')
    def validate_tax_rate(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Tax rate must be between 0 and 100')
        return v

class InvoiceLineItemResponse(BaseModel):
    id: str
    serviceType: str
    serviceTypeName: str
    description: Optional[str] = None
    quantity: float
    rate: float
    amount: float
    taxRate: float
    taxAmount: float
    total: float

# Invoice Schemas
class InvoiceCreate(BaseModel):
    invoiceNumber: Optional[str] = None  # Auto-generated if not provided
    invoiceDate: date
    customerId: str  # UUID
    dueDate: date
    referenceNumber: Optional[str] = None
    lineItems: List[InvoiceLineItemCreate]
    notes: Optional[str] = None
    
    @validator('lineItems')
    def validate_line_items(cls, v):
        if len(v) < 1:
            raise ValueError('At least one line item is required')
        return v
    
    @validator('dueDate')
    def validate_due_date(cls, v, values):
        if 'invoiceDate' in values and v < values['invoiceDate']:
            raise ValueError('Due date must be on or after invoice date')
        return v
    
    @validator('referenceNumber')
    def validate_reference_number(cls, v):
        if v and len(v) > 100:
            raise ValueError('Reference number must be 100 characters or less')
        return v
    
    @validator('notes')
    def validate_notes(cls, v):
        if v and len(v) > 1000:
            raise ValueError('Notes must be 1000 characters or less')
        return v

class InvoiceUpdate(InvoiceCreate):
    pass

class InvoiceResponse(BaseModel):
    id: str
    invoiceNumber: str
    invoiceDate: str
    customerId: str
    customerName: str
    customerGst: Optional[str] = None
    dueDate: str
    referenceNumber: Optional[str] = None
    lineItems: List[InvoiceLineItemResponse]
    subtotal: float
    taxTotal: float
    total: float
    status: str  # Paid, Pending, Overdue
    notes: Optional[str] = None
    createdAt: str
    updatedAt: str

class Pagination(BaseModel):
    total: int
    page: int
    limit: int
    totalPages: int
    hasMore: bool

class InvoiceListResponse(BaseModel):
    data: List[InvoiceResponse]
    pagination: Pagination

# Email Invoice Schema
class EmailInvoiceRequest(BaseModel):
    to: Optional[str] = None
    cc: Optional[List[str]] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    includePaymentLink: Optional[bool] = False

class EmailInvoiceResponse(BaseModel):
    success: bool
    message: str
    sentTo: str
    sentAt: str
