from fastapi import APIRouter, Request

from src.dependencies import get_current_user
from src.models.notification import NotificationPrefResponse, NotificationPrefsUpdate, NotificationHistoryItem
from src.services import notification_service

router = APIRouter(prefix="/auth/v1/notifications", tags=["Notifications"])


@router.get("/preferences", response_model=list[NotificationPrefResponse])
async def get_preferences(request: Request):
    user = get_current_user(request)
    prefs = notification_service.get_preferences(user["id"])
    return [NotificationPrefResponse(**p) for p in prefs]


@router.put("/preferences", response_model=list[NotificationPrefResponse])
async def update_preferences(body: NotificationPrefsUpdate, request: Request):
    user = get_current_user(request)
    prefs = notification_service.update_preferences(
        user["id"],
        [p.model_dump() for p in body.preferences],
    )
    return [NotificationPrefResponse(**p) for p in prefs]


@router.get("/history", response_model=list[NotificationHistoryItem])
async def get_history(request: Request, limit: int = 50):
    user = get_current_user(request)
    history = notification_service.get_history(user["id"], limit=limit)
    return [NotificationHistoryItem(**h) for h in history]
