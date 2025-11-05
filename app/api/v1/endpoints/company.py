from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyResponse

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
        name=company.name,
        address=company.address or "",
        registrationNumber=company.registration_number or "",
        taxId=company.tax_id or "",
        contactName=company.contact_name or "",
        contactEmail=company.contact_email or "",
        contactPhone=company.contact_phone or "",
        financialYearStart=company.financial_year_start,
        currency=company.currency or "INR",
        industry=company.industry or "",
        companySize=company.company_size or "",
        createdAt=company.created_at.isoformat() if company.created_at else "",
        updatedAt=company.updated_at.isoformat() if company.updated_at else ""
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
    
    # 3. Validate all fields (handled by Pydantic schema)
    
    # 4. Check if company already exists for tenant
    company = db.query(Company).filter(
        Company.tenant_id == tenant_id
    ).first()
    
    is_new = company is None
    
    if company:
        # 5. UPDATE existing company record
        company.name = payload.name
        company.address = payload.address
        company.registration_number = payload.registrationNumber
        company.tax_id = payload.taxId
        company.contact_name = payload.contactName
        company.contact_email = payload.contactEmail
        company.contact_phone = payload.contactPhone
        company.financial_year_start = payload.financialYearStart
        company.currency = payload.currency
        company.industry = payload.industry
        company.company_size = payload.companySize
        company.updated_at = datetime.utcnow()
        company.created_by = current_user.id
    else:
        # 6. INSERT new company record
        company = Company(
            id=uuid4(),
            tenant_id=tenant_id,
            name=payload.name,
            address=payload.address,
            registration_number=payload.registrationNumber,
            tax_id=payload.taxId,
            contact_name=payload.contactName,
            contact_email=payload.contactEmail,
            contact_phone=payload.contactPhone,
            financial_year_start=payload.financialYearStart,
            currency=payload.currency,
            industry=payload.industry,
            company_size=payload.companySize,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(company)
    
    # 7. Commit and return company details
    db.commit()
    db.refresh(company)
    
    # TODO: Create audit log entry (side effect)
    # TODO: May update tenant settings (side effect)
    
    return CompanyResponse(
        id=str(company.id),
        name=company.name,
        address=company.address,
        registrationNumber=company.registration_number,
        taxId=company.tax_id,
        contactName=company.contact_name,
        contactEmail=company.contact_email,
        contactPhone=company.contact_phone,
        financialYearStart=company.financial_year_start,
        currency=company.currency,
        industry=company.industry,
        companySize=company.company_size,
        createdAt=company.created_at.isoformat() if company.created_at else "",
        updatedAt=company.updated_at.isoformat() if company.updated_at else ""
    )
