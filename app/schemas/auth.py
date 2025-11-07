from pydantic import BaseModel, EmailStr, constr
from typing import Optional, Annotated

# ✅ Proper Annotated type definitions (Pylance + Pydantic v2 compatible)
PasswordStr = Annotated[str, constr(min_length=8)]
ShortStr = Annotated[str, constr(min_length=2)]

# ✅ Nested Models
class UserOut(BaseModel):
    id: int
    email: EmailStr
    firstName: str
    lastName: Optional[str] = None

class TenantOut(BaseModel):
    id: int
    companyName: str
    companySlug: str

class TokenOut(BaseModel):
    accessToken: str
    refreshToken: str

# ✅ Request & Response Models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: PasswordStr
    firstName: ShortStr
    lastName: Optional[ShortStr] = None
    companyName: ShortStr
    companySlug: ShortStr

class RegisterResponse(BaseModel):
    user: UserOut
    tenant: TenantOut
    message: str = "User created successfully"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    user: UserOut
    tenant: TenantOut
    tokens: TokenOut
