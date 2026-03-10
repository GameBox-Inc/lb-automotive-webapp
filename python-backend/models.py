from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID, uuid4
import logging

logger = logging.getLogger(__name__)

def parse_db_datetime(v: Any) -> Optional[datetime]:
    """Liberal datetime parser for SQLite/Postgres strings."""
    if v is None or isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            # Handle PostgreSQL format: '2026-03-09 21:08:05.39735+00'
            cleaned_v = v.strip()
            if ' ' in cleaned_v:
                cleaned_v = cleaned_v.replace(' ', 'T', 1)
            if cleaned_v.endswith('+00'):
                cleaned_v = cleaned_v.replace('+00', '+00:00')
            return datetime.fromisoformat(cleaned_v)
        except ValueError:
            # Fallback for other non-ISO formats
            from dateutil.parser import parse
            return parse(v)
    return v


class Service(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    duration: int  # in minutes
    price: float
    is_emergency: bool = False
    category: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_dates(cls, v):
        return parse_db_datetime(v)

    model_config = ConfigDict(from_attributes=True)


class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    duration: int  # in minutes
    price: float
    is_emergency: bool = False
    category: str


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    price: Optional[float] = None
    is_emergency: Optional[bool] = None
    category: Optional[str] = None


class AppointmentCreate(BaseModel):
    customer_name: str
    phone_number: str
    appointment_time: datetime
    service_type: str
    notes: Optional[str] = None
    emergency_request: bool = False


class AppointmentUpdate(BaseModel):
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    appointment_time: Optional[datetime] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    emergency_request: Optional[bool] = None
    assigned_staff_id: Optional[str] = None


class Appointment(BaseModel):
    id: str
    customer_name: str
    phone_number: str
    appointment_time: datetime
    service_type: str
    notes: Optional[str] = None
    status: str = "pending"
    emergency_request: bool = False
    assigned_staff_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None

    @field_validator("appointment_time", "created_at", "updated_at", "started_at", mode="before")
    @classmethod
    def validate_dates(cls, v):
        return parse_db_datetime(v)

    model_config = ConfigDict(from_attributes=True)


class CallState(BaseModel):
    id: Optional[str] = None
    call_sid: str
    current_step: str
    language: str = "en"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    appointment_id: Optional[str] = None
    last_response_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("last_response_time", "created_at", "updated_at", mode="before")
    @classmethod
    def validate_dates(cls, v):
        return parse_db_datetime(v)

    model_config = ConfigDict(from_attributes=True)


class IVRLog(BaseModel):
    id: Optional[str] = None
    call_sid: str
    step: str
    input: Optional[str] = None
    created_at: Optional[datetime] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_dates(cls, v):
        return parse_db_datetime(v)

    model_config = ConfigDict(from_attributes=True)


class User(BaseModel):
    id: Optional[str] = None
    username: str
    email: Optional[str] = None
    is_admin: bool = False
    staff_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    is_admin: bool = False
    staff_id: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
    is_admin: bool = False


class Setting(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class SettingUpdate(BaseModel):
    value: str


class CaseNote(BaseModel):
    id: str
    case_id: str
    staff_id: str
    note: str
    is_internal: bool = True
    created_at: Optional[datetime] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_dates(cls, v):
        return parse_db_datetime(v)

    model_config = ConfigDict(from_attributes=True)


class CaseNoteCreate(BaseModel):
    note: str
    is_internal: bool = True


class CasePart(BaseModel):
    id: str
    case_id: str
    part_name: str
    quantity: int = 1
    price: float = 0.0
    status: str = "pending"
    created_at: Optional[datetime] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_dates(cls, v):
        return parse_db_datetime(v)

    model_config = ConfigDict(from_attributes=True)


class CasePartCreate(BaseModel):
    part_name: str
    quantity: int = 1
    price: float = 0.0


class Case(BaseModel):
    id: str
    case_number: Optional[int] = None
    appointment_id: str
    status: str = "open"
    customer_signature: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    @field_validator("created_at", "started_at", "closed_at", mode="before")
    @classmethod
    def validate_dates(cls, v):
        return parse_db_datetime(v)
    notes: List[CaseNote] = []
    parts: List[CasePart] = []

    model_config = ConfigDict(from_attributes=True)


class CaseCreate(BaseModel):
    appointment_id: str
    metadata: Optional[Dict[str, Any]] = None


class CaseUpdate(BaseModel):
    status: Optional[str] = None
    customer_signature: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class StaffSchedule(BaseModel):
    id: str
    staff_id: str
    day_of_week: int
    start_time: str
    end_time: str
    is_off: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_dates(cls, v):
        return parse_db_datetime(v)

    model_config = ConfigDict(from_attributes=True)


class StaffScheduleUpdate(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str
    is_off: bool = False


class StaffCreate(BaseModel):
    name: str
    role: str
    active: bool = True


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None


class BusinessHours(BaseModel):
    day_of_week: int  # 0=Monday, 6=Sunday
    day_name: str  # "Monday", "Tuesday", etc.
    opening_time: Optional[str] = None  # HH:MM format
    closing_time: Optional[str] = None  # HH:MM format
    is_closed: bool = False
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BusinessHoursUpdate(BaseModel):
    opening_time: Optional[str] = None  # HH:MM format, None if closed
    closing_time: Optional[str] = None  # HH:MM format, None if closed
    is_closed: bool = False
