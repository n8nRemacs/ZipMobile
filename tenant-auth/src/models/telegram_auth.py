from pydantic import BaseModel, Field


class TelegramRegisterRequest(BaseModel):
    """Регистрация через Telegram Mini App."""
    init_data: str
    phone: str = Field(..., pattern=r"^\+\d{10,15}$")
    telegram_phone: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    company_name: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    address: str | None = None
    available_channels: list[str] = Field(..., min_length=1)
    preferred_channel: str = "telegram"


class TelegramAuthResponse(BaseModel):
    """Ответ авторизации — JWT-пара."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    tenant_id: str
    is_new: bool


class TelegramAutoLoginRequest(BaseModel):
    """Автологин — только initData."""
    init_data: str


class TelegramAutoLoginResponse(BaseModel):
    """Результат автологина."""
    authenticated: bool
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    phone_verified: bool | None = None


class TelegramWebLoginRequest(BaseModel):
    """Данные от Telegram Login Widget."""
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class ExistingUserData(BaseModel):
    """Данные существующего пользователя при попытке повторной регистрации."""
    user_id: str
    tenant_id: str
    name: str | None = None
    phone: str | None = None
    company_name: str | None = None
    city: str | None = None
    address: str | None = None
    available_channels: list[str] = []
    preferred_channel: str = "telegram"


class TelegramUpdateAndLoginRequest(BaseModel):
    """Обновление профиля + вход для уже зарегистрированного пользователя."""
    init_data: str
    phone: str | None = Field(None, pattern=r"^\+\d{10,15}$")
    telegram_phone: str | None = None
    name: str | None = Field(None, min_length=1, max_length=200)
    company_name: str | None = Field(None, min_length=1, max_length=200)
    city: str | None = Field(None, min_length=1, max_length=100)
    address: str | None = None
    available_channels: list[str] | None = None
    preferred_channel: str | None = None
