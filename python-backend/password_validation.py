"""
Password validation utilities for enforcing strong password policies.
"""
import re
from typing import Tuple


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength according to security policy.
    
    Requirements:
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
    
    # Check for common weak passwords
    common_passwords = [
        "password", "123456", "12345678", "qwerty", "abc123",
        "password123", "admin", "letmein", "welcome", "monkey"
    ]
    if password.lower() in common_passwords:
        return False, "Password is too common. Please choose a stronger password"
    
    return True, ""


def is_default_admin_password(password: str) -> bool:
    """
    Check if password is the default admin password.
    This should trigger a forced password change.
    """
    return password == "admin123"


def check_password_history(password: str, previous_hashes: list) -> Tuple[bool, str]:
    """
    Check if password was recently used (prevent password reuse).
    
    Args:
        password: New password to check
        previous_hashes: List of previous password hashes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
    
    for old_hash in previous_hashes:
        if pwd_context.verify(password, old_hash):
            return False, "Password was recently used. Please choose a different password"
    
    return True, ""
