from fastapi import APIRouter, HTTPException, Depends, Request

from src.dependencies import get_current_user
from src.models.user import UserProfile, UserUpdate, ChangePhoneRequest, ChangeEmailRequest, VerifyChangeRequest
from src.services import user_service, otp_service

router = APIRouter(prefix="/auth/v1/profile", tags=["Profile"])


@router.get("", response_model=UserProfile)
async def get_profile(request: Request):
    user = get_current_user(request)
    return UserProfile(
        id=user["id"],
        tenant_id=user["tenant_id"],
        phone=user["phone"],
        email=user.get("email"),
        email_verified=user.get("email_verified", False),
        phone_verified=user.get("phone_verified", False),
        name=user.get("name"),
        avatar_url=user.get("avatar_url"),
        role=user["role"],
        settings=user.get("settings") or {},
        created_at=user.get("created_at"),
    )


@router.patch("", response_model=UserProfile)
async def update_profile(body: UserUpdate, request: Request):
    user = get_current_user(request)
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    updated = user_service.update_user(user["id"], update_data)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update profile")

    return UserProfile(
        id=updated["id"],
        tenant_id=updated["tenant_id"],
        phone=updated["phone"],
        email=updated.get("email"),
        email_verified=updated.get("email_verified", False),
        phone_verified=updated.get("phone_verified", False),
        name=updated.get("name"),
        avatar_url=updated.get("avatar_url"),
        role=updated["role"],
        settings=updated.get("settings") or {},
        created_at=updated.get("created_at"),
    )


@router.post("/change-phone")
async def change_phone(body: ChangePhoneRequest, request: Request):
    user = get_current_user(request)
    # Check if new phone is already taken
    existing = user_service.get_user_by_phone(body.new_phone)
    if existing:
        raise HTTPException(status_code=409, detail="Phone number already in use")

    try:
        result = otp_service.send_otp(
            target=body.new_phone,
            target_type="phone",
            channel=body.otp_channel,
            purpose="change_phone",
        )
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))

    return {"message": "OTP sent to new phone", "channel": result["channel"], "expires_in": result["expires_in"]}


@router.post("/verify-phone")
async def verify_phone(body: VerifyChangeRequest, request: Request):
    """Verify the new phone number with OTP code."""
    user = get_current_user(request)

    # TODO: Добавить user_id в verification_codes для привязки OTP к пользователю.
    # Сейчас ищем последний неиспользованный OTP без привязки к user — для MVP приемлемо,
    # т.к. эксплуатация требует знания нового телефона И кода одновременно.
    from src.storage.supabase import get_supabase
    sb = get_supabase()
    otp_resp = (
        sb.table("verification_codes")
        .select("target")
        .eq("purpose", "change_phone")
        .eq("is_used", False)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not otp_resp.data:
        raise HTTPException(status_code=400, detail="No pending phone change")

    new_phone = otp_resp.data[0]["target"]

    try:
        otp_service.verify_otp(new_phone, body.code, "change_phone")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_service.change_phone(user["id"], new_phone)
    return {"message": "Phone number updated"}


@router.post("/change-email")
async def change_email(body: ChangeEmailRequest, request: Request):
    user = get_current_user(request)

    try:
        result = otp_service.send_otp(
            target=body.new_email,
            target_type="email",
            channel="email",
            purpose="change_email",
        )
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))

    return {"message": "OTP sent to new email", "channel": result["channel"], "expires_in": result["expires_in"]}


@router.post("/verify-email")
async def verify_email(body: VerifyChangeRequest, request: Request):
    """Verify the new email address with OTP code."""
    user = get_current_user(request)

    # TODO: Добавить user_id в verification_codes для привязки OTP к пользователю (аналогично verify-phone).
    from src.storage.supabase import get_supabase
    sb = get_supabase()
    otp_resp = (
        sb.table("verification_codes")
        .select("target")
        .eq("purpose", "change_email")
        .eq("is_used", False)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not otp_resp.data:
        raise HTTPException(status_code=400, detail="No pending email change")

    new_email = otp_resp.data[0]["target"]

    try:
        otp_service.verify_otp(new_email, body.code, "change_email")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_service.change_email(user["id"], new_email)
    return {"message": "Email updated"}
