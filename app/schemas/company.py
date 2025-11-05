from pydantic import BaseModel, EmailStr, constr, validator
from typing import Optional
from datetime import date

class CompanyCreate(BaseModel):
    name: constr(min_length=2, max_length=255)
    address: constr(min_length=10)
    registrationNumber: str
    taxId: str
    contactName: constr(min_length=2)
    contactEmail: EmailStr
    contactPhone: constr(min_length=10)
    financialYearStart: date
    currency: constr(min_length=3, max_length=3)
    industry: str
    companySize: str
    
    @validator('financialYearStart')
    def validate_financial_year_start(cls, v):
        if v > date.today():
            raise ValueError('Financial year start date cannot be in the future')
        return v
    
    @validator('companySize')
    def validate_company_size(cls, v):
        valid_sizes = ['1-10', '11-50', '51-200', '201-500', '501+']
        if v not in valid_sizes:
            raise ValueError(f'Company size must be one of: {", ".join(valid_sizes)}')
        return v

class CompanyUpdate(CompanyCreate):
    pass

class CompanyResponse(BaseModel):
    id: str
    name: str
    address: str
    registrationNumber: str
    taxId: str
    contactName: str
    contactEmail: str
    contactPhone: str
    financialYearStart: date
    currency: str
    industry: str
    companySize: str
    createdAt: str
    updatedAt: str
