from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import date
import re

# Tax Rate Schemas
class TaxRateCreate(BaseModel):
    category: str
    rate: float
    effectiveFrom: date
    description: Optional[str] = None
    
    @validator('rate')
    def validate_rate(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Tax rate must be between 0 and 100')
        return v

class TaxRateResponse(BaseModel):
    id: str
    category: str
    rate: float
    effectiveFrom: str
    description: Optional[str] = None

# GST Settings Schemas
class GSTSettingsCreate(BaseModel):
    isGstApplicable: bool
    gstNumber: Optional[str] = None
    effectiveDate: date
    defaultRate: float
    displayFormat: str
    filingFrequency: str
    taxRates: Optional[List[TaxRateCreate]] = []
    
    @validator('gstNumber')
    def validate_gst_number(cls, v, values):
        if values.get('isGstApplicable') and not v:
            raise ValueError('GST number is required when GST is applicable')
        if v:
            if len(v) != 15:
                raise ValueError('GST number must be exactly 15 characters')
            # GST format: 29ABCDE1234F1Z5
            pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
            if not re.match(pattern, v):
                raise ValueError('Invalid GST number format')
        return v
    
    @validator('defaultRate')
    def validate_default_rate(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Default rate must be between 0 and 100')
        return v
    
    @validator('displayFormat')
    def validate_display_format(cls, v):
        if v not in ['Inclusive', 'Exclusive']:
            raise ValueError('Display format must be either Inclusive or Exclusive')
        return v
    
    @validator('filingFrequency')
    def validate_filing_frequency(cls, v):
        if v not in ['MONTHLY', 'QUARTERLY', 'ANNUALLY']:
            raise ValueError('Filing frequency must be MONTHLY, QUARTERLY, or ANNUALLY')
        return v

class GSTSettingsResponse(BaseModel):
    id: str
    isGstApplicable: bool
    gstNumber: Optional[str] = None
    effectiveDate: str
    defaultRate: float
    displayFormat: str
    filingFrequency: str
    taxRates: List[TaxRateResponse]
    createdAt: str
    updatedAt: str
