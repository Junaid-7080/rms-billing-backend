from uuid import UUID, uuid4
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    ChangeUserRoleRequest,
)

router = APIRouter(prefix="/auth/users", tags=["Users"])


async def get_current_manager_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or Admin access required",
        )
    return current_user


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        firstName=user.first_name or "",
        lastName=user.last_name,
        role=user.role,
        isActive=user.is_active,
        emailVerified=user.email_verified,
        lastLoginAt=user.last_login_at.isoformat() if user.last_login_at else None,
        createdAt=user.created_at.isoformat() if user.created_at else None,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin),
):
    tenant_id = current_user.tenant_id

    users: List[User] = (
        db.query(User)
        .filter(
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
        .order_by(User.created_at.asc())
        .all()
    )

    return UserListResponse(data=[_to_user_response(u) for u in users])


@router.get("/{id}", response_model=UserResponse)
async def get_user(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin),
):
    user = (
        db.query(User)
        .filter(
            User.id == id,
            User.tenant_id == current_user.tenant_id,
            User.deleted_at.is_(None),
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _to_user_response(user)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    tenant_id = admin_user.tenant_id

    existing = (
        db.query(User)
        .filter(
            User.tenant_id == tenant_id,
            User.email == payload.email,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists for this tenant",
        )

    # Use same password hashing as auth.register
    from app.core.security import hash_password  # top-level import in real code

    user = User(
        id=uuid4(),
        tenant_id=tenant_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.firstName,
        last_name=payload.lastName,
        role=payload.role,
        is_active=payload.isActive,
        email_verified=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return _to_user_response(user)


@router.put("/{id}", response_model=UserResponse)
async def update_user(
    id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    tenant_id = admin_user.tenant_id

    user = (
        db.query(User)
        .filter(
            User.id == id,
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if payload.firstName is not None:
        user.first_name = payload.firstName
    if payload.lastName is not None:
        user.last_name = payload.lastName
    if payload.role is not None:
        user.role = payload.role
    if payload.isActive is not None:
        user.is_active = payload.isActive

    db.commit()
    db.refresh(user)

    return _to_user_response(user)


@router.delete("/{id}")
async def delete_user(
    id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    tenant_id = admin_user.tenant_id

    user = (
        db.query(User)
        .filter(
            User.id == id,
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Soft delete
    from datetime import datetime

    user.deleted_at = datetime.utcnow()
    user.is_active = False

    db.commit()

    return {"message": "User deleted successfully"}


@router.patch("/{id}/change-role", response_model=UserResponse)
async def change_user_role(
    id: UUID,
    payload: ChangeUserRoleRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    tenant_id = admin_user.tenant_id

    user = (
        db.query(User)
        .filter(
            User.id == id,
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.role = payload.role
    db.commit()
    db.refresh(user)

    return _to_user_response(user)