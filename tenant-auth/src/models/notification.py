from pydantic import BaseModel, Field


class NotificationPref(BaseModel):
    channel: str = Field(..., pattern=r"^(sms|telegram|whatsapp|vk_max|email)$")
    event_type: str
    is_enabled: bool = True


class NotificationPrefResponse(BaseModel):
    id: str
    user_id: str
    channel: str
    event_type: str
    is_enabled: bool


class NotificationPrefsUpdate(BaseModel):
    preferences: list[NotificationPref]


class NotificationHistoryItem(BaseModel):
    id: int
    channel: str
    event_type: str
    title: str | None = None
    body: str | None = None
    is_read: bool = False
    created_at: str | None = None
