from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyResponse, BankDetails

router = APIRouter(prefix="/api/v1/company", tags=["Company"])


@router.get("", response_model=CompanyResponse)
def get_company_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get company profile/settings for current tenant"""
    company = db.query(Company).filter(
        Company.tenant_id == current_user.tenant_id
    ).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found"
        )
    
    return CompanyResponse(
        id=str(company.id),
        companyName=company.company_name,
        PAN=company.pan,
        financialYearFrom=company.financial_year_from.isoformat(),
        financialYearTo=company.financial_year_to.isoformat(),
        addressLine1=company.address_line1,
        addressLine2=company.address_line2,
        addressLine3=company.address_line3,
        state=company.state,
        country=company.country,
        contactNo1=company.contact_no1,
        contactNo2=company.contact_no2,
        contactNo3=company.contact_no3,
        gstApplicable=company.gst_applicable,
        gstNumber=company.gst_number,
        gstStateCode=company.gst_state_code,
        gstCompoundingCompany=company.gst_compounding_company,
        groupCompany=company.group_company,
        groupCode=company.group_code,
        bankDetails=BankDetails(**company.bank_details),
        createdAt=company.created_at.isoformat() if company.created_at else None,
        updatedAt=company.updated_at.isoformat() if company.updated_at else None
    )


@router.post("", response_model=CompanyResponse)
def create_or_update_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update company profile. If exists, updates; if not, creates new. (admin only)"""
    # 1. Verify user has admin role
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify company profile"
        )
    
    # 2. Get tenant_id from JWT (already in current_user)
    tenant_id = current_user.tenant_id
    
    # 3. Validate GST fields
    if payload.gstApplicable and (not payload.gstNumber or not payload.gstStateCode):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GST Number and GST State Code are required when GST is applicable"
        )
    
    # 4. Validate group company fields
    if payload.groupCompany and not payload.groupCode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group Code is required when company is part of a group"
        )
    
    # 5. Check if company already exists for tenant
    company = db.query(Company).filter(
        Company.tenant_id == tenant_id
    ).first()
    
    # Convert bank details to dict
    bank_details_dict = payload.bankDetails.model_dump()
    
    if company:
        # 6. UPDATE existing company record
        company.company_name = payload.companyName
        company.pan = payload.PAN
        company.financial_year_from = payload.financialYearFrom
        company.financial_year_to = payload.financialYearTo
        company.address_line1 = payload.addressLine1
        company.address_line2 = payload.addressLine2
        company.address_line3 = payload.addressLine3
        company.state = payload.state
        company.country = payload.country
        company.contact_no1 = payload.contactNo1
        company.contact_no2 = payload.contactNo2
        company.contact_no3 = payload.contactNo3
        company.gst_applicable = payload.gstApplicable
        company.gst_number = payload.gstNumber
        company.gst_state_code = payload.gstStateCode
        company.gst_compounding_company = payload.gstCompoundingCompany
        company.group_company = payload.groupCompany
        company.group_code = payload.groupCode
        company.bank_details = bank_details_dict
        company.updated_at = datetime.utcnow()
        company.created_by = current_user.id
    else:
        # 7. INSERT new company record
        company = Company(
            id=uuid4(),
            tenant_id=tenant_id,
            company_name=payload.companyName,
            pan=payload.PAN,
            financial_year_from=payload.financialYearFrom,
            financial_year_to=payload.financialYearTo,
            address_line1=payload.addressLine1,
            address_line2=payload.addressLine2,
            address_line3=payload.addressLine3,
            state=payload.state,
            country=payload.country,
            contact_no1=payload.contactNo1,
            contact_no2=payload.contactNo2,
            contact_no3=payload.contactNo3,
            gst_applicable=payload.gstApplicable,
            gst_number=payload.gstNumber,
            gst_state_code=payload.gstStateCode,
            gst_compounding_company=payload.gstCompoundingCompany,
            group_company=payload.groupCompany,
            group_code=payload.groupCode,
            bank_details=bank_details_dict,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(company)
    
    # 8. Commit and return company details
    db.commit()
    db.refresh(company)
    
    # TODO: Create audit log entry (side effect)
    # TODO: May update tenant settings (side effect)
    
    return CompanyResponse(
        id=str(company.id),
        companyName=company.company_name,
        PAN=company.pan,
        financialYearFrom=company.financial_year_from.isoformat(),
        financialYearTo=company.financial_year_to.isoformat(),
        addressLine1=company.address_line1,
        addressLine2=company.address_line2,
        addressLine3=company.address_line3,
        state=company.state,
        country=company.country,
        contactNo1=company.contact_no1,
        contactNo2=company.contact_no2,
        contactNo3=company.contact_no3,
        gstApplicable=company.gst_applicable,
        gstNumber=company.gst_number,
        gstStateCode=company.gst_state_code,
        gstCompoundingCompany=company.gst_compounding_company,
        groupCompany=company.group_company,
        groupCode=company.group_code,
        bankDetails=BankDetails(**company.bank_details),
        createdAt=company.created_at.isoformat() if company.created_at else None,
        updatedAt=company.updated_at.isoformat() if company.updated_at else None
    )
