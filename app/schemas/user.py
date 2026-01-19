"""
User Pydantic schemas for user management
"""
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    firstName: str = Field(..., min_length=2)
    lastName: Optional[str] = Field(None, min_length=2)
    role: str = "user"
    roleId: Optional[UUID] = None
    isActive: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    firstName: Optional[str] = Field(None, min_length=2)
    lastName: Optional[str] = Field(None, min_length=2)
    role: Optional[str] = None
    roleId: Optional[UUID] = None
    isActive: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(BaseModel):
    id: str
    email: str
    firstName: str
    lastName: Optional[str]
    role: str
    roleId: Optional[str] = None
    roleName: Optional[str] = None
    isActive: bool
    emailVerified: bool
    lastLoginAt: Optional[str]
    createdAt: Optional[str]


class UserListResponse(BaseModel):
    data: List[UserResponse]


class ChangeUserRoleRequest(BaseModel):
    role: str


class ChangeRoleResponse(BaseModel):
    message: str
    userId: str
    oldRole: str
    newRole: str