import logging
import time
import functools
from typing import Any, Callable, Type, Tuple, Optional

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    """Raised when the circuit is open and calls are rejected."""
    pass

class CircuitBreaker:
    """
    Simple Circuit Breaker implementation.
    States: CLOSED (Normal), OPEN (Failing), HALF-OPEN (Testing)
    """
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.failures = 0
        self.last_failure_time = 0
        self.is_open = False
        
    def allow_request(self) -> bool:
        if not self.is_open:
            return True
        
        # Check if enough time has passed to try again (Half-Open)
        if time.time() - self.last_failure_time > self.recovery_timeout:
            logger.info(f"Circuit {self.name} is HALF-OPEN. Probing service...")
            return True
            
        return False
        
    def record_success(self):
        if self.is_open:
            logger.info(f"Circuit {self.name} closed. Service recovered.")
        self.failures = 0
        self.is_open = False
        
    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.failure_threshold:
            if not self.is_open:
                logger.warning(f"Circuit {self.name} OPENED after {self.failures} failures.")
            self.is_open = True

# Global registry for circuit breakers
_breakers = {}

def get_breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name)
    return _breakers[name]

def graceful_fallback(
    fallback_value: Any = None, 
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    circuit_name: Optional[str] = None
):
    """
    Decorator to gracefully handle exceptions and return a fallback value.
    
    Args:
        fallback_value: The value to return if an exception occurs. Can be a value or a callable.
        exceptions: Tuple of exception types to catch.
        circuit_name: Optional name for a Circuit Breaker to protect this function.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            breaker = get_breaker(circuit_name) if circuit_name else None
            
            # 1. Circuit Breaker Check
            if breaker and not breaker.allow_request():
                logger.warning(f"Circuit {circuit_name} is open. Returning fallback.")
                return _resolve_fallback(fallback_value, *args, **kwargs)
            
            try:
                # 2. Attempt Execution
                result = func(*args, **kwargs)
                
                # 3. Success - Reset Circuit
                if breaker:
                    breaker.record_success()
                return result
                
            except exceptions as e:
                # 4. Failure - Trip Circuit
                logger.error(f"Error in {func.__name__}: {e}. Falling back.")
                if breaker:
                    breaker.record_failure()
                
                return _resolve_fallback(fallback_value, *args, **kwargs)
                
        return wrapper
    return decorator

def _resolve_fallback(fallback, *args, **kwargs):
    """Helper to determine if fallback is a value or a function."""
    if callable(fallback):
        return fallback(*args, **kwargs)
    return fallback
