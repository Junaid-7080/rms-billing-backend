from datetime import datetime, timedelta
from typing import Optional, Union
from uuid import UUID
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer authentication
security = HTTPBearer()

# -------------------------
# PASSWORD UTILITIES
# -------------------------
def hash_password(password: str) -> str:
    """Hash a plain password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


# -------------------------
# TOKEN CREATION
# -------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    # Convert UUID to string if present
    if "sub" in to_encode and isinstance(to_encode["sub"], UUID):
        to_encode["sub"] = str(to_encode["sub"])
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    
    # Convert UUID to string if present
    if "sub" in to_encode and isinstance(to_encode["sub"], UUID):
        to_encode["sub"] = str(to_encode["sub"])
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# -------------------------
# TOKEN VERIFICATION
# -------------------------
def verify_token(token: str, token_type: str = "access") -> dict:
    """
    Verify and decode a JWT token
    
    Args:
        token: JWT token string
        token_type: Expected token type ('access' or 'refresh')
    
    Returns:
        Decoded token payload
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # Check token type if specified in payload
        if payload.get("type") and payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}"
            )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def decode_access_token(token: str) -> Optional[dict]:
    """Decode access token without raising exceptions"""
    try:
        return verify_token(token, token_type="access")
    except:
        return None


# -------------------------
# USER ID PARSING UTILITY
# -------------------------
def parse_user_id(user_id_raw: Union[str, int, UUID]) -> Union[str, int, UUID]:
    """
    Parse user ID from token to appropriate type
    Supports: int, UUID string, UUID object
    """
    if user_id_raw is None:
        raise ValueError("User ID is None")
    
    # If already UUID object, convert to string
    if isinstance(user_id_raw, UUID):
        return str(user_id_raw)
    
    # If string, check if it's UUID format
    if isinstance(user_id_raw, str):
        # Check if it's UUID format (contains hyphens)
        if "-" in user_id_raw:
            try:
                # Validate UUID format
                UUID(user_id_raw)
                return user_id_raw  # Return as string
            except ValueError:
                raise ValueError("Invalid UUID format")
        
        # Check if it's a numeric string
        if user_id_raw.isdigit():
            return int(user_id_raw)
        
        # Otherwise return as is
        return user_id_raw
    
    # If integer, return as is
    if isinstance(user_id_raw, int):
        return user_id_raw
    
    raise ValueError(f"Unsupported user ID type: {type(user_id_raw)}")


# -------------------------
# DEPENDENCY FUNCTIONS
# -------------------------
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Extract current user from JWT token
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Verify token and get payload
    payload = verify_token(token, token_type="access")
    
    # Extract and parse user ID
    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: user ID missing"
        )
    
    try:
        user_id = parse_user_id(user_id_raw)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Fetch user from database
    user = db.query(User).filter(
        User.id == user_id,
        User.is_active == True
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (additional check)
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


# -------------------------
# ROLE-BASED ACCESS CONTROL
# -------------------------
def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based access control
    
    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
        @router.get("/staff", dependencies=[Depends(require_role("admin", "manager"))])
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = getattr(current_user, "role", None)
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        return current_user
    
    return role_checker


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Shortcut dependency for admin-only access"""
    user_role = getattr(current_user, "role", None)
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_manager(current_user: User = Depends(get_current_user)) -> User:
    """Shortcut dependency for manager+ access"""
    user_role = getattr(current_user, "role", None)
    if user_role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin access required"
        )
    return current_user