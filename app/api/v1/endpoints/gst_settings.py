from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.gst import GSTSetting, TaxRate
from app.schemas.gst import (
    GSTSettingsCreate,
    GSTSettingsResponse,
    TaxRateResponse
)

router = APIRouter(prefix="/api/v1/gst-settings", tags=["GST Settings"])


def build_gst_settings_response(gst_setting, tax_rates):
    """Build GST settings response with tax rates"""
    tax_rates_list = [
        TaxRateResponse(
            id=str(tr.id),
            category=tr.category,
            rate=float(tr.rate),
            effectiveFrom=tr.effective_from.isoformat(),
            description=tr.description
        )
        for tr in tax_rates
    ]
    
    return GSTSettingsResponse(
        id=str(gst_setting.id),
        isGstApplicable=gst_setting.is_gst_applicable,
        gstNumber=gst_setting.gst_number,
        effectiveDate=gst_setting.effective_date.isoformat(),
        defaultRate=float(gst_setting.default_rate),
        displayFormat=gst_setting.display_format,
        filingFrequency=gst_setting.filing_frequency,
        taxRates=tax_rates_list,
        createdAt=gst_setting.created_at.isoformat() if gst_setting.created_at else "",
        updatedAt=gst_setting.updated_at.isoformat() if gst_setting.updated_at else ""
    )


@router.get("", response_model=GSTSettingsResponse)
def get_gst_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get GST/tax configuration for current tenant"""
    # 1. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 2. Query gst_settings WHERE tenant_id = ?
    gst_setting = db.query(GSTSetting).filter(
        GSTSetting.tenant_id == tenant_id
    ).first()
    
    if not gst_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GST settings not configured yet"
        )
    
    # 3. Include nested tax_rates
    tax_rates = db.query(TaxRate).filter(
        TaxRate.tenant_id == tenant_id
    ).order_by(TaxRate.category, TaxRate.effective_from.desc()).all()
    
    # 4. Return settings
    return build_gst_settings_response(gst_setting, tax_rates)


@router.post("", response_model=GSTSettingsResponse)
def create_or_update_gst_settings(
    payload: GSTSettingsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update GST settings with tax rates"""
    # 1. Verify user has admin role
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can modify GST settings"
        )
    
    # 2. Get tenant_id from JWT
    tenant_id = current_user.tenant_id
    
    # 3. Validate all fields (handled by Pydantic)
    # 4. If isGstApplicable = true, validate gstNumber format (handled by Pydantic)
    # 5. Validate filing frequency (handled by Pydantic)
    # 6. Validate all tax rates (handled by Pydantic)
    
    # 7. Check if settings exist
    existing_setting = db.query(GSTSetting).filter(
        GSTSetting.tenant_id == tenant_id
    ).first()
    
    if existing_setting:
        # UPDATE settings
        existing_setting.is_gst_applicable = payload.isGstApplicable
        existing_setting.gst_number = payload.gstNumber
        existing_setting.effective_date = payload.effectiveDate
        existing_setting.default_rate = payload.defaultRate
        existing_setting.display_format = payload.displayFormat
        existing_setting.filing_frequency = payload.filingFrequency
        existing_setting.updated_at = datetime.utcnow()
        
        gst_setting = existing_setting
        is_new = False
    else:
        # INSERT settings
        gst_setting_id = uuid4()
        gst_setting = GSTSetting(
            id=gst_setting_id,
            tenant_id=tenant_id,
            is_gst_applicable=payload.isGstApplicable,
            gst_number=payload.gstNumber,
            effective_date=payload.effectiveDate,
            default_rate=payload.defaultRate,
            display_format=payload.displayFormat,
            filing_frequency=payload.filingFrequency,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(gst_setting)
        is_new = True
    
    # 8. Delete existing tax rates for this tenant
    db.query(TaxRate).filter(
        TaxRate.tenant_id == tenant_id
    ).delete()
    
    # 9. Insert new tax rates with references to settings
    new_tax_rates = []
    if payload.taxRates:
        for tr in payload.taxRates:
            tax_rate = TaxRate(
                id=uuid4(),
                tenant_id=tenant_id,
                gst_setting_id=gst_setting.id,
                category=tr.category,
                rate=tr.rate,
                effective_from=tr.effectiveFrom,
                description=tr.description,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(tax_rate)
            new_tax_rates.append(tax_rate)
    
    db.commit()
    db.refresh(gst_setting)
    
    # Refresh tax rates
    tax_rates = db.query(TaxRate).filter(
        TaxRate.tenant_id == tenant_id
    ).order_by(TaxRate.category, TaxRate.effective_from.desc()).all()
    
    # 10. Return complete settings with tax rates
    response = build_gst_settings_response(gst_setting, tax_rates)
    
    # Set appropriate status code
    if is_new:
        return response
    else:
        return response
