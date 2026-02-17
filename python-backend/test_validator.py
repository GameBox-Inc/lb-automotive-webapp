
import os
from twilio.request_validator import RequestValidator

try:
    path = os.getenv("TWILIO_AUTH_TOKEN")
    print(f"Token from env: {path}")
    validator = RequestValidator(path)
    print("Validator initialized successfully")
except Exception as e:
    print(f"Error initializing validator: {e}")
