from pydantic import BaseModel, EmailStr, RootModel
from typing import List

class AccountManagerResponse(BaseModel):
    id: str
    name: str
    email: str
    isActive: bool

class AccountManagerListResponse(RootModel):
    root: List[AccountManagerResponse]
