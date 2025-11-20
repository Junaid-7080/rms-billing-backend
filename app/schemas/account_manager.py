# app/schemas/account_manager.py
from pydantic import BaseModel, EmailStr
from typing import List

class AccountManagerResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    isActive: bool

class AccountManagerListResponse(BaseModel):
    root: List[AccountManagerResponse]

# ✅ Add this schema for creating new managers
class AccountManagerCreateRequest(BaseModel):
    name: str
    email: EmailStr
    isActive: bool = True