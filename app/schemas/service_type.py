from pydantic import BaseModel, constr, validator
from typing import Optional, List

class ServiceTypeCreate(BaseModel):
    code: constr(min_length=2)
    name: constr(min_length=2)
    description: constr(min_length=5)
    taxRate: float
    isActive: Optional[bool] = True
    
    @validator('taxRate')
    def validate_tax_rate(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Tax rate must be between 0 and 100')
        return v

class ServiceTypeUpdate(ServiceTypeCreate):
    pass

class ServiceTypeResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    taxRate: float
    isActive: bool
    createdAt: str
    updatedAt: str

class Pagination(BaseModel):
    total: int
    page: int
    limit: int
    totalPages: int
    hasMore: bool

class ServiceTypeListResponse(BaseModel):
    data: List[ServiceTypeResponse]
    pagination: Pagination
