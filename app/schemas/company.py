from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date


class BankDetails(BaseModel):
    """Bank details nested object"""
    bankName: str = Field(..., min_length=2, max_length=100)
    branchName: str = Field(..., min_length=2, max_length=100)
    accountNumber: str = Field(..., min_length=5, max_length=20)
    ifscCode: str = Field(..., min_length=11, max_length=11)
    upiId: Optional[str] = Field(None, max_length=100)
    upiMobileNo: Optional[str] = Field(None, min_length=10, max_length=15)

    class Config:
        json_schema_extra = {
            "example": {
                "bankName": "SBI",
                "branchName": "Thrissur",
                "accountNumber": "123456789012",
                "ifscCode": "SBIN0001234",
                "upiId": "abc@upi",
                "upiMobileNo": "9876543210"
            }
        }


class CompanyCreate(BaseModel):
    """Schema for creating/updating company"""
    companyName: str = Field(..., min_length=2, max_length=255)
    PAN: str = Field(..., min_length=10, max_length=10)
    financialYearFrom: date
    financialYearTo: date
    
    # Address fields
    addressLine1: str = Field(..., min_length=2, max_length=255)
    addressLine2: Optional[str] = Field(None, max_length=255)
    addressLine3: Optional[str] = Field(None, max_length=255)
    state: str = Field(..., min_length=2, max_length=100)
    country: str = Field(..., min_length=2, max_length=100)
    
    # Contact numbers
    contactNo1: str = Field(..., min_length=10, max_length=20)
    contactNo2: Optional[str] = Field(None, min_length=10, max_length=20)
    contactNo3: Optional[str] = Field(None, min_length=10, max_length=20)
    
    # GST related
    gstApplicable: bool
    gstNumber: Optional[str] = Field(None, min_length=15, max_length=15)
    gstStateCode: Optional[str] = Field(None, min_length=2, max_length=2)
    gstCompoundingCompany: bool = False
    
    # Group company
    groupCompany: bool
    groupCode: Optional[str] = Field(None, min_length=2, max_length=50)
    
    # Bank details
    bankDetails: BankDetails
    
    @field_validator('PAN')
    @classmethod
    def validate_pan(cls, v: str) -> str:
        """Validate PAN format: ABCDE1234F"""
        if not v or len(v) != 10:
            raise ValueError('PAN must be exactly 10 characters')
        if not v[:5].isalpha() or not v[5:9].isdigit() or not v[9].isalpha():
            raise ValueError('Invalid PAN format. Expected format: ABCDE1234F')
        return v.upper()
    
    @field_validator('financialYearTo')
    @classmethod
    def validate_financial_year(cls, v: date, info) -> date:
        """Ensure financial year to is after from"""
        if 'financialYearFrom' in info.data:
            if v <= info.data['financialYearFrom']:
                raise ValueError('Financial year end date must be after start date')
        return v
    
    @field_validator('gstNumber')
    @classmethod
    def validate_gst_number(cls, v: Optional[str], info) -> Optional[str]:
        """Validate GST number format if provided"""
        if v:
            if len(v) != 15:
                raise ValueError('GST Number must be exactly 15 characters')
            # Basic GST format validation: 2 digits + 10 char PAN + 1 digit + 1 char + 1 digit
            if not (v[:2].isdigit() and v[12:14].isalnum() and v[14].isdigit()):
                raise ValueError('Invalid GST Number format')
        return v.upper() if v else None
    
    @field_validator('gstStateCode')
    @classmethod
    def validate_gst_state_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate GST state code"""
        if v:
            if not v.isdigit() or len(v) != 2:
                raise ValueError('GST State Code must be 2 digits')
            if int(v) < 1 or int(v) > 37:
                raise ValueError('GST State Code must be between 01 and 37')
        return v
    
    @field_validator('ifscCode', check_fields=False)
    @classmethod
    def validate_ifsc(cls, v: str) -> str:
        """Validate IFSC code format"""
        if len(v) != 11:
            raise ValueError('IFSC Code must be exactly 11 characters')
        if not v[:4].isalpha() or v[4] != '0' or not v[5:].isalnum():
            raise ValueError('Invalid IFSC Code format')
        return v.upper()

    class Config:
        json_schema_extra = {
            "example": {
                "companyName": "ABC Pvt Ltd",
                "PAN": "ABCDE1234F",
                "financialYearFrom": "2025-04-01",
                "financialYearTo": "2026-03-31",
                "addressLine1": "Line 1",
                "addressLine2": "Line 2",
                "addressLine3": "Line 3",
                "state": "Kerala",
                "country": "India",
                "contactNo1": "9876543210",
                "contactNo2": "9123456780",
                "contactNo3": "9988776655",
                "gstApplicable": True,
                "gstNumber": "32ABCDE1234F1Z5",
                "gstStateCode": "32",
                "gstCompoundingCompany": False,
                "groupCompany": True,
                "groupCode": "GRP001",
                "bankDetails": {
                    "bankName": "SBI",
                    "branchName": "Thrissur",
                    "accountNumber": "123456789012",
                    "ifscCode": "SBIN0001234",
                    "upiId": "abc@upi",
                    "upiMobileNo": "9876543210"
                }
            }
        }


class CompanyUpdate(CompanyCreate):
    """Schema for updating company - same as create"""
    pass


class CompanyResponse(BaseModel):
    """Schema for company response"""
    id: str
    companyName: str
    PAN: str
    financialYearFrom: str  # Will be converted to ISO format string
    financialYearTo: str
    
    addressLine1: str
    addressLine2: Optional[str] = None
    addressLine3: Optional[str] = None
    state: str
    country: str
    
    contactNo1: str
    contactNo2: Optional[str] = None
    contactNo3: Optional[str] = None
    
    gstApplicable: bool
    gstNumber: Optional[str] = None
    gstStateCode: Optional[str] = None
    gstCompoundingCompany: bool
    
    groupCompany: bool
    groupCode: Optional[str] = None
    
    bankDetails: BankDetails
    
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "COMP-001",
                "companyName": "ABC Pvt Ltd",
                "PAN": "ABCDE1234F",
                "financialYearFrom": "2025-04-01",
                "financialYearTo": "2026-03-31",
                "addressLine1": "Line 1",
                "addressLine2": "Line 2",
                "addressLine3": "Line 3",
                "state": "Kerala",
                "country": "India",
                "contactNo1": "9876543210",
                "contactNo2": "9123456780",
                "contactNo3": "9988776655",
                "gstApplicable": True,
                "gstNumber": "32ABCDE1234F1Z5",
                "gstStateCode": "32",
                "gstCompoundingCompany": False,
                "groupCompany": True,
                "groupCode": "GRP001",
                "bankDetails": {
                    "bankName": "SBI",
                    "branchName": "Thrissur",
                    "accountNumber": "123456789012",
                    "ifscCode": "SBIN0001234",
                    "upiId": "abc@upi",
                    "upiMobileNo": "9876543210"
                },
                "createdAt": "2025-12-06T10:30:00",
                "updatedAt": "2025-12-06T10:30:00"
            }
        }