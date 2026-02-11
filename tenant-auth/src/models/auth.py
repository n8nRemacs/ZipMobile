from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+\d{10,15}$")
    email: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    otp_channel: str = Field(default="sms", pattern=r"^(sms|telegram|whatsapp|vk_max|console)$")


class LoginRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+\d{10,15}$")
    otp_channel: str = Field(default="sms", pattern=r"^(sms|telegram|whatsapp|vk_max|console)$")


class VerifyOtpRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+\d{10,15}$")
    code: str = Field(..., min_length=4, max_length=8)
    purpose: str = Field(..., pattern=r"^(register|login|verify_email|change_phone|change_email)$")
    email: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class OtpSentResponse(BaseModel):
    message: str = "OTP sent"
    channel: str
    expires_in: int


class LogoutRequest(BaseModel):
    refresh_token: str
