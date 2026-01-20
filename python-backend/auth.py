import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_db_connection, current_user_context
from models import User, UserCreate, Token, TokenData
from cache import get_cached, set_cached, TTL_USER

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, hashed_password, is_admin, staff_id, created_at
        FROM users WHERE username = ?
    """, (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "hashed_password": row[3],
            "is_admin": bool(row[4]),
            "staff_id": row[5],
            "created_at": row[6]
        }
    return None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, is_admin, staff_id, created_at
        FROM users WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "is_admin": bool(row[3]),
            "staff_id": row[4],
            "created_at": row[5]
        }
    return None


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user."""
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_user(user: UserCreate) -> Dict[str, Any]:
    """Create a new user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user.password)
    
    cursor.execute("""
        INSERT INTO users (id, username, email, hashed_password, is_admin, staff_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, user.username, user.email, hashed_password, int(user.is_admin), user.staff_id))
    
    conn.commit()
    conn.close()
    
    return {
        "id": user_id,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "staff_id": user.staff_id
    }


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        is_admin: bool = payload.get("is_admin", False)
        
        if user_id is None:
            raise credentials_exception
            
        token_data = TokenData(user_id=user_id, username=username, is_admin=is_admin)
    except JWTError:
        raise credentials_exception
    
    # Try to get from cache first
    cache_key = f"user:{user_id}"
    user = await get_cached(cache_key)
    
    if user is None:
        user = get_user_by_id(user_id)
        if user:
            # Cache the result
            await set_cached(cache_key, user, TTL_USER)
            
    if user is None:
        raise credentials_exception
    
    # Set user context for RLS
    current_user_context.set(user)
    
    return user


async def get_current_active_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current active user."""
    return current_user


async def get_current_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current admin user."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


# Optional authentication for public endpoints
async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[Dict[str, Any]]:
    """Get current user if token is provided, None otherwise."""
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            return None
            
        user = get_user_by_id(user_id)
        if user:
            current_user_context.set(user)
        return user
    except JWTError:
        return None
