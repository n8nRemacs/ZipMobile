import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.config import settings
from src.models.telegram_auth import (
    TelegramRegisterRequest,
    TelegramAuthResponse,
    TelegramAutoLoginRequest,
    TelegramAutoLoginResponse,
    TelegramUpdateAndLoginRequest,
    TelegramWebLoginRequest,
)
from src.services import telegram_auth_service

logger = logging.getLogger("tenant-auth")

router = APIRouter(prefix="/auth/v1/telegram", tags=["Telegram Auth"])


@router.post("/register")
async def telegram_register(req: TelegramRegisterRequest):
    """Register a new tenant via Telegram Mini App."""
    # Validate initData signature
    try:
        tg_user = telegram_auth_service.validate_init_data(
            req.init_data, settings.telegram_bot_token
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Register
    try:
        result = telegram_auth_service.register_via_telegram(
            phone=req.phone,
            name=req.name,
            company_name=req.company_name,
            city=req.city,
            address=req.address,
            available_channels=req.available_channels,
            preferred_channel=req.preferred_channel,
            tg_user=tg_user,
            telegram_phone=req.telegram_phone,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # User already exists — return 409 with their data
    if result.get("status") == "existing":
        return JSONResponse(
            status_code=409,
            content={
                "detail": "already_registered",
                "existing_user": {
                    "user_id": result["user_id"],
                    "tenant_id": result["tenant_id"],
                    "name": result.get("name"),
                    "phone": result.get("phone"),
                    "company_name": result.get("company_name"),
                    "city": result.get("city"),
                    "address": result.get("address"),
                    "available_channels": result.get("available_channels", []),
                    "preferred_channel": result.get("preferred_channel", "telegram"),
                },
            },
        )

    # New user created
    return TelegramAuthResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result.get("token_type", "bearer"),
        expires_in=result["expires_in"],
        user_id=result["user_id"],
        tenant_id=result["tenant_id"],
        is_new=result["is_new"],
    )


@router.post("/auto-login", response_model=TelegramAutoLoginResponse)
async def telegram_auto_login(req: TelegramAutoLoginRequest):
    """Auto-login via Telegram initData. Returns authenticated=false if not registered."""
    # Validate initData signature
    try:
        tg_user = telegram_auth_service.validate_init_data(
            req.init_data, settings.telegram_bot_token
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Try auto-login
    try:
        result = telegram_auth_service.auto_login_via_telegram(tg_user)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if result is None:
        return TelegramAutoLoginResponse(authenticated=False)

    return TelegramAutoLoginResponse(
        authenticated=True,
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result.get("token_type", "bearer"),
        expires_in=result["expires_in"],
        user_id=result["user_id"],
        tenant_id=result["tenant_id"],
        phone_verified=result.get("phone_verified", False),
    )


@router.post("/update-and-login", response_model=TelegramAuthResponse)
async def telegram_update_and_login(req: TelegramUpdateAndLoginRequest):
    """Update existing user profile and login."""
    # Validate initData signature
    try:
        tg_user = telegram_auth_service.validate_init_data(
            req.init_data, settings.telegram_bot_token
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    try:
        result = telegram_auth_service.update_and_login_via_telegram(
            tg_user=tg_user,
            phone=req.phone,
            telegram_phone=req.telegram_phone,
            name=req.name,
            company_name=req.company_name,
            city=req.city,
            address=req.address,
            available_channels=req.available_channels,
            preferred_channel=req.preferred_channel,
        )
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)

    return TelegramAuthResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result.get("token_type", "bearer"),
        expires_in=result["expires_in"],
        user_id=result["user_id"],
        tenant_id=result["tenant_id"],
        is_new=False,
    )


@router.post("/get-shared-phone")
async def get_shared_phone(req: TelegramAutoLoginRequest):
    """Get phone number shared via requestContact from bot updates."""
    try:
        tg_user = telegram_auth_service.validate_init_data(
            req.init_data, settings.telegram_bot_token
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    phone = telegram_auth_service.get_phone_from_bot_updates(tg_user["id"])
    return {"phone": phone}


@router.post("/web-login")
async def telegram_web_login(req: TelegramWebLoginRequest):
    """Login via Telegram Login Widget (web)."""
    # Validate Login Widget hash (different from initData!)
    try:
        telegram_auth_service.validate_login_widget(
            req.model_dump(), settings.telegram_bot_token
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Find user by telegram_chat_id
    try:
        result = telegram_auth_service.web_login_via_telegram(req.id)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="User not found. Please register via @zipmobile_bot",
        )

    return TelegramAuthResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result.get("token_type", "bearer"),
        expires_in=result["expires_in"],
        user_id=result["user_id"],
        tenant_id=result["tenant_id"],
        is_new=False,
    )
