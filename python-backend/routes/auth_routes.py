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
from fastapi.responses import JSONResponse
from password_validation import validate_password_strength
import uuid
import random
import os
from security import redis_client

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.get("/captcha")
async def get_captcha():
    """Generate a captcha token for checkbox verification."""
    import time
    captcha_id = str(uuid.uuid4())
    
    # Store token with creation timestamp in Redis (5 minute expiry)
    if redis_client:
        redis_client.setex(f"captcha:{captcha_id}", 300, str(time.time()))
    
    return {
        "captcha_id": captcha_id
    }


@router.post("/verify-captcha")
async def verify_captcha(captcha_id: str = Form(...)):
    """Verify checkbox captcha with bot detection."""
    import time
    import logging
    logger = logging.getLogger(__name__)
    
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Captcha service unavailable"
        )
    
    # Check if captcha exists
    created_at = redis_client.get(f"captcha:{captcha_id}")
    if not created_at:
        logger.warning(f"Invalid or expired captcha: {captcha_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired captcha"
        )
    
    # Bot detection: check if checkbox was clicked too quickly (< 1 second)
    time_elapsed = time.time() - float(created_at)
    if time_elapsed < 1.0:
        logger.warning(f"Captcha clicked too quickly ({time_elapsed:.2f}s): likely bot")
        redis_client.delete(f"captcha:{captcha_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification failed"
        )
    
    # Mark as verified by updating the value
    redis_client.setex(f"captcha:{captcha_id}", 300, "verified")
    logger.info(f"Captcha verified successfully: {captcha_id}")
    
    return {"verified": True}



@router.post("/register", response_model=User)
def register(user: UserCreate):
    """Register a new user."""
    from database import get_db_connection
    import logging
    logger = logging.getLogger(__name__)
    
    # Validate password strength
    is_valid, error_message = validate_password_strength(user.password)
    if not is_valid:
        logger.warning(f"Registration failed: Weak password for user {user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
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
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    captcha_id: str = Form(None)
):
    """Login and get access token with optional CAPTCHA."""
    import logging
    logger = logging.getLogger(__name__)

    # Enforce CAPTCHA verification
    if captcha_id and redis_client:
        verification_status = redis_client.get(f"captcha:{captcha_id}")
        if verification_status != "verified":
            logger.warning(f"CAPTCHA not verified for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please verify you are human"
            )
        # Delete after use
        redis_client.delete(f"captcha:{captcha_id}")

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
