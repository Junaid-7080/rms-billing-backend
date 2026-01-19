"""Pydantic schemas for role management"""
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


class RoleBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    isActive: bool = True


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    isActive: Optional[bool] = None


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    permissions: Optional[Dict[str, Any]]
    isSystem: bool
    isActive: bool
    createdAt: Optional[str]
    updatedAt: Optional[str]


class RoleListResponse(BaseModel):
    data: List[RoleResponse]
