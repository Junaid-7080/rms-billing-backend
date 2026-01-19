"""Role management endpoints"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.role import Role
from app.models.user import User
from app.schemas.role import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
)

router = APIRouter(prefix="/roles", tags=["Roles"])





def _to_role_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=str(role.id),
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        isSystem=role.is_system,
        isActive=role.is_active,
        createdAt=role.created_at.isoformat() if role.created_at else None,
        updatedAt=role.updated_at.isoformat() if role.updated_at else None,
    )


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    tenant_id = admin_user.tenant_id

    existing = (
        db.query(Role)
        .filter(Role.tenant_id == tenant_id, Role.name == payload.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role name already exists for this tenant",
        )

    role = Role(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        permissions=payload.permissions,
        is_active=payload.isActive,
        is_system=False,
    )

    db.add(role)
    db.commit()
    db.refresh(role)

    return _to_role_response(role)


@router.get("", response_model=RoleListResponse)
def list_roles(
    isActive: Optional[bool] = None,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    query = db.query(Role).filter(Role.tenant_id == admin_user.tenant_id)
    
    if isActive is not None:
        query = query.filter(Role.is_active == isActive)
        
    roles = query.order_by(Role.name.asc()).all()
    return RoleListResponse(data=[_to_role_response(role) for role in roles])


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    role = (
        db.query(Role)
        .filter(Role.id == role_id, Role.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return _to_role_response(role)


@router.patch("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    role = (
        db.query(Role)
        .filter(Role.id == role_id, Role.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if payload.name and payload.name != role.name:
        duplicate = (
            db.query(Role)
            .filter(
                Role.tenant_id == admin_user.tenant_id,
                Role.name == payload.name,
                Role.id != role.id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another role with this name already exists",
            )
        role.name = payload.name

    if payload.description is not None:
        role.description = payload.description

    if payload.permissions is not None:
        role.permissions = payload.permissions

    if payload.isActive is not None:
        role.is_active = payload.isActive

    db.commit()
    db.refresh(role)
    return _to_role_response(role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    role = (
        db.query(Role)
        .filter(Role.id == role_id, Role.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System roles cannot be deleted",
        )

    db.delete(role)
    db.commit()

    return None
