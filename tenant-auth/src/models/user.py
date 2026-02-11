from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any


class UserProfile(BaseModel):
    id: str
    tenant_id: str
    phone: str
    email: str | None = None
    email_verified: bool = False
    phone_verified: bool = False
    name: str | None = None
    avatar_url: str | None = None
    role: str
    settings: dict[str, Any] = {}
    created_at: str | None = None


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    avatar_url: str | None = None
    settings: dict[str, Any] | None = None


class ChangePhoneRequest(BaseModel):
    new_phone: str = Field(..., pattern=r"^\+\d{10,15}$")
    otp_channel: str = Field(default="sms", pattern=r"^(sms|telegram|whatsapp|vk_max|console)$")


class ChangeEmailRequest(BaseModel):
    new_email: str


class VerifyChangeRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=8)
