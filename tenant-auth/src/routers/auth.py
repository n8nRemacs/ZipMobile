import logging
from fastapi import APIRouter, HTTPException

from src.models.auth import (
    RegisterRequest, LoginRequest, VerifyOtpRequest,
    RefreshRequest, TokenPair, OtpSentResponse, LogoutRequest,
)
from src.models.telegram_auth import (
    WebRegisterViaTelegramRequest,
    WebRegisterViaTelegramResponse,
)
from src.services import otp_service, jwt_service, user_service, telegram_auth_service
from src.config import settings

logger = logging.getLogger("tenant-auth")

router = APIRouter(prefix="/auth/v1", tags=["Auth"])


@router.post("/register", response_model=OtpSentResponse)
async def register(req: RegisterRequest):
    """Register a new tenant. Sends OTP to phone for verification."""
    # Check if phone already registered
    existing = user_service.get_user_by_phone(req.phone)
    if existing:
        raise HTTPException(status_code=409, detail="Phone number already registered")

    # Create tenant + user
    try:
        user = user_service.create_tenant_and_user(req.phone, req.email, req.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Send OTP
    try:
        result = otp_service.send_otp(
            target=req.phone,
            target_type="phone",
            channel=req.otp_channel,
            purpose="register",
        )
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))

    return OtpSentResponse(
        message="OTP sent for registration",
        channel=result["channel"],
        expires_in=result["expires_in"],
    )


@router.post("/login", response_model=OtpSentResponse)
async def login(req: LoginRequest):
    """Request OTP for login."""
    user = user_service.get_user_by_phone(req.phone)
    if not user:
        raise HTTPException(status_code=404, detail="Phone number not registered")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")

    try:
        result = otp_service.send_otp(
            target=req.phone,
            target_type="phone",
            channel=req.otp_channel,
            purpose="login",
        )
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))

    return OtpSentResponse(
        message="OTP sent for login",
        channel=result["channel"],
        expires_in=result["expires_in"],
    )


@router.post("/verify-otp", response_model=TokenPair)
async def verify_otp(req: VerifyOtpRequest):
    """Verify OTP code and return JWT pair."""
    try:
        otp_service.verify_otp(req.phone, req.code, req.purpose)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = user_service.get_user_by_phone(req.phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Handle purpose-specific logic
    if req.purpose == "register":
        user_service.set_phone_verified(user["id"])
        # Send email verification OTP
        if user.get("email"):
            try:
                otp_service.send_otp(
                    target=user["email"],
                    target_type="email",
                    channel="email",
                    purpose="verify_email",
                )
            except ValueError:
                logger.warning("Failed to send email verification OTP to %s", user.get("email"))

    elif req.purpose == "login":
        if not user.get("phone_verified"):
            user_service.set_phone_verified(user["id"])

    elif req.purpose == "verify_email":
        if req.email:
            user_service.set_email_verified(user["id"])
        else:
            user_service.set_email_verified(user["id"])

    elif req.purpose == "change_phone":
        # Смена телефона идёт через /profile/change-phone → /profile/verify-phone
        # Через общий /verify-otp не поддерживается (нужен JWT контекст)
        pass

    elif req.purpose == "change_email":
        # Смена email идёт через /profile/change-email → /profile/verify-email
        # Через общий /verify-otp не поддерживается (нужен JWT контекст)
        pass

    # Create JWT pair
    token_pair = jwt_service.create_token_pair(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
    )

    return TokenPair(**token_pair)


@router.post("/refresh", response_model=TokenPair)
async def refresh(req: RefreshRequest):
    """Rotate refresh token and return new JWT pair."""
    try:
        token_pair = jwt_service.rotate_refresh_token(req.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    return TokenPair(**token_pair)


@router.post("/logout")
async def logout(req: LogoutRequest):
    """Revoke a refresh token (logout from one device)."""
    jwt_service.revoke_refresh_token(req.refresh_token)
    return {"message": "Logged out"}


@router.post("/logout-all")
async def logout_all(req: LogoutRequest):
    """Revoke all refresh tokens for the user (logout from all devices)."""
    # We need to find the user from the refresh token
    import hashlib
    from src.storage.supabase import get_supabase

    token_hash = hashlib.sha256(req.refresh_token.encode()).hexdigest()
    sb = get_supabase()
    resp = sb.table("refresh_tokens").select("user_id").eq("token_hash", token_hash).execute()
    if not resp.data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = resp.data[0]["user_id"]
    count = jwt_service.revoke_all_user_tokens(user_id)
    return {"message": f"Revoked {count} sessions"}


@router.post("/register-via-telegram", response_model=WebRegisterViaTelegramResponse)
async def register_via_telegram(req: WebRegisterViaTelegramRequest):
    """Register or login via Telegram Login Widget / Dev Login."""
    # If hash is provided, validate Login Widget signature
    if req.hash and req.auth_date:
        widget_data: dict = {
            "id": req.telegram_id,
            "first_name": req.first_name,
            "auth_date": req.auth_date,
            "hash": req.hash,
        }
        if req.last_name:
            widget_data["last_name"] = req.last_name
        if req.username:
            widget_data["username"] = req.username
        if req.photo_url:
            widget_data["photo_url"] = req.photo_url
        try:
            telegram_auth_service.validate_login_widget(
                widget_data,
                settings.telegram_bot_token,
            )
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    # Register or login
    try:
        result = telegram_auth_service.register_or_login_via_web(
            telegram_id=req.telegram_id,
            username=req.username,
            first_name=req.first_name,
            last_name=req.last_name,
            photo_url=req.photo_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return WebRegisterViaTelegramResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result.get("token_type", "bearer"),
        expires_in=result["expires_in"],
        is_new_user=result["is_new_user"],
    )
