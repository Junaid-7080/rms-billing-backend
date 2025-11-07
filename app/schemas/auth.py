# pyright: reportInvalidTypeForm=false
from pydantic import BaseModel, EmailStr, constr
from typing import Optional

PasswordStr = constr(min_length=8)
ShortStr = constr(min_length=2)

class RegisterRequest(BaseModel):
    email: EmailStr
    password: PasswordStr
    firstName: ShortStr
    lastName: Optional[ShortStr] = None
    companyName: ShortStr
    companySlug: ShortStr

class RegisterResponse(BaseModel):
    user: dict
    tenant: dict
    message: str


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    message: str
    user: dict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user: dict
    tenant: dict
    tokens: dict


class RefreshTokenRequest(BaseModel):
    refreshToken: str


class RefreshTokenResponse(BaseModel):
    accessToken: str
    expiresIn: int


class LogoutResponse(BaseModel):
    message: str
