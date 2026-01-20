from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from models import Token, UserCreate, User

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=User)
def register(user: UserCreate):
    """Register a new user."""
    from database import get_db_connection
    import logging
    logger = logging.getLogger(__name__)
    
    # Check if username already exists
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (user.username,))
    existing = cursor.fetchone()
    conn.close()
    
    if existing:
        logger.warning(f"Registration failed: Username {user.username} already exists")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    created_user = create_user(user)
    logger.info(f"New user registered: {user.username}")
    return User(**created_user)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    import logging
    logger = logging.getLogger(__name__)

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"Login failed for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"],
            "staff_id": user["staff_id"]
        },
        expires_delta=access_token_expires
    )
    
    logger.info(f"User logged in successfully: {user['username']}")
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=User)
def read_users_me(current_user: dict = Depends(get_current_active_user)):
    """Get current user info."""
    return User(**current_user)
