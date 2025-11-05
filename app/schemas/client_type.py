from pydantic import BaseModel, constr, validator
from typing import Optional, List

class ClientTypeCreate(BaseModel):
    code: constr(min_length=2)
    name: constr(min_length=2)
    description: constr(min_length=5)
    paymentTerms: int
    isActive: Optional[bool] = True
    
    @validator('paymentTerms')
    def validate_payment_terms(cls, v):
        if v < 0:
            raise ValueError('Payment terms must be 0 or greater')
        return v

class ClientTypeUpdate(ClientTypeCreate):
    pass

class ClientTypeResponse(BaseModel):
    id: str
    code: str
    name: str
    description: str
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

class ClientTypeListResponse(BaseModel):
    data: List[ClientTypeResponse]
    pagination: Pagination
